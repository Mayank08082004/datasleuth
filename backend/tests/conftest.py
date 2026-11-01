import hashlib
import math
import re
from pathlib import Path

import pytest

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample_data"
TEST_KEY = "test-key-123"


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Each test gets its own data directory, database and vector store."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATASLEUTH_API_KEY", TEST_KEY)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1000")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    from app.config import get_settings
    from app.services import rag_service
    from app.agents import graph
    get_settings.cache_clear()
    rag_service._client = None
    graph._graph = None
    yield
    get_settings.cache_clear()
    rag_service._client = None
    graph._graph = None


@pytest.fixture
def sample_csv_bytes() -> bytes:
    return (SAMPLE_DIR / "transactions.csv").read_bytes()


@pytest.fixture
def sample_rules_text() -> str:
    return (SAMPLE_DIR / "business_rules.md").read_text()


@pytest.fixture
def fake_embeddings(monkeypatch):
    """Deterministic bag-of-words embeddings, so RAG can be tested without a provider key."""
    from app.services import llm_client
    dim = 256

    def _vec(text: str) -> list[float]:
        v = [0.0] * dim
        for token in re.findall(r"[a-z]+", text.lower()):
            idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % dim
            v[idx] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    monkeypatch.setattr(llm_client, "embed", lambda texts: [_vec(t) for t in texts])
    # The LLM is not configured in tests: explanations fall back to deterministic summaries.
    def _no_llm(system, user, temperature=0.0):
        raise llm_client.ProviderNotConfigured("LLM_API_KEY is not set.")

    monkeypatch.setattr(llm_client, "chat", _no_llm)
    return _vec
