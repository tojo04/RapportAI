import asyncio
import json
from time import monotonic
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, status
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings, get_settings
from app.models.realtime import (
    CLIENT_COMMAND_ADAPTER,
    PROTOCOL_VERSION,
    AudioAckEvent,
    AudioAckPayload,
    CallEndedEvent,
    CallEndedPayload,
    CallStartedEvent,
    CallStartedPayload,
    CallState,
    CallStoppingEvent,
    CallStoppingPayload,
    CoachSuggestionEvent,
    CoachSuggestionPayload,
    ClientCommand,
    CreateCallResponse,
    DiagnosticPayload,
    ErrorEvent,
    PingCommand,
    PongEvent,
    PongPayload,
    SalesEvent,
    SalesEventPayload,
    ServerEvent,
    SessionReadyEvent,
    SessionReadyPayload,
    StartCommand,
    StopCommand,
    TranscriptFinalEvent,
    WarningEvent,
    LiveTransportLimits,
)
from app.realtime.sessions import (
    LiveCallAttachError,
    LiveCallCapacityError,
    LiveCallSession,
    LiveCallStore,
    OutboundItem,
)
from app.realtime.coordinator import (
    LiveCoordinatorError,
    LiveTranscriptionCoordinator,
)
from app.services.streaming_transcription import (
    OpenAIStreamingTranscriber,
    StreamingTranscriber,
    StreamingTranscriptionError,
)
from app.services.sales_detection import (
    LiveSalesDetector,
    OpenAISalesEventClassifier,
    SalesEventClassifier,
)
from app.services.coaching import CoachService, LiveCoach, OpenAICoachGenerator
from app.knowledge.ingestion import OpenAIEmbeddingProvider
from app.knowledge.retrieval import PostgresSearchBackend, RetrievalService
from app.storage.database import create_database_engine, create_session_factory
from app.storage.call_repository import CallRepository, PersistenceError


router = APIRouter()

UNKNOWN_CALL_CLOSE_CODE = 4404
ORIGIN_REJECTED_CLOSE_CODE = 4403
SESSION_UNAVAILABLE_CLOSE_CODE = 4409


class InvalidProtocolVersion(ValueError):
    """Raised when a client command uses an incompatible protocol version."""


def _live_call_store(websocket_or_request: Any) -> LiveCallStore:
    return websocket_or_request.app.state.live_call_store


