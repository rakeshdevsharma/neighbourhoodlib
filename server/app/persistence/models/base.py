from __future__ import annotations

from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def pg_enum(py_enum, name: str) -> SAEnum:
    """A PostgreSQL ENUM column bound to a Python enum, keyed by ``value``."""
    return SAEnum(
        py_enum,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        native_enum=True,
        create_type=False,
    )
