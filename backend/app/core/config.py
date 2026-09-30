import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Environment-backed application settings."""

    openai_api_key: str | None = field(repr=False)
    openai_transcription_model: str | None
    openai_analysis_model: str | None
    max_upload_mb: int
    frontend_origin: str
    allowed_origins: tuple[str, ...] = ()
    max_active_live_calls: int = 10
    max_retained_live_calls: int = 100
    live_outbound_queue_size: int = 64
    live_command_history_size: int = 512
    live_max_control_message_bytes: int = 16_384
    live_queue_put_timeout_ms: int = 1_000
    live_max_audio_frame_bytes: int = 262_144
    live_audio_ack_every_frames: int = 4
    live_max_call_seconds: int = 1_800
    live_stt_model: str = "gpt-live-transcribe"

    @property
    def browser_origins(self) -> tuple[str, ...]:
        """Return the explicit browser origins used by CORS and WebSockets."""

        return self.allowed_origins or (self.frontend_origin,)


def _optional_environment_value(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _positive_integer_environment_value(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer.") from exc

    if value <= 0:
        raise ValueError(f"{name} must be a positive integer.")

    return value


def _allowed_origins(frontend_origin: str) -> tuple[str, ...]:
    configured = os.getenv("ALLOWED_ORIGINS", "")
    origins = tuple(
        origin.strip() for origin in configured.split(",") if origin.strip()
    )
    return origins or (frontend_origin,)


@lru_cache
def get_settings() -> Settings:
    frontend_origin = os.getenv(
        "FRONTEND_ORIGIN",
        "http://localhost:5173",
    ).strip()

    normalized_frontend_origin = frontend_origin or "http://localhost:5173"

    return Settings(
        openai_api_key=_optional_environment_value("OPENAI_API_KEY"),
        openai_transcription_model=_optional_environment_value(
            "OPENAI_TRANSCRIPTION_MODEL"
        ),
        openai_analysis_model=_optional_environment_value(
            "OPENAI_ANALYSIS_MODEL"
        ),
        max_upload_mb=_positive_integer_environment_value("MAX_UPLOAD_MB", 20),
        frontend_origin=normalized_frontend_origin,
        allowed_origins=_allowed_origins(normalized_frontend_origin),
        max_active_live_calls=_positive_integer_environment_value(
            "MAX_ACTIVE_LIVE_CALLS",
            10,
        ),
        max_retained_live_calls=_positive_integer_environment_value(
            "MAX_RETAINED_LIVE_CALLS",
            100,
        ),
        live_outbound_queue_size=_positive_integer_environment_value(
            "LIVE_OUTBOUND_QUEUE_SIZE",
            64,
        ),
        live_command_history_size=_positive_integer_environment_value(
            "LIVE_COMMAND_HISTORY_SIZE",
            512,
        ),
        live_max_control_message_bytes=_positive_integer_environment_value(
            "LIVE_MAX_CONTROL_MESSAGE_BYTES",
            16_384,
        ),
        live_queue_put_timeout_ms=_positive_integer_environment_value(
            "LIVE_QUEUE_PUT_TIMEOUT_MS",
            1_000,
        ),
        live_max_audio_frame_bytes=_positive_integer_environment_value(
            "LIVE_MAX_AUDIO_FRAME_BYTES",
            262_144,
        ),
        live_audio_ack_every_frames=_positive_integer_environment_value(
            "LIVE_AUDIO_ACK_EVERY_FRAMES",
            4,
        ),
        live_max_call_seconds=_positive_integer_environment_value(
            "LIVE_MAX_CALL_SECONDS",
            1_800,
        ),
        live_stt_model=(
            os.getenv("LIVE_STT_MODEL", "gpt-live-transcribe").strip()
            or "gpt-live-transcribe"
        ),
    )
