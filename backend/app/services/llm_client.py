"""Thin clients for Groq (OpenAI-compatible chat) and Google Gemini (embedding) endpoints.

Calls are made with httpx so no provider SDK is required. Missing credentials raise
ProviderNotConfigured, which the API maps to a 503 with setup instructions.
"""

import logging
import time
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
TIMEOUT_SECONDS = 30.0


class ProviderNotConfigured(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


RETRYABLE_STATUS = (429, 500, 502, 503, 504)


def _post(url: str, payload: dict, headers: dict | None = None) -> dict:
    """POST with bounded retries on rate limits, server errors and transport failures.

    Error messages never include the request, the API key, or the provider's response body.
    """
    settings = get_settings()
    req_headers = headers.copy() if headers else {}
    failure = "unknown error"
    for attempt in range(settings.max_retries + 1):
        try:
            resp = httpx.post(url, json=payload, timeout=TIMEOUT_SECONDS, headers=req_headers)
        except httpx.HTTPError as exc:
            failure = f"transport error ({type(exc).__name__})"
        else:
            if resp.status_code in RETRYABLE_STATUS:
                failure = f"HTTP {resp.status_code}"
            elif resp.status_code >= 400:
                raise ProviderError(f"Provider rejected the request (HTTP {resp.status_code}). "
                                    "Check the API key, model name and base URL.")
            else:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise ProviderError("Provider returned a response that is not valid JSON.") from exc
        if attempt < settings.max_retries:
            time.sleep(min(2 ** attempt, 8))
    raise ProviderError(f"Provider request failed after {settings.max_retries + 1} attempt(s): {failure}.")


def chat(system: str, user: str, temperature: float = 0.0) -> str:
    """Send chat prompt to Groq (OpenAI-compatible /chat/completions endpoint)."""
    settings = get_settings()
    if not settings.llm_api_key:
        raise ProviderNotConfigured("LLM_API_KEY is not set. See backend/README.md.")
    data = _post(
        f"{settings.llm_base_url.rstrip('/')}/chat/completions",
        payload={
            "model": settings.llm_model,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        },
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("Provider response did not contain a chat completion.") from exc
    if not isinstance(content, str) or not content.strip():
        raise ProviderError("Provider returned an empty completion.")
    return content.strip()


def embed(texts: list[str]) -> list[list[float]]:
    """Embed texts using Google Gemini embedding API (:batchEmbedContents).

    Handles batching up to 100 texts per API call as per Google Gemini specifications.
    Input order is strictly preserved.
    """
    settings = get_settings()
    if not settings.embedding_api_key:
        raise ProviderNotConfigured("EMBEDDING_API_KEY is not set. See backend/README.md.")
    if not texts:
        return []

    clean_model = settings.embedding_model.removeprefix("models/")
    base = settings.embedding_base_url.rstrip("/")
    if base.endswith("/models"):
        url = f"{base}/{clean_model}:batchEmbedContents"
    else:
        url = f"{base}/models/{clean_model}:batchEmbedContents"

    headers = {
        "x-goog-api-key": settings.embedding_api_key,
        "Content-Type": "application/json",
    }

    batch_size = 100
    all_vectors: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        requests_payload: list[dict[str, Any]] = []
        for t in batch:
            req: dict[str, Any] = {
                "model": f"models/{clean_model}",
                "content": {"parts": [{"text": t}]},
            }
            if settings.embedding_dimensions:
                req["outputDimensionality"] = settings.embedding_dimensions
            requests_payload.append(req)

        data = _post(url, payload={"requests": requests_payload}, headers=headers)
        if not isinstance(data, dict):
            raise ProviderError("Provider returned a response that is not valid JSON.")

        # Batch response format: {"embeddings": [{"values": [...]}, ...]}
        # Also support single embedContent format: {"embedding": {"values": [...]}}
        if "embeddings" in data and isinstance(data["embeddings"], list):
            batch_vectors: list[list[float]] = []
            for item in data["embeddings"]:
                if not isinstance(item, dict) or "values" not in item or not isinstance(item["values"], list):
                    raise ProviderError("Provider response did not contain embeddings.")
                batch_vectors.append(item["values"])
        elif "embedding" in data and isinstance(data["embedding"], dict) and "values" in data["embedding"]:
            batch_vectors = [data["embedding"]["values"]]
        else:
            raise ProviderError("Provider response did not contain embeddings.")

        if len(batch_vectors) != len(batch):
            raise ProviderError("Provider returned a different number of embeddings than inputs.")

        all_vectors.extend(batch_vectors)

    return all_vectors
