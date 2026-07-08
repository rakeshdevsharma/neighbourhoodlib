"""SQLAlchemy ORM models (per-copy data model).

Schema is owned by the Alembic migration; these models mirror it. The PostgreSQL
ENUM types are created by the migration, so columns reference them with
``create_type=False`` to avoid duplicate-creation attempts.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .enums import (
    COPY_CONDITION_PG,
    COPY_STATUS_PG,
    MEMBER_STATUS_PG,
    CopyCondition,
    CopyStatus,
    MemberStatus,
)


class Base(DeclarativeBase):
    pass


def _pg_enum(py_enum, name: str) -> SAEnum:
    """A PostgreSQL ENUM column bound to a Python enum, keyed by ``value``."""
    return SAEnum(
        py_enum,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        native_enum=True,
        create_type=False,
    )


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(Text, nullable=False)
    isbn: Mapped[Optional[str]] = mapped_column(Text, unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    copies: Mapped[list["BookCopy"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )


class BookCopy(Base):
    __tablename__ = "book_copies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    barcode: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    status: Mapped[CopyStatus] = mapped_column(
        _pg_enum(CopyStatus, COPY_STATUS_PG), nullable=False, default=CopyStatus.AVAILABLE
    )
    condition: Mapped[Optional[CopyCondition]] = mapped_column(
        _pg_enum(CopyCondition, COPY_CONDITION_PG), nullable=True
    )
    shelf_location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    book: Mapped[Book] = relationship(back_populates="copies")
    loans: Mapped[list["Loan"]] = relationship(back_populates="copy")


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[MemberStatus] = mapped_column(
        _pg_enum(MemberStatus, MEMBER_STATUS_PG), nullable=False, default=MemberStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    loans: Mapped[list["Loan"]] = relationship(back_populates="member")


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    copy_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("book_copies.id"), nullable=False
    )
    member_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("members.id"), nullable=False
    )
    borrowed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    returned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fine_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    copy: Mapped[BookCopy] = relationship(back_populates="loans")
    member: Mapped[Member] = relationship(back_populates="loans")
