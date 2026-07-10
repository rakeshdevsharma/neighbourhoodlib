#!/usr/bin/env bash
# Wait for Postgres, apply migrations, then start the gRPC server.
set -euo pipefail

echo "Waiting for the database..."
python - <<'PY'
import os, time
import psycopg

url = os.environ.get("DATABASE_URL", "").replace("postgresql+psycopg", "postgresql")
for attempt in range(60):
    try:
        with psycopg.connect(url, connect_timeout=2):
            break
    except Exception as exc:  # noqa: BLE001
        print(f"  db not ready ({attempt+1}/60): {exc}")
        time.sleep(1)
else:
    raise SystemExit("database never became ready")
print("Database is ready.")
PY

echo "Applying migrations..."
alembic upgrade head

if [ "${SEED_ON_START:-false}" = "true" ]; then
  echo "Seeding sample data..."
  python -m app.scripts.seed || echo "  seeding skipped/failed (non-fatal)"
fi

echo "Starting gRPC server..."
exec python -m app.api.grpc.server
