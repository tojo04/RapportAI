# Saved calls and post-call analysis

When `PERSISTENCE_ENABLED=true`, PostgreSQL stores accepted final transcript segments, signals, grounded suggestion snapshots, terminal call state, and analysis state. Writes are idempotent and ordered per call. Raw audio is never retained. History APIs are intended for local demo use only; opaque UUIDs are identifiers, not authorization.

On startup, abandoned active calls become `interrupted` and abandoned analysis claims become retryable failures. `GET /api/calls` is bounded to 100 items; `GET /api/calls/{call_id}` returns ordered details. Failed analysis can be rescheduled with `POST /api/calls/{call_id}/analysis/retry`.

After bounded stop/drain, the ordered final transcript is frozen and passed to the existing V1 `analyze_transcript` service and deterministic `calculate_call_score` function. Live audio is not retranscribed and no second scoring schema exists. The Python score is deterministic for the model ratings; those 0–5 ratings remain subjective model judgments. API retries can repeat a billable model request, although the database maintains one logical result for `call_id + analysis_version`.
