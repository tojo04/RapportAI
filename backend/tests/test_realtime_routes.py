import asyncio
from collections.abc import Iterator
from dataclasses import replace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.core.config import get_settings
from app.models.realtime import CallState
from app.realtime.sessions import LiveCallStore
from app.services.streaming_transcription import (
    FakeStreamingTranscriber,
    TranscriptEvent,
)
from app.services.sales_detection import FakeSalesEventClassifier, SalesSignalCandidate


ALLOWED_ORIGIN = "http://localhost:5173"
client = TestClient(app)


class TransportOnlyTranscriber(FakeStreamingTranscriber):
    async def flush(self) -> bool:
        return False


class ScriptedTranscriptTranscriber(TransportOnlyTranscriber):
    def __init__(self) -> None:
        super().__init__()
        self._audio_received = asyncio.Event()

    async def send_audio(self, pcm: bytes) -> None:
        await super().send_audio(pcm)
        self._audio_received.set()

    async def events(self):  # type: ignore[no-untyped-def]
        await self._audio_received.wait()
        yield TranscriptEvent(
            kind="partial",
            segment_id="item-1",
            order=0,
            revision=1,
            text="Hello",
            provider_event_id="provider-1",
            provider_item_id="item-1",
        )
        yield TranscriptEvent(
            kind="final",
            segment_id="item-1",
            order=0,
            revision=2,
            text="Hello there",
            provider_event_id="provider-2",
            provider_item_id="item-1",
        )


@pytest.fixture(autouse=True)
def isolated_live_call_store() -> Iterator[LiveCallStore]:
    original_store = app.state.live_call_store
    original_factory = getattr(
        app.state,
        "streaming_transcriber_factory",
        None,
    )
    original_classifier_factory = getattr(
        app.state,
        "sales_event_classifier_factory",
        None,
    )
    store = LiveCallStore(max_active_calls=10)
    app.state.live_call_store = store
    app.state.streaming_transcriber_factory = TransportOnlyTranscriber
    app.state.sales_event_classifier_factory = None
    yield store
    app.state.live_call_store = original_store
    app.state.streaming_transcriber_factory = original_factory
    app.state.sales_event_classifier_factory = original_classifier_factory


def create_call() -> dict[str, object]:
    response = client.post("/api/calls")
    assert response.status_code == 201
    return response.json()


def command(command_id: str, command_type: str) -> dict[str, object]:
    return {
        "protocol_version": 1,
        "command_id": command_id,
        "type": command_type,
        "payload": {},
    }


def pcm_start(command_id: str = "start-1") -> dict[str, object]:
    return {
        "protocol_version": 1,
        "command_id": command_id,
        "type": "start",
        "payload": {
            "audio": {
                "transport": "pcm_s16le",
                "sample_rate_hz": 24_000,
                "channels": 1,
                "frame_duration_ms": 100,
            }
        },
    }


