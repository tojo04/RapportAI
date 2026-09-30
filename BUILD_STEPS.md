# RapportAI V2 — build over the existing Sales Call Analyzer with Codex

## How to use these files

You already have V1: React + FastAPI, recording upload, transcription, validated analysis, and Python scoring. This guide extends that repository. It does not ask Codex to build a second application or replace the upload flow.

The source repository was not supplied with this guide. Paths, endpoint names, installed versions, and commands must be resolved from your repository in Task 0. Example paths below describe responsibilities; keep existing names where practical.

Use AGENTS.md for permanent rules and this file for one task at a time. A task can take more than one Codex turn. Complete its acceptance checks before moving on. Do not paste the whole guide and request all stages in one run.

### First: checkpoint V1 and install the V2 instructions

In the existing repository, inspect the changes before saving a baseline:

```bash
git status --short
git diff --stat
git diff
```

Stage the intended project files explicitly, inspect the staged diff, and commit the working V1 if it is not already committed. Do not stage .env, private recordings, credentials, or generated environments. Use your actual filenames; do not paste placeholder paths literally.

```bash
git diff --cached
git commit -m "release: preserve working upload analyzer"
git tag v1.0-upload-analyzer
git switch -c realtime-v2
```

Skip the commit if the working tree is already clean and V1 is committed. Reuse an existing baseline tag/branch if present; do not overwrite tags. If V1 is not working, document its existing failures before proceeding.

To preserve existing instructions, initially save the supplied AGENTS.md as AGENTS_V2.md and this guide as BUILD_STEPS_V2.md in the repository root. Keep any existing AGENTS.md/BUILD_STEPS.md available while Codex reconciles them in Task 0. Afterwards, the active root instructions should be AGENTS.md and the active guide BUILD_STEPS.md. Archive old guides under docs/v1/ if useful, without putting V1 restrictions in an active nested AGENTS.md.

Start Codex in that repository and use the Task 0 prompt. This avoids blindly replacing repository-specific rules.

### Loop after each task

1. Give Codex the single task prompt.
2. Inspect the diff and actual validation results.
3. Run the described manual check if it needs a browser or real service.
4. Ask for an explanation of unfamiliar code.
5. Commit the intended changes using the suggested message.
6. Continue with the next task.

The prompts authorize relevant reversible implementation, tests, and local checks. Credentials are kept out of prompts. Paid API smoke tests are opt-in; mocked tests do not require them. Codex should report a missing key as an unperformed real check, while finishing the fake-provider implementation and tests.

### Intended build sequence

| Stage | Outcome | Main dependency |
| --- | --- | --- |
| 0 | Existing-code audit and V1 baseline | Current repository |
| 1 | Typed protocol and live-call lifecycle | Audit |
| 2 | React microphone → FastAPI transport | Protocol |
| 3 | Correct PCM capture and bounded transport | Transport |
| 4 | Streaming STT adapter | PCM contract |
| 5 | Reliable live transcript and stop/drain | STT adapter |
| 6 | Offline transcript replay | Transcript protocol |
| 7 | Live sales-event detection | Finalized transcript windows |
| 8 | PostgreSQL + pgvector knowledge ingestion | Synthetic documents |
| 9 | Tested vector retrieval | Ingested corpus |
| 10 | Grounded live coaching | Events + retrieval |
| 11 | Durable call history | Proven live pipeline + PostgreSQL |
| 12 | Live-call post-analysis using V1 | Final transcripts + history |
| 13 | Redis session context | Working in-memory session store |
| 14 | Complete dashboard | Stable live/history contracts |
| 15 | Hindi/Hinglish evaluation; speaker limitations | Working English flow |
| 16 | Measured latency and controlled load | Full pipeline |
| 17 | Docker, CI, final review and demo | All core behavior |

Test harnesses and metrics hooks can be introduced earlier as needed. The table is a feature order, not an instruction to delay tests or cleanup until the end.

---

## Task 0 — Audit V1 and reconcile the instruction files

Paste into Codex:

