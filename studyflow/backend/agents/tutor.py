"""
Tutor Agent — Kimi K2.5 (облачный, OpenAI-compatible API)
Fallback на Ollama если KIMI_API_KEY не задан или ключ неполный.
"""
import logging
from langchain.prompts import ChatPromptTemplate
from config import LLM_CONFIG, AgentState

logger = logging.getLogger(__name__)


def _build_llm():
    tutor_cfg = LLM_CONFIG["tutor"]
    kimi_key  = tutor_cfg.get("api_key", "")

    if kimi_key and len(kimi_key) > 20:
        try:
            from langchain_ollama import ChatOllama
        
            model_name = tutor_cfg["model"] 
            base_url = tutor_cfg["base_url"]

            logger.info("Tutor: using Kimi K2.5")
            return ChatOllama(
                model=model_name,
                base_url=base_url,
                api_key=api_key,
                temperature=0.4,
            )
        except Exception as e:
            logger.warning(f"Kimi init failed: {e}, falling back to Ollama")

    from langchain_ollama import OllamaLLM
    logger.info("Tutor: using Ollama fallback (qwen2.5:1.5b)")
    return OllamaLLM(
        model="qwen2.5:1.5b",
        base_url=LLM_CONFIG["supervisor"]["base_url"],
        temperature=0.4,
    )


_llm = _build_llm()

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Ты — образовательный ассистент StudyFlow.
Объясняй сложные темы простым языком с примерами.
Начинай с базового уровня, постепенно усложняй.
Ищи связи между темами для лучшего запоминания.
Всегда отвечай на русском языке. Будь конкретным и полезным."""),
    ("human", "{user_input}"),
])


def tutor_node(state: AgentState) -> AgentState:
    if state["route"] not in ("tutor", "both"):
        return state

    try:
        chain = _PROMPT | _llm
        response = chain.invoke({"user_input": state["user_input"]})
        content = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error(f"Tutor error: {e}")
        content = f"[Tutor недоступен: {e}]"

    return {**state, "tutor_out": content}