"""Sample gRPC client exercising the core library flows end-to-end.

Run against a running server (default localhost:50051):

    # generate stubs first (once):
    cd server && bash scripts/gen_proto.sh
    # then, with server/gen on the path:
    PYTHONPATH=server/gen python examples/client.py
"""
from __future__ import annotations

import os
import sys
import time

import grpc

import library_pb2 as pb
import library_pb2_grpc as pb_grpc

ADDR = os.environ.get("GRPC_ADDR", "localhost:50051")


def main() -> None:
    channel = grpc.insecure_channel(ADDR)
    stub = pb_grpc.LibraryServiceStub(channel)

    unique = str(int(time.time()))

    # 1. Create a book.
    book = stub.CreateBook(
        pb.CreateBookRequest(
            title="The Go Programming Language",
            author="Donovan & Kernighan",
            isbn=None,
        )
    )
    print(f"created book #{book.id}: {book.title}")

    # 2. Add two physical copies.
    for i in range(2):
        copy = stub.AddCopy(
            pb.AddCopyRequest(
                book_id=book.id,
                barcode=f"DEMO-{unique}-{i}",
                condition=pb.COPY_CONDITION_GOOD,
                shelf_location="DEMO-1",
            )
        )
        print(f"  added copy #{copy.id} barcode={copy.barcode}")

    # 3. Create a member.
    member = stub.CreateMember(
        pb.CreateMemberRequest(
            name="Grace Hopper", email=f"grace{unique}@example.com", phone="555-0102"
        )
    )
    print(f"created member #{member.id}: {member.name}")

    # 4. Borrow any available copy of the book.
    loan = stub.BorrowBook(pb.BorrowBookRequest(member_id=member.id, book_id=book.id))
    print(f"borrowed: loan #{loan.id} copy #{loan.copy_id} due {loan.due_at.ToDatetime()}")

    # 5. Show the book's availability dropped by one.
    refreshed = stub.GetBook(pb.GetBookRequest(id=book.id))
    print(f"availability: {refreshed.available_copies}/{refreshed.total_copies}")

    # 6. List this member's outstanding loans.
    loans = stub.ListLoans(
        pb.ListLoansRequest(member_id=member.id, status=pb.LOAN_STATUS_OUTSTANDING)
    )
    print(f"member has {len(loans.loans)} outstanding loan(s):")
    for ln in loans.loans:
        print(f"  loan #{ln.id}: '{ln.book_title}' (barcode {ln.barcode})")

    # 7. Error handling demo: borrowing the last copy then one too many.
    stub.BorrowBook(pb.BorrowBookRequest(member_id=member.id, book_id=book.id))
    try:
        stub.BorrowBook(pb.BorrowBookRequest(member_id=member.id, book_id=book.id))
    except grpc.RpcError as e:
        print(f"expected failure borrowing sold-out book: {e.code().name}: {e.details()}")

    # 8. Return the first loan.
    returned = stub.ReturnBook(pb.ReturnBookRequest(loan_id=loan.id))
    print(f"returned loan #{returned.id}; fine={returned.fine_cents} cents")

    print("done.")


if __name__ == "__main__":
    sys.exit(main())
