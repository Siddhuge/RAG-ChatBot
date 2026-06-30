# Enterprise RAG Chatbot

A production-grade Retrieval-Augmented Generation chatbot over **your own
documents**. Drop files into `data/`, ingest them, and ask questions through a
**REST API**, a **CLI**, or a **Streamlit web chat UI**. Every answer is
**grounded with citations** that point back to the exact source text — so
answers are verifiable, not hallucinated.

## Why this stack (cost-effective + enterprise-ready)

| Concern | Choice | Why |
|---|---|---|
| Answering LLM | **Claude Sonnet 4.6** | Best quality/cost balance for RAG Q&A; configurable per request |
| Embeddings | **`BAAI/bge-small-en-v1.5`** (local) | Runs on CPU, **zero per-token cost**, fully offline |
| Vector store | **Qdrant** | Production vector DB; free in Docker, scales to managed cloud |
| API | **FastAPI** | Async, streaming (SSE), OpenAPI docs, typed |
| Grounding | **Claude native citations** | Answers cite exact source spans — auditable |
| Hardening | API-key auth, non-root container, JSON logs, healthchecks | Enterprise defaults |

The **only** paid dependency is the Claude API. Embeddings and the vector store
cost nothing to run.

## Architecture

```
            ┌─────────────┐   ingest   ┌──────────────┐   embed    ┌──────────┐
  data/ ───▶│  loaders    │──────────▶│   chunker     │──────────▶│  Qdrant  │
 (your docs)│ pdf/docx/md │            │ (overlapping) │  (bge)    │ (vectors)│
            └─────────────┘            └──────────────┘            └────┬─────┘
                                                                        │ top-k
  question ──▶ /v1/chat ──▶ retrieve ──▶ Claude (Sonnet 4.6) ──▶ answer + citations
                                         documents w/ citations enabled
```

## Quick start (Docker — recommended)

```bash
# 1. Configure
cp .env.example .env
#   edit .env and set ANTHROPIC_API_KEY (and APP_API_KEYS for auth)

# 2. Add documents
cp /path/to/your/*.pdf data/

# 3. Start the stack (API + Qdrant)
docker compose up -d --build

# 4. Ingest your documents
curl -X POST http://localhost:8000/v1/ingest

# 5. Ask a question
curl -s -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is our refund policy?"}' | jq
```

Interactive API docs: <http://localhost:8000/docs>
Web chat UI: <http://localhost:8501> (the `ui` service starts automatically).

## Quick start (local dev)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # set ANTHROPIC_API_KEY; QDRANT_URL=http://localhost:6333
make qdrant                   # start Qdrant in Docker (separate terminal)

