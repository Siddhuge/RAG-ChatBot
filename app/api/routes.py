"""API routes: chat (sync + streaming), ingestion, upload, health."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.api.security import require_api_key
from app.config import get_settings
from app.models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    IngestResponse,
)
from app.rag import ingest, pipeline, vectorstore
from app.rag.loaders import SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
def chat(req: ChatRequest):
    """Answer a question over the knowledge base (non-streaming)."""
    if req.stream:
        raise HTTPException(400, "Use /chat/stream for streaming responses.")
    history = [t.model_dump() for t in req.history]
    result = pipeline.answer(
        question=req.question, history=history, top_k=req.top_k, sources=req.sources
    )
    return ChatResponse(**result)


@router.post("/chat/stream", dependencies=[Depends(require_api_key)])
async def chat_stream(req: ChatRequest):
    """Stream an answer token-by-token via Server-Sent Events.

    Each SSE `data:` line is a JSON object: {"type": "sources"|"text"|"done", ...}.
    """
    history = [t.model_dump() for t in req.history]

    async def event_generator():
        try:
            async for event in pipeline.answer_stream(
                question=req.question,
                history=history,
                top_k=req.top_k,
                sources=req.sources,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:  # noqa: BLE001
            logger.exception("stream failed")
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/ingest", response_model=IngestResponse, dependencies=[Depends(require_api_key)])
def ingest_endpoint():
    """(Re)ingest every supported file in the data directory."""
    files, chunks, errors = ingest.ingest_directory()
    return IngestResponse(files_processed=files, chunks_indexed=chunks, errors=errors)


@router.post("/upload", response_model=IngestResponse, dependencies=[Depends(require_api_key)])
async def upload(file: UploadFile = File(...)):
    """Upload a single document and ingest it immediately."""
    settings = get_settings()
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported type '{ext}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    # basename() guards against path-traversal in the uploaded filename.
    dest = data_dir / Path(file.filename).name
    dest.write_bytes(await file.read())

    vectorstore.ensure_collection()
    count, err = ingest.ingest_file(dest, str(data_dir))
    return IngestResponse(
        files_processed=1,
        chunks_indexed=count,
        errors=[err] if err else [],
    )


@router.get("/health", response_model=HealthResponse)
def health():
    """Liveness + readiness: confirms Qdrant is reachable."""
    settings = get_settings()
    try:
        vectors = vectorstore.count_vectors()
        qdrant_status = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("qdrant unreachable", extra={"error": str(exc)})
        vectors = 0
        qdrant_status = "unreachable"

    return HealthResponse(
        status="ok" if qdrant_status == "ok" else "degraded",
        qdrant=qdrant_status,
        collection=settings.qdrant_collection,
        vectors=vectors,
        embedding_model=settings.embedding_model,
        llm_model=settings.anthropic_model,
    )
