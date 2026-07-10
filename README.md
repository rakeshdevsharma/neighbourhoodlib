# Neighborhood Library Service

A service to manage a small library's **books**, **physical copies**, **members**,
and **lending** (borrow / return), built with:

- **Python** gRPC server (SQLAlchemy 2.0 + Alembic)
- **PostgreSQL** data store
- **gRPC** with Protocol Buffers, exposed to the browser via **gRPC-Web** (Envoy)
- **Next.js** (React + TypeScript) frontend

The architecture, data model, and design decisions are documented in
[HIGH_LEVEL_DESIGN.md](HIGH_LEVEL_DESIGN.md). This README is the how-to-run guide.

---

## Architecture

```
Browser (Next.js) ──gRPC-Web──► Envoy ──gRPC──► Python server ──► PostgreSQL
   :3000                        :8080           :50051              :5432
```

- Browsers can't speak native gRPC, so **Envoy** translates gRPC-Web ⇄ gRPC.
- The Python server is the only component that touches the database.
- Data model is **per-copy**: `books` (bibliographic) → `book_copies` (physical
  items) → `loans`. A partial unique index guarantees a copy can never have two
  open loans. See the design doc for details.

The server is organized by **feature modules** (`books`, `members`, `lending`)
with shared **transport** (`api/grpc`), **persistence** (`persistence/`), and
**core** utilities (`core/`). Call flow:

```
api/grpc/servicer  →  {books,members,lending}/service  →  */repository  →  persistence
```

---

## Quick start (Docker)

Prerequisites: **Docker** + **Docker Compose** (v2).

```bash
cp .env.example .env      # optional; sensible defaults are built in
docker compose up --build
```

This starts four containers and, on first boot, applies migrations and seeds a
little sample data. Once healthy:

| Service | URL | Notes |
|---|---|---|
| Frontend | http://localhost:3000 | staff dashboard |
| Envoy (gRPC-Web) | http://localhost:8080 | browser → gRPC bridge |
| gRPC server | localhost:50051 | native gRPC (for CLI clients) |
| Envoy admin | http://localhost:9901 | proxy stats/health |
| PostgreSQL | localhost:5432 | user/pass/db = `library` |

Open **http://localhost:3000** and use the Books / Members / Loans tabs to
create records, borrow, and return.

Tear down (and wipe the database volume):

```bash
docker compose down -v
```

---

## Trying the API without the UI

### Sample Python client

Exercises the full flow (create book → add copies → member → borrow → list →
sold-out error → return):

```bash
# one-time: generate Python stubs locally
cd server && bash scripts/gen_proto.sh && cd ..

# run against the gRPC server exposed by compose
PYTHONPATH=server/gen python examples/client.py
```

### grpcurl (server reflection is enabled)

```bash
grpcurl -plaintext localhost:50051 list library.v1.LibraryService
grpcurl -plaintext -d '{"title":"Dune","author":"Herbert"}' \
  localhost:50051 library.v1.LibraryService/CreateBook
grpcurl -plaintext -d '{"member_id":1,"book_id":1}' \
  localhost:50051 library.v1.LibraryService/BorrowBook
```

---

## Configuration

