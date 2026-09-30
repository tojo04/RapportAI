from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal, TypeAlias
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
)


PROTOCOL_VERSION = 1
Identifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class ProtocolModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CallState(StrEnum):
    IDLE = "idle"
    CONNECTING = "connecting"
    LIVE = "live"
    STOPPING = "stopping"
    ENDED = "ended"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


class EmptyPayload(ProtocolModel):
    pass


class ClientCommandBase(ProtocolModel):
    protocol_version: Literal[1]
    command_id: Identifier


class PcmAudioConfig(ProtocolModel):
    transport: Literal["pcm_s16le"]
    sample_rate_hz: Literal[24_000]
    channels: Literal[1]
    frame_duration_ms: Annotated[int, Field(strict=True, ge=50, le=200)]


class StartPayload(ProtocolModel):
    audio: PcmAudioConfig | None = None


class StartCommand(ClientCommandBase):
    type: Literal["start"]
    payload: StartPayload


class StopCommand(ClientCommandBase):
    type: Literal["stop"]
    payload: EmptyPayload


class PingPayload(ProtocolModel):
    sent_at: datetime | None = None


class PingCommand(ClientCommandBase):
    type: Literal["ping"]
    payload: PingPayload


ClientCommand: TypeAlias = Annotated[
    StartCommand | StopCommand | PingCommand,
    Field(discriminator="type"),
]
CLIENT_COMMAND_ADAPTER = TypeAdapter(ClientCommand)


class ServerEventBase(ProtocolModel):
    protocol_version: Literal[1] = PROTOCOL_VERSION
    event_id: Identifier = Field(default_factory=lambda: str(uuid4()))
    call_id: Identifier
    seq: Annotated[int, Field(strict=True, ge=1)]
    emitted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class SessionReadyPayload(ProtocolModel):
    state: Literal[CallState.CONNECTING]


class SessionReadyEvent(ServerEventBase):
    type: Literal["session.ready"] = "session.ready"
    payload: SessionReadyPayload


class CallStartedPayload(ProtocolModel):
    state: Literal[CallState.LIVE]
    command_id: Identifier
    duplicate: bool = False


class CallStartedEvent(ServerEventBase):
    type: Literal["call.started"] = "call.started"
    payload: CallStartedPayload


class AudioAckPayload(ProtocolModel):
    frames_received: Annotated[int, Field(strict=True, ge=0)]
    bytes_received: Annotated[int, Field(strict=True, ge=0)]


class AudioAckEvent(ServerEventBase):
    type: Literal["audio.ack"] = "audio.ack"
    payload: AudioAckPayload


class TranscriptPayload(ProtocolModel):
    segment_id: Identifier
    order: Annotated[int, Field(strict=True, ge=0)]
    revision: Annotated[int, Field(strict=True, ge=1)]
    text: str
    speaker_id: str | None = None
    speaker_role: Literal["unknown", "salesperson", "customer"] = "unknown"
    start_ms: Annotated[int, Field(strict=True, ge=0)] | None = None
    end_ms: Annotated[int, Field(strict=True, ge=0)] | None = None
    language: str | None = None


class TranscriptPartialEvent(ServerEventBase):
    type: Literal["transcript.partial"] = "transcript.partial"
    payload: TranscriptPayload


class TranscriptFinalEvent(ServerEventBase):
    type: Literal["transcript.final"] = "transcript.final"
    payload: TranscriptPayload


SalesCategory = Literal[
    "question",
    "objection",
    "pricing",
    "competitor",
    "buying_signal",
    "requirement",
]


class SalesEventPayload(ProtocolModel):
    sales_event_id: Identifier
    category: SalesCategory
    evidence_segment_ids: list[Identifier]
    evidence_span: str
    subject: str
    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict
    )


class SalesEvent(ServerEventBase):
    type: Literal["sales.event"] = "sales.event"
    payload: SalesEventPayload


