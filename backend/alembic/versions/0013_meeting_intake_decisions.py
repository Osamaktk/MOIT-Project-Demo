"""Persist evidence-verified decisions on meeting records."""

from alembic import op
import sqlalchemy as sa


revision = "0013_meeting_intake_decisions"
down_revision = "0012_document_project_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("decisions", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    )
    op.add_column("meetings", sa.Column("summary", sa.String(2000), server_default="", nullable=False))


def downgrade() -> None:
    op.drop_column("meetings", "summary")
    op.drop_column("meetings", "decisions")
