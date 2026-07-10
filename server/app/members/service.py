"""Business logic for library members."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import IntegrityError

from app.core import validation as v
from app.core.enums import MemberStatus
from app.core.errors import AlreadyExists, NotFound
from app.members import repository as repo
from app.persistence.models import Member
from app.persistence.unit_of_work import unit_of_work


def create_member(*, name: str, email: str, phone: Optional[str]) -> Member:
    name = v.require_non_empty(name, "name")
    email = v.require_valid_email(email)
    phone = v.normalize_optional(phone)
    with unit_of_work() as s:
        try:
            member = repo.add_member(s, name=name, email=email, phone=phone)
            s.flush()
        except IntegrityError as e:
            raise AlreadyExists(f"a member with email '{email}' already exists") from e
        s.expunge(member)
        return member


def update_member(
    *, member_id: int, name: str, email: str, phone: Optional[str], status: Optional[MemberStatus]
) -> Member:
    name = v.require_non_empty(name, "name")
    email = v.require_valid_email(email)
    phone = v.normalize_optional(phone)
    with unit_of_work() as s:
        member = repo.get_member(s, member_id)
        if member is None:
            raise NotFound(f"member {member_id} not found")
        member.name, member.email, member.phone = name, email, phone
        if status is not None:
            member.status = status
        try:
            s.flush()
        except IntegrityError as e:
            raise AlreadyExists(f"a member with email '{email}' already exists") from e
        s.expunge(member)
        return member


def get_member(member_id: int) -> Member:
    with unit_of_work() as s:
        member = repo.get_member(s, member_id)
        if member is None:
            raise NotFound(f"member {member_id} not found")
        s.expunge(member)
        return member


def list_members(*, query: Optional[str], limit: int, offset: int) -> list[Member]:
    with unit_of_work() as s:
        members = list(repo.list_members(s, query=query, limit=limit, offset=offset))
        for m in members:
            s.expunge(m)
        return members
