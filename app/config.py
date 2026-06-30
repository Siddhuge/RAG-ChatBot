"""Centralized application configuration.

All settings are read from environment variables (or a local .env file) so the
same image runs unchanged across dev, staging, and prod — only the environment
differs. See .env.example for the full list.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing_extensions import Annotated


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Claude / Anthropic ---
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-6", alias="ANTHROPIC_MODEL")
    max_tokens: int = Field(default=2048, alias="MAX_TOKENS")
    # Adaptive thinking trades latency/cost for harder reasoning. Off by default
    # for a Q&A bot; flip ENABLE_THINKING=true for analysis-heavy corpora.
    enable_thinking: bool = Field(default=False, alias="ENABLE_THINKING")

    # --- Embeddings (local, free) ---
    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5", alias="EMBEDDING_MODEL"
    )
    # bge models expect this instruction prefixed to *queries* (not documents).
    query_instruction: str = Field(
        default="Represent this sentence for searching relevant passages: ",
        alias="QUERY_INSTRUCTION",
    )

    # --- Vector store (Qdrant) ---
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="documents", alias="QDRANT_COLLECTION")

    # --- Ingestion / retrieval ---
    data_dir: str = Field(default="./data", alias="DATA_DIR")
    chunk_size: int = Field(default=512, alias="CHUNK_SIZE")  # approx tokens
    chunk_overlap: int = Field(default=64, alias="CHUNK_OVERLAP")
    top_k: int = Field(default=5, alias="TOP_K")
    score_threshold: float = Field(default=0.3, alias="SCORE_THRESHOLD")

    # --- API server ---
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    # Comma-separated keys. If empty, the API is open (dev). Set in prod.
    # NoDecode disables pydantic-settings' JSON parsing so the raw string
    # reaches our CSV-splitting validator below (otherwise a plain key 400s).
    api_keys: Annotated[List[str], NoDecode] = Field(
        default_factory=list, alias="APP_API_KEYS"
    )
    cors_origins: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: ["*"], alias="CORS_ORIGINS"
    )

    @field_validator("api_keys", "cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so config is parsed once per process."""
    return Settings()
