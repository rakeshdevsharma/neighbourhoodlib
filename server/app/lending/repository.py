"""Data-access layer for loans.

Loan rows link a member to a physical copy for a borrowing period. Open loans
have ``returned_at IS NULL``; the schema enforces at most one open loan per copy.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, joinedload

from app.persistence.models import BookCopy, Loan, Member


def add_loan(
    session: Session, *, copy_id: int, member_id: int, borrowed_at, due_at
) -> Loan:
    loan = Loan(
        copy_id=copy_id, member_id=member_id, borrowed_at=borrowed_at, due_at=due_at
    )
    session.add(loan)
    session.flush()
    return loan


def get_loan_for_update(session: Session, loan_id: int) -> Optional[Loan]:
    stmt = select(Loan).where(Loan.id == loan_id).with_for_update()
    return session.scalars(stmt).first()


def open_loan_for_copy(session: Session, copy_id: int) -> Optional[Loan]:
    """Return the active (unreturned) loan for a copy, if any."""
    stmt = select(Loan).where(Loan.copy_id == copy_id, Loan.returned_at.is_(None))
    return session.scalars(stmt).first()


def list_loans(
    session: Session,
    *,
    member_id: Optional[int],
    status_filter: Optional[str],
    now: datetime,
    limit: int,
    offset: int,
) -> Sequence[Loan]:
    """List loans, eager-loading copy->book and member for display enrichment.

    ``status_filter`` is one of ``outstanding`` / ``returned`` / ``overdue`` or
    None for all.
    """
    stmt = select(Loan).options(
        joinedload(Loan.copy).joinedload(BookCopy.book),
        joinedload(Loan.member),
    )
    if member_id:
        stmt = stmt.where(Loan.member_id == member_id)
    if status_filter == "outstanding":
        stmt = stmt.where(Loan.returned_at.is_(None))
    elif status_filter == "returned":
        stmt = stmt.where(Loan.returned_at.is_not(None))
    elif status_filter == "overdue":
        stmt = stmt.where(and_(Loan.returned_at.is_(None), Loan.due_at < now))
    stmt = stmt.order_by(Loan.id.desc()).limit(limit).offset(offset)
    return session.scalars(stmt).all()
