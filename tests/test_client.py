"""Tests for the client SDK using an httpx MockTransport — no live server."""

import json

import httpx

from client import RagClient


def _transport(handler):
    return httpx.MockTransport(handler)


def test_chat_sends_payload_and_parses_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        captured["api_key"] = request.headers.get("x-api-key")
        return httpx.Response(
            200,
            json={
                "answer": "42 days.",
                "citations": [{"cited_text": "42 days", "source": "p.pdf"}],
                "sources": [],
                "model": "claude-sonnet-4-6",
                "usage": {},
            },
        )

    with RagClient(base_url="http://test", api_key="k", transport=_transport(handler)) as c:
        result = c.chat("How long?", top_k=3, sources=["p.pdf"])

    assert result["answer"] == "42 days."
    assert captured["body"]["question"] == "How long?"
    assert captured["body"]["top_k"] == 3
    assert captured["body"]["sources"] == ["p.pdf"]
    assert captured["api_key"] == "k"
    assert captured["url"].endswith("/v1/chat")


def test_chat_stream_parses_sse_events():
    sse = (
        'data: {"type": "sources", "sources": []}\n\n'
        'data: {"type": "text", "text": "Hello "}\n\n'
        'data: {"type": "text", "text": "world"}\n\n'
        'data: {"type": "done", "citations": [], "usage": {}}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})

    with RagClient(base_url="http://test", transport=_transport(handler)) as c:
        events = list(c.chat_stream("hi"))

    types = [e["type"] for e in events]
    assert types == ["sources", "text", "text", "done"]
    answer = "".join(e["text"] for e in events if e["type"] == "text")
    assert answer == "Hello world"


def test_upload_sends_multipart():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["ct"] = request.headers.get("content-type", "")
        captured["body_has_file"] = b"filename=" in request.content
        return httpx.Response(200, json={"files_processed": 1, "chunks_indexed": 3, "errors": []})

    with RagClient(base_url="http://test", transport=_transport(handler)) as c:
        res = c.upload("doc.txt", b"hello world", "text/plain")

    assert res["chunks_indexed"] == 3
    assert captured["ct"].startswith("multipart/form-data")
    assert captured["body_has_file"]


def test_error_status_raises():
    import pytest

    from client import RagClientError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    with RagClient(base_url="http://test", transport=_transport(handler)) as c:
        with pytest.raises(RagClientError):
            c.chat("hi")
