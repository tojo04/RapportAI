# RapportAI V2 architecture

## Upgrade strategy

V2 is an additive upgrade of the working upload analyzer. The existing
`POST /api/analyze-call` workflow remains available while a live call path is
introduced in bounded stages. New provider, storage, and session boundaries
will be added where substitution or failure isolation is useful; working V1
files will not be reorganized only for appearance.

The browser captures one consented microphone stream. It does not claim to
capture a phone, Zoom, or Teams participant independently, and speaker role is
`unknown` unless a later verified input provides a mapping.

## Target data flow

```text
React live-call controls + AudioWorklet
    -> binary PCM + JSON commands over one WebSocket
FastAPI live-call endpoint
    -> per-call coordinator and bounded queues
streaming transcription adapter
    -> ordered partial/final transcript segments
final-segment pipeline
    -> structured sales-event detector
    -> pgvector retrieval over versioned synthetic knowledge
    -> grounded text coach with source citations
durable repository
    -> calls, final transcript, events, suggestions, analysis status
post-call adapter
    -> existing analyze_transcript
    -> existing calculate_call_score
React transcript/signals/coaching/history panels
```

## Responsibility mapping onto the current repository

Exact filenames are chosen within each task after inspecting current code. The
following locations are the intended ownership boundaries, not permission to
build future tasks early.

| V2 responsibility | Existing integration point | Planned ownership |
| --- | --- | --- |
| Protocol models | New backend models + `frontend/src/types/` | Pydantic command/event envelopes and matching TypeScript discriminated unions/runtime validation. |
| Live REST and WebSocket routes | `backend/app/main.py`, `backend/app/api/` | Add session creation and `/ws/calls/{call_id}` without changing the V1 router contract. |
| Active call state/coordinator | New focused backend module | Own lifecycle, queues, child tasks, ordering, stop/drain, and one outbound writer. |
| Browser socket lifecycle | New hook under `frontend/src/` | Create session, connect, reduce events, enforce states, and release resources. |
| Microphone PCM capture | New AudioWorklet and a small capture wrapper | Mono conversion, continuous resampling, PCM16LE encoding, bounded frames, and cleanup. |
| Streaming STT | New service beside `backend/app/services/` | Provider-specific connection/events behind a `StreamingTranscriber` boundary plus deterministic fake. |
| Sales-event detection | New model/service modules | Structured, evidence-validated events from finalized transcript windows only. |
| Knowledge ingestion/retrieval | New focused knowledge modules | Markdown chunking, embeddings, PostgreSQL/pgvector revisions, and exact cosine retrieval. |
| Grounded coaching | New service module | Validated suggestions citing only supplied transcript segments and retrieved chunks. |
| Durable history | New repository/storage modules | SQLAlchemy/Alembic calls, final segments, events, suggestions, and analysis records. |
| Temporary context | In-memory store first, Redis implementation later | TTL metadata, recent context, and deduplication; never active sockets/provider handles. |
| Live-call post-analysis | Adapter around existing V1 services | Freeze ordered final text, call `analyze_transcript`, then `calculate_call_score`. |
| Live/history UI | New presentation components composed by `frontend/src/App.tsx` | Transcript, signals, suggestions, lifecycle, history, and honest unavailable metrics. |

## V1 functions and contracts retained

- `backend.app.services.analysis.analyze_transcript` remains the structured
  post-call analysis entry point.
- `backend.app.models.analysis.CallAnalysis` remains the validated analysis
  payload.
- `backend.app.scoring.calculator.calculate_call_score` remains the only final
  score/category calculator.
- `backend.app.models.analysis.AnalyzeCallResponse` remains the upload response.
- `POST /api/analyze-call` and `GET /api/health` remain compatible.
- `frontend/src/services/api.ts` retains the upload call while gaining separate
  live/history operations only when their tasks require them.

The live pipeline reuses the final transcript; it does not reconstruct an audio
file and send it through V1 transcription again.

## Additive API surface

The protocol task will define these contracts precisely:

- `POST /api/calls` creates an idle live call and returns a backend-generated
  opaque call ID plus WebSocket path.
- `/ws/calls/{call_id}` accepts versioned JSON commands and, after transport is
  enabled, binary audio frames.
- `GET /api/calls` and `GET /api/calls/{call_id}` arrive with persistence.
- `POST /api/calls/{call_id}/analysis/retry` arrives with durable post-analysis.

The WebSocket server event envelope uses protocol version 1, unique event ID,
call ID, monotonically increasing per-call sequence, type, UTC emission time,
and a typed payload. Segment order is distinct from event sequence. Final
segments are durable; partials and transport acknowledgements are ephemeral.

## Lifecycle and concurrency baseline

Call lifecycle:

```text
idle -> connecting -> live -> stopping -> ended
                              \-> interrupted | failed
```

Post-call analysis has an independent
`pending -> running -> completed | failed` status.

- One process/worker owns active sockets, provider connections, and task
  handles in V2.
- Each call has isolated bounded queues and one outbound writer.
- Audio/provider IO cannot wait on event detection, retrieval, or coaching.
- Finalized transcript segments are never silently discarded.
- Stop and disconnect perform bounded drain/cleanup and preserve accepted
  final text.
- Live resume and blind audio replay are not supported.
- Redis later improves temporary context/deduplication but does not make a live
  connection transferable between workers.

## Audio and provider boundary

The verified 2026-09-30 OpenAI Realtime transcription guide uses a
transcription-only session, 24 kHz PCM input, `input_audio_buffer.append`, and
client-side `input_audio_buffer.commit` for turn finalization. It emits delta
and completed transcript events keyed by provider item ID. Current guidance
recommends `gpt-live-transcribe` and states that it does not support server or
semantic VAD.

This is a preliminary architecture input, not a frozen implementation payload.
Task 3 will recheck audio requirements, and Task 4 will inspect the installed
SDK and current provider documentation before implementing the adapter. Model
names and endpointing remain configurable.

## Storage rollout

1. Tasks 1-7 use in-memory active session state and fake AI boundaries.
2. Task 8 introduces PostgreSQL, pgvector, SQLAlchemy, Alembic, Docker Compose,
   and versioned synthetic knowledge only.
3. Task 11 makes call history durable and authoritative in PostgreSQL.
4. Task 13 adds Redis for bounded short-lived context with an in-memory
   degraded-mode fallback.

Authentication is deliberately absent from the local/private demo. History and
transcript APIs must not be represented as safe for public deployment without a
separate access-control task.

## Testing and evaluation boundaries

- CI/unit tests use fake STT, classification, coaching, and embedding clients.
- Paid API smoke tests are opt-in and never run implicitly.
- Audio transcription quality, transcript replay reasoning, retrieval quality,
  detector precision/recall, and latency are distinct evaluations.
- English, Hindi, and Hinglish use labeled synthetic fixtures; results are
  reported as observed, not inferred.
- Database and Redis integration tests use disposable local services and are
  marked separately.
- The V1 backend/frontend suites remain regression gates at integration
  milestones.

## Explicitly deferred

Telephony/meeting integrations, authentication/accounts, multi-tenancy, spoken
agent responses, CRM writes, Kafka/Redis Streams, distributed workers, Celery,
Kubernetes, fine-tuning, and automatic role attribution remain out of scope.