```text
This is an existing working Sales Call Analyzer. Extend it; do not scaffold a replacement.

Read all existing applicable AGENTS.md files, AGENTS_V2.md, and BUILD_STEPS_V2.md. Inspect Git status, frontend/backend entry points, routes, schema models, services, scoring, tests, dependency manifests, environment examples, and existing docs. Do not print secrets or read private recordings.

Perform Task 0 only:
- Merge the supplied V2 rules into root AGENTS.md. Preserve unrelated repository rules; replace only V1 scope restrictions superseded by this authorized upgrade.
- Adopt the V2 task guide as BUILD_STEPS.md while preserving the old guide under docs/v1/ if useful.
- Create docs/V1_BASELINE.md mapping actual V1 paths, API contracts, CallAnalysis schema, score weights/categories, dependency tools, and run/test commands.
- Create docs/V2_ARCHITECTURE.md mapping new responsibilities onto the existing layout. Identify which V1 analysis/scoring functions will be reused.
- Create docs/BUILD_PROGRESS.md with the task checklist, decisions, baseline results, and next task.
- Reconcile conflicting nested instructions narrowly and explain each change.
- Run existing non-paid checks. Record pre-existing failures separately.

Do not change application source code or install a new stack. Report actual findings, missing assumptions, and the commands we will use for future tasks. Stop after Task 0.
```

Pass criteria: You know which code produces V1's transcript, analysis, and score; the active instructions agree with V2; baseline failures are documented. No upload contract changed.

Suggested commit: `docs: map v1 and define incremental realtime upgrade`

## Task 1 — Define the protocol and session state machine

```text
Read AGENTS.md, BUILD_STEPS.md Task 1, and docs/V1_BASELINE.md. Implement Task 1 only in the existing layout.

Define typed Pydantic server/client events, matching TypeScript discriminated unions with runtime validation, and docs/realtime-protocol.md. Use the envelope and fields from AGENTS.md. Keep segment IDs stable across partial/final updates and separate segment order from server event sequence.

Add session creation and /ws/calls/{call_id} with an in-memory store. Implement ready/start/stop/ping and states idle, connecting, live, stopping, ended, interrupted, failed. Return a backend-generated call ID. Add one per-call outbound writer. Do not connect an AI provider yet; reject binary audio until Task 2.

Validate Origin, missing sessions, invalid versions, malformed payloads, illegal states, duplicate start/stop commands, and disconnect cleanup. Use bounded queues and configurable limits. Document the single-worker baseline and no live resume policy.

Add meaningful protocol/state tests, run them plus V1 checks relevant to route changes, and update BUILD_PROGRESS.md. Report commands and outcomes. Stop here.
```

Pass criteria: A fake client can create/start/stop a session; invalid input is rejected; duplicate stop is harmless; no orphan session tasks remain. A call ID is not represented as authentication.

Suggested commit: `feat: add live call protocol and session lifecycle`

## Task 2 — Prove browser-to-backend audio transport

```text
Read AGENTS.md and perform BUILD_STEPS.md Task 2 only.

Add a live-call entry point alongside the existing upload UI, a useLiveCall hook, Start/Stop controls, elapsed time, connection status, and concise errors. Capture microphone audio and send bounded binary frames to the existing call WebSocket. MediaRecorder is allowed for this transport-only task; label the encoding accurately and document that it will be replaced by PCM in Task 3.

Backend receives frames, validates state/size, counts bytes, and sends throttled audio.ack diagnostics. It does not transcribe, decode each blob as an independent recording, or call an LLM. Add max call duration and browser bufferedAmount protection.

Release microphone tracks and socket resources on stop, start failure, permission denial, network loss, and unmount. Prevent duplicate capture under React StrictMode. Keep microphone capture separate from presentation components.

Test fake capture/socket lifecycle and backend frame limits; run typecheck/build and relevant V1 checks. Update protocol docs and BUILD_PROGRESS.md. Stop here.
```

Manual check: Start, speak for 10–20 seconds, see byte count rise, then stop. The browser microphone indicator turns off. Repeat twice. Deny microphone permission once and verify useful recovery.

Pass criteria: Transport works without AI, queues are bounded, Stop releases capture, and V1 upload still opens and works.

Suggested commit: `feat: stream microphone audio to fastapi`

## Task 3 — Replace demo capture with correct PCM streaming

