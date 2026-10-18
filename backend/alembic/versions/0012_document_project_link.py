"""Link uploaded documents to MoITT projects."""
from alembic import op
import sqlalchemy as sa

revision = "0012_document_project_link"
down_revision = "0011_document_intake"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("project_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_documents_project_id", "projects", ["project_id"], ["id"])
    op.create_index("ix_documents_project_id", "documents", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_project_id", table_name="documents")
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("fk_documents_project_id", type_="foreignkey")
        batch.drop_column("project_id")
