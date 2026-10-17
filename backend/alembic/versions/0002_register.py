"""Add the decision and action register."""
from alembic import op
import sqlalchemy as sa

revision = "0002_register"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "register_serial_counters",
        sa.Column("fy", sa.String(7), primary_key=True),
        sa.Column("last_serial", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "register_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("serial_no", sa.Integer(), nullable=True),
        sa.Column("fy", sa.String(7), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occasion_type", sa.String(20), nullable=False),
        sa.Column("occasion_ref", sa.String(255), nullable=True),
        sa.Column("description", sa.String(4000), nullable=False),
        sa.Column("minister_words", sa.String(2000), nullable=True),
        sa.Column("officer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=False),
        sa.Column("priority", sa.String(1), nullable=False),
        sa.Column("source_record", sa.String(255), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closure_note", sa.String(2000), nullable=True),
        sa.Column("transaction_id", sa.String(36), nullable=True),
        sa.Column("origin", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("review_state", sa.String(20), nullable=False, server_default="approved"),
        sa.Column("ai_assistance", sa.JSON(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("fy", "serial_no", name="uq_register_fy_serial"),
    )
    for column in ("fy", "officer_id", "priority", "status", "transaction_id", "review_state"):
        op.create_index(f"ix_register_entries_{column}", "register_entries", [column])


def downgrade() -> None:
    op.drop_table("register_entries")
    op.drop_table("register_serial_counters")
