"""
Planner Agent — qwen2.5:1.5b
Строит план дня, микрозадачи, корректирует после пропусков.
"""
import json
import logging
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from langchain.tools import tool
from config import LLM_CONFIG, AgentState

logger = logging.getLogger(__name__)

_llm = OllamaLLM(
    model=LLM_CONFIG["planner"]["model"],
    base_url=LLM_CONFIG["planner"]["base_url"],
    temperature=0.3,
)

# ── Skills ────────────────────────────────────────────────────

@tool
def analyze_complexity(topic: str) -> dict:
    """Оценивает сложность темы по эвристике."""
    hard_topics = ["квантовая", "дифференциальные", "нейросети", "термодинамика", "алгоритм"]
    score = 0.8 if any(h in topic.lower() for h in hard_topics) else 0.5
    return {"topic": topic, "complexity": score, "recommended_minutes": int(score * 90)}


@tool
def build_timeline(topics_json: str) -> list:
    """Строит план дня. topics_json: [{"name": "Python", "deadline": "завтра", "minutes": 60}]"""
    topics = json.loads(topics_json)
    plan, hour = [], 9
    for t in sorted(topics, key=lambda x: 0 if "завтра" in x.get("deadline","") else 1):
        plan.append({"time": f"{hour:02d}:00", "topic": t["name"],
                     "duration_min": t.get("minutes", 45), "type": "study"})
        hour += 1
        if len(plan) % 2 == 0:
            plan.append({"time": f"{hour:02d}:00", "topic": "Перерыв", "duration_min": 15, "type": "break"})
            hour += 1
    return plan


@tool
def microtask(topic: str, duration_min: int = 10) -> dict:
    """Короткая задача по теме для восстановления фокуса."""
    return {
        "topic": topic,
        "duration_min": duration_min,
        "task": f"Прочитай одну страницу по теме '{topic}' и сформулируй 1 вопрос.",
    }


# ── Prompt ───────────────────────────────────────────────────

_PROMPT = PromptTemplate.from_template("""Ты — планировщик учёбы. Создай конкретный план дня.

Запрос: {user_input}

Правила:
- Сначала самое срочное (дедлайн завтра → первым)
- Блоки по 45 минут, перерыв 15 минут после каждых 2 блоков
- Не более 4 часов учёбы подряд
- Формат: 09:00 — Python (45 мин): [конкретная задача]

Отвечай только на русском. Только план, без вступлений.""")


def planner_node(state: AgentState) -> AgentState:
    if state["route"] not in ("planner", "both"):
        return state

    try:
        response = _llm.invoke(_PROMPT.format(user_input=state["user_input"]))
    except Exception as e:
        logger.error(f"Planner error: {e}")
        response = f"[Planner недоступен: {e}]"

    return {**state, "planner_out": str(response)}
