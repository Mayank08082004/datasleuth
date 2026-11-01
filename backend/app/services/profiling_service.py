import numpy as np
import pandas as pd

from app.models.schemas import (
    CategoricalStats,
    ColumnProfile,
    DateStats,
    NumericStats,
    ProfileResponse,
)
from app.services.dataset_service import ID_NAME_HINTS


def _round(value) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return round(float(value), 6)


def _classify(series: pd.Series, name: str) -> str:
    lower = name.lower()
    if any(lower == h or lower.endswith(h) for h in ID_NAME_HINTS) and not pd.api.types.is_float_dtype(series):
        return "identifier"
    if pd.api.types.is_bool_dtype(series):
        return "categorical"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    return "categorical" if series.dropna().nunique() <= max(20, len(series) // 10) else "text"


def numeric_stats(series: pd.Series, missing: int | None = None) -> NumericStats:
    missing = int(series.isna().sum()) if missing is None else missing
    values = series.dropna().astype(float)
    if values.empty:
        return NumericStats(count=0, missing=missing, mean=None, median=None,
                            min=None, max=None, std=None, q1=None, q3=None, iqr=None)
    q1, q3 = values.quantile(0.25), values.quantile(0.75)
    return NumericStats(
        count=int(values.size),
        missing=missing,
        mean=_round(values.mean()),
        median=_round(values.median()),
        min=_round(values.min()),
        max=_round(values.max()),
        std=_round(values.std(ddof=1)) if values.size > 1 else None,
        q1=_round(q1),
        q3=_round(q3),
        iqr=_round(q3 - q1),
    )


def categorical_stats(series: pd.Series, top_n: int = 10, missing: int | None = None) -> CategoricalStats:
    missing = int(series.isna().sum()) if missing is None else missing
    non_null = series.dropna().astype(str)
    counts = non_null.value_counts()
    total = int(counts.sum()) or 1
    top = [
        {"value": str(v), "count": int(c), "share": round(c / total, 4)}
        for v, c in counts.head(top_n).items()
    ]
    return CategoricalStats(
        count=int(non_null.size),
        missing=missing,
        unique=int(counts.size),
        top_values=top,
    )


def date_stats(series: pd.Series, missing: int | None = None) -> DateStats:
    missing = int(series.isna().sum()) if missing is None else missing
    dates = series.dropna()
    if dates.empty:
        return DateStats(count=0, missing=missing, earliest=None, latest=None, range_days=None)
    earliest, latest = dates.min(), dates.max()
    return DateStats(
        count=int(dates.size),
        missing=missing,
        earliest=earliest.date().isoformat(),
        latest=latest.date().isoformat(),
        range_days=int((latest - earliest).days),
    )


def profile_frame(dataset_id: str, df: pd.DataFrame, raw: pd.DataFrame | None = None) -> ProfileResponse:
    """df: normalised frame. raw: original text frame; blank cells there are 'missing', while unparseable
    values (which become NaN in df) are reported as invalid by the quality engine instead."""
    source = raw if raw is not None else df
    columns: list[ColumnProfile] = []
    for name in df.columns:
        series = df[name]
        missing = int(source[name].isna().sum())
        kind = _classify(series, name)
        if kind == "numeric":
            stats = numeric_stats(series, missing)
        elif kind == "date":
            stats = date_stats(series, missing)
        else:
            stats = categorical_stats(series, missing=missing)
        columns.append(ColumnProfile(name=name, dtype=str(series.dtype), kind=kind, stats=stats))

    return ProfileResponse(
        dataset_id=dataset_id,
        row_count=int(len(df)),
        column_count=int(len(df.columns)),
        missing_cells=int(source.isna().sum().sum()),
        duplicate_rows=int(df.duplicated().sum()),
        memory_bytes=int(df.memory_usage(deep=True).sum()),
        columns=columns,
    )
