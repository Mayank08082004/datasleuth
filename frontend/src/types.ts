// Mirrors backend/app/models/schemas.py

export interface DatasetMeta {
  dataset_id: string;
  filename: string;
  file_type: "csv" | "xlsx";
  row_count: number;
  column_count: number;
  columns: string[];
  created_at: string;
}

export interface ColumnProfile {
  name: string;
  dtype: string;
  kind: "numeric" | "categorical" | "date" | "identifier" | "text";
  stats: Record<string, unknown> | null;
}

export interface ProfileResponse {
  dataset_id: string;
  row_count: number;
  column_count: number;
  missing_cells: number;
  duplicate_rows: number;
  memory_bytes: number;
  columns: ColumnProfile[];
}

export interface PreviewResponse {
  dataset_id: string;
  columns: string[];
  rows: Record<string, unknown>[];
  total_rows: number;
}

export interface Finding {
  finding_id: string;
  category: string;
  severity: "low" | "medium" | "high";
  column: string | null;
  description: string;
  affected_records: number;
  evidence: Record<string, unknown>;
  recommended_action: string;
  needs_investigation: boolean;
}

export interface UnsupportedRule {
  rule: string;
  reason: string;
}

export interface QualityResponse {
  dataset_id: string;
  findings: Finding[];
  unsupported_rules: UnsupportedRule[];
}

export interface DocumentMeta {
  document_id: string;
  dataset_id: string;
  filename: string;
  document_type: "data_dictionary" | "business_rules" | "description" | "other";
  chunk_count: number;
  created_at: string;
}

export interface ChartSpec {
  type: "bar" | "line";
  title: string;
  x_label: string;
  y_label: string;
  data: { name: string; value: number }[];
}

export interface Citation {
  document_id: string;
  filename: string;
  chunk_id: string;
  page: number | null;
  section: string | null;
}

export interface ChatResponse {
  dataset_id: string;
  intent: string;
  answer: string;
  analysis_results: { tool: string; args: Record<string, unknown>; output: unknown }[];
  citations: Citation[];
  chart: ChartSpec | null;
  verified: boolean;
  limitations: string[];
}

export interface ReportResponse {
  dataset_id: string;
  generated_at: string;
  overview: Record<string, unknown>;
  quality_findings: Finding[];
  statistical_observations: string[];
  business_rule_violations: Finding[];
  unsupported_rules: UnsupportedRule[];
  recommendations: string[];
}
