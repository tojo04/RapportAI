# RapportAI — instructions for extending the existing Sales Call Analyzer

## 1. Mission and starting point

Extend the working upload-based React + FastAPI Sales Call Analyzer into a real-time, multilingual, text-only sales copilot. This is an incremental migration of an existing repository, not a new scaffold.

V1 already accepts a recording, transcribes it, validates an LLM analysis, and calculates a score in Python. Preserve that workflow, its API contract, its UI, and its tests. Reuse its transcript analysis and scoring for completed live calls. Inspect the actual code before deciding paths, commands, schemas, dependencies, or refactors: the supplied plan describes responsibilities, not guaranteed filenames.

The repository owner is a student preparing for interviews. Prefer small, understandable modules and explicit data flow. Add engineering depth through correct streaming, retrieval, lifecycle management, and evaluation rather than broad feature count.

Read BUILD_STEPS.md and perform only the requested task. If V1 differs from the assumed React/FastAPI implementation, record the differences and adapt the migration without regenerating the application.

## 2. Target scope

Required by the end of V2:

- Existing recording upload and post-call analysis still work.
- Browser microphone capture sends audio to FastAPI over a WebSocket.
- A server-side streaming STT adapter provides live partial and final transcripts.
- Final transcript windows trigger structured sales-event detection.
- Events include question, objection, pricing, competitor, buying signal, and requirement.
- Retrieval searches a versioned Markdown knowledge base using PostgreSQL + pgvector.
- A text-only copilot produces concise, source-linked suggestions, or acknowledges insufficient evidence.
- Completed and interrupted calls have persisted history, transcripts, events, suggestions, and analysis status.
- Redis supplies short-lived context, deduplication, and session metadata after an in-memory version works.
- The final transcript runs through V1 analysis and deterministic scoring.
- English, Hindi, and Hinglish have explicit evaluation examples and documented limitations.
- Latency, failure behavior, tests, local Docker Compose, and CI are documented.

The live audio source is the browser's microphone. This does not automatically capture the other participant in a phone, Zoom, or Teams call. Demonstrate with a consented conversation audible to that microphone or synthetic test audio. Do not advertise telephony integration.

Defer Kafka, Redis Streams, distributed worker systems, Kubernetes, CRM integrations, real telephone calls, autonomous spoken responses, fine-tuning, and multi-tenant account management. Authentication is not part of this local/private demo; do not publish transcript/history endpoints publicly without a separate access-control task.

## 3. Technology and dependency policy

| Responsibility | Choice |
| --- | --- |
| Frontend | Existing React + TypeScript + Vite setup |
| Styling | Existing styling; use Tailwind only if already present or needed by the UI task |
| Backend | Existing FastAPI application; asyncio for live orchestration |
| Client/backend transport | WebSocket, JSON control/events + binary PCM audio |
| Capture for the STT path | AudioWorklet with explicit mono conversion, resampling, and PCM encoding |
| STT | OpenAI transcription-only streaming session behind a small adapter |
| Classification and coaching | OpenAI structured outputs, validated with Pydantic |
| Embeddings | OpenAI embeddings; model and dimensions recorded with the corpus |
| Storage and vector search | PostgreSQL + pgvector |
| ORM/migrations | SQLAlchemy + Alembic, adapting existing conventions |
| Temporary session context | In-memory first, Redis later |
| Tests | Existing pytest; Vitest/React Testing Library for new frontend behavior |
| Local services | Docker Compose, introduced when PostgreSQL is needed |
| CI | GitHub Actions with fake AI providers |

Retain the existing package manager, lockfiles, Python environment tooling, and supported versions. Do not switch npm to pnpm or pip to another tool gratuitously. Pin compatible versions and record provider API documentation used. Do not add a general agent framework when ordinary async functions suffice.

Model names, input audio configuration, SDK methods, and provider limits must be checked against current official documentation during implementation. Keep models configurable. Do not guess SDK fields, reuse obsolete session payloads, or assume every transcription model has the same VAD/diarization behavior. Check the installed OpenAI SDK before writing the adapter.

## 4. Responsibilities and migration boundaries

Keep the existing directory structure. Typical new responsibilities are:

