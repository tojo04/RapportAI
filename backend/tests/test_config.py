from collections.abc import Iterator

import pytest
from pytest import MonkeyPatch

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_use_safe_defaults(monkeypatch: MonkeyPatch) -> None:
    for name in (
        "OPENAI_API_KEY",
        "OPENAI_TRANSCRIPTION_MODEL",
        "OPENAI_ANALYSIS_MODEL",
        "MAX_UPLOAD_MB",
        "FRONTEND_ORIGIN",
        "ALLOWED_ORIGINS",
        "MAX_ACTIVE_LIVE_CALLS",
        "MAX_RETAINED_LIVE_CALLS",
        "LIVE_OUTBOUND_QUEUE_SIZE",
        "LIVE_COMMAND_HISTORY_SIZE",
        "LIVE_MAX_CONTROL_MESSAGE_BYTES",
        "LIVE_QUEUE_PUT_TIMEOUT_MS",
        "LIVE_MAX_AUDIO_FRAME_BYTES",
        "LIVE_AUDIO_ACK_EVERY_FRAMES",
        "LIVE_MAX_CALL_SECONDS",
        "LIVE_STT_MODEL",
        "LIVE_STT_FINALIZATION_TIMEOUT_MS",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = get_settings()

    assert settings.openai_api_key is None
    assert settings.openai_transcription_model is None
    assert settings.openai_analysis_model is None
    assert settings.max_upload_mb == 20
    assert settings.frontend_origin == "http://localhost:5173"
    assert settings.browser_origins == ("http://localhost:5173",)
    assert settings.max_active_live_calls == 10
    assert settings.max_retained_live_calls == 100
    assert settings.live_outbound_queue_size == 64
    assert settings.live_command_history_size == 512
    assert settings.live_max_control_message_bytes == 16_384
    assert settings.live_queue_put_timeout_ms == 1_000
    assert settings.live_max_audio_frame_bytes == 262_144
    assert settings.live_audio_ack_every_frames == 4
    assert settings.live_max_call_seconds == 1_800
    assert settings.live_stt_model == "gpt-live-transcribe"
    assert settings.live_stt_finalization_timeout_ms == 2_000


def test_settings_read_and_trim_environment_values(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", " test-key ")
    monkeypatch.setenv("OPENAI_TRANSCRIPTION_MODEL", " transcribe-model ")
    monkeypatch.setenv("OPENAI_ANALYSIS_MODEL", " analysis-model ")
    monkeypatch.setenv("MAX_UPLOAD_MB", "12")
    monkeypatch.setenv("FRONTEND_ORIGIN", " http://example.test ")
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        " http://example.test, https://second.example.test ",
    )
    monkeypatch.setenv("MAX_ACTIVE_LIVE_CALLS", "4")
    monkeypatch.setenv("MAX_RETAINED_LIVE_CALLS", "40")
    monkeypatch.setenv("LIVE_OUTBOUND_QUEUE_SIZE", "20")
    monkeypatch.setenv("LIVE_COMMAND_HISTORY_SIZE", "50")
    monkeypatch.setenv("LIVE_MAX_CONTROL_MESSAGE_BYTES", "2048")
    monkeypatch.setenv("LIVE_QUEUE_PUT_TIMEOUT_MS", "500")
    monkeypatch.setenv("LIVE_MAX_AUDIO_FRAME_BYTES", "65536")
    monkeypatch.setenv("LIVE_AUDIO_ACK_EVERY_FRAMES", "8")
    monkeypatch.setenv("LIVE_MAX_CALL_SECONDS", "900")
    monkeypatch.setenv("LIVE_STT_MODEL", " custom-live-transcribe ")
    monkeypatch.setenv("LIVE_STT_FINALIZATION_TIMEOUT_MS", "750")

    settings = get_settings()

    assert settings.openai_api_key == "test-key"
    assert settings.openai_transcription_model == "transcribe-model"
    assert settings.openai_analysis_model == "analysis-model"
    assert settings.max_upload_mb == 12
    assert settings.frontend_origin == "http://example.test"
    assert settings.browser_origins == (
        "http://example.test",
        "https://second.example.test",
    )
    assert settings.max_active_live_calls == 4
    assert settings.max_retained_live_calls == 40
    assert settings.live_outbound_queue_size == 20
    assert settings.live_command_history_size == 50
    assert settings.live_max_control_message_bytes == 2_048
    assert settings.live_queue_put_timeout_ms == 500
    assert settings.live_max_audio_frame_bytes == 65_536
    assert settings.live_audio_ack_every_frames == 8
    assert settings.live_max_call_seconds == 900
    assert settings.live_stt_model == "custom-live-transcribe"
    assert settings.live_stt_finalization_timeout_ms == 750
    assert "test-key" not in repr(settings)


@pytest.mark.parametrize("invalid_value", ["0", "-1", "not-a-number"])
def test_invalid_max_upload_size_is_rejected(
    invalid_value: str,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_MB", invalid_value)

    with pytest.raises(ValueError, match="positive integer"):
        get_settings()


@pytest.mark.parametrize(
    "name",
    [
        "MAX_ACTIVE_LIVE_CALLS",
        "MAX_RETAINED_LIVE_CALLS",
        "LIVE_OUTBOUND_QUEUE_SIZE",
        "LIVE_COMMAND_HISTORY_SIZE",
        "LIVE_MAX_CONTROL_MESSAGE_BYTES",
        "LIVE_QUEUE_PUT_TIMEOUT_MS",
        "LIVE_MAX_AUDIO_FRAME_BYTES",
        "LIVE_AUDIO_ACK_EVERY_FRAMES",
        "LIVE_MAX_CALL_SECONDS",
        "LIVE_STT_FINALIZATION_TIMEOUT_MS",
    ],
)
def test_invalid_live_limit_is_rejected(
    name: str,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv(name, "0")

    with pytest.raises(ValueError, match="positive integer"):
        get_settings()
