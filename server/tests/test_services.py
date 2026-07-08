"""Service-layer tests covering the core flows and key edge cases."""
from __future__ import annotations

import pytest

from app import services as svc
from app.enums import CopyCondition, MemberStatus
from app.errors import AlreadyExists, FailedPrecondition, InvalidArgument, NotFound


def _book_with_copies(n: int = 1):
    book = svc.create_book(title="Test Book", author="Author", isbn=None)
    for i in range(n):
        svc.add_copy(
            book_id=book.id,
            barcode=f"BC-{book.id}-{i}",
            condition=CopyCondition.GOOD,
            shelf_location="A-1",
        )
    return book


def _member(email="m@example.com"):
    return svc.create_member(name="Member", email=email, phone=None)


# --- books / validation -------------------------------------------------- #
def test_create_book_requires_title():
    with pytest.raises(InvalidArgument):
        svc.create_book(title="  ", author="A", isbn=None)


def test_duplicate_isbn_rejected():
    svc.create_book(title="A", author="X", isbn="9780201616224")
    with pytest.raises(AlreadyExists):
        svc.create_book(title="B", author="Y", isbn="9780201616224")


def test_invalid_isbn_rejected():
    with pytest.raises(InvalidArgument):
        svc.create_book(title="A", author="X", isbn="123")


def test_book_counts_reflect_copies():
    book = _book_with_copies(3)
    _, total, available = svc.get_book_with_counts(book.id)
    assert (total, available) == (3, 3)


# --- members ------------------------------------------------------------- #
def test_member_email_validation():
    with pytest.raises(InvalidArgument):
        svc.create_member(name="X", email="not-an-email", phone=None)


def test_duplicate_email_rejected():
    _member("dup@example.com")
    with pytest.raises(AlreadyExists):
        _member("dup@example.com")


# --- borrow / return ----------------------------------------------------- #
def test_borrow_decrements_availability():
    book = _book_with_copies(2)
    member = _member()
    svc.borrow_book(member_id=member.id, book_id=book.id, copy_id=None)
    _, total, available = svc.get_book_with_counts(book.id)
    assert (total, available) == (2, 1)


def test_borrow_soldout_book_fails():
    book = _book_with_copies(1)
    member = _member()
    svc.borrow_book(member_id=member.id, book_id=book.id, copy_id=None)
    with pytest.raises(FailedPrecondition):
        svc.borrow_book(member_id=member.id, book_id=book.id, copy_id=None)


def test_borrow_unknown_member_fails():
    book = _book_with_copies(1)
    with pytest.raises(NotFound):
        svc.borrow_book(member_id=999, book_id=book.id, copy_id=None)


def test_suspended_member_cannot_borrow():
    book = _book_with_copies(1)
    member = _member()
    svc.update_member(
        member_id=member.id,
        name=member.name,
        email=member.email,
        phone=None,
        status=MemberStatus.SUSPENDED,
    )
    with pytest.raises(FailedPrecondition):
        svc.borrow_book(member_id=member.id, book_id=book.id, copy_id=None)


def test_return_makes_copy_available_again():
    book = _book_with_copies(1)
    member = _member()
    loan = svc.borrow_book(member_id=member.id, book_id=book.id, copy_id=None)
    svc.return_book(loan_id=loan.id, mark_damaged=False)
    _, _, available = svc.get_book_with_counts(book.id)
    assert available == 1


def test_double_return_fails():
    book = _book_with_copies(1)
    member = _member()
    loan = svc.borrow_book(member_id=member.id, book_id=book.id, copy_id=None)
    svc.return_book(loan_id=loan.id, mark_damaged=False)
    with pytest.raises(FailedPrecondition):
        svc.return_book(loan_id=loan.id, mark_damaged=False)


def test_list_loans_filters_outstanding():
    book = _book_with_copies(2)
    member = _member()
    l1 = svc.borrow_book(member_id=member.id, book_id=book.id, copy_id=None)
    svc.borrow_book(member_id=member.id, book_id=book.id, copy_id=None)
    svc.return_book(loan_id=l1.id, mark_damaged=False)

    outstanding = svc.list_loans(
        member_id=member.id, status_filter="outstanding", limit=50, offset=0
    )
    returned = svc.list_loans(
        member_id=member.id, status_filter="returned", limit=50, offset=0
    )
    assert len(outstanding) == 1
    assert len(returned) == 1
