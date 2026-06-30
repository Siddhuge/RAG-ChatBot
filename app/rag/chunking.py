"""Text chunking.

A recursive splitter that prefers natural boundaries (paragraphs, then
sentences, then words) and falls back to hard character cuts only when a single
unit exceeds the target size. Overlap preserves context across chunk edges so a
fact split across a boundary is still retrievable.

Sizes are measured in characters as a cheap proxy for tokens (~4 chars/token);
CHUNK_SIZE is in approximate tokens, so we scale by 4 internally.
"""

from __future__ import annotations

import re
from typing import List

_CHARS_PER_TOKEN = 4
_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "]


def _split_recursive(text: str, max_chars: int, seps: List[str]) -> List[str]:
    if len(text) <= max_chars:
        return [text]
    if not seps:
        # No separators left — hard cut.
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

    sep = seps[0]
    parts = text.split(sep)
    pieces: List[str] = []
    for part in parts:
        unit = part + sep if part is not parts[-1] else part
        if len(unit) > max_chars:
            pieces.extend(_split_recursive(unit, max_chars, seps[1:]))
        else:
            pieces.append(unit)
    return pieces


def chunk_text(
    text: str, chunk_size_tokens: int = 512, overlap_tokens: int = 64
) -> List[str]:
    """Split text into overlapping chunks roughly chunk_size_tokens long."""
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []

    max_chars = max(chunk_size_tokens * _CHARS_PER_TOKEN, 1)
    overlap_chars = max(overlap_tokens * _CHARS_PER_TOKEN, 0)

    units = _split_recursive(text, max_chars, _SEPARATORS)

    # Greedily pack units into chunks, then add tail-overlap from the previous
    # chunk to the start of the next.
    chunks: List[str] = []
    current = ""
    for unit in units:
        if current and len(current) + len(unit) > max_chars:
            chunks.append(current.strip())
            current = (current[-overlap_chars:] if overlap_chars else "") + unit
        else:
            current += unit
    if current.strip():
        chunks.append(current.strip())

    return [c for c in chunks if c]