```text
Read AGENTS.md and perform Task 3 only. Inspect current official OpenAI streaming transcription audio requirements before fixing the contract. Record the reference and chosen format in docs/STT_PROVIDER.md.

Replace the MediaRecorder transport demo with an AudioWorklet path. Implement mono conversion, continuous resampling from the actual AudioContext rate, float clipping, and signed 16-bit little-endian PCM encoding. Baseline target is 24 kHz mono and approximately 100 ms frames, subject to the verified API contract.

Carry resampling/frame state across worklet blocks and flush the final short frame before stop. Do not assume browser constraints set the hardware sample rate. Ensure audio before start is rejected; backend validates frame bounds/alignment and encoding metadata. Keep the worklet in the appropriate Vite-served location.

Test known PCM samples, clipping, byte order, resampling duration at 44.1/48 kHz, continuity across block boundaries, partial-frame flush, congestion, and resource cleanup. No paid API calls. Update docs and progress. Stop here.
```

Pass criteria: Encoded duration matches captured duration within a documented tolerance; continuous input does not reset at block boundaries. No WebM data is labeled PCM. Browser testing is recorded separately from unit tests.

Suggested commit: `feat: encode bounded microphone pcm frames`

## Task 4 — Add the streaming transcription adapter

```text
Read AGENTS.md and perform Task 4 only. Check the installed OpenAI SDK and current official realtime transcription/session docs. Do not guess SDK methods, model names, VAD support, or event fields. Choose a configurable transcription-only model supported by the account and record the contract in docs/STT_PROVIDER.md. Use server-side credentials.

Implement a small StreamingTranscriber adapter with connect, send_audio, finish_turn/flush, events, and close responsibilities, plus a deterministic fake. Normalize provider partial/final events into internal transcript segments. Preserve provider turn/item identifiers and ordering links needed to handle out-of-order completions. Map provider errors to sanitized application errors.

Implement endpointing compatible with the chosen model. If provider VAD is unsupported, use a simple documented local endpoint detector or an explicit turn-commit control during development; do not assume unsupported VAD works. Test silence, continuous speech, turn boundaries, and final flush behavior.

Mock the provider to test deltas, duplicate/out-of-order finals, provider failure, timeout, and cleanup. Do not run a paid smoke test. Document the opt-in smoke-test command and what remains unverified without credentials. Stop here.
```

Pass criteria: A fake provider generates accurate partial/final normalized events in audio-turn order. The chosen provider protocol is documented, with endpointing and commit rules. If the model is inaccessible, Codex finishes fake tests and reports the real integration blocker rather than silently substituting an incompatible model.

Optional manual smoke test, explicitly requested by you: Use 15–30 seconds of synthetic/consented speech with a server-side key. Verify the selected provider model produces incremental text and a final completion. Never paste your key into a prompt.

Suggested commit: `feat: add isolated streaming transcription adapter`

## Task 5 — Connect live transcription and implement stop/drain

```text
Read AGENTS.md and perform Task 5 only.

Connect PCM receive to the STT adapter and render transcript.partial/transcript.final in React. Partials replace the displayed draft; finals replace the draft and enter final context once. Keep segment order correct when provider completions arrive out of order. Show unknown speaker roles unless evidence exists.

Separate audio IO, transcript handling, and semantic-work queues. Add the stop sequence from AGENTS.md: send/flush last browser frame, stop accepting audio, drain queued frames, flush the provider's final nonempty turn, wait bounded time for pending finals, preserve incomplete status, close resources, and emit call.ended. Disconnect performs bounded cleanup and marks interrupted. Do not implement seamless live resume.

Test duplicate stop, final text arriving during stopping, empty/silent call, no provider completion, fake slow consumers, queue saturation, network loss, and isolation of two simultaneous calls. Verify StrictMode/unmount cleanup. Keep V1 unchanged. Update docs/progress and run relevant backend/frontend checks. Stop here.
```

Manual check: Speak a sentence, pause, speak another, stop immediately after the final word. Check that the last utterance is retained and the microphone is released. A timed-out finalization must show incomplete transcript status.

Pass criteria: Slow downstream work cannot stall transcription, no finalized segments are silently lost, and final ordering is stable.

