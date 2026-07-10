"""Tests for lending business logic."""
from __future__ import annotations

import pytest

from app.books import service as books_svc
from app.core.enums import MemberStatus
from app.core.errors import FailedPrecondition, NotFound
from app.lending import service as lending_svc
from app.members import service as members_svc
from tests.helpers import book_with_copies, member


def test_borrow_decrements_availability():
    book = book_with_copies(2)
    m = member()
    lending_svc.borrow_book(member_id=m.id, book_id=book.id, copy_id=None)
    _, total, available = books_svc.get_book_with_counts(book.id)
    assert (total, available) == (2, 1)


def test_borrow_soldout_book_fails():
    book = book_with_copies(1)
    m = member()
    lending_svc.borrow_book(member_id=m.id, book_id=book.id, copy_id=None)
    with pytest.raises(FailedPrecondition):
        lending_svc.borrow_book(member_id=m.id, book_id=book.id, copy_id=None)


def test_borrow_unknown_member_fails():
    book = book_with_copies(1)
    with pytest.raises(NotFound):
        lending_svc.borrow_book(member_id=999, book_id=book.id, copy_id=None)


def test_suspended_member_cannot_borrow():
    book = book_with_copies(1)
    m = member()
    members_svc.update_member(
        member_id=m.id,
        name=m.name,
        email=m.email,
        phone=None,
        status=MemberStatus.SUSPENDED,
    )
    with pytest.raises(FailedPrecondition):
        lending_svc.borrow_book(member_id=m.id, book_id=book.id, copy_id=None)


def test_return_makes_copy_available_again():
    book = book_with_copies(1)
    m = member()
    loan = lending_svc.borrow_book(member_id=m.id, book_id=book.id, copy_id=None)
    lending_svc.return_book(loan_id=loan.id, mark_damaged=False)
    _, _, available = books_svc.get_book_with_counts(book.id)
    assert available == 1


def test_double_return_fails():
    book = book_with_copies(1)
    m = member()
    loan = lending_svc.borrow_book(member_id=m.id, book_id=book.id, copy_id=None)
    lending_svc.return_book(loan_id=loan.id, mark_damaged=False)
    with pytest.raises(FailedPrecondition):
        lending_svc.return_book(loan_id=loan.id, mark_damaged=False)


def test_list_loans_filters_outstanding():
    book = book_with_copies(2)
    m = member()
    l1 = lending_svc.borrow_book(member_id=m.id, book_id=book.id, copy_id=None)
    lending_svc.borrow_book(member_id=m.id, book_id=book.id, copy_id=None)
    lending_svc.return_book(loan_id=l1.id, mark_damaged=False)

    outstanding = lending_svc.list_loans(
        member_id=m.id, status_filter="outstanding", limit=50, offset=0
    )
    returned = lending_svc.list_loans(
        member_id=m.id, status_filter="returned", limit=50, offset=0
    )
    assert len(outstanding) == 1
    assert len(returned) == 1
