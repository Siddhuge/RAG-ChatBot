#!/usr/bin/env python3
"""CLI to query the RAG chatbot.

Examples:
    # One-shot question (streams by default)
    python -m scripts.chat "What is our refund policy?"

    # Interactive multi-turn REPL
    python -m scripts.chat

    # Options
    python -m scripts.chat "..." --no-stream --top-k 8 --source handbook.pdf
    RAG_API_URL=http://host:8000 RAG_API_KEY=secret python -m scripts.chat "..."

In the REPL: type a question, /sources to toggle showing retrieved chunks,
/clear to reset history, /exit (or Ctrl-D) to quit.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from client import RagClient, RagClientError

# --- tiny ANSI helpers (no extra deps) ---
_BOLD, _DIM, _CYAN, _YELLOW, _RESET = "\033[1m", "\033[2m", "\033[36m", "\033[33m", "\033[0m"


def _supports_color() -> bool:
    return sys.stdout.isatty()


def c(text: str, color: str) -> str:
    return f"{color}{text}{_RESET}" if _supports_color() else text


def _print_citations(citations: List[dict]) -> None:
    if not citations:
        return
    print("\n" + c("Citations:", _BOLD))
    for i, cit in enumerate(citations, 1):
        src = cit.get("source", "?")
        idx = cit.get("chunk_index")
        loc = f" (chunk {idx})" if idx is not None else ""
        quote = (cit.get("cited_text") or "").strip().replace("\n", " ")
        if len(quote) > 200:
            quote = quote[:197] + "..."
        print(f"  {c(f'[{i}] {src}{loc}', _CYAN)}: {c(quote, _DIM)}")


def _print_sources(sources: List[dict]) -> None:
    if not sources:
        return
    print(c("Retrieved:", _BOLD), end=" ")
    print(
        ", ".join(
            f"{s['source']}#{s['chunk_index']} ({s['score']:.2f})" for s in sources
        )
    )


def ask(
    client: RagClient,
    question: str,
    history: List[dict],
    stream: bool,
    top_k: Optional[int],
    sources: Optional[List[str]],
    show_sources: bool,
) -> str:
    """Ask one question, print the answer, return the assistant text for history."""
    if stream:
        answer_parts: List[str] = []
        print(c("Assistant: ", _BOLD), end="", flush=True)
        for event in client.chat_stream(question, history, top_k, sources):
            etype = event.get("type")
            if etype == "sources" and show_sources:
                _print_sources(event["sources"])
                print(c("Assistant: ", _BOLD), end="", flush=True)
            elif etype == "text":
                sys.stdout.write(event["text"])
                sys.stdout.flush()
                answer_parts.append(event["text"])
            elif etype == "done":
                print()
                _print_citations(event.get("citations", []))
            elif etype == "error":
                print(c(f"\n[error] {event.get('error')}", _YELLOW))
        return "".join(answer_parts)

    result = client.chat(question, history, top_k, sources)
    if show_sources:
        _print_sources(result.get("sources", []))
    print(c("Assistant: ", _BOLD) + result["answer"])
    _print_citations(result.get("citations", []))
    return result["answer"]


def repl(client: RagClient, args) -> int:
    history: List[dict] = []
    show_sources = args.show_sources
    print(c("RAG Chatbot — interactive mode.", _BOLD))
    print(c("Commands: /sources  /clear  /exit", _DIM))
    while True:
        try:
            question = input(c("\nYou: ", _BOLD)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not question:
            continue
        if question in ("/exit", "/quit"):
            return 0
        if question == "/clear":
            history.clear()
            print(c("(history cleared)", _DIM))
            continue
        if question == "/sources":
            show_sources = not show_sources
            print(c(f"(show sources: {show_sources})", _DIM))
            continue
        try:
            answer = ask(
                client, question, history, args.stream, args.top_k, args.source, show_sources
            )
        except RagClientError as exc:
            print(c(f"[error] {exc}", _YELLOW))
            continue
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})


def main() -> int:
    parser = argparse.ArgumentParser(description="Query the RAG chatbot.")
    parser.add_argument("question", nargs="?", help="Question to ask (omit for REPL).")
    parser.add_argument("--url", help="API base URL (default $RAG_API_URL or localhost:8000).")
    parser.add_argument("--api-key", help="API key (default $RAG_API_KEY).")
    parser.add_argument("--top-k", type=int, default=None, help="Chunks to retrieve.")
    parser.add_argument(
        "--source", action="append", help="Restrict to a source filename (repeatable)."
    )
    parser.add_argument(
        "--no-stream", dest="stream", action="store_false", help="Disable streaming."
    )
    parser.add_argument(
        "--sources", dest="show_sources", action="store_true", help="Show retrieved chunks."
    )
    parser.set_defaults(stream=True, show_sources=False)
    args = parser.parse_args()

    client = RagClient(base_url=args.url, api_key=args.api_key)

    if args.question:
        try:
            ask(
                client, args.question, [], args.stream, args.top_k, args.source, args.show_sources
            )
        except RagClientError as exc:
            print(c(f"[error] {exc}", _YELLOW), file=sys.stderr)
            return 1
        return 0

    return repl(client, args)


if __name__ == "__main__":
    raise SystemExit(main())
