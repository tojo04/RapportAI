# Streaming transcription provider contract

## Verified baseline

Checked 2026-09-30 against the official OpenAI Realtime transcription guide:
https://developers.openai.com/api/docs/guides/realtime-transcription#create-a-transcription-session

RapportAI targets a transcription session with configurable model default
`gpt-live-transcribe`. Its browser/backend audio contract is raw signed 16-bit
little-endian PCM, 24,000 Hz, mono. The browser groups approximately 100 ms
(2,400 samples / 4,800 bytes) per WebSocket frame and flushes a shorter final
sample-aligned frame on stop.

The official example configures `audio.input.format` as `audio/pcm` at rate
24,000. It also states that `gpt-live-transcribe` does not support `server_vad`
or `semantic_vad`; `turn_detection` must be omitted or `null`. RapportAI will
therefore use explicit, server-controlled input-buffer commits in the initial
adapter rather than claiming provider VAD support.

## Browser conversion

AudioWorklet mixes available input channels to mono. The main-thread encoder
uses the actual `AudioContext.sampleRate`, maintains interpolation and framing
state across worklet blocks, clips floats to [-1, 1], and writes PCM samples in
little-endian order. Duration tests cover 44.1 kHz and 48 kHz input.

## Verification boundary

Task 3 tests the deterministic encoding and transport contract only. It makes
no paid API call. Browser microphone/device compatibility remains a manual
check; provider event compatibility is implemented and mocked in Task 4.

## Task 4 adapter contract

The implementation was checked against installed `openai` Python SDK 2.52.0.
It uses `AsyncOpenAI.realtime.connect`, `session.update`,
`input_audio_buffer.append`, and `input_audio_buffer.commit`. Automatic SDK
reconnect is disabled so RapportAI never replays ambiguous audio after a lost
provider connection.

The adapter exposes `connect`, `send_audio`, `finish_turn`/`flush`, `events`,
and `close`. It normalizes provider delta/completed events to stable segment
records, accumulates deltas into replacement partial text, ignores duplicate
finals, and retains `item_id`/`previous_item_id` so later orchestration can sort
finals even when completions arrive out of order. Provider details are not
included in client-safe errors.

Because `gpt-live-transcribe` has no supported provider VAD, a deliberately
simple local detector starts forwarding when PCM peak amplitude reaches 500 and
commits after 700 ms of silence. Continuous speech is committed by explicit
Stop/flush. These are development defaults, not calibrated speech-detection
quality claims.

### Opt-in paid smoke test

Prepare a short synthetic or consented raw PCM16LE 24 kHz mono file, set the
server-side key in `backend/.env`, then run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke_streaming_stt .\sample.pcm
```

This command incurs API usage and was not run automatically. Without it,
account/model access and real provider behavior remain unverified; all default
tests use mocks or the deterministic fake.

## Task 5 orchestration

Each active call owns one adapter and bounded audio, transcript, and semantic
queues. The WebSocket handler validates/counts PCM before enqueueing it. A
provider reader normalizes events, and a transcript worker emits protocol
partials/finals without waiting for future classification work.

Stop drains accepted audio, explicitly flushes the last nonempty turn, then
waits for the adapter's pending-final count and any visible partials to clear.
The wait is bounded by `LIVE_STT_FINALIZATION_TIMEOUT_MS` (2 seconds by
default). Missing completion is represented as an interrupted call with
`transcript_complete: false`; it is never reported as successful finalization.
