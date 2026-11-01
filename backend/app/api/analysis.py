from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.graph import run_question
from app.models.schemas import ChatRequest, ChatResponse, Citation, ChartSpec
from app.services import dataset_service
from app.utils.security import rate_limit, require_api_key

router = APIRouter(prefix="/api/datasets", dependencies=[Depends(require_api_key), Depends(rate_limit)])


@router.post("/{dataset_id}/chat", response_model=ChatResponse)
def chat(dataset_id: str, body: ChatRequest):
    if dataset_service.get_dataset_row(dataset_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Dataset not found.")
    state = run_question(dataset_id, body.question)
    validation = state.get("validation_results", {})
    chart = state.get("chart")
    # "verified" means: the answer is backed by computed results or cited documents, and passed the checks.
    evidenced = bool(state.get("analysis_results")) or bool(state.get("citations"))
    verified = bool(validation.get("ok")) and validation.get("grounded", True) and evidenced
    return ChatResponse(
        dataset_id=dataset_id,
        intent=state.get("intent", "general"),
        answer=state.get("final_response", ""),
        analysis_results=state.get("analysis_results", []),
        citations=[Citation(**c) for c in state.get("citations", [])],
        chart=ChartSpec(**chart) if chart else None,
        verified=verified,
        limitations=state.get("limitations", []),
    )
