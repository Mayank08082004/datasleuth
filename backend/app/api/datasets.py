from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.models.schemas import (
    DatasetListResponse,
    DatasetMeta,
    DocumentListResponse,
    DocumentMeta,
    PreviewResponse,
    ProfileResponse,
    QualityResponse,
)
from app.services import dataset_service, profiling_service, quality_service, rag_service
from app.services.llm_client import ProviderError, ProviderNotConfigured
from app.services.rules_service import evaluate_rules
from app.utils.file_validation import FileValidationError
from app.utils.security import rate_limit, require_api_key

router = APIRouter(prefix="/api/datasets", dependencies=[Depends(require_api_key), Depends(rate_limit)])
MAX_PREVIEW_PAGE_SIZE = 100


def _load_or_404(dataset_id: str):
    row = dataset_service.get_dataset_row(dataset_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Dataset not found.")
    return row


def _frames(dataset_id: str):
    row = _load_or_404(dataset_id)
    return dataset_service.load_raw_frame(row["stored_path"]), dataset_service.load_dataset_frame(row["stored_path"])


@router.post("/upload", response_model=DatasetMeta, status_code=status.HTTP_201_CREATED)
async def upload_dataset(file: UploadFile = File(...)):
    content = await file.read()
    try:
        return dataset_service.save_dataset(file.filename or "", content)
    except FileValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("", response_model=DatasetListResponse)
def list_datasets():
    return DatasetListResponse(datasets=dataset_service.list_datasets())


@router.get("/{dataset_id}", response_model=DatasetMeta)
def get_dataset(dataset_id: str):
    meta = dataset_service.get_dataset(dataset_id)
    if meta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Dataset not found.")
    return meta


@router.get("/{dataset_id}/profile", response_model=ProfileResponse)
def get_profile(dataset_id: str):
    raw, norm = _frames(dataset_id)
    return profiling_service.profile_frame(dataset_id, norm, raw)


@router.get("/{dataset_id}/preview", response_model=PreviewResponse)
def get_preview(dataset_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=MAX_PREVIEW_PAGE_SIZE)):
    _, norm = _frames(dataset_id)
    total = len(norm)
    start = (page - 1) * page_size
    chunk = norm.iloc[start:start + page_size].copy()
    # Replace NaN and timestamps with JSON-safe values.
    for col in chunk.columns:
        if str(chunk[col].dtype).startswith("datetime"):
            chunk[col] = chunk[col].dt.strftime("%Y-%m-%d")
    records = chunk.astype(object).where(chunk.notna(), None).to_dict(orient="records")
    return PreviewResponse(dataset_id=dataset_id, columns=[str(c) for c in norm.columns],
                           rows=records, total_rows=total)


@router.get("/{dataset_id}/quality", response_model=QualityResponse)
def get_quality(dataset_id: str):
    raw, norm = _frames(dataset_id)
    findings = quality_service.run_quality_checks(norm, raw)
    rules_text = rag_service.get_rules_text(dataset_id)
    rule_violations, unsupported, _ = evaluate_rules(rules_text, norm) if rules_text else ([], [], [])
    return QualityResponse(dataset_id=dataset_id, findings=findings + rule_violations,
                           unsupported_rules=unsupported)


@router.post("/{dataset_id}/documents", response_model=DocumentMeta, status_code=status.HTTP_201_CREATED)
async def upload_document(dataset_id: str, file: UploadFile = File(...)):
    _load_or_404(dataset_id)
    content = await file.read()
    try:
        result = rag_service.ingest_document(dataset_id, file.filename or "", content)
    except FileValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except ProviderNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except ProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    docs = rag_service.list_documents(dataset_id)
    created = next(d for d in docs if d["document_id"] == result["document_id"])
    return DocumentMeta(**created)


@router.get("/{dataset_id}/documents", response_model=DocumentListResponse)
def list_documents(dataset_id: str):
    _load_or_404(dataset_id)
    return DocumentListResponse(documents=[DocumentMeta(**d) for d in rag_service.list_documents(dataset_id)])
