"""Pydantic request/response schemas for the API surface."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=8000)
    # Prior turns for multi-turn conversations. The service is stateless; the
    # client owns history.
    history: List[ChatTurn] = Field(default_factory=list)
    top_k: Optional[int] = Field(default=None, ge=1, le=50)
    # Restrict retrieval to specific source filenames (e.g. ["policy.pdf"]).
    sources: Optional[List[str]] = None
    stream: bool = False


class Citation(BaseModel):
    cited_text: str
    source: str
    chunk_index: Optional[int] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None


class RetrievedChunk(BaseModel):
    source: str
    chunk_index: int
    score: float
    text: str


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    sources: List[RetrievedChunk] = Field(default_factory=list)
    model: str
    usage: dict = Field(default_factory=dict)


class IngestResponse(BaseModel):
    files_processed: int
    chunks_indexed: int
    errors: List[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    qdrant: str
    collection: str
    vectors: int
    embedding_model: str
    llm_model: str
