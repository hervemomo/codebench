"""Mandatory org-scoping layer.

Direct `select(<TenantModel>)` / `session.query(<TenantModel>)` calls against
tenant tables are forbidden outside this module — enforced by convention and
by `scripts/check_org_scoping.sh` in CI. No caller may ever trust a
client-supplied `org_id`; it always comes from the authenticated session
(wired up in Sequence 3).
"""

from __future__ import annotations

from typing import Generic, Optional, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

ModelT = TypeVar("ModelT")


def scoped_query(session: Session, model: type[ModelT], org_id: int) -> Select:
    """Return a SELECT for `model` restricted to `org_id`.

    The only sanctioned way to query a tenant table. `model` must have an
    `org_id` column (every tenant model does — see `app.models.mixins.TenantMixin`).
    """
    return select(model).where(model.org_id == org_id)


class ScopedRepository(Generic[ModelT]):
    """Thin repository base: every read/write goes through org_id scoping."""

    model: type[ModelT]

    def __init__(self, session: Session, org_id: int):
        self.session = session
        self.org_id = org_id

    def query(self) -> Select:
        return scoped_query(self.session, self.model, self.org_id)

    def list(self) -> list[ModelT]:
        return list(self.session.scalars(self.query()).all())

    def get(self, obj_id: int) -> ModelT | None:
        return self.session.scalars(self.query().where(self.model.id == obj_id)).first()

    def add(self, obj: ModelT) -> ModelT:
        obj.org_id = self.org_id
        self.session.add(obj)
        return obj


# ── Pre-auth lookups ─────────────────────────────────────────────────────────
#
# The ONE sanctioned exception to org-scoping: determining which org a user
# belongs to is the whole point of these two queries, so no org_id can exist
# yet. Keeping them here (not in app/auth.py) means the org-scoping grep check
# doesn't need special-casing beyond its existing "outside this module" rule.


def find_user_by_email(session: Session, email: str) -> Optional["User"]:  # noqa: F821
    """Login lookup. Returns None if no user has this email."""
    from app.models import User

    return session.execute(select(User).where(User.email == email)).scalars().one_or_none()


def get_user_by_id_unscoped(session: Session, user_id: int) -> Optional["User"]:  # noqa: F821
    """Session-resolution lookup: the cookie carries only a user id; org_id is
    read off the row itself and becomes the org_id for the rest of the request."""
    from app.models import User

    return session.get(User, user_id)
