"""Add transactions, minister decisions, and engagements."""
from alembic import op
import sqlalchemy as sa

revision = "0003_transactions_dashboard"
down_revision = "0002_register"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(12), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("sector", sa.String(80), nullable=False),
        sa.Column("stage", sa.String(40), nullable=False),
        sa.Column("next_milestone", sa.String(255), nullable=False),
        sa.Column("next_milestone_date", sa.Date(), nullable=False),
        sa.Column("health", sa.String(20), nullable=False),
        sa.Column("lead_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("summary", sa.String(2000), nullable=False),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("stage", "next_milestone_date", "health"):
        op.create_index(f"ix_transactions_{column}", "transactions", [column])
    op.create_table(
        "transaction_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("transaction_id", sa.String(36), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_transaction_events_transaction_id", "transaction_events", ["transaction_id"])
    op.create_index("ix_transaction_events_occurred_at", "transaction_events", ["occurred_at"])
    op.create_table(
        "minister_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("transaction_id", sa.String(36), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("context_ref", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_minister_decisions_due_date", "minister_decisions", ["due_date"])
    op.create_index("ix_minister_decisions_transaction_id", "minister_decisions", ["transaction_id"])
    op.create_index("ix_minister_decisions_status", "minister_decisions", ["status"])
    op.create_table(
        "engagements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("engagement_type", sa.String(80), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("pack_status", sa.String(20), nullable=False, server_default="not_started"),
        sa.Column("pack_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("transaction_id", sa.String(36), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("starts_at", "pack_status", "transaction_id"):
        op.create_index(f"ix_engagements_{column}", "engagements", [column])


def downgrade() -> None:
    op.drop_table("engagements")
    op.drop_table("minister_decisions")
    op.drop_table("transaction_events")
    op.drop_table("transactions")
