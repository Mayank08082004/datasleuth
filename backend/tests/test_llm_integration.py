"""Provider integration tests using mocked HTTP responses. No paid API access is needed.

These check request format, response parsing, retries, error handling and key handling
for Groq chat completions and Google Gemini embeddings.
"""

import json
from typing import Any

import httpx
import pytest

from app.config import get_settings
from app.services import llm_client, rag_service
from app.services.llm_client import ProviderError, ProviderNotConfigured

FAKE_CHAT_KEY = "gsk_test_chat_key_do_not_use"
FAKE_EMBED_KEY = "AQ.test_gemini_key_do_not_use"


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", FAKE_CHAT_KEY)
    monkeypatch.setenv("EMBEDDING_API_KEY", FAKE_EMBED_KEY)
    monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("EMBEDDING_MODEL", "gemini-embedding-2")
    monkeypatch.setenv("MAX_RETRIES", "2")
    get_settings.cache_clear()
    monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)
    yield
    get_settings.cache_clear()


def _route(monkeypatch, handler):
    """Routes httpx.post through a MockTransport so the real request construction is exercised."""
    transport = httpx.MockTransport(handler)

    def fake_post(url, **kwargs):
        with httpx.Client(transport=transport) as client:
            return client.post(url, **kwargs)

    monkeypatch.setattr(llm_client.httpx, "post", fake_post)


def test_groq_chat_request_and_response_format(monkeypatch, configured):
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "  Hello from Groq.  "}}]})

    _route(monkeypatch, handler)
    out = llm_client.chat("system prompt", "user prompt")
    assert out == "Hello from Groq."
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen["auth"] == f"Bearer {FAKE_CHAT_KEY}"
    assert seen["body"]["model"] == "openai/gpt-oss-120b"
    assert seen["body"]["temperature"] == 0.0
    assert seen["body"]["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "user prompt"},
    ]


def test_gemini_document_embedding_batch_request_format(monkeypatch, configured):
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["key_header"] = request.headers.get("x-goog-api-key")
        seen["content_type"] = request.headers.get("content-type")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "embeddings": [
                {"values": [0.1, 0.2, 0.3]},
                {"values": [0.4, 0.5, 0.6]},
            ]
        })

    _route(monkeypatch, handler)
    vectors = llm_client.embed(["Chunk one text", "Chunk two text"])
    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert seen["url"] == "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:batchEmbedContents"
    assert seen["key_header"] == FAKE_EMBED_KEY
    assert "application/json" in seen["content_type"]
    assert seen["body"] == {
        "requests": [
            {"model": "models/gemini-embedding-2", "content": {"parts": [{"text": "Chunk one text"}]}},
            {"model": "models/gemini-embedding-2", "content": {"parts": [{"text": "Chunk two text"}]}},
        ]
    }


def test_gemini_query_embedding_single_request_format(monkeypatch, configured):
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "embeddings": [
                {"values": [0.9, 0.8, 0.7]}
            ]
        })

    _route(monkeypatch, handler)
    vectors = llm_client.embed(["What is the regional total?"])
    assert len(vectors) == 1
    assert vectors[0] == [0.9, 0.8, 0.7]
    assert len(seen["body"]["requests"]) == 1
    assert seen["body"]["requests"][0]["content"]["parts"][0]["text"] == "What is the regional total?"


def test_gemini_embedding_custom_dimensionality(monkeypatch, configured):
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "768")
    get_settings.cache_clear()
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"embeddings": [{"values": [0.1] * 768}]})

    _route(monkeypatch, handler)
    vectors = llm_client.embed(["Testing dimensions"])
    assert len(vectors[0]) == 768
    assert seen["body"]["requests"][0]["outputDimensionality"] == 768
    get_settings.cache_clear()


def test_transient_errors_are_retried_then_succeed(monkeypatch, configured):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    _route(monkeypatch, handler)
    assert llm_client.chat("s", "u") == "ok"
    assert calls["n"] == 2


