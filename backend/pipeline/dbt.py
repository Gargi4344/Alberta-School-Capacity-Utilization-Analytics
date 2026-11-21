"""Run dbt in-process (dbtRunner), configured from the app settings.

The dbt profile reads ABCAP_DB_* environment variables; they are filled here from
DATABASE_URL so the connection is configured in exactly one place.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url

DBT_DIR = Path(__file__).resolve().parents[1] / "dbt"


def dbt_env(database_url: str) -> dict[str, str]:
    url = make_url(database_url)
    return {
        "ABCAP_DB_HOST": url.host or "localhost",
        "ABCAP_DB_PORT": str(url.port or 5432),
        "ABCAP_DB_USER": url.username or "",
        "ABCAP_DB_PASSWORD": url.password or "",
        "ABCAP_DB_NAME": url.database or "",
    }


def dbt_vars(utilization_threshold_pct: float, over_capacity_pct: float) -> dict[str, Any]:
    return {
        "utilization_threshold": utilization_threshold_pct / 100,
        "over_capacity_threshold": over_capacity_pct / 100,
    }


@contextmanager
def _env(values: dict[str, str]) -> Iterator[None]:
    old = {k: os.environ.get(k) for k in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@dataclass
class DbtOutcome:
    success: bool
    counts: dict[str, int] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def invoke(args: list[str], database_url: str, variables: dict[str, Any] | None = None) -> Any:
    """Run any dbt command; returns dbt's own result object."""
    from dbt.cli.main import dbtRunner

    cli = [*args, "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    if variables:
        cli += ["--vars", json.dumps(variables)]
    with _env(dbt_env(database_url)):
        return dbtRunner().invoke(cli)


def build(database_url: str, variables: dict[str, Any]) -> DbtOutcome:
    """`dbt build` (seeds, models, tests) and a summary for ops.pipeline_run."""
    res = invoke(["build"], database_url, variables)
    if res.exception is not None:
        return DbtOutcome(success=False, error=f"{type(res.exception).__name__}: {res.exception}")
    results = list(getattr(res.result, "results", []) or [])
    counts = Counter(str(r.status) for r in results)
    failures = [
        f"{r.node.unique_id}: {r.message or r.status}"
        for r in results
        if str(r.status) in {"error", "fail"}
    ]
    warnings = [
        f"{r.node.unique_id}: {r.failures} row(s)" for r in results if str(r.status) == "warn"
    ]
    return DbtOutcome(
        success=bool(res.success),
        counts=dict(counts),
        failures=failures,
        warnings=warnings,
    )
