from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.models.realtime import TranscriptFinalEvent, TranscriptPartialEvent, TranscriptPayload
from app.services.streaming_transcription import TranscriptEvent


TranscriptServerEvent = TranscriptPartialEvent | TranscriptFinalEvent


class TranscriptProjector:
    """Project normalized provider events into deduplicated protocol events."""

    def __init__(self, call_id: str) -> None:
        self._call_id = call_id
        self._finalized: set[str] = set()
        self._revisions: dict[str, int] = {}

    async def project(
        self,
        event: TranscriptEvent,
        next_sequence: Callable[[], Awaitable[int]],
    ) -> TranscriptServerEvent | None:
        previous_revision = self._revisions.get(event.segment_id, 0)
        if event.segment_id in self._finalized or event.revision <= previous_revision:
            return None
        self._revisions[event.segment_id] = event.revision
        payload = TranscriptPayload(
            segment_id=event.segment_id,
            order=event.order,
            revision=event.revision,
            text=event.text,
            speaker_id=None,
            speaker_role="unknown",
            start_ms=None,
            end_ms=None,
            language=event.language,
        )
        if event.kind == "partial":
            return TranscriptPartialEvent(
                call_id=self._call_id,
                seq=await next_sequence(),
                payload=payload,
            )
        self._finalized.add(event.segment_id)
        return TranscriptFinalEvent(
            call_id=self._call_id,
            seq=await next_sequence(),
            payload=payload,
        )
