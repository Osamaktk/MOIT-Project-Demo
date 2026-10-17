"""Add AI run logging and tool switches."""
from alembic import op
import sqlalchemy as sa

revision = "0004_ai_assurance"
down_revision = "0003_transactions_dashboard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_switches",
        sa.Column("tool", sa.String(80), primary_key=True),
        sa.Column("suspended", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("changed_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(500)),
    )
    op.create_table(
        "ai_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tool", sa.String(80), nullable=False),
        sa.Column("model_role", sa.String(30), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("zone", sa.String(12), nullable=False),
        sa.Column("classification", sa.String(24), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("prompt_metadata", sa.JSON()),
        sa.Column("approver_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("diff_summary", sa.String(2000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_runs_tool", "ai_runs", ["tool"])
    op.create_index("ix_ai_runs_outcome", "ai_runs", ["outcome"])
    op.create_index("ix_ai_runs_user_id", "ai_runs", ["user_id"])
    op.create_index("ix_ai_runs_created_at", "ai_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_runs_created_at", table_name="ai_runs")
    op.drop_index("ix_ai_runs_user_id", table_name="ai_runs")
    op.drop_index("ix_ai_runs_outcome", table_name="ai_runs")
    op.drop_index("ix_ai_runs_tool", table_name="ai_runs")
    op.drop_table("ai_runs")
    op.drop_table("tool_switches")
