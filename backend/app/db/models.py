"""SQLAlchemy models for the tables this app owns (raw and ops schemas).

The staging and mart schemas are built by dbt (Phase 2) and are not declared here.
Raw tables keep the source's wide layout (one column per grade); every row records
the file it came from, its Excel row or feature index, and the pipeline run_id.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

GRADE_COLUMNS = ["ungraded", "ecs", *[f"grade_{g}" for g in range(1, 13)]]


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


# ---------------------------------------------------------------------------
# ops
# ---------------------------------------------------------------------------


class PipelineRun(Base):
    """One row per pipeline step per run. All steps of a run share a run_id."""

    __tablename__ = "pipeline_run"
    __table_args__ = ({"schema": "ops"},)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    step: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(16))  # raw or sample
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_in: Mapped[int | None] = mapped_column(Integer)
    rows_out: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))  # running, success, failed
    message: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


# ---------------------------------------------------------------------------
# raw (Core tables: the grade columns are generated)
# ---------------------------------------------------------------------------


def _lineage() -> list[Column[Any]]:
    return [
        Column("source_file", String(255), nullable=False),
        Column("run_id", UUID(as_uuid=True), nullable=False),
        Column("loaded_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    ]


def _grades() -> list[Column[Any]]:
    return [Column(g, Integer, nullable=False) for g in [*GRADE_COLUMNS, "total"]]


raw_enrolment_school = Table(
    "enrolment_school",
    Base.metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("school_year", String(7), nullable=False),
    Column("authority_category", String(32), nullable=False),
    Column("authority_code", String(4), nullable=False),
    Column("authority_name", String(255), nullable=False),
    Column("school_code", String(4), nullable=False),
    Column("school_name", String(255), nullable=False),
    *_grades(),
    Column("source_row", Integer, nullable=False),
    *_lineage(),
    schema="raw",
)

raw_enrolment_authority = Table(
    "enrolment_authority",
    Base.metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("school_year", String(7), nullable=False),
    Column("authority_category", String(32), nullable=False),
    Column("authority_code", String(4), nullable=False),
    Column("authority_name", String(255), nullable=False),
    *_grades(),
    Column("source_row", Integer, nullable=False),
    *_lineage(),
    schema="raw",
)

raw_capacity = Table(
    "capacity",
    Base.metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("school_year", String(7), nullable=False),
    Column("authority_name", String(255), nullable=False),
    Column("school_name", String(255), nullable=False),
    Column("facility_name", String(255)),
    Column("facility_location", String(255)),
    Column("net_capacity", Integer, nullable=False),
    Column("adj_total_enrolment", Float, nullable=False),
    Column("utilization_rate", Float, nullable=False),
    Column("source_row", Integer, nullable=False),
    *_lineage(),
    schema="raw",
)

raw_authority_boundary = Table(
    "authority_boundary",
    Base.metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("authority_code", String(4), nullable=False),
    Column("authority_name", String(255)),
    Column("layer", String(16), nullable=False),  # public or separate
    Column("boundary_year", Integer),
    Column("was_invalid", Boolean, nullable=False),
    Column("geom", Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False),
    Column("source_feature", Integer, nullable=False),
    *_lineage(),
    schema="raw",
)

raw_school_point = Table(
    "school_point",
    Base.metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("school_code", String(4), nullable=False),
    Column("school_name", String(255)),
    Column("grades", String(64)),
    Column("school_type", String(16)),
    Column("address", String(255)),
    Column("geom", Geometry("POINT", srid=4326, spatial_index=False), nullable=False),
    Column("source_feature", Integer, nullable=False),
    *_lineage(),
    schema="raw",
)

RAW_TABLES = {
    "enrolment_school": raw_enrolment_school,
    "enrolment_authority": raw_enrolment_authority,
    "capacity": raw_capacity,
    "authority_boundary": raw_authority_boundary,
    "school_point": raw_school_point,
}
