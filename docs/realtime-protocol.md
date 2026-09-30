# RapportAI realtime protocol v1

This document is the wire contract between the RapportAI browser and FastAPI
live-call endpoint. Protocol version 1 currently covers call creation and the
JSON control lifecycle. Binary audio is deliberately rejected until Task 2.

## Transport and session creation

Create a server-owned live-call ID:

```http
POST /api/calls
```

The successful HTTP 201 response is:

```json
{
  "protocol_version": 1,
  "call_id": "opaque-server-generated-id",
  "websocket_path": "/ws/calls/opaque-server-generated-id",
  "state": "idle"
}
```

Connect to the returned path on the same backend host. Local development uses
`ws://localhost:8000`; a non-local deployment must use HTTPS/WSS for browser
microphone access. The server checks the WebSocket `Origin` header against
`ALLOWED_ORIGINS` independently from HTTP CORS.

A call ID locates an in-memory session. It is not authentication or an access
token. V2 is a local/private demonstration and the endpoint must not be exposed
publicly without separate access control.

## Server event envelope

Every known server event has this envelope:

```json
{
  "protocol_version": 1,
  "event_id": "unique-event-id",
  "call_id": "opaque-call-id",
  "seq": 12,
  "type": "transcript.final",
  "emitted_at": "2026-09-30T08:00:00Z",
  "payload": {}
}
```

- `protocol_version` must equal `1`. An incompatible version fails visibly.
- `event_id` identifies one emitted event.
- `seq` starts at 1 and is assigned by the single per-call outbound path. It is
  ordering metadata for server events, not transcript order.
- `emitted_at` is a UTC record timestamp. It is not an audio timestamp.
- `payload` is selected by the `type` discriminator and rejects unexpected
  fields on the backend.
- A client may ignore an unknown future optional event type with a diagnostic,
  but it rejects a malformed known event.

## Client commands

Commands are JSON text frames. Every command contains a caller-generated,
non-empty `command_id` of at most 128 characters. IDs make retries observable
and idempotent within one process-local session.

### Start

```json
{
  "protocol_version": 1,
  "command_id": "start-1",
  "type": "start",
  "payload": {}
}
```

Allowed only while `connecting`. A repeated `start` with the same command ID
while the session is `live` returns `call.started` with `duplicate: true`. A new
start while already live returns an `illegal_state` error.

### Stop

```json
{
  "protocol_version": 1,
  "command_id": "stop-1",
  "type": "stop",
  "payload": {}
}
```

Allowed while `connecting` or `live`. It emits `call.stopping` followed by
`call.ended`. Any later stop is harmless and returns `call.ended` with
`duplicate: true`; it does not repeat finalization.

### Ping

```json
{
  "protocol_version": 1,
  "command_id": "ping-1",
  "type": "ping",
  "payload": {
    "sent_at": "2026-09-30T08:00:00Z"
  }
}
```

`sent_at` may be omitted or `null`. The server replies with `pong`, echoes the
command ID and optional timestamp, and includes the authoritative call state.
Repeating the same ping ID sets `duplicate: true`.

Reusing a command ID for a different command type returns
`command_id_conflict`. Missing fields, unknown command types, invalid JSON, and
unexpected payload fields return `malformed_command`. A supplied version other
than integer `1` returns `invalid_protocol_version`.

## Lifecycle

```text
POST /api/calls: idle
WebSocket accepted: idle -> connecting
start: connecting -> live
stop: connecting|live -> stopping -> ended
disconnect before ended: connecting|live|stopping -> interrupted
critical internal failure: active state -> failed
```

| Current state            | `start`            | `stop`                                     | `ping`                            |
| ------------------------ | ------------------ | ------------------------------------------ | --------------------------------- |
| `connecting`             | Move to `live`     | Move through `stopping` to `ended`         | Allowed                           |
| `live`                   | Same-ID retry only | Move through `stopping` to `ended`         | Allowed                           |
| `stopping`               | Rejected           | Rejected while finalization is in progress | Allowed                           |
| `ended`                  | Rejected           | Idempotent `call.ended`                    | Allowed while socket remains open |
| `interrupted` / `failed` | Rejected           | Rejected                                   | No new socket is accepted         |

