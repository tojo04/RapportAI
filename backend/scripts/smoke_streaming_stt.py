"""Opt-in paid smoke test for a consented raw PCM16LE 24 kHz mono file."""

import argparse
import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.services.streaming_transcription import OpenAIStreamingTranscriber


async def transcribe(path: Path) -> None:
    settings = get_settings()
    if settings.openai_api_key is None:
        raise SystemExit("Set OPENAI_API_KEY in backend/.env first.")
    audio = path.read_bytes()
    if not audio or len(audio) % 2:
        raise SystemExit("Input must be non-empty aligned PCM16LE audio.")

    transcriber = OpenAIStreamingTranscriber(
        api_key=settings.openai_api_key,
        model=settings.live_stt_model,
    )
    await transcriber.connect()
    try:
        for offset in range(0, len(audio), 4_800):
            await transcriber.send_audio(audio[offset : offset + 4_800])
        committed = await transcriber.flush()
        if not committed:
            raise SystemExit("No speech crossed the local endpoint threshold.")

        events = transcriber.events()
        while True:
            event = await asyncio.wait_for(anext(events), timeout=15)
            print(f"{event.kind}: {event.text}")
            if event.kind == "final":
                return
    finally:
        await transcriber.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pcm_file", type=Path)
    args = parser.parse_args()
    asyncio.run(transcribe(args.pcm_file))


if __name__ == "__main__":
    main()
