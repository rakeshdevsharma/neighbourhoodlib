"""Domain exceptions.

Raised by the service layer and translated to gRPC status codes at the servicer
boundary, keeping business logic free of any gRPC dependency.
"""
from __future__ import annotations


class DomainError(Exception):
    """Base class for expected, client-facing errors."""


class NotFound(DomainError):
    """A referenced entity does not exist."""


class InvalidArgument(DomainError):
    """Input failed validation."""


class FailedPrecondition(DomainError):
    """The operation is not allowed in the current state (e.g. no copies free)."""


class AlreadyExists(DomainError):
    """A uniqueness constraint would be violated (e.g. duplicate barcode/email)."""
