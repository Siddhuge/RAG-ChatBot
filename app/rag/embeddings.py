"""Local embedding model wrapper (sentence-transformers, free / offline).

The model is loaded lazily and reused process-wide — loading is expensive
(hundreds of MB), inference is cheap.
"""

from __future__ import annotations

import logging
import threading
from typing import List

from app.config import get_settings

logger = logging.getLogger(__name__)

_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                settings = get_settings()
                logger.info(
                    "loading embedding model", extra={"model": settings.embedding_model}
                )
                _model = SentenceTransformer(settings.embedding_model)
    return _model


def embedding_dimension() -> int:
    return _get_model().get_sentence_embedding_dimension()


def embed_documents(texts: List[str]) -> List[List[float]]:
    """Embed passages for indexing (no query instruction)."""
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(
        texts, normalize_embeddings=True, show_progress_bar=False, batch_size=32
    )
    return [v.tolist() for v in vectors]


def embed_query(text: str) -> List[float]:
    """Embed a search query (bge models want an instruction prefix)."""
    settings = get_settings()
    model = _get_model()
    vector = model.encode(
        settings.query_instruction + text, normalize_embeddings=True
    )
    return vector.tolist()
