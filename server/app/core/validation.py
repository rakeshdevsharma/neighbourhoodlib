"""Input validation helpers, raising InvalidArgument on failure.

Validation runs in the service layer before any database write so clients receive
a consistent INVALID_ARGUMENT gRPC status for bad input.
"""
from __future__ import annotations

import re

from app.core.errors import InvalidArgument

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def require_non_empty(value: str, field: str) -> str:
    """Reject blank or whitespace-only strings; return trimmed value.

    Raises ``InvalidArgument`` so the servicer maps it to gRPC INVALID_ARGUMENT.
    """
    if value is None or value.strip() == "":
        raise InvalidArgument(f"{field} is required")
    return value.strip()


def require_valid_email(value: str, field: str = "email") -> str:
    """Validate a basic email shape (local@domain.tld) after trimming."""
    value = require_non_empty(value, field)
    if not _EMAIL_RE.match(value):
        raise InvalidArgument(f"{field} is not a valid email address")
    return value


def normalize_optional(value: str | None) -> str | None:
    """Treat protobuf's empty-string default as absent."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def validate_isbn(value: str | None) -> str | None:
    """Light ISBN check: accept ISBN-10/13 ignoring separators, or None."""
    value = normalize_optional(value)
    if value is None:
        return None
    digits = value.replace("-", "").replace(" ", "")
    # Last char may be 'X' on ISBN-10; we only validate length and digit body.
    if len(digits) not in (10, 13) or not digits[:-1].isdigit():
        raise InvalidArgument("isbn must be a 10- or 13-digit ISBN")
    return value
