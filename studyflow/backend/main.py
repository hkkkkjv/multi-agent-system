"""
FastAPI backend StudyFlow — с памятью и загрузкой документов.
"""
import os
import logging
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="StudyFlow API", version="1.0")

try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app)
except ImportError:
    pass

_graph = None
_langfuse = None


def get_graph():
    global _graph
    if _graph is None:
        from graph import graph
        _graph = graph
    return _graph


def get_langfuse():
    global _langfuse
    if _langfuse is not None:
        return _langfuse
    pk = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    sk = os.getenv("LANGFUSE_SECRET_KEY", "")
    if not pk or pk in ("pk-lf-", "pk-lf-xxx") or not sk or sk in ("sk-lf-", "sk-lf-xxx"):
        return None
    try:
        from langfuse import Langfuse
        _langfuse = Langfuse(
            public_key=pk,
            secret_key=sk,
            host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
        )
        logger.info("Langfuse initialized")
    except Exception as e:
        logger.warning(f"Langfuse init failed: {e}")
    return _langfuse


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    answer: str
    quality_score: float
    route: str


@app.on_event("startup")
async def startup():
    try:
        get_graph()
        logger.info("Graph loaded OK")
    except Exception as e:
        logger.error(f"Graph load failed: {e}")


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        graph = get_graph()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph error: {e}")

    # Подтягиваем историю и RAG-контекст
    from memory.store import format_history, rag_search, add_to_buffer, save_to_memory
    history = format_history(req.session_id)
    rag_ctx = rag_search(req.message, session_id=req.session_id)

    enriched_input = req.message
    if history:
        enriched_input = f"{history}\n\nТекущий запрос: {req.message}"
    if rag_ctx:
        enriched_input = f"{rag_ctx}\n\n{enriched_input}"

    from config import AgentState
    initial_state: AgentState = {
        "user_input":    enriched_input,
        "route":         "both",
        "planner_out":   None,
        "tutor_out":     None,
        "final_answer":  None,
        "quality_score": None,
        "retry_count":   0,
    }

    lf = get_langfuse()
    trace = None
    supervisor_gen = None
    planner_gen = None
    tutor_gen = None
    
    if lf:
        try:
            # Создаём основной trace
            trace = lf.trace(
                name="studyflow-chat", 
                session_id=req.session_id, 
                input=req.message,
                metadata={"user_id": req.session_id}
            )
            
            # Создаём generation для Supervisor (он всегда вызывается)
            supervisor_gen = trace.generation(
                name="supervisor",
                model="qwen2.5:7b",
                input=req.message,
                metadata={"type": "router"}
            )
            logger.info("Langfuse: created supervisor generation")
        except Exception as e:
            logger.warning(f"Langfuse trace/generation creation failed: {e}")

    try:
        # Засекаем время выполнения
        import time
        start_time = time.time()
        
        result = graph.invoke(initial_state)
        
        elapsed_time = time.time() - start_time
        
    except Exception as e:
        logger.error(f"Graph invoke error: {e}", exc_info=True)
        # В случае ошибки, отмечаем generation как ошибку
        if supervisor_gen:
            supervisor_gen.update(
                output={"error": str(e)},
                level="ERROR"
            )
        if trace:
            trace.update(output={"error": str(e)})
        if lf:
            lf.flush()
        raise HTTPException(status_code=500, detail=str(e))

    answer = result.get("final_answer") or "Не удалось получить ответ"
    score = float(result.get("quality_score") or 0.0)
    route = result.get("route") or "unknown"
    planner_out = result.get("planner_out")
    tutor_out = result.get("tutor_out")

    # Обновляем generation для Supervisor (результат маршрутизации)
    if supervisor_gen:
        supervisor_gen.update(
            output={"route": route},
            metadata={"routing_time_ms": elapsed_time * 1000}
        )
        supervisor_gen.end()
        logger.info(f"Langfuse: updated supervisor generation, route={route}")

    # Создаём отдельные generation для Planner и Tutor, если они были вызваны
    if planner_out and route in ("planner", "both"):
        if trace:
            planner_gen = trace.generation(
                name="planner",
                model="qwen2.5:3b",
                input=req.message,
                output=planner_out[:1000],  # ограничиваем длину
                metadata={"type": "planner", "route": route}
            )
            planner_gen.end()
            logger.info("Langfuse: created planner generation")

    if tutor_out and route in ("tutor", "both"):
        if trace:
            tutor_gen = trace.generation(
                name="tutor",
                model="kimi-k2.5:cloud",
                input=req.message,
                output=tutor_out[:1000],
                metadata={"type": "tutor", "route": route}
            )
            tutor_gen.end()
            logger.info("Langfuse: created tutor generation")

    # Добавляем Score для оценки качества ответа
    if trace:
        try:
            # Добавляем score как отдельную сущность (видна во вкладке Scores)
            trace.score(
                name="quality_score",
                value=score,
                comment=f"Evaluator agent score for route={route}"
            )
            
            # Также добавляем метрики времени выполнения
            trace.score(
                name="latency_seconds",
                value=elapsed_time,
                comment=f"Total response time: {elapsed_time:.2f}s"
            )
            
            # Обновляем trace с финальным ответом
            trace.update(
                output=answer,
                metadata={
                    "quality_score": score, 
                    "route": route,
                    "latency_seconds": elapsed_time,
                    "planner_used": bool(planner_out and route in ("planner", "both")),
                    "tutor_used": bool(tutor_out and route in ("tutor", "both"))
                }
            )
            logger.info(f"Langfuse: added scores (quality={score}, latency={elapsed_time:.2f}s)")
        except Exception as e:
            logger.warning(f"Langfuse trace update failed: {e}")

    # Сохраняем в буфер и долгосрочную память
    add_to_buffer(req.session_id, "user", req.message)
    add_to_buffer(req.session_id, "assistant", answer[:200])
    save_to_memory(req.session_id, f"Q: {req.message}\nA: {answer}", doc_type="dialog")

    # Принудительная отправка всех данных в Langfuse
    if lf:
        try:
            lf.flush()
            logger.debug("Langfuse: flushed data")
        except Exception as e:
            logger.warning(f"Langfuse flush failed: {e}")

    logger.info(f"Chat OK | route={route} score={score:.2f} session={req.session_id} latency={elapsed_time:.2f}s")
    return ChatResponse(answer=answer, quality_score=score, route=route)


@app.post("/upload")
async def upload_document(session_id: str, file: UploadFile = File(...)):
    """Загружает текстовый файл или PDF в ChromaDB для RAG."""
    from memory.store import ingest_text

    content = await file.read()

    if file.filename.endswith(".pdf"):
        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            text = "\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF parse error: {e}")
    else:
        try:
            text = content.decode("utf-8")
        except Exception:
            raise HTTPException(status_code=400, detail="File must be UTF-8 text or PDF")

    chunks = ingest_text(text, session_id=session_id, source=file.filename)
    return {"status": "ok", "chunks_saved": chunks, "filename": file.filename}


@app.get("/health")
def health():
    status = {"api": "ok", "graph": "unknown", "langfuse": "disabled", "chromadb": "unknown"}
    try:
        get_graph()
        status["graph"] = "ok"
    except Exception as e:
        status["graph"] = f"error: {e}"
    if get_langfuse():
        status["langfuse"] = "ok"
    try:
        import chromadb
        host = os.getenv("CHROMA_HOST", "localhost")
        port = int(os.getenv("CHROMA_PORT", "8001"))
        chromadb.HttpClient(host=host, port=port).heartbeat()
        status["chromadb"] = "ok"
    except Exception:
        status["chromadb"] = "unavailable"
    return status
