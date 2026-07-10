from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import library_pb2 as pb

from app.persistence.models import Loan


def _set_ts(field, value: Optional[datetime]) -> None:
    if value is not None:
        field.FromDatetime(value)


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
