"""Streamlit web chat UI for the RAG Chatbot.

Talks to the running API via the shared client SDK. Streams answers token by
token and shows the citations + retrieved chunks behind each answer.

Run:
    streamlit run ui/streamlit_app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

# Make the repo root importable when run via `streamlit run ui/streamlit_app.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client import RagClient, RagClientError  # noqa: E402

st.set_page_config(page_title="Enterprise RAG Chatbot", page_icon="💬", layout="centered")


# --- sidebar: connection + retrieval settings ---
with st.sidebar:
    st.title("⚙️ Settings")
    api_url = st.text_input(
        "API URL", value=os.getenv("RAG_API_URL", "http://localhost:8000")
    )
    api_key = st.text_input(
        "API key", value=os.getenv("RAG_API_KEY", ""), type="password"
    )
    top_k = st.slider("Chunks to retrieve (top_k)", 1, 20, 5)
    sources_raw = st.text_input("Restrict to sources (comma-separated, optional)")
    show_sources = st.checkbox("Show retrieved chunks", value=True)

    client = RagClient(base_url=api_url, api_key=api_key or None)

    st.divider()
    col_a, col_b = st.columns(2)
    if col_a.button("Health"):
        try:
            health = client.health()
            st.success(
                f"{health['status']} · {health['vectors']} vectors · {health['llm_model']}"
            )
        except RagClientError as exc:
            st.error(str(exc))
    if col_b.button("Ingest data/"):
        with st.spinner("Ingesting documents…"):
            try:
                result = client.ingest()
                st.success(
                    f"{result['files_processed']} files · {result['chunks_indexed']} chunks"
                )
                if result.get("errors"):
                    st.warning("\n".join(result["errors"]))
            except RagClientError as exc:
                st.error(str(exc))

    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.rerun()


st.title("💬 Enterprise RAG Chatbot")
st.caption("Answers are grounded in your documents, with citations.")

if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {role, content, citations?, sources?}

sources_filter = [s.strip() for s in sources_raw.split(",") if s.strip()] or None


def _render_citations(citations, sources):
    if sources and show_sources:
        with st.expander(f"🔎 Retrieved {len(sources)} chunk(s)"):
            for s in sources:
                st.markdown(
                    f"**{s['source']}** · chunk {s['chunk_index']} · score {s['score']:.2f}"
                )
                st.caption(s["text"][:500] + ("…" if len(s["text"]) > 500 else ""))
    if citations:
        with st.expander(f"📑 {len(citations)} citation(s)"):
            for i, cit in enumerate(citations, 1):
                quote = (cit.get("cited_text") or "").strip()
                loc = (
                    f" (chunk {cit['chunk_index']})"
                    if cit.get("chunk_index") is not None
                    else ""
                )
                st.markdown(f"**[{i}] {cit.get('source', '?')}{loc}**")
                st.caption(f"“{quote}”")


# Replay history.
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            _render_citations(msg.get("citations"), msg.get("sources"))


# Handle a new question.
if prompt := st.chat_input("Ask a question about your documents…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # History excludes the message we just appended.
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]
    ]

    with st.chat_message("assistant"):
        placeholder = st.empty()
        answer = ""
        citations: list = []
        sources: list = []
        try:
            for event in client.chat_stream(prompt, history, top_k, sources_filter):
                etype = event.get("type")
                if etype == "sources":
                    sources = event["sources"]
                elif etype == "text":
                    answer += event["text"]
                    placeholder.markdown(answer + "▌")
                elif etype == "done":
                    citations = event.get("citations", [])
                elif etype == "error":
                    st.error(event.get("error"))
            placeholder.markdown(answer)
            _render_citations(citations, sources)
        except RagClientError as exc:
            placeholder.empty()
            st.error(str(exc))
            answer = f"_Error: {exc}_"

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "citations": citations, "sources": sources}
    )
