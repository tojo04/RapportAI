import pytest
from pydantic import ValidationError

from app.models.analysis import (
    AnalyzeCallResponse,
    CallAnalysis,
    ObjectionResponse,
    ScoreBreakdown,
    ScoreResult,
)


def analysis_data() -> dict[str, object]:
    return {
        "summary": "The customer needs faster weekly reporting.",
        "customer_needs": ["Automate weekly reports"],
        "questions_asked": ["How long does reporting take today?"],
        "objections": [
            {
                "objection": "The proposed plan may be too expensive.",
                "response": "The salesperson offered a smaller plan.",
            }
        ],
        "follow_up_actions": ["Send a proposal by Friday"],
        "sentiment": "positive",
        "next_step_confirmed": True,
        "objection_handling_quality": 4,
        "discovery_quality": 5,
        "communication_clarity": 4,
    }


def score_data() -> dict[str, object]:
    return {
        "total": 91,
        "category": "Excellent",
        "breakdown": {
            "discovery": 25,
            "objection_handling": 20,
            "communication_clarity": 16,
            "confirmed_next_step": 20,
            "follow_up_actions": 10,
        },
    }


def test_valid_analyze_call_response() -> None:
    response = AnalyzeCallResponse.model_validate(
        {
            "transcript": "Salesperson: What problem are you trying to solve?",
            "analysis": analysis_data(),
            "score": score_data(),
        }
    )

    assert response.analysis.sentiment == "positive"
    assert response.analysis.objections[0].response is not None
    assert response.score.total == 91
    assert response.score.breakdown.discovery == 25


def test_objection_can_have_no_response() -> None:
    objection = ObjectionResponse(
        objection="The price is too high.",
        response=None,
    )

    assert objection.response is None


def test_invalid_sentiment_is_rejected() -> None:
    data = analysis_data()
    data["sentiment"] = "optimistic"

    with pytest.raises(ValidationError):
        CallAnalysis.model_validate(data)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("objection_handling_quality", -1),
        ("objection_handling_quality", 6),
        ("discovery_quality", -1),
        ("discovery_quality", 6),
        ("communication_clarity", -1),
        ("communication_clarity", 6),
    ],
)
def test_quality_rating_bounds_are_enforced(
    field_name: str,
    invalid_value: int,
) -> None:
    data = analysis_data()
    data[field_name] = invalid_value

    with pytest.raises(ValidationError):
        CallAnalysis.model_validate(data)


@pytest.mark.parametrize("invalid_total", [-1, 101])
def test_invalid_score_total_is_rejected(invalid_total: int) -> None:
    data = score_data()
    data["total"] = invalid_total

    with pytest.raises(ValidationError):
        ScoreResult.model_validate(data)


def test_invalid_score_category_is_rejected() -> None:
    data = score_data()
    data["category"] = "Average"

    with pytest.raises(ValidationError):
        ScoreResult.model_validate(data)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("discovery", 26),
        ("objection_handling", -1),
        ("communication_clarity", 21),
        ("confirmed_next_step", 21),
        ("follow_up_actions", 11),
    ],
)
def test_score_breakdown_bounds_are_enforced(
    field_name: str,
    invalid_value: int,
) -> None:
    data = score_data()["breakdown"]
    assert isinstance(data, dict)
    data[field_name] = invalid_value

    with pytest.raises(ValidationError):
        ScoreBreakdown.model_validate(data)


@pytest.mark.parametrize("empty_value", ["", "   "])
def test_empty_summary_is_rejected(empty_value: str) -> None:
    data = analysis_data()
    data["summary"] = empty_value

    with pytest.raises(ValidationError):
        CallAnalysis.model_validate(data)


@pytest.mark.parametrize("empty_value", ["", "   "])
def test_empty_objection_is_rejected(empty_value: str) -> None:
    with pytest.raises(ValidationError):
        ObjectionResponse(objection=empty_value, response=None)


@pytest.mark.parametrize("empty_value", ["", "   "])
def test_empty_transcript_is_rejected(empty_value: str) -> None:
    with pytest.raises(ValidationError):
        AnalyzeCallResponse.model_validate(
            {
                "transcript": empty_value,
                "analysis": analysis_data(),
                "score": score_data(),
            }
        )


def test_unknown_fields_are_rejected() -> None:
    data = analysis_data()
    data["unsupported_field"] = "not part of the API contract"

    with pytest.raises(ValidationError):
        CallAnalysis.model_validate(data)
