from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from openai import OpenAIError

from app.core.config import Settings
from app.models.analysis import CallAnalysis
from app.services.analysis import (
    ANALYSIS_INSTRUCTIONS,
    AnalysisServiceError,
    analyze_transcript,
)


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
        summary="The customer wants to automate weekly reports.",
        customer_needs=["Automated weekly reporting"],
        questions_asked=["How long does reporting take today?"],
        objections=[],
        follow_up_actions=["Send a proposal"],
        sentiment="positive",
        next_step_confirmed=True,
        objection_handling_quality=3,
        discovery_quality=5,
        communication_clarity=4,
    )


def test_successful_analysis_returns_validated_model() -> None:
    client = MagicMock()
    expected_analysis = valid_analysis()
    client.responses.parse.return_value = SimpleNamespace(
        output_parsed=expected_analysis
    )

    result = analyze_transcript(
        "  Salesperson: What problem are you trying to solve?  ",
        client=client,
        settings=make_settings(),
    )

    assert result == expected_analysis
    client.responses.parse.assert_called_once_with(
        model="test-analysis-model",
        input=[
            {"role": "system", "content": ANALYSIS_INSTRUCTIONS},
            {
                "role": "user",
                "content": "Salesperson: What problem are you trying to solve?",
            },
        ],
        text_format=CallAnalysis,
    )


@pytest.mark.parametrize("transcript", ["", "   \n\t"])
def test_empty_transcript_is_rejected(transcript: str) -> None:
    client = MagicMock()

    with pytest.raises(AnalysisServiceError, match="must not be empty"):
        analyze_transcript(
            transcript,
            client=client,
            settings=make_settings(),
        )

    client.responses.parse.assert_not_called()


def test_sdk_failure_is_translated_without_internal_details() -> None:
    client = MagicMock()
    client.responses.parse.side_effect = OpenAIError("private SDK detail")

    with pytest.raises(AnalysisServiceError) as error:
        analyze_transcript(
            "A valid transcript.",
            client=client,
            settings=make_settings(),
        )

    assert str(error.value) == "Transcript analysis failed. Please try again."
    assert "private SDK detail" not in str(error.value)


def test_invalid_structured_output_is_rejected() -> None:
    client = MagicMock()
    invalid_analysis = valid_analysis().model_dump()
    invalid_analysis["sentiment"] = "optimistic"
    client.responses.parse.return_value = SimpleNamespace(
        output_parsed=invalid_analysis
    )

    with pytest.raises(
        AnalysisServiceError,
        match="invalid structured output",
    ):
        analyze_transcript(
            "A valid transcript.",
            client=client,
            settings=make_settings(),
        )


def test_missing_analysis_model_is_reported_before_api_call() -> None:
    client = MagicMock()
    settings = make_settings()
    settings = Settings(
        openai_api_key=settings.openai_api_key,
        openai_transcription_model=settings.openai_transcription_model,
        openai_analysis_model=None,
        max_upload_mb=settings.max_upload_mb,
        frontend_origin=settings.frontend_origin,
    )

    with pytest.raises(
        AnalysisServiceError,
        match="OPENAI_ANALYSIS_MODEL",
    ):
        analyze_transcript(
            "A valid transcript.",
            client=client,
            settings=settings,
        )

    client.responses.parse.assert_not_called()


def test_missing_api_key_is_reported_when_no_client_is_injected() -> None:
    with pytest.raises(AnalysisServiceError, match="OPENAI_API_KEY"):
        analyze_transcript(
            "A valid transcript.",
            settings=make_settings(),
        )
