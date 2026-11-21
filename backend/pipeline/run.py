"""Pipeline orchestration. Phase 1: extract/load + raw row-count verification.

Later phases append steps here (dbt build, quality checks, forecast), each tracked
in ops.pipeline_run under the same run_id.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine

from pipeline.load import (
    LoadResult,
    load_boundaries,
    load_capacity,
    load_enrolment,
    load_school_points,
)
from pipeline.runlog import track_step
from pipeline.verify import verify_raw_counts

BACKEND_DIR = Path(__file__).resolve().parents[1]

Loader = Callable[[Connection, Path, uuid.UUID], LoadResult]

LOAD_STEPS: list[tuple[str, str, Loader, bool]] = [
    # step name, sub-folder, loader, required
    ("load_enrolment", "enrolment", load_enrolment, True),
    ("load_capacity", "capacity", load_capacity, True),
    ("load_boundaries", "boundaries", load_boundaries, True),
    ("load_school_points", "boundaries", load_school_points, False),
]


def migrate(database_url: str) -> None:
    """Apply Alembic migrations (alembic upgrade head) to the given database."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["url"] = database_url
    cfg.attributes["skip_logging_config"] = True
    command.upgrade(cfg, "head")


def run_pipeline(engine: Engine, source_dir: Path, source: str, run_id: uuid.UUID) -> list[dict]:
    if not source_dir.is_dir():
        raise FileNotFoundError(f"source folder {source_dir} does not exist; run `make data`")
    summary: list[dict] = []

    for step, sub, loader, required in LOAD_STEPS:
        folder = source_dir / sub
        with track_step(engine, run_id, step, source) as res, engine.begin() as conn:
            # Optional loaders still run when their files are absent: they empty their
            # table, so rows from an earlier run can never mix with this one.
            out = loader(conn, folder, run_id)
            res.rows_in, res.rows_out = out.rows_in, out.rows_out
            res.details = {"per_file": out.per_file, **out.notes}
            if not required and not out.per_file:
                res.message = "optional source not present; table emptied"
        summary.append({"step": step, **asdict(out)})

    with track_step(engine, run_id, "verify_raw_counts", source) as res, engine.connect() as conn:
        v = verify_raw_counts(conn, source_dir)
        res.rows_in, res.rows_out = v.expected_rows, v.loaded_rows
        res.message = f"{v.files} files: source rows = loaded rows"
        res.details = {"per_file": v.per_file}
    summary.append({"step": "verify_raw_counts", "files": v.files, "rows": v.loaded_rows})
    return summary