def test_retries_are_bounded(monkeypatch, configured):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503, text="unavailable")

    _route(monkeypatch, handler)
    with pytest.raises(ProviderError, match="3 attempt"):
        llm_client.chat("s", "u")
    assert calls["n"] == 3  # 1 try + MAX_RETRIES=2


def test_client_error_is_not_retried_and_leaks_nothing(monkeypatch, configured):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401, json={"error": f"bad key {FAKE_CHAT_KEY}"})

    _route(monkeypatch, handler)
    with pytest.raises(ProviderError) as exc:
        llm_client.chat("s", "u")
    assert calls["n"] == 1
    assert FAKE_CHAT_KEY not in str(exc.value)
    assert "HTTP 401" in str(exc.value)


def test_gemini_client_error_leaks_no_embedding_key(monkeypatch, configured):
    def handler(request):
        return httpx.Response(403, json={"error": f"permission denied for {FAKE_EMBED_KEY}"})

    _route(monkeypatch, handler)
    with pytest.raises(ProviderError) as exc:
        llm_client.embed(["test doc"])
    assert FAKE_EMBED_KEY not in str(exc.value)
    assert "HTTP 403" in str(exc.value)


def test_network_failure_is_reported_without_secrets(monkeypatch, configured):
    def handler(request):
        raise httpx.ConnectError(f"cannot reach host for {FAKE_CHAT_KEY} or {FAKE_EMBED_KEY}")

    _route(monkeypatch, handler)
    with pytest.raises(ProviderError) as exc:
        llm_client.chat("s", "u")
    assert "ConnectError" in str(exc.value)
    assert FAKE_CHAT_KEY not in str(exc.value)

    with pytest.raises(ProviderError) as exc2:
        llm_client.embed(["test doc"])
    assert "ConnectError" in str(exc2.value)
    assert FAKE_EMBED_KEY not in str(exc2.value)


def test_non_json_and_malformed_responses(monkeypatch, configured):
    _route(monkeypatch, lambda r: httpx.Response(200, text="<html>gateway</html>"))
    with pytest.raises(ProviderError, match="not valid JSON"):
        llm_client.chat("s", "u")

    _route(monkeypatch, lambda r: httpx.Response(200, json={"unexpected": True}))
    with pytest.raises(ProviderError, match="did not contain a chat completion"):
        llm_client.chat("s", "u")

    _route(monkeypatch, lambda r: httpx.Response(200, json={"unexpected": True}))
    with pytest.raises(ProviderError, match="did not contain embeddings"):
        llm_client.embed(["a"])

    _route(monkeypatch, lambda r: httpx.Response(200, json={"embeddings": [{"values": [1.0]}]}))
    with pytest.raises(ProviderError, match="different number of embeddings"):
        llm_client.embed(["a", "b"])


