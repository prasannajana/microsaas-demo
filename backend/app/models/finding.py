"""Finding model with FindingCategory and Severity enums."""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin
from app.models.scan import _enum_values

if TYPE_CHECKING:
    from app.models.scan import Scan


class FindingCategory(str, enum.Enum):
    """Area of the repository a finding relates to."""

    documentation = "documentation"
    testing = "testing"
    ci_cd = "ci_cd"
    deployment = "deployment"
    configuration = "configuration"
    dependencies = "dependencies"


class Severity(str, enum.Enum):
    """How serious a finding is (drives the score weight)."""

    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class Finding(Base, TimestampMixin):
    """A single missing item detected during a scan."""

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    scan_id: Mapped[int] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    check_id: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[FindingCategory] = mapped_column(
        Enum(FindingCategory, name="finding_category", values_callable=_enum_values),
        nullable=False,
    )
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, name="severity", values_callable=_enum_values),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    scan: Mapped["Scan"] = relationship(back_populates="findings")
