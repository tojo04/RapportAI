from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.realtime import ServerEvent
from app.realtime.transcript_pipeline import TranscriptProjector
from app.services.streaming_transcription import TranscriptEvent


class ReplayStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["partial", "final"]
    segment_id: str = Field(min_length=1)
    order: int = Field(ge=0)
    revision: int = Field(ge=1)
    text: str
    delay_ms: int = Field(default=0, ge=0)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    language: str | None = None


class ReplayFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str
    steps: list[ReplayStep]
    expected_sales_signals: list[
        Literal[
            "question",
            "objection",
            "competitor",
            "pricing",
            "buying_signal",
            "requirement",
        ]
    ]


def load_replay_fixture(path: Path) -> ReplayFixture:
    return ReplayFixture.model_validate(json.loads(path.read_text(encoding="utf-8")))


async def replay_fixture(
    fixture: ReplayFixture,
    *,
    call_id: str = "replay-call",
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> list[ServerEvent]:
    sequence = 0

    async def next_sequence() -> int:
        nonlocal sequence
        sequence += 1
        return sequence

    projector = TranscriptProjector(call_id)
    emitted: list[ServerEvent] = []
    for index, step in enumerate(fixture.steps):
        if step.delay_ms:
            await sleep(step.delay_ms / 1_000)
        event = await projector.project(
            TranscriptEvent(
                kind=step.kind,
                segment_id=step.segment_id,
                order=step.order,
                revision=step.revision,
                text=step.text,
                provider_event_id=f"replay-{index}",
                provider_item_id=step.segment_id,
                language=step.language,
            ),
            next_sequence,
        )
        if event is not None:
            if step.start_ms is not None or step.end_ms is not None:
                event.payload.start_ms = step.start_ms
                event.payload.end_ms = step.end_ms
            emitted.append(event)
    return emitted
