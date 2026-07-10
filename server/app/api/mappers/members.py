from __future__ import annotations

import library_pb2 as pb

from app.core.enums import MemberStatus
from app.persistence.models import Member

_MEMBER_STATUS_TO_PB = {
    MemberStatus.ACTIVE: pb.MEMBER_STATUS_ACTIVE,
    MemberStatus.SUSPENDED: pb.MEMBER_STATUS_SUSPENDED,
}


def member_to_pb(member: Member) -> pb.Member:
    return pb.Member(
        id=member.id,
        name=member.name,
        email=member.email,
        phone=member.phone or "",
        status=_MEMBER_STATUS_TO_PB[member.status],
    )
