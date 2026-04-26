"""
Evaluator Agent — контроль качества ответов.
Загружает секцию Evaluator из AGENT_CONTEXT.md и SKILLS_REFERENCE.md.
"""
import re
import logging
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from config import LLM_CONFIG, AgentState

logger = logging.getLogger(__name__)

_llm = OllamaLLM(
    model=LLM_CONFIG["evaluator"]["model"],
    base_url=LLM_CONFIG["evaluator"]["base_url"],
    temperature=0.0,
)

_PROMPT = PromptTemplate.from_template("""Rate the answer. Reply with ONE number: 0.0 to 1.0

Question: {user_input}
Answer: {answer}

Scoring:
- On topic (+0.4)
- Specific details (+0.3)
- No contradictions (+0.3)

Number only:""")

# Артефакты промпта которые не должны попасть в финальный ответ
_PROMPT_ARTIFACTS = [
    "Формат для каждой темы (срочное первым):",
    "Только план, без вступлений и итогов:",
    "Срочное первым. Только план:",
    "Для каждой темы:",
    "Только план:",
    "Только микрозадача:",
]


def _clean(text: str) -> str:
    """Обрезает ответ если в него попал промпт."""
    for artifact in _PROMPT_ARTIFACTS:
        if artifact in text:
            text = text[:text.index(artifact)].strip()
    return text


def evaluator_node(state: AgentState) -> AgentState:
    parts = []
    if state.get("planner_out"):
        parts.append(_clean(state["planner_out"]))
    if state.get("tutor_out"):
        parts.append(state["tutor_out"])

    combined = "\n\n---\n\n".join(parts) if parts else "Нет ответа"

    score = 0.5
    try:
        raw = _llm.invoke(_PROMPT.format(
            user_input=state["user_input"],
            answer=combined[:400],
        )).strip()
        nums = re.findall(r"\d+\.?\d*", raw)
        if nums:
            score = max(0.0, min(1.0, float(nums[0])))
    except Exception as e:
        logger.warning(f"Evaluator error: {e}")

    logger.info(f"Evaluator score: {score}")
    return {**state, "final_answer": combined, "quality_score": score}


def should_retry(state: AgentState) -> str:
    if state.get("quality_score", 1.0) < 0.8 and state.get("retry_count", 0) < 2:
        return "retry"
    return "end"