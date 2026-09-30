from dataclasses import dataclass

import pytest

from app.knowledge.ingestion import FakeEmbeddingProvider
from app.knowledge.retrieval import (
    CorpusConfig,
    RetrievalError,
    RetrievalService,
    RetrievedChunk,
)


@dataclass
class FakeBackend:
    corpus: CorpusConfig | None
    rows: list[RetrievedChunk]

    def active_corpus(self) -> CorpusConfig | None:
        return self.corpus

    def cosine_search(self, corpus: CorpusConfig, vector: list[float], top_k: int) -> list[RetrievedChunk]:
        assert corpus == self.corpus
        return sorted(self.rows, key=lambda item: item.distance)[:top_k]


def chunk(distance: float, source: str = "pricing.md", revision: str = "active") -> RetrievedChunk:
    return RetrievedChunk(distance, source, source, "Heading", "Fictional text", "v1", revision)


def test_returns_ordered_bounded_active_evidence() -> None:
    provider = FakeEmbeddingProvider(dimensions=4)
    backend = FakeBackend(CorpusConfig("active", provider.model, 4), [chunk(0.3), chunk(0.1, "product.md"), chunk(0.8)])
    result = RetrievalService(backend, provider, 0.35).retrieve("price", top_k=2)
    assert [item.source_path for item in result.evidence] == ["product.md", "pricing.md"]


def test_empty_corpus_and_below_threshold_are_explicit() -> None:
    provider = FakeEmbeddingProvider(dimensions=4)
    assert RetrievalService(FakeBackend(None, []), provider).retrieve("query").reason
    backend = FakeBackend(CorpusConfig("active", provider.model, 4), [chunk(0.9)])
    assert RetrievalService(backend, provider, 0.2).retrieve("query").evidence == ()


def test_invalid_dimensions_or_model_are_rejected() -> None:
    provider = FakeEmbeddingProvider(dimensions=4)
    backend = FakeBackend(CorpusConfig("active", provider.model, 8), [])
    with pytest.raises(RetrievalError, match="does not match"):
        RetrievalService(backend, provider).retrieve("query")


def test_query_and_top_k_validation() -> None:
    provider = FakeEmbeddingProvider(dimensions=4)
    service = RetrievalService(FakeBackend(None, []), provider)
    with pytest.raises(ValueError):
        service.retrieve(" ")
    with pytest.raises(ValueError):
        service.retrieve("query", 11)