`idle` exists before a socket is attached. The first server event after a
successful connection is `session.ready` with state `connecting`.

There is no live resume in version 1. A disconnect marks an unfinished call
`interrupted`, releases its writer/queue, and a new call must be created. An
ended, interrupted, failed, or already-connected session rejects another
socket.

## Server event types

| Type                                     | Payload fields                                                              | Stage first emitted |
| ---------------------------------------- | --------------------------------------------------------------------------- | ------------------- |
| `session.ready`                          | `state: connecting`                                                         | Task 1              |
| `call.started`                           | `state`, `command_id`, `duplicate`                                          | Task 1              |
| `pong`                                   | `command_id`, `state`, `sent_at`, `duplicate`                               | Task 1              |
| `call.stopping`                          | `state`, `command_id`                                                       | Task 1              |
| `call.ended`                             | terminal `state`, nullable `command_id`, `duplicate`, `transcript_complete` | Task 1              |
| `error`, `warning`                       | `code`, sanitized `message`, `recoverable`, nullable `command_id`, `state`  | Task 1+             |
| `audio.ack`                              | cumulative `frames_received`, `bytes_received`                              | Task 2              |
| `transcript.partial`, `transcript.final` | transcript segment payload below                                            | Task 5              |
| `sales.event`                            | structured category and transcript evidence                                 | Task 7              |
| `coach.suggestion`                       | suggestion, evidence segments, sources, insufficiency flag                  | Task 10             |
| `analysis.started`, `analysis.completed` | `analysis_version`                                                          | Task 12             |
| `analysis.failed`                        | version, code, message, retryability                                        | Task 12             |

Future event models are defined now so Python and TypeScript agree on their
discriminators. Their producing features are not implemented in Task 1.

## Transcript segment payload

Partial and final transcript events share this shape:

```json
{
  "segment_id": "stable-segment-id",
  "order": 3,
  "revision": 2,
  "text": "Your pricing is higher than expected.",
  "speaker_id": null,
  "speaker_role": "unknown",
  "start_ms": null,
  "end_ms": null,
  "language": null
}
```

- `segment_id` remains stable when a partial is revised or becomes final.
- `revision` increases for replacement content.
- `order` is normalized audio-turn order. It is independent of envelope `seq`
  because provider final completions may arrive out of order.
- Partial content replaces the currently displayed partial for that segment.
- A final replaces that partial and enters durable context once.
- Unavailable speaker, timing, and language values remain `null`/`unknown` and
  are never guessed.

## Errors and WebSocket close codes

Recoverable command errors are ordinary typed `error` events and keep the
socket open. Before WebSocket acceptance, these close codes are used:

| Code | Meaning                                                  |
| ---: | -------------------------------------------------------- |
| 4403 | Missing or disallowed browser Origin                     |
| 4404 | Call ID does not exist in this worker                    |
| 4409 | Session is connected, terminal, or otherwise unavailable |

Binary frames currently produce recoverable `audio_not_supported` errors. Task
2 will replace that behavior with bounded transport diagnostics. Control text
larger than `LIVE_MAX_CONTROL_MESSAGE_BYTES` produces `command_too_large`.

## Bounds and deployment assumptions

The Task 1 defaults are configurable in the backend environment:

```env
ALLOWED_ORIGINS=http://localhost:5173
MAX_ACTIVE_LIVE_CALLS=10
MAX_RETAINED_LIVE_CALLS=100
LIVE_OUTBOUND_QUEUE_SIZE=64
LIVE_COMMAND_HISTORY_SIZE=512
LIVE_MAX_CONTROL_MESSAGE_BYTES=16384
LIVE_QUEUE_PUT_TIMEOUT_MS=1000
```

The store, command idempotency records, queues, and writer tasks live in one
backend process. Terminal process-local sessions and per-session command IDs
are retained only up to their configured bounds; PostgreSQL history comes in a
later task. Run one Uvicorn worker. Multiple calls in that worker are isolated,
but another process cannot see or resume them. Redis will not change ownership
of active sockets/provider connections when introduced later.
