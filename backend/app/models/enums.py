"""Python enums backing SQLAlchemy Enum columns."""

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ANALYST = "analyst"


class CodingRunKind(str, enum.Enum):
    S2 = "s2"
    S3 = "s3"
    SPLIT = "split"
    MERGE = "merge"


class CodingRunStatus(str, enum.Enum):
    """Human-in-the-loop review gate: DRAFT (codes proposed, awaiting review)
    -> REVIEWED (finalized, ready to apply) -> APPLIED (coding job has run)."""

    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPLIED = "applied"
