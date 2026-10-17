"""Add documents and citation-ready chunks."""
from alembic import op
import sqlalchemy as sa

revision = "0006_records_search"
down_revision = "0005_minutes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("doc_type", sa.String(40), nullable=False),
        sa.Column("classification", sa.String(24), nullable=False),
        sa.Column("transaction_id", sa.String(36), sa.ForeignKey("transactions.id")),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("text_extracted", sa.String(), nullable=False),
        sa.Column("source_note", sa.String(1000)),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ingest_status", sa.String(24), nullable=False, server_default="ready"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("doc_type", "classification", "transaction_id", "ingest_status"):
        op.create_index(f"ix_documents_{column}", "documents", [column])
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("page", sa.Integer()),
        sa.Column("section", sa.String(255)),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("vector_id", sa.String(36), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    for column in ("ingest_status", "transaction_id", "classification", "doc_type"):
        op.drop_index(f"ix_documents_{column}", table_name="documents")
    op.drop_table("documents")
