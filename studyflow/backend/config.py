"""
Конфигурация моделей StudyFlow.
"""
import os
from typing import TypedDict, Literal, Optional

# ── LLM конфиги ──────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_API_KEY    = os.getenv("OLLAMA_API_KEY", "")

LLM_CONFIG = {
    "supervisor": {"model": "qwen2.5:7b",  "base_url": OLLAMA_BASE_URL},
    "planner":    {"model": "qwen2.5:3b",  "base_url": OLLAMA_BASE_URL},
    "evaluator":  {"model": "qwen2.5:1.5b","base_url": OLLAMA_BASE_URL},
    # Tutor использует Kimi K2.5 через OLLAMA
    "tutor": {
        "model": "kimi-k2.5:cloud",   # Cloud модель
        "base_url": OLLAMA_BASE_URL,
        "api_key": OLLAMA_API_KEY,
    },
}

# ── Граф состояния ────────────────────────────────────────────
class AgentState(TypedDict):
    user_input:   str
    route:        Literal["planner", "tutor", "both"]
    planner_out:  Optional[str]
    tutor_out:    Optional[str]
    final_answer: Optional[str]
    quality_score: Optional[float]
    retry_count:  int