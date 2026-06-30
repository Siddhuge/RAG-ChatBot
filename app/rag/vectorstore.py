"""Qdrant vector store wrapper.

Encapsulates collection lifecycle, upsert (idempotent by content), and search.
Re-ingesting the same file replaces its points rather than duplicating them,
because point IDs are deterministic (uuid5 of source + chunk index).
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.config import get_settings
from app.rag import embeddings

logger = logging.getLogger(__name__)

_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00cf4fc964ff")
_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            timeout=30,
        )
    return _client


def point_id(source: str, chunk_index: int) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{source}::{chunk_index}"))


def ensure_collection() -> None:
    """Create the collection if it doesn't exist (dimension from the model)."""
    settings = get_settings()
    client = get_client()
    dim = embeddings.embedding_dimension()
    if not client.collection_exists(settings.qdrant_collection):
        logger.info(
            "creating collection",
            extra={"collection": settings.qdrant_collection, "dim": dim},
        )
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )
        # Index the source field so per-document filtering is fast.
        client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="source",
            field_schema=qm.PayloadSchemaType.KEYWORD,
        )


def delete_source(source: str) -> None:
    """Remove all chunks belonging to one source file."""
    settings = get_settings()
    get_client().delete(
        collection_name=settings.qdrant_collection,
        points_selector=qm.FilterSelector(
            filter=qm.Filter(
                must=[qm.FieldCondition(key="source", match=qm.MatchValue(value=source))]
            )
        ),
    )


def upsert_chunks(source: str, chunks: List[str]) -> int:
    """Embed and store chunks for one source. Returns count indexed."""
    if not chunks:
        return 0
    settings = get_settings()
    vectors = embeddings.embed_documents(chunks)
    points = [
        qm.PointStruct(
            id=point_id(source, i),
            vector=vec,
            payload={"source": source, "chunk_index": i, "text": chunk},
        )
        for i, (chunk, vec) in enumerate(zip(chunks, vectors))
    ]
    get_client().upsert(collection_name=settings.qdrant_collection, points=points)
    return len(points)


def search(
    query: str, top_k: int, sources: Optional[List[str]] = None
) -> List[dict]:
    """Return the top_k most relevant chunks, optionally filtered by source."""
    settings = get_settings()
    query_vector = embeddings.embed_query(query)

    flt = None
    if sources:
        flt = qm.Filter(
            must=[qm.FieldCondition(key="source", match=qm.MatchAny(any=sources))]
        )

    results = get_client().query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        limit=top_k,
        query_filter=flt,
        score_threshold=settings.score_threshold,
        with_payload=True,
    ).points

    return [
        {
            "source": r.payload["source"],
            "chunk_index": r.payload["chunk_index"],
            "text": r.payload["text"],
            "score": r.score,
        }
        for r in results
    ]


def count_vectors() -> int:
    settings = get_settings()
    try:
        return get_client().count(settings.qdrant_collection, exact=True).count
    except Exception:
        return 0
