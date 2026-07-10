"""Data-access layer for library members."""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.persistence.models import Member


def add_member(
    session: Session, *, name: str, email: str, phone: Optional[str]
) -> Member:
    member = Member(name=name, email=email, phone=phone)
    session.add(member)
    session.flush()
    return member


def get_member(session: Session, member_id: int) -> Optional[Member]:
    return session.get(Member, member_id)


def list_members(
    session: Session, *, query: Optional[str], limit: int, offset: int
) -> Sequence[Member]:
    stmt = select(Member)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(or_(Member.name.ilike(like), Member.email.ilike(like)))
    stmt = stmt.order_by(Member.id).limit(limit).offset(offset)
    return session.scalars(stmt).all()
