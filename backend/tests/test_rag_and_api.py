import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import llm_client, rag_service
from app.services.llm_client import ProviderNotConfigured

KEY = {"X-API-Key": "test-key-123"}


@pytest.fixture
def client(fake_embeddings):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _upload_dataset(client, csv_bytes):
    r = client.post("/api/datasets/upload", headers=KEY,
                    files={"file": ("transactions.csv", csv_bytes, "text/csv")})
    assert r.status_code == 201
    return r.json()["dataset_id"]


def test_chunking_keeps_markdown_sections_and_pages():
    text = "# Region\nRegions are North, South, East, West.\n\n# Status\nStatus is active or closed."
    segments = rag_service._split_markdown_sections(text)
    assert [s["section"] for s in segments] == ["Region", "Status"]
    chunks = rag_service.chunk_segments([{"text": "x" * 2000, "page": 3, "section": None}])
    assert len(chunks) >= 2 and all(c["page"] == 3 for c in chunks)


def test_document_retrieval_is_dataset_scoped(client, sample_csv_bytes, sample_rules_text, fake_embeddings):
    d1 = _upload_dataset(client, sample_csv_bytes)
    d2 = _upload_dataset(client, sample_csv_bytes)
    rag_service.ingest_document(d1, "data_dictionary.md", b"# Region\nRegion is the sales territory name.")
    rag_service.ingest_document(d2, "other_notes.md", b"# Region\nRegion codes are numeric for archived data.")

    hits = rag_service.retrieve(d1, "What is region?")
    assert hits, "expected at least one hit"
    assert all(h["filename"] == "data_dictionary.md" for h in hits), "must never return another dataset's document"
    assert hits[0]["section"] == "Region"
    assert hits[0]["document_type"] == "data_dictionary"


def test_document_upload_fails_cleanly_without_embedding_key(client, sample_csv_bytes, monkeypatch):
    did = _upload_dataset(client, sample_csv_bytes)
    monkeypatch.setattr(llm_client, "embed", lambda texts: (_ for _ in ()).throw(
        ProviderNotConfigured("EMBEDDING_API_KEY is not set.")))
    r = client.post(f"/api/datasets/{did}/documents", headers=KEY,
                    files={"file": ("rules.md", b"# Rules\nAmounts must be positive.", "text/markdown")})
    assert r.status_code == 503
    assert client.get(f"/api/datasets/{did}/documents", headers=KEY).json()["documents"] == []


def test_api_requires_key(client):
    assert client.get("/api/datasets").status_code == 401
    assert client.get("/api/datasets", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/health").status_code == 200


def test_api_rejects_unsupported_upload(client):
    r = client.post("/api/datasets/upload", headers=KEY, files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 422


def test_api_flow_profile_preview_quality_chat_report(client, sample_csv_bytes):
    did = _upload_dataset(client, sample_csv_bytes)
    assert client.get(f"/api/datasets/{did}/profile", headers=KEY).json()["row_count"] == 76
    preview = client.get(f"/api/datasets/{did}/preview?page=1&page_size=5", headers=KEY).json()
    assert len(preview["rows"]) == 5 and preview["total_rows"] == 76
    quality = client.get(f"/api/datasets/{did}/quality", headers=KEY).json()
    assert any(f["category"] == "missing_values" for f in quality["findings"])
    chat = client.post(f"/api/datasets/{did}/chat", headers=KEY,
                       json={"question": "What is the average amount by region?"}).json()
    assert chat["verified"] is True and chat["chart"]["type"] == "bar"
    report = client.post(f"/api/datasets/{did}/reports", headers=KEY, json={})
    assert report.status_code == 200 and report.json()["overview"]["row_count"] == 76


def test_unknown_dataset_returns_404(client):
    assert client.get("/api/datasets/does-not-exist/profile", headers=KEY).status_code == 404
    assert client.post("/api/datasets/does-not-exist/chat", headers=KEY,
                       json={"question": "missing values?"}).status_code == 404
