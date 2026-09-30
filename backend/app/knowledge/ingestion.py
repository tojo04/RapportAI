from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from openai import OpenAI
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.storage.database import session_scope
from app.storage.models import KnowledgeChunk, KnowledgeCorpus, KnowledgeDocument


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourceDocument:
    source_path: str
    text: str
    content_hash: str
    content_revision: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_path: str
    heading: str
    text: str
    content_hash: str
    content_revision: str


@dataclass(frozen=True)
class IngestionResult:
    corpus_revision: str
    document_count: int
    chunk_count: int
    embedded_count: int
    reused_count: int
    already_active: bool


class EmbeddingProvider(Protocol):
    model: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbeddingProvider:
    def __init__(self, model: str = "fake-sha256-v1", dimensions: int = 16):
        self.model = model
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.shake_256(text.encode("utf-8")).digest(
                self.dimensions
            )
            values = [(byte - 127.5) / 127.5 for byte in digest]
            magnitude = math.sqrt(sum(value * value for value in values)) or 1
            vectors.append([value / magnitude for value in values])
        return vectors


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str, model: str, dimensions: int):
        self.model = model
        self.dimensions = dimensions
        self._client = OpenAI(api_key=api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
            encoding_format="float",
        )
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


def load_documents(root: Path) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for path in sorted(root.glob("*.md")):
        if path.name.casefold() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
        content_hash = _hash(text)
        documents.append(
            SourceDocument(path.relative_to(root).as_posix(), text, content_hash, content_hash[:12])
        )
    return documents


def chunk_document(document: SourceDocument) -> list[Chunk]:
    sections: list[tuple[str, list[str]]] = []
    heading = "Document"
    lines: list[str] = []
    for line in document.text.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match:
            if any(part.strip() for part in lines):
                sections.append((heading, lines))
            heading = match.group(1).strip()
            lines = []
        else:
            lines.append(line)
    if any(part.strip() for part in lines):
        sections.append((heading, lines))

    chunks: list[Chunk] = []
    for index, (section_heading, body) in enumerate(sections):
        text = "\n".join(body).strip()
        if not text:
            continue
        content_hash = _hash(text)
        identity = f"{document.source_path}\n{section_heading}\n{index}"
        chunks.append(
            Chunk(
                chunk_id=_hash(identity),
                source_path=document.source_path,
                heading=section_heading,
                text=text,
                content_hash=content_hash,
                content_revision=content_hash[:12],
            )
        )
    return chunks


def corpus_revision(
    documents: list[SourceDocument], model: str, dimensions: int
) -> str:
    manifest = "\n".join(
        f"{item.source_path}:{item.content_hash}" for item in documents
    )
    return _hash(f"{model}:{dimensions}\n{manifest}")


class KnowledgeIngester:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        provider: EmbeddingProvider,
    ):
        self._sessions = session_factory
        self._provider = provider

    def ingest(self, root: Path) -> IngestionResult:
        documents = load_documents(root)
        if not documents:
            raise ValueError("No Markdown knowledge documents were found.")
        chunks = [chunk for document in documents for chunk in chunk_document(document)]
        revision = corpus_revision(documents, self._provider.model, self._provider.dimensions)

        with session_scope(self._sessions) as session:
            existing = session.get(KnowledgeCorpus, revision)
            if existing is not None and existing.is_active:
                return IngestionResult(revision, len(documents), len(chunks), 0, len(chunks), True)

            reusable: dict[str, list[float]] = {}
            hashes = [chunk.content_hash for chunk in chunks]
            if hashes:
                rows = session.execute(
                    select(KnowledgeChunk).where(
                        KnowledgeChunk.content_hash.in_(hashes),
                        KnowledgeChunk.embedding_model == self._provider.model,
                        KnowledgeChunk.dimensions == self._provider.dimensions,
                    )
                ).scalars()
                for row in rows:
                    reusable.setdefault(row.content_hash, list(row.embedding))

            missing = [chunk for chunk in chunks if chunk.content_hash not in reusable]
            created = self._provider.embed([chunk.text for chunk in missing]) if missing else []
            if len(created) != len(missing):
                raise ValueError("Embedding provider returned an unexpected batch size.")
            for chunk, vector in zip(missing, created, strict=True):
                if len(vector) != self._provider.dimensions:
                    raise ValueError("Embedding dimensions do not match the configured corpus.")
                reusable[chunk.content_hash] = vector

            if existing is not None:
                session.delete(existing)
                session.flush()
            corpus = KnowledgeCorpus(
                revision=revision,
                embedding_model=self._provider.model,
                dimensions=self._provider.dimensions,
                content_hash=_hash("".join(item.content_hash for item in documents)),
                is_active=False,
            )
            session.add(corpus)
            for document in documents:
                session.add(KnowledgeDocument(
                    corpus_revision=revision,
                    source_path=document.source_path,
                    content_hash=document.content_hash,
                    content_revision=document.content_revision,
                ))
            for chunk in chunks:
                session.add(KnowledgeChunk(
                    chunk_id=chunk.chunk_id,
                    corpus_revision=revision,
                    source_path=chunk.source_path,
                    heading=chunk.heading,
                    text=chunk.text,
                    content_hash=chunk.content_hash,
                    content_revision=chunk.content_revision,
                    embedding_model=self._provider.model,
                    dimensions=self._provider.dimensions,
                    embedding=reusable[chunk.content_hash],
                ))
            session.flush()
            session.execute(update(KnowledgeCorpus).values(is_active=False, activated_at=None))
            corpus.is_active = True
            from datetime import datetime, timezone
            corpus.activated_at = datetime.now(timezone.utc)

        return IngestionResult(
            revision, len(documents), len(chunks), len(missing), len(chunks) - len(missing), False
        )
