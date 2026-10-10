"""ScanRequest: an append-only log of scan starts, used for the per-user hourly quota.

Kept separate from Scan so deleting a project (which cascades to its scans) cannot reset
the user's quota. Rows are removed only when the user is deleted.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ScanRequest(Base):
    """One row per accepted scan start."""

    __tablename__ = "scan_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
