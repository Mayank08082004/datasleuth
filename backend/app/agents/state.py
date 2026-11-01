from typing import Any, Optional, TypedDict


class AgentState(TypedDict, total=False):
    dataset_id: str
    user_question: str
    intent: str                       # quality | aggregation | business_rules | documentation | general
    tool_plan: list[dict[str, Any]]   # [{"name": str, "args": dict}] chosen deterministically
    retrieved_documents: list[dict[str, Any]]
    analysis_results: list[dict[str, Any]]
    validation_results: dict[str, Any]
    final_response: str
    chart: Optional[dict[str, Any]]
    citations: list[dict[str, Any]]
    limitations: list[str]
    retries: int
    error: Optional[str]
