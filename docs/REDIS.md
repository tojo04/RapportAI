# Ephemeral context

Redis has one narrow role: bounded recent finalized context, active metadata, and atomic per-call deduplication keys with TTLs. PostgreSQL remains the durable owner of full saved calls. Sockets, provider connections, raw audio, and asyncio tasks never enter Redis.

Set `REDIS_ENABLED=true` to use it. A Redis outage switches the one-worker demo to a bounded in-memory store and should be presented as degraded mode; it does not interrupt transcription or erase PostgreSQL history. Completed ephemeral context expires sooner than active context.

Redis does not make active calls resumable and does not enable multiple backend workers. This release intentionally remains one worker without pub/sub or streams.
