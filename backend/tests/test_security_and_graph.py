"""Upload safety, API hygiene, and LangGraph control-flow tests."""

import pytest
from fastapi.testclient import TestClient

from app.agents import graph as graph_module
from app.agents import nodes
from app.agents.graph import build_graph, run_question
from app.database.db import init_db
from app.main import app
from app.services import dataset_service
from app.utils.file_validation import FileValidationError

KEY = {"X-API-Key": "test-key-123"}


# ---------- upload safety ----------

@pytest.mark.parametrize("name,content,message", [
    ("data.csv", b"\x00\x01\x02binary", "binary"),
    ("data.csv", "caf\xe9,1\n".encode("latin-1"), "UTF-8"),
    ("data.xlsx", b"just text, not a zip", ".xlsx but is not"),
    ("data.exe", b"MZ\x90\x00", "Unsupported file type"),
])
def test_content_must_match_extension(name, content, message):
    init_db()
    with pytest.raises(FileValidationError, match=message):
        dataset_service.save_dataset(name, content)


def test_path_traversal_filename_is_neutralised(sample_csv_bytes):
    init_db()
    meta = dataset_service.save_dataset("../../etc/passwd.csv", sample_csv_bytes)
    row = dataset_service.get_dataset_row(meta.dataset_id)
    assert meta.filename == "passwd.csv"
    # Stored under a generated UUID inside DATA_DIR, never under the supplied name.
    assert "passwd" not in row["stored_path"] and row["stored_path"].endswith(".csv")
    assert str(row["stored_path"]).startswith(str(dataset_service.get_settings().upload_dir))


def test_document_upload_rejects_fake_pdf(fake_embeddings, sample_csv_bytes):
    with TestClient(app) as c:
        did = c.post("/api/datasets/upload", headers=KEY,
                     files={"file": ("t.csv", sample_csv_bytes, "text/csv")}).json()["dataset_id"]
        r = c.post(f"/api/datasets/{did}/documents", headers=KEY,
                   files={"file": ("rules.pdf", b"not really a pdf", "application/pdf")})
    assert r.status_code == 422 and "PDF header" in r.json()["detail"]


def test_api_errors_do_not_expose_internals(fake_embeddings):
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/datasets/does-not-exist/profile", headers=KEY)
        assert r.status_code == 404
        assert "Traceback" not in r.text and "File \"" not in r.text


def test_rate_limit_uses_forwarded_client_when_trusted(monkeypatch):
    from app.config import get_settings
    from app.utils import security
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    get_settings.cache_clear()
    security._hits.clear()

    class Req:
        client = type("C", (), {"host": "10.0.0.1"})()
        headers = {"x-forwarded-for": "203.0.113.7, 10.0.0.1"}

    security.rate_limit(Req())
    security.rate_limit(Req())
    with pytest.raises(Exception) as exc:
        security.rate_limit(Req())
    assert exc.value.status_code == 429
    assert "203.0.113.7" in security._hits and "10.0.0.1" not in security._hits
    get_settings.cache_clear()


# ---------- LangGraph control flow ----------

def _visited(dataset_id: str, question: str) -> list[str]:
    compiled = build_graph()
    seen = []
    for update in compiled.stream({"dataset_id": dataset_id, "user_question": question, "retries": 0,
                                   "limitations": [], "analysis_results": [], "retrieved_documents": []},
                                  stream_mode="updates"):
        seen.extend(update.keys())
    return seen


@pytest.fixture
def dataset_id(sample_csv_bytes):
    init_db()
    return dataset_service.save_dataset("transactions.csv", sample_csv_bytes).dataset_id


def test_routing_analytical_path(dataset_id):
    path = _visited(dataset_id, "What is the average amount by region?")
    assert path == ["classify", "validate", "plan", "analyse", "verify", "make_chart", "respond", "check_grounding"]


def test_routing_documentation_path(dataset_id, fake_embeddings):
    path = _visited(dataset_id, "What does the data dictionary say about region?")
    assert path == ["classify", "validate", "retrieve", "verify", "make_chart", "respond", "check_grounding"]


def test_routing_business_rules_path(dataset_id, fake_embeddings):
    path = _visited(dataset_id, "Does this dataset violate the uploaded business rules?")
    assert path == ["classify", "validate", "retrieve", "rules", "verify", "make_chart", "respond", "check_grounding"]


def test_routing_unsupported_question_skips_tools(dataset_id):
    path = _visited(dataset_id, "What is the weather in Mumbai today?")
    assert "analyse" in path  # planning found nothing; analysis node runs with an empty plan
    state = run_question(dataset_id, "What is the weather in Mumbai today?")
    assert state["analysis_results"] == []


def test_retries_are_bounded_when_verification_keeps_failing(dataset_id, monkeypatch):
    """A verifier that always fails must not loop forever: planning runs at most MAX_RETRIES + 1 times."""
    def always_fail(state, frames):
        return {"validation_results": {"ok": False, "problems": ["forced"]},
                "retries": state.get("retries", 0) + 1}

    monkeypatch.setattr(nodes, "verify", always_fail)
    monkeypatch.setattr(graph_module, "_graph", None)
    path = _visited(dataset_id, "What is the average amount by region?")
    assert path.count("plan") == graph_module.MAX_RETRIES + 1
    assert path[-1] == "check_grounding"


def test_dataset_isolation_for_analysis(sample_csv_bytes):
    init_db()
    a = dataset_service.save_dataset("a.csv", b"region,amount\nNorth,10\nSouth,20\n")
    b = dataset_service.save_dataset("b.csv", b"region,amount\nEast,500\n")
    state_a = run_question(a.dataset_id, "What is the total amount by region?")
    state_b = run_question(b.dataset_id, "What is the total amount by region?")
    assert "East" not in state_a["final_response"] and "North" in state_a["final_response"]
    assert "North" not in state_b["final_response"] and "East" in state_b["final_response"]


def test_every_api_route_requires_the_key():
    """Only /health may be unauthenticated; every /api route must carry the API-key dependency."""
    from app.utils.security import require_api_key
    api_routes = [r for r in app.routes if getattr(r, "path", "").startswith("/api")]
    assert len(api_routes) >= 10
    for route in api_routes:
        deps = [d.call for d in route.dependant.dependencies]
        assert require_api_key in deps, f"{route.path} is missing the API key check"
