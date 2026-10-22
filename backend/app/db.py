"""SQLite 引擎与会话管理。WAL + 外键，单文件数据库便于服务器备份。"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models import Base

_engine = None
SessionLocal: sessionmaker[Session] | None = None


def _build_url() -> str:
    path = Path(settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def get_engine():
    global _engine, SessionLocal
    if _engine is None:
        _engine = create_engine(
            _build_url(),
            connect_args={"check_same_thread": False, "timeout": 30},
            pool_pre_ping=True,
            future=True,
        )

        @event.listens_for(_engine, "connect")
        def _set_pragma(dbapi_conn, _record):  # pragma: no cover - 连接级副作用
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()

        SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    get_engine()
    assert SessionLocal is not None
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI 依赖。"""
    get_engine()
    assert SessionLocal is not None
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
