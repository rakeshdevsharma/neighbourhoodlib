"""Domain enums, shared by the ORM models and the proto mappers.

The string ``value`` of each member is the exact label stored in the matching
PostgreSQL ENUM type (see the Alembic migration). Proto <-> domain translation
lives in ``mappers.py``.
"""
from __future__ import annotations

import enum


class CopyStatus(enum.Enum):
    AVAILABLE = "available"
    ON_LOAN = "on_loan"
    LOST = "lost"
    DAMAGED = "damaged"
    WITHDRAWN = "withdrawn"


class CopyCondition(enum.Enum):
    NEW = "new"
    GOOD = "good"
    WORN = "worn"


class MemberStatus(enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


# Names of the PostgreSQL ENUM types created by the migration.
COPY_STATUS_PG = "copy_status"
COPY_CONDITION_PG = "copy_condition"
MEMBER_STATUS_PG = "member_status"
