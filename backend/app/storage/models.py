from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
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
