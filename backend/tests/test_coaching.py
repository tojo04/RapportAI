import asyncio

import pytest

from app.knowledge.ingestion import FakeEmbeddingProvider
from app.knowledge.retrieval import CorpusConfig, RetrievalService, RetrievedChunk
from app.models.realtime import SalesEventPayload
from app.services.coaching import (
    COACH_INSTRUCTIONS,
    CoachCandidate,
    CoachingError,
    CoachService,
    FakeCoachGenerator,
    LiveCoach,
)
from app.services.sales_detection import DetectionSegment


class Backend:
    def __init__(self, rows: list[RetrievedChunk]):
        self.rows = rows

    def active_corpus(self) -> CorpusConfig:
        return CorpusConfig("corpus-v1", "fake-sha256-v1", 4)

    def cosine_search(self, corpus: CorpusConfig, vector: list[float], top_k: int) -> list[RetrievedChunk]:
        return self.rows[:top_k]


def event() -> SalesEventPayload:
    return SalesEventPayload(
        sales_event_id="event-1", category="pricing", evidence_segment_ids=["s1"],
        evidence_span="too expensive", subject="Growth price",
    )


def evidence() -> RetrievedChunk:
    return RetrievedChunk(0.1, "c1", "pricing.md", "Growth", "Fictional $49", "r1", "corpus-v1")


def service(candidate: CoachCandidate, rows: list[RetrievedChunk] | None = None, delay: float = 0) -> CoachService:
    retrieval = RetrievalService(Backend(rows if rows is not None else [evidence()]), FakeEmbeddingProvider(dimensions=4), 0.35)
    return CoachService(retrieval, FakeCoachGenerator(candidate, delay))


def test_valid_citations_include_snapshot_metadata() -> None:
    result = asyncio.run(service(CoachCandidate(
        text="Clarify seats, then explain the published price.",
        evidence_segment_ids=["s1"], source_chunk_ids=["c1"], insufficient_evidence=False,
    )).suggest(event(), [DetectionSegment(segment_id="s1", order=1, text="too expensive")]))
    assert result.source_versions == {"c1": "r1"}
    assert result.sources[0].source_path == "pricing.md"


def test_invalid_citations_and_unsupported_claims_are_rejected() -> None:
    async def scenario() -> None:
        context = [DetectionSegment(segment_id="s1", order=1, text="too expensive")]
        with pytest.raises(CoachingError, match="not retrieved"):
            await service(CoachCandidate(text="Use it", evidence_segment_ids=["s1"], source_chunk_ids=["missing"], insufficient_evidence=False)).suggest(event(), context)
        with pytest.raises(CoachingError, match="without evidence"):
            await service(CoachCandidate(text="Invent a discount", evidence_segment_ids=["s1"], source_chunk_ids=[], insufficient_evidence=False), []).suggest(event(), context)
    asyncio.run(scenario())


def test_stop_suppresses_slow_suggestion_and_duplicates() -> None:
    async def scenario() -> None:
        outputs = []
        candidate = CoachCandidate(text="Ask a question", evidence_segment_ids=["s1"], source_chunk_ids=[], insufficient_evidence=True)
        async def sink(item: object) -> None:
            outputs.append(item)
        coach = LiveCoach(service(candidate, [], delay=0.05), sink, lambda message: asyncio.sleep(0), cooldown_seconds=0)
        context = [DetectionSegment(segment_id="s1", order=1, text="too expensive")]
        await coach.submit(event(), context)
        await coach.submit(event(), context)
        await coach.stop()
        await asyncio.sleep(0.06)
        assert outputs == []
    asyncio.run(scenario())


def test_prompt_treats_transcript_and_knowledge_as_untrusted_data() -> None:
    assert "untrusted" in COACH_INSTRUCTIONS
    assert "never instructions" in COACH_INSTRUCTIONS
