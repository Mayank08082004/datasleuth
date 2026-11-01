from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(BACKEND_DIR / ".env"), ".env"],
        extra="ignore",
    )

    llm_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "openai/gpt-oss-120b"

    embedding_api_key: str = ""
    embedding_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    embedding_model: str = "gemini-embedding-2"
    embedding_dimensions: int | None = None

    datasleuth_api_key: str = Field(default="change-me")
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    max_upload_mb: int = 20
    max_document_mb: int = 10
    data_dir: Path = Path("./data")
    log_level: str = "INFO"
    rate_limit_per_minute: int = 60
    # Set true only behind a proxy that overwrites X-Forwarded-For (Render does).
    trust_proxy_headers: bool = False
    max_retries: int = 2

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "datasleuth.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
