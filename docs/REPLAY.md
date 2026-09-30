# Offline transcript replay

Replay feeds fictional transcript events through the same deduplication and
partial/final projection used by live provider events. It does not open a
microphone, transcribe audio, or contact OpenAI.

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m scripts.replay_transcript fixtures/replay/demo.json
```

The committed fixtures cover a multi-signal demo, a no-signal greeting, and
two separate repeated objections. Segment IDs and audio order are stable;
speaker roles remain `unknown`. Replay verifies application behavior only and
is not evidence of speech-to-text accuracy or model quality.
