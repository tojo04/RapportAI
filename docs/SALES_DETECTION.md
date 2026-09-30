# Live sales-signal detection

Only finalized transcript segments reach the detector. It coalesces bounded
recent windows, triggers on count/character thresholds or a 750 ms quiet tail,
and keeps one classifier request in flight. New finals are coalesced while that
request runs.

The classifier uses Pydantic Structured Outputs through the Responses API. Each
question, objection, competitor, pricing, buying-signal, or requirement result
must cite existing segment IDs and a short exact evidence span. RapportAI
validates both before emission. Transcript text is treated as untrusted data,
speaker role stays unknown, overlapping results are deduplicated, and a later
objection from a new segment remains eligible.

`LIVE_CLASSIFICATION_MODEL` is optional. When unset, live transcription works
without classification. Tests use injected fakes; no paid classifier call was
run. The implementation follows the official OpenAI Structured Outputs guide:
https://developers.openai.com/api/docs/guides/structured-outputs