| Component | Owns | Must delegate |
| --- | --- | --- |
| React live-call hook | Capture, local status, socket lifecycle, reducing events | AI calls and authoritative history |
| React panels | Transcript, signals, suggestions, history, metrics | Provider connections |
| FastAPI call routes | Validation, session creation, history access | Domain orchestration |
| WebSocket handler | Control/binary framing, limits, lifecycle entry points | Classification and RAG |
| Call coordinator | Session lifecycle, bounded queues, child tasks, stop/drain | STT/provider-specific parsing |
| STT adapter | Provider audio protocol and transcript normalization | Sales reasoning |
| Event detector | Structured, evidence-backed events from final transcript windows | Final score |
| Knowledge ingestion | Markdown chunks, hashes, embeddings, corpus revisions | Live audio |
| Retriever | Similarity search and source metadata | Product claims |
| Coach | Grounded response suggestions with validated citations | Tool execution or speaking into calls |
| Session store | Recent context, deduplication, metadata with TTL | Owning active sockets/tasks |
| Call repository | Durable records and idempotent writes | Redis as the sole transcript record |
| Post-call adapter | Invoke existing V1 analysis/scoring on finalized text | Retranscribing already-transcribed live audio |

Put interfaces at real substitution points: STT provider, session store, repository, and AI service clients. Do not create an abstract class for every function. Do not move working V1 files merely to make a directory tree look uniform.

## 5. Protocol contract

Define the protocol before implementing the live UI. Document it in docs/realtime-protocol.md and validate it on both ends. The backend assigns call IDs. Treat IDs as opaque.

Suggested additive REST routes, adjusted for the existing API prefix:

- POST /api/calls: create an idle live session; return call_id and the WebSocket path.
- GET /api/calls: paginated call history after persistence exists.
- GET /api/calls/{call_id}: snapshot, status, and latest analysis state.
- POST /api/calls/{call_id}/analysis/retry: explicit retry of failed post-call analysis after that task is implemented.
- GET /api/health: retain the existing route if one exists.

Live endpoint: /ws/calls/{call_id}. Verify call existence, allowed state, and configured browser Origin independently of REST CORS. Restrict local/private use; a UUID is not authentication.

Use this common JSON envelope for server events:

```json
{
  "protocol_version": 1,
  "event_id": "opaque-unique-id",
  "call_id": "opaque-call-id",
  "seq": 12,
  "type": "transcript.final",
  "emitted_at": "2026-09-30T08:00:00Z",
  "payload": {
    "segment_id": "stable-segment-id",
    "order": 3,
    "revision": 1,
    "text": "Your pricing is higher than expected.",
    "speaker_id": null,
    "speaker_role": "unknown",
    "start_ms": null,
    "end_ms": null,
    "language": null
  }
}
```

- seq is assigned by one per-call writer and increases for outgoing events; persisted history may contain gaps because partial transcripts and transport acknowledgements are ephemeral.
- event_id identifies an emitted event; segment_id identifies a transcript segment across partial/final updates. Deduplicate durable segment writes by call_id + segment_id.
- order is the normalized audio-turn order, not provider completion arrival order. Preserve provider item/previous-item identifiers internally when needed. Final completions can arrive out of order.
- Partial updates replace the displayed partial for their segment. Final updates replace that partial and enter durable context once. Do not append every delta as a new utterance.
- Nullable timestamps/language/speaker fields mean unavailable. Do not substitute guessed values. UTC emitted_at is not an audio timestamp.
- Clients validate unknown versions and malformed payloads. Unrecognized optional event types may be ignored with a diagnostic; incompatible versions fail visibly.

Required types: session.ready, call.started, audio.ack (transport demo only), transcript.partial, transcript.final, sales.event, coach.suggestion, call.stopping, call.ended, analysis.started, analysis.completed, analysis.failed, warning, error. Put the sales category inside the sales.event payload rather than multiplying inconsistent event shapes.

Client JSON commands include start, stop, and ping with command_id and protocol_version. Define typed payloads, allowed states, and idempotency. Binary frames are audio only after start has been accepted. Do not wrap every audio chunk in a JSON object or log its bytes.

## 6. Audio contract and browser lifecycle

