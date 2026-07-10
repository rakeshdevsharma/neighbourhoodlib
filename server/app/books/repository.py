"""Data-access layer for books and physical copies."""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.enums import CopyStatus
from app.persistence.models import Book, BookCopy


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
