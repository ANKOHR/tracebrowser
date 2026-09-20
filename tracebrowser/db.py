from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def configure_database(url: str | None = None):
    """Configure a SQLite fallback or a PostgreSQL-compatible SQLAlchemy URL."""
    global _engine, _SessionLocal
    database_url = url or os.getenv("DATABASE_URL", "sqlite:///./tracebrowser.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("sqlite:///"):
        db_path = database_url.removeprefix("sqlite:///")
        if db_path not in {":memory:", ""}:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        connect_args = {"check_same_thread": False}
    else:
        connect_args = {}
    _engine = create_engine(
        database_url, future=True, pool_pre_ping=True, connect_args=connect_args
    )
    _SessionLocal = sessionmaker(
        bind=_engine, autoflush=False, expire_on_commit=False, class_=Session
    )
    return _engine


configure_database()


def create_tables() -> None:
    from . import models  # noqa: F401

    assert _engine is not None
    Base.metadata.create_all(_engine)


def session_factory() -> sessionmaker[Session]:
    if _SessionLocal is None:
        configure_database()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    session = session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
