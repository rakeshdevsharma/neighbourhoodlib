"""Simple offset-based pagination over an opaque page token.

The token is just the next offset encoded as a string. It is opaque to clients;
they pass back whatever ``next_page_token`` was returned.
"""
from __future__ import annotations

from .config import settings
from .errors import InvalidArgument


def resolve(page_size: int, page_token: str) -> tuple[int, int]:
    """Return (limit, offset) from a request's page_size/page_token."""
    if page_size < 0:
        raise InvalidArgument("page_size must be >= 0")
    limit = page_size or settings.default_page_size
    limit = min(limit, settings.max_page_size)

    offset = 0
    if page_token:
        try:
            offset = int(page_token)
        except ValueError as e:
            raise InvalidArgument("invalid page_token") from e
        if offset < 0:
            raise InvalidArgument("invalid page_token")
    return limit, offset


def next_token(offset: int, limit: int, returned: int) -> str:
    """Next token if a full page was returned, else empty (last page)."""
    if returned < limit:
        return ""
    return str(offset + limit)
