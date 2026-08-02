import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.config import Settings, get_settings
from app.models.analysis import AnalyzeCallResponse
from app.scoring.calculator import calculate_call_score
from app.services.analysis import AnalysisServiceError, analyze_transcript
from app.services.transcription import (
    TranscriptionServiceError,
    transcribe_audio,
)


router = APIRouter(prefix="/api")

UPLOAD_CHUNK_SIZE = 1024 * 1024
GENERIC_CONTENT_TYPES = {"", "application/octet-stream"}
CONTENT_TYPES_BY_EXTENSION = {
    ".mp3": {"audio/mpeg", "audio/mp3"},
    ".wav": {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"},
}


def _validated_extension(file: UploadFile) -> str:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in CONTENT_TYPES_BY_EXTENSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only MP3 and WAV files are supported.",
        )

    content_type = (file.content_type or "").partition(";")[0].strip().lower()
    valid_content_types = CONTENT_TYPES_BY_EXTENSION[extension]
    if (
        content_type not in GENERIC_CONTENT_TYPES
        and content_type not in valid_content_types
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The file content type does not match its extension.",
        )

    return extension


def _create_temporary_path(extension: str) -> Path:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as file:
            return Path(file.name)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The uploaded file could not be stored.",
        ) from exc


async def _store_upload(
    upload: UploadFile,
    destination: Path,
    maximum_bytes: int,
) -> None:
    total_bytes = 0

    try:
        with destination.open("wb") as output:
            while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                total_bytes += len(chunk)
                if total_bytes > maximum_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="The uploaded file exceeds the configured size limit.",
                    )
                output.write(chunk)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The uploaded file could not be stored.",
        ) from exc

    if total_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file must not be empty.",
        )


@router.post(
    "/analyze-call",
    response_model=AnalyzeCallResponse,
)
async def analyze_call(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> AnalyzeCallResponse:
    temporary_path: Path | None = None

    try:
        extension = _validated_extension(file)
        temporary_path = _create_temporary_path(extension)
        await _store_upload(
            file,
            temporary_path,
            settings.max_upload_mb * 1024 * 1024,
        )

        transcript = transcribe_audio(temporary_path, settings=settings)
        analysis = analyze_transcript(transcript, settings=settings)
        score = calculate_call_score(analysis)

        return AnalyzeCallResponse(
            transcript=transcript,
            analysis=analysis,
            score=score,
        )
    except (TranscriptionServiceError, AnalysisServiceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    finally:
        try:
            await file.close()
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
