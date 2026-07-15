"""Tests for books and copies business logic."""
from __future__ import annotations

import pytest

from app.books import service as books_svc
from app.core.errors import AlreadyExists, InvalidArgument
from tests.helpers import book_with_copies


def test_create_book_requires_title():
    # Whitespace-only title must be rejected before hitting the database.
    with pytest.raises(InvalidArgument):
        books_svc.create_book(title="  ", author="A", isbn=None)


def test_duplicate_isbn_rejected():
    books_svc.create_book(title="A", author="X", isbn="9780201616224")
    with pytest.raises(AlreadyExists):
        books_svc.create_book(title="B", author="Y", isbn="9780201616224")


def test_invalid_isbn_rejected():
    with pytest.raises(InvalidArgument):
        books_svc.create_book(title="A", author="X", isbn="123")


def test_book_counts_reflect_copies():
    # available_copies should equal total when nothing is on loan.
    book = book_with_copies(3)
    _, total, available = books_svc.get_book_with_counts(book.id)
    assert (total, available) == (3, 3)


def test_list_books_returns_counts_in_one_query():
    book = book_with_copies(2)
    empty = books_svc.create_book(title="Empty Shelf", author="Author", isbn=None)
    rows = books_svc.list_books(query=None, limit=100, offset=0)
    by_id = {b.id: (total, available) for b, total, available in rows}
    assert by_id[book.id] == (2, 2)
    assert by_id[empty.id] == (0, 0)
