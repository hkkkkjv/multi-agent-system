"""
Supervisor Agent — маршрутизирует запрос к нужным агентам.
Загружает AGENT_CONTEXT.md для понимания системы.
"""
import logging
from pathlib import Path
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from config import LLM_CONFIG, AgentState

logger = logging.getLogger(__name__)

_llm = OllamaLLM(
    model=LLM_CONFIG["supervisor"]["model"],
    base_url=LLM_CONFIG["supervisor"]["base_url"],
    temperature=0.0,
)


def _load_routing_context() -> str:
    """Загружает описание агентов из AGENT_CONTEXT.md для точной маршрутизации."""
    md_path = Path(__file__).parent.parent.parent / "prompts" / "AGENT_CONTEXT.md"
    try:
        content = md_path.read_text(encoding="utf-8")
        # Берём только секцию про агентов — она описывает кто что умеет
        start = content.find("## Агенты системы")
        end   = content.find("## Формат взаимодействия")
        if start != -1 and end != -1:
            return content[start:end].strip()
        return content
    except Exception:
        return ""


_routing_context = _load_routing_context()

_PROMPT = PromptTemplate.from_template("""Ты — оркестратор системы StudyFlow. Классифицируй запрос пользователя.

{routing_context}

Запрос: {user_input}

Правила маршрутизации:
- "planner" — расписание, план, дедлайн, микрозадача, пропустил занятие
- "tutor"   — объяснение темы, что такое, как работает, аналогия, конспект
- "both"    — нужно и то, и другое

Ответь ОДНИМ словом: planner / tutor / both""")

_PLANNER_KEYWORDS = [
    "план", "дедлайн", "расписание", "завтра", "неделя",
    "пропустил", "микрозадач", "сколько времени", "когда учить",
    "застрял", "устал",
]
_TUTOR_KEYWORDS = [
    "объясни", "что такое", "как работает", "аналог", "конспект",
    "расскажи", "помоги понять", "как меня", "зовут", "помни",
    "что я", "кто я", "напомни", "что значит", "почему",
]


def _keyword_route(text: str) -> str | None:
    t = text.lower()
    has_plan  = any(k in t for k in _PLANNER_KEYWORDS)
    has_tutor = any(k in t for k in _TUTOR_KEYWORDS)
    if has_plan and has_tutor:
        return "both"
    if has_plan:
        return "planner"
    if has_tutor:
        return "tutor"
    return None


def supervisor_node(state: AgentState) -> AgentState:
    user_input = state["user_input"]
    route = _keyword_route(user_input)

    if route is None:
        try:
            raw = _llm.invoke(_PROMPT.format(
                routing_context=_routing_context,
                user_input=user_input,
            )).strip().lower()
            if "planner" in raw:
                route = "planner"
            elif "both" in raw:
                route = "both"
            else:
                route = "tutor"
        except Exception as e:
            logger.warning(f"Supervisor LLM error: {e}, defaulting to both")
            route = "both"

    logger.info(f"Supervisor routed to: {route}")
    return {**state, "route": route}