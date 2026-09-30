from __future__ import annotations

import asyncio
from collections.abc import Callable

from app.core.config import Settings
from app.models.analysis import AnalyzeCallResponse
from app.scoring.calculator import calculate_call_score
from app.services.analysis import AnalysisServiceError, analyze_transcript
from app.storage.call_repository import CallRepository, PersistenceError


ANALYSIS_VERSION = "v1"
MINIMUM_TRANSCRIPT_CHARACTERS = 20


class LiveAnalysisRunner:
    """Supervises one logical V1 analysis result per finalized live call."""

    def __init__(
        self,
        repository: CallRepository,
        settings: Settings,
        analyzer: Callable[..., object] = analyze_transcript,
    ):
        self._repository = repository
        self._settings = settings
        self._analyzer = analyzer
        self._tasks: set[asyncio.Task[None]] = set()

    def schedule(self, call_id: str) -> bool:
        if any(task.get_name() == f"analysis-{call_id}" for task in self._tasks):
            return False
        task = asyncio.create_task(self._run(call_id), name=f"analysis-{call_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return True

    async def _run(self, call_id: str) -> None:
        claimed = await asyncio.to_thread(self._repository.claim_analysis, call_id, ANALYSIS_VERSION)
        if not claimed:
            return
        try:
            saved = await asyncio.to_thread(self._repository.get_call, call_id)
            if saved is None:
                raise PersistenceError("Saved call was not found.")
            transcript = "\n".join(item["text"] for item in saved["transcript_segments"]).strip()
            if len(transcript) < MINIMUM_TRANSCRIPT_CHARACTERS:
                raise AnalysisServiceError("Transcript is too short for reliable analysis.")
            analysis = await asyncio.to_thread(self._analyzer, transcript, settings=self._settings)
            response = AnalyzeCallResponse(
                transcript=transcript,
                analysis=analysis,  # type: ignore[arg-type]
                score=calculate_call_score(analysis),  # type: ignore[arg-type]
            )
            await asyncio.to_thread(
                self._repository.complete_analysis,
                call_id,
                ANALYSIS_VERSION,
                response.model_dump(mode="json"),
            )
        except (AnalysisServiceError, PersistenceError, ValueError) as exc:
            await asyncio.to_thread(
                self._repository.fail_analysis, call_id, ANALYSIS_VERSION, str(exc)
            )

    async def close(self) -> None:
        tasks, self._tasks = self._tasks, set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
