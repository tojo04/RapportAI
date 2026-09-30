"""Create versioned vector knowledge storage."""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0001_knowledge"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_corpora",
        sa.Column("revision", sa.String(64), primary_key=True),
        sa.Column("embedding_model", sa.String(120), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "uq_knowledge_one_active_corpus",
        "knowledge_corpora",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("corpus_revision", sa.String(64), sa.ForeignKey("knowledge_corpora.revision", ondelete="CASCADE"), nullable=False),
        sa.Column("source_path", sa.String(500), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content_revision", sa.String(64), nullable=False),
        sa.UniqueConstraint("corpus_revision", "source_path", name="uq_knowledge_document_revision_path"),
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chunk_id", sa.String(64), nullable=False),
        sa.Column("corpus_revision", sa.String(64), sa.ForeignKey("knowledge_corpora.revision", ondelete="CASCADE"), nullable=False),
        sa.Column("source_path", sa.String(500), nullable=False),
        sa.Column("heading", sa.String(500), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content_revision", sa.String(64), nullable=False),
        sa.Column("embedding_model", sa.String(120), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.UniqueConstraint("corpus_revision", "chunk_id", name="uq_knowledge_chunk_revision_id"),
    )
    op.create_index("ix_knowledge_chunk_content_hash", "knowledge_chunks", ["content_hash"])


def downgrade() -> None:
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_table("knowledge_corpora")
