"""Python enums backing SQLAlchemy Enum columns.

`CodingRun.status` is deliberately a plain string (not a DB enum) here —
Sequence 4 introduces the DRAFT/REVIEWED/APPLIED run-status enum via its own
migration, so we don't lock that shape in early.
"""

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
