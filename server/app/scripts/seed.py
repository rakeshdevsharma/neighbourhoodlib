"""Insert a small amount of sample data (idempotent-ish; ignores duplicates)."""
from __future__ import annotations

import logging

from app.books import service as books_svc
from app.core.enums import CopyCondition
from app.core.errors import AlreadyExists
from app.members import service as members_svc

log = logging.getLogger("library.seed")

BOOKS = [
    ("The Pragmatic Programmer", "Hunt & Thomas", "9780201616224", 2),
    ("Clean Code", "Robert C. Martin", "9780132350884", 1),
    ("Designing Data-Intensive Applications", "Martin Kleppmann", "9781449373320", 3),
]

MEMBERS = [
    ("Ada Lovelace", "ada@example.com", "555-0100"),
    ("Alan Turing", "alan@example.com", "555-0101"),
]


def run() -> None:
    """Insert sample books, copies, and members (safe to re-run).

    Uses the real service layer so validation and constraints apply. Catches
    ``AlreadyExists`` for idempotent startup seeding when data is already present.
    """
    for i, (title, author, isbn, n_copies) in enumerate(BOOKS):
        try:
            book = books_svc.create_book(title=title, author=author, isbn=isbn)
        except AlreadyExists:
            log.info("book already seeded: %s", title)
            continue
        for c in range(n_copies):
            try:
                books_svc.add_copy(
                    book_id=book.id,
                    barcode=f"BC-{book.id:04d}-{c+1:02d}",
                    condition=CopyCondition.GOOD,
                    shelf_location=f"A-{i+1}",
                )
            except AlreadyExists:
                pass

    for name, email, phone in MEMBERS:
        try:
            members_svc.create_member(name=name, email=email, phone=phone)
        except AlreadyExists:
            log.info("member already seeded: %s", email)

    log.info("seed complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
