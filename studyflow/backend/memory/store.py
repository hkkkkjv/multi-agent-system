"""
Система памяти StudyFlow.

Краткосрочная: буфер последних N сообщений в памяти процесса.
Долгосрочная: ChromaDB — хранит конспекты, планы, загруженные PDF.

Выбор обоснован:
- ChromaDB: локальная, без внешних зависимостей, хорошая интеграция с LangChain
- Недостатки: нет TTL, не масштабируется на много пользователей, нет авторизации
- Альтернативы: pgvector (SQL + векторы), Pinecone (облако), Mem0 (управляемая память)
"""
import os
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Краткосрочная память (in-process буфер) ───────────────────
_session_buffer: dict[str, list[dict]] = {}
MAX_BUFFER = 10  # последних N сообщений


def add_to_buffer(session_id: str, role: str, content: str):
    if session_id not in _session_buffer:
        _session_buffer[session_id] = []
    _session_buffer[session_id].append({"role": role, "content": content})
    # Обрезаем до MAX_BUFFER
    _session_buffer[session_id] = _session_buffer[session_id][-MAX_BUFFER:]


def get_buffer(session_id: str) -> list[dict]:
    return _session_buffer.get(session_id, [])


def format_history(session_id: str) -> str:
    """Форматирует историю для вставки в промпт."""
    history = get_buffer(session_id)
    if not history:
        return ""
    lines = [f"{m['role'].upper()}: {m['content']}" for m in history[-4:]]
    return "История диалога:\n" + "\n".join(lines)


# ── Долгосрочная память (ChromaDB) ────────────────────────────
def _get_chroma_client():
    try:
        import chromadb
        host = os.getenv("CHROMA_HOST", "chromadb")
        port = int(os.getenv("CHROMA_PORT", "8000"))
        return chromadb.HttpClient(host=host, port=port)
    except Exception as e:
        logger.warning(f"ChromaDB unavailable: {e}")
        return None


def _get_collection(client, name: str = "studyflow_docs"):
    try:
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as e:
        logger.warning(f"ChromaDB collection error: {e}")
        return None


def save_to_memory(session_id: str, content: str, doc_type: str = "note"):
    """Сохраняет конспект/план в долгосрочную память."""
    client = _get_chroma_client()
    if not client:
        return

    collection = _get_collection(client)
    if not collection:
        return

    doc_id = f"{session_id}_{doc_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        collection.add(
            ids=[doc_id],
            documents=[content],
            metadatas=[{"session_id": session_id, "type": doc_type, "ts": datetime.now().isoformat()}],
        )
        logger.info(f"Saved to ChromaDB: {doc_id}")
    except Exception as e:
        logger.warning(f"ChromaDB save error: {e}")


def rag_search(query: str, session_id: Optional[str] = None, n_results: int = 3) -> str:
    """
    Семантический поиск по сохранённым документам.
    Возвращает текст для вставки в промпт.
    """
    client = _get_chroma_client()
    if not client:
        return ""

    collection = _get_collection(client)
    if not collection:
        return ""

    try:
        where = {"session_id": session_id} if session_id else None
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count() or 1),
            where=where,
        )
        docs = results.get("documents", [[]])[0]
        if not docs:
            return ""
        context = "\n\n---\n\n".join(docs)
        return f"Из твоих материалов:\n{context}"
    except Exception as e:
        logger.warning(f"RAG search error: {e}")
        return ""


def ingest_text(text: str, session_id: str, source: str = "manual"):
    """Загружает текст в ChromaDB (для PDF и конспектов)."""
    # Простая разбивка на чанки по 500 символов с overlap 50
    chunk_size, overlap = 500, 50
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i + chunk_size]
        if chunk.strip():
            chunks.append(chunk)

    client = _get_chroma_client()
    if not client or not chunks:
        return 0

    collection = _get_collection(client)
    if not collection:
        return 0

    ids = [f"{session_id}_{source}_{i}" for i in range(len(chunks))]
    metas = [{"session_id": session_id, "source": source, "chunk": i} for i in range(len(chunks))]

    try:
        collection.add(ids=ids, documents=chunks, metadatas=metas)
        logger.info(f"Ingested {len(chunks)} chunks from {source}")
        return len(chunks)
    except Exception as e:
        logger.warning(f"Ingest error: {e}")
        return 0
