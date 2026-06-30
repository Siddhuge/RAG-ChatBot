"""Unit tests for the chunker — no external services required."""

from app.rag.chunking import chunk_text


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_short_text_is_single_chunk():
    text = "This is a short document."
    chunks = chunk_text(text, chunk_size_tokens=512, overlap_tokens=64)
    assert chunks == ["This is a short document."]


def test_long_text_is_split():
    text = ("Sentence number that keeps going. " * 400).strip()
    chunks = chunk_text(text, chunk_size_tokens=64, overlap_tokens=8)
    assert len(chunks) > 1
    # Each chunk should respect the approximate size bound (64 tokens ~ 256 chars,
    # with some slack for overlap and boundary units).
    assert all(len(c) <= 64 * 4 + 64 for c in chunks)


def test_overlap_preserves_context():
    text = "AAAA. BBBB. CCCC. DDDD. EEEE. FFFF. GGGG. HHHH. IIII. JJJJ. " * 20
    chunks = chunk_text(text, chunk_size_tokens=32, overlap_tokens=16)
    assert len(chunks) >= 2
    # Adjacent chunks should share some trailing/leading content.
    assert any(chunks[i][-10:] in chunks[i + 1] for i in range(len(chunks) - 1))
