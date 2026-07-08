"""Runtime configuration, sourced from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    grpc_port: int
    loan_period_days: int
    fine_cents_per_day: int
    max_page_size: int
    default_page_size: int

    @staticmethod
    def from_env() -> "Settings":
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
