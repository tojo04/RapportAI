from __future__ import annotations

import asyncio
import base64
import sys
from array import array
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from openai import AsyncOpenAI


TranscriptEventKind = Literal["partial", "final"]


class StreamingTranscriptionError(RuntimeError):
    """A sanitized error safe to expose to the live-call coordinator."""


@dataclass(frozen=True)
class TranscriptEvent:
    kind: TranscriptEventKind
    segment_id: str
    order: int
    revision: int
    text: str
    provider_event_id: str
    provider_item_id: str
    previous_item_id: str | None = None
    language: str | None = None


class StreamingTranscriber(Protocol):
    async def connect(self) -> None: ...

    async def send_audio(self, pcm: bytes) -> None: ...

    async def finish_turn(self) -> bool: ...

    async def flush(self) -> bool: ...

    def events(self) -> AsyncIterator[TranscriptEvent]: ...

    async def close(self) -> None: ...


class PcmEndpointDetector:
    """Detect a simple speech-to-silence boundary in 24 kHz PCM16LE audio."""

    def __init__(
        self,
        *,
        sample_rate_hz: int = 24_000,
        silence_ms: float = 700,
        speech_amplitude: int = 500,
    ) -> None:
        self._sample_rate_hz = sample_rate_hz
        self._silence_ms_limit = silence_ms
        self._speech_amplitude = speech_amplitude
        self._silence_ms = 0.0
        self._has_speech = False

    @property
    def has_speech(self) -> bool:
        return self._has_speech

    def accept(self, pcm: bytes) -> tuple[bool, bool]:
        """Return (should_send, should_commit) for a complete PCM frame."""

        if not pcm or len(pcm) % 2:
            raise ValueError("PCM audio must contain complete 16-bit samples.")
        samples = array("h")
        samples.frombytes(pcm)
        if sys.byteorder != "little":
            samples.byteswap()
        speech = max((abs(sample) for sample in samples), default=0) >= (
            self._speech_amplitude
        )
        duration_ms = len(samples) * 1_000 / self._sample_rate_hz

        if speech:
            self._has_speech = True
            self._silence_ms = 0.0
        elif self._has_speech:
            self._silence_ms += duration_ms

        should_send = self._has_speech
        should_commit = self._has_speech and (
            self._silence_ms >= self._silence_ms_limit
        )
        return should_send, should_commit

    def finish_turn(self) -> bool:
        should_commit = self._has_speech
        self.reset()
        return should_commit

    def reset(self) -> None:
        self._silence_ms = 0.0
        self._has_speech = False


