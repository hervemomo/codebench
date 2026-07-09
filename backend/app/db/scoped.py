"""Mandatory org-scoping layer.

Direct `select(<TenantModel>)` / `session.query(<TenantModel>)` calls against
tenant tables are forbidden outside this module — enforced by convention and
by `scripts/check_org_scoping.sh` in CI. No caller may ever trust a
client-supplied `org_id`; it always comes from the authenticated session
(wired up in Sequence 3).
"""

from __future__ import annotations

from typing import Generic, TypeVar

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
