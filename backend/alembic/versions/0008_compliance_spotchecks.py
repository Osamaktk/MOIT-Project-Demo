"""Add compliance calendar and accuracy spot-checks."""
from alembic import op
import sqlalchemy as sa

revision = "0008_phase7"
down_revision = "0007_jarvis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compliance_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("reference", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("category", "due_date", "owner_id", "status"):
        op.create_index(f"ix_compliance_items_{column}", "compliance_items", [column])
    op.create_table(
        "spot_checks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("sample", sa.JSON(), nullable=False),
        sa.Column("reconciled_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("findings", sa.String(4000)),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("creator_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_spot_checks_period", "spot_checks", ["period"])
    op.create_index("ix_spot_checks_status", "spot_checks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_spot_checks_status", table_name="spot_checks")
    op.drop_index("ix_spot_checks_period", table_name="spot_checks")
    op.drop_table("spot_checks")
    for column in ("status", "owner_id", "due_date", "category"):
        op.drop_index(f"ix_compliance_items_{column}", table_name="compliance_items")
    op.drop_table("compliance_items")