- Initial transport tests may use MediaRecorder solely to prove binary transfer. WebM/Opus blobs are not raw PCM, and individual blobs are not necessarily standalone decodable audio files. Remove that shortcut from the production streaming path.
- For the OpenAI PCM path, the design baseline is signed 16-bit little-endian mono at 24 kHz. Verify the selected session's current requirements before implementation and update the documented contract if necessary.
- Read the actual AudioContext sample rate. A getUserMedia constraint does not guarantee 24 kHz capture. Resample continuously with state across blocks, avoid per-block resets/drift, clip floats safely, and test known samples and output duration.
- Target roughly 100 ms binary frames; keep frame duration and size bounded and configurable. At the baseline format, 100 ms is 4,800 bytes. Reject invalid lengths, excessive frames, audio before start, and calls exceeding the configured duration.
- Never replay buffered audio blindly after reconnection; it can duplicate transcription. The V2 baseline ends a disconnected live stream as interrupted and allows reviewing its saved snapshot, then starting a new call. Seamless live resume is deferred.
- Gate UI on actual connection/session states, not just a recording boolean. Start failure, permission denial, network loss, tab unmount, repeated stop, and React StrictMode must release tracks, worklets, nodes, AudioContext, listeners, timers, and sockets.
- Check WebSocket.bufferedAmount against a documented threshold. If congested, terminate/interruption with an explicit error rather than accumulate unbounded audio or silently corrupt the transcript.
- Use localhost or HTTPS for microphone access. Pair HTTPS with WSS outside localhost. Secrets belong only in server environment variables, never VITE_* variables.

## 7. Session lifecycle, concurrency, and failures

States: idle → connecting → live → stopping → ended. Abnormal shutdown yields interrupted or failed. Post-call analysis has its own pending/running/completed/failed state; a call ending does not mean its analysis has completed.

Start with one backend worker and one process holding active providers and task handles. Redis does not make a live provider connection transferable between workers. State this limitation explicitly; multiple concurrent calls in that worker must remain isolated.

Use separate bounded paths for audio/provider IO and semantic work. Slow classification/coaching must not block audio receive or transcript delivery. Use one outbound writer per socket. Serialize order-sensitive per-call state updates. Await/cancel all child tasks during cleanup; do not leave orphan tasks or unhandled exceptions.

On overload, coalesce pending semantic windows and replace obsolete partial updates. Never silently discard finalized transcript segments. If a critical queue cannot accept a final segment within a bounded time, persist what is available and end the call with an explicit failure. Default limits must cover audio queues, final segments, transcript length, active calls, context size, model requests, and total call duration.

Normal stop:

1. Stop browser capture and transmit the final audio frame before the stop command.
2. Server enters stopping once; reject new start/audio commands.
3. Finish queued audio and commit/flush the last nonempty provider turn according to the selected API. Track already-committed turns to avoid duplicate or empty commits.
4. Wait for pending final transcripts with a bounded timeout. Drain accepted finals into ordered durable state.
5. Cancel superseded coaching/detection requests and close provider resources.
6. Mark ended if fully finalized, or interrupted with an incomplete-transcript warning.
7. Schedule post-call analysis from the frozen ordered final transcript; do not use partials.

Handle disconnect with the same bounded cleanup and best-effort finalization. Persist interrupted status and retained final text. A browser disconnect does not erase the call. Choose and test timeout values; do not leave stop waiting forever.

Retries are bounded and stage-specific. Retrying an LLM request after a timeout may repeat billable work. Do not reconnect STT and replay audio automatically. Optional live coaching failures show a warning and preserve transcription; STT failure ends the live path. Sanitize error messages and log identifiers rather than transcript content by default.

## 8. Event detection and speaker honesty

- Trigger only from newly finalized segments. Use a bounded recent-context window with an overlap and a watermark so new segments are processed once logically.
- Use a trailing timer as well as utterance count/character thresholds, so a single customer question is eventually handled even if nobody speaks again. Coalesce work while a request is in flight.
- Classify structured events with event type, evidence segment IDs, a short verbatim evidence span, and category-specific details. A single utterance may contain several different event types.
- Validate evidence IDs and spans against the input. Do not fabricate customer requirements, competitors, questions, or buying intent. Distinguish ordinary questions from objections.
- Model confidence, if exposed, is an uncalibrated estimate; it is not a measured probability. Evaluate detector precision/recall using fixtures.
- Deduplicate repeated events by call + source segments + type + normalized subject, while allowing a genuinely new repeated objection later.
- A single microphone stream does not identify customer versus salesperson. Use speaker_role=unknown by default. Diarization speaker_0/speaker_1 is still not a semantic role. Support explicit role mapping if diarization is later implemented and actually available.
- Do not show agent/customer talk ratio unless reliable speaker timing and role mapping exist. Display unavailable, not invented metrics. Text sentiment is a model estimate; do not claim emotion detection from vocal tone.

