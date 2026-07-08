"""Data-access layer: all SQL/ORM queries live here.

Functions take an explicit ``Session`` so the service layer owns transaction
boundaries. Nothing here contains business rules.
"""
from __future__ import annotations

from typing import Optional, Sequence

from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from .enums import CopyStatus
from .models import Book, BookCopy, Loan, Member


# --------------------------------------------------------------------------- #
# Books
# --------------------------------------------------------------------------- #
def add_book(session: Session, *, title: str, author: str, isbn: Optional[str]) -> Book:
    book = Book(title=title, author=author, isbn=isbn)
    session.add(book)
    session.flush()
    return book


def get_book(session: Session, book_id: int) -> Optional[Book]:
    return session.get(Book, book_id)


def list_books(
    session: Session, *, query: Optional[str], limit: int, offset: int
) -> Sequence[Book]:
    stmt = select(Book)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(or_(Book.title.ilike(like), Book.author.ilike(like)))
    stmt = stmt.order_by(Book.id).limit(limit).offset(offset)
    return session.scalars(stmt).all()


def copy_counts(session: Session, book_id: int) -> tuple[int, int]:
    """Return (total_copies, available_copies) for a book."""
    total = session.scalar(
        select(func.count()).select_from(BookCopy).where(BookCopy.book_id == book_id)
    )
    available = session.scalar(
        select(func.count())
        .select_from(BookCopy)
        .where(BookCopy.book_id == book_id, BookCopy.status == CopyStatus.AVAILABLE)
    )
    return int(total or 0), int(available or 0)


# --------------------------------------------------------------------------- #
# Copies
# --------------------------------------------------------------------------- #
def add_copy(
    session: Session,
    *,
    book_id: int,
    barcode: str,
    condition,
    shelf_location: Optional[str],
) -> BookCopy:
    copy = BookCopy(
        book_id=book_id,
        barcode=barcode,
        status=CopyStatus.AVAILABLE,
        condition=condition,
        shelf_location=shelf_location,
    )
    session.add(copy)
    session.flush()
    return copy


def get_copy(session: Session, copy_id: int) -> Optional[BookCopy]:
    return session.get(BookCopy, copy_id)


def get_copy_for_update(session: Session, copy_id: int) -> Optional[BookCopy]:
    stmt = select(BookCopy).where(BookCopy.id == copy_id).with_for_update()
    return session.scalars(stmt).first()


def lock_available_copy(session: Session, book_id: int) -> Optional[BookCopy]:
    """Pick and lock one AVAILABLE copy of a book.

    ``FOR UPDATE SKIP LOCKED`` lets concurrent borrows of the same title grab
    *different* copies without blocking each other.
    """
    stmt = (
        select(BookCopy)
        .where(BookCopy.book_id == book_id, BookCopy.status == CopyStatus.AVAILABLE)
        .order_by(BookCopy.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return session.scalars(stmt).first()


def list_copies(
    session: Session, *, book_id: Optional[int], limit: int, offset: int
) -> Sequence[BookCopy]:
    stmt = select(BookCopy)
    if book_id:
        stmt = stmt.where(BookCopy.book_id == book_id)
    stmt = stmt.order_by(BookCopy.id).limit(limit).offset(offset)
    return session.scalars(stmt).all()


# --------------------------------------------------------------------------- #
# Members
# --------------------------------------------------------------------------- #
def add_member(
    session: Session, *, name: str, email: str, phone: Optional[str]
) -> Member:
    member = Member(name=name, email=email, phone=phone)
    session.add(member)
    session.flush()
    return member


def get_member(session: Session, member_id: int) -> Optional[Member]:
    return session.get(Member, member_id)


def list_members(
    session: Session, *, query: Optional[str], limit: int, offset: int
) -> Sequence[Member]:
    stmt = select(Member)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(or_(Member.name.ilike(like), Member.email.ilike(like)))
    stmt = stmt.order_by(Member.id).limit(limit).offset(offset)
    return session.scalars(stmt).all()


# --------------------------------------------------------------------------- #
# Loans
# --------------------------------------------------------------------------- #
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
