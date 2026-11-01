"""Dataset-scoped document RAG.

Documents are chunked, embedded with Google Gemini embedding API and stored in ChromaDB.
Every chunk carries dataset_id, so retrieval for one dataset never sees another's documents.
Handles embedding model changes and dimensionality mismatches safely.
"""

import logging
import re
import uuid
from io import BytesIO
from typing import Any

from app.config import get_settings
from app.database.db import get_db
from app.services import llm_client
from app.utils.file_validation import (
    ALLOWED_DOCUMENT_EXTENSIONS,
    FileValidationError,
    check_content,
    check_extension,
    check_size,
    sanitize_filename,
)

logger = logging.getLogger(__name__)

CHUNK_CHARS = 900
CHUNK_OVERLAP = 150
COLLECTION = "dataset_documents"
_client = None


def _is_dimension_mismatch(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    return "invaliddimension" in name or (
        "dimension" in msg and ("match" in msg or "expected" in msg or "mismatch" in msg)
    )


def _reset_collection(client: Any, model_name: str) -> Any:
    """Safely recreates the ChromaDB collection when model or dimensionality changes."""
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    new_col = client.create_collection(
        COLLECTION,
        metadata={"hnsw:space": "cosine", "embedding_model": model_name},
    )
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM documents")
    except Exception as db_exc:
        logger.warning("Could not clear documents table during ChromaDB reset: %s", db_exc)
    return new_col


def _collection():
    """ChromaDB is imported lazily so the rest of the API runs without it."""
    global _client
    import chromadb  # noqa: WPS433 (lazy by design)

    settings = get_settings()
    if _client is None:
        settings.chroma_dir.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )

    current_model = settings.embedding_model
    try:
        col = _client.get_collection(COLLECTION)
        meta = col.metadata or {}
        col_model = meta.get("embedding_model")
        if col_model and col_model != current_model:
            logger.warning(
                "Embedding model changed from '%s' to '%s'. Incompatible ChromaDB collection '%s' will be reset.",
                col_model,
                current_model,
                COLLECTION,
            )
            return _reset_collection(_client, current_model)
        return col
    except Exception:
        return _client.get_or_create_collection(
            COLLECTION,
            metadata={"hnsw:space": "cosine", "embedding_model": current_model},
        )


def extract_text(filename: str, content: bytes, ext: str) -> list[dict]:
    """Returns a list of {text, page, section} segments."""
    if ext == ".pdf":
        from pypdf import PdfReader

        try:
            reader = PdfReader(BytesIO(content))
        except Exception as exc:
            raise FileValidationError(f"Could not read PDF: {exc}") from exc
        segments = []
        for i, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                segments.append({"text": text, "page": i, "section": None})
        if not segments:
            raise FileValidationError("PDF contains no extractable text (it may be scanned).")
        return segments
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FileValidationError("Text documents must be UTF-8 encoded.") from exc
    return _split_markdown_sections(text)


def _split_markdown_sections(text: str) -> list[dict]:
    segments: list[dict] = []
    section = None
    buffer: list[str] = []
    for line in text.splitlines():
        heading = re.match(r"^#{1,6}\s+(.*)", line)
        if heading:
            if buffer and "\n".join(buffer).strip():
                segments.append({"text": "\n".join(buffer).strip(), "page": None, "section": section})
            buffer = []
            section = heading.group(1).strip()
        buffer.append(line)
    if buffer and "\n".join(buffer).strip():
        segments.append({"text": "\n".join(buffer).strip(), "page": None, "section": section})
    return segments


def chunk_segments(segments: list[dict]) -> list[dict]:
    chunks = []
    for seg in segments:
        text = seg["text"]
        start = 0
        while start < len(text):
            piece = text[start:start + CHUNK_CHARS].strip()
            if piece:
                chunks.append({"text": piece, "page": seg["page"], "section": seg["section"]})
            if start + CHUNK_CHARS >= len(text):
                break
            start += CHUNK_CHARS - CHUNK_OVERLAP
    return chunks


def classify_document(filename: str) -> str:
    name = filename.lower()
    if "dictionary" in name:
        return "data_dictionary"
    if "rule" in name:
        return "business_rules"
    if "description" in name or "readme" in name:
        return "description"
    return "other"


