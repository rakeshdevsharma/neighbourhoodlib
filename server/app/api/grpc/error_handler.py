"""Map domain errors to gRPC status codes.

The ``@handle`` decorator wraps every RPC method so services can raise plain
``DomainError`` subclasses without importing grpc. Unexpected exceptions become
INTERNAL after logging the stack trace.
"""
from __future__ import annotations

import logging

import grpc

from app.core.errors import AlreadyExists, FailedPrecondition, InvalidArgument, NotFound

log = logging.getLogger("library.servicer")

_ERROR_CODES = {
    NotFound: grpc.StatusCode.NOT_FOUND,
    InvalidArgument: grpc.StatusCode.INVALID_ARGUMENT,
    FailedPrecondition: grpc.StatusCode.FAILED_PRECONDITION,
    AlreadyExists: grpc.StatusCode.ALREADY_EXISTS,
}


def abort(context: grpc.ServicerContext, exc: Exception) -> None:
    for exc_type, code in _ERROR_CODES.items():
        if isinstance(exc, exc_type):
            context.abort(code, str(exc))
            return
    log.exception("unhandled error")
    context.abort(grpc.StatusCode.INTERNAL, "internal error")


def handle(fn):
    """Decorator mapping domain errors to gRPC status codes."""

    def wrapper(self, request, context):
        try:
            return fn(self, request, context)
        except grpc.RpcError:
            raise  # already a gRPC error; do not wrap
        except Exception as exc:  # noqa: BLE001 - deliberate boundary catch
            abort(context, exc)

    return wrapper
