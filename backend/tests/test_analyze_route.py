from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.api import routes
from app.core.config import Settings, get_settings
from app.main import app
from app.models.analysis import CallAnalysis
from app.services.analysis import AnalysisServiceError
from app.services.transcription import TranscriptionServiceError


client = TestClient(app)


def make_settings() -> Settings:
    return Settings(
        openai_api_key=None,
        openai_transcription_model="test-transcription-model",
        openai_analysis_model="test-analysis-model",
        max_upload_mb=20,
        frontend_origin="http://localhost:5173",
    )


def valid_analysis() -> CallAnalysis:
    return CallAnalysis(
        summary="The customer wants automated weekly reports.",
        customer_needs=["Automated weekly reporting"],
        questions_asked=["How long does reporting take today?"],
        objections=[
            {
                "objection": "The plan may be too expensive.",
                "response": "The salesperson offered a smaller plan.",
            }
        ],
        follow_up_actions=["Send a proposal"],
        sentiment="positive",
        next_step_confirmed=True,
        objection_handling_quality=4,
        discovery_quality=5,
        communication_clarity=4,
    )


@pytest.fixture(autouse=True)
def override_settings() -> Iterator[Settings]:
    settings = make_settings()
    app.dependency_overrides[get_settings] = lambda: settings
    yield settings
    app.dependency_overrides.clear()


def test_successful_request_returns_expected_response_and_cleans_up(
    monkeypatch: MonkeyPatch,
    override_settings: Settings,
) -> None:
    transcription = MagicMock(return_value="A useful transcript.")
    analysis = MagicMock(return_value=valid_analysis())
    monkeypatch.setattr(routes, "transcribe_audio", transcription)
    monkeypatch.setattr(routes, "analyze_transcript", analysis)

    response = client.post(
        "/api/analyze-call",
        files={"file": ("../../unsafe-name.mp3", b"audio bytes", "audio/mpeg")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "transcript": "A useful transcript.",
        "analysis": valid_analysis().model_dump(),
        "score": {
            "total": 91,
            "category": "Excellent",
            "breakdown": {
                "discovery": 25,
                "objection_handling": 20,
                "communication_clarity": 16,
                "confirmed_next_step": 20,
                "follow_up_actions": 10,
            },
        },
    }

    temporary_path = transcription.call_args.args[0]
    assert isinstance(temporary_path, Path)
    assert temporary_path.suffix == ".mp3"
    assert "unsafe-name" not in temporary_path.name
    assert not temporary_path.exists()
    transcription.assert_called_once_with(
        temporary_path,
        settings=override_settings,
    )
    analysis.assert_called_once_with(
        "A useful transcript.",
        settings=override_settings,
    )


def test_unsupported_extension_is_rejected() -> None:
    response = client.post(
        "/api/analyze-call",
        files={"file": ("call.txt", b"not audio", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Only MP3 and WAV files are supported."
    }


def test_mismatched_content_type_is_rejected() -> None:
    response = client.post(
        "/api/analyze-call",
        files={"file": ("call.mp3", b"audio bytes", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "The file content type does not match its extension."
    }


def test_empty_upload_is_rejected() -> None:
    response = client.post(
        "/api/analyze-call",
        files={"file": ("call.wav", b"", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "The uploaded file must not be empty."
    }


def test_oversized_upload_is_rejected(
    monkeypatch: MonkeyPatch,
    override_settings: Settings,
) -> None:
    small_limit = replace(override_settings, max_upload_mb=1)
    app.dependency_overrides[get_settings] = lambda: small_limit
    transcription = MagicMock()
    monkeypatch.setattr(routes, "transcribe_audio", transcription)

    response = client.post(
        "/api/analyze-call",
        files={
            "file": (
                "call.mp3",
                b"x" * (1024 * 1024 + 1),
                "audio/mpeg",
            )
        },
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "The uploaded file exceeds the configured size limit."
    }
    transcription.assert_not_called()


def test_transcription_failure_becomes_http_error_and_cleans_up(
    monkeypatch: MonkeyPatch,
) -> None:
    transcription = MagicMock(
        side_effect=TranscriptionServiceError(
            "Audio transcription failed. Please try again."
        )
    )
    analysis = MagicMock()
    monkeypatch.setattr(routes, "transcribe_audio", transcription)
    monkeypatch.setattr(routes, "analyze_transcript", analysis)

    response = client.post(
        "/api/analyze-call",
        files={"file": ("call.wav", b"audio bytes", "audio/wav")},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Audio transcription failed. Please try again."
    }
    temporary_path = transcription.call_args.args[0]
    assert not temporary_path.exists()
    analysis.assert_not_called()


def test_analysis_failure_becomes_http_error_and_cleans_up(
    monkeypatch: MonkeyPatch,
) -> None:
    transcription = MagicMock(return_value="A useful transcript.")
    analysis = MagicMock(
        side_effect=AnalysisServiceError(
            "Transcript analysis failed. Please try again."
        )
    )
    monkeypatch.setattr(routes, "transcribe_audio", transcription)
    monkeypatch.setattr(routes, "analyze_transcript", analysis)

    response = client.post(
        "/api/analyze-call",
        files={"file": ("call.mp3", b"audio bytes", "audio/mpeg")},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Transcript analysis failed. Please try again."
    }
    temporary_path = transcription.call_args.args[0]
    assert not temporary_path.exists()