Suggested commit: `feat: render live transcript with reliable call finalization`

## Task 6 — Add an offline transcript replay harness

```text
Read AGENTS.md and perform Task 6 only.

Add synthetic transcript fixtures with stable segment IDs/order, optional timing, explicit unknown speaker roles, and expected sales signals. Include a demo with pricing, competitor, ordinary question, requirement, and buying-intent utterances; also include silence/no-signal and repeated-objection cases.

Implement a developer replay command that feeds these fixtures through the same final-segment pipeline without microphone or STT API usage. Keep replay out of the production audio path. Let tests inject a fake clock; avoid real waiting in unit tests.

Use replay to demonstrate partial/final replacement, repeated finals, and out-of-order completion handling. Document the command and distinguish transcript replay from STT evaluation. Do not pretend replay proves audio transcription accuracy. Update progress and stop here.
```

Pass criteria: You can reproduce the transcript/UI behavior without paid APIs or microphone access. Fixtures are fictional and committed; private customer recordings are excluded.

Suggested commit: `test: add deterministic transcript replay fixtures`

## Task 7 — Detect live sales events from final context

```text
Read AGENTS.md and perform Task 7 only.

Add validated SalesEvent schemas for question, objection, competitor, pricing, buying_signal, and requirement. Each event cites source segment IDs and a short exact evidence span; validate both against the input. Treat confidence as an uncalibrated model estimate if included.

Implement a small structured-output classifier behind an injected client. Trigger from bounded final-transcript windows using count/character thresholds plus a trailing timer. Process a lone utterance even when conversation stops; coalesce pending windows while one request runs. Never classify partial words. Preserve a processed watermark, deduplicate overlapping-window events, and allow a genuinely new repeated objection.

Emit sales.event and show a simple signal list. Classify role-unknown text honestly; do not invent who said it. No RAG/coaching yet.

Test evidence validation, ordinary question vs objection, multiple event types, no-signal text, duplicates, quiet trailing windows, stale results, schema/API failure, and continuing transcript delivery during a slow classifier. Use fake AI calls. Update docs/progress and stop here.
```

Pass criteria: The replay fixture produces expected events with valid evidence references, while no-signal and repeated windows avoid spurious duplicate signals. Report fixture results, not unmeasured accuracy.

Suggested commit: `feat: detect evidence backed live sales signals`

## Task 8 — Introduce PostgreSQL + pgvector and ingest knowledge

```text
Read AGENTS.md and perform Task 8 only.

Add local Docker Compose for PostgreSQL with pgvector and migrations using SQLAlchemy/Alembic, following existing conventions. This stage introduces only knowledge storage; do not add Redis or accounts yet. Pin tested image/dependency versions. Document Windows/WSL-compatible setup without assuming host package installation.

Create synthetic Markdown product, pricing, competitor, objection-handling, and sales-playbook documents for a fictional company. State that all facts/prices are fictional. Implement deterministic heading-aware chunks with stable IDs, source path/heading, content hashes, document/corpus revisions, embedding model, and vector dimensions.

Add a CLI ingestion command with a fake embedding mode for tests and explicit opt-in real embedding usage. Make unchanged ingestion reusable, changed/deleted content non-stale, and corpus publication atomic so failed ingestion leaves the previous revision searchable. Never mix embedding models/dimensions.

Test chunk determinism, repeated ingestion, changes/deletions, failed embedding batch, and dimension mismatch; run marked DB integration tests if services are available. Update docs/progress and stop here.
```

Pass criteria: Migrations work on an empty disposable database; fake ingestion is reproducible and idempotent; failing a refresh does not publish a partial corpus. Credentials and database volumes are not committed.

Suggested commit: `feat: ingest versioned sales knowledge into pgvector`

## Task 9 — Implement and evaluate retrieval

```text
Read AGENTS.md and perform Task 9 only.

Implement parameterized exact cosine search over the active corpus revision. Use the corpus embedding model/dimensions for query embeddings. Return bounded top-k results with distance, chunk ID, source heading/path, text, and content revision. Do not add ANN indexes, a second vector database, or a web crawler.

Add labeled retrieval fixtures: pricing question, competitor comparison, implementation requirement, and unrelated/no-answer query. Use deterministic test vectors for integration tests; separate those results from real embedding quality. Define a configurable evidence threshold and explain that it requires empirical tuning.

Test expected source ordering, empty corpus, below-threshold results, invalid dimensions, inactive/stale revisions, database failure, and SQL parameterization. Document a developer query command and opt-in real retrieval evaluation. Do not implement coaching yet. Update progress and stop here.
```

