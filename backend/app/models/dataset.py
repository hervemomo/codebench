from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TenantMixin


class Dataset(TenantMixin, Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    file_key: Mapped[str] = mapped_column(String(512), nullable=False)
    sheet: Mapped[str] = mapped_column(String(255), nullable=False, default="0")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded")

    question = relationship("Question", back_populates="datasets")
    responses = relationship("Response", back_populates="dataset", cascade="all, delete-orphan")
