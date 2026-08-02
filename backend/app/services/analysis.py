from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.models.analysis import CallAnalysis


ANALYSIS_INSTRUCTIONS = """
Analyze the sales-call transcript using only evidence explicitly present in it.

Rules:
- Never invent customer needs, questions, objections, responses, or next steps.
- Use an empty list when the transcript contains no evidence for a list field.
- Distinguish a customer objection from a normal informational question.
- Set an objection's response to null when the salesperson did not answer it.
- Evaluate all quality ratings only from the conversation evidence.
- Keep the summary concise and factual.
- Return data that exactly matches the supplied schema.
""".strip()


class AnalysisServiceError(RuntimeError):
    """Raised when a transcript cannot be analyzed safely."""


def _analysis_client(settings: Settings) -> OpenAI:
    if not settings.openai_api_key:
        raise AnalysisServiceError("OPENAI_API_KEY is not configured.")

    return OpenAI(api_key=settings.openai_api_key)


def analyze_transcript(
    transcript: str,
    *,
    client: OpenAI | None = None,
    settings: Settings | None = None,
) -> CallAnalysis:
    """Extract and validate structured sales information from a transcript."""

    normalized_transcript = transcript.strip()
    if not normalized_transcript:
        raise AnalysisServiceError("Transcript must not be empty.")

    active_settings = settings or get_settings()
    if not active_settings.openai_analysis_model:
        raise AnalysisServiceError("OPENAI_ANALYSIS_MODEL is not configured.")

    active_client = client or _analysis_client(active_settings)

    try:
        response = active_client.responses.parse(
            model=active_settings.openai_analysis_model,
            input=[
                {"role": "system", "content": ANALYSIS_INSTRUCTIONS},
                {"role": "user", "content": normalized_transcript},
            ],
            text_format=CallAnalysis,
        )
    except ValidationError as exc:
        raise AnalysisServiceError(
            "The analysis service returned invalid structured output."
        ) from exc
    except OpenAIError as exc:
        raise AnalysisServiceError(
            "Transcript analysis failed. Please try again."
        ) from exc

    try:
        return CallAnalysis.model_validate(response.output_parsed)
    except (TypeError, ValidationError) as exc:
        raise AnalysisServiceError(
            "The analysis service returned invalid structured output."
        ) from exc
