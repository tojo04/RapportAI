import pytest

from app.models.analysis import CallAnalysis, ScoreCategory
from app.scoring.calculator import calculate_call_score


def make_analysis(**overrides: object) -> CallAnalysis:
    data: dict[str, object] = {
        "summary": "A concise call summary.",
        "customer_needs": [],
        "questions_asked": [],
        "objections": [],
        "follow_up_actions": [],
        "sentiment": "neutral",
        "next_step_confirmed": False,
        "objection_handling_quality": 0,
        "discovery_quality": 0,
        "communication_clarity": 0,
    }
    data.update(overrides)
    return CallAnalysis.model_validate(data)


def test_zero_score() -> None:
    score = calculate_call_score(make_analysis())

    assert score.total == 0
    assert score.category == "Poor"
    assert score.breakdown.model_dump() == {
        "discovery": 0,
        "objection_handling": 0,
        "communication_clarity": 0,
        "confirmed_next_step": 0,
        "follow_up_actions": 0,
    }


def test_maximum_score() -> None:
    score = calculate_call_score(
        make_analysis(
            discovery_quality=5,
            objection_handling_quality=5,
            communication_clarity=5,
            next_step_confirmed=True,
            follow_up_actions=["Send the proposal"],
        )
    )

    assert score.total == 100
    assert score.category == "Excellent"
    assert score.breakdown.model_dump() == {
        "discovery": 25,
        "objection_handling": 25,
        "communication_clarity": 20,
        "confirmed_next_step": 20,
        "follow_up_actions": 10,
    }


@pytest.mark.parametrize(
    ("rating_field", "breakdown_field", "expected_points"),
    [
        ("discovery_quality", "discovery", 5),
        ("objection_handling_quality", "objection_handling", 5),
        ("communication_clarity", "communication_clarity", 4),
    ],
)
def test_quality_component_calculation(
    rating_field: str,
    breakdown_field: str,
    expected_points: int,
) -> None:
    score = calculate_call_score(make_analysis(**{rating_field: 1}))

    assert getattr(score.breakdown, breakdown_field) == expected_points
    assert score.total == expected_points


def test_confirmed_next_step_adds_twenty_points() -> None:
    score = calculate_call_score(make_analysis(next_step_confirmed=True))

    assert score.breakdown.confirmed_next_step == 20
    assert score.total == 20


@pytest.mark.parametrize(
    ("follow_up_actions", "expected_points"),
    [
        ([], 0),
        (["Send a proposal"], 10),
        (["Send a proposal", "Book a review call"], 10),
    ],
)
def test_follow_up_action_points(
    follow_up_actions: list[str],
    expected_points: int,
) -> None:
    score = calculate_call_score(
        make_analysis(follow_up_actions=follow_up_actions)
    )

    assert score.breakdown.follow_up_actions == expected_points
    assert score.total == expected_points


@pytest.mark.parametrize(
    ("expected_total", "expected_category", "analysis_values"),
    [
        (
            49,
            "Poor",
            {
                "discovery_quality": 5,
                "communication_clarity": 1,
                "next_step_confirmed": True,
            },
        ),
        (
            50,
            "Needs Improvement",
            {
                "communication_clarity": 5,
                "next_step_confirmed": True,
                "follow_up_actions": ["Send a proposal"],
            },
        ),
        (
            69,
            "Needs Improvement",
            {
                "discovery_quality": 5,
                "objection_handling_quality": 2,
                "communication_clarity": 1,
                "next_step_confirmed": True,
                "follow_up_actions": ["Send a proposal"],
            },
        ),
        (
            70,
            "Good",
            {
                "discovery_quality": 4,
                "objection_handling_quality": 4,
                "next_step_confirmed": True,
                "follow_up_actions": ["Send a proposal"],
            },
        ),
        (
            84,
            "Good",
            {
                "discovery_quality": 5,
                "objection_handling_quality": 5,
                "communication_clarity": 1,
                "next_step_confirmed": True,
                "follow_up_actions": ["Send a proposal"],
            },
        ),
        (
            85,
            "Excellent",
            {
                "discovery_quality": 5,
                "objection_handling_quality": 2,
                "communication_clarity": 5,
                "next_step_confirmed": True,
                "follow_up_actions": ["Send a proposal"],
            },
        ),
    ],
)
def test_score_category_boundaries(
    expected_total: int,
    expected_category: ScoreCategory,
    analysis_values: dict[str, object],
) -> None:
    score = calculate_call_score(make_analysis(**analysis_values))

    assert score.total == expected_total
    assert score.category == expected_category
    assert sum(score.breakdown.model_dump().values()) == score.total
