# Neighborhood Library Service — High Level Design

**Status:** Draft · **Date:** 2026-07-10 · **Owner:** Rakesh Sharma

---

## 1. Overview

A small neighborhood library needs a service to manage **books**, **members**, and
**lending operations** (borrow / return). This document describes the high-level
architecture, data model, service interface, and key design decisions for that
system.

### 1.1 Goals

- CRUD for books and members.
- Record borrow and return events with full history.
- Query outstanding loans (e.g. all books a member currently has out).
- Enforce lending rules (a copy can't be borrowed twice at once).
- Provide a minimal web frontend for library staff.

### 1.2 Non-Goals (for this iteration)

- Authentication / role-based access control (single trusted-staff assumption).
- Multi-branch / multi-tenant support.
- Reservations / holds queue, notifications, e-mail reminders.
- Payment processing for fines (fines are *tracked*, not *collected*).

### 1.3 Core Design Decisions

| Concern | Decision | Rationale |
|---|---|---|
| Server language | **Python 3.11+** | Required by spec; rich ecosystem. |
| Service interface | **gRPC** with Protocol Buffers, exposed to the browser via **gRPC-Web** (Envoy proxy) | Spec prefers gRPC-Web; strong typing, code-gen for clients. REST fallback documented in §6.4. |
| Data store | **PostgreSQL 15+** | Required by spec; relational integrity fits the domain. |
| DB access | **SQLAlchemy 2.0** (Core/ORM) + **Alembic** migrations | Mature, migration tooling, avoids hand-rolled SQL sprawl. |
| Frontend | **Next.js (React, TypeScript)** | Required by spec. |
| Packaging | **Docker Compose** (db + server + proxy + web) | One-command local setup. |
| Code layout | **Feature modules** + shared `api/`, `persistence/`, `core/` | Clear boundaries; scales without monolithic service/repo files. |

---

## 2. System Architecture

```
┌──────────────┐      gRPC-Web        ┌─────────────┐     gRPC      ┌──────────────┐
│  Next.js UI  │ ───────────────────► │   Envoy     │ ────────────► │  Python gRPC │
│  (browser)   │ ◄─────────────────── │  (grpc-web  │ ◄──────────── │    server    │
└──────────────┘   HTTP/1.1 + JSON    │   filter)   │   HTTP/2      └──────┬───────┘
                                       └─────────────┘                     │
                                                                           │ SQLAlchemy
                                                                           ▼
                                                                    ┌──────────────┐
                                                                    │  PostgreSQL  │
                                                                    └──────────────┘
```

**Components**

1. **Next.js frontend** — staff-facing UI. Calls the backend over gRPC-Web using
   generated TypeScript stubs.
2. **Envoy proxy** — translates browser gRPC-Web (HTTP/1.1) to native gRPC (HTTP/2).
   Browsers cannot speak raw gRPC, so this hop is required for the gRPC path.
3. **Python gRPC server** — implements the `LibraryService` via a thin gRPC adapter
   (`api/grpc/`) that delegates to feature services (`books`, `members`, `lending`).
   It is the only component that talks to the database.
4. **PostgreSQL** — durable store for all entities.

The server is stateless; all state lives in Postgres, so it can be scaled
horizontally behind a load balancer if needed.

---

## 3. Data Model

The service uses a **per-copy model**: `books` holds the bibliographic record (the
title/edition), and each physical item on the shelf is a row in `book_copies`.
Loans reference a *copy*, not a *book*. This mirrors how a real integrated library
system (ILS) works and lets the database itself enforce the "no double-borrow"
invariant. (A simpler copies-count alternative is noted in §8.)

### 3.1 Entity-Relationship Diagram

```
   books                      book_copies                    loans
 ┌──────────┐               ┌──────────────┐            ┌────────────────┐
 │ id (PK)  │◄──── 1:N ──────┤ id (PK)      │◄─── 1:N ────┤ id (PK)        │
 │ title    │               │ book_id (FK) │            │ copy_id  (FK) ─┼──► book_copies.id
 │ author   │               │ barcode      │            │ member_id(FK) ─┼──► members.id
 │ isbn     │               │ status       │            │ borrowed_at    │
 │ ...      │               │ condition    │            │ due_at         │
 └──────────┘               │ shelf_loc    │            │ returned_at    │
                            │ acquired_at  │            │ fine_cents     │
   members                  └──────────────┘            └───────┬────────┘
 ┌──────────┐                                                   │ N
 │ id (PK)  │◄────────────────────── 1:N ───────────────────────┘
 │ name     │        one member has many loans;
 │ email    │        one book has many copies; one copy has many (historical) loans
 │ phone    │
 │ status   │
 └──────────┘
```

### 3.2 Tables

**`books`** — bibliographic record (one row per title/edition)

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `title` | `TEXT NOT NULL` | |
| `author` | `TEXT NOT NULL` | |
| `isbn` | `TEXT UNIQUE` | nullable; validated if present |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

Availability counts are *derived* from `book_copies`, not stored here:
`COUNT(*)` = total, `COUNT(*) FILTER (WHERE status = 'available')` = available.

**`book_copies`** — physical item (one row per copy on the shelf)

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `book_id` | `BIGINT FK → books.id NOT NULL` | which title this is a copy of |
| `barcode` | `TEXT UNIQUE NOT NULL` | physical label / accession number |
| `status` | `copy_status NOT NULL DEFAULT 'available'` | ENUM: `available` / `on_loan` / `lost` / `damaged` / `withdrawn` |
| `condition` | `copy_condition` | ENUM: `new` / `good` / `worn`; nullable |
| `shelf_location` | `TEXT` | e.g. `FIC-SMI-01` |
| `acquired_at` | `TIMESTAMPTZ` | |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

**`members`**

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `name` | `TEXT NOT NULL` | |
| `email` | `TEXT UNIQUE NOT NULL` | validated format |
| `phone` | `TEXT` | nullable |
| `status` | `member_status NOT NULL DEFAULT 'active'` | ENUM: `active` / `suspended` |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

The `copy_status`, `copy_condition`, and `member_status` PostgreSQL `ENUM` types
mirror the protobuf enums 1:1 (minus the `*_UNSPECIFIED` sentinel, which is an
API-boundary concept only). `app/api/mappers/` translates between the proto enum
integers and these DB enum labels.

**`loans`**

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `copy_id` | `BIGINT FK → book_copies.id` | the physical copy that was lent |
| `member_id` | `BIGINT FK → members.id` | |
| `borrowed_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `due_at` | `TIMESTAMPTZ NOT NULL` | e.g. borrowed_at + 14 days |
| `returned_at` | `TIMESTAMPTZ` | `NULL` while outstanding |
| `fine_cents` | `INT NOT NULL DEFAULT 0` | computed on overdue return |

### 3.3 Design Notes & Constraints

- **Prevent double-borrow — DB-enforced.** A copy can have at most one open loan.
  This is guaranteed by a partial unique index, not by counter arithmetic, so there
  is no race window:

  ```sql
  CREATE UNIQUE INDEX one_open_loan_per_copy
    ON loans (copy_id)
    WHERE returned_at IS NULL;
  ```

  The copy's `status` (`available` ⇄ `on_loan`) is flipped in the same transaction
  as the loan insert/return, keeping it consistent with the loan state.
- **History preserved.** Returns set `returned_at` rather than deleting the loan, so
  a copy accumulates a full borrowing history and the loan row is never destroyed.
- **Availability is derived**, not stored, avoiding a denormalized counter that can
  drift out of sync with reality.
- **Indexes.** `loans(member_id) WHERE returned_at IS NULL`,
  `loans(due_at) WHERE returned_at IS NULL` (overdue scans),
  `one_open_loan_per_copy` (above), `book_copies(book_id)`,
  `book_copies(barcode)`, `books(isbn)`, `members(email)`.

---

## 4. Key Workflows

### 4.1 Borrow a book

`BorrowBook` accepts either a `book_id` (lend *any* available copy — the common
staff flow) or a `copy_id` (a specific copy, e.g. from a barcode scan).

1. Client calls `BorrowBook(member_id, {book_id | copy_id})`.
2. Server opens a transaction and locks the target copy:
   - By `book_id`: `SELECT id FROM book_copies WHERE book_id = $1 AND status = 'available'
     LIMIT 1 FOR UPDATE SKIP LOCKED` — `SKIP LOCKED` lets concurrent borrows grab
     *different* copies without blocking each other.
   - By `copy_id`: `SELECT ... FOR UPDATE` on that row.
3. Validate: member exists & `active`; a copy was found (else no availability);
   copy `status = 'available'`.
4. Insert `loans` row (`due_at = now() + loan_period`), set copy `status = 'on_loan'`.
5. Commit. Return the created loan.

Failure cases → typed gRPC errors: `NOT_FOUND` (bad ids), `FAILED_PRECONDITION`
(no copies available / copy not available / member suspended), `INVALID_ARGUMENT`
(missing fields). The `one_open_loan_per_copy` index is the final backstop if two
transactions race for the same copy.

### 4.2 Return a book

1. Client calls `ReturnBook(loan_id)`.
2. Transaction + row lock on the loan and its copy.
3. Validate loan exists and `returned_at IS NULL` (else `FAILED_PRECONDITION`).
4. Set `returned_at = now()`; if past `due_at`, compute `fine_cents`.
5. Set the copy `status = 'available'` (or `damaged` if flagged on return). Commit.

### 4.3 Query outstanding loans

`ListLoans(member_id?, status=OUTSTANDING|RETURNED|OVERDUE, page)` →
filters on `returned_at` and `due_at`, joins book + member for display fields.

---

## 5. Service Interface (gRPC / Protobuf)

`proto/library/v1/library.proto` (sketch):

```proto
syntax = "proto3";
package library.v1;

import "google/protobuf/timestamp.proto";

service LibraryService {
  // Books (bibliographic records)
  rpc CreateBook (CreateBookRequest) returns (Book);
  rpc UpdateBook (UpdateBookRequest) returns (Book);
  rpc GetBook    (GetBookRequest)    returns (Book);
  rpc ListBooks  (ListBooksRequest)  returns (ListBooksResponse);

  // Copies (physical items)
  rpc AddCopy    (AddCopyRequest)    returns (BookCopy);
  rpc UpdateCopy (UpdateCopyRequest) returns (BookCopy);  // mark lost/damaged/withdrawn
  rpc ListCopies (ListCopiesRequest) returns (ListCopiesResponse);

  // Members
  rpc CreateMember (CreateMemberRequest) returns (Member);
  rpc UpdateMember (UpdateMemberRequest) returns (Member);
  rpc GetMember    (GetMemberRequest)    returns (Member);
  rpc ListMembers  (ListMembersRequest)  returns (ListMembersResponse);

  // Lending
  rpc BorrowBook (BorrowBookRequest) returns (Loan);
  rpc ReturnBook (ReturnBookRequest) returns (Loan);
  rpc ListLoans  (ListLoansRequest)  returns (ListLoansResponse);
}

message Book {
  int64 id = 1;
  string title = 2;
  string author = 3;
  string isbn = 4;
  int32 total_copies = 5;      // derived: COUNT(book_copies)
  int32 available_copies = 6;  // derived: COUNT(... status='available')
}

enum CopyStatus {
  COPY_STATUS_UNSPECIFIED = 0;
  COPY_STATUS_AVAILABLE   = 1;
  COPY_STATUS_ON_LOAN     = 2;
  COPY_STATUS_LOST        = 3;
  COPY_STATUS_DAMAGED     = 4;
  COPY_STATUS_WITHDRAWN   = 5;
}

enum CopyCondition {
  COPY_CONDITION_UNSPECIFIED = 0;
  COPY_CONDITION_NEW         = 1;
  COPY_CONDITION_GOOD        = 2;
  COPY_CONDITION_WORN        = 3;
}

enum MemberStatus {
  MEMBER_STATUS_UNSPECIFIED = 0;
  MEMBER_STATUS_ACTIVE      = 1;
  MEMBER_STATUS_SUSPENDED   = 2;
}

message BookCopy {
  int64 id = 1;
  int64 book_id = 2;
  string barcode = 3;
  CopyStatus status = 4;
  CopyCondition condition = 5;
  string shelf_location = 6;
}

message Member {
  int64 id = 1;
  string name = 2;
  string email = 3;
  string phone = 4;
  MemberStatus status = 5;
}

message Loan {
  int64 id = 1;
  int64 copy_id = 2;
  int64 member_id = 3;
  google.protobuf.Timestamp borrowed_at = 4;
  google.protobuf.Timestamp due_at = 5;
  google.protobuf.Timestamp returned_at = 6;  // unset while outstanding
  int32 fine_cents = 7;
}

message BorrowBookRequest {
  int64 member_id = 1;
  oneof target {
    int64 book_id = 2;  // lend any available copy of this title
    int64 copy_id = 3;  // lend this specific copy (e.g. barcode scan)
  }
}
message ReturnBookRequest {
  int64 loan_id = 1;
  bool  mark_damaged = 2;  // optional: return copy as damaged instead of available
}

enum LoanStatus { LOAN_STATUS_UNSPECIFIED = 0; OUTSTANDING = 1; RETURNED = 2; OVERDUE = 3; }
message ListLoansRequest  { int64 member_id = 1; LoanStatus status = 2; int32 page_size = 3; string page_token = 4; }
message ListLoansResponse { repeated Loan loans = 1; string next_page_token = 2; }
```

**Conventions**

- **Enums, not free strings.** All closed-set fields are typed protobuf enums
  (`CopyStatus`, `CopyCondition`, `MemberStatus`, `LoanStatus`), following the
  proto style guide: a zero `*_UNSPECIFIED` sentinel and a shared type prefix on
  every value. This makes the contract self-documenting and type-safe for
  generated clients, and lets the server reject unknown values at the boundary.
  These map to PostgreSQL `ENUM` types of the same value set (see §3.2), so the
  allowed set is enforced consistently at both the API and storage layers.
- Update methods use explicit request messages; a `field_mask` may be added for
  partial updates (§8).
- List methods are paginated (`page_size` + `page_token`).
- Errors use standard gRPC status codes mapped from domain rules (see §4).

---

## 6. Server Design

### 6.1 Layering

The Python server is organized into **feature modules** with shared transport and
persistence packages. Business rules never live in the gRPC or repository layers.

```
api/grpc/servicer.py          ← thin RPC adapter: proto ⇄ domain, map errors
        │
api/mappers/                  ← protobuf translation (proto-free below this line)
        │
{books, members, lending}/service.py   ← business rules, validation, transactions
        │
{books, members, lending}/repository.py ← SQL/ORM queries only
        │
persistence/                  ← engine, unit_of_work, ORM models
        │
PostgreSQL                    ← Alembic migrations in server/migrations/
```

**Dependency rules**

| Layer | May import | Must not import |
|---|---|---|
| `api/grpc/` | feature `service`, `api/mappers`, `core` | `repository` directly |
| `{feature}/service.py` | own `repository`, `persistence`, `core`; cross-feature `repository` for orchestration (e.g. lending → books, members) | `api/`, protobuf |
| `{feature}/repository.py` | `persistence/models`, `core/enums` | feature `service`, `api/` |
| `persistence/` | `core` | any feature module |

Keeping business rules out of the gRPC servicer makes the logic unit-testable
without a running server and reusable if a REST facade is added later.

### 6.2 Code organization

```
server/app/
  api/
    grpc/           server.py, servicer.py, error_handler.py
    mappers/        books, copies, members, lending, enums
  books/            service.py, repository.py   (bibliographic + physical copies)
  members/          service.py, repository.py
  lending/          service.py, repository.py   (borrow/return orchestration)
  persistence/
    engine.py       SQLAlchemy engine + SessionLocal
    unit_of_work.py transactional session scope
    models/         Book, BookCopy, Member, Loan
  core/             config, errors, enums, validation, pagination
  scripts/          seed.py
```

Physical copies (`book_copies`) live in the **books** module because they are a
child entity of a bibliographic record. **Lending** is a separate module because
borrow/return is a cross-domain workflow that coordinates members, copies, and
loans.

### 6.3 Transactions & Concurrency

Borrow/return run inside a single DB transaction. Borrow selects an available copy
with `SELECT ... FOR UPDATE SKIP LOCKED` so concurrent borrows of the same title
pick *different* copies without blocking; return locks the loan and its copy row.
The `one_open_loan_per_copy` partial unique index is the last-line safety net at the
DB level, guaranteeing a copy can never have two open loans even under a race.
Transaction boundaries are owned by `persistence/unit_of_work.py`; each feature
`service.py` opens a `unit_of_work()` scope per operation.

### 6.4 Validation

- Proto-level: required fields present (checked in `api/grpc/servicer.py`).
- Domain-level: email format, non-negative copies, ISBN checksum (if provided),
  member status, book availability (in `core/validation.py`, called from feature
  services).

### 6.5 REST Alternative

If gRPC-Web + Envoy proves too heavy for the timebox, the same service layer can be
exposed via **FastAPI** with equivalent resource endpoints
(`POST /books`, `POST /loans:borrow`, `POST /loans/{id}:return`,
`GET /loans?member_id=&status=`). The proto messages map 1:1 to Pydantic models.
This is the documented fallback per the spec ("use REST if you are not comfortable
with gRPC web").

---

## 7. Deployment & Local Setup

`docker-compose.yml` brings up four services:

| Service | Image / build | Port |
|---|---|---|
| `db` | `postgres:15` | 5432 |
| `server` | Python gRPC (built) | 50051 |
| `envoy` | `envoyproxy/envoy` w/ grpc-web filter | 8080 |
| `web` | Next.js | 3000 |

**Config via environment variables:** `DATABASE_URL`, `GRPC_PORT`,
`LOAN_PERIOD_DAYS`, `FINE_CENTS_PER_DAY`.

**Bring-up sequence:** `docker compose up` → Alembic migrations run on server start
(`server/migrations/`) → optional `python -m app.scripts.seed` inserts sample
books/members → gRPC server starts via `python -m app.api.grpc.server` → UI
available at `:3000`.

---

## 8. Future Enhancements

- **Copies-count alternative.** For a much simpler deployment that doesn't need to
  distinguish physical copies, `book_copies` can be collapsed into
  `total_copies` / `available_copies` columns on `books`, with double-borrow
  enforced by a transactional decrement + `CHECK` constraint instead of the
  per-copy unique index. Fewer tables/RPCs, at the cost of per-item tracking.
- **Reservations / holds** queue when all copies are out.
- **AuthN/AuthZ** — staff login, roles (librarian vs. admin).
- **Notifications** — overdue reminders via email/SMS.
- **Fine collection** and payment records.
- **`field_mask`** support for partial updates.
- **Full-text search** on title/author (Postgres `tsvector`).

---

## 9. Testing Strategy

- **Service-layer tests** per feature module (`server/tests/{books,members,lending}/`)
  exercising business rules against a real PostgreSQL database (needed for ENUM
  types, partial unique indexes, and `SKIP LOCKED`).
- **Shared fixtures** in `server/tests/helpers.py` and table truncation in
  `conftest.py` for per-test isolation.
- **Integration tests** (future) driving the gRPC server end-to-end
  (borrow → list → return).
- **Sample client script** (`examples/client.py`) demonstrating each RPC, per the
  spec's optional tip.
- Key edge cases: borrow when no copies available, double-return, borrow by
  suspended member, overdue fine computation.
