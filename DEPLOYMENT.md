# Deployment Guide

A complete, step-by-step guide to deploying the Enterprise RAG Chatbot — from a
laptop to a production server. Covers configuration, every deployment path,
CI/CD, operations, and troubleshooting.

---

## Table of contents

1. [Architecture & components](#1-architecture--components)
2. [Prerequisites](#2-prerequisites)
3. [Get the code](#3-get-the-code)
4. [Configuration (`.env`)](#4-configuration-env)
5. [Path A — Local development (no Docker for the app)](#5-path-a--local-development)
6. [Path B — Docker Compose (build locally)](#6-path-b--docker-compose-build-locally)
7. [Path C — Deploy from Docker Hub (any machine)](#7-path-c--deploy-from-docker-hub-any-machine)
8. [CI/CD setup (GitHub Actions → Docker Hub)](#8-cicd-setup)
9. [Load your documents (ingestion)](#9-load-your-documents-ingestion)
10. [Verify the deployment](#10-verify-the-deployment)
11. [Using the chatbot (API / CLI / UI)](#11-using-the-chatbot)
12. [Production hardening](#12-production-hardening)
13. [Deploy on a cloud VM (end-to-end example)](#13-deploy-on-a-cloud-vm)
14. [Deploy to AKS (Kubernetes)](#deploy-to-aks-kubernetes)
15. [Operations (logs, updates, backup, scaling)](#14-operations)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Architecture & components

```
            ┌─────────────┐   ingest   ┌──────────────┐   embed    ┌──────────┐
  data/ ───▶│  loaders    │──────────▶│   chunker     │──────────▶│  Qdrant  │
 (your docs)│ pdf/docx/md │            │ (overlapping) │  (bge)    │ (vectors)│
            └─────────────┘            └──────────────┘            └────┬─────┘
                                                                        │ top-k
  question ─▶ API ─▶ retrieve ─▶ Claude (Sonnet 4.6) ─▶ answer + citations
```

Three runtime containers:

| Container | Image | Port | Purpose |
|---|---|---|---|
| `qdrant` | `qdrant/qdrant` | 6333 (HTTP), 6334 (gRPC) | Vector database (persists to a volume) |
| `api` | `siddhuge/rag-chatbot` | 8000 | FastAPI service (retrieval + Claude) |
| `ui` | `siddhuge/rag-chatbot` | 8501 | Streamlit web chat (same image, different command) |

External dependency: the **Claude API** (the only paid component). Embeddings
run locally and cost nothing.

---

## 2. Prerequisites

| Requirement | Local dev | Docker deploy |
|---|---|---|
| Docker Engine + Compose v2 | for Qdrant | **required** |
| Python 3.11 | required | not needed |
| Anthropic API key | required | required |
| Disk space | ~3 GB | ~4 GB (image + model + Qdrant) |
| RAM | 2 GB+ | 2 GB+ |

Get an Anthropic API key: **console.anthropic.com → API Keys → Create Key**.

Check your tooling:

```bash
docker --version          # Docker Engine
docker compose version    # Compose v2
python3 --version         # 3.11 (local dev only)
```

---

## 3. Get the code

```bash
git clone https://github.com/Siddhuge/RAG-ChatBot.git
cd RAG-ChatBot
```

For **Path C** (deploy from Docker Hub) you don't need the full repo — only
`docker-compose.deploy.yml` and a `.env`. See section 7.

---

## 4. Configuration (`.env`)

All configuration is environment-driven. Create `.env` from the template:

```bash
cp .env.example .env
```

Edit `.env`. Full reference:

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required.** Your Claude API key. |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Answering model. Use `claude-haiku-4-5` (cheaper) or `claude-opus-4-8` (best). |
| `MAX_TOKENS` | `2048` | Max tokens in the answer. |
| `ENABLE_THINKING` | `false` | `true` enables adaptive thinking (deeper reasoning, higher latency/cost). |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Local embedding model (baked into the image). |
| `QUERY_INSTRUCTION` | (bge prompt) | Instruction prefix added to queries. |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint. In Compose this is overridden to `http://qdrant:6333`. |
| `QDRANT_API_KEY` | — | Set if your Qdrant requires auth. |
| `QDRANT_COLLECTION` | `documents` | Collection name. |
| `DATA_DIR` | `./data` | Where source documents live. |
| `CHUNK_SIZE` | `512` | Approx tokens per chunk. |
| `CHUNK_OVERLAP` | `64` | Token overlap between chunks. |
| `TOP_K` | `5` | Chunks retrieved per query. |
| `SCORE_THRESHOLD` | `0.3` | Minimum similarity score to include a chunk. |
| `LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR`. |
| `APP_API_KEYS` | — | Comma-separated keys that the API accepts. **Empty = open API (dev only).** |
| `CORS_ORIGINS` | `*` | Allowed CORS origins, comma-separated. |
| `RAG_API_URL` | `http://localhost:8000` | Where the CLI/UI find the API. |
| `RAG_API_KEY` | — | Key the CLI/UI send (must match one of `APP_API_KEYS`). |
| `DOCKERHUB_USERNAME` | — | Only for Path C — the Docker Hub namespace to pull from (`siddhuge`). |

### Generate an API key for your own service

`APP_API_KEYS` / `RAG_API_KEY` are **not** from any provider — you invent them
to protect your own API:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put that value in **both** `APP_API_KEYS` and `RAG_API_KEY`.

> ⚠️ `.env` is gitignored — never commit it. In production, inject these via your
> platform's secrets manager instead of a file (see section 12).

---

## 5. Path A — Local development

Run the app from source; only Qdrant runs in Docker.

```bash
# 1. Python environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # installs CPU torch, sentence-transformers, etc.

# 2. Start Qdrant
make qdrant                              # docker run qdrant on :6333

# 3. Configure (.env: QDRANT_URL=http://localhost:6333)

# 4. Add documents and ingest
cp /path/to/docs/*.pdf data/
make ingest                              # python -m scripts.ingest

# 5. Run the API (terminal 1)
make run                                 # uvicorn on :8000, autoreload

# 6. Run the UI (terminal 2, optional)
make ui                                  # streamlit on :8501
```

First ingest/query downloads the embedding model (~130 MB) to your local HF cache.

---

## 6. Path B — Docker Compose (build locally)

The standard self-hosted path. Builds the image from source and runs all three
containers.

```bash
# 1. Configure
cp .env.example .env        # set ANTHROPIC_API_KEY (+ APP_API_KEYS / RAG_API_KEY)

# 2. Add documents
cp /path/to/docs/*.pdf data/

# 3. Build + start everything
docker compose up -d --build
```

- First build takes a few minutes (installs CPU PyTorch, bakes the embedding
  model into the image).
- Services: API `http://localhost:8000`, UI `http://localhost:8501`,
  Qdrant `http://localhost:6333`.

```bash
# 4. Ingest (auth header only if APP_API_KEYS is set)
curl -X POST http://localhost:8000/v1/ingest -H "X-API-Key: <RAG_API_KEY>"

# 5. Check status
docker compose ps
curl -s http://localhost:8000/v1/health
```

Stop / restart:

```bash
docker compose down          # stop (keeps the Qdrant volume / your vectors)
docker compose up -d         # start again (no rebuild)
docker compose up -d --build # rebuild after code changes
```

---

## 7. Path C — Deploy from Docker Hub (any machine)

No source checkout, no local build — pull the published image. You need only
two files on the target machine: `docker-compose.deploy.yml` and `.env`.

```bash
# 1. Get the two files (copy them over, or download from the repo)
mkdir rag-chatbot && cd rag-chatbot
curl -O https://raw.githubusercontent.com/Siddhuge/RAG-ChatBot/main/docker-compose.deploy.yml
curl -O https://raw.githubusercontent.com/Siddhuge/RAG-ChatBot/main/.env.example
mv .env.example .env
mkdir data

# 2. Edit .env — set ANTHROPIC_API_KEY, APP_API_KEYS, RAG_API_KEY, DOCKERHUB_USERNAME=siddhuge

# 3. Pull and start
export DOCKERHUB_USERNAME=siddhuge
docker compose -f docker-compose.deploy.yml --env-file .env up -d

# 4. Add documents + ingest
cp /path/to/docs/*.pdf data/
curl -X POST http://localhost:8000/v1/ingest -H "X-API-Key: <RAG_API_KEY>"
```

`pull_policy: always` ensures each `up` fetches the latest published image.

---

## 8. CI/CD setup

The pipeline ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) tests,
security-scans, builds, scans the image, and publishes to Docker Hub.

### One-time setup

1. **Create a Docker Hub access token:** hub.docker.com → Account Settings →
   Personal access tokens → **Generate new token** (permissions: **Read & Write**).
   Copy it with no trailing spaces/newlines.

2. **Add GitHub repository secrets:** repo → Settings → Secrets and variables →
   Actions → New repository secret:
   - `DOCKERHUB_USERNAME` = `siddhuge` (lowercase — Docker Hub usernames and
     image names must be lowercase)
   - `DOCKERHUB_TOKEN` = the access token from step 1

### How it runs

| Trigger | Result |
|---|---|
| Pull request → `main` | `test` + `security` run (no publish) |
| Push → `main` | full pipeline; publishes `siddhuge/rag-chatbot:latest`, `:main`, `:<sha>` |
| Push tag `v1.2.3` | publishes `:1.2.3`, `:1.2`, `:<sha>` |

Pipeline stages:

```
test      → pytest
security  → Gitleaks (secrets) · Bandit (SAST) · Trivy fs (dep/Dockerfile CVEs)
docker    → login → build → Trivy image scan → push   (only if test+security pass)
```

The image is **scanned before it is pushed** — a CRITICAL vulnerability fails
the build, so a vulnerable image never reaches Docker Hub.

### Cut a release

```bash
git tag v1.0.0
git push origin v1.0.0
```

Watch runs at `https://github.com/Siddhuge/RAG-ChatBot/actions`.

### Automated dependency updates

[`.github/dependabot.yml`](.github/dependabot.yml) opens weekly grouped PRs for
pip, Docker, and GitHub Actions. Each PR is validated by the same CI, so CVEs
arrive as reviewable PRs rather than failed builds.

---

## 9. Load your documents (ingestion)

Supported types: `.pdf`, `.docx`, `.txt`, `.md` (subdirectories scanned
recursively).

```bash
# Add files
cp /path/to/docs/* data/

# Ingest the whole data/ directory
curl -X POST http://localhost:8000/v1/ingest -H "X-API-Key: <RAG_API_KEY>"

# Or upload + ingest a single file
curl -X POST http://localhost:8000/v1/upload \
  -H "X-API-Key: <RAG_API_KEY>" -F "file=@./contract.pdf"
```

Re-ingesting a file **replaces** its chunks (deterministic IDs — no duplicates).
Response: `{"files_processed": N, "chunks_indexed": M, "errors": []}`.

CLI alternative (from source): `make ingest`.

---

## 10. Verify the deployment

```bash
# Containers healthy
docker compose ps                     # api/qdrant healthy

# Readiness + index stats (no auth required)
curl -s http://localhost:8000/v1/health
# {"status":"ok","qdrant":"ok","vectors":<N>, ...}

# End-to-end answer
curl -s -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" -H "X-API-Key: <RAG_API_KEY>" \
  -d '{"question":"What is this corpus about?"}'
```

`vectors > 0` confirms ingestion worked. A JSON answer with `citations` confirms
the full pipeline (retrieval → Claude → grounding).

---

## 11. Using the chatbot

**REST API** (`/v1`, send `X-API-Key` when auth is enabled):

| Endpoint | Purpose |
|---|---|
| `POST /v1/chat` | Ask a question; returns answer + citations + sources |
| `POST /v1/chat/stream` | Same, streamed as SSE (`sources`/`text`/`done` events) |
| `POST /v1/ingest` | Re-index everything in `data/` |
| `POST /v1/upload` | Upload + ingest one file |
| `GET /v1/health` | Health + index stats |
| `GET /docs` | Interactive OpenAPI docs |

Request body for `/v1/chat`:

```json
{"question": "...", "history": [], "top_k": 5, "sources": ["handbook.pdf"]}
```

**Web UI:** open `http://localhost:8501`, enter the API URL and key in the
sidebar, chat with streaming + citation panels.

**CLI** (from source): `python -m scripts.chat "your question"` (one-shot) or
`make ask` (interactive REPL). Reads `RAG_API_URL` / `RAG_API_KEY` from `.env`.

---

## 12. Production hardening

- **Authentication:** always set `APP_API_KEYS` to a strong random value. With
  it empty the API is open.
- **Secrets management:** don't ship a `.env` with real keys. Inject
  `ANTHROPIC_API_KEY` and `APP_API_KEYS` via your platform's secrets store
  (Docker/K8s secrets, AWS Secrets Manager, etc.). Rotate keys if exposed.
- **TLS:** terminate HTTPS at a reverse proxy (nginx/Caddy/Traefik) in front of
  the API and UI — see section 13.
- **CORS:** set `CORS_ORIGINS` to your actual front-end origin(s), not `*`.
- **Scaling:** the API is stateless — run multiple replicas behind a load
  balancer, all pointing at one shared (or managed) Qdrant.
- **Resource sizing:** API container ~1–2 GB RAM (the embedding model loads in
  memory). Qdrant memory scales with vector count.
- **Cost control:** `claude-haiku-4-5` for cheap high-volume Q&A; lower `TOP_K`
  to cut input tokens; keep `ENABLE_THINKING=false` unless needed.
- **Observability:** logs are structured JSON on stdout — ship to your log
  platform (`docker compose logs`, or a log driver).
- **Pin image versions** in production: use a tag like
  `siddhuge/rag-chatbot:1.0.0` instead of `:latest` for reproducible rollouts.

---

## 13. Deploy on a cloud VM

End-to-end on a fresh Ubuntu VM, behind nginx with TLS.

```bash
# 1. Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# 2. Fetch deploy files
mkdir ~/rag && cd ~/rag
curl -O https://raw.githubusercontent.com/Siddhuge/RAG-ChatBot/main/docker-compose.deploy.yml
curl -fsSL https://raw.githubusercontent.com/Siddhuge/RAG-ChatBot/main/.env.example -o .env
mkdir data

# 3. Edit .env — ANTHROPIC_API_KEY, APP_API_KEYS, RAG_API_KEY, DOCKERHUB_USERNAME=siddhuge

# 4. Start
export DOCKERHUB_USERNAME=siddhuge
docker compose -f docker-compose.deploy.yml --env-file .env up -d

# 5. Ingest
cp /path/to/docs/* data/
curl -X POST http://localhost:8000/v1/ingest -H "X-API-Key: <RAG_API_KEY>"
```

Minimal nginx reverse proxy with TLS (after pointing a domain at the VM and
obtaining a cert, e.g. via certbot):

```nginx
server {
    listen 443 ssl;
    server_name rag.example.com;

    ssl_certificate     /etc/letsencrypt/live/rag.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/rag.example.com/privkey.pem;

    location /        { proxy_pass http://127.0.0.1:8501; }   # UI
    location /v1/     { proxy_pass http://127.0.0.1:8000; }   # API
    # SSE needs buffering off for streaming:
    location /v1/chat/stream {
        proxy_pass http://127.0.0.1:8000;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
```

Bind the app ports to localhost only (so they're reachable only via nginx) by
editing the published ports in the compose file to `127.0.0.1:8000:8000` etc.

The stack auto-restarts on reboot (`restart: unless-stopped`).

---

## Deploy to AKS (Kubernetes)

Run the app on Azure Kubernetes Service, published automatically by the CD
workflow. Manifests live in [`k8s/`](k8s/); the cluster is defined in
[`terraform/`](terraform/).

### One-time, per cluster

```bash
# 1. Provision a cost-effective AKS cluster (see terraform/README.md)
cd terraform && terraform init && terraform apply
az aks get-credentials -g rag-chatbot-rg -n rag-chatbot-aks --overwrite-existing

# 2. Install the ingress controller + cert-manager
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.3/deploy/static/provider/cloud/deploy.yaml
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.2/cert-manager.yaml
kubectl -n ingress-nginx wait --for=condition=available deploy/ingress-nginx-controller --timeout=240s
kubectl -n cert-manager wait --for=condition=available deploy --all --timeout=240s

# 3. cert-manager issuers (set your email first)
sed 's/<YOUR_EMAIL>/you@example.com/' k8s/setup/cert-manager-issuers.yaml | kubectl apply -f -

# 4. Point DNS at the ingress IP, and (optionally) automate it — full TLS/DNS
#    details in k8s/INGRESS-SETUP.md
kubectl -n ingress-nginx get svc ingress-nginx-controller   # note EXTERNAL-IP
```

### CD authentication — OIDC (no stored Azure secret)

CD logs into Azure with a **federated credential** (GitHub OIDC), so there's no
long-lived secret. Create the identity once:

```bash
SUB=$(az account show --query id -o tsv)
TENANT=$(az account show --query tenantId -o tsv)

# App registration + service principal
APP_ID=$(az ad app create --display-name rag-chatbot-oidc --query appId -o tsv)
az ad sp create --id "$APP_ID"
SP_OID=$(az ad sp show --id "$APP_ID" --query id -o tsv)

# Federated credential — subject MUST match the deploy trigger (main branch)
az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name":"github-main",
  "issuer":"https://token.actions.githubusercontent.com",
  "subject":"repo:<owner>/<repo>:ref:refs/heads/main",
  "audiences":["api://AzureADTokenExchange"]
}'

# Let CD fetch the kubeconfig + apply to the cluster
az role assignment create --assignee-object-id "$SP_OID" \
  --assignee-principal-type ServicePrincipal \
  --role "Azure Kubernetes Service Cluster User Role" \
  --scope "/subscriptions/$SUB/resourceGroups/rag-chatbot-rg"

echo "AZURE_CLIENT_ID=$APP_ID  AZURE_TENANT_ID=$TENANT  AZURE_SUBSCRIPTION_ID=$SUB"
```

Add `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` as GitHub
secrets. The workflow requests an OIDC token via `permissions: id-token: write`.

### Every deploy (automated by CD)

Once the cluster exists and the CD secrets are set (`AZURE_CLIENT_ID`,
`AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `ANTHROPIC_API_KEY`, `APP_API_KEYS`),
a push to `main` runs CI then [`cd.yml`](.github/workflows/cd.yml), which:

1. logs into Azure and fetches AKS credentials,
2. syncs the `rag-secrets` Secret from your GitHub secrets,
3. `kubectl apply -f k8s/` and rolls out the new image.

Trigger manually anytime from **Actions → CD (AKS) → Run workflow**.

### Verify & use

```bash
kubectl -n rag-chatbot get pods                       # all Running
kubectl -n rag-chatbot get certificate rag-tls        # READY=True (trusted TLS)

# UI:  https://rag.<your-domain>      API: https://api.<your-domain>
curl -X POST https://api.<your-domain>/v1/upload \
  -H "X-API-Key: <APP_API_KEYS value>" -F "file=@yourdoc.pdf"
```

Data persists across pod restarts: Qdrant vectors on its PVC, uploaded files on
the API's `rag-data` PVC.

---

## 14. Operations

**Logs**

```bash
docker compose logs -f            # all services
docker compose logs -f api        # just the API
```

**Update to the latest published image** (Path C)

```bash
docker compose -f docker-compose.deploy.yml pull
docker compose -f docker-compose.deploy.yml up -d
```

**Update from source** (Path B)

```bash
git pull
docker compose up -d --build
```

**Back up the vector store** (the `qdrant_storage` volume holds your index)

```bash
docker run --rm -v rag-chatbot_qdrant_storage:/data -v "$PWD:/backup" \
  alpine tar czf /backup/qdrant-backup.tar.gz -C /data .
```

Restore by extracting into the same volume before starting Qdrant. (You can also
always re-ingest from `data/` to rebuild the index.)

**Scale the API** (shared Qdrant)

```bash
docker compose up -d --scale api=3   # behind a load balancer
```

**Reclaim disk**

```bash
docker builder prune -af     # clear build cache (safe; ~GBs)
docker image prune -f        # remove dangling images
```

---

## 15. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `env file .env not found` | No `.env` | `cp .env.example .env` and edit |
| API container restarts; `error parsing value for field "api_keys"` | Old build before the `NoDecode` fix | Rebuild (`docker compose up -d --build`) |
| Ingest 500: `PermissionError ... /huggingface` | Old build; model cache permission | Rebuild — the model is now baked into the image |
| Chat 500: `401 invalid x-api-key` (in API logs) | Invalid/expired **Anthropic** key | Put a valid `ANTHROPIC_API_KEY` in `.env`, `docker compose up -d` |
| API returns `401` to your curl | Missing/wrong `X-API-Key` | Send a key matching `APP_API_KEYS` |
| `vectors: 0` in health | Nothing ingested | Add files to `data/`, run `/v1/ingest` |
| Docker login: `malformed HTTP Authorization header` | Token has a trailing newline, or **uppercase username** | Re-create the secret cleanly; username must be lowercase |
| CI: `unable to find version` for an action | Bad action tag | Pin a valid tag (we run Trivy via its Docker image to avoid this) |
| Trivy fails with `no space left on device` | Host disk full | `docker builder prune -af`; free disk |
| Build/scan slow first time | Downloading torch + model + Trivy DB | Expected once; subsequent runs are cached |
| UI shows `unhealthy` but works | UI inherits the API healthcheck (probes :8000) | Cosmetic only; the UI serves on :8501 |
| Streaming hangs behind a proxy | Proxy buffering | Disable buffering for `/v1/chat/stream` (see nginx config) |

For Claude-credential failures, the API logs show the upstream error; for
container issues, `docker compose logs <service>` is the first stop.
