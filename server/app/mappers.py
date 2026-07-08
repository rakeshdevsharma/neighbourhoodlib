"""Translation between domain/ORM objects and generated protobuf messages.

Isolates every reference to the generated ``library_pb2`` module so the rest of
the app stays proto-free.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import library_pb2 as pb

from .enums import CopyCondition, CopyStatus, MemberStatus
from .errors import InvalidArgument
from .models import Book, BookCopy, Loan, Member

# --------------------------------------------------------------------------- #
# Enum maps
# --------------------------------------------------------------------------- #
_COPY_STATUS_TO_PB = {
    CopyStatus.AVAILABLE: pb.COPY_STATUS_AVAILABLE,
    CopyStatus.ON_LOAN: pb.COPY_STATUS_ON_LOAN,
    CopyStatus.LOST: pb.COPY_STATUS_LOST,
    CopyStatus.DAMAGED: pb.COPY_STATUS_DAMAGED,
    CopyStatus.WITHDRAWN: pb.COPY_STATUS_WITHDRAWN,
}
_COPY_STATUS_FROM_PB = {v: k for k, v in _COPY_STATUS_TO_PB.items()}

_COPY_CONDITION_TO_PB = {
    CopyCondition.NEW: pb.COPY_CONDITION_NEW,
    CopyCondition.GOOD: pb.COPY_CONDITION_GOOD,
    CopyCondition.WORN: pb.COPY_CONDITION_WORN,
}
_COPY_CONDITION_FROM_PB = {v: k for k, v in _COPY_CONDITION_TO_PB.items()}

_MEMBER_STATUS_TO_PB = {
    MemberStatus.ACTIVE: pb.MEMBER_STATUS_ACTIVE,
    MemberStatus.SUSPENDED: pb.MEMBER_STATUS_SUSPENDED,
}
_MEMBER_STATUS_FROM_PB = {v: k for k, v in _MEMBER_STATUS_TO_PB.items()}


# --------------------------------------------------------------------------- #
# Enum: proto -> domain (with validation)
# --------------------------------------------------------------------------- #
def copy_status_from_pb(value: int, *, required: bool = False) -> Optional[CopyStatus]:
    if value == pb.COPY_STATUS_UNSPECIFIED:
        if required:
            raise InvalidArgument("status must be specified")
        return None
    if value not in _COPY_STATUS_FROM_PB:
        raise InvalidArgument("unknown copy status")
    return _COPY_STATUS_FROM_PB[value]


def copy_condition_from_pb(value: int) -> Optional[CopyCondition]:
    if value == pb.COPY_CONDITION_UNSPECIFIED:
        return None
    if value not in _COPY_CONDITION_FROM_PB:
        raise InvalidArgument("unknown copy condition")
    return _COPY_CONDITION_FROM_PB[value]


def member_status_from_pb(value: int) -> Optional[MemberStatus]:
    if value == pb.MEMBER_STATUS_UNSPECIFIED:
        return None
    if value not in _MEMBER_STATUS_FROM_PB:
        raise InvalidArgument("unknown member status")
    return _MEMBER_STATUS_FROM_PB[value]


def loan_status_filter_from_pb(value: int) -> Optional[str]:
    return {
        pb.LOAN_STATUS_UNSPECIFIED: None,
        pb.LOAN_STATUS_OUTSTANDING: "outstanding",
        pb.LOAN_STATUS_RETURNED: "returned",
        pb.LOAN_STATUS_OVERDUE: "overdue",
    }.get(value, None)


# --------------------------------------------------------------------------- #
# Domain -> proto
# --------------------------------------------------------------------------- #
def _set_ts(field, value: Optional[datetime]) -> None:
    if value is not None:
        field.FromDatetime(value)


def book_to_pb(book: Book, total: int, available: int) -> pb.Book:
    return pb.Book(
        id=book.id,
        title=book.title,
        author=book.author,
        isbn=book.isbn or "",
        total_copies=total,
        available_copies=available,
    )


def copy_to_pb(copy: BookCopy) -> pb.BookCopy:
    return pb.BookCopy(
        id=copy.id,
        book_id=copy.book_id,
        barcode=copy.barcode,
        status=_COPY_STATUS_TO_PB[copy.status],
        condition=(
            _COPY_CONDITION_TO_PB[copy.condition]
            if copy.condition is not None
            else pb.COPY_CONDITION_UNSPECIFIED
        ),
        shelf_location=copy.shelf_location or "",
    )


def member_to_pb(member: Member) -> pb.Member:
    return pb.Member(
        id=member.id,
        name=member.name,
        email=member.email,
        phone=member.phone or "",
        status=_MEMBER_STATUS_TO_PB[member.status],
    )


def _loan_status_pb(loan: Loan, now: datetime) -> int:
    if loan.returned_at is not None:
        return pb.LOAN_STATUS_RETURNED
    if loan.due_at < now:
        return pb.LOAN_STATUS_OVERDUE
    return pb.LOAN_STATUS_OUTSTANDING


def loan_to_pb(loan: Loan, now: Optional[datetime] = None) -> pb.Loan:
    now = now or datetime.now(timezone.utc)
    msg = pb.Loan(
        id=loan.id,
        copy_id=loan.copy_id,
        member_id=loan.member_id,
        fine_cents=loan.fine_cents,
        book_id=loan.copy.book_id,
        book_title=loan.copy.book.title,
        member_name=loan.member.name,
        barcode=loan.copy.barcode,
        status=_loan_status_pb(loan, now),
    )
    _set_ts(msg.borrowed_at, loan.borrowed_at)
    _set_ts(msg.due_at, loan.due_at)
    _set_ts(msg.returned_at, loan.returned_at)
    return msg
