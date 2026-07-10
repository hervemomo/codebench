from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TenantMixin


class Question(TenantMixin, Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(String, nullable=False)
    survey_col: Mapped[str] = mapped_column(String(255), nullable=False)
    # Bookkeeping pointer only (notebook 0-G reset) -- moved by POST
    # /api/questions/{id}/reset, auto-advanced whenever a run finishes apply.
    # Nothing is ever deleted by moving it; SET NULL if the pointed-to run goes away.
    active_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("coding_runs.id", ondelete="SET NULL"), nullable=True
    )

    project = relationship("Project", back_populates="questions")
    datasets = relationship("Dataset", back_populates="question", cascade="all, delete-orphan")
    coding_runs = relationship("CodingRun", back_populates="question", cascade="all, delete-orphan", foreign_keys="CodingRun.question_id")
    active_run = relationship("CodingRun", foreign_keys=[active_run_id])
