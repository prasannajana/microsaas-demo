"""Initial schema: users, refresh_tokens, projects, scans, findings.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-10 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

scan_status = postgresql.ENUM(
    "queued", "running", "completed", "failed", name="scan_status", create_type=False
)
finding_category = postgresql.ENUM(
    "documentation",
    "testing",
    "ci_cd",
    "deployment",
    "configuration",
    "dependencies",
    name="finding_category",
    create_type=False,
)
severity = postgresql.ENUM(
    "critical", "high", "medium", "low", name="severity", create_type=False
)


def _timestamps() -> list[sa.Column]:
    """Columns provided by TimestampMixin."""
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    """Create enums, tables, indexes and constraints."""
    bind = op.get_bind()
    scan_status.create(bind, checkfirst=True)
    finding_category.create(bind, checkfirst=True)
    severity.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("oauth_provider", sa.String(length=50), nullable=True),
        sa.Column("google_id", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=512), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_refresh_tokens_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
    )
    op.create_index("ix_refresh_tokens_id", "refresh_tokens", ["id"])
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token", "refresh_tokens", ["token"], unique=True)

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("repo_url", sa.String(length=500), nullable=False),
        sa.Column("default_branch", sa.String(length=100), nullable=True),
        sa.Column("primary_language", sa.String(length=50), nullable=True),
        sa.Column("latest_score", sa.Integer(), nullable=True),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_projects_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("user_id", "repo_url", name="uq_projects_user_id_repo_url"),
    )
    op.create_index("ix_projects_id", "projects", ["id"])
    op.create_index("ix_projects_user_id", "projects", ["user_id"])

    op.create_table(
        "scans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("status", scan_status, server_default="queued", nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("commit_sha", sa.String(length=40), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_scans_project_id_projects", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scans"),
    )
    op.create_index("ix_scans_id", "scans", ["id"])
    op.create_index("ix_scans_project_id", "scans", ["project_id"])
    op.create_index("ix_scans_status", "scans", ["status"])
    op.create_index("ix_scans_project_id_created_at", "scans", ["project_id", "created_at"])

    op.create_table(
        "findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.Integer(), nullable=False),
        sa.Column("check_id", sa.String(length=50), nullable=False),
        sa.Column("category", finding_category, nullable=False),
        sa.Column("severity", severity, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["scan_id"], ["scans.id"], name="fk_findings_scan_id_scans", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_findings"),
    )
    op.create_index("ix_findings_id", "findings", ["id"])
    op.create_index("ix_findings_scan_id", "findings", ["scan_id"])


def downgrade() -> None:
    """Drop all tables (children first), then the enum types."""
    op.drop_index("ix_findings_scan_id", table_name="findings")
    op.drop_index("ix_findings_id", table_name="findings")
    op.drop_table("findings")

    op.drop_index("ix_scans_project_id_created_at", table_name="scans")
    op.drop_index("ix_scans_status", table_name="scans")
    op.drop_index("ix_scans_project_id", table_name="scans")
    op.drop_index("ix_scans_id", table_name="scans")
    op.drop_table("scans")

    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_index("ix_projects_id", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_refresh_tokens_token", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_users_google_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    severity.drop(bind, checkfirst=True)
    finding_category.drop(bind, checkfirst=True)
    scan_status.drop(bind, checkfirst=True)
