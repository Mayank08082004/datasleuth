"""Answers to the audit questions are checked against direct pandas calculations on the sample data."""

import pytest
from fastapi.testclient import TestClient

from app.agents.graph import run_question
from app.database.db import init_db
from app.main import app
from app.services import dataset_service, rag_service

KEY = {"X-API-Key": "test-key-123"}


@pytest.fixture
def ds(sample_csv_bytes, sample_rules_text):
    init_db()
    meta = dataset_service.save_dataset("transactions.csv", sample_csv_bytes)
    raw_text = dataset_service._read_frame(sample_csv_bytes, ".csv")
    norm = dataset_service.coerce_frame(raw_text)
    return {"id": meta.dataset_id, "norm": norm, "raw": raw_text}


def test_row_count_and_distinct_transactions(ds):
    state = run_question(ds["id"], "How many transactions are there?")
    out = state["analysis_results"][0]["output"]
    assert out["row_count"] == len(ds["raw"]) == 76
    assert out["distinct_identifiers"] == ds["raw"]["transaction_id"].nunique() == 75
    assert "76 row(s) (75 distinct transaction_id value(s))" in state["final_response"]


def test_total_amount_matches_pandas(ds):
    state = run_question(ds["id"], "What is the total transaction amount?")
    assert [r["tool"] for r in state["analysis_results"]] == ["column_statistics"]
    expected = ds["norm"]["amount"].sum()
    assert state["analysis_results"][0]["output"]["sum"] == pytest.approx(expected)
    assert f"{expected:,.2f}" in state["final_response"]


def test_highest_region_matches_pandas(ds):
    state = run_question(ds["id"], "Which region has the highest total sales?")
    totals = ds["norm"].groupby("region")["amount"].sum()
    top_region, top_value = totals.idxmax(), totals.max()
    assert f"Highest: {top_region} ({top_value:,.2f})" in state["final_response"]


def test_missing_values_match_pandas(ds):
    state = run_question(ds["id"], "How many missing values are present?")
    missing_tool = next(r for r in state["analysis_results"] if r["tool"] == "missing_values")["output"]
    expected = ds["raw"].isna().sum()
    got = {c["column"]: c["missing"] for c in missing_tool["columns"]}
    for col, n in expected.items():
        assert got[col] == n, col
    # Only blank cells are 'missing'; 'not available' and '2026-02-30' are invalid, reported separately.
    assert missing_tool["total_missing"] == int(expected.sum()) == 2


def test_invalid_dates_name_the_transaction(ds):
    state = run_question(ds["id"], "Which transactions have invalid dates?")
    qc = next(r for r in state["analysis_results"] if r["tool"] == "quality_checks")["output"]
    invalid = [f for f in qc["findings"] if f["category"] == "invalid_dates"]
    assert len(invalid) == 1
    assert invalid[0]["evidence"]["row_ids"] == ["T0075"]
    assert invalid[0]["evidence"]["examples"] == ["2026-02-30"]
    assert "Affected: T0075" in state["final_response"]


def test_invalid_numeric_is_separate_from_missing(ds):
    state = run_question(ds["id"], "Which values are missing or invalid?")
    qc = next(r for r in state["analysis_results"] if r["tool"] == "quality_checks")["output"]
    by_cat = {}
    for f in qc["findings"]:
        by_cat.setdefault(f["category"], []).append(f)
    assert "missing_values" in by_cat and "invalid_numeric" in by_cat
    assert by_cat["invalid_numeric"][0]["evidence"]["examples"] == ["not available"]
    assert by_cat["invalid_numeric"][0]["evidence"]["row_ids"] == ["T0063"]


def test_duplicate_transaction_ids_checked_on_the_id_column(ds):
    state = run_question(ds["id"], "Are there duplicate transaction IDs?")
    dup = next(r for r in state["analysis_results"] if r["tool"] == "duplicate_records")
    assert dup["args"] == {"column": "transaction_id"}
    counts = ds["norm"]["transaction_id"].value_counts()
    assert dup["output"]["repeated_values"] == int((counts > 1).sum()) == 1
    assert dup["output"]["affected_rows"] == 2
    assert "T0001" in state["final_response"]


