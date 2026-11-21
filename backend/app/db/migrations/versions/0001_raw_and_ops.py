"""Raw source tables and ops.pipeline_run.

Revision ID: 0001
Revises:
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRADES = ["ungraded", "ecs", *[f"grade_{g}" for g in range(1, 13)], "total"]


def _lineage() -> list[sa.Column]:
    return [
        sa.Column("source_file", sa.String(255), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "loaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _pk(table: str) -> list:
    return [
        sa.Column("id", sa.BigInteger, sa.Identity(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=f"pk_{table}"),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE SCHEMA IF NOT EXISTS raw")
    op.execute("CREATE SCHEMA IF NOT EXISTS ops")

    op.create_table(
        "pipeline_run",
        *_pk("pipeline_run"),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("step", sa.String(64), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("rows_in", sa.Integer),
        sa.Column("rows_out", sa.Integer),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("message", sa.Text),
        sa.Column("details", JSONB),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'failed')", name="ck_pipeline_run_status"
        ),
        schema="ops",
    )
    op.create_index("ix_pipeline_run_run_id", "pipeline_run", ["run_id"], schema="ops")

    for table, has_school in (("enrolment_school", True), ("enrolment_authority", False)):
        school_cols = (
            [
                sa.Column("school_code", sa.String(4), nullable=False),
                sa.Column("school_name", sa.String(255), nullable=False),
            ]
            if has_school
            else []
        )
        op.create_table(
            table,
            *_pk(table),
            sa.Column("school_year", sa.String(7), nullable=False),
            sa.Column("authority_category", sa.String(32), nullable=False),
            sa.Column("authority_code", sa.String(4), nullable=False),
            sa.Column("authority_name", sa.String(255), nullable=False),
            *school_cols,
            *[sa.Column(g, sa.Integer, nullable=False) for g in GRADES],
            sa.Column("source_row", sa.Integer, nullable=False),
            *_lineage(),
            schema="raw",
        )

    op.create_table(
        "capacity",
        *_pk("capacity"),
        sa.Column("school_year", sa.String(7), nullable=False),
        sa.Column("authority_name", sa.String(255), nullable=False),
        sa.Column("school_name", sa.String(255), nullable=False),
        sa.Column("facility_name", sa.String(255)),
        sa.Column("facility_location", sa.String(255)),
        sa.Column("net_capacity", sa.Integer, nullable=False),
        sa.Column("adj_total_enrolment", sa.Float, nullable=False),
        sa.Column("utilization_rate", sa.Float, nullable=False),
        sa.Column("source_row", sa.Integer, nullable=False),
        *_lineage(),
        schema="raw",
    )

    op.create_table(
        "authority_boundary",
        *_pk("authority_boundary"),
        sa.Column("authority_code", sa.String(4), nullable=False),
        sa.Column("authority_name", sa.String(255)),
        sa.Column("layer", sa.String(16), nullable=False),
        sa.Column("boundary_year", sa.Integer),
        sa.Column("was_invalid", sa.Boolean, nullable=False),
        sa.Column("geom", Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False),
        sa.Column("source_feature", sa.Integer, nullable=False),
        *_lineage(),
        schema="raw",
    )
    op.create_index(
        "ix_authority_boundary_geom",
        "authority_boundary",
        ["geom"],
        schema="raw",
        postgresql_using="gist",
    )

    op.create_table(
        "school_point",
        *_pk("school_point"),
        sa.Column("school_code", sa.String(4), nullable=False),
        sa.Column("school_name", sa.String(255)),
        sa.Column("grades", sa.String(64)),
        sa.Column("school_type", sa.String(16)),
        sa.Column("address", sa.String(255)),
        sa.Column("geom", Geometry("POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("source_feature", sa.Integer, nullable=False),
        *_lineage(),
        schema="raw",
    )
    op.create_index(
        "ix_school_point_geom", "school_point", ["geom"], schema="raw", postgresql_using="gist"
    )


def downgrade() -> None:
    for table in (
        "school_point",
        "authority_boundary",
        "capacity",
        "enrolment_authority",
        "enrolment_school",
    ):
        op.drop_table(table, schema="raw")
    op.drop_table("pipeline_run", schema="ops")
