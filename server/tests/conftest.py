"""Pytest fixtures.

These tests exercise the real service + repository layers against a PostgreSQL
database (needed for ENUM types, partial unique indexes, and SKIP LOCKED). Point
TEST_DATABASE_URL at a throwaway database; the schema is applied via Alembic and
tables are truncated between tests.

    createdb library_test   # or use the compose db + a separate database
    TEST_DATABASE_URL=postgresql+psycopg://library:library@localhost:5432/library_test \
        python -m pytest -v
"""
from __future__ import annotations

import os

# Must be set before importing app modules (config reads it at import time).
TEST_DB = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://library:library@localhost:5432/library_test",
)
os.environ["DATABASE_URL"] = TEST_DB

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """Apply migrations once for the test session."""
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncate all data before each test for isolation."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE loans, book_copies, members, books "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield
