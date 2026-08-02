from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    model_validator,
)


NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]
QualityRating = Annotated[int, Field(strict=True, ge=0, le=5)]

Sentiment = Literal["positive", "neutral", "mixed", "negative"]
ScoreCategory = Literal["Excellent", "Good", "Needs Improvement", "Poor"]


def score_category_for_total(total: int) -> ScoreCategory:
    if total >= 85:
        return "Excellent"
    if total >= 70:
        return "Good"
    if total >= 50:
        return "Needs Improvement"
    return "Poor"


class _SchemaModel(BaseModel):
    """Base configuration shared by response models."""

    model_config = ConfigDict(extra="forbid")


class ObjectionResponse(_SchemaModel):
    objection: NonEmptyString
    response: str | None


class CallAnalysis(_SchemaModel):
    summary: NonEmptyString
    customer_needs: list[str]
    questions_asked: list[str]
    objections: list[ObjectionResponse]
    follow_up_actions: list[str]
    sentiment: Sentiment
    next_step_confirmed: StrictBool
    objection_handling_quality: QualityRating
    discovery_quality: QualityRating
    communication_clarity: QualityRating


class ScoreBreakdown(_SchemaModel):
    discovery: Annotated[int, Field(strict=True, ge=0, le=25)]
    objection_handling: Annotated[int, Field(strict=True, ge=0, le=25)]
    communication_clarity: Annotated[int, Field(strict=True, ge=0, le=20)]
    confirmed_next_step: Annotated[int, Field(strict=True, ge=0, le=20)]
    follow_up_actions: Annotated[int, Field(strict=True, ge=0, le=10)]


class ScoreResult(_SchemaModel):
    total: Annotated[int, Field(strict=True, ge=0, le=100)]
    category: ScoreCategory
    breakdown: ScoreBreakdown

    @model_validator(mode="after")
    def validate_score_consistency(self) -> "ScoreResult":
        component_total = sum(
            (
                self.breakdown.discovery,
                self.breakdown.objection_handling,
                self.breakdown.communication_clarity,
                self.breakdown.confirmed_next_step,
                self.breakdown.follow_up_actions,
            )
        )
        if self.total != component_total:
            raise ValueError("Score total must equal the component breakdown.")

        expected_category = score_category_for_total(self.total)
        if self.category != expected_category:
            raise ValueError("Score category must match the total.")

        return self


class AnalyzeCallResponse(_SchemaModel):
    transcript: NonEmptyString
    analysis: CallAnalysis
    score: ScoreResult
