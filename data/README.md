# Data directory

**Drop your documents here**, then run ingestion to make them searchable.

Supported file types:

- `.txt`
- `.md` / `.markdown`
- `.pdf`
- `.docx`

Subdirectories are scanned recursively. The path relative to this folder is used
as each document's `source` identifier (so re-ingesting a file updates it in
place rather than duplicating it).

## Ingest

```bash
# Local
python -m scripts.ingest

# Or via the API once the server is running
curl -X POST http://localhost:8000/v1/ingest
```

> This file is kept in git as a placeholder; your actual documents are ignored
> via `.gitignore`.
