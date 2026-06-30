"""Ingestion pipeline: discover files -> load -> chunk -> embed -> upsert."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from app.config import get_settings
from app.rag import vectorstore
from app.rag.chunking import chunk_text
from app.rag.loaders import SUPPORTED_EXTENSIONS, load_text

logger = logging.getLogger(__name__)


def discover_files(data_dir: str) -> List[Path]:
    root = Path(data_dir)
    if not root.exists():
        return []
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def ingest_file(path: Path, data_dir: str) -> Tuple[int, Optional[str]]:
    """Ingest a single file. Returns (chunks_indexed, error_message)."""
    settings = get_settings()
    # Use the path relative to data_dir as the stable source identifier.
    try:
        source = str(path.relative_to(data_dir))
    except ValueError:
        source = path.name

    try:
        text = load_text(path)
        if not text.strip():
            return 0, f"{source}: no extractable text"
        chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
        # Replace any prior version of this file before re-indexing.
        vectorstore.delete_source(source)
        count = vectorstore.upsert_chunks(source, chunks)
        logger.info("ingested file", extra={"source": source, "chunks": count})
        return count, None
    except Exception as exc:  # noqa: BLE001 — surface per-file errors, keep going
        logger.exception("ingest failed", extra={"source": source})
        return 0, f"{source}: {exc}"


def ingest_directory(data_dir: Optional[str] = None) -> Tuple[int, int, List[str]]:
    """Ingest every supported file under data_dir.

    Returns (files_processed, chunks_indexed, errors).
    """
    settings = get_settings()
    data_dir = data_dir or settings.data_dir
    vectorstore.ensure_collection()

    files = discover_files(data_dir)
    chunks_total = 0
    errors: List[str] = []
    for path in files:
        count, err = ingest_file(path, data_dir)
        chunks_total += count
        if err:
            errors.append(err)
    return len(files), chunks_total, errors
