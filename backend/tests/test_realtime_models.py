from pydantic import ValidationError
import pytest

from app.models.realtime import (
    CLIENT_COMMAND_ADAPTER,
    SERVER_EVENT_ADAPTER,
)


def test_valid_start_command_is_discriminated() -> None:
    command = CLIENT_COMMAND_ADAPTER.validate_python(
        {
            "protocol_version": 1,
            "command_id": "command-1",
            "type": "start",
            "payload": {},
        }
    )

    assert command.type == "start"
    assert command.command_id == "command-1"


@pytest.mark.parametrize(
    "override",
    [
        {"protocol_version": 2},
        {"command_id": ""},
        {"type": "unknown"},
        {"payload": {"unexpected": True}},
    ],
)
def test_invalid_client_command_is_rejected(
    override: dict[str, object],
) -> None:
    data: dict[str, object] = {
        "protocol_version": 1,
        "command_id": "command-1",
        "type": "start",
        "payload": {},
    }
    data.update(override)

    with pytest.raises(ValidationError):
        CLIENT_COMMAND_ADAPTER.validate_python(data)


def test_transcript_segment_order_is_separate_from_event_sequence() -> None:
    partial = SERVER_EVENT_ADAPTER.validate_python(
        {
            "protocol_version": 1,
            "event_id": "event-10",
            "call_id": "call-1",
            "seq": 10,
            "type": "transcript.partial",
            "emitted_at": "2026-09-30T08:00:00Z",
            "payload": {
                "segment_id": "segment-3",
                "order": 3,
                "revision": 1,
                "text": "Your price",
                "speaker_id": None,
                "speaker_role": "unknown",
                "start_ms": None,
                "end_ms": None,
                "language": None,
            },
        }
    )
    final = SERVER_EVENT_ADAPTER.validate_python(
        {
            **partial.model_dump(mode="json"),
            "event_id": "event-12",
            "seq": 12,
            "type": "transcript.final",
            "payload": {
                **partial.payload.model_dump(),
                "revision": 2,
                "text": "Your price is higher than expected.",
            },
        }
    )

    assert partial.seq == 10
    assert final.seq == 12
    assert partial.payload.order == final.payload.order == 3
    assert partial.payload.segment_id == final.payload.segment_id


def test_server_event_rejects_unknown_payload_fields() -> None:
    with pytest.raises(ValidationError):
        SERVER_EVENT_ADAPTER.validate_python(
            {
                "protocol_version": 1,
                "event_id": "event-1",
                "call_id": "call-1",
                "seq": 1,
                "type": "session.ready",
                "emitted_at": "2026-09-30T08:00:00Z",
                "payload": {
                    "state": "connecting",
                    "unexpected": True,
                },
            }
        )


@pytest.mark.parametrize(
    "audio",
    [
        {
            "transport": "pcm_s16le",
            "sample_rate_hz": 48_000,
            "channels": 1,
            "frame_duration_ms": 100,
        },
        {
            "transport": "pcm_s16le",
            "sample_rate_hz": 24_000,
            "channels": 2,
            "frame_duration_ms": 100,
        },
        {
            "transport": "pcm_s16le",
            "sample_rate_hz": 24_000,
            "channels": 1,
            "frame_duration_ms": 10,
        },
    ],
)
def test_invalid_pcm_metadata_is_rejected(
    audio: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        CLIENT_COMMAND_ADAPTER.validate_python(
            {
                "protocol_version": 1,
                "command_id": "start-1",
                "type": "start",
                "payload": {"audio": audio},
            }
        )
