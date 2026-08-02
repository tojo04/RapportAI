from app.models.analysis import (
    CallAnalysis,
    ScoreBreakdown,
    ScoreResult,
    score_category_for_total,
)


MAX_QUALITY_RATING = 5
DISCOVERY_MAX_POINTS = 25
OBJECTION_HANDLING_MAX_POINTS = 25
COMMUNICATION_CLARITY_MAX_POINTS = 20
CONFIRMED_NEXT_STEP_POINTS = 20
FOLLOW_UP_ACTIONS_POINTS = 10


def _scale_quality_rating(rating: int, maximum_points: int) -> int:
    """Scale a 0-5 rating and round it to the nearest whole point.

    Python's ``round`` uses ties-to-even rounding. The current component maxima
    are divisible by five, so every valid rating maps to an exact integer.
    """

    return round(rating / MAX_QUALITY_RATING * maximum_points)


def calculate_call_score(analysis: CallAnalysis) -> ScoreResult:
    """Calculate a reproducible call-quality score from validated analysis."""

    breakdown = ScoreBreakdown(
        discovery=_scale_quality_rating(
            analysis.discovery_quality,
            DISCOVERY_MAX_POINTS,
        ),
        objection_handling=_scale_quality_rating(
            analysis.objection_handling_quality,
            OBJECTION_HANDLING_MAX_POINTS,
        ),
        communication_clarity=_scale_quality_rating(
            analysis.communication_clarity,
            COMMUNICATION_CLARITY_MAX_POINTS,
        ),
        confirmed_next_step=(
            CONFIRMED_NEXT_STEP_POINTS if analysis.next_step_confirmed else 0
        ),
        follow_up_actions=(
            FOLLOW_UP_ACTIONS_POINTS if analysis.follow_up_actions else 0
        ),
    )

    total = sum(
        (
            breakdown.discovery,
            breakdown.objection_handling,
            breakdown.communication_clarity,
            breakdown.confirmed_next_step,
            breakdown.follow_up_actions,
        )
    )

    return ScoreResult(
        total=total,
        category=score_category_for_total(total),
        breakdown=breakdown,
    )
