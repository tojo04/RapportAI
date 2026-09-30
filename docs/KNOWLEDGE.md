# Versioned demo knowledge

RapportAI stores a synthetic Markdown corpus in PostgreSQL with pgvector. Every fact and price in `backend/knowledge` is fictional.

## Local setup

Docker Desktop (Linux containers) or Docker Engine through WSL is required; PostgreSQL does not need to be installed on Windows.

```powershell
docker compose up -d postgres
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\ingest_knowledge.py --fake
```

`--fake` produces stable non-semantic vectors for development and tests. It does not measure retrieval quality. `--real` is an explicit, billable opt-in and requires `OPENAI_API_KEY`; it uses the configured model and dimensions.

Each corpus records its model and dimensions, document/content revisions, and stable heading-aware chunk IDs. Publication occurs in one database transaction. Unchanged chunks can reuse compatible embeddings; deleted chunks disappear because queries only use the active revision. A model or dimension change creates a separate corpus revision.

Never run `docker compose down -v` unless you intentionally want to erase the local database.
