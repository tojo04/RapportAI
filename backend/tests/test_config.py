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
    ):
        monkeypatch.delenv(name, raising=False)

    settings = get_settings()

    assert settings.openai_api_key is None
    assert settings.openai_transcription_model is None
    assert settings.openai_analysis_model is None
    assert settings.max_upload_mb == 20
    assert settings.frontend_origin == "http://localhost:5173"


def test_settings_read_and_trim_environment_values(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", " test-key ")
    monkeypatch.setenv("OPENAI_TRANSCRIPTION_MODEL", " transcribe-model ")
    monkeypatch.setenv("OPENAI_ANALYSIS_MODEL", " analysis-model ")
    monkeypatch.setenv("MAX_UPLOAD_MB", "12")
    monkeypatch.setenv("FRONTEND_ORIGIN", " http://example.test ")

    settings = get_settings()

    assert settings.openai_api_key == "test-key"
    assert settings.openai_transcription_model == "transcribe-model"
    assert settings.openai_analysis_model == "analysis-model"
    assert settings.max_upload_mb == 12
    assert settings.frontend_origin == "http://example.test"
    assert "test-key" not in repr(settings)


@pytest.mark.parametrize("invalid_value", ["0", "-1", "not-a-number"])
def test_invalid_max_upload_size_is_rejected(
    invalid_value: str,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_MB", invalid_value)

    with pytest.raises(ValueError, match="positive integer"):
        get_settings()