Pass criteria: Retrieval returns inspectable sources or a clear no-evidence result. Test vectors do not masquerade as measured semantic-search quality.

Suggested commit: `feat: retrieve relevant sales playbook evidence`

## Task 10 — Add source-grounded live coaching

```text
Read AGENTS.md and perform Task 10 only.

Connect eligible sales events to retrieval and then a structured-output CoachService. Pass bounded recent context, evidence segments, and retrieved chunks. Return a concise suggested response/clarifying question, source chunk IDs, evidence segment IDs, and insufficient_evidence status. Treat transcript and knowledge text as data, not instructions.

Validate cited chunks were retrieved and evidence IDs exist. Require source support for factual product/pricing/competitor claims. If retrieval is weak, offer a clarifying question or acknowledge missing facts; never invent discounts or advantages. Store source versions in the suggestion payload and render clickable/expandable source details in React.

Add per-call cooldown, bounded concurrency, trigger deduplication, and context freshness checks. Suppress stale results and all new live suggestions after stopping. Coaching failures produce a warning while transcript delivery continues. No spoken audio or external actions.

Test valid/invalid citations, no-evidence handling, injected instructions, duplicate triggers, stale results, stop cancellation, and slow-model behavior using fakes. Update docs/progress and stop here.
```

Manual check: Replay a pricing objection with a matching playbook, inspect the suggestion's sources, then replay an unsupported feature question. The second must not invent an answer.

Pass criteria: Live transcript remains responsive; suggestions are short and evidence-linked. The UI does not imply that model confidence or a citation alone guarantees correctness.

Suggested commit: `feat: provide grounded text coaching during live calls`

## Task 11 — Persist active calls and add history APIs

```text
Read AGENTS.md and perform Task 11 only.

Add migrations and repository methods for calls, final transcript_segments, sales_events, suggestions, and analysis status. Persist accepted finals/events/suggestions during a call rather than waiting for stop. Retain source metadata/version snapshots for historical citations. Raw audio retention stays off.

Add bounded paginated list/detail endpoints and a basic history view. Use foreign keys, unique constraints, per-call ordering, parameterized queries, transactions, and idempotent writes. Call ended/interrupted and analysis pending/completed are separate statuses. On service shutdown mark recoverable calls interrupted; on restart reconcile abandoned live state.

Handle write failures explicitly: do not display Saved when persistence failed. Limit local access and validate WebSocket Origin; do not describe UUIDs as authorization or deploy public history endpoints.

Test duplicate final writes, event/suggestion identity, call isolation, interrupted-call retention, pagination, failed writes, restart reconciliation, and historical citations after corpus changes. Use a disposable DB. Update docs/progress and stop here.
```

Pass criteria: A stopped/interrupted call remains readable after backend restart with correct ordered finals. PostgreSQL, not Redis or UI state, owns saved history.

Suggested commit: `feat: persist live call records and history`

## Task 12 — Reuse V1 analysis and scoring after live calls

```text
Read AGENTS.md, docs/V1_BASELINE.md, and Task 12. Perform only this task.

Freeze the ordered final transcript after bounded stop/drain and invoke the existing V1 transcript-analysis service and scoring function through a thin adapter. Do not retranscribe live audio or create a second analysis schema/scoring implementation. Preserve V1 score weights, categories, upload endpoint, and response compatibility.

Persist analysis pending/running/completed/failed status and result version. Use an atomic job claim and one logical result per call+version, a supervised single-process task, bounded retries, and an explicit failed-analysis retry endpoint. Recover abandoned running claims after a documented timeout. Do not claim exactly-once API execution; retries may repeat a billable request.

Publish analysis.started/completed/failed when a socket remains available; history polling must work after disconnect. Label incomplete transcripts and skip analysis/scoring for empty or insufficient text according to existing validation. Explain deterministic Python scoring vs subjective LLM ratings.

Test simultaneous stop/retry, duplicate scheduling, failed analysis recovery, empty/incomplete calls, V1 schema/score compatibility, and the original upload flow. Use fake providers. Update docs/progress and stop here.
```

