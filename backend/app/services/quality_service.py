"""Deterministic data-quality checks. Never mutates the input DataFrame."""

import itertools

import numpy as np
import pandas as pd

from app.models.schemas import Finding
from app.services.dataset_service import ID_NAME_HINTS
from app.tools.data_tools import identifier_column

IQR_MULTIPLIER = 1.5
MAX_CATEGORY_CARDINALITY = 30
MAX_EXAMPLES = 5


class _Ids:
    def __init__(self) -> None:
        self._counter = itertools.count(1)

    def next(self) -> str:
        return f"F{next(self._counter):04d}"


def _examples(values, limit: int = MAX_EXAMPLES) -> list:
    return [v.item() if hasattr(v, "item") else v for v in list(values)[:limit]]


def check_missing(raw: pd.DataFrame, ids: _Ids) -> list[Finding]:
    """Blank cells in the original file. Unparseable text is reported separately as invalid."""
    findings = []
    total = len(raw)
    for col in raw.columns:
        n = int(raw[col].isna().sum())
        if n == 0:
            continue
        share = n / total if total else 0
        findings.append(Finding(
            finding_id=ids.next(), category="missing_values",
            severity="high" if share >= 0.2 else "medium" if share >= 0.05 else "low",
            column=col,
            description=f"Column '{col}' has {n} missing value(s) ({share:.1%} of rows).",
            affected_records=n,
            evidence={"missing": n, "share": round(share, 4)},
            recommended_action="Decide whether to impute, drop, or source the missing values upstream.",
        ))
    return findings


def check_duplicate_rows(df: pd.DataFrame, ids: _Ids) -> list[Finding]:
    dup_mask = df.duplicated(keep=False)
    n = int(df.duplicated().sum())
    if n == 0:
        return []
    return [Finding(
        finding_id=ids.next(), category="duplicate_rows", severity="high",
        column=None,
        description=(f"{n} row(s) are exact duplicates of an earlier row."
                     + _where(_row_refs(df, dup_mask))),
        affected_records=n,
        evidence={"duplicate_extra_rows": n, "row_indices_sample": _examples(df.index[dup_mask])},
        recommended_action="Review and remove exact duplicate rows if they are unintended.",
    )]


def _is_identifier_column(col: str) -> bool:
    lower = col.lower()
    return any(lower == h or lower.endswith(h) for h in ID_NAME_HINTS)


def _is_likely_primary_key(col: str, df: pd.DataFrame) -> bool:
    """Heuristic: a key-like name whose values are fully populated and mostly unique.

    Foreign-key-style columns (e.g. customer_id, which legitimately repeats across
    transactions) are excluded because they are not expected to be unique.
    """
    lower = col.lower()
    if not _is_identifier_column(col):
        return False
    if "customer" in lower or "product" in lower or "account" in lower:
        return False
    return True


def check_duplicate_identifiers(df: pd.DataFrame, ids: _Ids) -> list[Finding]:
    """Repeated values in primary-key-like columns. Uniqueness of other IDs is a business rule."""
    findings = []
    for col in df.columns:
        if not _is_likely_primary_key(col, df):
            continue
        series = df[col].dropna()
        dup = series[series.duplicated(keep=False)]
        if dup.empty:
            continue
        n_values = int(dup.nunique())
        findings.append(Finding(
            finding_id=ids.next(), category="duplicate_identifiers", severity="high",
            column=col,
            description=(f"Identifier column '{col}' has {n_values} repeated value(s) across {len(dup)} rows."
                          + _where(_row_refs(df, df.index.isin(dup.index)))),
            affected_records=int(len(dup)),
            evidence={"repeated_values": _examples(dup.unique()), **_row_refs(df, df.index.isin(dup.index))},
            recommended_action="Confirm whether this identifier must be unique; fix or deduplicate if so.",
        ))
    return findings


def check_outliers(df: pd.DataFrame, ids: _Ids) -> list[Finding]:
    findings = []
    for col in df.select_dtypes(include=[np.number]).columns:
        if _is_identifier_column(col):
            continue
        values = df[col].dropna()
        if len(values) < 4:
            continue
        q1, q3 = values.quantile(0.25), values.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        low, high = q1 - IQR_MULTIPLIER * iqr, q3 + IQR_MULTIPLIER * iqr
        mask = (values < low) | (values > high)
        n = int(mask.sum())
        if n == 0:
            continue
        findings.append(Finding(
            finding_id=ids.next(), category="statistical_outlier", severity="low",
            column=col,
            description=(f"{n} value(s) in '{col}' fall outside the IQR fences "
                         f"[{low:.4g}, {high:.4g}]. These may be legitimate and require investigation."),
            affected_records=n,
            evidence={"fence_low": round(float(low), 4), "fence_high": round(float(high), 4),
                      "outlier_row_indices": _examples(values[mask].index, 20),
                      "outlier_values": _examples(values[mask], 20)},
            recommended_action="Investigate these records before deciding whether they are errors.",
            needs_investigation=True,
        ))
    return findings


