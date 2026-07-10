"""Data-access layer for books and physical copies.

Repositories contain SQL only — no validation or business rules. Callers pass
an open ``Session`` so multiple reads/writes share one transaction.
"""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.enums import CopyStatus
from app.persistence.models import Book, BookCopy


def add_book(session: Session, *, title: str, author: str, isbn: Optional[str]) -> Book:
    """INSERT a new ``books`` row and return the ORM object.

  ``session.add`` stages the insert; ``flush()`` sends SQL immediately so the
  auto-generated ``id`` is available without committing the transaction.
  """
    book = Book(title=title, author=author, isbn=isbn)
    session.add(book)
    session.flush()
    return book


def get_book(session: Session, book_id: int) -> Optional[Book]:
    """Primary-key lookup by id. Returns None if the row does not exist."""
    return session.get(Book, book_id)


def list_books(
    session: Session, *, query: Optional[str], limit: int, offset: int
) -> Sequence[Book]:
    """SELECT books with optional search and pagination.

  Builds a SQLAlchemy ``select()`` statement dynamically. ``ilike`` is Postgres
  case-insensitive pattern match; ``%query%`` matches substrings. Results are
  ordered by id for stable pagination.
  """
    stmt = select(Book)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(or_(Book.title.ilike(like), Book.author.ilike(like)))
    stmt = stmt.order_by(Book.id).limit(limit).offset(offset)
    return session.scalars(stmt).all()


def copy_counts(session: Session, book_id: int) -> tuple[int, int]:
    """Run two COUNT queries: all copies vs. those with status AVAILABLE.

  ``session.scalar()`` runs an aggregate query and returns a single number.
  Used by the service layer to enrich book responses without loading every copy.
  """
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
    """INSERT a new ``book_copies`` row defaulting to AVAILABLE status."""
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
    """Primary-key lookup for a physical copy."""
    return session.get(BookCopy, copy_id)


def get_copy_for_update(session: Session, copy_id: int) -> Optional[BookCopy]:
    """Load a copy and lock its row until the transaction ends.

  ``with_for_update()`` appends ``FOR UPDATE`` to the SQL, preventing other
  transactions from modifying (or SKIP LOCKING) this row until we commit/rollback.
  Used during borrow, return, and copy status changes.
  """
    stmt = select(BookCopy).where(BookCopy.id == copy_id).with_for_update()
    return session.scalars(stmt).first()


def lock_available_copy(session: Session, book_id: int) -> Optional[BookCopy]:
    """Atomically claim one AVAILABLE copy of a book for lending.

  ``FOR UPDATE SKIP LOCKED`` (Postgres-specific): if another transaction already
  locked the first available copy, this query skips it and grabs the next one
  instead of waiting. That lets two patrons borrow different copies of the same
  title concurrently without deadlocks.
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
    """SELECT copies, optionally restricted to one book, with pagination."""
    stmt = select(BookCopy)
    if book_id:
        stmt = stmt.where(BookCopy.book_id == book_id)
    stmt = stmt.order_by(BookCopy.id).limit(limit).offset(offset)
    return session.scalars(stmt).all()
