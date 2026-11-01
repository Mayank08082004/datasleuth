"""LangGraph workflow: classify → validate → (retrieve | analyse) → verify → respond.

Routing is conditional on intent. Verification failures retry the analysis at most
MAX_RETRIES times before a limitation message is returned.
"""

import functools
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents import nodes
from app.agents.state import AgentState
from app.services.dataset_service import load_dataset_frame, load_raw_frame, get_dataset_row

MAX_RETRIES = nodes.MAX_RETRIES


def _frames(dataset_id: str) -> dict:
    row = get_dataset_row(dataset_id)
    if row is None:
        raise ValueError("dataset_not_found")
    return {"raw": load_raw_frame(row["stored_path"]), "norm": load_dataset_frame(row["stored_path"])}


def _with_frames(fn):
    """Wraps a node that needs DataFrames; frames are loaded once per node call from the stored file."""
    @functools.wraps(fn)
    def wrapper(state: AgentState) -> dict[str, Any]:
        return fn(state, _frames(state["dataset_id"]))
    return wrapper


def _error_node(state: AgentState) -> dict[str, Any]:
    limitations = state.get("limitations") or ["The request could not be completed."]
    return {"final_response": "\n".join(limitations), "chart": None, "citations": []}


def _route_after_validate(state: AgentState) -> str:
    if state.get("error"):
        return "error"
    intent = state.get("intent")
    if intent == "documentation":
        return "retrieve"
    if intent == "business_rules":
        return "retrieve"
    return "plan"


def _route_after_retrieve(state: AgentState) -> str:
    if state.get("intent") == "business_rules":
        return "rules"
    return "verify"  # documentation: check retrieved evidence before answering


def _route_after_verify(state: AgentState) -> str:
    validation = state.get("validation_results", {})
    if validation.get("ok"):
        return "chart"
    if state.get("retries", 0) <= MAX_RETRIES and state.get("intent") in ("aggregation", "quality", "general"):
        return "plan"
    return "respond"


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("classify", nodes.classify)
    g.add_node("validate", nodes.validate_dataset)
    g.add_node("retrieve", nodes.retrieve_documents)
    g.add_node("plan", _with_frames(nodes.plan_analysis))
    g.add_node("analyse", _with_frames(nodes.execute_analysis))
    g.add_node("rules", _with_frames(nodes.evaluate_business_rules))
    g.add_node("verify", _with_frames(nodes.verify))
    g.add_node("make_chart", _with_frames(nodes.build_chart))
    g.add_node("respond", nodes.generate_response)
    g.add_node("check_grounding", nodes.check_grounding)
    g.add_node("handle_error", _error_node)

    g.set_entry_point("classify")
    g.add_edge("classify", "validate")
    g.add_conditional_edges("validate", _route_after_validate,
                            {"retrieve": "retrieve", "plan": "plan", "error": "handle_error"})
    g.add_conditional_edges("retrieve", _route_after_retrieve,
                            {"rules": "rules", "verify": "verify"})
    g.add_edge("plan", "analyse")
    g.add_edge("analyse", "verify")
    g.add_edge("rules", "verify")
    g.add_conditional_edges("verify", _route_after_verify,
                            {"chart": "make_chart", "plan": "plan", "respond": "respond"})
    g.add_edge("make_chart", "respond")
    g.add_edge("respond", "check_grounding")
    g.add_edge("check_grounding", END)
    g.add_edge("handle_error", END)
    return g.compile()


_graph = None


def run_question(dataset_id: str, question: str) -> AgentState:
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph.invoke({"dataset_id": dataset_id, "user_question": question, "retries": 0,
                          "limitations": [], "analysis_results": [], "retrieved_documents": []})
