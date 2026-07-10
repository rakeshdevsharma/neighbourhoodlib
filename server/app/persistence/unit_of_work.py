"""Session scope for transactional operations."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session

from app.persistence.engine import SessionLocal


@contextmanager
def unit_of_work() -> Iterator[Session]:
    """Session scope that commits on success and rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
