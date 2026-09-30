# RapportAI V1 baseline

## Snapshot

- Baseline commit: `db893a3` (`update project name to RapportAI`)
- Baseline tag: `v1.0-upload-analyzer`
- V2 development branch: `realtime-v2`
- Audit date: 2026-09-30
- Working V1 source was clean before the supplied V2 instruction files were
  added.

RapportAI V1 is a React upload dashboard backed by a FastAPI API. It accepts a
single MP3 or WAV recording, transcribes it, requests a validated structured
analysis, calculates a deterministic score, and returns one result. It has no
database, live socket, call history, or background worker.

## Actual V1 paths and responsibilities

| Responsibility | Actual path | Notes |
| --- | --- | --- |
| FastAPI construction, CORS, health | `backend/app/main.py` | Registers the API router and `GET /api/health`. |
| Upload endpoint and orchestration | `backend/app/api/routes.py` | Validates/stores the upload, calls both services off the event loop, scores, and deletes the temporary file in `finally`. |
| Environment settings | `backend/app/core/config.py` | Cached dataclass populated from environment variables. API key is excluded from its representation. |
| File transcription | `backend/app/services/transcription.py` | Calls `client.audio.transcriptions.create` and returns non-empty text. |
| Structured transcript analysis | `backend/app/services/analysis.py` | Calls `client.responses.parse` with `CallAnalysis` as `text_format`. |
| Pydantic contract | `backend/app/models/analysis.py` | Defines analysis, score, and complete response models with forbidden extra fields. |
| Deterministic scoring | `backend/app/scoring/calculator.py` | Pure Python; makes no provider calls. |
| React request state/layout | `frontend/src/App.tsx` | Owns selected file, loading, error, and result state. |
| Upload interaction | `frontend/src/components/AudioUploader.tsx` | Browser-side MP3/WAV selection and validation. |
| Result rendering | `frontend/src/components/AnalysisResults.tsx` | Summary, lists, objections, sentiment, and transcript. |
| Score rendering | `frontend/src/components/ScoreCard.tsx`, `frontend/src/components/ScoreBreakdown.tsx` | Displays total/category and component values. |
| Typed HTTP client | `frontend/src/services/api.ts` | Sends multipart data and validates the response at runtime. |
| TypeScript contract | `frontend/src/types/analysis.ts` | Mirrors the backend response types. |

## V1 API contracts

### Health

`GET /api/health` returns HTTP 200 with:

```json
{"status": "ok"}
```

### Analyze an uploaded call

`POST /api/analyze-call` accepts `multipart/form-data` with one field named
`file`.

- Accepted filename extensions: `.mp3`, `.wav`
- Accepted content types are checked against the extension where practical.
- Empty files return HTTP 400.
- Files larger than `MAX_UPLOAD_MB` return HTTP 413.
- Provider/service failures return HTTP 502.
- Errors use `{"detail": "Human-readable message"}`.
- The original filename is not used for the temporary path.
- The temporary file and upload handle are cleaned up after every outcome.

The success response is `AnalyzeCallResponse`:

```text
transcript: non-empty string
analysis: CallAnalysis
score: ScoreResult
```

The V2 implementation must leave this endpoint and response shape compatible.

## CallAnalysis and score schemas

`CallAnalysis` contains:

| Field | Constraint |
| --- | --- |
| `summary` | Non-empty string |
| `customer_needs` | List of strings |
| `questions_asked` | List of strings |
| `objections` | List of `{ objection: non-empty string, response: string | null }` |
| `follow_up_actions` | List of strings |
| `sentiment` | `positive`, `neutral`, `mixed`, or `negative` |
| `next_step_confirmed` | Strict boolean |
| `objection_handling_quality` | Strict integer from 0 through 5 |
| `discovery_quality` | Strict integer from 0 through 5 |
| `communication_clarity` | Strict integer from 0 through 5 |

All response models reject unknown fields. `ScoreResult` also validates that the
component sum equals `total` and that `category` agrees with `total`.

## Deterministic scoring contract

| Component | Formula | Maximum |
| --- | --- | ---: |
| Discovery | `discovery_quality / 5 * 25` | 25 |
| Objection handling | `objection_handling_quality / 5 * 25` | 25 |
| Communication clarity | `communication_clarity / 5 * 20` | 20 |
| Confirmed next step | 20 when true, otherwise 0 | 20 |
| Follow-up actions | 10 when the list is non-empty, otherwise 0 | 10 |

The quality calculations use Python `round` (ties to even). The current maxima
are divisible by five, so every valid rating maps to an exact integer.

Categories remain:

- 85-100: Excellent
- 70-84: Good
- 50-69: Needs Improvement
- 0-49: Poor

V2 post-call analysis will reuse `analyze_transcript` and
`calculate_call_score`; the live path must not let a language model set the
final total or category.

## Existing configuration

Backend (`backend/.env.example`):

```env
OPENAI_API_KEY=
OPENAI_TRANSCRIPTION_MODEL=
OPENAI_ANALYSIS_MODEL=
MAX_UPLOAD_MB=20
FRONTEND_ORIGIN=http://localhost:5173
```

Frontend (`frontend/.env.example`):

```env
VITE_API_BASE_URL=http://localhost:8000
```

No `.env` value was read or printed during this audit.

## Dependency and tool baseline

- Backend uses `requirements.txt` with compatible version ranges; there is no
  Python lockfile.
- The audit environment used Python 3.14.3, FastAPI 0.141.1, OpenAI Python SDK
  2.52.0, Pydantic 2.13.4, Pytest 9.1.1, and Uvicorn 0.52.1.
- Frontend uses npm with a committed `package-lock.json`.
- The audit environment used Node 22.20.0 and npm 10.9.3.
- Git version was 2.51.0.windows.2.

## Run and verification commands

Backend setup/start from the repository root:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend tests:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

Frontend setup/start:

```powershell
cd frontend
npm ci
npm run dev
```

Frontend checks:

```powershell
cd frontend
npm test -- --run
npm run lint
npm run typecheck
npm run format:check
npm run build
```

## Recorded baseline results

- Backend: 75 tests passed in 3.07 seconds.
- Frontend: 22 tests across 4 files passed.
- ESLint: passed.
- TypeScript typecheck: passed.
- Prettier check: passed.
- Vite production build: passed.
- No paid provider call was made.

Observed baseline warnings/findings:

- FastAPI's test client emitted one deprecation warning about its current
  `httpx` integration.
- Frontend dependencies were absent initially; `npm ci` restored the committed
  lockfile dependencies without changing the manifest.
- `npm ci` reported five dependency audit findings (two moderate, three high).
  They are recorded for later dependency review; no automatic or breaking
  upgrade was applied during Task 0.

