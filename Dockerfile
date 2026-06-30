# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # Embedding model is baked into the image at build time (see below) so the
    # container starts instantly and runs offline — no runtime download.
    HF_HOME=/home/appuser/.cache/huggingface

WORKDIR /app

# System deps kept minimal; slim + wheels cover most needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install CPU-only PyTorch FIRST so sentence-transformers reuses it instead of
# pulling the multi-GB CUDA build. Shrinks the image from ~6GB to ~1.5GB.
RUN pip install --no-cache-dir torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY client ./client
COPY ui ./ui

# Run as a non-root user (enterprise hardening).
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data /home/appuser/.cache \
    && chown -R appuser:appuser /app /home/appuser
USER appuser

# Pre-download the embedding model into appuser's cache so it ships in the
# image (works offline; no permission issues from a root-owned volume).
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