Pass criteria: Upload and live-final transcripts converge on the same analysis/scoring implementation. Saved failures are retryable without duplicating logical results or erasing the call.

Suggested commit: `feat: reuse v1 analysis for finalized live transcripts`

## Task 13 — Add Redis for bounded temporary context

```text
Read AGENTS.md and perform Task 13 only.

Introduce a small SessionStore interface by extracting the working in-memory session context, then implement a Redis store with equivalent tested behavior. Add Redis to Compose. Store only active metadata, bounded recent context, event/suggestion deduplication keys, and TTLs. Sockets, STT connections, async tasks, and durable full transcripts stay elsewhere.

Use call-scoped keys, active TTL refresh, cleanup policy, and atomic conditional deduplication operations. Avoid unsafe concurrent read-modify-write and unbounded histories. Define expiry shorter for completed context and a bounded in-memory fallback for Redis outages in the single-worker demo. Emit degraded-mode status without interrupting transcription unnecessarily.

Test store equivalence, TTL/refresh, call isolation, duplicate detection races, Redis outage/recovery, cleanup, and unchanged PostgreSQL history. Document that Redis does not enable multiple workers or seamless active-call resume. Do not add streams, pub/sub fan-out, or Kafka. Update docs/progress and stop here.
```

Pass criteria: Redis has an observable purpose and failure policy; stopping Redis does not erase saved calls. The deployment still uses one backend worker.

Suggested commit: `feat: keep ephemeral call context in redis`

## Task 14 — Finish the dashboard without expanding scope

```text
Read AGENTS.md and perform Task 14 only.

Refine the existing React UI into live transcript, latest grounded suggestion/source details, sales-signal timeline, call status/duration, and a completed-call view using the existing V1 analysis components. Retain the upload workflow. Add history navigation, analysis pending/failed/retry states, and visible incomplete/degraded-state messages.

Show partial text differently from finals. Avoid forcing scroll when the user reads earlier text. Keep unknown speakers labeled honestly. Show only measured metrics: event counts and known stage timings; no fabricated agent/customer talk ratio or emotion meter. Explain score components using the existing rubric.

Use existing styling and routing conventions. Add accessible labels, keyboard operation, useful empty states, responsive layout, and safeguards against stale events from the previous call. Do not add auth, billing, CRM, or a redesign of unrelated V1 pages.

Test event reducers, controls by state, call-switch isolation, delayed/stale events, source details, history/retry, and resource cleanup. Run typecheck/build and relevant V1 checks. Update progress and stop here.
```

Pass criteria: You can show the complete demo from Start through saved analysis; microphone errors, interrupted calls, and unavailable metrics have clear UI states.

Suggested commit: `feat: complete live coaching and call history dashboard`

## Task 15 — Evaluate English, Hindi, and Hinglish honestly

```text
Read AGENTS.md and perform Task 15 only.

Add labeled synthetic English, Hindi (Devanagari), and Hinglish fixtures covering questions, objections, competitors, requirements, negation, and no-signal conversations. Preserve original transcript text and Unicode. Adapt detector/coach instructions to understand code-switching and choose a documented suggestion language without altering factual grounding.

Separate transcript reasoning evaluation from actual audio STT evaluation. Add optional consented/synthetic audio smoke-test instructions and document model language configuration, uncertain language labels, and known failures. Never force Hindi-only configuration for a mixed-language call without testing the provider behavior.

Maintain unknown speaker roles for mixed microphone input. If automatic diarization is supported by the chosen streaming provider, first document capability and limitations; only implement it as a separately requested subtask. Speaker IDs require explicit salesperson/customer role mapping, and talk ratio requires actual reliable timing. Do not guess roles from wording or assign alternating utterances.

Test Unicode roundtrip and multilingual evidence spans, evaluate fixtures using fake/classifier outputs where appropriate, and provide an opt-in real evaluation command. Report actual measured results separately; do not invent multilingual accuracy. Update docs/progress and stop here.
```