@router.post(
    "/api/calls",
    response_model=CreateCallResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_live_call(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> CreateCallResponse:
    response = await _create_live_call_for_store(
        _live_call_store(request),
        settings,
    )
    repository: CallRepository | None = getattr(request.app.state, "call_repository", None)
    if repository is not None:
        try:
            await asyncio.to_thread(repository.create_call, response.call_id)
            session = await _live_call_store(request).get(response.call_id)
            if session is not None:
                async def persist(event: ServerEvent) -> None:
                    await asyncio.to_thread(repository.record_event, event)
                session.persistence_sink = persist
                runner = getattr(request.app.state, "live_analysis_runner", None)
                if runner is not None:
                    session.analysis_scheduler = runner.schedule
        except PersistenceError as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    session = await _live_call_store(request).get(response.call_id)
    context_store = getattr(request.app.state, "session_context_store", None)
    if session is not None and context_store is not None:
        session.context_store = context_store
        await context_store.start(response.call_id)
    return response


async def _create_live_call_for_store(
    store: LiveCallStore,
    settings: Settings,
) -> CreateCallResponse:
    try:
        session = await store.create()
    except LiveCallCapacityError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return CreateCallResponse(
        call_id=session.call_id,
        websocket_path=f"/ws/calls/{session.call_id}",
        limits=LiveTransportLimits(
            max_call_seconds=settings.live_max_call_seconds,
            max_frame_bytes=settings.live_max_audio_frame_bytes,
            ack_every_frames=settings.live_audio_ack_every_frames,
        ),
    )


async def _outbound_writer(
    websocket: WebSocket,
    queue: asyncio.Queue[OutboundItem],
) -> None:
    while True:
        event = await queue.get()
        try:
            if event is None:
                return
            await websocket.send_json(event.model_dump(mode="json"))
        finally:
            queue.task_done()


async def _enqueue(
    session: LiveCallSession,
    event: ServerEvent,
    settings: Settings,
) -> None:
    queue = session.outbound_queue
    if queue is None:
        raise RuntimeError("The live-call outbound queue is unavailable.")

    try:
        async with session.outbound_lock:
            event.seq = session.next_outbound_sequence()
            await asyncio.wait_for(
                queue.put(event),
                timeout=settings.live_queue_put_timeout_ms / 1_000,
            )
            if session.persistence_sink is not None:
                try:
                    await session.persistence_sink(event)
                except PersistenceError:
                    session.persistence_failed = True
            if isinstance(event, CallEndedEvent) and session.analysis_scheduler is not None:
                session.analysis_scheduler(session.call_id)
            if session.context_store is not None:
                if isinstance(event, TranscriptFinalEvent):
                    await session.context_store.append(session.call_id, event.payload.model_dump(mode="json"))
                elif isinstance(event, CallEndedEvent):
                    await session.context_store.finish(session.call_id)
    except TimeoutError as exc:
        async with session.lock:
            session.state = CallState.FAILED
        raise RuntimeError("The live-call outbound queue is overloaded.") from exc


async def _error_event(
    session: LiveCallSession,
    *,
    code: str,
    message: str,
    recoverable: bool,
    command_id: str | None = None,
) -> ErrorEvent:
    return ErrorEvent(
        call_id=session.call_id,
        seq=await session.next_sequence(),
        payload=DiagnosticPayload(
            code=code,
            message=message,
            recoverable=recoverable,
            command_id=command_id,
            state=session.state,
        ),
    )


def _parse_command(text: str) -> ClientCommand:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("The command is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("A command must be a JSON object.")
    supplied_version = payload.get("protocol_version")
    if "protocol_version" in payload and (
        type(supplied_version) is not int
        or supplied_version != PROTOCOL_VERSION
    ):
        raise InvalidProtocolVersion

    return CLIENT_COMMAND_ADAPTER.validate_python(payload)


async def _command_conflict(
    session: LiveCallSession,
    command_id: str,
) -> ErrorEvent:
    return await _error_event(
        session,
        code="command_id_conflict",
        message="The command ID was already used for another command type.",
        recoverable=True,
        command_id=command_id,
    )


async def _illegal_state(
    session: LiveCallSession,
    command_id: str,
    command_type: str,
) -> ErrorEvent:
    return await _error_event(
        session,
        code="illegal_state",
        message=f"The {command_type} command is not valid in this call state.",
        recoverable=True,
        command_id=command_id,
    )


async def _handle_start(
    session: LiveCallSession,
    command: StartCommand,
) -> ServerEvent:
    duplicate = False
    error_kind: str | None = None

    async with session.lock:
        previous_type = session.processed_commands.get(command.command_id)
        if previous_type is not None and previous_type != command.type:
            error_kind = "conflict"
        elif previous_type == command.type and session.state is CallState.LIVE:
            duplicate = True
        elif session.state is not CallState.CONNECTING:
            error_kind = "state"
        else:
            session.remember_command(command.command_id, command.type)
            session.state = CallState.LIVE
            audio = command.payload.audio
            session.mark_started(
                transport=audio.transport if audio is not None else None,
                sample_rate_hz=(
                    audio.sample_rate_hz if audio is not None else None
                ),
                channels=audio.channels if audio is not None else None,
                frame_duration_ms=(
                    audio.frame_duration_ms if audio is not None else None
                ),
            )

    if error_kind == "conflict":
        return await _command_conflict(session, command.command_id)
    if error_kind == "state":
        return await _illegal_state(session, command.command_id, command.type)

    return CallStartedEvent(
        call_id=session.call_id,
        seq=await session.next_sequence(),
        payload=CallStartedPayload(
            state=CallState.LIVE,
            command_id=command.command_id,
            duplicate=duplicate,
        ),
    )


async def _handle_stop(
    session: LiveCallSession,
    command: StopCommand,
    coordinator: LiveTranscriptionCoordinator | None = None,
    event_sink: Callable[[ServerEvent], Awaitable[None]] | None = None,
) -> list[ServerEvent]:
    duplicate = False
    error_kind: str | None = None

    async with session.lock:
        previous_type = session.processed_commands.get(command.command_id)
        if previous_type is not None and previous_type != command.type:
            error_kind = "conflict"
        elif session.state in {
            CallState.ENDED,
            CallState.INTERRUPTED,
            CallState.FAILED,
        }:
            if previous_type is None:
                session.remember_command(command.command_id, command.type)
            duplicate = True
        elif session.state not in {CallState.CONNECTING, CallState.LIVE}:
            error_kind = "state"
        else:
            session.remember_command(command.command_id, command.type)
            session.state = CallState.STOPPING

    if error_kind == "conflict":
        return [await _command_conflict(session, command.command_id)]
    if error_kind == "state":
        return [
            await _illegal_state(session, command.command_id, command.type)
        ]

    if duplicate:
        return [
            CallEndedEvent(
                call_id=session.call_id,
                seq=await session.next_sequence(),
                payload=CallEndedPayload(
                    state=session.state,
                    command_id=command.command_id,
                    duplicate=True,
                    transcript_complete=session.state is CallState.ENDED,
                ),
            )
        ]

    stopping_event = CallStoppingEvent(
        call_id=session.call_id,
        seq=await session.next_sequence(),
        payload=CallStoppingPayload(
            state=CallState.STOPPING,
            command_id=command.command_id,
        ),
    )
    if event_sink is not None:
        await event_sink(stopping_event)
    transcript_complete = True
    if coordinator is not None:
        transcript_complete = await coordinator.stop()
    async with session.lock:
        session.state = (
            CallState.ENDED
            if transcript_complete
            else CallState.INTERRUPTED
        )
    ended_event = CallEndedEvent(
        call_id=session.call_id,
        seq=await session.next_sequence(),
        payload=CallEndedPayload(
            state=session.state,
            command_id=command.command_id,
            transcript_complete=transcript_complete,
        ),
    )
    return [ended_event] if event_sink is not None else [stopping_event, ended_event]


async def _handle_ping(
    session: LiveCallSession,
    command: PingCommand,
) -> ServerEvent:
    duplicate = False
    conflict = False

    async with session.lock:
        previous_type = session.processed_commands.get(command.command_id)
        if previous_type is not None and previous_type != command.type:
            conflict = True
        else:
            duplicate = previous_type == command.type
            session.remember_command(command.command_id, command.type)
            current_state = session.state

    if conflict:
        return await _command_conflict(session, command.command_id)

    return PongEvent(
        call_id=session.call_id,
        seq=await session.next_sequence(),
        payload=PongPayload(
            command_id=command.command_id,
            state=current_state,
            sent_at=command.payload.sent_at,
            duplicate=duplicate,
        ),
    )


async def _audio_ack(
    session: LiveCallSession,
    settings: Settings,
    *,
    force: bool = False,
) -> AudioAckEvent | None:
    async with session.lock:
        pending_frames = (
            session.audio_frames_received
            - session.audio_frames_acknowledged
        )
        if pending_frames == 0 or (
            not force
            and pending_frames < settings.live_audio_ack_every_frames
        ):
            return None
        session.audio_frames_acknowledged = session.audio_frames_received
        frames_received = session.audio_frames_received
        bytes_received = session.audio_bytes_received

    return AudioAckEvent(
        call_id=session.call_id,
        seq=await session.next_sequence(),
        payload=AudioAckPayload(
            frames_received=frames_received,
            bytes_received=bytes_received,
        ),
    )


async def _handle_audio_frame(
    session: LiveCallSession,
    frame: bytes,
    settings: Settings,
) -> ServerEvent | None:
    error_code: str | None = None
    error_message = ""

    async with session.lock:
        if session.state is not CallState.LIVE:
            error_code = "audio_not_live"
            error_message = "Audio is accepted only while the call is live."
        elif session.audio_transport != "pcm_s16le":
            error_code = "audio_metadata_required"
            error_message = "Start the call with 24 kHz mono PCM metadata."
        elif not frame:
            error_code = "empty_audio_frame"
            error_message = "Empty audio frames are not accepted."
        elif len(frame) > settings.live_max_audio_frame_bytes:
            error_code = "audio_frame_too_large"
            error_message = "The audio frame exceeds the configured limit."
        elif len(frame) % 2 != 0:
            error_code = "audio_frame_misaligned"
            error_message = "PCM audio frames must contain complete 16-bit samples."
        else:
            session.audio_frames_received += 1
            session.audio_bytes_received += len(frame)

    if error_code is not None:
        return await _error_event(
            session,
            code=error_code,
            message=error_message,
            recoverable=True,
        )
    return await _audio_ack(session, settings)


async def _remaining_call_seconds(
    session: LiveCallSession,
    maximum_seconds: int,
) -> float | None:
    async with session.lock:
        if session.state is not CallState.LIVE or session.started_at is None:
            return None
        return maximum_seconds - (monotonic() - session.started_at)


async def _receive_message(
    websocket: WebSocket,
    session: LiveCallSession,
    settings: Settings,
) -> dict[str, Any]:
    remaining = await _remaining_call_seconds(
        session,
        settings.live_max_call_seconds,
    )
    if remaining is None:
        return await websocket.receive()
    if remaining <= 0:
        raise TimeoutError
    return await asyncio.wait_for(websocket.receive(), timeout=remaining)


async def _duration_limit_events(
    session: LiveCallSession,
    coordinator: LiveTranscriptionCoordinator | None = None,
) -> list[ServerEvent]:
    error = await _error_event(
        session,
        code="call_duration_exceeded",
        message="The call reached the configured duration limit.",
        recoverable=False,
    )
    transcript_complete = (
        await coordinator.stop() if coordinator is not None else True
    )
    async with session.lock:
        session.state = (
            CallState.ENDED
            if transcript_complete
            else CallState.INTERRUPTED
        )
    ended = CallEndedEvent(
        call_id=session.call_id,
        seq=await session.next_sequence(),
        payload=CallEndedPayload(
            state=session.state,
            transcript_complete=transcript_complete,
        ),
    )
    return [error, ended]


async def _handle_command(
    session: LiveCallSession,
    command: ClientCommand,
    settings: Settings,
    coordinator: LiveTranscriptionCoordinator | None = None,
    event_sink: Callable[[ServerEvent], Awaitable[None]] | None = None,
) -> list[ServerEvent]:
    if isinstance(command, StartCommand):
        return [await _handle_start(session, command)]
    if isinstance(command, StopCommand):
        events: list[ServerEvent] = []
        pending_ack = await _audio_ack(session, settings, force=True)
        if pending_ack is not None:
            if event_sink is not None:
                await event_sink(pending_ack)
            else:
                events.append(pending_ack)
        events.extend(
            await _handle_stop(
                session,
                command,
                coordinator,
                event_sink,
            )
        )
        return events
    return [await _handle_ping(session, command)]


def _create_streaming_transcriber(
    websocket: WebSocket,
    settings: Settings,
) -> StreamingTranscriber:
    factory = getattr(
        websocket.app.state,
        "streaming_transcriber_factory",
        None,
    )
    if factory is not None:
        return factory()
    if settings.openai_api_key is None:
        raise StreamingTranscriptionError(
            "Streaming transcription is not configured."
        )
    return OpenAIStreamingTranscriber(
        api_key=settings.openai_api_key,
        model=settings.live_stt_model,
    )


def _create_sales_detector(
    websocket: WebSocket,
    session: LiveCallSession,
    settings: Settings,
    live_coach: LiveCoach | None = None,
) -> LiveSalesDetector | None:
    factory = getattr(
        websocket.app.state,
        "sales_event_classifier_factory",
        None,
    )
    classifier: SalesEventClassifier | None = None
    if factory is not None:
        classifier = factory()
    elif settings.openai_api_key and settings.live_classification_model:
        classifier = OpenAISalesEventClassifier(
            api_key=settings.openai_api_key,
            model=settings.live_classification_model,
        )
    if classifier is None:
        return None

    detector: LiveSalesDetector | None = None

    async def emit_sales_event(payload: SalesEventPayload) -> None:
        await _enqueue(
            session,
            SalesEvent(
                call_id=session.call_id,
                seq=await session.next_sequence(),
                payload=payload,
            ),
            settings,
        )
        if live_coach is not None and detector is not None:
            await live_coach.submit(payload, detector.recent_segments())

    async def emit_warning(message: str) -> None:
        await _enqueue(
            session,
            WarningEvent(
                call_id=session.call_id,
                seq=await session.next_sequence(),
                payload=DiagnosticPayload(
                    code="sales_detection_failed",
                    message=message,
                    recoverable=True,
                    state=session.state,
                ),
            ),
            settings,
        )

    detector = LiveSalesDetector(
        classifier=classifier,
        event_sink=emit_sales_event,
        warning_sink=emit_warning,
    )
    return detector


def _create_live_coach(
    websocket: WebSocket,
    session: LiveCallSession,
    settings: Settings,
) -> LiveCoach | None:
    service_factory = getattr(websocket.app.state, "coach_service_factory", None)
    service: CoachService | None = None
    if service_factory is not None:
        service = service_factory()
    elif settings.openai_api_key and settings.live_coach_model:
        sessions = create_session_factory(
            create_database_engine(settings.database_url)
        )
        service = CoachService(
            RetrievalService(
                PostgresSearchBackend(sessions),
                OpenAIEmbeddingProvider(
                    settings.openai_api_key,
                    settings.knowledge_embedding_model,
                    settings.knowledge_embedding_dimensions,
                ),
                settings.knowledge_evidence_threshold,
            ),
            OpenAICoachGenerator(
                settings.openai_api_key,
                settings.live_coach_model,
            ),
        )
    if service is None:
        return None

    async def emit(payload: CoachSuggestionPayload) -> None:
        await _enqueue(
            session,
            CoachSuggestionEvent(
                call_id=session.call_id,
                seq=await session.next_sequence(),
                payload=payload,
            ),
            settings,
        )

    async def warn(message: str) -> None:
        await _enqueue(
            session,
            WarningEvent(
                call_id=session.call_id,
                seq=await session.next_sequence(),
                payload=DiagnosticPayload(
                    code="coaching_failed",
                    message=message,
                    recoverable=True,
                    state=session.state,
                ),
            ),
            settings,
        )

    return LiveCoach(service, emit, warn)


async def _shutdown_writer(
    session: LiveCallSession,
    timeout_ms: int,
) -> None:
    queue = session.outbound_queue
    writer_task = session.writer_task
    if queue is None or writer_task is None:
        return

    if not writer_task.done():
        try:
            queue.put_nowait(None)
        except asyncio.QueueFull:
            writer_task.cancel()

    try:
        await asyncio.wait_for(writer_task, timeout=timeout_ms / 1_000)
    except TimeoutError:
        writer_task.cancel()
        try:
            await writer_task
        except (
            asyncio.CancelledError,
            WebSocketDisconnect,
            RuntimeError,
            OSError,
        ):
            pass
    except (
        asyncio.CancelledError,
        WebSocketDisconnect,
        RuntimeError,
        OSError,
    ):
        pass


@router.websocket("/ws/calls/{call_id}")
async def live_call_socket(
    websocket: WebSocket,
    call_id: str,
    settings: Settings = Depends(get_settings),
) -> None:
    origin = websocket.headers.get("origin")
    if origin not in settings.browser_origins:
        await websocket.close(
            code=ORIGIN_REJECTED_CLOSE_CODE,
            reason="WebSocket origin is not allowed.",
        )
        return

    store = _live_call_store(websocket)
    session = await store.get(call_id)
    if session is None:
        await websocket.close(
            code=UNKNOWN_CALL_CLOSE_CODE,
            reason="Live call was not found.",
        )
        return

    queue: asyncio.Queue[OutboundItem] = asyncio.Queue(
        maxsize=settings.live_outbound_queue_size
    )
    coordinator: LiveTranscriptionCoordinator | None = None
    try:
        await session.attach(queue)
    except LiveCallAttachError:
        await websocket.close(
            code=SESSION_UNAVAILABLE_CLOSE_CODE,
            reason="Live call cannot accept this connection.",
        )
        return

    try:
        await websocket.accept()
        session.writer_task = asyncio.create_task(
            _outbound_writer(websocket, queue),
            name=f"live-call-writer-{call_id}",
        )

        ready = SessionReadyEvent(
            call_id=call_id,
            seq=await session.next_sequence(),
            payload=SessionReadyPayload(state=CallState.CONNECTING),
        )
        await _enqueue(session, ready, settings)
        while True:
            try:
                message = await _receive_message(
                    websocket,
                    session,
                    settings,
                )
            except TimeoutError:
                for event in await _duration_limit_events(
                    session,
                    coordinator,
                ):
                    await _enqueue(session, event, settings)
                break
            if message["type"] == "websocket.disconnect":
                break

            binary = message.get("bytes")
            if binary is not None:
                event = await _handle_audio_frame(
                    session,
                    binary,
                    settings,
                )
                if event is not None:
                    await _enqueue(session, event, settings)
                if not isinstance(event, ErrorEvent):
                    if coordinator is None:
                        missing = await _error_event(
                            session,
                            code="transcription_not_started",
                            message="The transcription stream is unavailable.",
                            recoverable=False,
                        )
                        await _enqueue(session, missing, settings)
                        break
                    try:
                        await coordinator.accept_audio(binary)
                    except LiveCoordinatorError as exc:
                        overloaded = await _error_event(
                            session,
                            code="transcription_overloaded",
                            message=str(exc),
                            recoverable=False,
                        )
                        await _enqueue(session, overloaded, settings)
                        break
                continue

            text = message.get("text")
            if text is None:
                continue
            if len(text.encode("utf-8")) > settings.live_max_control_message_bytes:
                event = await _error_event(
                    session,
                    code="command_too_large",
                    message="The control message exceeds the configured limit.",
                    recoverable=True,
                )
                await _enqueue(session, event, settings)
                continue

            try:
                command = _parse_command(text)
            except InvalidProtocolVersion:
                event = await _error_event(
                    session,
                    code="invalid_protocol_version",
                    message="The protocol version is not supported.",
                    recoverable=False,
                )
                await _enqueue(session, event, settings)
                continue
            except (ValidationError, ValueError):
                event = await _error_event(
                    session,
                    code="malformed_command",
                    message="The command payload is malformed.",
                    recoverable=True,
                )
                await _enqueue(session, event, settings)
                continue

            events = await _handle_command(
                session,
                command,
                settings,
                coordinator,
                lambda event: _enqueue(session, event, settings),
            )
            if isinstance(command, StartCommand):
                started = next(
                    (
                        event
                        for event in events
                        if isinstance(event, CallStartedEvent)
                        and not event.payload.duplicate
                    ),
                    None,
                )
                if started is not None and command.payload.audio is not None:
                    try:
                        transcriber = _create_streaming_transcriber(
                            websocket,
                            settings,
                        )
                        live_coach = _create_live_coach(
                            websocket,
                            session,
                            settings,
                        )
                        coordinator = LiveTranscriptionCoordinator(
                            call_id=call_id,
                            transcriber=transcriber,
                            event_sink=lambda event: _enqueue(
                                session,
                                event,
                                settings,
                            ),
                            next_sequence=session.next_sequence,
                            queue_size=settings.live_outbound_queue_size,
                            queue_timeout_seconds=(
                                settings.live_queue_put_timeout_ms / 1_000
                            ),
                            finalization_timeout_seconds=(
                                settings.live_stt_finalization_timeout_ms
                                / 1_000
                            ),
                            sales_detector=_create_sales_detector(
                                websocket,
                                session,
                                settings,
                                live_coach,
                            ),
                            live_coach=live_coach,
                        )
                        await coordinator.start()
                    except StreamingTranscriptionError as exc:
                        async with session.lock:
                            session.state = CallState.FAILED
                        events = [
                            await _error_event(
                                session,
                                code="transcription_start_failed",
                                message=str(exc),
                                recoverable=False,
                                command_id=command.command_id,
                            ),
                            CallEndedEvent(
                                call_id=call_id,
                                seq=await session.next_sequence(),
                                payload=CallEndedPayload(
                                    state=CallState.FAILED,
                                    command_id=command.command_id,
                                    transcript_complete=False,
                                ),
                            ),
                        ]
            for event in events:
                await _enqueue(session, event, settings)
    except (WebSocketDisconnect, RuntimeError, OSError):
        pass
    finally:
        try:
            if coordinator is not None:
                await coordinator.interrupt()
            await _shutdown_writer(
                session,
                settings.live_queue_put_timeout_ms,
            )
        finally:
            await session.detach()
