"""Tests for member business logic."""
from __future__ import annotations

import pytest

from app.core.errors import AlreadyExists, InvalidArgument
from app.members import service as members_svc
from tests.helpers import member


def test_member_email_validation():
    with pytest.raises(InvalidArgument):
        members_svc.create_member(name="X", email="not-an-email", phone=None)


def test_duplicate_email_rejected():
    # Email uniqueness is enforced by DB index; service maps to AlreadyExists.
    member("dup@example.com")
    with pytest.raises(AlreadyExists):
        member("dup@example.com")