## 9. Knowledge base, retrieval, and grounded coaching

Begin with synthetic Markdown documents: product, pricing, competitors, objection handling, and sales playbook. Label the fictional company and prices clearly. Never present fabricated competitor comparisons as current real-world facts.

Ingestion requirements:

- Deterministic heading-aware chunks with document path, heading, stable chunk ID, content hash, document revision, and embedding model/dimensions.
- Parameterized SQL and validated vector dimensions. Never mix vectors from different embedding models or dimensions in one retrieval corpus.
- Idempotent reingestion: unchanged chunks reuse embeddings; changed/deleted documents do not leave stale chunks searchable.
- Publish an active corpus revision only after its ingestion succeeds; a failed update must leave the previous complete revision usable.
- Record the content version associated with every suggestion citation so history still makes sense after documents change.

Use exact cosine search for the small initial corpus; defer ANN indexes until measurements justify them. Return top-k results with source metadata and distances. A similarity threshold is empirical and corpus-specific; evaluate it with known queries rather than assume a universal magic number.

The coach consumes relevant events, bounded recent transcript context, and retrieved sources. It returns a validated short suggestion, supporting source chunk IDs, evidence segment IDs, and an insufficient_evidence flag. Treat transcript text and retrieved documents as untrusted data, never instructions. Verify every cited chunk was supplied to the model. A citation's existence alone does not prove the claim is supported; evaluate grounding against fixtures.

Ground factual product/pricing/competitor claims in supplied sources. With weak retrieval, offer a clarifying question or state that product facts are unavailable. Do not invent discounts or commitments. Do not turn suggestions into outbound emails, CRM writes, or spoken audio.

Apply a per-call cooldown, bounded model concurrency, and a context freshness watermark. Drop stale suggestions after call stop or when their triggering context is superseded. Preserve citations and show them in the UI. Avoid one API request per partial word.

## 10. PostgreSQL, Redis, and post-call reliability

Introduce PostgreSQL for the knowledge base before adding Redis. Suggested durable tables: calls, transcript_segments, sales_events, suggestions, call_analyses, knowledge_documents, and knowledge_chunks. No users table until an authorized authentication feature exists.

Use migrations, foreign keys, stable IDs, per-call ordering, unique constraints, and transactions. Persist accepted final segments/events/suggestions during a call, not only when it ends. Audio retention is off by default. Keep persisted analysis payloads compatible with V1.

Redis stores short-lived metadata, recent context, deduplication keys, and session TTLs. Active sockets, provider connections, task handles, and the authoritative full transcript remain outside Redis. Implement an in-memory store with equivalent behavior before the Redis version. Refresh TTL while active; use atomic conditional writes where concurrent tasks share deduplication state.

If Redis fails, use a documented bounded in-memory fallback for the current single-worker demo and emit a degraded-mode warning. If PostgreSQL writes fail, do not claim a call was saved: surface the storage failure and mark it explicitly. History reconstruction reads PostgreSQL.

For post-call analysis, reuse V1's validated CallAnalysis and scoring function. Preserve V1 weights/categories unless a scoring change is separately requested. Explain that Python scoring is deterministic given inputs, while LLM rubric ratings can vary. Incomplete or too-short transcripts must be labeled and may skip scoring if unsupported by V1's validation.

Use a durable analysis status with an atomic claim and one logical result per call + analysis version. A single-process supervised task plus a retry endpoint is sufficient; Kafka/Celery is unnecessary. Recover abandoned running jobs as retryable after a documented timeout. Do not claim exactly-once external API execution: database uniqueness prevents duplicate stored results, not duplicate billed API requests. Limit retries and record failures without hiding them.

## 11. Testing and evaluation

Retain V1 tests and add meaningful tests at behavior boundaries:

