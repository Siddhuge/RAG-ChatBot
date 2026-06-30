"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import router
from app.config import get_settings
from app.logging_config import configure_logging
from app.rag import vectorstore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("starting RAG chatbot", extra={"version": __version__})

    if not settings.api_keys:
        logger.warning("APP_API_KEYS not set — API is OPEN (do not run like this in prod)")
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set — chat endpoints will fail")

    # Best-effort: make sure the collection exists so the first query is fast.
    try:
        vectorstore.ensure_collection()
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not reach Qdrant at startup", extra={"error": str(exc)})

    yield
    logger.info("shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Enterprise RAG Chatbot",
        version=__version__,
        description="Retrieval-augmented chatbot over your documents, grounded with citations.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/v1")
    return app


app = create_app()
