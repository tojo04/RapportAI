from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from openai import OpenAIError

from app.core.config import Settings
from app.services.transcription import (
    TranscriptionServiceError,
    transcribe_audio,
)


def make_settings() -> Settings:
    return Settings(
        openai_api_key=None,
        openai_transcription_model="test-transcription-model",
        openai_analysis_model="test-analysis-model",
        max_upload_mb=20,
        frontend_origin="http://localhost:5173",
    )


@pytest.mark.parametrize("extension", [".mp3", ".wav"])
def test_successful_transcription(
    extension: str,
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / f"call{extension}"
    audio_path.write_bytes(b"test audio bytes")
    client = MagicMock()
    client.audio.transcriptions.create.return_value = SimpleNamespace(
        text="  A useful transcript.  "
    )

    transcript = transcribe_audio(
        audio_path,
        client=client,
        settings=make_settings(),
    )

    assert transcript == "A useful transcript."
    call = client.audio.transcriptions.create.call_args
    assert call.kwargs["model"] == "test-transcription-model"
    assert call.kwargs["file"].name == str(audio_path)
    assert call.kwargs["file"].closed is True


def test_unsupported_extension_is_rejected(tmp_path: Path) -> None:
    audio_path = tmp_path / "call.m4a"
    audio_path.write_bytes(b"test audio bytes")
    client = MagicMock()

    with pytest.raises(TranscriptionServiceError, match="Only MP3 and WAV"):
        transcribe_audio(
            audio_path,
            client=client,
            settings=make_settings(),
        )

    client.audio.transcriptions.create.assert_not_called()


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    client = MagicMock()

    with pytest.raises(TranscriptionServiceError, match="does not exist"):
        transcribe_audio(
            tmp_path / "missing.mp3",
            client=client,
            settings=make_settings(),
        )

    client.audio.transcriptions.create.assert_not_called()


def test_empty_file_is_rejected(tmp_path: Path) -> None:
    audio_path = tmp_path / "empty.wav"
    audio_path.touch()
    client = MagicMock()

    with pytest.raises(TranscriptionServiceError, match="must not be empty"):
        transcribe_audio(
            audio_path,
            client=client,
            settings=make_settings(),
        )

    client.audio.transcriptions.create.assert_not_called()


@pytest.mark.parametrize("empty_text", ["", "  \n\t"])
def test_empty_transcription_response_is_rejected(
    empty_text: str,
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "call.mp3"
    audio_path.write_bytes(b"test audio bytes")
    client = MagicMock()
    client.audio.transcriptions.create.return_value = SimpleNamespace(
        text=empty_text
    )

    with pytest.raises(
        TranscriptionServiceError,
        match="returned an empty transcript",
    ):
        transcribe_audio(
            audio_path,
            client=client,
            settings=make_settings(),
        )


def test_sdk_failure_is_translated_without_internal_details(
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "call.wav"
    audio_path.write_bytes(b"test audio bytes")
    client = MagicMock()
    client.audio.transcriptions.create.side_effect = OpenAIError(
        "private SDK detail"
    )

    with pytest.raises(TranscriptionServiceError) as error:
        transcribe_audio(
            audio_path,
            client=client,
            settings=make_settings(),
        )

    assert str(error.value) == "Audio transcription failed. Please try again."
    assert "private SDK detail" not in str(error.value)


def test_missing_transcription_model_is_reported_before_api_call(
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "call.mp3"
    audio_path.write_bytes(b"test audio bytes")
    client = MagicMock()
    settings = make_settings()
    settings = Settings(
        openai_api_key=settings.openai_api_key,
        openai_transcription_model=None,
        openai_analysis_model=settings.openai_analysis_model,
        max_upload_mb=settings.max_upload_mb,
        frontend_origin=settings.frontend_origin,
    )

    with pytest.raises(
        TranscriptionServiceError,
        match="OPENAI_TRANSCRIPTION_MODEL",
    ):
        transcribe_audio(
            audio_path,
            client=client,
            settings=settings,
        )

    client.audio.transcriptions.create.assert_not_called()


def test_missing_api_key_is_reported_when_no_client_is_injected(
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "call.wav"
    audio_path.write_bytes(b"test audio bytes")

    with pytest.raises(TranscriptionServiceError, match="OPENAI_API_KEY"):
        transcribe_audio(
            audio_path,
            settings=make_settings(),
        )
