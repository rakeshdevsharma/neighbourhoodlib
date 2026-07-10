"""ORM model for a borrowing transaction (loan).

A loan ties one member to one copy for a period bounded by ``borrowed_at``,
``due_at``, and optionally ``returned_at``. Fines are computed on return.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import Base

if TYPE_CHECKING:
    from app.persistence.models.book import BookCopy
    from app.persistence.models.member import Member


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

    copy: Mapped["BookCopy"] = relationship(back_populates="loans")
    member: Mapped["Member"] = relationship(back_populates="loans")
