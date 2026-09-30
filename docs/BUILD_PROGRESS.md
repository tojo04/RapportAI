# RapportAI V2 build progress

Last updated: 2026-09-30

## Task checklist

- [x] Task 0 — Audit V1 and reconcile instruction files
- [x] Task 1 — Define the protocol and session state machine
- [x] Task 2 — Prove browser-to-backend audio transport
- [ ] Task 3 — Replace demo capture with correct PCM streaming
- [ ] Task 4 — Add the streaming transcription adapter
- [ ] Task 5 — Connect live transcription and implement stop/drain
- [ ] Task 6 — Add an offline transcript replay harness
- [ ] Task 7 — Detect live sales events from final context
- [ ] Task 8 — Introduce PostgreSQL + pgvector and ingest knowledge
- [ ] Task 9 — Implement and evaluate retrieval
- [ ] Task 10 — Add source-grounded live coaching
- [ ] Task 11 — Persist active calls and add history APIs
- [ ] Task 12 — Reuse V1 analysis and scoring after live calls
- [ ] Task 13 — Add Redis for bounded temporary context
- [ ] Task 14 — Finish the dashboard without expanding scope
- [ ] Task 15 — Evaluate English, Hindi, and Hinglish honestly
- [ ] Task 16 — Instrument latency and test controlled load
- [ ] Task 17 — Package, review, and prepare the interview demo

## Task 0 outcome

### Baseline

- V1 baseline is commit `db893a3` and tag `v1.0-upload-analyzer`.
- V2 work is on branch `realtime-v2`.
- The V1 upload application was not changed.
- The old V1 root rules and build guide are archived as
  `docs/v1/AGENTS_V1.md` and `docs/v1/BUILD_STEPS_V1.md` so they do not act as
  nested Codex instructions.
- The supplied V2 files are now the active root `AGENTS.md` and
  `BUILD_STEPS.md`.

### Reconciled decisions

- Kept the actual project name **RapportAI**; the supplied **PitchPilot** title
  was treated as a template placeholder.
- The V2 authorization supersedes V1 prohibitions on WebSockets, live
  transcription, PostgreSQL/pgvector, Redis, and Docker Compose only for the
  staged tasks in the active guide.
- Preserved V1 rules for its upload contract, typed validation, deterministic
  scoring, secret handling, tests, and small understandable modules.
- Found no nested active `AGENTS.md` file requiring reconciliation.
- Retained npm/package-lock and `requirements.txt`; no package manager or stack
  was changed.
- Selected an additive migration: V1 upload remains, while live calls gain
  separate routes, protocol, services, and UI composed into the same app.
- Recorded the current Realtime transcription documentation as preliminary
  provider input. Tasks 3 and 4 must verify it again before implementation.

### Actual checks

```text
backend/.venv/Scripts/python.exe -m pytest
75 passed, 1 provider-library deprecation warning

npm test -- --run
4 files passed, 22 tests passed

npm run lint
passed

npm run typecheck
passed

npm run format:check
passed

npm run build
passed
```

No paid OpenAI request or private recording was used.

### Baseline findings to track

- The frontend install was absent; `npm ci` restored dependencies before
  checks. npm reported two moderate and three high dependency audit findings.
- FastAPI's test client emitted a deprecation warning about the installed
  `httpx` integration.
- Python dependencies are version-ranged rather than locked; Task-specific
  additions must be compatible and documented.
- The audit ran on Python 3.14.3 even though the project minimum is Python
  3.11. Compatibility must continue to be tested against the supported range
  in CI when CI is introduced.

## Task 1 outcome

### Implemented

- Added versioned Pydantic command/event models and matching TypeScript
  discriminated unions with runtime validation.
- Added `POST /api/calls`, returning a backend-generated opaque call ID and its
  `/ws/calls/{call_id}` path.
- Added the in-memory lifecycle `idle -> connecting -> live -> stopping ->
ended`, with `interrupted` disconnect cleanup and a reserved `failed` state.
- Implemented `start`, `stop`, and `ping`, including command-ID collision
  detection, duplicate start acknowledgement, and harmless duplicate stop.
- Added one bounded outbound writer per connected call and bounded shutdown so
  child tasks are awaited or cancelled.
- Enforced configured browser Origin checks independently from CORS, bounded
  control messages, active calls, terminal-session retention, command history,
  and outbound queues.
- Rejected unknown calls, terminal/already-connected sessions, malformed
  payloads, incompatible versions, illegal transitions, and binary audio.
- Documented event envelopes, payloads, transitions, close codes, single-worker
  ownership, and the no-live-resume policy in `docs/realtime-protocol.md`.
- Kept `POST /api/analyze-call`, its models, and V1 scoring unchanged.

### Verification

```text
backend/.venv/Scripts/python.exe -m pytest
104 passed, 1 existing provider-library deprecation warning

npm test -- --run
5 files passed, 28 tests passed

npm run lint
passed

npm run typecheck
passed

npm run format:check
passed

npm run build
passed
```

