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


@lru_cache
def get_settings() -> Settings:
    frontend_origin = os.getenv(
        "FRONTEND_ORIGIN",
        "http://localhost:5173",
    ).strip()

    return Settings(
        openai_api_key=_optional_environment_value("OPENAI_API_KEY"),
        openai_transcription_model=_optional_environment_value(
            "OPENAI_TRANSCRIPTION_MODEL"
        ),
        openai_analysis_model=_optional_environment_value(
            "OPENAI_ANALYSIS_MODEL"
        ),
        max_upload_mb=_positive_integer_environment_value("MAX_UPLOAD_MB", 20),
        frontend_origin=frontend_origin or "http://localhost:5173",
    )
