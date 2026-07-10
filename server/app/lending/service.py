"""Business logic for borrow, return, and loan queries.

Borrowing atomically locks a copy, flips its status to ON_LOAN, and inserts a
loan row. The partial unique index ``one_open_loan_per_copy`` is the database
backstop against double-borrow races.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.books import repository as books_repo
from app.core.config import settings
from app.core.enums import CopyCondition, CopyStatus, MemberStatus
from app.core.errors import FailedPrecondition, InvalidArgument, NotFound
from app.lending import repository as repo
from app.members import repository as members_repo
from app.persistence.models import Loan
from app.persistence.unit_of_work import unit_of_work


def _now() -> datetime:
    return datetime.now(timezone.utc)


def borrow_book(
    *, member_id: int, book_id: Optional[int], copy_id: Optional[int]
) -> Loan:
    if not book_id and not copy_id:
        raise InvalidArgument("either book_id or copy_id must be provided")
    with unit_of_work() as s:
        member = members_repo.get_member(s, member_id)
        if member is None:
            raise NotFound(f"member {member_id} not found")
        if member.status != MemberStatus.ACTIVE:
            raise FailedPrecondition("member is not active and cannot borrow")

        if copy_id:
            # Lend a specific copy (e.g. barcode scan at the desk).
            copy = books_repo.get_copy_for_update(s, copy_id)
            if copy is None:
                raise NotFound(f"copy {copy_id} not found")
            if copy.status != CopyStatus.AVAILABLE:
                raise FailedPrecondition(f"copy {copy_id} is not available")
        else:
            # Lend any available copy of the requested title.
            copy = books_repo.lock_available_copy(s, book_id)
            if copy is None:
                if books_repo.get_book(s, book_id) is None:
                    raise NotFound(f"book {book_id} not found")
                raise FailedPrecondition("no available copies for this book")

        now = _now()
        due = now + timedelta(days=settings.loan_period_days)
        copy.status = CopyStatus.ON_LOAN
        try:
            loan = repo.add_loan(
                s, copy_id=copy.id, member_id=member_id, borrowed_at=now, due_at=due
            )
            s.flush()
        except IntegrityError as e:
            # Lost race on one_open_loan_per_copy partial unique index.
            raise FailedPrecondition("copy was just borrowed by someone else") from e
        loan = _reload_loan(s, loan.id)
        return loan


def return_book(*, loan_id: int, mark_damaged: bool) -> Loan:
    with unit_of_work() as s:
        loan = repo.get_loan_for_update(s, loan_id)
        if loan is None:
            raise NotFound(f"loan {loan_id} not found")
        if loan.returned_at is not None:
            raise FailedPrecondition("loan has already been returned")

        now = _now()
        loan.returned_at = now
        loan.fine_cents = _compute_fine(loan.due_at, now)

        copy = books_repo.get_copy_for_update(s, loan.copy_id)
        copy.status = CopyStatus.DAMAGED if mark_damaged else CopyStatus.AVAILABLE
        if mark_damaged:
            copy.condition = CopyCondition.WORN
        s.flush()
        return _reload_loan(s, loan.id)


def list_loans(
    *, member_id: Optional[int], status_filter: Optional[str], limit: int, offset: int
) -> list[Loan]:
    with unit_of_work() as s:
        loans = list(
            repo.list_loans(
                s,
                member_id=member_id,
                status_filter=status_filter,
                now=_now(),
                limit=limit,
                offset=offset,
            )
        )
        # Touch relationships so they are loaded before expunge (for proto mapping).
        for ln in loans:
            _ = ln.copy.book.title, ln.member.name
        for ln in loans:
            s.expunge(ln)
        return loans


def _compute_fine(due_at: datetime, returned_at: datetime) -> int:
    """Late fines: one billing day per partial day past due, in cents."""
    if returned_at <= due_at:
        return 0
    days_late = math.ceil((returned_at - due_at).total_seconds() / 86400)
    return days_late * settings.fine_cents_per_day


def _reload_loan(s: Session, loan_id: int) -> Loan:
    """Fetch a loan and load copy/book/member before detaching it for mapping."""
    loan = repo.get_loan_for_update(s, loan_id)
    _ = loan.copy.book.title, loan.copy.barcode, loan.member.name
    s.expunge(loan)
    return loan
