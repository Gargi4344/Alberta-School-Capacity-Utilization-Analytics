"""Record every pipeline step in ops.pipeline_run.

The 'running' row is committed before the step starts, in its own transaction, so a
crash still leaves a trace. The row is then closed as 'success' or 'failed'.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, insert, update

from app.db.models import PipelineRun

log = logging.getLogger("pipeline.run")


@dataclass
class StepResult:
    rows_in: int | None = None
    rows_out: int | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@contextmanager
def track_step(engine: Engine, run_id: uuid.UUID, step: str, source: str) -> Iterator[StepResult]:
    started = datetime.now(UTC)
    with engine.begin() as conn:
        row_id = conn.execute(
            insert(PipelineRun)
            .values(run_id=run_id, step=step, source=source, started_at=started, status="running")
            .returning(PipelineRun.id)
        ).scalar_one()
    log.info("step started", extra={"run_id": str(run_id), "step": step})

    result = StepResult()
    try:
        yield result
    except Exception as exc:
        message = root_cause(exc)
        _close(engine, row_id, "failed", result, message=message)
        log.error("step failed", extra={"run_id": str(run_id), "step": step, "error": message})
        raise
    _close(engine, row_id, "success", result, message=result.message)
    log.info(
        "step finished",
        extra={
            "run_id": str(run_id),
            "step": step,
            "rows_in": result.rows_in,
            "rows_out": result.rows_out,
        },
    )


def root_cause(exc: BaseException, limit: int = 1000) -> str:
    """The innermost exception's first line. Wrapped database errors (pandas, SQLAlchemy)
    otherwise bury the real reason under the full SQL statement."""
    inner = exc
    while (nxt := inner.__cause__ or inner.__context__) is not None:
        inner = nxt
    first_line = (str(inner).strip().splitlines() or [""])[0]
    return f"{type(inner).__name__}: {first_line}"[:limit]


def _close(engine: Engine, row_id: int, status: str, res: StepResult, message: str | None) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(PipelineRun)
            .where(PipelineRun.id == row_id)
            .values(
                status=status,
                finished_at=datetime.now(UTC),
                rows_in=res.rows_in,
                rows_out=res.rows_out,
                message=message,
                details=res.details or None,
            )
        )
