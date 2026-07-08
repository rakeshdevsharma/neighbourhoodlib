"""gRPC servicer: thin adapter translating proto <-> domain and errors <-> codes.

Business rules live in ``services.py``; this layer only marshals.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import grpc
import library_pb2 as pb
import library_pb2_grpc as pb_grpc

from . import mappers, pagination
from . import services as svc
from .errors import AlreadyExists, FailedPrecondition, InvalidArgument, NotFound

log = logging.getLogger("library.servicer")

_ERROR_CODES = {
    NotFound: grpc.StatusCode.NOT_FOUND,
    InvalidArgument: grpc.StatusCode.INVALID_ARGUMENT,
    FailedPrecondition: grpc.StatusCode.FAILED_PRECONDITION,
    AlreadyExists: grpc.StatusCode.ALREADY_EXISTS,
}


def _abort(context: grpc.ServicerContext, exc: Exception) -> None:
    for exc_type, code in _ERROR_CODES.items():
        if isinstance(exc, exc_type):
            context.abort(code, str(exc))
            return
    log.exception("unhandled error")
    context.abort(grpc.StatusCode.INTERNAL, "internal error")


def _handle(fn):
    """Decorator mapping domain errors to gRPC status codes."""

    def wrapper(self, request, context):
        try:
            return fn(self, request, context)
        except grpc.RpcError:
            raise
        except Exception as exc:  # noqa: BLE001 - deliberate boundary catch
            _abort(context, exc)

    return wrapper


class LibraryServicer(pb_grpc.LibraryServiceServicer):
    # ---- Books ---------------------------------------------------------- #
    @_handle
    def CreateBook(self, request, context):
        book = svc.create_book(
            title=request.title, author=request.author, isbn=request.isbn
        )
        return mappers.book_to_pb(book, 0, 0)

    @_handle
    def UpdateBook(self, request, context):
        book = svc.update_book(
            book_id=request.id,
            title=request.title,
            author=request.author,
            isbn=request.isbn,
        )
        _, total, available = svc.get_book_with_counts(book.id)
        return mappers.book_to_pb(book, total, available)

    @_handle
    def GetBook(self, request, context):
        book, total, available = svc.get_book_with_counts(request.id)
        return mappers.book_to_pb(book, total, available)

    @_handle
    def ListBooks(self, request, context):
        limit, offset = pagination.resolve(request.page_size, request.page_token)
        rows = svc.list_books(query=request.query or None, limit=limit, offset=offset)
        return pb.ListBooksResponse(
            books=[mappers.book_to_pb(b, t, a) for (b, t, a) in rows],
            next_page_token=pagination.next_token(offset, limit, len(rows)),
        )

    # ---- Copies --------------------------------------------------------- #
    @_handle
    def AddCopy(self, request, context):
        copy = svc.add_copy(
            book_id=request.book_id,
            barcode=request.barcode,
            condition=mappers.copy_condition_from_pb(request.condition),
            shelf_location=request.shelf_location,
        )
        return mappers.copy_to_pb(copy)

    @_handle
    def UpdateCopy(self, request, context):
        copy = svc.update_copy(
            copy_id=request.id,
            status=mappers.copy_status_from_pb(request.status),
            condition=mappers.copy_condition_from_pb(request.condition),
            shelf_location=request.shelf_location or None,
        )
        return mappers.copy_to_pb(copy)

    @_handle
    def ListCopies(self, request, context):
        limit, offset = pagination.resolve(request.page_size, request.page_token)
        copies = svc.list_copies(
            book_id=request.book_id or None, limit=limit, offset=offset
        )
        return pb.ListCopiesResponse(
            copies=[mappers.copy_to_pb(c) for c in copies],
            next_page_token=pagination.next_token(offset, limit, len(copies)),
        )

    # ---- Members -------------------------------------------------------- #
    @_handle
    def CreateMember(self, request, context):
        member = svc.create_member(
            name=request.name, email=request.email, phone=request.phone
        )
        return mappers.member_to_pb(member)

    @_handle
    def UpdateMember(self, request, context):
        member = svc.update_member(
            member_id=request.id,
            name=request.name,
            email=request.email,
            phone=request.phone,
            status=mappers.member_status_from_pb(request.status),
        )
        return mappers.member_to_pb(member)

    @_handle
    def GetMember(self, request, context):
        return mappers.member_to_pb(svc.get_member(request.id))

    @_handle
    def ListMembers(self, request, context):
        limit, offset = pagination.resolve(request.page_size, request.page_token)
        members = svc.list_members(
            query=request.query or None, limit=limit, offset=offset
        )
        return pb.ListMembersResponse(
            members=[mappers.member_to_pb(m) for m in members],
            next_page_token=pagination.next_token(offset, limit, len(members)),
        )

    # ---- Lending -------------------------------------------------------- #
    @_handle
    def BorrowBook(self, request, context):
        target = request.WhichOneof("target")
        loan = svc.borrow_book(
            member_id=request.member_id,
            book_id=request.book_id if target == "book_id" else None,
            copy_id=request.copy_id if target == "copy_id" else None,
        )
        return mappers.loan_to_pb(loan)

    @_handle
    def ReturnBook(self, request, context):
        loan = svc.return_book(loan_id=request.loan_id, mark_damaged=request.mark_damaged)
        return mappers.loan_to_pb(loan)

    @_handle
    def ListLoans(self, request, context):
        limit, offset = pagination.resolve(request.page_size, request.page_token)
        now = datetime.now(timezone.utc)
        loans = svc.list_loans(
            member_id=request.member_id or None,
            status_filter=mappers.loan_status_filter_from_pb(request.status),
            limit=limit,
            offset=offset,
        )
        return pb.ListLoansResponse(
            loans=[mappers.loan_to_pb(ln, now) for ln in loans],
            next_page_token=pagination.next_token(offset, limit, len(loans)),
        )
