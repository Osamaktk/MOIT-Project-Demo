"""Add document intake review queue and duplicate tracking."""
from alembic import op
import sqlalchemy as sa

revision = "0011_document_intake"
down_revision = "0010_moitt_projects_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("sha256", sa.String(64), nullable=True))
        batch.add_column(sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id", name="fk_documents_uploaded_by_users"), nullable=True))
        batch.add_column(sa.Column("cloud_ai_allowed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_documents_sha256", "documents", ["sha256"], unique=True)
    op.create_index("ix_documents_uploaded_by", "documents", ["uploaded_by"])
    op.create_table(
        "intake_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_to", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="review"),
        sa.Column("was_edited", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("doc_kind", sa.String(24), nullable=False, server_default="other"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("warnings", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("ai_run_id", sa.String(36), sa.ForeignKey("ai_runs.id"), nullable=True),
        sa.Column("diff_summary", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("document_id", "owner_id", "assigned_to", "status"):
        op.create_index(f"ix_intake_reviews_{column}", "intake_reviews", [column], unique=column == "document_id")


def downgrade() -> None:
    for column in ("document_id", "owner_id", "assigned_to", "status"):
        op.drop_index(f"ix_intake_reviews_{column}", table_name="intake_reviews")
    op.drop_table("intake_reviews")
    op.drop_index("ix_documents_uploaded_by", table_name="documents")
    op.drop_index("ix_documents_sha256", table_name="documents")
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("cloud_ai_allowed")
        batch.drop_column("uploaded_by")
        batch.drop_column("sha256")