cp /path/to/docs/*.pdf data/
make ingest                   # build the index
make run                      # start the API at :8000
```

## Interfaces

Three ways to use the bot — all hit the same REST service, so they share the
same retrieval, grounding, and auth.

### 1. Web chat UI (Streamlit)

A browser chat front-end with streaming answers, citation/source expanders, and
buttons to run ingestion and check health.

```bash
# With docker compose, it's already running:
open http://localhost:8501

# Or locally (API must be running):
make ui            # streamlit run ui/streamlit_app.py
```

Set the API URL and key in the sidebar (or via `RAG_API_URL` / `RAG_API_KEY`).

### 2. CLI

```bash
# One-shot (streams by default)
python -m scripts.chat "What is our refund policy?"

# Interactive multi-turn REPL (/sources, /clear, /exit)
make ask                          # == python -m scripts.chat

# Options
python -m scripts.chat "..." --no-stream --top-k 8 --source handbook.pdf --sources
RAG_API_URL=http://host:8000 RAG_API_KEY=secret python -m scripts.chat "..."
```

### 3. REST API

All endpoints are under `/v1`. If `APP_API_KEYS` is set, send `X-API-Key: <key>`.

### `POST /v1/chat` — ask a question

```json
{
  "question": "How many vacation days do new employees get?",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
  "top_k": 5,
  "sources": ["handbook.pdf"]
}
```

Response:

```json
{
  "answer": "New employees receive 15 vacation days per year.",
  "citations": [
    {"cited_text": "new hires accrue 15 days", "source": "handbook.pdf", "chunk_index": 3}
  ],
  "sources": [{"source": "handbook.pdf", "chunk_index": 3, "score": 0.82, "text": "..."}],
  "model": "claude-sonnet-4-6",
  "usage": {"input_tokens": 1203, "output_tokens": 48}
}
```

### `POST /v1/chat/stream` — streaming (Server-Sent Events)

Same request body. Emits `data:` lines, each a JSON event:

- `{"type": "sources", "sources": [...]}` — what was retrieved (first)
- `{"type": "text", "text": "..."}` — answer tokens as they arrive
- `{"type": "done", "citations": [...], "usage": {...}}` — final metadata

```bash
curl -N -X POST http://localhost:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "Summarize the security policy."}'
```

### `POST /v1/ingest` — (re)index everything in `data/`

### `POST /v1/upload` — upload + ingest one file (multipart `file=@...`)

```bash
curl -X POST http://localhost:8000/v1/upload -F "file=@./contract.pdf"
```

### `GET /v1/health` — liveness/readiness + index stats

## How grounding works

Each retrieved chunk is sent to Claude as a `document` content block with
`citations: {enabled: true}`. Claude is instructed to answer **only** from those
documents and cite what it uses. The response's `citations` carry the exact
`cited_text` and map back to the originating file and chunk — giving you an
audit trail for every claim. If nothing relevant is retrieved, the bot says so
instead of guessing.

## Configuration

All via environment variables / `.env` — see [`.env.example`](.env.example).
Key knobs: `ANTHROPIC_MODEL`, `TOP_K`, `CHUNK_SIZE`, `SCORE_THRESHOLD`,
`ENABLE_THINKING`, `APP_API_KEYS`.

## Testing

```bash
make test        # or: pytest -q
```

Tests mock Qdrant and Claude, so they run with no services and no API key.

## Production notes

- **Auth**: always set `APP_API_KEYS` (comma-separated) in production.
- **Secrets**: inject `ANTHROPIC_API_KEY` via your secrets manager, not a
  committed `.env`.
- **Scaling**: the API is stateless — run multiple replicas behind a load
  balancer. Point them at a shared/managed Qdrant.
- **Cost control**: switch `ANTHROPIC_MODEL` to `claude-haiku-4-5` for cheaper
  high-volume Q&A, or `claude-opus-4-8` for maximum quality. Lower `TOP_K` to
  reduce input tokens.
- **Observability**: logs are structured JSON on stdout — ship to your log
  platform.

## Deployment & CI/CD

### Continuous delivery (GitHub Actions → Docker Hub)

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the test suite on
every push/PR, then builds and publishes the image to Docker Hub. It pushes on
pushes to `main` and on `v*.*.*` tags (PRs build only, no push).

**One-time setup** — add two repository secrets (GitHub → Settings → Secrets and
variables → Actions):

| Secret | Value |
|---|---|
| `DOCKERHUB_USERNAME` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | A Docker Hub **access token** (hub.docker.com → Account Settings → Security → New Access Token) — not your password |

Published image: `<DOCKERHUB_USERNAME>/rag-chatbot`

| Trigger | Tags produced |
|---|---|
| push to `main` | `latest`, `main`, `<short-sha>` |
| tag `v1.2.3` | `1.2.3`, `1.2`, `<short-sha>` |

Cut a release:

```bash
git tag v1.0.0 && git push origin v1.0.0
```

### Deploy on any machine (pull from Docker Hub)

No source checkout needed — just [`docker-compose.deploy.yml`](docker-compose.deploy.yml)
and a `.env`:

```bash
export DOCKERHUB_USERNAME=your-dockerhub-username   # or set it in .env
docker compose -f docker-compose.deploy.yml --env-file .env up -d
```

This pulls `<username>/rag-chatbot:latest` for the API and UI and starts Qdrant
alongside. Then ingest and chat exactly as in Quick Start.
