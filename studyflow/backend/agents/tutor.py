"""
Tutor Agent — объясняет темы.
Загружает секцию Tutor из AGENT_CONTEXT.md и SKILLS_REFERENCE.md.
"""
import logging
from pathlib import Path
from langchain.prompts import ChatPromptTemplate
from langchain_ollama import OllamaLLM
from config import LLM_CONFIG, AgentState

logger = logging.getLogger(__name__)


def _load_system_prompt() -> str:
    prompts_dir = Path(__file__).parent.parent.parent / "prompts"
    base = """Ты — образовательный ассистент StudyFlow.
Объясняй темы простым языком. Структура ответа:
1. Простыми словами (1-2 предложения)
2. Пример из жизни
3. Техническая суть (кратко)
4. Запомни: [одна ключевая мысль]
Отвечай на русском. Без воды."""

    sections = [base]

    # Берём только секцию про Tutor агента
    try:
        content = (prompts_dir / "AGENT_CONTEXT.md").read_text(encoding="utf-8")
        start = content.find("### Tutor")
        end   = content.find("### Evaluator")
        if start != -1 and end != -1:
            sections.append("Твоя роль:\n" + content[start:end].strip())
    except Exception:
        pass

    # Берём только скиллы Tutor из SKILLS_REFERENCE
    try:
        content = (prompts_dir / "SKILLS_REFERENCE.md").read_text(encoding="utf-8")
        start = content.find("## Tutor Agent Skills")
        end   = content.find("## Evaluator Skills")
        if start != -1 and end != -1:
            sections.append("Твои инструменты:\n" + content[start:end].strip())
    except Exception:
        pass

    return "\n\n---\n\n".join(sections)


def _build_llm():
    cfg = LLM_CONFIG["tutor"]
    key = cfg.get("api_key", "")
    if key and len(key) > 20 and "moonshot" in cfg.get("base_url", ""):
        try:
            from langchain_openai import ChatOpenAI
            logger.info("Tutor: Kimi K2.5")
            return ChatOpenAI(model=cfg["model"], base_url=cfg["base_url"],
                              api_key=key, temperature=0.4)
        except Exception as e:
            logger.warning(f"Kimi failed: {e}")
    logger.info(f"Tutor: Ollama {cfg['model']}")
    return OllamaLLM(model=cfg["model"], base_url=cfg["base_url"], temperature=0.4)


_llm = _build_llm()
_system_prompt = _load_system_prompt()
logger.info(f"Tutor system prompt loaded ({len(_system_prompt)} chars)")

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _system_prompt),
    ("human", "{user_input}"),
])


def tutor_node(state: AgentState) -> AgentState:
    if state["route"] not in ("tutor", "both"):
        return state
    try:
        chain = _PROMPT | _llm
        resp = chain.invoke({"user_input": state["user_input"]})
        content = resp.content if hasattr(resp, "content") else str(resp)
    except Exception as e:
        logger.error(f"Tutor error: {e}")
        content = f"[Tutor недоступен: {e}]"
    return {**state, "tutor_out": content}