class CoachSuggestionPayload(ProtocolModel):
    suggestion_id: Identifier
    text: str
    evidence_segment_ids: list[Identifier]
    source_chunk_ids: list[Identifier]
    source_versions: dict[Identifier, Identifier] = Field(default_factory=dict)
    sources: list["CoachSource"] = Field(default_factory=list)
    insufficient_evidence: bool


class CoachSource(ProtocolModel):
    chunk_id: Identifier
    source_path: str
    heading: str
    text: str
    content_revision: Identifier
    corpus_revision: Identifier


class CoachSuggestionEvent(ServerEventBase):
    type: Literal["coach.suggestion"] = "coach.suggestion"
    payload: CoachSuggestionPayload


class CallStoppingPayload(ProtocolModel):
    state: Literal[CallState.STOPPING]
    command_id: Identifier


class CallStoppingEvent(ServerEventBase):
    type: Literal["call.stopping"] = "call.stopping"
    payload: CallStoppingPayload


class CallEndedPayload(ProtocolModel):
    state: Literal[
        CallState.ENDED,
        CallState.INTERRUPTED,
        CallState.FAILED,
    ]
    command_id: Identifier | None = None
    duplicate: bool = False
    transcript_complete: bool


class CallEndedEvent(ServerEventBase):
    type: Literal["call.ended"] = "call.ended"
    payload: CallEndedPayload


class AnalysisStatusPayload(ProtocolModel):
    analysis_version: Identifier


class AnalysisStartedEvent(ServerEventBase):
    type: Literal["analysis.started"] = "analysis.started"
    payload: AnalysisStatusPayload


class AnalysisCompletedEvent(ServerEventBase):
    type: Literal["analysis.completed"] = "analysis.completed"
    payload: AnalysisStatusPayload


class AnalysisFailedPayload(AnalysisStatusPayload):
    code: Identifier
    message: str
    retryable: bool


class AnalysisFailedEvent(ServerEventBase):
    type: Literal["analysis.failed"] = "analysis.failed"
    payload: AnalysisFailedPayload


class DiagnosticPayload(ProtocolModel):
    code: Identifier
    message: str
    recoverable: bool
    command_id: Identifier | None = None
    state: CallState


class WarningEvent(ServerEventBase):
    type: Literal["warning"] = "warning"
    payload: DiagnosticPayload


class ErrorEvent(ServerEventBase):
    type: Literal["error"] = "error"
    payload: DiagnosticPayload


class PongPayload(ProtocolModel):
    command_id: Identifier
    state: CallState
    sent_at: datetime | None = None
    duplicate: bool = False


class PongEvent(ServerEventBase):
    type: Literal["pong"] = "pong"
    payload: PongPayload


ServerEvent: TypeAlias = Annotated[
    SessionReadyEvent
    | CallStartedEvent
    | AudioAckEvent
    | TranscriptPartialEvent
    | TranscriptFinalEvent
    | SalesEvent
    | CoachSuggestionEvent
    | CallStoppingEvent
    | CallEndedEvent
    | AnalysisStartedEvent
    | AnalysisCompletedEvent
    | AnalysisFailedEvent
    | WarningEvent
    | ErrorEvent
    | PongEvent,
    Field(discriminator="type"),
]
SERVER_EVENT_ADAPTER = TypeAdapter(ServerEvent)


class LiveTransportLimits(ProtocolModel):
    max_call_seconds: Annotated[int, Field(strict=True, ge=1)]
    max_frame_bytes: Annotated[int, Field(strict=True, ge=1)]
    ack_every_frames: Annotated[int, Field(strict=True, ge=1)]


class CreateCallResponse(ProtocolModel):
    protocol_version: Literal[1] = PROTOCOL_VERSION
    call_id: Identifier
    websocket_path: str
    state: Literal[CallState.IDLE] = CallState.IDLE
    limits: LiveTransportLimits