Environment variables (see [.env.example](.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `library` | DB credentials |
| `LOAN_PERIOD_DAYS` | `14` | days until a loan is due |
| `FINE_CENTS_PER_DAY` | `25` | overdue fine per day, in cents |
| `SEED_ON_START` | `true` | seed sample data on first boot |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8080` | Envoy URL baked into the frontend |

---

## Local development

### Regenerate stubs after editing the `.proto`

```bash
make proto-py    # Python stubs  -> server/gen/
make proto-web   # grpc-web stubs -> web/gen/   (needs protoc + protoc-gen-grpc-web)
```

The Docker builds do this automatically; the targets above are for running
outside containers.

### Run the backend tests

Tests run the real service + repository layers against PostgreSQL (needed for
enum types, the partial unique index, and `SKIP LOCKED`). They are split by
feature module under `server/tests/{books,members,lending}/`.

Create a throwaway database and point the tests at it:

```bash
docker compose up -d db
docker compose exec db createdb -U library library_test

cd server
pip install -r requirements-dev.txt
TEST_DATABASE_URL=postgresql+psycopg://library:library@localhost:5432/library_test \
  python -m pytest -v
```

Or run inside the server container:

```bash
docker compose run --rm \
  -e TEST_DATABASE_URL=postgresql+psycopg://library:library@db:5432/library_test \
  server sh -c "pip install -q pytest && python -m pytest -v"
```

### Database migrations

Schema is owned by Alembic (`server/migrations/`). The server applies
`alembic upgrade head` on start. To add a migration during development:

```bash
cd server
alembic revision -m "describe change"   # then edit the generated file
alembic upgrade head
```

---

## Project layout

```
proto/library/v1/library.proto   # service + message + enum definitions
server/
  app/
    api/
      grpc/
        server.py         # gRPC entrypoint (+ reflection); python -m app.api.grpc.server
        servicer.py       # thin RPC adapter; delegates to feature services
        error_handler.py  # domain error → gRPC status mapping
      mappers/            # proto ↔ domain translation (per entity)
    books/
      service.py          # bibliographic records + physical copies
      repository.py
    members/
      service.py
      repository.py
    lending/
      service.py          # borrow/return, fines, loan queries
      repository.py
    persistence/
      engine.py           # SQLAlchemy engine + session factory
      unit_of_work.py     # transactional session scope
      models/             # ORM models (book, member, loan)
    core/
      config.py           # env-driven settings
      errors.py           # domain exceptions
      enums.py            # domain enums (mirror PG ENUM types)
      validation.py
      pagination.py
    scripts/
      seed.py             # sample data; python -m app.scripts.seed
  migrations/             # Alembic
  scripts/                # Docker entrypoint + proto codegen
  tests/
    books/                # book + copy service tests
    members/
    lending/              # borrow/return service tests
    helpers.py            # shared test fixtures
envoy/envoy.yaml          # gRPC-Web proxy config
web/                      # Next.js frontend (grpc-web client)
examples/client.py        # sample gRPC client
docker-compose.yml
Makefile
```

---

## Design highlights

- **Per-copy model** so the DB itself enforces "no double-borrow" via a partial
  unique index (`one_open_loan_per_copy`), rather than a drift-prone counter.
- **Typed enums everywhere** (`CopyStatus`, `CopyCondition`, `MemberStatus`,
  `LoanStatus`) in both the proto contract and PostgreSQL.
- **Concurrency-safe borrowing** with `SELECT … FOR UPDATE SKIP LOCKED`, so two
  staff can borrow different copies of the same title without blocking.
- **Layered server** organized by feature module
  (`api/grpc` → `{books,members,lending}/service` → `*/repository` → `persistence`),
  keeping business logic free of any gRPC or DB-transport concerns and unit-testable.
- **Validation & typed errors** mapped to gRPC status codes
  (`NOT_FOUND`, `INVALID_ARGUMENT`, `FAILED_PRECONDITION`, `ALREADY_EXISTS`).

See [HIGH_LEVEL_DESIGN.md](HIGH_LEVEL_DESIGN.md) for the full rationale.

---

## Troubleshooting

- **Frontend can't reach the API**: confirm Envoy is up (`http://localhost:9901`)
  and `NEXT_PUBLIC_API_URL` matches the Envoy URL. It's baked at build time, so
  changing it requires `docker compose build web`.
- **`web` build fails downloading the grpc-web plugin**: it's fetched from GitHub
  releases per-arch during the build; ensure network access, or run
  `make proto-web` locally.
- **Server exits on start**: it waits for Postgres health then runs migrations;
  check `docker compose logs server`.
