"""Session scope for transactional operations.

Each service function wraps its work in ``unit_of_work()`` so that a single
database transaction spans validation, reads, and writes. Commit happens only
if the block exits normally; any exception triggers a rollback.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session

from app.persistence.engine import SessionLocal


@contextmanager
def unit_of_work() -> Iterator[Session]:
    """Yield a session that commits on success and rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
