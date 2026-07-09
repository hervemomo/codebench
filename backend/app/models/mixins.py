"""Shared mixins for tenant-scoped models.

Every tenant table gets a non-nullable, indexed `org_id` FK from day one —
see `app/db/scoped.py` for the mandatory query-scoping layer built on top.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TenantMixin(TimestampMixin):
    """Adds a mandatory, indexed org_id FK. Mix in before Base for every tenant table."""

    @declared_attr
    def org_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
