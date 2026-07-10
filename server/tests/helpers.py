"""Shared helpers for service-layer tests."""
from __future__ import annotations

from app.books import service as books_svc
from app.core.enums import CopyCondition
from app.members import service as members_svc


def book_with_copies(n: int = 1):
    book = books_svc.create_book(title="Test Book", author="Author", isbn=None)
    for i in range(n):
        books_svc.add_copy(
            book_id=book.id,
            barcode=f"BC-{book.id}-{i}",
            condition=CopyCondition.GOOD,
            shelf_location="A-1",
        )
    return book


def member(email="m@example.com"):
    return members_svc.create_member(name="Member", email=email, phone=None)
