# RapportAI

RapportAI is an interview-sized AI sales-call analyzer with two preserved workflows:

- upload an MP3/WAV, transcribe it, extract a validated analysis, and calculate an explainable score;
- stream a browser microphone in realtime, detect evidence-backed sales signals, retrieve a fictional versioned playbook, show grounded text coaching, save the finalized call, and run the same V1 analysis after stop.

All company facts and prices in `backend/knowledge` are fictional. The browser never receives an OpenAI key and raw live audio is never persisted.

## Architecture

```text
React (upload + live dashboard + history)
   ├─ POST /api/analyze-call ── temporary audio ── transcription ─┐
   └─ WS /ws/calls/{id} ── PCM16 24 kHz ── streaming STT         │
                                  └─ final transcript             │
                                      ├─ signal detection         │
                                      ├─ pgvector retrieval       │
                                      └─ grounded coaching        │
PostgreSQL ← finals/events/suggestions/analysis                   │
Redis ← bounded active context (optional/fallback)                │
                         V1 structured analysis + Python scoring ←┘
```

The release deliberately uses one backend worker. PostgreSQL is durable; Redis is only ephemeral context. UUIDs are identifiers, not authorization, so the history APIs are for local use and must not be exposed publicly.

## Prerequisites

- Python 3.11+
- Node.js 20.19+ or 22.12+ and npm
- Docker Desktop using Linux containers (for PostgreSQL/pgvector and Redis)
- an OpenAI API key for real transcription/analysis/coaching; all default tests use fakes

## Run locally on Windows PowerShell

From the repository root, start infrastructure (make sure Docker Desktop is running):

```powershell
docker compose up -d postgres redis
```

Set up and migrate the backend:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m scripts.ingest_knowledge --fake
```

Edit `backend/.env`. For durable history and Redis locally set:

```env
OPENAI_API_KEY=your-key
OPENAI_TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe
OPENAI_ANALYSIS_MODEL=gpt-4o-mini
LIVE_STT_MODEL=gpt-live-transcribe
LIVE_CLASSIFICATION_MODEL=gpt-4o-mini
LIVE_COACH_MODEL=gpt-4o-mini
PERSISTENCE_ENABLED=true
REDIS_ENABLED=true
```

The Compose PostgreSQL host port defaults to `55432` to avoid colliding with a
locally installed PostgreSQL on `5432`. If an older private `.env` points to a
different port, update its `DATABASE_URL` to match `.env.example`.

Model names are examples; use models available to your OpenAI project. Then start exactly one backend worker:

```powershell
uvicorn app.main:app --reload --workers 1
```

In a second terminal:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:5173`. Browser microphone capture works on localhost; non-local deployment requires HTTPS. The API/Swagger/health endpoints are `http://localhost:8000`, `/docs`, and `/api/health`.

## Run the packaged stack

Put non-secret model names and your key in the shell environment, then:

```powershell
docker compose up --build -d
docker compose exec backend python -m scripts.ingest_knowledge --fake
```

Open `http://localhost:8080`. Compose runs migrations before the one-worker backend. It uses a persistent PostgreSQL volume; never run `docker compose down -v` unless you intentionally want to erase it. The nginx configuration proxies both HTTP and WebSocket Upgrade/Origin headers.

## Offline demo and developer tools

These do not use a microphone or paid API:

```powershell
cd backend
python -m scripts.replay_transcript fixtures/replay/demo.json
python -m scripts.query_knowledge --fake "What does the Growth plan cost?"
python -m scripts.benchmark_replay --samples 100
```

Fake embeddings are deterministic but non-semantic. Real ingestion/retrieval and multilingual reasoning require explicit `--real` and may be billable:

```powershell
python -m scripts.ingest_knowledge --real
python -m scripts.query_knowledge --real "How long is implementation?"
python -m scripts.evaluate_multilingual --real
```

## Verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m alembic upgrade head --sql

cd ..\frontend
npm test -- --run
npm run lint
npm run typecheck
npm run format:check
npm run build

cd ..
docker compose config
```

CI additionally starts disposable pgvector and Redis services, migrates an empty database, ingests fake knowledge, and runs both suites. No default test contacts OpenAI.

## Scoring

The model supplies bounded 0–5 discovery, objection-handling, and clarity ratings. Python—not the model—maps these to 25, 25, and 20 points, then adds 20 for a confirmed next step and 10 for at least one follow-up. Categories are Excellent (85–100), Good (70–84), Needs Improvement (50–69), and Poor (0–49). Python `round` uses ties-to-even; current weights map valid ratings to integers exactly.

## Failure behavior and limitations

- A saturated or failed optional detector/coach emits a warning while finalized transcript delivery continues.
- Stop drains accepted audio and waits a bounded time; incomplete finalization is retained and labeled.
- A Redis outage degrades to bounded process memory; it never replaces PostgreSQL history.
- Failed post-call analysis remains saved and retryable. Retries may repeat a billable request; exactly-once external execution is not claimed.
- A citation is inspectable source support, not a correctness guarantee. The retrieval threshold requires empirical tuning.
- One mixed microphone cannot identify speakers; the UI says `Unknown speaker`. No diarization, role guessing, talk ratio, or emotion meter exists.
- Real browser/provider behavior, semantic retrieval quality, multilingual audio accuracy, and controlled real load are not claimed until their opt-in checks are run.
- No authentication, public deployment, CRM actions, billing, background-worker platform, or horizontal scaling is included.

See [demo script](docs/DEMO_SCRIPT.md), [interview notes](docs/INTERVIEW_NOTES.md), [protocol](docs/realtime-protocol.md), [knowledge](docs/KNOWLEDGE.md), [coaching](docs/COACHING.md), and [latency](docs/LATENCY.md).
