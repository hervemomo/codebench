from __future__ import annotations

from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TenantMixin


class CodeAssignment(TenantMixin, Base):
    """Long format: one row per (response, run, code)."""

    __tablename__ = "code_assignments"
    __table_args__ = (UniqueConstraint("response_id", "run_id", "code_id", name="uq_code_assignment_response_run_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    response_id: Mapped[int] = mapped_column(ForeignKey("responses.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("coding_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    code_id: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    response = relationship("Response", back_populates="code_assignments")
    run = relationship("CodingRun", back_populates="code_assignments")
