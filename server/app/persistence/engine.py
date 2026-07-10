"""Database engine and session factory.

Creates a single process-wide SQLAlchemy engine and a ``SessionLocal`` factory
used by ``unit_of_work`` to open short-lived sessions per request/operation.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# pool_pre_ping: verify connections before use so a restarted Postgres does not
# hand out stale sockets from the pool.
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

# autoflush=False: callers flush explicitly when they need DB-generated IDs.
# expire_on_commit=False: detached objects keep loaded attributes after commit
# (services expunge entities before returning them to the gRPC layer).
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
