from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.knowledge.ingestion import EmbeddingProvider
from app.storage.database import session_scope
from app.storage.models import KnowledgeChunk, KnowledgeCorpus


class RetrievalError(RuntimeError):
    pass


@dataclass(frozen=True)
class CorpusConfig:
    revision: str
    embedding_model: str
    dimensions: int


@dataclass(frozen=True)
class RetrievedChunk:
    distance: float
    chunk_id: str
    source_path: str
    heading: str
    text: str
    content_revision: str
    corpus_revision: str


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    evidence: tuple[RetrievedChunk, ...]
    reason: str | None = None


class SearchBackend(Protocol):
    def active_corpus(self) -> CorpusConfig | None: ...

    def cosine_search(
        self, corpus: CorpusConfig, vector: list[float], top_k: int
    ) -> list[RetrievedChunk]: ...


class PostgresSearchBackend:
    def __init__(self, sessions: sessionmaker[Session]):
        self._sessions = sessions

    def active_corpus(self) -> CorpusConfig | None:
        try:
            with session_scope(self._sessions) as session:
                row = session.execute(
                    select(KnowledgeCorpus).where(KnowledgeCorpus.is_active.is_(True))
                ).scalar_one_or_none()
                return None if row is None else CorpusConfig(
                    row.revision, row.embedding_model, row.dimensions
                )
        except SQLAlchemyError as exc:
            raise RetrievalError("Knowledge database is unavailable.") from exc

    def cosine_search(
        self, corpus: CorpusConfig, vector: list[float], top_k: int
    ) -> list[RetrievedChunk]:
        distance = KnowledgeChunk.embedding.cosine_distance(vector).label("distance")
        statement = (
            select(KnowledgeChunk, distance)
            .where(
                KnowledgeChunk.corpus_revision == corpus.revision,
                KnowledgeChunk.embedding_model == corpus.embedding_model,
                KnowledgeChunk.dimensions == corpus.dimensions,
            )
            .order_by(distance)
            .limit(top_k)
        )
        try:
            with session_scope(self._sessions) as session:
                rows = session.execute(statement).all()
                return [
                    RetrievedChunk(
                        distance=float(row.distance),
                        chunk_id=row.KnowledgeChunk.chunk_id,
                        source_path=row.KnowledgeChunk.source_path,
                        heading=row.KnowledgeChunk.heading,
                        text=row.KnowledgeChunk.text,
                        content_revision=row.KnowledgeChunk.content_revision,
                        corpus_revision=row.KnowledgeChunk.corpus_revision,
                    )
                    for row in rows
                ]
        except SQLAlchemyError as exc:
            raise RetrievalError("Knowledge search failed.") from exc


class RetrievalService:
    def __init__(
        self,
        backend: SearchBackend,
        provider: EmbeddingProvider,
        evidence_threshold: float = 0.35,
    ):
        self._backend = backend
        self._provider = provider
        self._threshold = evidence_threshold

    def retrieve(self, query: str, top_k: int = 4) -> RetrievalResult:
        normalized = query.strip()
        if not normalized:
            raise ValueError("Retrieval query must not be empty.")
        if not 1 <= top_k <= 10:
            raise ValueError("top_k must be between 1 and 10.")
        corpus = self._backend.active_corpus()
        if corpus is None:
            return RetrievalResult(normalized, (), "No active knowledge corpus.")
        if (
            corpus.embedding_model != self._provider.model
            or corpus.dimensions != self._provider.dimensions
        ):
            raise RetrievalError("Query embedding configuration does not match the active corpus.")
        vectors = self._provider.embed([normalized])
        if len(vectors) != 1 or len(vectors[0]) != corpus.dimensions:
            raise RetrievalError("Query embedding has invalid dimensions.")
        candidates = self._backend.cosine_search(corpus, vectors[0], top_k)
        evidence = tuple(item for item in candidates if item.distance <= self._threshold)
        reason = None if evidence else "No evidence met the configured distance threshold."
        return RetrievalResult(normalized, evidence, reason)