def _row_refs(df: pd.DataFrame, mask: pd.Series) -> dict:
    """Row positions and, where available, their identifiers, so findings can be traced to records."""
    id_col = identifier_column(df.columns)
    idx = list(df.index[mask])[:MAX_EXAMPLES * 4]
    out = {"row_indices": [int(i) for i in idx]}
    if id_col:
        out["row_ids"] = [_examples([df.loc[i, id_col]], 1)[0] for i in idx]
    return out


def _where(refs: dict) -> str:
    ids = refs.get("row_ids")
    if not ids:
        return ""
    shown = ", ".join(str(i) for i in ids[:5])
    more = f" and {len(ids) - 5} more" if len(ids) > 5 else ""
    return f" Affected: {shown}{more}."


def check_invalid_numeric(df: pd.DataFrame, raw: pd.DataFrame, ids: _Ids) -> list[Finding]:
    """Cells present in the raw text that could not be parsed as numbers in numeric-looking columns."""
    findings = []
    for col in df.select_dtypes(include=[np.number]).columns:
        if col not in raw.columns:
            continue
        original = raw[col]
        bad = original.notna() & df[col].isna()
        n = int(bad.sum())
        if n == 0:
            continue
        findings.append(Finding(
            finding_id=ids.next(), category="invalid_numeric", severity="medium",
            column=col,
            description=f"{n} value(s) in numeric column '{col}' could not be parsed as numbers.{_where(_row_refs(df, bad))}",
            affected_records=n,
            evidence={"examples": _examples(original[bad].astype(str)), **_row_refs(df, bad)},
            recommended_action="Correct the non-numeric entries at the source.",
        ))
    return findings


def check_invalid_dates(df: pd.DataFrame, raw: pd.DataFrame, ids: _Ids) -> list[Finding]:
    findings = []
    for col in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df[col]):
            continue
        original = raw[col]
        bad = original.notna() & df[col].isna()
        n = int(bad.sum())
        if n == 0:
            continue
        findings.append(Finding(
            finding_id=ids.next(), category="invalid_dates", severity="medium",
            column=col,
            description=f"{n} value(s) in date column '{col}' are not valid dates.{_where(_row_refs(df, bad))}",
            affected_records=n,
            evidence={"examples": _examples(original[bad].astype(str)), **_row_refs(df, bad)},
            recommended_action="Standardise the date format and correct invalid entries.",
        ))
    return findings


def check_unexpected_categories(df: pd.DataFrame, ids: _Ids) -> list[Finding]:
    """Flags rare categories (single occurrence) in low-cardinality text columns, e.g. typos in region names."""
    findings = []
    for col in df.columns:
        series = df[col].dropna()
        if series.empty or pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_datetime64_any_dtype(df[col]):
            continue
        if _is_identifier_column(col):
            continue
        counts = series.astype(str).str.strip().value_counts()
        if counts.size < 2 or counts.size > MAX_CATEGORY_CARDINALITY:
            continue
        rare = counts[counts == 1]
        if rare.empty or len(rare) > counts.size * 0.5:
            continue
        findings.append(Finding(
            finding_id=ids.next(), category="unexpected_category", severity="low",
            column=col,
            description=f"Column '{col}' has {len(rare)} category value(s) that appear only once; they may be typos.",
            affected_records=int(rare.sum()),
            evidence={"rare_values": _examples(rare.index), "known_values": _examples(counts.index[:10], 10)},
            recommended_action="Check whether these single-occurrence values are valid or misspelled.",
            needs_investigation=True,
        ))
    return findings


def run_quality_checks(df: pd.DataFrame, raw: pd.DataFrame) -> list[Finding]:
    """df: normalised frame (statistics). raw: original text values (invalid-value detection)."""
    if len(df) != len(raw) or list(df.columns) != list(raw.columns):
        raise ValueError("Raw and normalised frames must have identical shape and columns.")
    ids = _Ids()
    findings: list[Finding] = []
    findings += check_missing(raw, ids)
    findings += check_duplicate_rows(df, ids)
    findings += check_duplicate_identifiers(df, ids)
    findings += check_outliers(df, ids)
    findings += check_invalid_numeric(df, raw, ids)
    findings += check_invalid_dates(df, raw, ids)
    findings += check_unexpected_categories(df, ids)
    return findings
