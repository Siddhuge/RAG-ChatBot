"""Retrieval-augmented generation pipeline.

Retrieves the most relevant chunks from Qdrant and asks Claude to answer using
*only* those chunks. Each chunk is passed as a `document` content block with
citations enabled, so Claude returns verifiable citations pointing back to the
exact source text — the key to a trustworthy, enterprise-grade RAG system.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator, Dict, List, Optional, Tuple

import anthropic

from app.config import get_settings
from app.models import Citation, RetrievedChunk
from app.rag import vectorstore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a precise enterprise knowledge assistant. Answer the user's "
    "question using ONLY the information in the provided documents. "
    "Cite the specific text you rely on. If the documents do not contain the "
    "answer, say so plainly — do not use outside knowledge or guess. "
    "Be concise and direct."
)

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        settings = get_settings()
        # Resolves ANTHROPIC_API_KEY from the environment.
        _client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key or None
        )
    return _client


def _build_documents(chunks: List[dict]) -> List[dict]:
    """Turn retrieved chunks into citation-enabled document content blocks."""
    docs = []
    for chunk in chunks:
        title = f"{chunk['source']} (chunk {chunk['chunk_index']})"
        docs.append(
            {
                "type": "document",
                "source": {
                    "type": "text",
                    "media_type": "text/plain",
                    "data": chunk["text"],
                },
                "title": title,
                "citations": {"enabled": True},
            }
        )
    return docs


def _build_messages(
    question: str, history: List[dict], documents: List[dict]
) -> List[dict]:
    messages: List[dict] = []
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    # Documents + question go together in the final user turn.
    messages.append({"role": "user", "content": documents + [{"type": "text", "text": question}]})
    return messages


def _retrieve(
    question: str, top_k: Optional[int], sources: Optional[List[str]]
) -> List[dict]:
    settings = get_settings()
    k = top_k or settings.top_k
    return vectorstore.search(question, top_k=k, sources=sources)


def _request_kwargs(messages: List[dict]) -> dict:
    settings = get_settings()
    kwargs: dict = {
        "model": settings.anthropic_model,
        "max_tokens": settings.max_tokens,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }
    if settings.enable_thinking:
        kwargs["thinking"] = {"type": "adaptive"}
    return kwargs


def _parse_citations(content_blocks, chunks: List[dict]) -> Tuple[str, List[Citation]]:
    answer = ""
    citations: List[Citation] = []
    for block in content_blocks:
        if block.type == "text":
            answer += block.text
            for c in getattr(block, "citations", None) or []:
                idx = getattr(c, "document_index", None)
                chunk = chunks[idx] if idx is not None and idx < len(chunks) else {}
                citations.append(
                    Citation(
                        cited_text=getattr(c, "cited_text", ""),
                        source=chunk.get("source", getattr(c, "document_title", "")),
                        chunk_index=chunk.get("chunk_index"),
                        start_char=getattr(c, "start_char_index", None),
                        end_char=getattr(c, "end_char_index", None),
                    )
                )
    return answer, citations


def answer(
    question: str,
    history: Optional[List[dict]] = None,
    top_k: Optional[int] = None,
    sources: Optional[List[str]] = None,
) -> dict:
    """Synchronous RAG answer with grounded citations."""
    chunks = _retrieve(question, top_k, sources)
    settings = get_settings()

    if not chunks:
        return {
            "answer": "I couldn't find anything relevant in the knowledge base to answer that.",
            "citations": [],
            "sources": [],
            "model": settings.anthropic_model,
            "usage": {},
        }

    documents = _build_documents(chunks)
    messages = _build_messages(question, history or [], documents)
    response = _get_client().messages.create(**_request_kwargs(messages))

    answer_text, citations = _parse_citations(response.content, chunks)
    return {
        "answer": answer_text,
        "citations": [c.model_dump() for c in citations],
        "sources": [RetrievedChunk(**chunk).model_dump() for chunk in chunks],
        "model": response.model,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }


async def answer_stream(
    question: str,
    history: Optional[List[dict]] = None,
    top_k: Optional[int] = None,
    sources: Optional[List[str]] = None,
) -> AsyncIterator[Dict]:
    """Stream tokens, then emit a final event with citations + sources.

    Yields dicts shaped as {"type": "...", ...} for SSE serialization.
    """
    chunks = _retrieve(question, top_k, sources)

    # Always tell the client what was retrieved up front.
    yield {
        "type": "sources",
        "sources": [RetrievedChunk(**chunk).model_dump() for chunk in chunks],
    }

    if not chunks:
        yield {
            "type": "text",
            "text": "I couldn't find anything relevant in the knowledge base to answer that.",
        }
        yield {"type": "done", "citations": [], "usage": {}}
        return

    documents = _build_documents(chunks)
    messages = _build_messages(question, history or [], documents)

    with _get_client().messages.stream(**_request_kwargs(messages)) as stream:
        for event in stream:
            if event.type == "content_block_delta" and event.delta.type == "text_delta":
                yield {"type": "text", "text": event.delta.text}
        final = stream.get_final_message()

    _, citations = _parse_citations(final.content, chunks)
    yield {
        "type": "done",
        "citations": [c.model_dump() for c in citations],
        "usage": {
            "input_tokens": final.usage.input_tokens,
            "output_tokens": final.usage.output_tokens,
        },
    }
