"""Tests for books and copies business logic."""
from __future__ import annotations

import pytest

from app.books import service as books_svc
from app.core.errors import AlreadyExists, InvalidArgument
from tests.helpers import book_with_copies


def test_create_book_requires_title():
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
    book = book_with_copies(3)
    _, total, available = books_svc.get_book_with_counts(book.id)
    assert (total, available) == (3, 3)
