from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["up", "down"]
    postgis_version: str | None = None
    last_pipeline_run: datetime | None = None  # latest successful step in ops.pipeline_run
