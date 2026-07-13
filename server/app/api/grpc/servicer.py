"""gRPC servicer: thin adapter translating proto <-> domain and errors <-> codes.

Each RPC method validates nothing itself — it maps request fields to service
calls, converts results via mappers, and applies pagination helpers. Business
rules and DB access live entirely in the service/repository layers.
"""
from __future__ import annotations

from datetime import datetime, timezone

import library_pb2 as pb
import library_pb2_grpc as pb_grpc

from app.api.grpc.error_handler import handle
from app.api.mappers import (
    book_to_pb,
    copy_condition_from_pb,
    copy_status_from_pb,
    copy_to_pb,
    loan_status_filter_from_pb,
    loan_to_pb,
    member_status_from_pb,
    member_to_pb,
)
from app.books import service as books_svc
from app.core import pagination
from app.lending import service as lending_svc
from app.members import service as members_svc


class LibraryServicer(pb_grpc.LibraryServiceServicer):
    """gRPC adapter for ``LibraryService`` defined in ``library.proto``.

    Each method is a thin translation layer: proto request fields → service call
    → domain result → proto response. The ``@handle`` decorator converts domain
    errors (``NotFound``, etc.) into gRPC status codes so this class never
    imports business rules directly.
    """

    # ---- Books ---------------------------------------------------------- #
    @handle
    def CreateBook(self, request, context):
        """RPC: register a new catalog title (title, author, optional ISBN).

        Delegates to ``books_svc.create_book``. Copy counts are zero on create;
        call ``GetBook`` after adding copies to see live availability.
        """
        book = books_svc.create_book(
            title=request.title, author=request.author, isbn=request.isbn
        )
        # Counts are zero on create; client can call GetBook for live totals.
        return book_to_pb(book, 0, 0)

    @handle
    def UpdateBook(self, request, context):
        """RPC: change bibliographic fields on an existing book.

        After update, re-fetches copy counts so the response reflects current
        shelf availability (``total_copies`` / ``available_copies``).
        """
        book = books_svc.update_book(
            book_id=request.id,
            title=request.title,
            author=request.author,
            isbn=request.isbn,
        )
        _, total, available = books_svc.get_book_with_counts(book.id)
        return book_to_pb(book, total, available)

    @handle
    def GetBook(self, request, context):
        """RPC: fetch one book by id, including live copy counts."""
        book, total, available = books_svc.get_book_with_counts(request.id)
        return book_to_pb(book, total, available)

    @handle
    def ListBooks(self, request, context):
        """RPC: paginated catalog search.

        ``page_size``/``page_token`` are resolved to SQL ``limit``/``offset`` via
        ``pagination.resolve``. An optional ``query`` filters by title/author.
        """
        limit, offset = pagination.resolve(request.page_size, request.page_token)
        rows = books_svc.list_books(query=request.query or None, limit=limit, offset=offset)
        return pb.ListBooksResponse(
            books=[book_to_pb(b, t, a) for (b, t, a) in rows],
            next_page_token=pagination.next_token(offset, limit, len(rows)),
        )

    # ---- Copies --------------------------------------------------------- #
    @handle
    def AddCopy(self, request, context):
        """RPC: add a physical copy of an existing book.

        Proto enums (condition) are converted to domain enums before the service
        layer inserts a row with status AVAILABLE.
        """
        copy = books_svc.add_copy(
            book_id=request.book_id,
            barcode=request.barcode,
            condition=copy_condition_from_pb(request.condition),
            shelf_location=request.shelf_location,
        )
        return copy_to_pb(copy)

    @handle
    def UpdateCopy(self, request, context):
        """RPC: change a copy's circulation status, condition, or shelf location.

        Only non-default proto enum values are applied (UNSPECIFIED means "leave
        unchanged"). Status changes are blocked while an open loan exists.
        """
        copy = books_svc.update_copy(
            copy_id=request.id,
            status=copy_status_from_pb(request.status),
            condition=copy_condition_from_pb(request.condition),
            shelf_location=request.shelf_location or None,
        )
        return copy_to_pb(copy)

    @handle
    def ListCopies(self, request, context):
        """RPC: list physical copies, optionally filtered to one ``book_id``."""
        limit, offset = pagination.resolve(request.page_size, request.page_token)
        copies = books_svc.list_copies(
            book_id=request.book_id or None, limit=limit, offset=offset
        )
        return pb.ListCopiesResponse(
            copies=[copy_to_pb(c) for c in copies],
            next_page_token=pagination.next_token(offset, limit, len(copies)),
        )

    # ---- Members -------------------------------------------------------- #
    @handle
    def CreateMember(self, request, context):
        """RPC: register a new library patron (name, email, optional phone)."""
        member = members_svc.create_member(
            name=request.name, email=request.email, phone=request.phone
        )
        return member_to_pb(member)

    @handle
    def UpdateMember(self, request, context):
        """RPC: update member profile and optionally suspend borrowing.

        Setting status to SUSPENDED blocks future borrows without deleting loan
        history.
        """
        member = members_svc.update_member(
            member_id=request.id,
            name=request.name,
            email=request.email,
            phone=request.phone,
            status=member_status_from_pb(request.status),
        )
        return member_to_pb(member)

    @handle
    def GetMember(self, request, context):
        """RPC: fetch a single member by id."""
        return member_to_pb(members_svc.get_member(request.id))

    @handle
    def ListMembers(self, request, context):
        """RPC: paginated member search by name or email substring."""
        limit, offset = pagination.resolve(request.page_size, request.page_token)
        members = members_svc.list_members(
            query=request.query or None, limit=limit, offset=offset
        )
        return pb.ListMembersResponse(
            members=[member_to_pb(m) for m in members],
            next_page_token=pagination.next_token(offset, limit, len(members)),
        )

    # ---- Lending -------------------------------------------------------- #
    @handle
    def BorrowBook(self, request, context):
        """RPC: check out a book to a member.

        The request uses a proto ``oneof``: lend by ``book_id`` (any available
        copy, SKIP LOCKED) or by specific ``copy_id``. Exactly one must be set.
        """
        target = request.WhichOneof("target")
        loan = lending_svc.borrow_book(
            member_id=request.member_id,
            book_id=request.book_id if target == "book_id" else None,
            copy_id=request.copy_id if target == "copy_id" else None,
        )
        return loan_to_pb(loan)

    @handle
    def ReturnBook(self, request, context):
        """RPC: close an open loan and return the copy to the shelf.

        ``mark_damaged`` sets the copy to DAMAGED/WORN instead of AVAILABLE.
        Late fines are computed and stored on the loan row.
        """
        loan = lending_svc.return_book(loan_id=request.loan_id, mark_damaged=request.mark_damaged)
        return loan_to_pb(loan)

    @handle
    def ListLoans(self, request, context):
        """RPC: paginated loan history with optional member/status filters.

        Loan status (outstanding/overdue/returned) is derived at mapping time
        from ``returned_at`` and ``due_at`` — not stored as a DB column.
        """
        limit, offset = pagination.resolve(request.page_size, request.page_token)
        now = datetime.now(timezone.utc)  # drives overdue vs outstanding in mapper
        loans = lending_svc.list_loans(
            member_id=request.member_id or None,
            status_filter=loan_status_filter_from_pb(request.status),
            limit=limit,
            offset=offset,
        )
        return pb.ListLoansResponse(
            loans=[loan_to_pb(ln, now) for ln in loans],
            next_page_token=pagination.next_token(offset, limit, len(loans)),
        )
