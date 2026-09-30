# RapportAI V2 build progress

Last updated: 2026-09-30

## Task checklist

- [x] Task 0 — Audit V1 and reconcile instruction files
- [ ] Task 1 — Define the protocol and session state machine
- [ ] Task 2 — Prove browser-to-backend audio transport
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

## Next task

Task 1 — define and test the versioned realtime protocol, in-memory live-call
state machine, session creation route, and WebSocket control lifecycle. Do not
connect microphone audio or an AI provider in that task.

