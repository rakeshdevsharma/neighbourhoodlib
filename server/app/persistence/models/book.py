from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    COPY_CONDITION_PG,
    COPY_STATUS_PG,
    CopyCondition,
    CopyStatus,
)
from app.persistence.models.base import Base, pg_enum

if TYPE_CHECKING:
    from app.persistence.models.loan import Loan


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
        pg_enum(CopyStatus, COPY_STATUS_PG), nullable=False, default=CopyStatus.AVAILABLE
    )
    condition: Mapped[Optional[CopyCondition]] = mapped_column(
        pg_enum(CopyCondition, COPY_CONDITION_PG), nullable=True
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
