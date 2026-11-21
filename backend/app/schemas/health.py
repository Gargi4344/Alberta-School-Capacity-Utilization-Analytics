from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["up", "down"]
    postgis_version: str | None = None
    last_pipeline_run: datetime | None = None  # filled once ops.pipeline_run exists (Phase 1)
