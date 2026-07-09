from __future__ import annotations

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CodingRunKind, CodingRunStatus
from app.models.mixins import TenantMixin


class CodingRun(TenantMixin, Base):
    __tablename__ = "coding_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    # Self-referential checkpoint lineage (replaces notebook 0-G pickles). Kept
    # on SET NULL so deleting an ancestor run doesn't cascade-delete its
    # descendants — lineage is metadata, not an ownership relationship.
    parent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("coding_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )

    kind: Mapped[CodingRunKind] = mapped_column(SAEnum(CodingRunKind, name="coding_run_kind", native_enum=True), nullable=False)
    status: Mapped[CodingRunStatus] = mapped_column(
        SAEnum(CodingRunStatus, name="coding_run_status", native_enum=True), nullable=False, default=CodingRunStatus.DRAFT
    )

    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    codebook_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    token_usage: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    question = relationship("Question", back_populates="coding_runs")
    parent_run = relationship("CodingRun", remote_side=[id], back_populates="child_runs")
    child_runs = relationship("CodingRun", back_populates="parent_run")
    code_assignments = relationship("CodeAssignment", back_populates="run", cascade="all, delete-orphan")
    export_artifacts = relationship("ExportArtifact", back_populates="run", cascade="all, delete-orphan")
