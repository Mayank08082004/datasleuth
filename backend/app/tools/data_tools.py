"""Controlled analytical tools. The LLM may only select a tool and supply validated arguments.

Nothing here evaluates code or SQL supplied by the model. Every column reference is
checked against the dataset's actual columns, and aggregation is limited to a fixed set.
"""

from typing import Any, Literal, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator

AGG_FUNCS = ("sum", "mean", "min", "max", "count", "median")
TIME_GRAINS = ("month", "quarter", "year")
MAX_RESULT_ROWS = 50


class ToolError(ValueError):
    """Raised when a tool call is invalid for the dataset."""


def _require_columns(df: pd.DataFrame, cols: list[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ToolError(f"Unknown column(s): {', '.join(missing)}. Available: {', '.join(map(str, df.columns))}")


ROW_ID_PREFERENCE = ("transaction_id", "order_id", "id")


def identifier_column(columns) -> str | None:
    """The column used to name a row to the user (e.g. transaction_id), if the dataset has one."""
    lower = {str(c).lower(): c for c in columns}
    for name in ROW_ID_PREFERENCE:
        if name in lower:
            return lower[name]
    return None


def _to_python(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else round(float(value), 6)
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    return value


# ---------- argument models ----------

class ColumnStatsArgs(BaseModel):
    column: str


class GroupedAggregationArgs(BaseModel):
    value_column: str
    group_by: str
    agg: Literal["sum", "mean", "min", "max", "count", "median"] = "sum"
    top_n: Optional[int] = Field(default=None, ge=1, le=MAX_RESULT_ROWS)
    descending: bool = True


class MonthlyAggregationArgs(BaseModel):
    value_column: str
    date_column: str
    agg: Literal["sum", "mean", "min", "max", "count", "median"] = "sum"
    grain: Literal["month", "quarter", "year"] = "month"


class CorrelationArgs(BaseModel):
    column_a: str
    column_b: str

    @model_validator(mode="after")
    def distinct(self):
        if self.column_a == self.column_b:
            raise ValueError("column_a and column_b must differ")
        return self


class OutlierArgs(BaseModel):
    column: str
    method: Literal["iqr"] = "iqr"
    limit: int = Field(default=10, ge=1, le=MAX_RESULT_ROWS)


class DuplicateArgs(BaseModel):
    column: Optional[str] = None  # None = whole-row duplicates


class MissingArgs(BaseModel):
    column: Optional[str] = None


# ---------- tools ----------

def dataset_summary(df: pd.DataFrame, raw: pd.DataFrame | None = None) -> dict:
    id_col = identifier_column(df.columns)
    source = raw if raw is not None else df
    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": [{"name": c, "dtype": str(df[c].dtype)} for c in df.columns],
        "missing_cells": int(source.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "identifier_column": id_col,
        "distinct_identifiers": int(df[id_col].nunique()) if id_col else None,
    }


def column_statistics(df: pd.DataFrame, args: ColumnStatsArgs) -> dict:
    _require_columns(df, [args.column])
    s = df[args.column]
    if pd.api.types.is_numeric_dtype(s):
        v = s.dropna().astype(float)
        if v.empty:
            raise ToolError(f"Column '{args.column}' has no numeric values.")
        q1, q3 = v.quantile(0.25), v.quantile(0.75)
        return {
            "column": args.column, "type": "numeric", "count": int(v.size),
            "missing": int(s.isna().sum()), "mean": _to_python(v.mean()),
            "median": _to_python(v.median()), "min": _to_python(v.min()),
            "max": _to_python(v.max()), "sum": _to_python(v.sum()),
            "std": _to_python(v.std(ddof=1)) if v.size > 1 else None,
            "q1": _to_python(q1), "q3": _to_python(q3), "iqr": _to_python(q3 - q1),
        }
    if pd.api.types.is_datetime64_any_dtype(s):
        d = s.dropna()
        return {"column": args.column, "type": "date", "count": int(d.size),
                "missing": int(s.isna().sum()),
                "earliest": d.min().date().isoformat() if len(d) else None,
                "latest": d.max().date().isoformat() if len(d) else None}
    counts = s.dropna().astype(str).value_counts()
    return {"column": args.column, "type": "categorical", "count": int(counts.sum()),
            "missing": int(s.isna().sum()), "unique": int(counts.size),
            "top_values": [{"value": k, "count": int(v)} for k, v in counts.head(10).items()]}


def missing_values(df: pd.DataFrame, args: MissingArgs) -> dict:
    if args.column:
        _require_columns(df, [args.column])
        cols = [args.column]
    else:
        cols = list(df.columns)
    total = len(df)
    rows = []
    for c in cols:
        n = int(df[c].isna().sum())
        rows.append({"column": c, "missing": n,
                     "share": round(n / total, 4) if total else 0.0})
    return {"total_rows": total, "columns": rows,
            "total_missing": int(sum(r["missing"] for r in rows))}


def duplicate_records(df: pd.DataFrame, args: DuplicateArgs) -> dict:
    if args.column:
        _require_columns(df, [args.column])
        series = df[args.column].dropna()
        dup_mask = series.duplicated(keep=False)
        values = series[dup_mask].value_counts()
        return {"column": args.column, "repeated_values": int(values.size),
                "affected_rows": int(dup_mask.sum()),
                "examples": [{"value": _to_python(k), "count": int(v)} for k, v in values.head(10).items()]}
    mask = df.duplicated(keep=False)
    return {"scope": "whole_row", "extra_duplicate_rows": int(df.duplicated().sum()),
            "affected_rows": int(mask.sum()),
            "row_indices": [int(i) for i in df.index[mask][:20]]}


def grouped_aggregation(df: pd.DataFrame, args: GroupedAggregationArgs) -> dict:
    _require_columns(df, [args.value_column, args.group_by])
    if not pd.api.types.is_numeric_dtype(df[args.value_column]) and args.agg != "count":
        raise ToolError(f"'{args.value_column}' is not numeric; use agg='count'.")
    grouped = df.groupby(args.group_by, dropna=True)[args.value_column].agg(args.agg)
    grouped = grouped.sort_values(ascending=not args.descending)
    if args.top_n:
        grouped = grouped.head(args.top_n)
    return {"value_column": args.value_column, "group_by": args.group_by, "agg": args.agg,
            "rows": [{args.group_by: str(k), args.agg: _to_python(v)} for k, v in grouped.items()]}


def monthly_aggregation(df: pd.DataFrame, args: MonthlyAggregationArgs) -> dict:
    _require_columns(df, [args.value_column, args.date_column])
    if not pd.api.types.is_datetime64_any_dtype(df[args.date_column]):
        raise ToolError(f"'{args.date_column}' is not a date column.")
    if not pd.api.types.is_numeric_dtype(df[args.value_column]) and args.agg != "count":
        raise ToolError(f"'{args.value_column}' is not numeric; use agg='count'.")
    d = df.dropna(subset=[args.date_column])
    freq = {"month": "M", "quarter": "Q", "year": "Y"}[args.grain]
    period = d[args.date_column].dt.to_period(freq)
    grouped = d.groupby(period)[args.value_column].agg(args.agg)
    return {"value_column": args.value_column, "date_column": args.date_column,
            "agg": args.agg, "grain": args.grain,
            "rows": [{"period": str(k), args.agg: _to_python(v)} for k, v in grouped.items()]}


def correlation(df: pd.DataFrame, args: CorrelationArgs) -> dict:
    _require_columns(df, [args.column_a, args.column_b])
    for c in (args.column_a, args.column_b):
        if not pd.api.types.is_numeric_dtype(df[c]):
            raise ToolError(f"'{c}' is not numeric.")
    pair = df[[args.column_a, args.column_b]].dropna()
    if len(pair) < 3:
        raise ToolError("Not enough complete pairs to compute a correlation.")
    r = pair[args.column_a].corr(pair[args.column_b], method="pearson")
    return {"column_a": args.column_a, "column_b": args.column_b, "method": "pearson",
            "pairs_used": int(len(pair)), "coefficient": _to_python(r)}


def outlier_investigation(df: pd.DataFrame, args: OutlierArgs) -> dict:
    _require_columns(df, [args.column])
    if not pd.api.types.is_numeric_dtype(df[args.column]):
        raise ToolError(f"'{args.column}' is not numeric.")
    v = df[args.column].dropna()
    q1, q3 = v.quantile(0.25), v.quantile(0.75)
    iqr = q3 - q1
    low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    mask = (v < low) | (v > high)
    flagged = v[mask].sort_values(key=lambda s: (s - v.median()).abs(), ascending=False)
    id_col = identifier_column(df.columns)
    def _label(i):
        return _to_python(df.loc[i, id_col]) if id_col else None
    return {"column": args.column, "method": "iqr", "fence_low": _to_python(low),
            "fence_high": _to_python(high), "outlier_count": int(mask.sum()),
            "identifier_column": id_col,
            "rows": [{"row_index": int(i), "row_id": _label(i), "value": _to_python(x)}
                     for i, x in flagged.head(args.limit).items()],
            "note": "Outliers may be legitimate and require investigation."}


# ---------- registry ----------

TOOL_REGISTRY = {
    "dataset_summary": (None, dataset_summary),
    "column_statistics": (ColumnStatsArgs, column_statistics),
    "missing_values": (MissingArgs, missing_values),
    "duplicate_records": (DuplicateArgs, duplicate_records),
    "grouped_aggregation": (GroupedAggregationArgs, grouped_aggregation),
    "monthly_aggregation": (MonthlyAggregationArgs, monthly_aggregation),
    "correlation": (CorrelationArgs, correlation),
    "outlier_investigation": (OutlierArgs, outlier_investigation),
}


def run_tool(name: str, df: pd.DataFrame, raw_args: dict | None = None,
             raw: pd.DataFrame | None = None) -> dict:
    """Validate arguments with Pydantic and execute a registered tool.

    df is the normalised frame. raw (optional) is the original text frame, used for blank-cell counts.
    """
    if name not in TOOL_REGISTRY:
        raise ToolError(f"Unknown tool '{name}'. Allowed: {', '.join(TOOL_REGISTRY)}")
    model, fn = TOOL_REGISTRY[name]
    if model is None:
        return fn(df, raw)
    if name == "missing_values":
        return fn(raw if raw is not None else df, _validate(model, name, raw_args))
    return fn(df, _validate(model, name, raw_args))


def _validate(model, name: str, raw_args: dict | None):
    from pydantic import ValidationError
    try:
        return model.model_validate(raw_args or {})
    except ValidationError as exc:
        raise ToolError(f"Invalid arguments for {name}: {exc.errors()[0]['msg']}") from exc
