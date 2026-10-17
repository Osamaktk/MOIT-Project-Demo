"""Add meetings, transcripts, minutes, and reviewable actions."""
from alembic import op
import sqlalchemy as sa

revision = "0005_minutes"
down_revision = "0004_ai_assurance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meetings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occasion_type", sa.String(24), nullable=False),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("attendees", sa.JSON(), nullable=False),
        sa.Column("audio_path", sa.String(500)),
        sa.Column("language_hint", sa.String(20), nullable=False),
        sa.Column("classification", sa.String(24), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("draft_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issue_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_meetings_occurred_at", "meetings", ["occurred_at"])
    op.create_index("ix_meetings_status", "meetings", ["status"])
    op.create_table(
        "transcripts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("segments", sa.JSON(), nullable=False),
        sa.Column("stt_provider", sa.String(80), nullable=False),
        sa.Column("stt_model", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("meeting_id", name="uq_transcripts_meeting"),
    )
    op.create_index("ix_transcripts_meeting_id", "transcripts", ["meeting_id"])
    op.create_table(
        "minutes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body_markdown", sa.String(30000), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("drafted_by_run_id", sa.String(36), sa.ForeignKey("ai_runs.id")),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("issued_at", sa.DateTime(timezone=True)),
        sa.Column("export_path", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("meeting_id", "version", name="uq_minutes_meeting_version"),
    )
    op.create_index("ix_minutes_meeting_id", "minutes", ["meeting_id"])
    op.create_index("ix_minutes_status", "minutes", ["status"])
    op.create_table(
        "meeting_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("ai_run_id", sa.String(36), sa.ForeignKey("ai_runs.id")),
        sa.Column("register_entry_id", sa.String(36)),
        sa.Column("description", sa.String(4000), nullable=False),
        sa.Column("officer_hint", sa.String(255)),
        sa.Column("officer_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("deadline_hint", sa.String(255)),
        sa.Column("deadline_date", sa.Date()),
        sa.Column("priority_suggestion", sa.String(1), nullable=False),
        sa.Column("transaction_hint", sa.String(255)),
        sa.Column("transaction_id", sa.String(36), sa.ForeignKey("transactions.id")),
        sa.Column("quote", sa.String(2000), nullable=False),
        sa.Column("transcript_start", sa.Float(), nullable=False),
        sa.Column("transcript_end", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("review_state", sa.String(24), nullable=False),
        sa.Column("review_reason", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_meeting_actions_meeting_id", "meeting_actions", ["meeting_id"])
    op.create_index("ix_meeting_actions_ai_run_id", "meeting_actions", ["ai_run_id"])
    op.create_index("ix_meeting_actions_register_entry_id", "meeting_actions", ["register_entry_id"])
    op.create_index("ix_meeting_actions_review_state", "meeting_actions", ["review_state"])


def downgrade() -> None:
    op.drop_index("ix_meeting_actions_review_state", table_name="meeting_actions")
    op.drop_index("ix_meeting_actions_register_entry_id", table_name="meeting_actions")
    op.drop_index("ix_meeting_actions_ai_run_id", table_name="meeting_actions")
    op.drop_index("ix_meeting_actions_meeting_id", table_name="meeting_actions")
    op.drop_table("meeting_actions")
    op.drop_index("ix_minutes_status", table_name="minutes")
    op.drop_index("ix_minutes_meeting_id", table_name="minutes")
    op.drop_table("minutes")
    op.drop_index("ix_transcripts_meeting_id", table_name="transcripts")
    op.drop_table("transcripts")
    op.drop_index("ix_meetings_status", table_name="meetings")
    op.drop_index("ix_meetings_occurred_at", table_name="meetings")
    op.drop_table("meetings")
