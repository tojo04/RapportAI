"""Replay a fictional transcript fixture without microphone or AI services."""

import argparse
import asyncio
import json
from pathlib import Path

from app.realtime.replay import load_replay_fixture, replay_fixture


async def run(path: Path) -> None:
    fixture = load_replay_fixture(path)
    events = await replay_fixture(fixture)
    for event in events:
        print(json.dumps(event.model_dump(mode="json"), ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.fixture))


if __name__ == "__main__":
    main()
