"""Business logic for library members.

Members are identified by unique email. Only ACTIVE members may borrow; status
can be set to SUSPENDED via update to block circulation without deleting history.
"""
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
    """Register a new library patron.

    Validates name/email, inserts a row with default status ACTIVE, and returns
    a detached ORM object. Email uniqueness is enforced by the database; a duplicate
    triggers ``IntegrityError`` which we convert to ``AlreadyExists``.

    Raises:
        InvalidArgument: name empty or email malformed.
        AlreadyExists: email already registered.
    """
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
    """Update a member's profile and optionally change borrowing eligibility.

    Setting ``status`` to SUSPENDED blocks future borrows (checked in lending
    service) without deleting loan history. Pass ``status=None`` to leave unchanged.

    Raises:
        NotFound: member does not exist.
        AlreadyExists: new email belongs to another member.
    """
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
    """Fetch a single member by primary key.

    Raises:
        NotFound: no row with that id.
    """
    with unit_of_work() as s:
        member = repo.get_member(s, member_id)
        if member is None:
            raise NotFound(f"member {member_id} not found")
        s.expunge(member)
        return member


def list_members(*, query: Optional[str], limit: int, offset: int) -> list[Member]:
    """Return a paginated list of members, optionally filtered by name/email.

    Same pagination pattern as ``list_books``; entities are expunged so they
    survive after the SQLAlchemy session closes.
    """
    with unit_of_work() as s:
        members = list(repo.list_members(s, query=query, limit=limit, offset=offset))
        for m in members:
            s.expunge(m)
        return members