Pass criteria: The app handles multilingual text without corrupting evidence or citations. Language/STT accuracy remains a documented measured capability, not a blanket claim.

Suggested commit: `feat: support and evaluate multilingual call context`

## Task 16 — Instrument latency and test controlled load

```text
Read AGENTS.md and perform Task 16 only.

Add correlated monotonic timing for STT final receipt, detection, embedding/retrieval, coaching, and suggestion delivery. Define the main application metric precisely as final transcript received → suggestion delivered. Measure speech-end latency only if a valid audio/VAD boundary and compatible clock mapping exist; otherwise label it unavailable.

Track stage durations, p50/p95 over repeated samples, errors, active calls, queue depth, coalesced windows, and stale suggestions. Do not log audio/transcript contents or secrets. Create a replay benchmark with fake providers and an opt-in real benchmark; explicitly distinguish their results.

Use bounded synthetic load to test slow classification, slow DB/Redis, queue saturation, provider timeouts, repeated start/stop, and two concurrent calls in one worker. Confirm finalized transcripts are retained or failure is explicit. Set budgets as engineering targets, not claimed benchmark results. Optimize only demonstrated bottlenecks within the existing architecture.

Run relevant checks, record actual measured environment/sample count/results in docs/LATENCY.md, update progress, and stop here.
```

Pass criteria: Latency numbers have named start/end events, sample counts, and environment. No made-up subsecond guarantee. Overload does not silently lose final transcripts.

Suggested commit: `perf: instrument and validate live pipeline latency`

## Task 17 — Package, review, and prepare the interview demo

```text
Read AGENTS.md and perform Task 17 only.

Complete local Docker Compose for frontend, one backend worker, PostgreSQL+pgvector, and Redis. Add health checks, dependency readiness, persistent DB volume, non-secret environment examples, and explicit migration/ingestion commands. Never call docker compose down -v automatically. Explain localhost/HTTPS microphone restrictions and WebSocket proxy configuration.

Add CI for backend unit tests, frontend tests/typecheck/build, and disposable PostgreSQL/Redis integration checks. All default tests use fake AI providers and synthetic data. Preserve existing CI rather than duplicate it. Real API tests remain explicitly opt-in.

Review source and docs for secret leakage, PCM errors, provider schema drift, V1 regression, final-turn loss, blocking IO, orphan tasks, unbounded queues, invented speakers, stale suggestions, unsupported citations, duplicate jobs, persistence failures, and unnecessary complexity. Fix high/medium findings within scope; document remaining limitations with evidence.

Run the full relevant suite once after fixes. Write README setup/run/demo/troubleshooting commands using actual repository paths, docs/DEMO_SCRIPT.md, and docs/INTERVIEW_NOTES.md. Include architecture, V1→V2 evolution, failure behavior, retrieval grounding, measured latency, privacy/local-use boundary, and deferred work. Mark BUILD_PROGRESS.md truthfully; do not mark unrun paid checks passed. Stop here.
```

Pass criteria: A fresh clone can install dependencies, migrate/ingest demo knowledge, and run fake replay with documented commands. Real mode is configured separately. The full V1 upload workflow survives the V2 release.

Suggested commit: `chore: package verify and document pitchpilot v2`

After you verify the intended release commit:

```bash
git tag v2.0-realtime-copilot
```

Do not overwrite an existing release tag. Publishing or public hosting is a separate task because this baseline has no user access control.

---

## Verification commands: resolve them in Task 0

Codex must replace these examples with the actual commands and paths in docs/V1_BASELINE.md/README. Run only configured scripts; missing scripts are not passing checks.

| Check | Typical command | Notes |
| --- | --- | --- |
| Backend unit tests | `python -m pytest` | Run from actual backend/environment; default fakes only |
| Frontend tests | `npm run test -- --run` | Use the existing package manager and test script |
| Typecheck | `npm run typecheck` | Add a script if needed; do not silently skip TS validation |
| Frontend production build | `npm run build` | Verify worklet assets resolve |
| Infrastructure | `docker compose up -d postgres redis` | Use actual service names; Redis exists from Task 13 |
| Migrations | `python -m alembic upgrade head` | Correct working directory/config required |
| DB/Redis integration | `python -m pytest -m integration` | Disposable test services, never the user's real DB |
| Frontend dev | `npm run dev` | Preserve existing dev conventions |
| Backend dev | Repository's documented Uvicorn command | Do not invent a module path |
| Replay / ingestion / benchmark | Scripts added by their tasks | README must contain concrete commands |

