from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TenantMixin


class Project(TenantMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    context: Mapped[str] = mapped_column(String, nullable=False, default="")
    source_lang: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    target_lang: Mapped[str] = mapped_column(String(8), nullable=False, default="fr")
    codebook_lang: Mapped[str] = mapped_column(String(8), nullable=False, default="fr")

    organization = relationship("Organization", back_populates="projects")
    questions = relationship("Question", back_populates="project", cascade="all, delete-orphan")
