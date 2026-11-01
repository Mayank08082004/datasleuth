import io

import pandas as pd
import pytest

from app.database.db import init_db
from app.services import dataset_service, profiling_service, quality_service
from app.services.rules_service import evaluate_rules
from app.utils.file_validation import FileValidationError


@pytest.fixture
def dataset(sample_csv_bytes):
    init_db()
    meta = dataset_service.save_dataset("transactions.csv", sample_csv_bytes)
    row = dataset_service.get_dataset_row(meta.dataset_id)
    return {
        "id": meta.dataset_id,
        "raw": dataset_service.load_raw_frame(row["stored_path"]),
        "norm": dataset_service.load_dataset_frame(row["stored_path"]),
    }


def test_csv_upload_records_metadata(dataset):
    meta = dataset_service.get_dataset(dataset["id"])
    assert meta.file_type == "csv"
    assert meta.row_count == 76 and meta.column_count == 8


def test_xlsx_upload_is_accepted():
    init_db()
    buf = io.BytesIO()
    pd.DataFrame({"sku": ["00123", "00456"], "price": [10.5, 20.0]}).to_excel(buf, index=False)
    meta = dataset_service.save_dataset("items.xlsx", buf.getvalue())
    assert meta.file_type == "xlsx" and meta.row_count == 2
    row = dataset_service.get_dataset_row(meta.dataset_id)
    norm = dataset_service.load_dataset_frame(row["stored_path"])
    assert norm["sku"].tolist() == ["00123", "00456"], "identifiers with leading zeros must be preserved"


@pytest.mark.parametrize("name,content,message", [
    ("data.txt", b"a,b\n1,2", "Unsupported file type"),
    ("empty.csv", b"", "empty"),
    ("bad.xlsx", b"not an excel file", "not an Excel"),
])
def test_malformed_uploads_are_rejected(name, content, message):
    init_db()
    with pytest.raises(FileValidationError, match=message):
        dataset_service.save_dataset(name, content)


def test_profile_classifies_columns(dataset):
    profile = profiling_service.profile_frame(dataset["id"], dataset["norm"])
    kinds = {c.name: c.kind for c in profile.columns}
    assert kinds["transaction_date"] == "date"
    assert kinds["amount"] == "numeric"
    assert kinds["region"] == "categorical"
    amount = next(c for c in profile.columns if c.name == "amount").stats
    assert amount.iqr is not None and amount.q1 is not None and amount.std is not None


def test_missing_values_detected(dataset):
    """Missing = blank cells. Unparseable text is invalid, not missing, so it is not counted here."""
    findings = quality_service.run_quality_checks(dataset["norm"], dataset["raw"])
    missing = {f.column for f in findings if f.category == "missing_values"}
    assert missing == {"customer_id", "quantity"}


def test_invalid_values_detected_from_raw_text(dataset):
    """Requires the raw frame: 'not available' and '2026-02-30' are NaN in the normalised frame."""
    findings = quality_service.run_quality_checks(dataset["norm"], dataset["raw"])
    invalid_numeric = [f for f in findings if f.category == "invalid_numeric"]
    invalid_dates = [f for f in findings if f.category == "invalid_dates"]
    assert invalid_numeric and invalid_numeric[0].evidence["examples"] == ["not available"]
    assert invalid_dates and invalid_dates[0].evidence["examples"] == ["2026-02-30"]


def test_duplicate_rows_and_transaction_ids_detected(dataset):
    findings = quality_service.run_quality_checks(dataset["norm"], dataset["raw"])
    assert any(f.category == "duplicate_rows" and f.affected_records == 1 for f in findings)
    dup_ids = [f for f in findings if f.category == "duplicate_identifiers"]
    assert [f.column for f in dup_ids] == ["transaction_id"], "customer_id repeats legitimately"


def test_iqr_outliers_flagged_for_investigation(dataset):
    findings = quality_service.run_quality_checks(dataset["norm"], dataset["raw"])
    outliers = [f for f in findings if f.category == "statistical_outlier" and f.column == "amount"]
    assert outliers and outliers[0].needs_investigation is True
    assert 15000.0 in outliers[0].evidence["outlier_values"]


def test_quality_checks_do_not_modify_input(dataset):
    before = dataset["norm"].copy(deep=True)
    quality_service.run_quality_checks(dataset["norm"], dataset["raw"])
    pd.testing.assert_frame_equal(before, dataset["norm"])


def test_raw_and_normalised_shapes_must_match(dataset):
    with pytest.raises(ValueError):
        quality_service.run_quality_checks(dataset["norm"], dataset["raw"].iloc[:5])


def test_business_rules_evaluated_deterministically(dataset, sample_rules_text):
    violations, unsupported, evaluated = evaluate_rules(sample_rules_text, dataset["norm"])
    by_col = {v.column: v.affected_records for v in violations}
    assert by_col["transaction_id"] == 2
    assert by_col["customer_id"] == 14
    assert by_col["amount"] == 2
    assert by_col["unit_price"] == 1
    assert "Transaction amounts must be positive." in evaluated  # maps to 'amount'


def test_unsupported_rules_are_reported_not_guessed(dataset):
    text = "Customers should be happy with their order.\nAge must be between 0 and 120."
    _, unsupported, _ = evaluate_rules(text, dataset["norm"])
    assert any("happy" in u.rule for u in unsupported)
    assert any("Age must be between" in u.rule for u in unsupported), "'age' column absent -> unsupported"
