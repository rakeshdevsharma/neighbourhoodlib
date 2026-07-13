"""Runtime configuration, sourced from environment variables.

``settings`` is instantiated at import time so modules can read config without
passing a context object. Override via env vars in Docker or local shell.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration read once from environment variables."""

    database_url: str
    grpc_port: int
    loan_period_days: int
    fine_cents_per_day: int
    max_page_size: int
    default_page_size: int

    @staticmethod
    def from_env() -> "Settings":
        """Build settings from environment variables, falling back to dev defaults.

        Called once at import time; ``settings`` is shared process-wide. Docker
        Compose injects ``DATABASE_URL``, ``LOAN_PERIOD_DAYS``, etc.
        """
        return Settings(
            database_url=os.environ.get(
                "DATABASE_URL",
                "postgresql+psycopg://library:library@localhost:5432/library",
            ),
            grpc_port=int(os.environ.get("GRPC_PORT", "50051")),
            loan_period_days=int(os.environ.get("LOAN_PERIOD_DAYS", "14")),
            fine_cents_per_day=int(os.environ.get("FINE_CENTS_PER_DAY", "25")),
            max_page_size=int(os.environ.get("MAX_PAGE_SIZE", "100")),
            default_page_size=int(os.environ.get("DEFAULT_PAGE_SIZE", "20")),
        )


settings = Settings.from_env()
