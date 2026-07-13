"""Simple offset-based pagination over an opaque page token.

The token is just the next offset encoded as a string. It is opaque to clients;
they pass back whatever ``next_page_token`` was returned.
"""
from __future__ import annotations

from app.core.config import settings
from app.core.errors import InvalidArgument


def resolve(page_size: int, page_token: str) -> tuple[int, int]:
    """Convert gRPC pagination fields to SQL ``(limit, offset)``.

    ``page_size`` of 0 uses ``settings.default_page_size``; values above
    ``max_page_size`` are capped. ``page_token`` is the stringified offset from
    a previous ``next_page_token`` (opaque to clients).
    """
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
    """Compute the token for the next page, or "" if this was the last page.

    A full page (``returned == limit``) implies more rows may exist; an empty
    token tells clients to stop paginating.
    """
    if returned < limit:
        return ""
    return str(offset + limit)
