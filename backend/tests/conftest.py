"""Shared fixtures.

Database tests use a separate database (default `abcap_test` on the local Compose
server, or TEST_DATABASE_URL). They are skipped when PostgreSQL is not reachable,
unless REQUIRE_DB=1 (set in CI), where a missing database is a failure.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = REPO_ROOT / "data" / "sample"
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://abcap:abcap@localhost:5432/abcap_test"
)


def _ensure_database(url: str) -> None:
    target = make_url(url)
    admin = create_engine(
        target.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 3},
    )
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
            ).scalar()
            if not exists:
                # Database name comes from test configuration, never from user input.
                conn.exec_driver_sql(f'CREATE DATABASE "{target.database}"')
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def db_url() -> str:
    try:
        _ensure_database(TEST_DATABASE_URL)
    except OperationalError as exc:
        if os.environ.get("REQUIRE_DB") == "1":
            pytest.fail(f"PostgreSQL required but not reachable: {exc}")
        pytest.skip("PostgreSQL not reachable; start it with `make db-up`")
    from pipeline.run import migrate

    migrate(TEST_DATABASE_URL)
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def db_engine(db_url: str) -> Iterator[Engine]:
    engine = create_engine(db_url)
    yield engine
    engine.dispose()
