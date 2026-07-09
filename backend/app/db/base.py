"""Declarative base, engine, and session factory."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def get_engine():
    return create_engine(get_settings().database_url, future=True)


SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


def get_db_session() -> Session:
    """FastAPI-style dependency: yields a session, closes it after the request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
