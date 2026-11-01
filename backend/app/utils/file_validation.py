from pathlib import Path

ALLOWED_DATASET_EXTENSIONS = {".csv", ".xlsx"}
ALLOWED_DOCUMENT_EXTENSIONS = {".txt", ".md", ".pdf"}


class FileValidationError(ValueError):
    """Raised when an uploaded file is unsupported or malformed."""


def check_extension(filename: str, allowed: set[str]) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext not in allowed:
        raise FileValidationError(
            f"Unsupported file type '{ext or 'none'}'. Allowed: {', '.join(sorted(allowed))}"
        )
    return ext


def check_size(content: bytes, max_mb: int) -> None:
    if len(content) == 0:
        raise FileValidationError("Uploaded file is empty.")
    if len(content) > max_mb * 1024 * 1024:
        raise FileValidationError(f"File exceeds the {max_mb} MB size limit.")


def check_content(content: bytes, ext: str) -> None:
    """Content must match the extension, not just the filename."""
    if ext == ".xlsx":
        if not content.startswith(b"PK\x03\x04"):
            raise FileValidationError("File is named .xlsx but is not an Excel (zip-based) file.")
    elif ext == ".pdf":
        if not content.startswith(b"%PDF"):
            raise FileValidationError("File is named .pdf but does not start with a PDF header.")
    elif ext in (".csv", ".txt", ".md"):
        if b"\x00" in content[:4096]:
            raise FileValidationError("File looks binary, not text.")
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise FileValidationError("Text files must be UTF-8 encoded.") from exc


def sanitize_filename(filename: str) -> str:
    """Strip directory components and unsafe characters; keeps the original name for display."""
    name = Path(filename or "upload").name
    cleaned = "".join(c if c.isalnum() or c in "._- " else "_" for c in name).strip()
    return cleaned[:200] or "upload"
