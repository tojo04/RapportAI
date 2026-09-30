import asyncio
from dataclasses import dataclass, field
from time import monotonic
from typing import TypeAlias
from uuid import uuid4

from app.models.realtime import CallState, ServerEvent


OutboundItem: TypeAlias = ServerEvent | None


class LiveCallCapacityError(RuntimeError):
    """Raised when the configured active-call limit has been reached."""


class LiveCallAttachError(RuntimeError):
    """Raised when a call cannot accept a new live WebSocket."""


@dataclass
class LiveCallSession:
    call_id: str
    max_command_history: int
    state: CallState = CallState.IDLE
    sequence: int = 0
    outbound_sequence: int = 0
    connected: bool = False
    processed_commands: dict[str, str] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    outbound_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    outbound_queue: asyncio.Queue[OutboundItem] | None = field(
        default=None,
        repr=False,
    )
    writer_task: asyncio.Task[None] | None = field(default=None, repr=False)
    started_at: float | None = None
    audio_transport: str | None = None
    audio_sample_rate_hz: int | None = None
    audio_channels: int | None = None
    audio_frame_duration_ms: int | None = None
    audio_frames_received: int = 0
    audio_bytes_received: int = 0
    audio_frames_acknowledged: int = 0

    async def attach(
        self,
        outbound_queue: asyncio.Queue[OutboundItem],
    ) -> None:
        async with self.lock:
            if self.connected or self.state is not CallState.IDLE:
                raise LiveCallAttachError(
                    "This call cannot accept another live connection."
                )
            self.connected = True
            self.state = CallState.CONNECTING
            self.outbound_queue = outbound_queue

    async def detach(self) -> None:
        async with self.lock:
            if self.state not in {
                CallState.ENDED,
                CallState.INTERRUPTED,
                CallState.FAILED,
            }:
                self.state = CallState.INTERRUPTED
            self.connected = False
            self.outbound_queue = None
            self.writer_task = None

    async def next_sequence(self) -> int:
        async with self.lock:
            self.sequence += 1
            return self.sequence

    def next_outbound_sequence(self) -> int:
        """Assign wire order while the caller holds outbound_lock."""

        self.outbound_sequence += 1
        return self.outbound_sequence

    def remember_command(self, command_id: str, command_type: str) -> None:
        """Record a command while the caller holds the session lock."""

        self.processed_commands[command_id] = command_type
        while len(self.processed_commands) > self.max_command_history:
            oldest_command_id = next(iter(self.processed_commands))
            del self.processed_commands[oldest_command_id]

    def mark_started(
        self,
        *,
        transport: str | None,
        sample_rate_hz: int | None,
        channels: int | None,
        frame_duration_ms: int | None,
    ) -> None:
        """Record transport metadata while the caller holds the session lock."""

        self.started_at = monotonic()
        self.audio_transport = transport
        self.audio_sample_rate_hz = sample_rate_hz
        self.audio_channels = channels
        self.audio_frame_duration_ms = frame_duration_ms


class LiveCallStore:
    """Process-local live-call registry for the one-worker baseline."""

    def __init__(
        self,
        max_active_calls: int,
        max_retained_calls: int = 100,
        max_command_history: int = 512,
    ) -> None:
        self._max_active_calls = max_active_calls
        self._max_retained_calls = max_retained_calls
        self._max_command_history = max_command_history
        self._sessions: dict[str, LiveCallSession] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> LiveCallSession:
        async with self._lock:
            while len(self._sessions) >= self._max_retained_calls:
                terminal_call_id = next(
                    (
                        call_id
                        for call_id, session in self._sessions.items()
                        if session.state
                        in {
                            CallState.ENDED,
                            CallState.INTERRUPTED,
                            CallState.FAILED,
                        }
                    ),
                    None,
                )
                if terminal_call_id is None:
                    raise LiveCallCapacityError(
                        "The live-call capacity has been reached."
                    )
                del self._sessions[terminal_call_id]

            active_calls = sum(
                session.state
                not in {
                    CallState.ENDED,
                    CallState.INTERRUPTED,
                    CallState.FAILED,
                }
                for session in self._sessions.values()
            )
            if active_calls >= self._max_active_calls:
                raise LiveCallCapacityError(
                    "The live-call capacity has been reached."
                )

            call_id = str(uuid4())
            session = LiveCallSession(
                call_id=call_id,
                max_command_history=self._max_command_history,
            )
            self._sessions[call_id] = session
            return session

    async def get(self, call_id: str) -> LiveCallSession | None:
        async with self._lock:
            return self._sessions.get(call_id)

    async def clear(self) -> None:
        """Clear the process-local store for deterministic tests."""

        async with self._lock:
            self._sessions.clear()
