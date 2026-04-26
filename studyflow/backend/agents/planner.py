import logging
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from langchain.tools import tool
from config import LLM_CONFIG, AgentState

logger = logging.getLogger(__name__)

_llm = OllamaLLM(
    model=LLM_CONFIG["planner"]["model"],
    base_url=LLM_CONFIG["planner"]["base_url"],
    temperature=0.2,
)

_MICROTASK_KEYWORDS = [
    "микрозадач", "застрял", "устал", "отвлечься",
    "передохнуть", "10 минут", "5 минут", "небольшую задачу",
]

_PLAN_PROMPT = PromptTemplate.from_template(
"""Составь учебный план. Запрос: {user_input}

Формат для каждой темы (срочное первым):

Тема: [название]
1. Введение — [задача]
2. [Раздел] — [задача]
3. [Раздел] — [задача]
4. Вопросы — записать 2 вопроса

Перерыв 15 мин между темами.
Только план, без вступлений и итогов:"""
)

_MICRO_PROMPT = PromptTemplate.from_template(
"""Запрос: {user_input}

Тема: [определи из запроса]
Время: 10 минут
Задача: [одно конкретное действие]"""
)


@tool
def microtask(topic: str, duration_min: int = 10) -> dict:
    """Короткая задача для восстановления фокуса."""
    return {"topic": topic, "duration_min": duration_min,
            "task": f"Прочитай одну страницу по '{topic}', запиши 1 вопрос."}


def _is_microtask(text: str) -> bool:
    return any(k in text.lower() for k in _MICROTASK_KEYWORDS)


def planner_node(state: AgentState) -> AgentState:
    if state["route"] not in ("planner", "both"):
        return state
    try:
        prompt = _MICRO_PROMPT if _is_microtask(state["user_input"]) else _PLAN_PROMPT
        response = _llm.invoke(prompt.format(user_input=state["user_input"]))
    except Exception as e:
        logger.error(f"Planner error: {e}")
        response = f"[Planner недоступен: {e}]"
    return {**state, "planner_out": str(response)}