No paid API call, microphone capture, or AI provider connection was used.

### Current limitations

- Live sessions are process-local and require one backend worker.
- Terminal sessions and command IDs have bounded in-memory retention; durable
  history is intentionally deferred.
- Binary audio returns `audio_not_supported` until Task 2.
- The browser has protocol types only; live-call controls/capture begin in Task 2.

## Task 2 outcome

### Implemented

- Added a live-call panel beside the unchanged upload workflow with Start/Stop,
  authoritative connection state, elapsed time, cumulative frames/bytes, and
  concise errors.
- Added `useLiveCall` to isolate microphone, MediaRecorder, socket, timers, and
  cleanup from presentation components.
- Streams approximately 250 ms MediaRecorder blobs as binary frames and labels
  them with the recorder's actual MIME type. It never calls this data PCM.
- Flushes the recorder's final blob before sending `stop`, releases microphone
  tracks promptly, and handles permission failure, connection loss, unmount,
  repeated start/stop, and React StrictMode.
- Terminates the call when `WebSocket.bufferedAmount` exceeds 1 MiB instead of
  buffering audio without a bound.
- Extended session creation with authoritative frame, acknowledgement, and
  duration limits.
- Backend accepts audio only in `live` state with MediaRecorder metadata,
  rejects empty/oversized frames, counts accepted bytes/frames, emits throttled
  `audio.ack`, forces a final acknowledgement before stop, and enforces maximum
  call duration.
- Audio is not decoded, persisted, transcribed, or sent to an AI model.

### Verification

```text
backend/.venv/Scripts/python.exe -m pytest
114 passed, 1 existing provider-library deprecation warning

npm test -- --run
7 files passed, 37 tests passed

npm run lint
passed

npm run typecheck
passed

npm run format:check
passed

npm run build
passed
```

Automated tests cover fake capture/socket cleanup, final-frame ordering,
congestion, network loss, permission denial, StrictMode, acknowledgements,
frame limits, and server duration enforcement.

### Manual check pending

The real-browser microphone check has not been run in this environment. Run the
backend/frontend, speak for 10-20 seconds, verify byte count increases and the
microphone indicator turns off, repeat once, then deny permission once. This is
required before claiming browser/device compatibility.

## Next task

## Task 3 outcome

### Implemented

- Verified the official Realtime transcription contract and recorded the model,
  PCM format, and unsupported provider VAD modes in `docs/STT_PROVIDER.md`.
- Replaced MediaRecorder with AudioWorklet mono capture plus continuous,
  stateful resampling from the actual AudioContext rate.
- Added clipped signed PCM16LE encoding, 24 kHz mono 100 ms framing, and a
  final short-frame flush before the stop command.
- Backend now requires matching PCM metadata and rejects empty, oversized, and
  odd-byte frames as well as audio received outside the live state.
- Retained the 1 MiB browser WebSocket congestion cutoff and resource cleanup.

### Verification

```text
backend/.venv/Scripts/python.exe -m pytest
114 passed, 1 existing provider-library deprecation warning

npm test -- --run
8 files passed, 42 tests passed

npm run lint
passed

npm run typecheck
passed

npm run format:check
passed after formatting the two new PCM test/source files

npm run build
passed; the worklet is copied as a Vite public asset
```

### Manual check pending

Real AudioWorklet microphone capture has not been exercised in a browser in
this environment. Confirm that acknowledged PCM bytes rise, the microphone
indicator turns off, repeated calls work, and permission denial is recoverable.

## Next task

## Task 4 outcome

### Implemented

- Verified installed OpenAI SDK 2.52.0 methods and current official Realtime
  session, audio-buffer, delta, completion, and ordering contracts.
- Added a small streaming adapter with `connect`, `send_audio`, explicit
  `finish_turn`/`flush`, normalized `events`, and idempotent `close`.
- Added a deterministic fake and provider injection boundary; no test contacts
  an external service.
- Normalized cumulative partials and finals while preserving provider event,
  item, predecessor, revision, and audio-turn order data. Duplicate finals are
  ignored and provider completions may arrive out of turn order.
- Added local peak/silence endpointing because the selected model does not
  support server or semantic VAD. Silence is not committed, speech pauses
  commit, and Stop flushes continuous speech.
- Added sanitized failure/timeout handling, configurable `LIVE_STT_MODEL`, and
  an explicitly paid raw-PCM smoke-test script that was not run.

### Verification

```text
backend/.venv/Scripts/python.exe -m pytest
119 passed, 1 existing provider-library deprecation warning

backend/.venv/Scripts/python.exe -m scripts.smoke_streaming_stt --help
passed without contacting the provider
```

### Unverified

The opt-in paid provider smoke test was not run. Account access, model
availability, and real provider latency/event behavior remain unverified.

## Next task

Task 5 — connect accepted PCM to the adapter, stream normalized partial/final
events to React, and implement bounded stop/drain cleanup.
