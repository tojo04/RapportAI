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
