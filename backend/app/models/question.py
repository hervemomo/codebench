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

    project = relationship("Project", back_populates="questions")
    datasets = relationship("Dataset", back_populates="question", cascade="all, delete-orphan")
    coding_runs = relationship("CodingRun", back_populates="question", cascade="all, delete-orphan")
