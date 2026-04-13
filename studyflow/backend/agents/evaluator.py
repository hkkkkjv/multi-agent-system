"""
Evaluator Agent — qwen2.5:1.5b
Простая проверка по чеклисту.
"""
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

Criteria:
- On topic (+0.4)
- Has specific details (+0.3)  
- No contradictions (+0.3)

Number only:""")


def evaluator_node(state: AgentState) -> AgentState:
    parts = [p for p in [state.get("planner_out"), state.get("tutor_out")] if p]
    combined = "\n\n".join(parts) if parts else "Нет ответа"

    score = 0.5  # default
    try:
        raw = _llm.invoke(
            _PROMPT.format(user_input=state["user_input"], answer=combined[:400])
        ).strip()
        # Берём первое число из ответа
        import re
        nums = re.findall(r"\d+\.?\d*", raw)
        if nums:
            score = max(0.0, min(1.0, float(nums[0])))
    except Exception as e:
        logger.warning(f"Evaluator error: {e}, using default score 0.5")

    logger.info(f"Evaluator score: {score}")
    return {**state, "final_answer": combined, "quality_score": score}


def should_retry(state: AgentState) -> str:
    if state.get("quality_score", 1.0) < 0.8 and state.get("retry_count", 0) < 2:
        return "retry"
    return "end"
