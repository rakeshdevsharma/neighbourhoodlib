"""Proto enum <-> domain enum translation."""
from __future__ import annotations

from typing import Optional

import library_pb2 as pb

from app.core.enums import CopyCondition, CopyStatus, MemberStatus
from app.core.errors import InvalidArgument

_COPY_STATUS_FROM_PB = {
    pb.COPY_STATUS_AVAILABLE: CopyStatus.AVAILABLE,
    pb.COPY_STATUS_ON_LOAN: CopyStatus.ON_LOAN,
    pb.COPY_STATUS_LOST: CopyStatus.LOST,
    pb.COPY_STATUS_DAMAGED: CopyStatus.DAMAGED,
    pb.COPY_STATUS_WITHDRAWN: CopyStatus.WITHDRAWN,
}

_COPY_CONDITION_FROM_PB = {
    pb.COPY_CONDITION_NEW: CopyCondition.NEW,
    pb.COPY_CONDITION_GOOD: CopyCondition.GOOD,
    pb.COPY_CONDITION_WORN: CopyCondition.WORN,
}

_MEMBER_STATUS_FROM_PB = {
    pb.MEMBER_STATUS_ACTIVE: MemberStatus.ACTIVE,
    pb.MEMBER_STATUS_SUSPENDED: MemberStatus.SUSPENDED,
}


def copy_status_from_pb(value: int, *, required: bool = False) -> Optional[CopyStatus]:
    """Map a protobuf ``CopyStatus`` enum to the domain enum.

    ``UNSPECIFIED`` means "not provided" unless ``required=True`` (update flows).
    Unknown values raise ``InvalidArgument``.
    """
    if value == pb.COPY_STATUS_UNSPECIFIED:
        if required:
            raise InvalidArgument("status must be specified")
        return None
    if value not in _COPY_STATUS_FROM_PB:
        raise InvalidArgument("unknown copy status")
    return _COPY_STATUS_FROM_PB[value]


def copy_condition_from_pb(value: int) -> Optional[CopyCondition]:
    """Map protobuf ``CopyCondition`` to domain; UNSPECIFIED → None."""
    if value == pb.COPY_CONDITION_UNSPECIFIED:
        return None
    if value not in _COPY_CONDITION_FROM_PB:
        raise InvalidArgument("unknown copy condition")
    return _COPY_CONDITION_FROM_PB[value]


def member_status_from_pb(value: int) -> Optional[MemberStatus]:
    """Map protobuf ``MemberStatus`` to domain; UNSPECIFIED → None (no change)."""
    if value == pb.MEMBER_STATUS_UNSPECIFIED:
        return None
    if value not in _MEMBER_STATUS_FROM_PB:
        raise InvalidArgument("unknown member status")
    return _MEMBER_STATUS_FROM_PB[value]


def loan_status_filter_from_pb(value: int) -> Optional[str]:
    """Map proto ``LoanStatus`` filter to repository query string (or None for all).

    The DB stores only timestamps; "overdue" is computed as open + past due_at.
    """
    return {
        pb.LOAN_STATUS_UNSPECIFIED: None,
        pb.LOAN_STATUS_OUTSTANDING: "outstanding",
        pb.LOAN_STATUS_RETURNED: "returned",
        pb.LOAN_STATUS_OVERDUE: "overdue",
    }.get(value, None)
