export const REALTIME_PROTOCOL_VERSION = 1 as const;

export type CallState =
  | 'idle'
  | 'connecting'
  | 'live'
  | 'stopping'
  | 'ended'
  | 'interrupted'
  | 'failed';

export type SalesCategory =
  | 'question'
  | 'objection'
  | 'pricing'
  | 'competitor'
  | 'buying_signal'
  | 'requirement';

export interface CreateCallResponse {
  protocol_version: typeof REALTIME_PROTOCOL_VERSION;
  call_id: string;
  websocket_path: string;
  state: 'idle';
  limits: {
    max_call_seconds: number;
    max_frame_bytes: number;
    ack_every_frames: number;
  };
}

interface ClientCommandEnvelope<TType extends string, TPayload> {
  protocol_version: typeof REALTIME_PROTOCOL_VERSION;
  command_id: string;
  type: TType;
  payload: TPayload;
}

export interface MediaRecorderAudioConfig {
  transport: 'media_recorder';
  mime_type: string;
  timeslice_ms: number;
}

export type StartCommand = ClientCommandEnvelope<
  'start',
  { audio?: MediaRecorderAudioConfig | null }
>;
export type StopCommand = ClientCommandEnvelope<'stop', Record<string, never>>;
export type PingCommand = ClientCommandEnvelope<
  'ping',
  { sent_at?: string | null }
>;
export type ClientCommand = StartCommand | StopCommand | PingCommand;

interface ServerEventEnvelope<TType extends string, TPayload> {
  protocol_version: typeof REALTIME_PROTOCOL_VERSION;
  event_id: string;
  call_id: string;
  seq: number;
  type: TType;
  emitted_at: string;
  payload: TPayload;
}

export type SessionReadyEvent = ServerEventEnvelope<
  'session.ready',
  { state: 'connecting' }
>;
export type CallStartedEvent = ServerEventEnvelope<
  'call.started',
  { state: 'live'; command_id: string; duplicate: boolean }
>;
export type AudioAckEvent = ServerEventEnvelope<
  'audio.ack',
  { frames_received: number; bytes_received: number }
>;

export interface TranscriptPayload {
  segment_id: string;
  order: number;
  revision: number;
  text: string;
  speaker_id: string | null;
  speaker_role: 'unknown' | 'salesperson' | 'customer';
  start_ms: number | null;
  end_ms: number | null;
  language: string | null;
}

export type TranscriptPartialEvent = ServerEventEnvelope<
  'transcript.partial',
  TranscriptPayload
>;
export type TranscriptFinalEvent = ServerEventEnvelope<
  'transcript.final',
  TranscriptPayload
>;

export interface SalesEventPayload {
  sales_event_id: string;
  category: SalesCategory;
  evidence_segment_ids: string[];
  evidence_span: string;
  subject: string;
  details: Record<string, string | number | boolean | null>;
}

export type SalesEvent = ServerEventEnvelope<'sales.event', SalesEventPayload>;
export type CoachSuggestionEvent = ServerEventEnvelope<
  'coach.suggestion',
  {
    suggestion_id: string;
    text: string;
    evidence_segment_ids: string[];
    source_chunk_ids: string[];
    insufficient_evidence: boolean;
  }
>;
export type CallStoppingEvent = ServerEventEnvelope<
  'call.stopping',
  { state: 'stopping'; command_id: string }
>;
export type CallEndedEvent = ServerEventEnvelope<
  'call.ended',
  {
    state: 'ended' | 'interrupted' | 'failed';
    command_id: string | null;
    duplicate: boolean;
    transcript_complete: boolean;
  }
>;
export type AnalysisStartedEvent = ServerEventEnvelope<
  'analysis.started',
  { analysis_version: string }
>;
export type AnalysisCompletedEvent = ServerEventEnvelope<
  'analysis.completed',
  { analysis_version: string }
>;
export type AnalysisFailedEvent = ServerEventEnvelope<
  'analysis.failed',
  {
    analysis_version: string;
    code: string;
    message: string;
    retryable: boolean;
  }
>;

export interface DiagnosticPayload {
  code: string;
  message: string;
  recoverable: boolean;
  command_id: string | null;
  state: CallState;
}

export type WarningEvent = ServerEventEnvelope<'warning', DiagnosticPayload>;
export type ErrorEvent = ServerEventEnvelope<'error', DiagnosticPayload>;
export type PongEvent = ServerEventEnvelope<
  'pong',
  {
    command_id: string;
    state: CallState;
    sent_at: string | null;
    duplicate: boolean;
  }