def test_missing_keys_raise_configuration_errors(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("EMBEDDING_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(ProviderNotConfigured, match="LLM_API_KEY"):
        llm_client.chat("s", "u")
    with pytest.raises(ProviderNotConfigured, match="EMBEDDING_API_KEY"):
        llm_client.embed(["x"])
    get_settings.cache_clear()


def test_incompatible_collection_model_change_handled_safely(monkeypatch, configured):
    """When the embedding model changes, ChromaDB collection is safely reset with the new model."""
    from app.database.db import init_db
    init_db()

    # Pre-create a collection with an older model
    col = rag_service._collection()
    import chromadb
    client = rag_service._client
    client.delete_collection(rag_service.COLLECTION)
    old_col = client.create_collection(
        rag_service.COLLECTION,
        metadata={"hnsw:space": "cosine", "embedding_model": "old-text-embedding-3-small"}
    )
    old_col.add(ids=["doc1:0"], embeddings=[[0.1, 0.2]], documents=["old document content"],
                metadatas=[{"dataset_id": "d1"}])

    assert old_col.metadata.get("embedding_model") == "old-text-embedding-3-small"

    # Now when _collection() is accessed under configured (gemini-embedding-2), it detects the mismatch
    new_col = rag_service._collection()
    assert new_col.metadata.get("embedding_model") == "gemini-embedding-2"
    assert new_col.count() == 0


def test_incompatible_collection_dimension_mismatch_recovered_safely(monkeypatch, configured, sample_csv_bytes):
    """If ChromaDB raises a dimension mismatch during ingest or retrieve, it safely recreates the collection."""
    from app.database.db import init_db
    from app.services.dataset_service import save_dataset

    init_db()
    meta = save_dataset("transactions.csv", sample_csv_bytes)
    d1 = meta.dataset_id

    # Create collection with dimension 2
    col = rag_service._collection()
    import chromadb
    client = rag_service._client
    client.delete_collection(rag_service.COLLECTION)
    col = client.create_collection(
        rag_service.COLLECTION,
        metadata={"hnsw:space": "cosine", "embedding_model": "gemini-embedding-2"}
    )
    col.add(ids=["old:0"], embeddings=[[1.0, 0.0]], documents=["old"], metadatas=[{"dataset_id": d1}])

    # Now mock embed to return 3-dimensional vectors (like gemini embeddings)
    monkeypatch.setattr(llm_client, "embed", lambda texts: [[0.5, 0.5, 0.5] for _ in texts])

    # Ingestion should recover safely without crashing
    res = rag_service.ingest_document(d1, "guide.md", b"# Guide\nNew guide content.")
    assert res["chunk_count"] >= 1

    # Retrieval with 3-dimensional vectors should succeed and return the new doc
    hits = rag_service.retrieve(d1, "guide")
    assert len(hits) >= 1
    assert hits[0]["filename"] == "guide.md"


def test_incompatible_collection_query_dimension_mismatch_recovered_safely(monkeypatch, configured):
    """If ChromaDB raises a dimension mismatch during query, it safely resets the collection and returns empty hits."""
    col = rag_service._collection()
    import chromadb
    client = rag_service._client
    client.delete_collection(rag_service.COLLECTION)
    col = client.create_collection(
        rag_service.COLLECTION,
        metadata={"hnsw:space": "cosine", "embedding_model": "gemini-embedding-2"}
    )
    col.add(ids=["old:0"], embeddings=[[1.0, 0.0]], documents=["old"], metadatas=[{"dataset_id": "d1"}])

    # Query with 3-dimensional vectors against 2-dim collection
    monkeypatch.setattr(llm_client, "embed", lambda texts: [[0.5, 0.5, 0.5] for _ in texts])

    hits = rag_service.retrieve("d1", "any question")
    assert hits == []
    # Collection should now be reset and empty
    assert rag_service._collection().count() == 0


def test_llm_answer_with_unsupported_figure_is_replaced(monkeypatch, configured, sample_csv_bytes):
    """If the model invents a number, the computed summary is returned instead."""
    from app.database.db import init_db
    from app.services.dataset_service import save_dataset
    from app.agents.graph import run_question

    init_db()
    meta = save_dataset("transactions.csv", sample_csv_bytes)
    monkeypatch.setattr(llm_client, "chat", lambda system, user, temperature=0.0:
                        "The East region earned 99,999.00 in total.")
    state = run_question(meta.dataset_id, "What is the average amount by region?")
    assert "99,999" not in state["final_response"]
    assert "East: 1,031.58" in state["final_response"]
    assert state["validation_results"]["grounded"] is False
    assert any("not in the computed results" in lim for lim in state["limitations"])


def test_llm_answer_with_grounded_figures_is_kept(monkeypatch, configured, sample_csv_bytes):
    from app.database.db import init_db
    from app.services.dataset_service import save_dataset
    from app.agents.graph import run_question

    init_db()
    meta = save_dataset("transactions.csv", sample_csv_bytes)
    monkeypatch.setattr(llm_client, "chat", lambda system, user, temperature=0.0:
                        "East has the highest average amount at 1,031.58.")
    state = run_question(meta.dataset_id, "What is the average amount by region?")
    assert state["final_response"].startswith("East has the highest average amount")
    assert state["validation_results"]["grounded"] is True
