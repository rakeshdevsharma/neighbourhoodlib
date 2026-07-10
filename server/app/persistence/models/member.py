"""ORM model for library patrons (members).

Members borrow copies via loan rows. Email is the natural unique identifier;
status gates whether circulation is allowed.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import MEMBER_STATUS_PG, MemberStatus
from app.persistence.models.base import Base, pg_enum

if TYPE_CHECKING:
    from app.persistence.models.loan import Loan


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[MemberStatus] = mapped_column(
        pg_enum(MemberStatus, MEMBER_STATUS_PG), nullable=False, default=MemberStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    loans: Mapped[list["Loan"]] = relationship(back_populates="member")
