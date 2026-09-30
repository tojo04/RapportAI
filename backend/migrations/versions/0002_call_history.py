"""Persist live calls and their accepted outputs."""
from alembic import op
import sqlalchemy as sa

revision = "0002_call_history"
down_revision = "0001_knowledge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("calls",
        sa.Column("call_id", sa.String(64), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("transcript_complete", sa.Boolean(), nullable=False),
        sa.Column("analysis_status", sa.String(32), nullable=False),
        sa.Column("analysis_version", sa.String(64)),
        sa.Column("analysis_result", sa.JSON()),
        sa.Column("analysis_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table("transcript_segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("call_id", sa.String(64), sa.ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=False),
        sa.Column("segment_id", sa.String(128), nullable=False),
        sa.Column("segment_order", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(32)),
        sa.Column("speaker_role", sa.String(32), nullable=False),
        sa.UniqueConstraint("call_id", "segment_id", name="uq_transcript_call_segment"),
    )
    op.create_table("sales_events",
        sa.Column("sales_event_id", sa.String(128), primary_key=True),
        sa.Column("call_id", sa.String(64), sa.ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_order", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table("suggestions",
        sa.Column("suggestion_id", sa.String(128), primary_key=True),
        sa.Column("call_id", sa.String(64), sa.ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=False),
        sa.Column("suggestion_order", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("suggestions")
    op.drop_table("sales_events")
    op.drop_table("transcript_segments")
    op.drop_table("calls")
