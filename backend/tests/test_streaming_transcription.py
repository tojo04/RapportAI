import asyncio
import base64
from array import array
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services.streaming_transcription import (
    FakeStreamingTranscriber,
    OpenAIStreamingTranscriber,
    PcmEndpointDetector,
    StreamingTranscriptionError,
    TranscriptEvent,
)


def pcm_frame(amplitude: int, samples: int = 2_400) -> bytes:
    return array("h", [amplitude] * samples).tobytes()


class FakeProviderConnection:
    def __init__(self, events: list[dict[str, object]] | None = None) -> None:
        self.session = SimpleNamespace(update=AsyncMock())
        self.input_audio_buffer = SimpleNamespace(
            append=AsyncMock(),
            commit=AsyncMock(),
        )
        self._events = events or []

    async def __aiter__(self) -> AsyncIterator[dict[str, object]]:
        for event in self._events:
            yield event


class FakeConnectionManager:
    def __init__(self, connection: FakeProviderConnection) -> None:
        self.connection = connection
        self.entered = 0
        self.exited = 0

    async def __aenter__(self) -> FakeProviderConnection:
        self.entered += 1
        return self.connection

    async def __aexit__(self, *_args: object) -> None:
        self.exited += 1


def adapter_with(
    connection: FakeProviderConnection,
    *,
    timeout: float = 1,
) -> tuple[OpenAIStreamingTranscriber, FakeConnectionManager, Mock]:
    manager = FakeConnectionManager(connection)
    realtime = SimpleNamespace(connect=Mock(return_value=manager))
    client = SimpleNamespace(realtime=realtime)
    adapter = OpenAIStreamingTranscriber(
        api_key="test-key",
        client=client,
        operation_timeout_seconds=timeout,
    )
    return adapter, manager, realtime.connect


def test_endpoint_detector_ignores_silence_and_commits_after_speech_pause() -> None:
    detector = PcmEndpointDetector(silence_ms=300)
    assert detector.accept(pcm_frame(0)) == (False, False)
    assert detector.accept(pcm_frame(1_000)) == (True, False)
    assert detector.accept(pcm_frame(0)) == (True, False)
    assert detector.accept(pcm_frame(0)) == (True, False)
    assert detector.accept(pcm_frame(0)) == (True, True)


def test_continuous_speech_and_final_flush_use_explicit_commits() -> None:
    async def scenario() -> None:
        connection = FakeProviderConnection()
        adapter, manager, connect = adapter_with(connection)
        await adapter.connect()
        for _ in range(10):
            await adapter.send_audio(pcm_frame(2_000))

        connection.input_audio_buffer.commit.assert_not_awaited()
        assert await adapter.flush() is True
        connection.input_audio_buffer.commit.assert_awaited_once()
        assert await adapter.flush() is False
        assert connection.input_audio_buffer.append.await_count == 10
        encoded = connection.input_audio_buffer.append.await_args_list[0].kwargs[
            "audio"
        ]
        assert base64.b64decode(encoded) == pcm_frame(2_000)
        connect.assert_called_once_with(
            model="gpt-live-transcribe",
            max_retries=0,
        )
        session = connection.session.update.await_args.kwargs["session"]
        assert session["type"] == "transcription"
        assert session["audio"]["input"]["format"] == {
            "type": "audio/pcm",
            "rate": 24_000,
        }
        assert session["audio"]["input"]["turn_detection"] is None
        await adapter.close()
        assert manager.exited == 1

    asyncio.run(scenario())


def test_deltas_and_out_of_order_duplicate_finals_are_normalized() -> None:
    async def scenario() -> list[TranscriptEvent]:
        events: list[dict[str, object]] = [
            {
                "type": "input_audio_buffer.committed",
                "event_id": "commit-1",
                "item_id": "item-1",
                "previous_item_id": None,
            },
            {
                "type": "input_audio_buffer.committed",
                "event_id": "commit-2",
                "item_id": "item-2",
                "previous_item_id": "item-1",
            },
            {
                "type": "conversation.item.input_audio_transcription.delta",
                "event_id": "delta-2a",
                "item_id": "item-2",
                "delta": "Second ",
            },
            {
                "type": "conversation.item.input_audio_transcription.delta",
                "event_id": "delta-2b",
                "item_id": "item-2",
                "delta": "turn",
            },
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "event_id": "final-2",
                "item_id": "item-2",
                "transcript": "Second turn",
            },
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "event_id": "final-2-duplicate",
                "item_id": "item-2",
                "transcript": "Second turn",
            },
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "event_id": "final-1",
                "item_id": "item-1",
                "transcript": "First turn",
            },
        ]
        connection = FakeProviderConnection(events)
        adapter, _, _ = adapter_with(connection)
        await adapter.connect()
        return [event async for event in adapter.events()]

    normalized = asyncio.run(scenario())
    assert [(event.kind, event.text) for event in normalized] == [
        ("partial", "Second "),
        ("partial", "Second turn"),
        ("final", "Second turn"),
        ("final", "First turn"),
    ]
    assert [event.order for event in normalized] == [1, 1, 1, 0]
    assert normalized[2].previous_item_id == "item-1"


def test_provider_failure_and_timeout_are_sanitized() -> None:
    async def provider_error() -> None:
        connection = FakeProviderConnection(
            [{"type": "error", "error": {"message": "secret provider text"}}]
        )
        adapter, _, _ = adapter_with(connection)
        await adapter.connect()
        with pytest.raises(StreamingTranscriptionError) as caught:
            await anext(adapter.events())
        assert "secret provider text" not in str(caught.value)

    async def provider_timeout() -> None:
        connection = FakeProviderConnection()

        async def slow_append(**_kwargs: object) -> None:
            await asyncio.sleep(0.1)

        connection.input_audio_buffer.append.side_effect = slow_append
        adapter, _, _ = adapter_with(connection, timeout=0.001)
        await adapter.connect()
        with pytest.raises(StreamingTranscriptionError, match="timed out"):
            await adapter.send_audio(pcm_frame(1_000))

    asyncio.run(provider_error())
    asyncio.run(provider_timeout())


def test_fake_transcriber_is_deterministic_and_closes_event_stream() -> None:
    async def scenario() -> list[TranscriptEvent]:
        fake = FakeStreamingTranscriber()
        event = TranscriptEvent(
            kind="final",
            segment_id="segment-1",
            order=0,
            revision=1,
            text="Test transcript",
            provider_event_id="event-1",
            provider_item_id="item-1",
        )
        await fake.connect()
        await fake.send_audio(pcm_frame(1_000))
        assert await fake.finish_turn() is True
        assert await fake.finish_turn() is False
        await fake.emit(event)
        await fake.close()
        received = [item async for item in fake.events()]
        assert fake.audio_frames == [pcm_frame(1_000)]
        assert fake.commits == 1
        return received

    assert asyncio.run(scenario())[0].text == "Test transcript"
