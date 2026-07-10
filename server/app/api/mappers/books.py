"""Map domain Book models to protobuf Book messages."""
from __future__ import annotations

import library_pb2 as pb

from app.persistence.models import Book


def book_to_pb(book: Book, total: int, available: int) -> pb.Book:
    return pb.Book(
        id=book.id,
        title=book.title,
        author=book.author,
        isbn=book.isbn or "",
        total_copies=total,
        available_copies=available,
    )
