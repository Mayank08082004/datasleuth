from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas import ReportRequest, ReportResponse
from app.services import dataset_service, profiling_service, quality_service, rag_service
from app.services.rules_service import evaluate_rules
from app.utils.security import rate_limit, require_api_key

router = APIRouter(prefix="/api/datasets", dependencies=[Depends(require_api_key), Depends(rate_limit)])


@router.post("/{dataset_id}/reports", response_model=ReportResponse)
def create_report(dataset_id: str, body: ReportRequest):
    row = dataset_service.get_dataset_row(dataset_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Dataset not found.")
    raw = dataset_service.load_raw_frame(row["stored_path"])
    norm = dataset_service.load_dataset_frame(row["stored_path"])
    profile = profiling_service.profile_frame(dataset_id, norm, raw)
    findings = quality_service.run_quality_checks(norm, raw)

    violations, unsupported, evaluated = [], [], []
    if body.include_business_rules:
        rules_text = rag_service.get_rules_text(dataset_id)
        if rules_text:
            violations, unsupported, evaluated = evaluate_rules(rules_text, norm)

    observations = []
    for col in profile.columns:
        if col.kind == "numeric" and col.stats and col.stats.mean is not None:
            observations.append(f"'{col.name}': mean {col.stats.mean}, median {col.stats.median}, "
                                f"range [{col.stats.min}, {col.stats.max}].")

    recommendations = [f.recommended_action for f in findings + violations]
    recommendations = list(dict.fromkeys(recommendations))  # de-duplicate, keep order

    return ReportResponse(
        dataset_id=dataset_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        overview={"filename": row["filename"], "row_count": profile.row_count,
                  "column_count": profile.column_count, "missing_cells": profile.missing_cells,
                  "duplicate_rows": profile.duplicate_rows,
                  "business_rules_evaluated": len(evaluated)},
        quality_findings=findings,
        statistical_observations=observations,
        business_rule_violations=violations,
        unsupported_rules=unsupported,
        recommendations=recommendations,
    )