>;

export type ServerEvent =
  | SessionReadyEvent
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
  | PongEvent;

const CALL_STATES: readonly CallState[] = [
  'idle',
  'connecting',
  'live',
  'stopping',
  'ended',
  'interrupted',
  'failed',
];
const SALES_CATEGORIES: readonly SalesCategory[] = [
  'question',
  'objection',
  'pricing',
  'competitor',
  'buying_signal',
  'requirement',
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isBoolean(value: unknown): value is boolean {
  return typeof value === 'boolean';
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 1;
}

function isNullableString(value: unknown): value is string | null {
  return typeof value === 'string' || value === null;
}

function isNullableNonNegativeInteger(value: unknown): value is number | null {
  return value === null || isNonNegativeInteger(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(isNonEmptyString);
}

function isCallState(value: unknown): value is CallState {
  return typeof value === 'string' && CALL_STATES.includes(value as CallState);
}

function isIsoDate(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    value.length > 0 &&
    !Number.isNaN(Date.parse(value))
  );
}

function hasOnlyEmptyPayload(value: unknown): boolean {
  return isRecord(value) && Object.keys(value).length === 0;
}

function isMediaRecorderAudioConfig(
  value: unknown,
): value is MediaRecorderAudioConfig {
  return (
    isRecord(value) &&
    value.transport === 'media_recorder' &&
    isNonEmptyString(value.mime_type) &&
    value.mime_type.toLowerCase().startsWith('audio/') &&
    !/[\r\n]/u.test(value.mime_type) &&
    isPositiveInteger(value.timeslice_ms) &&
    value.timeslice_ms >= 50 &&
    value.timeslice_ms <= 1_000
  );
}

function isTranscriptPayload(value: unknown): value is TranscriptPayload {
  return (
    isRecord(value) &&
    isNonEmptyString(value.segment_id) &&
    isNonNegativeInteger(value.order) &&
    isPositiveInteger(value.revision) &&
    typeof value.text === 'string' &&
    isNullableString(value.speaker_id) &&
    (value.speaker_role === 'unknown' ||
      value.speaker_role === 'salesperson' ||
      value.speaker_role === 'customer') &&
    isNullableNonNegativeInteger(value.start_ms) &&
    isNullableNonNegativeInteger(value.end_ms) &&
    isNullableString(value.language)
  );
}

function isDetails(
  value: unknown,
): value is Record<string, string | number | boolean | null> {
  return (
    isRecord(value) &&
    Object.values(value).every(
      (item) =>
        item === null ||
        typeof item === 'string' ||
        (typeof item === 'number' && Number.isFinite(item)) ||
        typeof item === 'boolean',
    )
  );
}

function isDiagnosticPayload(value: unknown): value is DiagnosticPayload {
  return (
    isRecord(value) &&
    isNonEmptyString(value.code) &&
    typeof value.message === 'string' &&
    isBoolean(value.recoverable) &&
    isNullableString(value.command_id) &&
    isCallState(value.state)
  );
}

function hasValidEnvelope(value: Record<string, unknown>): boolean {
  return (
    value.protocol_version === REALTIME_PROTOCOL_VERSION &&
    isNonEmptyString(value.event_id) &&
    isNonEmptyString(value.call_id) &&
    isPositiveInteger(value.seq) &&
    isIsoDate(value.emitted_at) &&
    typeof value.type === 'string'
  );
}

function hasAnalysisStatus(value: unknown): boolean {
  return isRecord(value) && isNonEmptyString(value.analysis_version);
}

function hasValidPayload(type: ServerEvent['type'], payload: unknown): boolean {
  if (!isRecord(payload)) return false;

  switch (type) {
    case 'session.ready':
      return payload.state === 'connecting';
    case 'call.started':
      return (
        payload.state === 'live' &&
        isNonEmptyString(payload.command_id) &&
        isBoolean(payload.duplicate)
      );
    case 'audio.ack':
      return (
        isNonNegativeInteger(payload.frames_received) &&
        isNonNegativeInteger(payload.bytes_received)
      );
    case 'transcript.partial':
    case 'transcript.final':
      return isTranscriptPayload(payload);
    case 'sales.event':
      return (
        isNonEmptyString(payload.sales_event_id) &&
        typeof payload.category === 'string' &&
        SALES_CATEGORIES.includes(payload.category as SalesCategory) &&
        isStringArray(payload.evidence_segment_ids) &&
        typeof payload.evidence_span === 'string' &&
        typeof payload.subject === 'string' &&
        isDetails(payload.details)
      );
    case 'coach.suggestion':
      return (
        isNonEmptyString(payload.suggestion_id) &&
        typeof payload.text === 'string' &&
        isStringArray(payload.evidence_segment_ids) &&
        isStringArray(payload.source_chunk_ids) &&
        isBoolean(payload.insufficient_evidence)
      );
    case 'call.stopping':
      return (
        payload.state === 'stopping' && isNonEmptyString(payload.command_id)
      );
    case 'call.ended':
      return (
        (payload.state === 'ended' ||
          payload.state === 'interrupted' ||
          payload.state === 'failed') &&
        isNullableString(payload.command_id) &&
        isBoolean(payload.duplicate) &&
        isBoolean(payload.transcript_complete)
      );
    case 'analysis.started':
    case 'analysis.completed':
      return hasAnalysisStatus(payload);
    case 'analysis.failed':
      return (
        hasAnalysisStatus(payload) &&
        isNonEmptyString(payload.code) &&
        typeof payload.message === 'string' &&
        isBoolean(payload.retryable)
      );
    case 'warning':
    case 'error':
      return isDiagnosticPayload(payload);
    case 'pong':
      return (
        isNonEmptyString(payload.command_id) &&
        isCallState(payload.state) &&
        (payload.sent_at === null || isIsoDate(payload.sent_at)) &&
        isBoolean(payload.duplicate)
      );
  }
}

const SERVER_EVENT_TYPES: readonly ServerEvent['type'][] = [
  'session.ready',
  'call.started',
  'audio.ack',
  'transcript.partial',
  'transcript.final',
  'sales.event',
  'coach.suggestion',
  'call.stopping',
  'call.ended',
  'analysis.started',
  'analysis.completed',
  'analysis.failed',
  'warning',
  'error',
  'pong',
];

export function parseServerEvent(value: unknown): ServerEvent | null {
  if (!isRecord(value)) {
    throw new Error('Realtime event must be an object.');
  }
  if (value.protocol_version !== REALTIME_PROTOCOL_VERSION) {
    throw new Error('Realtime event uses an incompatible protocol version.');
  }
  if (!hasValidEnvelope(value)) {
    throw new Error('Realtime event envelope is malformed.');
  }
  if (!SERVER_EVENT_TYPES.includes(value.type as ServerEvent['type'])) {
    return null;
  }
  if (!hasValidPayload(value.type as ServerEvent['type'], value.payload)) {
    throw new Error(`Realtime ${value.type} payload is malformed.`);
  }
  return value as unknown as ServerEvent;
}

export function parseCreateCallResponse(value: unknown): CreateCallResponse {
  if (
    !isRecord(value) ||
    value.protocol_version !== REALTIME_PROTOCOL_VERSION ||
    !isNonEmptyString(value.call_id) ||
    !isNonEmptyString(value.websocket_path) ||
    value.state !== 'idle' ||
    !isRecord(value.limits) ||
    !isPositiveInteger(value.limits.max_call_seconds) ||
    !isPositiveInteger(value.limits.max_frame_bytes) ||
    !isPositiveInteger(value.limits.ack_every_frames)
  ) {
    throw new Error('The server returned malformed live-call data.');
  }
  return value as unknown as CreateCallResponse;
}

export function isClientCommand(value: unknown): value is ClientCommand {
  if (
    !isRecord(value) ||
    value.protocol_version !== REALTIME_PROTOCOL_VERSION ||
    !isNonEmptyString(value.command_id) ||
    !isRecord(value.payload)
  ) {
    return false;
  }

  if (value.type === 'start') {
    return (
      Object.keys(value.payload).every((key) => key === 'audio') &&
      (value.payload.audio === undefined ||
        value.payload.audio === null ||
        isMediaRecorderAudioConfig(value.payload.audio))
    );
  }
  if (value.type === 'stop') {
    return hasOnlyEmptyPayload(value.payload);
  }
  if (value.type === 'ping') {
    return (
      Object.keys(value.payload).every((key) => key === 'sent_at') &&
      (value.payload.sent_at === undefined ||
        value.payload.sent_at === null ||
        isIsoDate(value.payload.sent_at))
    );
  }
  return false;
}
