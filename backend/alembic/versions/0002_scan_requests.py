"""Scan request log (quota survives project deletion) + scans.created_at index.

Revision ID: 0002_scan_requests
Revises: 0001_initial
Create Date: 2026-10-10 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_scan_requests"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create scan_requests (backfilled from existing scans) and index scans.created_at."""
    op.create_table(
        "scan_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_scan_requests_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scan_requests"),
    )
    op.create_index("ix_scan_requests_user_id", "scan_requests", ["user_id"])
    op.create_index("ix_scan_requests_created_at", "scan_requests", ["created_at"])
    op.create_index("ix_scans_created_at", "scans", ["created_at"])

    # Keep the current hour's quota intact across the upgrade.
    op.execute(
        "INSERT INTO scan_requests (user_id, created_at) "
        "SELECT projects.user_id, scans.created_at FROM scans "
        "JOIN projects ON projects.id = scans.project_id "
        "WHERE scans.created_at >= now() - interval '1 hour'"
    )


def downgrade() -> None:
    """Drop the scans.created_at index and the scan_requests table."""
    op.drop_index("ix_scans_created_at", table_name="scans")
    op.drop_index("ix_scan_requests_created_at", table_name="scan_requests")
    op.drop_index("ix_scan_requests_user_id", table_name="scan_requests")
    op.drop_table("scan_requests")
