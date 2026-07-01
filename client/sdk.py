"""HTTP client for the RAG Chatbot API.

Wraps the `/v1` endpoints with typed-ish helpers and SSE stream parsing so
callers don't reimplement transport. Reads sensible defaults from the
environment (RAG_API_URL, RAG_API_KEY).
"""

from __future__ import annotations

import json
import os
from typing import Dict, Iterator, List, Optional

import httpx


class RagClientError(RuntimeError):
    """Raised when the API returns an error or is unreachable."""


class RagClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 120.0,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        base_url = (base_url or os.getenv("RAG_API_URL", "http://localhost:8000")).rstrip("/")
        self.api_key = api_key or os.getenv("RAG_API_KEY") or None
        # No default Content-Type: httpx sets it per request (application/json for
        # json=, multipart/form-data for files=). A fixed default would break uploads.
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        # A single client gives connection reuse and an injection point for tests.
        self._client = httpx.Client(
            base_url=base_url, timeout=timeout, headers=headers, transport=transport
        )

    # --- context management / cleanup ---

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "RagClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- payload helper ---

    @staticmethod
    def _payload(
        question: str,
        history: Optional[List[dict]],
        top_k: Optional[int],
        sources: Optional[List[str]],
    ) -> dict:
        return {
            "question": question,
            "history": history or [],
            "top_k": top_k,
            "sources": sources,
        }

    # --- introspection ---

    def health(self) -> dict:
        return self._request("GET", "/v1/health")

    def ingest(self) -> dict:
        return self._request("POST", "/v1/ingest", {})

    def upload(
        self, filename: str, content: bytes, content_type: str = "application/octet-stream"
    ) -> dict:
        """Upload a single document; the server saves it and ingests it."""
        files = {"file": (filename, content, content_type)}
        try:
            resp = self._client.post("/v1/upload", files=files)
        except httpx.HTTPError as exc:
            raise RagClientError(f"Request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise RagClientError(f"{resp.status_code}: {resp.text}")
        return resp.json()

    # --- chat ---

    def chat(
        self,
        question: str,
        history: Optional[List[dict]] = None,
        top_k: Optional[int] = None,
        sources: Optional[List[str]] = None,
    ) -> dict:
        """Non-streaming answer. Returns the full ChatResponse dict."""
        return self._request(
            "POST", "/v1/chat", self._payload(question, history, top_k, sources)
        )

    def chat_stream(
        self,
        question: str,
        history: Optional[List[dict]] = None,
        top_k: Optional[int] = None,
        sources: Optional[List[str]] = None,
    ) -> Iterator[dict]:
        """Stream answer events. Yields {"type": "sources"|"text"|"done"|"error", ...}."""
        payload = self._payload(question, history, top_k, sources)
        try:
            with self._client.stream("POST", "/v1/chat/stream", json=payload) as resp:
                if resp.status_code >= 400:
                    resp.read()
                    raise RagClientError(f"{resp.status_code}: {resp.text}")
                for line in resp.iter_lines():
                    if line and line.startswith("data: "):
                        yield json.loads(line[len("data: ") :])
        except httpx.HTTPError as exc:
            raise RagClientError(f"Request failed: {exc}") from exc

    # --- transport ---

    def _request(self, method: str, path: str, payload: Optional[dict] = None) -> dict:
        try:
            resp = self._client.request(method, path, json=payload)
        except httpx.HTTPError as exc:
            raise RagClientError(f"Request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise RagClientError(f"{resp.status_code}: {resp.text}")
        return resp.json()
