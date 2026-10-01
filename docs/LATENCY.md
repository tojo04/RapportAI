# Latency and controlled load

The primary application metric is precisely **backend receipt of a finalized transcript segment → delivery of a coaching suggestion to the outbound queue**, measured with the same process monotonic clock. It is not microphone speech-end latency. Speech-end latency is unavailable because this build has no validated VAD boundary mapped to the backend clock.

Engineering targets (not measured guarantees): p50 under 1.5 s and p95 under 3 s for final-to-suggestion under one-worker demo load. The bounded registry also exposes errors, active calls, queue depth, finals, and suggestions without logging transcript/audio content or secrets.

## Recorded fake benchmark

The deterministic benchmark uses simulated fake-provider durations and no DB, Redis, network, microphone, or model call. It validates measurement math only. On 2026-09-30, 100 samples on Windows 11/Python 3.14.3 produced p50 **43.66 ms** and p95 **76.44 ms** (rerun output is the source of truth). This is not real application latency or AI quality.

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.benchmark_replay --samples 100
```

Real load/latency evaluation remains opt-in because it requires running services and potentially billable providers. Test two concurrent calls, slow classification/DB/Redis, queue saturation, timeouts, and repeated start/stop; record exact hardware, models, sample count, errors, and percentiles rather than claiming subsecond performance.