- Protocol validation, unknown call, illegal state, malformed frames, duplicate commands.
- PCM clipping/encoding, resampling duration and continuity, fake microphone cleanup.
- Partial/final replacement, duplicate/out-of-order provider completions, final stop flush.
- Slow coach while transcription continues, bounded queues, socket disconnect, cancellation.
- Isolation between concurrent calls and React rerun/unmount behavior.
- Event evidence validation, deduplication, quiet trailing-window processing.
- Chunk determinism, reingestion/deletion, corpus failure, dimensions mismatch.
- Retrieval expected source and no-match cases using deterministic test embeddings.
- Citation validation, weak evidence abstention, injection attempts, stale suggestions.
- PostgreSQL constraints, interrupted-call history, analysis claim/retry; Redis TTL/failure.
- V1 upload regression and live transcript reuse of V1 scoring.

Unit tests/CI must use fake providers and must never make paid API calls or use real customer recordings. Mark PostgreSQL/Redis integration tests and run against disposable test services. Keep opt-in paid smoke tests separate and document expected usage; do not run them without an explicit user request.

Create labeled synthetic English/Hindi/Hinglish fixtures. Offline transcript replay tests reasoning without claiming STT quality; end-to-end audio smoke tests assess transcription separately. Report observed results and failures; never invent benchmark scores.

## 12. Observability and configuration

Use monotonic timers for durations, UTC for records, and IDs for trace correlation. Track audio receipt → final transcript when accurately attributable, detector time, retrieval time, coach time, and final-received → suggestion-delivered time. Physical speech-end latency requires a known audio/VAD boundary; do not infer it from an unrelated server clock.

Track p50/p95 over enough samples, counts, errors, dropped obsolete windows, and unavailable stages. Measurements from fake providers are not production latency. Log no raw audio, full transcript, credentials, or WebSocket URLs containing secrets by default.

Extend .env.example with placeholders as tasks need them: OPENAI_API_KEY, LIVE_STT_MODEL, EVENT_MODEL, COACH_MODEL, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, DATABASE_URL, REDIS_URL, ALLOWED_ORIGINS, and bounded timeout/queue/call-duration settings. Retain existing V1 variables. Frontend variables contain only public backend URLs/configuration.

## 13. Codex working process

For each bounded task:

1. Inspect Git status, existing instructions, relevant files, dependencies, and tests.
2. Give a brief change description tied to the existing code.
3. Implement the requested stage and necessary tests/documentation only.
4. Run relevant tests and frontend typecheck/build if frontend changed. Run the existing V1 suite at integration milestones.
5. Report changed files, commands and actual outcomes, known limitations, and a short explanation of the data flow.
6. Update docs/BUILD_PROGRESS.md with status, decisions, verification, and the next task. Record only true outcomes.
7. Stop after the requested task. Do not implement future stages, remove failing tests, or refactor unrelated code.

Within the requested task, proceed with ordinary reversible edits and local verification without repeated confirmations. Report concrete blockers rather than pretend a credentialed or unavailable test passed. Keep secrets out of Git. Do not overwrite user edits, perform destructive Git commands, publish, or run paid API tests unless requested. Suggest a commit; create one only when the task requests it.

If a root AGENTS.md already exists, this V2 guide supersedes only V1 scope restrictions that conflict with the authorized streaming/database/Redis features. Preserve unrelated repository rules. Inspect nested AGENTS.md files and reconcile stale V1 constraints narrowly; do not silently ignore them or replace every instruction file.

## 14. Definition of done

V2 is complete when a consented/synthetic live conversation yields an ordered transcript, evidence-backed sales events, grounded source-linked coaching, and a saved post-call result using V1 scoring; microphone/provider resources are released, failures are visible, English/Hindi/Hinglish limitations and observed latency are documented, CI passes without secrets, and the original upload workflow still works.

## Official references to verify during implementation

- Codex repository instructions: https://developers.openai.com/codex/guides/agents-md
- Realtime transcription: https://developers.openai.com/api/docs/guides/realtime-transcription
- Structured outputs: https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI Python SDK: https://github.com/openai/openai-python
- pgvector: https://github.com/pgvector/pgvector

These links are starting points, not a frozen provider payload. Check the installed SDK and current relevant documentation at the STT/LLM tasks.
