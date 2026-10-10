"""Scan model and ScanStatus enum."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.finding import Finding
    from app.models.project import Project


class ScanStatus(str, enum.Enum):
    """Lifecycle state of a scan."""

    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """Persist enum *values* (lowercase strings) rather than member names."""
    return [member.value for member in enum_cls]


class Scan(Base, TimestampMixin):
    """A single scan run of a project's repository."""

    __tablename__ = "scans"
    __table_args__ = (
        Index("ix_scans_project_id_created_at", "project_id", "created_at"),
        Index("ix_scans_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, name="scan_status", values_callable=_enum_values),
        default=ScanStatus.queued,
        server_default=ScanStatus.queued.value,
        index=True,
        nullable=False,
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="scans")
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan", passive_deletes=True
    )
