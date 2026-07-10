from __future__ import annotations

import library_pb2 as pb

from app.core.enums import CopyCondition, CopyStatus
from app.persistence.models import BookCopy

_COPY_STATUS_TO_PB = {
    CopyStatus.AVAILABLE: pb.COPY_STATUS_AVAILABLE,
    CopyStatus.ON_LOAN: pb.COPY_STATUS_ON_LOAN,
    CopyStatus.LOST: pb.COPY_STATUS_LOST,
    CopyStatus.DAMAGED: pb.COPY_STATUS_DAMAGED,
    CopyStatus.WITHDRAWN: pb.COPY_STATUS_WITHDRAWN,
}

_COPY_CONDITION_TO_PB = {
    CopyCondition.NEW: pb.COPY_CONDITION_NEW,
    CopyCondition.GOOD: pb.COPY_CONDITION_GOOD,
    CopyCondition.WORN: pb.COPY_CONDITION_WORN,
}


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
