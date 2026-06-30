"""Thin Python client for the RAG Chatbot REST API.

Shared by the CLI (scripts/chat.py) and the Streamlit UI (ui/streamlit_app.py)
so both talk to the same running service rather than importing the server.
"""

from client.sdk import RagClient, RagClientError

__all__ = ["RagClient", "RagClientError"]
