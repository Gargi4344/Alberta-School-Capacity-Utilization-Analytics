import logging
from datetime import datetime

from sqlalchemy import Connection, func, select, text
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError

from app.db.models import PipelineRun
from app.db.session import get_engine
from app.schemas.health import HealthOut

log = logging.getLogger("app.health")


def _last_successful_run(conn: Connection) -> datetime | None:
    try:
        with conn.begin_nested():
            return conn.execute(
                select(func.max(PipelineRun.finished_at)).where(PipelineRun.status == "success")
            ).scalar_one()
    except ProgrammingError:  # migrations not applied yet
        return None


def check_health() -> HealthOut:
    try:
        with get_engine().connect() as conn:
            version = conn.execute(text("SELECT postgis_lib_version()")).scalar_one()
            last_run = _last_successful_run(conn)
    except SQLAlchemyError as exc:
        log.warning("database unavailable", extra={"error": str(exc).splitlines()[0]})
        return HealthOut(status="degraded", database="down")
    return HealthOut(
        status="ok", database="up", postgis_version=str(version), last_pipeline_run=last_run
    )
