# ./app/db/session.py

from __future__ import annotations
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path

from app.core.config import settings
from app.db.models.base import Base

# 모델 강제 import (생략 금지)
from app.db.models import project as _p  # noqa: F401
from app.db.models import scenario as _s  # noqa: F401
from app.db.models import report_job as _r  # noqa: F401

from app.core.fs import ensure_dirs
ensure_dirs()


def _ensure_sqlite_dir(url: str) -> None:
    """sqlite:///path/to/db.sqlite 형태에서 폴더 자동 생성"""
    if not url.startswith("sqlite"):
        return
    # sqlite:///./.data/aquanova.db → "./.data/aquanova.db"
    path_part = url.split("///", 1)[1] if "///" in url else url.split("//", 1)[1]
    path_part = path_part.split("?", 1)[0]
    try:
        Path(path_part).parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

_ensure_sqlite_dir(settings.DB_URL)

engine = create_engine(
    settings.DB_URL,
    connect_args={"check_same_thread": False} if settings.DB_URL.startswith("sqlite") else {},
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
    expire_on_commit=False,
)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
