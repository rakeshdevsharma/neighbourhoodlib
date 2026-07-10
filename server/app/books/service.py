"""Business logic for bibliographic records and physical copies."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import IntegrityError

from app.books import repository as repo
from app.core import validation as v
from app.core.enums import CopyCondition, CopyStatus
from app.core.errors import AlreadyExists, FailedPrecondition, NotFound
from app.lending import repository as lending_repo
from app.persistence.models import Book, BookCopy
from app.persistence.unit_of_work import unit_of_work


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
            if status != CopyStatus.ON_LOAN and lending_repo.open_loan_for_copy(s, copy_id):
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