def ingest_document(dataset_id: str, filename: str, content: bytes) -> dict:
    settings = get_settings()
    ext = check_extension(filename, ALLOWED_DOCUMENT_EXTENSIONS)
    check_size(content, settings.max_document_mb)
    check_content(content, ext)

    segments = extract_text(filename, content, ext)
    chunks = chunk_segments(segments)
    if not chunks:
        raise FileValidationError("Document contains no text to index.")

    document_id = str(uuid.uuid4())
    display_name = sanitize_filename(filename)
    doc_type = classify_document(display_name)

    # Embed first: if the embedding provider is unavailable nothing is persisted.
    vectors = llm_client.embed([c["text"] for c in chunks])

    collection = _collection()
    ids = [f"{document_id}:{i}" for i in range(len(chunks))]
    metadatas = [{
        "dataset_id": dataset_id,
        "document_id": document_id,
        "filename": display_name,
        "chunk_id": ids[i],
        "page": c["page"] if c["page"] is not None else -1,
        "section": c["section"] or "",
        "document_type": doc_type,
    } for i, c in enumerate(chunks)]

    try:
        collection.add(ids=ids, embeddings=vectors, documents=[c["text"] for c in chunks], metadatas=metadatas)
    except Exception as exc:
        if _is_dimension_mismatch(exc):
            logger.warning("ChromaDB dimension mismatch during document ingestion (%s). Recreating collection.", exc)
            collection = _reset_collection(_client, settings.embedding_model)
            collection.add(ids=ids, embeddings=vectors, documents=[c["text"] for c in chunks], metadatas=metadatas)
        else:
            raise

    with get_db() as conn:
        conn.execute(
            "INSERT INTO documents (document_id, dataset_id, filename, document_type, stored_path, chunk_count)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (document_id, dataset_id, display_name, doc_type, "", len(chunks)),
        )
    logger.info("document_ingested dataset=%s document=%s chunks=%d", dataset_id, document_id, len(chunks))
    return {"document_id": document_id, "filename": display_name, "document_type": doc_type,
            "chunk_count": len(chunks)}


def list_documents(dataset_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT document_id, dataset_id, filename, document_type, chunk_count, created_at"
            " FROM documents WHERE dataset_id = ? ORDER BY created_at DESC",
            (dataset_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_rules_text(dataset_id: str) -> str | None:
    """All business-rules chunks for one dataset, read directly so similarity search cannot drop rules."""
    with get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE dataset_id = ? AND document_type = 'business_rules'",
            (dataset_id,),
        ).fetchone()[0]
    if not count:
        return None
    try:
        got = _collection().get(where={"$and": [{"dataset_id": dataset_id}, {"document_type": "business_rules"}]})
    except Exception as exc:
        if _is_dimension_mismatch(exc):
            logger.warning("ChromaDB dimension mismatch during get_rules_text (%s). Resetting collection.", exc)
            _reset_collection(_client, get_settings().embedding_model)
            return None
        raise
    return "\n".join(got["documents"]) if got and got["documents"] else None


def retrieve(dataset_id: str, question: str, k: int = 4) -> list[dict]:
    """Semantic search restricted to one dataset. Returns chunks with source metadata."""
    collection = _collection()
    if collection.count() == 0:
        return []
    query_vec = llm_client.embed([question])[0]
    try:
        result = collection.query(
            query_embeddings=[query_vec],
            n_results=k,
            where={"dataset_id": dataset_id},
        )
    except Exception as exc:
        if _is_dimension_mismatch(exc):
            logger.warning("ChromaDB dimension mismatch during retrieval (%s). Resetting collection.", exc)
            _reset_collection(_client, get_settings().embedding_model)
            return []
        raise

    hits = []
    if not result or not result.get("documents") or not result["documents"][0]:
        return hits
    for text, meta, dist in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
        hits.append({
            "text": text,
            "document_id": meta["document_id"],
            "filename": meta["filename"],
            "chunk_id": meta["chunk_id"],
            "page": None if meta["page"] == -1 else meta["page"],
            "section": meta["section"] or None,
            "document_type": meta["document_type"],
            "score": round(1 - float(dist), 4),
        })
    return hits
