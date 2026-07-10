"""SQLAlchemy declarative base and PostgreSQL ENUM column helper.

``pg_enum`` binds Python enums to existing Postgres ENUM types (created by
Alembic) so ORM columns stay in sync with the database without re-creating types.
"""
from __future__ import annotations

from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Root metadata registry for all ORM table mappings."""
    pass


def pg_enum(py_enum, name: str) -> SAEnum:
    """A PostgreSQL ENUM column bound to a Python enum, keyed by ``value``."""
    return SAEnum(
        py_enum,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        native_enum=True,
        create_type=False,  # types are created by migrations, not ORM
    )
