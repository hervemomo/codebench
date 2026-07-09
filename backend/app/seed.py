"""Seed a demo org/user/project/question for manual browsing. Idempotent.

Usage: python -m app.seed
"""

from __future__ import annotations

import hashlib

from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.scoped import scoped_query
from app.models import Organization, Project, Question, User, UserRole
from app.storage import ensure_bucket


def _dev_password_hash(password: str) -> str:
    # Placeholder only — Sequence 3 replaces this with real argon2/bcrypt hashing.
    return "sha256$" + hashlib.sha256(password.encode()).hexdigest()


def seed() -> dict:
    session = SessionLocal()
    try:
        # Organization is the tenant root, not itself tenant-scoped — querying
        # it directly is expected and outside check_org_scoping.sh's rule.
        org = session.execute(select(Organization).where(Organization.name == "Demo Org")).scalars().one_or_none()
        if org is None:
            org = Organization(name="Demo Org")
            session.add(org)
            session.flush()

        user = session.execute(
            scoped_query(session, User, org.id).where(User.email == "demo@codebench.local")
        ).scalars().one_or_none()
        if user is None:
            user = User(
                org_id=org.id, email="demo@codebench.local",
                password_hash=_dev_password_hash("changeme"), role=UserRole.ADMIN,
            )
            session.add(user)
            session.flush()

        project = session.execute(
            scoped_query(session, Project, org.id).where(Project.name == "Demo Project")
        ).scalars().one_or_none()
        if project is None:
            project = Project(
                org_id=org.id, name="Demo Project",
                context="Consumers of a beverage brand describe what they like about it.",
                source_lang="en", target_lang="fr", codebook_lang="fr",
            )
            session.add(project)
            session.flush()

        question = session.execute(
            scoped_query(session, Question, org.id).where(Question.project_id == project.id)
        ).scalars().one_or_none()
        if question is None:
            question = Question(
                org_id=org.id, project_id=project.id,
                text="Pourquoi préférez-vous cette boisson ?", survey_col="feedback",
            )
            session.add(question)
            session.flush()

        session.commit()
        ensure_bucket()

        return {"org_id": org.id, "user_id": user.id, "project_id": project.id, "question_id": question.id}
    finally:
        session.close()


if __name__ == "__main__":
    result = seed()
    print(f"Seeded demo data: {result}")
