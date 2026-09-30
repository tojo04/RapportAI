from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.realtime.transcript_pipeline import TranscriptProjector, TranscriptServerEvent
from app.services.streaming_transcription import (
    StreamingTranscriber,
    StreamingTranscriptionError,
    TranscriptEvent,
)
from app.services.sales_detection import DetectionSegment, LiveSalesDetector


class LiveCoordinatorError(RuntimeError):
    pass


EventSink = Callable[[TranscriptServerEvent], Awaitable[None]]


class LiveTranscriptionCoordinator:
    """Own bounded per-call provider IO and transcript processing tasks."""

    def __init__(
        self,
        *,
        call_id: str,
        transcriber: StreamingTranscriber,
        event_sink: EventSink,
        next_sequence: Callable[[], Awaitable[int]],
        queue_size: int,
        queue_timeout_seconds: float,
        finalization_timeout_seconds: float,
        sales_detector: LiveSalesDetector | None = None,
    ) -> None:
        self._call_id = call_id
        self._transcriber = transcriber
        self._event_sink = event_sink
        self._next_sequence = next_sequence
        self._queue_timeout = queue_timeout_seconds
        self._finalization_timeout = finalization_timeout_seconds
        self._sales_detector = sales_detector
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(queue_size)
        self._transcript_queue: asyncio.Queue[TranscriptEvent | None] = (
            asyncio.Queue(queue_size)
        )
        self._semantic_queue: asyncio.Queue[TranscriptEvent | None] = (
            asyncio.Queue(queue_size)
        )
        self._tasks: list[asyncio.Task[None]] = []
        self._accepting_audio = False
        self._closed = False
        self._stop_lock = asyncio.Lock()
        self._stop_result: bool | None = None
        self._event_changed = asyncio.Event()
        self._partial_ids: set[str] = set()
        self._final_ids: set[str] = set()
        self._projector = TranscriptProjector(call_id)
        self.failure: StreamingTranscriptionError | None = None

    async def start(self) -> None:
        await self._transcriber.connect()
        if self._sales_detector is not None:
            await self._sales_detector.start()
        self._accepting_audio = True
        self._tasks = [
            asyncio.create_task(self._audio_worker(), name=f"audio-{self._call_id}"),
            asyncio.create_task(
                self._provider_reader(), name=f"provider-{self._call_id}"
            ),
            asyncio.create_task(
                self._transcript_worker(), name=f"transcript-{self._call_id}"
            ),
            asyncio.create_task(
                self._semantic_worker(), name=f"semantic-{self._call_id}"
            ),
        ]

    async def accept_audio(self, frame: bytes) -> None:
        if not self._accepting_audio or self._closed:
            raise LiveCoordinatorError("The transcription stream is not accepting audio.")
        if self.failure is not None:
            raise LiveCoordinatorError(str(self.failure))
        try:
            await asyncio.wait_for(
                self._audio_queue.put(frame),
                timeout=self._queue_timeout,
            )
        except TimeoutError as exc:
            raise LiveCoordinatorError("The transcription audio queue is full.") from exc

    async def stop(self) -> bool:
        async with self._stop_lock:
            if self._stop_result is not None:
                return self._stop_result
            self._accepting_audio = False
            complete = True
            try:
                await asyncio.wait_for(
                    self._audio_queue.join(), timeout=self._finalization_timeout
                )
                await self._transcriber.flush()
                await self._wait_for_finals()
                await asyncio.wait_for(
                    self._semantic_queue.join(),
                    timeout=self._finalization_timeout,
                )
                if self._sales_detector is not None:
                    await asyncio.wait_for(
                        self._sales_detector.flush(),
                        timeout=self._finalization_timeout,
                    )
            except (TimeoutError, StreamingTranscriptionError):
                complete = False
            if self.failure is not None:
                complete = False
            await self._shutdown()
            self._stop_result = complete
            return complete

    async def interrupt(self) -> None:
        if not self._closed:
            await self.stop()

    async def _wait_for_finals(self) -> None:
        async def finalized() -> None:
            while self._partial_ids or self._transcriber.pending_final_count > 0:
                self._event_changed.clear()
                await self._event_changed.wait()

        await asyncio.wait_for(finalized(), timeout=self._finalization_timeout)

    async def _audio_worker(self) -> None:
        while True:
            frame = await self._audio_queue.get()
            try:
                if frame is None:
                    return
                await self._transcriber.send_audio(frame)
            except StreamingTranscriptionError as exc:
                self.failure = exc
                self._event_changed.set()
            finally:
                self._audio_queue.task_done()

    async def _provider_reader(self) -> None:
        try:
            async for event in self._transcriber.events():
                await asyncio.wait_for(
                    self._transcript_queue.put(event),
                    timeout=self._queue_timeout,
                )
        except asyncio.CancelledError:
            raise
        except (TimeoutError, StreamingTranscriptionError) as exc:
            self.failure = StreamingTranscriptionError(str(exc))
            self._event_changed.set()

    async def _transcript_worker(self) -> None:
        while True:
            event = await self._transcript_queue.get()
            try:
                if event is None:
                    return
                if event.kind == "partial":
                    self._partial_ids.add(event.segment_id)
                else:
                    if event.segment_id in self._final_ids:
                        continue
                    self._partial_ids.discard(event.segment_id)
                    self._final_ids.add(event.segment_id)
                outgoing = await self._projector.project(
                    event,
                    self._next_sequence,
                )
                if outgoing is None:
                    continue
                await self._event_sink(outgoing)
                self._event_changed.set()
                if event.kind == "final":
                    try:
                        self._semantic_queue.put_nowait(event)
                    except asyncio.QueueFull:
                        # Semantic work is optional at this stage. A saturated
                        # future classifier queue must never delay a final.
                        pass
            except (TimeoutError, RuntimeError):
                self.failure = StreamingTranscriptionError(
                    "The transcript processing queue is overloaded."
                )
                self._event_changed.set()
            finally:
                self._transcript_queue.task_done()

    async def _semantic_worker(self) -> None:
        while True:
            event = await self._semantic_queue.get()
            try:
                if event is None:
                    return
                if self._sales_detector is not None:
                    await self._sales_detector.submit(
                        DetectionSegment(
                            segment_id=event.segment_id,
                            order=event.order,
                            text=event.text,
                        )
                    )
            finally:
                self._semantic_queue.task_done()

    async def _shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._sales_detector is not None:
            await self._sales_detector.close()
        await self._transcriber.close()
        for queue in (self._audio_queue, self._transcript_queue, self._semantic_queue):
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
