from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class DatasetMeta(BaseModel):
    dataset_id: str
    filename: str
    file_type: Literal["csv", "xlsx"]
    row_count: int
    column_count: int
    columns: list[str]
    created_at: str


class DatasetListResponse(BaseModel):
    datasets: list[DatasetMeta]


class PreviewResponse(BaseModel):
    dataset_id: str
    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows: int


class NumericStats(BaseModel):
    count: int
    missing: int
    mean: Optional[float]
    median: Optional[float]
    min: Optional[float]
    max: Optional[float]
    std: Optional[float]
    q1: Optional[float]
    q3: Optional[float]
    iqr: Optional[float]


class CategoricalStats(BaseModel):
    count: int
    missing: int
    unique: int
    top_values: list[dict[str, Any]]


class DateStats(BaseModel):
    count: int
    missing: int
    earliest: Optional[str]
    latest: Optional[str]
    range_days: Optional[int]


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    kind: Literal["numeric", "categorical", "date", "identifier", "text"]
    stats: Optional[NumericStats | CategoricalStats | DateStats] = None


class ProfileResponse(BaseModel):
    dataset_id: str
    row_count: int
    column_count: int
    missing_cells: int
    duplicate_rows: int
    memory_bytes: int
    columns: list[ColumnProfile]


class Finding(BaseModel):
    finding_id: str
    category: str
    severity: Literal["low", "medium", "high"]
    column: Optional[str]
    description: str
    affected_records: int
    evidence: dict[str, Any] = Field(default_factory=dict)
    recommended_action: str
    needs_investigation: bool = False


class UnsupportedRule(BaseModel):
    rule: str
    reason: str


class QualityResponse(BaseModel):
    dataset_id: str
    findings: list[Finding]
    unsupported_rules: list[UnsupportedRule] = Field(default_factory=list)


class DocumentMeta(BaseModel):
    document_id: str
    dataset_id: str
    filename: str
    document_type: Literal["data_dictionary", "business_rules", "description", "other"]
    chunk_count: int
    created_at: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentMeta]


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class ChartSpec(BaseModel):
    type: Literal["bar", "line"]
    title: str
    x_label: str
    y_label: str
    data: list[dict[str, Any]]


class Citation(BaseModel):
    document_id: str
    filename: str
    chunk_id: str
    page: Optional[int] = None
    section: Optional[str] = None


class ChatResponse(BaseModel):
    dataset_id: str
    intent: str
    answer: str
    analysis_results: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    chart: Optional[ChartSpec] = None
    verified: bool
    limitations: list[str] = Field(default_factory=list)


class ReportRequest(BaseModel):
    include_business_rules: bool = True


class ReportResponse(BaseModel):
    dataset_id: str
    generated_at: str
    overview: dict[str, Any]
    quality_findings: list[Finding]
    statistical_observations: list[str]
    business_rule_violations: list[Finding]
    unsupported_rules: list[UnsupportedRule]
    recommendations: list[str]
