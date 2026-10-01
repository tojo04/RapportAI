from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.storage.database import Base


class KnowledgeCorpus(Base):
    __tablename__ = "knowledge_corpora"

    revision: Mapped[str] = mapped_column(String(64), primary_key=True)
    embedding_model: Mapped[str] = mapped_column(String(120), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    documents: Mapped[list["KnowledgeDocument"]] = relationship(
        back_populates="corpus", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="corpus", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "uq_knowledge_one_active_corpus",
            "is_active",
            unique=True,
            postgresql_where=(is_active.is_(True)),
        ),
    )


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    corpus_revision: Mapped[str] = mapped_column(
        ForeignKey("knowledge_corpora.revision", ondelete="CASCADE"),
        nullable=False,
    )
    source_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    corpus: Mapped[KnowledgeCorpus] = relationship(back_populates="documents")

    __table_args__ = (
        Index(
            "uq_knowledge_document_revision_path",
            "corpus_revision",
            "source_path",
            unique=True,
        ),
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    chunk_id: Mapped[str] = mapped_column(String(64), nullable=False)
    corpus_revision: Mapped[str] = mapped_column(
        ForeignKey("knowledge_corpora.revision", ondelete="CASCADE"),
        nullable=False,
    )
    source_path: Mapped[str] = mapped_column(String(500), nullable=False)
    heading: Mapped[str] = mapped_column(String(500), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(120), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)
    corpus: Mapped[KnowledgeCorpus] = relationship(back_populates="chunks")

    __table_args__ = (
        Index(
            "uq_knowledge_chunk_revision_id",
            "corpus_revision",
            "chunk_id",
            unique=True,
        ),
        Index("ix_knowledge_chunk_content_hash", "content_hash"),
    )


class CallRecord(Base):
    __tablename__ = "calls"
    call_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="idle")
    transcript_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    analysis_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    analysis_version: Mapped[str | None] = mapped_column(String(64))
    analysis_result: Mapped[dict | None] = mapped_column(JSON)
    analysis_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class TranscriptSegmentRecord(Base):
    __tablename__ = "transcript_segments"
    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    segment_order: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(32))
    speaker_role: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    __table_args__ = (Index("uq_transcript_call_segment", "call_id", "segment_id", unique=True),)


class SalesEventRecord(Base):
    __tablename__ = "sales_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    sales_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=False)
    event_order: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    __table_args__ = (
        Index("uq_sales_event_call_identity", "call_id", "sales_event_id", unique=True),
    )


class SuggestionRecord(Base):
    __tablename__ = "suggestions"
    id: Mapped[int] = mapped_column(primary_key=True)
    suggestion_id: Mapped[str] = mapped_column(String(128), nullable=False)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=False)
    suggestion_order: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    __table_args__ = (
        Index("uq_suggestion_call_identity", "call_id", "suggestion_id", unique=True),
    )
