import asyncio
import json
from time import monotonic
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
    ClientCommand,
    CreateCallResponse,
    DiagnosticPayload,
    ErrorEvent,
    PingCommand,
    PongEvent,
    PongPayload,
    ServerEvent,
    SessionReadyEvent,
    SessionReadyPayload,
    StartCommand,
    StopCommand,
    LiveTransportLimits,
)
from app.realtime.sessions import (
    LiveCallAttachError,
    LiveCallCapacityError,
    LiveCallSession,
    LiveCallStore,
    OutboundItem,
)


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
    return await _create_live_call_for_store(
        _live_call_store(request),
        settings,
    )


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
        await asyncio.wait_for(
            queue.put(event),
            timeout=settings.live_queue_put_timeout_ms / 1_000,
        )
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
                mime_type=audio.mime_type if audio is not None else None,
                timeslice_ms=(
                    audio.timeslice_ms if audio is not None else None
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
) -> list[ServerEvent]:
    duplicate = False
    error_kind: str | None = None

    async with session.lock:
        previous_type = session.processed_commands.get(command.command_id)
        if previous_type is not None and previous_type != command.type:
            error_kind = "conflict"
        elif session.state is CallState.ENDED:
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
                    state=CallState.ENDED,
                    command_id=command.command_id,
                    duplicate=True,
                    transcript_complete=True,
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
    async with session.lock:
        session.state = CallState.ENDED
    ended_event = CallEndedEvent(
        call_id=session.call_id,
        seq=await session.next_sequence(),
        payload=CallEndedPayload(
            state=CallState.ENDED,
            command_id=command.command_id,
            transcript_complete=True,
        ),
    )
    return [stopping_event, ended_event]


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
        elif session.audio_transport != "media_recorder":
            error_code = "audio_metadata_required"
            error_message = "Start the call with MediaRecorder audio metadata."
        elif not frame:
            error_code = "empty_audio_frame"
            error_message = "Empty audio frames are not accepted."
        elif len(frame) > settings.live_max_audio_frame_bytes:
            error_code = "audio_frame_too_large"
            error_message = "The audio frame exceeds the configured limit."
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
) -> list[ServerEvent]:
    error = await _error_event(
        session,
        code="call_duration_exceeded",
        message="The call reached the configured duration limit.",
        recoverable=False,
    )
    async with session.lock:
        session.state = CallState.ENDED
    ended = CallEndedEvent(
        call_id=session.call_id,
        seq=await session.next_sequence(),
        payload=CallEndedPayload(
            state=CallState.ENDED,
            transcript_complete=True,
        ),
    )
    return [error, ended]


async def _handle_command(
    session: LiveCallSession,
    command: ClientCommand,
    settings: Settings,
) -> list[ServerEvent]:
    if isinstance(command, StartCommand):
        return [await _handle_start(session, command)]
    if isinstance(command, StopCommand):
        events: list[ServerEvent] = []
        pending_ack = await _audio_ack(session, settings, force=True)
        if pending_ack is not None:
            events.append(pending_ack)
        events.extend(await _handle_stop(session, command))
        return events
    return [await _handle_ping(session, command)]


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
                for event in await _duration_limit_events(session):
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

            for event in await _handle_command(session, command, settings):
                await _enqueue(session, event, settings)
    except (WebSocketDisconnect, RuntimeError, OSError):
        pass
    finally:
        try:
            await _shutdown_writer(
                session,
                settings.live_queue_put_timeout_ms,
            )
        finally:
            await session.detach()
