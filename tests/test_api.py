"""API tests with the RAG pipeline mocked — no Qdrant/Claude needed."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_payload():
    with patch("app.rag.vectorstore.count_vectors", return_value=42):
        resp = client.get("/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["vectors"] == 42
    assert "llm_model" in body


def test_chat_returns_answer_and_citations():
    fake = {
        "answer": "The policy allows 20 days.",
        "citations": [
            {"cited_text": "20 days of leave", "source": "policy.pdf", "chunk_index": 1}
        ],
        "sources": [
            {"source": "policy.pdf", "chunk_index": 1, "score": 0.9, "text": "..."}
        ],
        "model": "claude-sonnet-4-6",
        "usage": {"input_tokens": 100, "output_tokens": 20},
    }
    with patch("app.rag.pipeline.answer", return_value=fake):
        resp = client.post("/v1/chat", json={"question": "How much leave?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "The policy allows 20 days."
    assert body["citations"][0]["source"] == "policy.pdf"


def test_chat_rejects_empty_question():
    resp = client.post("/v1/chat", json={"question": ""})
    assert resp.status_code == 422


def test_auth_enforced_when_keys_configured():
    from app.config import get_settings

    settings = get_settings()
    settings.api_keys = ["secret-key"]
    try:
        with patch("app.rag.pipeline.answer", return_value={
            "answer": "ok", "citations": [], "sources": [],
            "model": "m", "usage": {},
        }):
            unauth = client.post("/v1/chat", json={"question": "hi"})
            assert unauth.status_code == 401

            authed = client.post(
                "/v1/chat",
                json={"question": "hi"},
                headers={"X-API-Key": "secret-key"},
            )
            assert authed.status_code == 200
    finally:
        settings.api_keys = []
