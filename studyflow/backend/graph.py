"""
LangGraph граф StudyFlow.
Supervisor → [Planner | Tutor] → Evaluator → (retry или END)
"""
from langgraph.graph import StateGraph, END
from config import AgentState
from agents.supervisor import supervisor_node
from agents.planner import planner_node
from agents.tutor import tutor_node
from agents.evaluator import evaluator_node, should_retry


def increment_retry(state: AgentState) -> AgentState:
    return {**state, "retry_count": state.get("retry_count", 0) + 1}


def build_graph():
    g = StateGraph(AgentState)

    g.add_node("supervisor", supervisor_node)
    g.add_node("planner",    planner_node)
    g.add_node("tutor",      tutor_node)
    g.add_node("evaluator",  evaluator_node)
    g.add_node("retry",      increment_retry)

    # Старт
    g.set_entry_point("supervisor")

    # Supervisor → workers (оба запускаются, неактивный просто пропускает)
    g.add_edge("supervisor", "planner")
    g.add_edge("planner",    "tutor")
    g.add_edge("tutor",      "evaluator")

    # Evaluator → retry или END
    g.add_conditional_edges(
        "evaluator",
        should_retry,
        {"retry": "retry", "end": END},
    )
    # После retry — снова через workers
    g.add_edge("retry", "planner")

    return g.compile()


graph = build_graph()
