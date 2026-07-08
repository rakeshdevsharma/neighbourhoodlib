"""Business logic. gRPC-agnostic; raises domain errors from ``errors.py``.

Each mutating operation runs in a single transaction. Borrow/return use row
locking so concurrent staff actions stay correct; the DB's partial unique index
(``one_open_loan_per_copy``) is the final backstop.
"""
from __future__ import annotations

import math
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import repositories as repo
from . import validation as v
from .config import settings
from .enums import CopyCondition, CopyStatus, MemberStatus
from .errors import AlreadyExists, FailedPrecondition, InvalidArgument, NotFound
from .db import SessionLocal
from .models import Book, BookCopy, Loan, Member


def _now() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def unit_of_work() -> Iterator[Session]:
    """Session scope that commits on success and rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# =============================================================================
# Books
# =============================================================================
def create_book(*, title: str, author: str, isbn: Optional[str]) -> Book:
    title = v.require_non_empty(title, "title")
    author = v.require_non_empty(author, "author")
    isbn = v.validate_isbn(isbn)
    with unit_of_work() as s:
        try:
            book = repo.add_book(s, title=title, author=author, isbn=isbn)
            s.flush()
        except IntegrityError as e:
            raise AlreadyExists("a book with this isbn already exists") from e
        s.expunge(book)
        return book


def update_book(*, book_id: int, title: str, author: str, isbn: Optional[str]) -> Book:
    title = v.require_non_empty(title, "title")
    author = v.require_non_empty(author, "author")
    isbn = v.validate_isbn(isbn)
    with unit_of_work() as s:
        book = repo.get_book(s, book_id)
        if book is None:
            raise NotFound(f"book {book_id} not found")
        book.title, book.author, book.isbn = title, author, isbn
        try:
            s.flush()
        except IntegrityError as e:
            raise AlreadyExists("a book with this isbn already exists") from e
        s.expunge(book)
        return book


def get_book_with_counts(book_id: int) -> tuple[Book, int, int]:
    with unit_of_work() as s:
        book = repo.get_book(s, book_id)
        if book is None:
            raise NotFound(f"book {book_id} not found")
        total, available = repo.copy_counts(s, book_id)
        s.expunge(book)
        return book, total, available


def list_books(*, query: Optional[str], limit: int, offset: int) -> list[tuple[Book, int, int]]:
    with unit_of_work() as s:
        books = repo.list_books(s, query=query, limit=limit, offset=offset)
        result = []
        for b in books:
            total, available = repo.copy_counts(s, b.id)
            s.expunge(b)
            result.append((b, total, available))
        return result


# =============================================================================
# Copies
# =============================================================================
def add_copy(
    *, book_id: int, barcode: str, condition: Optional[CopyCondition], shelf_location: Optional[str]
) -> BookCopy:
    barcode = v.require_non_empty(barcode, "barcode")
    shelf_location = v.normalize_optional(shelf_location)
    with unit_of_work() as s:
        if repo.get_book(s, book_id) is None:
            raise NotFound(f"book {book_id} not found")
        try:
            copy = repo.add_copy(
                s,
                book_id=book_id,
                barcode=barcode,
                condition=condition,
                shelf_location=shelf_location,
            )
            s.flush()
        except IntegrityError as e:
            raise AlreadyExists(f"a copy with barcode '{barcode}' already exists") from e
        s.expunge(copy)
        return copy


def update_copy(
    *,
    copy_id: int,
    status: Optional[CopyStatus],
    condition: Optional[CopyCondition],
    shelf_location: Optional[str],
) -> BookCopy:
    with unit_of_work() as s:
        copy = repo.get_copy_for_update(s, copy_id)
        if copy is None:
            raise NotFound(f"copy {copy_id} not found")
        if status is not None:
            # Guard against manually contradicting an active loan.
            if status != CopyStatus.ON_LOAN and repo.open_loan_for_copy(s, copy_id):
                raise FailedPrecondition(
                    "copy has an open loan; return it before changing status"
                )
            copy.status = status
        if condition is not None:
            copy.condition = condition
        if shelf_location is not None:
            copy.shelf_location = v.normalize_optional(shelf_location)
        s.flush()
        s.expunge(copy)
        return copy


def list_copies(*, book_id: Optional[int], limit: int, offset: int) -> list[BookCopy]:
    with unit_of_work() as s:
        copies = list(repo.list_copies(s, book_id=book_id, limit=limit, offset=offset))
        for c in copies:
            s.expunge(c)
        return copies


# =============================================================================
# Members
# =============================================================================
def create_member(*, name: str, email: str, phone: Optional[str]) -> Member:
    name = v.require_non_empty(name, "name")
    email = v.require_valid_email(email)
    phone = v.normalize_optional(phone)
    with unit_of_work() as s:
        try:
            member = repo.add_member(s, name=name, email=email, phone=phone)
            s.flush()
        except IntegrityError as e:
            raise AlreadyExists(f"a member with email '{email}' already exists") from e
        s.expunge(member)
        return member


def update_member(
    *, member_id: int, name: str, email: str, phone: Optional[str], status: Optional[MemberStatus]
) -> Member:
    name = v.require_non_empty(name, "name")
    email = v.require_valid_email(email)
    phone = v.normalize_optional(phone)
    with unit_of_work() as s:
        member = repo.get_member(s, member_id)
        if member is None:
            raise NotFound(f"member {member_id} not found")
        member.name, member.email, member.phone = name, email, phone
        if status is not None:
            member.status = status
        try:
            s.flush()
        except IntegrityError as e:
            raise AlreadyExists(f"a member with email '{email}' already exists") from e
        s.expunge(member)
        return member


def get_member(member_id: int) -> Member:
    with unit_of_work() as s:
        member = repo.get_member(s, member_id)
        if member is None:
            raise NotFound(f"member {member_id} not found")
        s.expunge(member)
        return member


def list_members(*, query: Optional[str], limit: int, offset: int) -> list[Member]:
    with unit_of_work() as s:
        members = list(repo.list_members(s, query=query, limit=limit, offset=offset))
        for m in members:
            s.expunge(m)
        return members


# =============================================================================
# Lending
# =============================================================================
def borrow_book(
    *, member_id: int, book_id: Optional[int], copy_id: Optional[int]
) -> Loan:
    if not book_id and not copy_id:
        raise InvalidArgument("either book_id or copy_id must be provided")
    with unit_of_work() as s:
        member = repo.get_member(s, member_id)
        if member is None:
            raise NotFound(f"member {member_id} not found")
        if member.status != MemberStatus.ACTIVE:
            raise FailedPrecondition("member is not active and cannot borrow")

        if copy_id:
            copy = repo.get_copy_for_update(s, copy_id)
            if copy is None:
                raise NotFound(f"copy {copy_id} not found")
            if copy.status != CopyStatus.AVAILABLE:
                raise FailedPrecondition(f"copy {copy_id} is not available")
        else:
            copy = repo.lock_available_copy(s, book_id)
            if copy is None:
                if repo.get_book(s, book_id) is None:
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
            # one_open_loan_per_copy backstop: lost a race for this copy.
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

        copy = repo.get_copy_for_update(s, loan.copy_id)
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
        # Access relationships while the session is open, then detach.
        for ln in loans:
            _ = ln.copy.book.title, ln.member.name
        for ln in loans:
            s.expunge(ln)
        return loans


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _compute_fine(due_at: datetime, returned_at: datetime) -> int:
    if returned_at <= due_at:
        return 0
    days_late = math.ceil((returned_at - due_at).total_seconds() / 86400)
    return days_late * settings.fine_cents_per_day


def _reload_loan(s: Session, loan_id: int) -> Loan:
    """Fetch a loan and load copy/book/member before detaching it for mapping."""
    loan = repo.get_loan_for_update(s, loan_id)
    # Touch relationships so they are populated before expunge (no lazy load
    # after the session closes).
    _ = loan.copy.book.title, loan.copy.barcode, loan.member.name
    s.expunge(loan)
    return loan
