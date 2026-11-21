import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_engine
from app.schemas.health import HealthOut

log = logging.getLogger("app.health")


def check_health() -> HealthOut:
    try:
        with get_engine().connect() as conn:
            version = conn.execute(text("SELECT postgis_lib_version()")).scalar_one()
    except SQLAlchemyError as exc:
        log.warning("database unavailable", extra={"error": str(exc).splitlines()[0]})
        return HealthOut(status="degraded", database="down")
    return HealthOut(status="ok", database="up", postgis_version=str(version))
