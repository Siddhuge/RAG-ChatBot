#!/usr/bin/env python3
"""CLI to ingest the data directory into the vector store.

Usage:
    python -m scripts.ingest            # ingest ./data (or $DATA_DIR)
    python -m scripts.ingest ./mydocs   # ingest a specific directory
"""

from __future__ import annotations

import sys

from app.config import get_settings
from app.logging_config import configure_logging
from app.rag import ingest


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)

    data_dir = sys.argv[1] if len(sys.argv) > 1 else settings.data_dir
    print(f"Ingesting documents from: {data_dir}")
    files, chunks, errors = ingest.ingest_directory(data_dir)

    print(f"\n  Files processed : {files}")
    print(f"  Chunks indexed  : {chunks}")
    if errors:
        print(f"  Errors ({len(errors)}):")
        for err in errors:
            print(f"    - {err}")
    print("\nDone.")
    return 1 if errors and chunks == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
