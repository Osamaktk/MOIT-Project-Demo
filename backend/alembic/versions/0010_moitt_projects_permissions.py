"""Introduce MoITT domain entities and permission presets."""
from alembic import op
import sqlalchemy as sa


revision = "0010_moitt_projects_permissions"
down_revision = "0009_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organisations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(180), nullable=False, unique=True),
        sa.Column("short_name", sa.String(40), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_organisations_short_name", "organisations", ["short_name"], unique=True)
    op.create_index("ix_organisations_type", "organisations", ["type"])

    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(24), nullable=False, unique=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("sector", sa.String(80), nullable=False),
        sa.Column("stage", sa.String(40), nullable=False),
        sa.Column("health", sa.String(20), nullable=False, server_default="on_track"),
        sa.Column("health_reason", sa.String(1000), nullable=False),
        sa.Column("lead_org_id", sa.String(36), sa.ForeignKey("organisations.id"), nullable=True),
        sa.Column("summary", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("name", "stage", "health", "lead_org_id"):
        op.create_index(f"ix_projects_{column}", "projects", [column])

    op.create_table(
        "actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("serial_no", sa.Integer(), nullable=True),
        sa.Column("fy", sa.String(7), nullable=False),
        sa.Column("description", sa.String(4000), nullable=False),
        sa.Column("owner_org_id", sa.String(36), sa.ForeignKey("organisations.id"), nullable=True),
        sa.Column("owner_person_name", sa.String(160), nullable=True),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("deadline_text", sa.String(255), nullable=False),
        sa.Column("deadline_precision", sa.String(16), nullable=False),
        sa.Column("priority", sa.String(1), nullable=False, server_default="B"),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("status_source", sa.String(24), nullable=False, server_default="open"),
        sa.Column("review_state", sa.String(20), nullable=False, server_default="proposed"),
        sa.Column("origin", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("source_document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("source_quote", sa.String(2000), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("fy", "serial_no", name="uq_action_fy_serial"),
        sa.CheckConstraint("owner_org_id IS NOT NULL OR coalesce(length(trim(owner_person_name)), 0) > 0", name="ck_action_has_owner"),
    )
    for column in ("fy", "owner_org_id", "owner_user_id", "deadline", "status", "review_state", "project_id", "source_document_id"):
        op.create_index(f"ix_actions_{column}", "actions", [column])

    op.create_table(
        "commitments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("statement", sa.String(2000), nullable=False),
        sa.Column("committed_by_org_id", sa.String(36), sa.ForeignKey("organisations.id"), nullable=True),
        sa.Column("committed_by_text", sa.String(255), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("due_text", sa.String(255), nullable=False),
        sa.Column("precision", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("source_document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("source_quote", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("project_id", "committed_by_org_id", "due_date", "status", "source_document_id"):
        op.create_index(f"ix_commitments_{column}", "commitments", [column])

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("document_clearance", sa.String(24), nullable=False, server_default="internal"))
        batch.add_column(sa.Column("organisation_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_users_organisation_id", "organisations", ["organisation_id"], ["id"])
    op.create_index("ix_users_organisation_id", "users", ["organisation_id"])

    op.create_table(
        "roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_roles_key", "roles", ["key"], unique=True)
    op.create_table(
        "user_permissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_key", sa.String(80), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("changed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "permission_key", name="uq_user_permission_key"),
    )
    op.create_index("ix_user_permissions_user_id", "user_permissions", ["user_id"])

    op.add_column("meetings", sa.Column("chair", sa.String(255), nullable=True))
    op.add_column("meetings", sa.Column("venue", sa.String(255), nullable=True))
    op.add_column("meetings", sa.Column("participants", sa.JSON(), nullable=False, server_default="[]"))
    with op.batch_alter_table("meetings") as batch:
        batch.add_column(sa.Column("source_document_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_meetings_source_document_id", "documents", ["source_document_id"], ["id"])
    op.create_index("ix_meetings_source_document_id", "meetings", ["source_document_id"])


def downgrade() -> None:
    op.drop_index("ix_meetings_source_document_id", table_name="meetings")
    with op.batch_alter_table("meetings") as batch:
        for column in ("source_document_id", "participants", "venue", "chair"):
            batch.drop_column(column)
    op.drop_index("ix_user_permissions_user_id", table_name="user_permissions")
    op.drop_table("user_permissions")
    op.drop_index("ix_roles_key", table_name="roles")
    op.drop_table("roles")
    op.drop_index("ix_users_organisation_id", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("organisation_id")
        batch.drop_column("document_clearance")
    for table, columns in {
        "commitments": ("source_document_id", "status", "due_date", "committed_by_org_id", "project_id"),
        "actions": ("source_document_id", "project_id", "review_state", "status", "deadline", "owner_user_id", "owner_org_id", "fy"),
    }.items():
        for column in columns:
            op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_table(table)
    for column in ("lead_org_id", "health", "stage", "name"):
        op.drop_index(f"ix_projects_{column}", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_organisations_type", table_name="organisations")
    op.drop_index("ix_organisations_short_name", table_name="organisations")
    op.drop_table("organisations")
