from pathlib import Path

from openai import OpenAI, OpenAIError

from app.core.config import Settings, get_settings


SUPPORTED_AUDIO_EXTENSIONS = frozenset({".mp3", ".wav"})


class TranscriptionServiceError(RuntimeError):
    """Raised when a local audio file cannot be transcribed."""


def _transcription_client(settings: Settings) -> OpenAI:
    if not settings.openai_api_key:
        raise TranscriptionServiceError("OPENAI_API_KEY is not configured.")

    return OpenAI(api_key=settings.openai_api_key)


def transcribe_audio(
    audio_path: Path,
    *,
    client: OpenAI | None = None,
    settings: Settings | None = None,
) -> str:
    """Transcribe a non-empty local MP3 or WAV file."""

    path = Path(audio_path)

    if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise TranscriptionServiceError("Only MP3 and WAV files are supported.")
    if not path.is_file():
        raise TranscriptionServiceError("Audio file does not exist.")
    if path.stat().st_size == 0:
        raise TranscriptionServiceError("Audio file must not be empty.")

    active_settings = settings or get_settings()
    if not active_settings.openai_transcription_model:
        raise TranscriptionServiceError(
            "OPENAI_TRANSCRIPTION_MODEL is not configured."
        )

    active_client = client or _transcription_client(active_settings)

    try:
        with path.open("rb") as audio_file:
            response = active_client.audio.transcriptions.create(
                model=active_settings.openai_transcription_model,
                file=audio_file,
            )
    except OSError as exc:
        raise TranscriptionServiceError("Audio file could not be read.") from exc
    except OpenAIError as exc:
        raise TranscriptionServiceError(
            "Audio transcription failed. Please try again."
        ) from exc

    transcript = (
        response if isinstance(response, str) else getattr(response, "text", None)
    )
    if not isinstance(transcript, str) or not transcript.strip():
        raise TranscriptionServiceError(
            "The transcription service returned an empty transcript."
        )

    return transcript.strip()
