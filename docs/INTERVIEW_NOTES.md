# RapportAI interview notes

## Evolution

V1 is a recorded-call analyzer: temporary upload → transcription → schema-validated analysis → deterministic Python score. V2 preserves that contract and adds browser PCM streaming, provider-normalized transcript events, evidence-backed sales detection, versioned pgvector knowledge, grounded text coaching, durable history, and post-call reuse of V1 analysis.

## Design choices

- One backend worker keeps socket/task ownership explicit. Redis provides bounded ephemeral context, not distributed execution or resume.
- PostgreSQL owns durable finals/events/suggestions/analysis; raw audio is never stored.
- Corpus publication is transactional and model/dimension-specific. Exact cosine search is inspectable; no ANN complexity is justified for the demo corpus.
- The LLM detects/rates semantics. Pydantic validates it, citations are checked, and ordinary Python calculates the score.
- Optional semantic failures never silently remove finalized transcript text.

## Failure and privacy boundary

This is a localhost/interview baseline without auth; never expose history publicly. UUIDs are not access control. Browser microphones require localhost or HTTPS. CORS and WebSocket Origin allowlists are separate. A reverse proxy must forward WebSocket Upgrade and Origin headers. Provider calls may be billable and retry; no exactly-once external execution is claimed.

## Evidence and limitations

Fake providers and synthetic data cover deterministic behavior. The recorded fake latency benchmark is measurement-math evidence, not real AI latency. Docker integration, real microphone/provider behavior, real multilingual audio quality, model retrieval quality, and controlled two-call load require their documented opt-in checks. Diarization, reliable role mapping, talk ratio, auth, public deployment, CRM actions, and horizontal scaling are deferred.