Do not run destructive cleanup against development volumes just to reset integration tests. Create isolated test services/databases.

## Small demo script you should be able to perform

1. Show V1 upload and its existing structured analysis/score.
2. Start a live call and speak a fictional product question followed by a price objection.
3. Show partial text becoming final, detected evidence-backed events, and a grounded suggestion with sources.
4. Ask about an unsupported feature; show a clarifying question or insufficient evidence.
5. Stop immediately after a final utterance; verify it survives finalization and microphone capture ends.
6. Open saved history and show V1 analysis/scoring applied to the live transcript.
7. Use replay for a Hindi/Hinglish example and state that replay tests reasoning, not STT accuracy.
8. Show observed latency metrics and explain what their start/end boundaries measure.

Use fictional data. When demonstrating real microphone/STT mode, explicitly choose to incur its API usage.

## Ask Codex to explain each completed stage

```text
Explain the task we just completed so I can defend it in an interview.
Keep it concise. For each important changed module, describe:
- its responsibility and input/output;
- its place in the data flow;
- the failure it handles;
- one reasonable alternative and why we chose this approach.
Identify any limitation or check that was not actually verified.
Then ask me one technical question at a time; wait for my answer.
```

## Recovery prompt when something breaks

```text
Read AGENTS.md and docs/BUILD_PROGRESS.md. Diagnose this failure in the existing implementation.
Reproduce with a focused fake-provider test where possible, identify the earliest failed boundary, and fix only the cause. Preserve V1 contracts and unrelated edits. Do not remove assertions, hide errors, replace the stack, or add infrastructure to bypass the bug. Run the relevant checks and report actual results. Update progress with the fix and any remaining limitation.
```

## Completion checklist

- [ ] V1 upload API, schema, scoring, UI, and tests remain compatible.
- [ ] Binary audio encoding matches the verified provider contract.
- [ ] Capture/resources are released after normal stop and failures.
- [ ] Partial/final replacement and out-of-order final handling are correct.
- [ ] Stop drains the last utterance within a timeout or marks incomplete.
- [ ] Slow semantic work does not block audio/transcript delivery.
- [ ] Event evidence is validated and duplicates are controlled.
- [ ] Knowledge updates are reproducible and do not expose stale/partial corpora.
- [ ] Retrieval returns inspectable sources and handles no-match queries.
- [ ] Coaching validates citations and abstains from unsupported product claims.
- [ ] Durable records survive interruption/restart; errors do not falsely claim Saved.
- [ ] Post-call analysis reuses V1 and has recorded retryable failures.
- [ ] Redis state is bounded, isolated, and temporary.
- [ ] Unknown speakers and unavailable talk ratio are displayed honestly.
- [ ] English/Hindi/Hinglish evaluation distinguishes reasoning from STT quality.
- [ ] Measured latency is labeled with boundaries, samples, and environment.
- [ ] Default tests/CI run without API keys or real customer recordings.
- [ ] Fresh-clone setup and fake demo are documented and verified.
- [ ] Private/local demo limitations and deferred public access control are clear.

## Reference notes

The provider and library APIs change. Consult these primary sources during the relevant task:

- Repository instructions: https://developers.openai.com/codex/guides/agents-md
- OpenAI streaming transcription: https://developers.openai.com/api/docs/guides/realtime-transcription
- OpenAI structured outputs: https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI Python SDK: https://github.com/openai/openai-python
- PostgreSQL vector search: https://github.com/pgvector/pgvector
- Browser AudioWorklet: https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet

At preparation time, official transcription documentation described transcription-only sessions, PCM audio, incremental/completed transcript events, and model-specific endpointing behavior. The plan deliberately requires checking those fields again instead of treating old example payloads as a permanent API contract. Exact pgvector search is sufficient for the small initial corpus; approximate indexing is a measured future choice.
