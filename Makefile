.PHONY: help install test ingest run qdrant ask ui up down logs fmt

help:
	@echo "Targets:"
	@echo "  install   Install Python dependencies"
	@echo "  qdrant    Start only Qdrant (Docker) for local dev"
	@echo "  run       Run the API locally with autoreload"
	@echo "  ingest    Ingest ./data into the vector store"
	@echo "  ask       Interactive CLI chat (REPL)"
	@echo "  ui        Launch the Streamlit web chat UI"
	@echo "  test      Run the test suite"
	@echo "  up        Build + start full stack (api + qdrant) via compose"
	@echo "  down      Stop the stack"
	@echo "  logs      Tail the stack logs"

install:
	pip install -r requirements.txt

qdrant:
	docker run -p 6333:6333 -p 6334:6334 -v qdrant_storage:/qdrant/storage qdrant/qdrant:v1.12.5

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

ingest:
	python -m scripts.ingest

ask:
	python -m scripts.chat

ui:
	streamlit run ui/streamlit_app.py

test:
	pytest -q

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f
