import pandas as pd
import pytest

from app.agents import nodes
from app.agents.graph import run_question
from app.database.db import init_db
from app.services import dataset_service
from app.tools.data_tools import ToolError, run_tool


@pytest.fixture
def frame(sample_csv_bytes):
    return dataset_service.coerce_frame(dataset_service._read_frame(sample_csv_bytes, ".csv"))


@pytest.fixture
def stored_dataset(sample_csv_bytes):
    init_db()
    return dataset_service.save_dataset("transactions.csv", sample_csv_bytes)


def test_grouped_sum_matches_pandas(frame):
    out = run_tool("grouped_aggregation", frame,
                   {"value_column": "amount", "group_by": "region", "agg": "sum"})
    expected = frame.groupby("region")["amount"].sum()
    got = {r["region"]: r["sum"] for r in out["rows"]}
    for region, value in expected.items():
        assert got[region] == pytest.approx(value)


def test_monthly_aggregation_matches_pandas(frame):
    out = run_tool("monthly_aggregation", frame,
                   {"value_column": "amount", "date_column": "transaction_date", "agg": "sum"})
    expected = frame.groupby(frame["transaction_date"].dt.to_period("M"))["amount"].sum()
    got = {r["period"]: r["sum"] for r in out["rows"]}
    assert got["2026-03"] == pytest.approx(expected[pd.Period("2026-03")])


def test_correlation_matches_pandas(frame):
    out = run_tool("correlation", frame, {"column_a": "quantity", "column_b": "amount"})
    pair = frame[["quantity", "amount"]].dropna()
    assert out["coefficient"] == pytest.approx(pair["quantity"].corr(pair["amount"]), abs=1e-6)


@pytest.mark.parametrize("name,args", [
    ("grouped_aggregation", {"value_column": "amount", "group_by": "nope"}),
    ("grouped_aggregation", {"value_column": "region", "group_by": "region", "agg": "sum"}),
    ("grouped_aggregation", {"value_column": "amount", "group_by": "region", "agg": "__import__"}),
    ("eval", {}),
    ("column_statistics", {"column": "amount; DROP TABLE datasets"}),
])
def test_tools_reject_invalid_requests(frame, name, args):
    with pytest.raises(ToolError):
        run_tool(name, frame, args)


def test_routing_by_intent():
    cases = {
        "Which columns have missing values?": "quality",
        "Are there duplicate records?": "quality",
        "Does this dataset violate the uploaded business rules?": "business_rules",
        "What is the average revenue by region?": "aggregation",
        "What does the data dictionary say about region?": "documentation",
    }
    for question, expected in cases.items():
        assert nodes.classify({"user_question": question})["intent"] == expected, question


def test_graph_routes_missing_values_to_quality_tools(stored_dataset):
    state = run_question(stored_dataset.dataset_id, "Which columns have missing values?")
    tools = [r["tool"] for r in state["analysis_results"]]
    assert "missing_values" in tools and "quality_checks" in tools
    assert state["validation_results"]["ok"] is True


def test_graph_routes_aggregation_to_grouped_tool(stored_dataset):
    state = run_question(stored_dataset.dataset_id, "What is the average amount by region?")
    assert [r["tool"] for r in state["analysis_results"]] == ["grouped_aggregation"]
    assert state["chart"]["type"] == "bar"


def test_answer_numbers_come_from_tool_output(stored_dataset, frame):
    """Numbers in the final text must match the Python-computed result, not anything the LLM wrote."""
    state = run_question(stored_dataset.dataset_id, "What is the average amount by region?")
    expected_east = frame[frame["region"] == "East"]["amount"].mean()
    assert f"{expected_east:,.2f}" in state["final_response"]


def test_business_rule_question_without_rules_reports_limitation(stored_dataset):
    state = run_question(stored_dataset.dataset_id, "Does this dataset violate the uploaded business rules?")
    assert state["analysis_results"] == []
    assert any("No business-rules document" in lim for lim in state["limitations"])


def test_summary_is_readable_without_llm(stored_dataset):
    state = run_question(stored_dataset.dataset_id, "Which columns have missing values?")
    assert "customer_id" in state["final_response"]
    assert "{" not in state["final_response"], "raw dict dumps must not reach the user"
