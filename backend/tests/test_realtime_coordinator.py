import asyncio

import pytest

from app.realtime.coordinator import (
    LiveCoordinatorError,
    LiveTranscriptionCoordinator,
)
from app.services.streaming_transcription import (
    FakeStreamingTranscriber,
    TranscriptEvent,
)


def final_event(segment_id: str, order: int, text: str) -> TranscriptEvent:
    return TranscriptEvent(
        kind="final",
        segment_id=segment_id,
        order=order,
        revision=2,
        text=text,
        provider_event_id=f"event-{segment_id}",
        provider_item_id=segment_id,
    )


def make_coordinator(
    fake: FakeStreamingTranscriber,
    emitted: list[object],
    *,
    queue_size: int = 4,
    queue_timeout: float = 0.05,
    finalization_timeout: float = 0.1,
) -> LiveTranscriptionCoordinator:
    sequence = 0

    async def next_sequence() -> int:
        nonlocal sequence
        sequence += 1
        return sequence

    async def sink(event: object) -> None:
        emitted.append(event)

    return LiveTranscriptionCoordinator(
        call_id="call-1",
        transcriber=fake,
        event_sink=sink,
        next_sequence=next_sequence,
        queue_size=queue_size,
        queue_timeout_seconds=queue_timeout,
        finalization_timeout_seconds=finalization_timeout,
    )


def test_stop_drains_audio_and_accepts_final_arriving_while_stopping() -> None:
    async def scenario() -> tuple[bool, list[object], FakeStreamingTranscriber]:
        fake = FakeStreamingTranscriber()
        emitted: list[object] = []
        coordinator = make_coordinator(fake, emitted)
        await coordinator.start()
        await coordinator.accept_audio(b"\x01\x00" * 100)
        stop_task = asyncio.create_task(coordinator.stop())
        while fake.commits == 0:
            await asyncio.sleep(0)
        await fake.emit(final_event("item-1", 0, "Last word retained"))
        complete = await stop_task
        return complete, emitted, fake

    complete, emitted, fake = asyncio.run(scenario())
    assert complete is True
    assert [event.payload.text for event in emitted] == ["Last word retained"]
    assert fake.closed is True


def test_duplicate_stop_is_idempotent_and_missing_completion_is_incomplete() -> None:
    async def scenario() -> tuple[bool, bool, int]:
        fake = FakeStreamingTranscriber()
        coordinator = make_coordinator(
            fake,
            [],
            finalization_timeout=0.01,
        )
        await coordinator.start()
        await coordinator.accept_audio(b"\x01\x00")
        first = await coordinator.stop()
        second = await coordinator.stop()
        return first, second, fake.commits

    first, second, commits = asyncio.run(scenario())
    assert first is second is False
    assert commits == 1


def test_empty_call_finishes_without_an_empty_provider_commit() -> None:
    async def scenario() -> tuple[bool, int]:
        fake = FakeStreamingTranscriber()
        coordinator = make_coordinator(fake, [])
        await coordinator.start()
        complete = await coordinator.stop()
        return complete, fake.commits

    assert asyncio.run(scenario()) == (True, 0)


def test_partial_is_replaced_by_final_and_finals_keep_audio_order() -> None:
    async def scenario() -> list[object]:
        fake = FakeStreamingTranscriber()
        emitted: list[object] = []
        coordinator = make_coordinator(fake, emitted)
        await coordinator.start()
        await fake.emit(
            TranscriptEvent(
                kind="partial",
                segment_id="item-2",
                order=1,
                revision=1,
                text="Sec",
                provider_event_id="partial-2",
                provider_item_id="item-2",
            )
        )
        await fake.emit(final_event("item-2", 1, "Second"))
        await fake.emit(final_event("item-1", 0, "First"))
        while len(emitted) < 3:
            await asyncio.sleep(0)
        await coordinator.interrupt()
        return emitted

    emitted = asyncio.run(scenario())
    assert [event.type for event in emitted] == [
        "transcript.partial",
        "transcript.final",
        "transcript.final",
    ]
    ordered_finals = sorted(
        (event for event in emitted if event.type == "transcript.final"),
        key=lambda event: event.payload.order,
    )
    assert [event.payload.text for event in ordered_finals] == ["First", "Second"]
    assert all(event.payload.speaker_role == "unknown" for event in emitted)


def test_audio_queue_saturation_is_explicit() -> None:
    class SlowFake(FakeStreamingTranscriber):
        async def send_audio(self, pcm: bytes) -> None:
            await asyncio.sleep(1)
            await super().send_audio(pcm)

    async def scenario() -> None:
        coordinator = make_coordinator(
            SlowFake(),
            [],
            queue_size=1,
            queue_timeout=0.001,
        )
        await coordinator.start()
        await coordinator.accept_audio(b"\x01\x00")
        await asyncio.sleep(0)
        await coordinator.accept_audio(b"\x02\x00")
        with pytest.raises(LiveCoordinatorError, match="queue is full"):
            await coordinator.accept_audio(b"\x03\x00")
        await coordinator.interrupt()

    asyncio.run(scenario())


def test_two_calls_keep_audio_and_transcripts_isolated() -> None:
    async def scenario() -> tuple[list[object], list[object]]:
        first_fake = FakeStreamingTranscriber()
        second_fake = FakeStreamingTranscriber()
        first_events: list[object] = []
        second_events: list[object] = []
        first = make_coordinator(first_fake, first_events)
        second = make_coordinator(second_fake, second_events)
        await asyncio.gather(first.start(), second.start())
        await first_fake.emit(final_event("first", 0, "Call one"))
        await second_fake.emit(final_event("second", 0, "Call two"))
        while not first_events or not second_events:
            await asyncio.sleep(0)
        await asyncio.gather(first.interrupt(), second.interrupt())
        return first_events, second_events

    first, second = asyncio.run(scenario())
    assert [event.payload.text for event in first] == ["Call one"]
    assert [event.payload.text for event in second] == ["Call two"]
