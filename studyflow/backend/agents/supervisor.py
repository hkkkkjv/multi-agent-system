"""
Supervisor Agent — qwen2.5:1.5b
Маршрутизирует запрос к нужным агентам.
"""
import logging
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from config import LLM_CONFIG, AgentState

logger = logging.getLogger(__name__)

_llm = OllamaLLM(
    model=LLM_CONFIG["supervisor"]["model"],
    base_url=LLM_CONFIG["supervisor"]["base_url"],
    temperature=0.0,  # детерминированная маршрутизация
)

_PROMPT = PromptTemplate.from_template("""Classify the user's request. Reply with ONE word only.

User request: {user_input}

Rules:
- "planner" — schedule, plan, deadline, timetable, microtask, missed class
- "tutor" — explain, what is, how does, analogy, concept, summary
- "both" — needs planning AND explanation

Reply only: planner / tutor / both""")

# Ключевые слова для надёжного fallback без LLM
_PLANNER_KEYWORDS = ["план", "дедлайн", "расписание", "завтра", "неделя", "время", "пропустил", "микрозадач"]
_TUTOR_KEYWORDS   = ["объясни", "что такое", "как работает", "аналог", "конспект", "расскажи", "помоги понять"]


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

    # Сначала пробуем keyword matching — быстро и надёжно
    route = _keyword_route(user_input)

    if route is None:
        # Если keywords не сработали — спрашиваем LLM
        try:
            raw = _llm.invoke(_PROMPT.format(user_input=user_input)).strip().lower()
            if "plan" in raw:
                route = "planner"
            elif "tutor" in raw or "both" not in raw:
                route = "tutor"
            else:
                route = "both"
        except Exception as e:
            logger.warning(f"Supervisor LLM error: {e}, defaulting to both")
            route = "both"

    logger.info(f"Supervisor routed to: {route}")
    return {**state, "route": route}
