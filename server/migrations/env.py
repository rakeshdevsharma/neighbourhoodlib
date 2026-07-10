"""Alembic environment. Uses DATABASE_URL and the ORM metadata.

Alembic reads ``target_metadata`` from the SQLAlchemy models so autogenerate
can diff the ORM against the live database. ``env.py`` overrides the ini-file
URL with the ``DATABASE_URL`` environment variable.
"""
from __future__ import annotations

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.persistence.models import Base

config = context.config

database_url = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://library:library@localhost:5432/library"
)
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting (``alembic upgrade head --sql``)."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
