import logging
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd

from app.config import get_settings
from app.database.db import get_db
from app.models.schemas import DatasetMeta
from app.utils.file_validation import (
    ALLOWED_DATASET_EXTENSIONS,
    FileValidationError,
    check_content,
    check_extension,
    check_size,
    sanitize_filename,
)

logger = logging.getLogger(__name__)

# Columns that look like identifiers keep their text form (leading zeros preserved).
ID_NAME_HINTS = ("id", "code", "number", "no", "sku", "ref")


def _read_frame(content: bytes, ext: str) -> pd.DataFrame:
    try:
        if ext == ".csv":
            # dtype=str preserves leading zeros; numeric inference is applied afterwards per column.
            df = pd.read_csv(BytesIO(content), dtype=str, keep_default_na=True)
        else:
            df = pd.read_excel(BytesIO(content), dtype=str, engine="openpyxl")
    except Exception as exc:  # pandas raises many parser-specific types
        raise FileValidationError(f"Could not parse file: {exc}") from exc

    if df.empty and len(df.columns) == 0:
        raise FileValidationError("File contains no columns.")
    if len(df.columns) == 0:
        raise FileValidationError("File contains no columns.")
    df.columns = [str(c).strip() for c in df.columns]
    if len(set(df.columns)) != len(df.columns):
        raise FileValidationError("Duplicate column names are not supported.")
    return df


COERCE_MAJORITY = 0.9  # a column is converted when at least this share of values parse


def coerce_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Convert text columns to numeric or date when most non-null values parse.

    Unparseable cells become NaN in the normalised frame; the raw frame still holds
    them so the quality engine can report them. ID-like columns and columns with
    leading zeros stay as text so values such as '00123' are not altered.
    """
    out = df.copy()
    for col in out.columns:
        series = out[col]
        non_null = series.dropna().astype(str).str.strip()
        if non_null.empty:
            continue
        lower = col.lower()
        looks_like_id = any(lower == h or lower.endswith(h) for h in ID_NAME_HINTS)
        has_leading_zero = non_null.str.match(r"^0\d+").any()
        if looks_like_id or has_leading_zero:
            continue
        numeric = pd.to_numeric(non_null, errors="coerce")
        if numeric.notna().mean() >= COERCE_MAJORITY:
            out[col] = pd.to_numeric(series.astype(str).str.strip(), errors="coerce")
            continue
        if non_null.str.fullmatch(r"\d+(\.\d+)?").any():
            continue  # plain numbers that failed numeric parsing are not dates
        dates = pd.to_datetime(non_null, errors="coerce", format="mixed")
        if dates.notna().mean() >= COERCE_MAJORITY:
            out[col] = pd.to_datetime(series.astype(str).str.strip(), errors="coerce", format="mixed")
    return out


def load_raw_frame(stored_path: str) -> pd.DataFrame:
    """Original cell values as text (never coerced). Used for invalid-value detection."""
    path = Path(stored_path)
    return _read_frame(path.read_bytes(), path.suffix.lower())


def load_dataset_frame(stored_path: str) -> pd.DataFrame:
    """Normalised frame for statistics: numeric/date columns converted, IDs kept as text."""
    return coerce_frame(load_raw_frame(stored_path))


def _row_to_meta(row) -> DatasetMeta:
    df = load_dataset_frame(row["stored_path"])
    return DatasetMeta(
        dataset_id=row["dataset_id"],
        filename=row["filename"],
        file_type=row["file_type"],
        row_count=int(row["row_count"]),
        column_count=int(row["column_count"]),
        columns=[str(c) for c in df.columns],
        created_at=row["created_at"],
    )


def save_dataset(filename: str, content: bytes) -> DatasetMeta:
    settings = get_settings()
    ext = check_extension(filename, ALLOWED_DATASET_EXTENSIONS)
    check_size(content, settings.max_upload_mb)
    check_content(content, ext)

    df = _read_frame(content, ext)
    dataset_id = str(uuid.uuid4())
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    stored = settings.upload_dir / f"{dataset_id}{ext}"
    stored.write_bytes(content)  # original bytes are kept; the dataset is never modified

    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO datasets (dataset_id, filename, file_type, stored_path, row_count, column_count, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                dataset_id,
                sanitize_filename(filename),
                ext.lstrip("."),
                str(stored),
                len(df),
                len(df.columns),
                created_at,
            ),
        )
    logger.info("dataset_uploaded id=%s rows=%d cols=%d", dataset_id, len(df), len(df.columns))
    return get_dataset(dataset_id)


def list_datasets() -> list[DatasetMeta]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM datasets ORDER BY created_at DESC").fetchall()
    return [_row_to_meta(r) for r in rows]


def get_dataset_row(dataset_id: str):
    with get_db() as conn:
        return conn.execute("SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,)).fetchone()


def get_dataset(dataset_id: str) -> DatasetMeta | None:
    row = get_dataset_row(dataset_id)
    return _row_to_meta(row) if row else None