def test_create_start_ping_and_stop_call() -> None:
    created = create_call()
    call_id = str(created["call_id"])
    UUID(call_id)
    assert created == {
        "protocol_version": 1,
        "call_id": call_id,
        "websocket_path": f"/ws/calls/{call_id}",
        "state": "idle",
        "limits": {
            "max_call_seconds": 1_800,
            "max_frame_bytes": 262_144,
            "ack_every_frames": 4,
        },
    }

    with client.websocket_connect(
        str(created["websocket_path"]),
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "session.ready"
        assert ready["payload"] == {"state": "connecting"}

        websocket.send_json(command("start-1", "start"))
        started = websocket.receive_json()
        assert started["type"] == "call.started"
        assert started["payload"] == {
            "state": "live",
            "command_id": "start-1",
            "duplicate": False,
        }

        websocket.send_json(command("ping-1", "ping"))
        pong = websocket.receive_json()
        assert pong["type"] == "pong"
        assert pong["payload"]["state"] == "live"
        assert pong["payload"]["command_id"] == "ping-1"

        websocket.send_json(command("stop-1", "stop"))
        stopping = websocket.receive_json()
        ended = websocket.receive_json()
        assert stopping["type"] == "call.stopping"
        assert ended["type"] == "call.ended"
        assert ended["payload"]["state"] == "ended"
        assert ended["payload"]["transcript_complete"] is True

        sequences = [
            ready["seq"],
            started["seq"],
            pong["seq"],
            stopping["seq"],
            ended["seq"],
        ]
        assert sequences == sorted(sequences)
        assert len(set(sequences)) == len(sequences)
        assert sequences[0] == 1


def test_duplicate_start_and_stop_are_idempotent() -> None:
    created = create_call()
    with client.websocket_connect(
        str(created["websocket_path"]),
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        websocket.receive_json()
        websocket.send_json(command("start-1", "start"))
        websocket.receive_json()

        websocket.send_json(command("start-1", "start"))
        duplicate_start = websocket.receive_json()
        assert duplicate_start["type"] == "call.started"
        assert duplicate_start["payload"]["duplicate"] is True

        websocket.send_json(command("stop-1", "stop"))
        websocket.receive_json()
        websocket.receive_json()

        websocket.send_json(command("stop-1", "stop"))
        duplicate_stop = websocket.receive_json()
        assert duplicate_stop["type"] == "call.ended"
        assert duplicate_stop["payload"]["duplicate"] is True

        websocket.send_json(command("stop-2", "stop"))
        later_stop = websocket.receive_json()
        assert later_stop["type"] == "call.ended"
        assert later_stop["payload"]["duplicate"] is True


def test_illegal_state_and_command_id_conflict_return_errors() -> None:
    created = create_call()
    with client.websocket_connect(
        str(created["websocket_path"]),
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        websocket.receive_json()
        websocket.send_json(command("shared", "start"))
        websocket.receive_json()

        websocket.send_json(command("start-2", "start"))
        illegal = websocket.receive_json()
        assert illegal["type"] == "error"
        assert illegal["payload"]["code"] == "illegal_state"

        websocket.send_json(command("shared", "stop"))
        conflict = websocket.receive_json()
        assert conflict["type"] == "error"
        assert conflict["payload"]["code"] == "command_id_conflict"


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ("not-json", "malformed_command"),
        (
            '{"protocol_version":2,"command_id":"x","type":"ping","payload":{}}',
            "invalid_protocol_version",
        ),
        (
            '{"protocol_version":1,"command_id":"x","type":"unknown","payload":{}}',
            "malformed_command",
        ),
        (
            '{"command_id":"x","type":"ping","payload":{}}',
            "malformed_command",
        ),
    ],
)
def test_invalid_control_messages_return_typed_errors(
    payload: str,
    expected_code: str,
) -> None:
    created = create_call()
    with client.websocket_connect(
        str(created["websocket_path"]),
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        websocket.receive_json()
        websocket.send_text(payload)
        event = websocket.receive_json()

        assert event["type"] == "error"
        assert event["payload"]["code"] == expected_code


def test_binary_audio_before_start_is_rejected() -> None:
    created = create_call()
    with client.websocket_connect(
        str(created["websocket_path"]),
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        websocket.receive_json()
        websocket.send_bytes(b"not-enabled-yet")
        event = websocket.receive_json()

        assert event["type"] == "error"
        assert event["payload"]["code"] == "audio_not_live"


def test_live_audio_is_counted_and_acknowledged_at_interval() -> None:
    created = create_call()
    with client.websocket_connect(
        str(created["websocket_path"]),
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        websocket.receive_json()
        websocket.send_json(pcm_start())
        websocket.receive_json()

        for _ in range(4):
            websocket.send_bytes(b"\x00\x00\x01\x00")

        ack = websocket.receive_json()
        assert ack["type"] == "audio.ack"
        assert ack["payload"] == {
            "frames_received": 4,
            "bytes_received": 16,
        }


def test_stop_flushes_pending_audio_ack_before_end_events() -> None:
    created = create_call()
    with client.websocket_connect(
        str(created["websocket_path"]),
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        websocket.receive_json()
        websocket.send_json(pcm_start())
        websocket.receive_json()
        websocket.send_bytes(b"\x00\x00\x01\x00")
        websocket.send_json(command("stop-1", "stop"))

        ack = websocket.receive_json()
        stopping = websocket.receive_json()
        ended = websocket.receive_json()
        assert ack["type"] == "audio.ack"
        assert ack["payload"]["frames_received"] == 1
        assert ack["payload"]["bytes_received"] == 4
        assert stopping["type"] == "call.stopping"
        assert ended["type"] == "call.ended"


def test_pcm_audio_emits_partial_then_final_transcript() -> None:
    app.state.streaming_transcriber_factory = ScriptedTranscriptTranscriber
    created = create_call()
    with client.websocket_connect(
        str(created["websocket_path"]),
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        websocket.receive_json()
        websocket.send_json(pcm_start())
        websocket.receive_json()
        websocket.send_bytes(b"\x01\x00" * 2_400)

        partial = websocket.receive_json()
        final = websocket.receive_json()
        assert partial["type"] == "transcript.partial"
        assert partial["payload"]["text"] == "Hello"
        assert final["type"] == "transcript.final"
        assert final["payload"]["text"] == "Hello there"
        assert final["payload"]["speaker_role"] == "unknown"

        websocket.send_json(command("stop-1", "stop"))
        ack = websocket.receive_json()
        stopping = websocket.receive_json()
        ended = websocket.receive_json()
        assert ack["type"] == "audio.ack"
        assert stopping["type"] == "call.stopping"
        assert ended["payload"]["transcript_complete"] is True


def test_final_transcript_emits_validated_sales_signal() -> None:
    app.state.streaming_transcriber_factory = ScriptedTranscriptTranscriber
    app.state.sales_event_classifier_factory = lambda: FakeSalesEventClassifier(
        [
            [
                SalesSignalCandidate(
                    category="question",
                    evidence_segment_ids=["item-1"],
                    evidence_span="Hello there",
                    subject="greeting question",
                    details=[],
                )
            ]
        ]
    )
    created = create_call()
    with client.websocket_connect(
        str(created["websocket_path"]),
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        websocket.receive_json()
        websocket.send_json(pcm_start())
        websocket.receive_json()
        websocket.send_bytes(b"\x01\x00" * 2_400)
        assert websocket.receive_json()["type"] == "transcript.partial"
        assert websocket.receive_json()["type"] == "transcript.final"
        websocket.send_json(command("stop-1", "stop"))
        assert websocket.receive_json()["type"] == "audio.ack"
        assert websocket.receive_json()["type"] == "call.stopping"
        signal = websocket.receive_json()
        ended = websocket.receive_json()
        assert signal["type"] == "sales.event"
        assert signal["payload"]["category"] == "question"
        assert signal["payload"]["evidence_segment_ids"] == ["item-1"]
        assert ended["type"] == "call.ended"


def test_missing_provider_completion_marks_transcript_incomplete() -> None:
    limited_settings = replace(
        get_settings(),
        live_stt_finalization_timeout_ms=10,
    )
    app.dependency_overrides[get_settings] = lambda: limited_settings
    app.state.streaming_transcriber_factory = FakeStreamingTranscriber
    try:
        created = create_call()
        with client.websocket_connect(
            str(created["websocket_path"]),
            headers={"origin": ALLOWED_ORIGIN},
        ) as websocket:
            websocket.receive_json()
            websocket.send_json(pcm_start())
            websocket.receive_json()
            websocket.send_bytes(b"\x01\x00")
            websocket.send_json(command("stop-1", "stop"))

            ack = websocket.receive_json()
            stopping = websocket.receive_json()
            ended = websocket.receive_json()
            assert ack["type"] == "audio.ack"
            assert stopping["type"] == "call.stopping"
            assert ended["payload"] == {
                "state": "interrupted",
                "command_id": "stop-1",
                "duplicate": False,
                "transcript_complete": False,
            }
    finally:
        app.dependency_overrides.clear()


def test_audio_requires_metadata_and_enforces_frame_limit() -> None:
    created = create_call()
    with client.websocket_connect(
        str(created["websocket_path"]),
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        websocket.receive_json()
        websocket.send_json(command("start-1", "start"))
        websocket.receive_json()
        websocket.send_bytes(b"unlabelled")
        missing_metadata = websocket.receive_json()
        assert missing_metadata["payload"]["code"] == "audio_metadata_required"

    created = create_call()
    with client.websocket_connect(
        str(created["websocket_path"]),
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        websocket.receive_json()
        websocket.send_json(pcm_start())
        websocket.receive_json()
        websocket.send_bytes(b"x" * 262_145)
        oversized = websocket.receive_json()
        assert oversized["payload"]["code"] == "audio_frame_too_large"

    created = create_call()
    with client.websocket_connect(
        str(created["websocket_path"]),
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        websocket.receive_json()
        websocket.send_json(pcm_start())
        websocket.receive_json()
        websocket.send_bytes(b"odd")
        misaligned = websocket.receive_json()
        assert misaligned["payload"]["code"] == "audio_frame_misaligned"


def test_server_ends_call_at_duration_limit() -> None:
    limited_settings = replace(get_settings(), live_max_call_seconds=1)
    app.dependency_overrides[get_settings] = lambda: limited_settings

    try:
        created = create_call()
        assert created["limits"]["max_call_seconds"] == 1
        with client.websocket_connect(
            str(created["websocket_path"]),
            headers={"origin": ALLOWED_ORIGIN},
        ) as websocket:
            websocket.receive_json()
            websocket.send_json(pcm_start())
            websocket.receive_json()

            duration_error = websocket.receive_json()
            ended = websocket.receive_json()
            assert duration_error["payload"]["code"] == "call_duration_exceeded"
            assert ended["type"] == "call.ended"
    finally:
        app.dependency_overrides.clear()


def test_oversized_control_message_is_rejected() -> None:
    created = create_call()
    with client.websocket_connect(
        str(created["websocket_path"]),
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        websocket.receive_json()
        websocket.send_text("x" * 16_385)
        event = websocket.receive_json()

        assert event["type"] == "error"
        assert event["payload"]["code"] == "command_too_large"


def test_unknown_call_and_disallowed_origin_are_rejected() -> None:
    with pytest.raises(WebSocketDisconnect) as missing:
        with client.websocket_connect(
            "/ws/calls/not-a-call",
            headers={"origin": ALLOWED_ORIGIN},
        ):
            pass
    assert missing.value.code == 4404

    created = create_call()
    with pytest.raises(WebSocketDisconnect) as forbidden:
        with client.websocket_connect(
            str(created["websocket_path"]),
            headers={"origin": "https://untrusted.example"},
        ):
            pass
    assert forbidden.value.code == 4403


def test_disconnect_marks_call_interrupted_and_cleans_writer(
    isolated_live_call_store: LiveCallStore,
) -> None:
    created = create_call()
    call_id = str(created["call_id"])
    with client.websocket_connect(
        str(created["websocket_path"]),
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        websocket.receive_json()
        websocket.send_json(command("start-1", "start"))
        websocket.receive_json()

    session = asyncio.run(isolated_live_call_store.get(call_id))
    assert session is not None
    assert session.state is CallState.INTERRUPTED
    assert session.connected is False
    assert session.writer_task is None
    assert session.outbound_queue is None


def test_disconnect_closes_live_transcriber() -> None:
    instances: list[TransportOnlyTranscriber] = []

    def factory() -> TransportOnlyTranscriber:
        instance = TransportOnlyTranscriber()
        instances.append(instance)
        return instance

    app.state.streaming_transcriber_factory = factory
    created = create_call()
    with client.websocket_connect(
        str(created["websocket_path"]),
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        websocket.receive_json()
        websocket.send_json(pcm_start())
        websocket.receive_json()
        websocket.send_bytes(b"\x01\x00")

    assert len(instances) == 1
    assert instances[0].closed is True


def test_ended_call_cannot_accept_a_new_socket(
    isolated_live_call_store: LiveCallStore,
) -> None:
    created = create_call()
    path = str(created["websocket_path"])
    with client.websocket_connect(
        path,
        headers={"origin": ALLOWED_ORIGIN},
    ) as websocket:
        websocket.receive_json()
        websocket.send_json(command("stop-1", "stop"))
        websocket.receive_json()
        websocket.receive_json()

    session = asyncio.run(
        isolated_live_call_store.get(str(created["call_id"]))
    )
    assert session is not None
    assert session.state is CallState.ENDED
    assert session.writer_task is None
    assert session.outbound_queue is None

    with pytest.raises(WebSocketDisconnect) as unavailable:
        with client.websocket_connect(
            path,
            headers={"origin": ALLOWED_ORIGIN},
        ):
            pass
    assert unavailable.value.code == 4409