def test_high_amounts_are_outliers_named_by_transaction(ds):
    state = run_question(ds["id"], "Which transactions have unusually high amounts?")
    out = next(r for r in state["analysis_results"] if r["tool"] == "outlier_investigation")["output"]
    q1, q3 = ds["norm"]["amount"].quantile([0.25, 0.75])
    fence_high = q3 + 1.5 * (q3 - q1)
    expected_count = int((ds["norm"]["amount"] > fence_high).sum())
    assert out["outlier_count"] == expected_count == 2
    top = out["rows"][0]
    assert top["row_id"] == "T0060" and top["value"] == 15000.0
    assert "investigation" in state["final_response"] or "investigate" in state["final_response"]


def test_chart_uses_tool_output_values(ds):
    state = run_question(ds["id"], "What is the average amount by region?")
    tool = state["analysis_results"][0]["output"]
    chart_values = {row["name"]: row["value"] for row in state["chart"]["data"]}
    for row in tool["rows"]:
        assert chart_values[row["region"]] == row["mean"]


def test_unsupported_question_is_refused_honestly(ds):
    state = run_question(ds["id"], "What is the weather in Mumbai today?")
    assert state["analysis_results"] == []
    assert "outside the analyses DataSleuth supports" in state["final_response"]
    assert state["chart"] is None


def test_api_reports_unsupported_as_not_verified(ds, fake_embeddings):
    with TestClient(app) as c:
        body = c.post(f"/api/datasets/{ds['id']}/chat", headers=KEY,
                      json={"question": "What is the weather in Mumbai today?"}).json()
        assert body["verified"] is False
        assert body["analysis_results"] == []


def test_documentation_answer_cites_uploaded_section(ds, fake_embeddings):
    rag_service.ingest_document(ds["id"], "data_dictionary.md",
                                b"# transaction_id\nUnique identifier. Format: letter T followed by four digits.\n\n"
                                b"# region\nSales region: North, South, East or West.")
    with TestClient(app) as c:
        body = c.post(f"/api/datasets/{ds['id']}/chat", headers=KEY,
                      json={"question": "What does the data dictionary say about region?"}).json()
    assert body["citations"], "documentation answers must cite the chunk they used"
    cite = body["citations"][0]
    assert cite["filename"] == "data_dictionary.md"
    assert cite["section"] == "region"
    assert body["verified"] is True


def test_documentation_question_without_documents_says_so(ds, fake_embeddings):
    with TestClient(app) as c:
        body = c.post(f"/api/datasets/{ds['id']}/chat", headers=KEY,
                      json={"question": "What does the data dictionary say about region?"}).json()
    assert body["citations"] == []
    assert any("No uploaded documentation" in lim for lim in body["limitations"])
    assert body["verified"] is False


def test_rules_and_dictionary_both_retrievable_for_same_dataset(ds, fake_embeddings, sample_rules_text):
    rag_service.ingest_document(ds["id"], "business_rules.md", sample_rules_text.encode())
    rag_service.ingest_document(ds["id"], "data_dictionary.md", b"# region\nSales region name.")
    hits = rag_service.retrieve(ds["id"], "region sales rules amounts")
    names = {h["filename"] for h in hits}
    assert {"business_rules.md", "data_dictionary.md"} <= names
    assert all(h["document_type"] in ("business_rules", "data_dictionary") for h in hits)


def test_rule_violations_flow_through_graph(ds, fake_embeddings, sample_rules_text):
    rag_service.ingest_document(ds["id"], "business_rules.md", sample_rules_text.encode())
    state = run_question(ds["id"], "Does this dataset violate the uploaded business rules?")
    rules = next(r for r in state["analysis_results"] if r["tool"] == "business_rule_validation")["output"]
    assert any(v["column"] == "amount" and v["affected_records"] == 2 for v in rules["violations"])
    assert state["validation_results"]["ok"] is True


def test_provider_errors_never_reach_the_answer(ds, monkeypatch):
    """A failing LLM must not break the answer or expose its error text."""
    from app.services import llm_client

    def boom(system, user, temperature=0.0):
        raise llm_client.ProviderError("Provider request failed after 3 attempt(s): HTTP 503.")

    monkeypatch.setattr(llm_client, "chat", boom)
    state = run_question(ds["id"], "What is the average amount by region?")
    assert "LLM explanation unavailable: the provider request failed" in state["final_response"]
    assert "Traceback" not in state["final_response"]
    assert "East: 1,031.58" in state["final_response"]