class OpenAIStreamingTranscriber:
    """OpenAI Realtime transcription adapter with explicit local endpointing."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-live-transcribe",
        client: Any | None = None,
        endpoint_detector: PcmEndpointDetector | None = None,
        operation_timeout_seconds: float = 10.0,
    ) -> None:
        if not api_key.strip():
            raise StreamingTranscriptionError(
                "Streaming transcription is not configured."
            )
        self._client = client or AsyncOpenAI(api_key=api_key)
        self._model = model
        self._detector = endpoint_detector or PcmEndpointDetector()
        self._operation_timeout_seconds = operation_timeout_seconds
        self._manager: Any | None = None
        self._connection: Any | None = None
        self._closed = False
        self._partial_text: dict[str, str] = {}
        self._revisions: dict[str, int] = {}
        self._orders: dict[str, int] = {}
        self._previous_items: dict[str, str | None] = {}
        self._finalized: set[str] = set()

    async def connect(self) -> None:
        if self._connection is not None:
            return
        try:
            self._manager = self._client.realtime.connect(
                model=self._model,
                max_retries=0,
            )
            self._connection = await asyncio.wait_for(
                self._manager.__aenter__(),
                timeout=self._operation_timeout_seconds,
            )
            await self._timed(
                self._connection.session.update(
                    session={
                        "type": "transcription",
                        "audio": {
                            "input": {
                                "format": {
                                    "type": "audio/pcm",
                                    "rate": 24_000,
                                },
                                "transcription": {"model": self._model},
                                "turn_detection": None,
                            }
                        },
                    }
                )
            )
        except TimeoutError as exc:
            await self.close()
            raise StreamingTranscriptionError(
                "Streaming transcription connection timed out."
            ) from exc
        except Exception as exc:
            await self.close()
            raise StreamingTranscriptionError(
                "Streaming transcription could not connect."
            ) from exc

    async def send_audio(self, pcm: bytes) -> None:
        connection = self._require_connection()
        try:
            should_send, should_commit = self._detector.accept(pcm)
            if not should_send:
                return
            encoded = base64.b64encode(pcm).decode("ascii")
            await self._timed(
                connection.input_audio_buffer.append(audio=encoded)
            )
            if should_commit:
                await self._commit()
        except ValueError:
            raise
        except TimeoutError as exc:
            raise StreamingTranscriptionError(
                "Streaming transcription timed out while sending audio."
            ) from exc
        except Exception as exc:
            raise StreamingTranscriptionError(
                "Streaming transcription rejected audio."
            ) from exc

    async def finish_turn(self) -> bool:
        self._require_connection()
        if not self._detector.finish_turn():
            return False
        await self._commit(reset_detector=False)
        return True

    async def flush(self) -> bool:
        return await self.finish_turn()

    async def _commit(self, *, reset_detector: bool = True) -> None:
        connection = self._require_connection()
        try:
            await self._timed(connection.input_audio_buffer.commit())
        except TimeoutError as exc:
            raise StreamingTranscriptionError(
                "Streaming transcription turn commit timed out."
            ) from exc
        except Exception as exc:
            raise StreamingTranscriptionError(
                "Streaming transcription could not finish the audio turn."
            ) from exc
        finally:
            if reset_detector:
                self._detector.reset()

    async def _timed(self, operation: Any) -> Any:
        return await asyncio.wait_for(
            operation,
            timeout=self._operation_timeout_seconds,
        )

    async def events(self) -> AsyncIterator[TranscriptEvent]:
        connection = self._require_connection()
        try:
            async for event in connection:
                normalized = self._normalize_event(event)
                if normalized is not None:
                    yield normalized
        except asyncio.CancelledError:
            raise
        except StreamingTranscriptionError:
            raise
        except Exception as exc:
            raise StreamingTranscriptionError(
                "Streaming transcription provider failed."
            ) from exc

    def _normalize_event(self, event: Any) -> TranscriptEvent | None:
        event_type = _field(event, "type")
        if event_type == "error":
            raise StreamingTranscriptionError(
                "Streaming transcription provider failed."
            )
        if event_type == "input_audio_buffer.committed":
            item_id = _required_text(event, "item_id")
            previous = _field(event, "previous_item_id")
            self._previous_items[item_id] = (
                previous if isinstance(previous, str) else None
            )
            self._ensure_order(item_id)
            return None
        if event_type not in {
            "conversation.item.input_audio_transcription.delta",
            "conversation.item.input_audio_transcription.completed",
        }:
            return None

        item_id = _required_text(event, "item_id")
        if item_id in self._finalized:
            return None
        order = self._ensure_order(item_id)
        self._revisions[item_id] = self._revisions.get(item_id, 0) + 1

        if event_type.endswith(".delta"):
            delta = _field(event, "delta")
            if not isinstance(delta, str) or not delta:
                return None
            text = self._partial_text.get(item_id, "") + delta
            self._partial_text[item_id] = text
            kind: TranscriptEventKind = "partial"
        else:
            transcript = _field(event, "transcript")
            if not isinstance(transcript, str) or not transcript.strip():
                return None
            text = transcript.strip()
            self._partial_text.pop(item_id, None)
            self._finalized.add(item_id)
            kind = "final"

        return TranscriptEvent(
            kind=kind,
            segment_id=item_id,
            order=order,
            revision=self._revisions[item_id],
            text=text,
            provider_event_id=_required_text(event, "event_id"),
            provider_item_id=item_id,
            previous_item_id=self._previous_items.get(item_id),
            language=None,
        )

    def _ensure_order(self, item_id: str) -> int:
        existing = self._orders.get(item_id)
        if existing is not None:
            return existing
        previous = self._previous_items.get(item_id)
        previous_order = self._orders.get(previous) if previous else None
        order = (
            previous_order + 1
            if previous_order is not None
            else max(self._orders.values(), default=-1) + 1
        )
        self._orders[item_id] = order
        return order

    def _require_connection(self) -> Any:
        if self._connection is None or self._closed:
            raise StreamingTranscriptionError(
                "Streaming transcription is not connected."
            )
        return self._connection

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        manager = self._manager
        self._manager = None
        self._connection = None
        if manager is not None:
            try:
                await manager.__aexit__(None, None, None)
            except Exception:
                pass


class FakeStreamingTranscriber:
    """Deterministic no-network transcriber used by orchestration tests."""

    def __init__(self) -> None:
        self.audio_frames: list[bytes] = []
        self.commits = 0
        self.connected = False
        self.closed = False
        self._pending_audio = False
        self._events: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()

    async def connect(self) -> None:
        self.connected = True

    async def send_audio(self, pcm: bytes) -> None:
        if not self.connected or self.closed:
            raise StreamingTranscriptionError("Fake transcriber is not connected.")
        self.audio_frames.append(pcm)
        self._pending_audio = True

    async def finish_turn(self) -> bool:
        if not self._pending_audio:
            return False
        self.commits += 1
        self._pending_audio = False
        return True

    async def flush(self) -> bool:
        return await self.finish_turn()

    async def emit(self, event: TranscriptEvent) -> None:
        await self._events.put(event)

    async def events(self) -> AsyncIterator[TranscriptEvent]:
        while True:
            event = await self._events.get()
            try:
                if event is None:
                    return
                yield event
            finally:
                self._events.task_done()

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        await self._events.put(None)


def _field(event: Any, name: str) -> Any:
    if isinstance(event, dict):
        return event.get(name)
    return getattr(event, name, None)


def _required_text(event: Any, name: str) -> str:
    value = _field(event, name)
    if not isinstance(value, str) or not value:
        raise StreamingTranscriptionError(
            "Streaming transcription returned a malformed event."
        )
    return value
