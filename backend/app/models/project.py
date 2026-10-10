"""Project model (a GitHub repository registered by a user)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.scan import Scan
    from app.models.user import User


class Project(Base, TimestampMixin):
    """A user's GitHub repository to be scanned."""

    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("user_id", "repo_url", name="uq_projects_user_id_repo_url"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    repo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    primary_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    latest_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="projects")
    scans: Mapped[list["Scan"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="desc(Scan.created_at)",
    )
