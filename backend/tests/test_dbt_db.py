"""Phase 2: the dbt star schema built from data/sample/ (9 real authorities)."""

import uuid

import jinja2
import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.db.models import PipelineRun
from pipeline.dbt import DBT_DIR
from pipeline.readers import normalize_name

pytestmark = pytest.mark.db


def _scalar(engine: Engine, sql: str) -> object:
    with engine.connect() as conn:
        return conn.execute(text(sql)).scalar_one()


def test_dbt_build_step_logged_with_expected_warning(
    db_engine: Engine, sample_run: uuid.UUID
) -> None:
    with Session(db_engine) as s:
        step = s.query(PipelineRun).filter_by(run_id=sample_run, step="dbt_build").one()
    assert step.status == "success"
    assert step.details["failures"] == []
    # The sample includes Lloydminster's Saskatchewan-side schools, which match no
    # Alberta enrolment: the only expected warning.
    assert step.details["warnings"] == [
        "test.ab_capacity.assert_capacity_rows_match_a_school: 4 row(s)"
    ]


def test_star_schema_row_counts(db_engine: Engine, sample_run: uuid.UUID) -> None:
    school_years = _scalar(db_engine, "SELECT count(*) FROM raw.enrolment_school")
    authority_years = _scalar(db_engine, "SELECT count(*) FROM raw.enrolment_authority")
    assert _scalar(db_engine, "SELECT count(*) FROM mart.dim_school_year") == 10
    assert _scalar(db_engine, "SELECT count(*) FROM mart.dim_authority") == 9
    assert _scalar(db_engine, "SELECT count(*) FROM mart.fact_school_year") == school_years
    assert _scalar(db_engine, "SELECT count(*) FROM mart.fact_enrolment") == school_years * 14
    assert _scalar(db_engine, "SELECT count(*) FROM mart.agg_authority_year") == authority_years


def test_marts_reconcile_with_published_totals(db_engine: Engine, sample_run: uuid.UUID) -> None:
    diff = _scalar(
        db_engine,
        """
        SELECT count(*) FROM (
            SELECT school_year, sum(headcount) AS t FROM mart.fact_enrolment GROUP BY 1
        ) f
        FULL JOIN (
            SELECT school_year, sum(total) AS t FROM raw.enrolment_authority GROUP BY 1
        ) r USING (school_year)
        WHERE f.t IS DISTINCT FROM r.t
        """,
    )
    assert diff == 0


def test_dimensions_carry_latest_names_and_boundaries(
    db_engine: Engine, sample_run: uuid.UUID
) -> None:
    with db_engine.connect() as conn:
        red_deer = conn.execute(
            text("SELECT authority_name, authority_type, boundary_layer, geom IS NOT NULL AS g "
                 "FROM mart.dim_authority WHERE authority_code = '0019'")
        ).one()  # fmt: skip
        francophone = conn.execute(
            text(
                "SELECT authority_type, geom FROM mart.dim_authority WHERE authority_code = '0284'"
            )
        ).one()
        big_valley = conn.execute(
            text("SELECT grades_offered, is_open FROM mart.dim_school WHERE school_code = '4601'")
        ).one()
    # Renamed in 2019; the dimension keeps the latest name.
    assert red_deer.authority_name == "The Red Deer Catholic Separate School Division"
    assert (red_deer.authority_type, red_deer.boundary_layer, red_deer.g) == (
        "separate",
        "separate",
        True,
    )
    assert francophone.authority_type == "francophone" and francophone.geom is None
    assert (big_valley.grades_offered, big_valley.is_open) == ("ECS\N{EN DASH}9", True)


def test_estimate_matches_published_in_capacity_year(
    db_engine: Engine, sample_run: uuid.UUID
) -> None:
    with db_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT utilization_published p, utilization_estimated e, utilization_basis b "
                "FROM mart.fact_school_year WHERE school_year = '2023-24' AND capacity IS NOT NULL"
            )
        ).all()
        basis_other_years = conn.execute(
            text(
                "SELECT DISTINCT utilization_basis FROM mart.fact_school_year "
                "WHERE school_year <> '2023-24' AND capacity IS NOT NULL"
            )
        ).scalars().all()  # fmt: skip
    assert rows, "sample should contain schools with capacity"
    assert all(r.b == "published" and abs(r.p - r.e) < 1e-9 for r in rows)
    assert basis_other_years == ["estimated"]


def test_sql_name_normalization_matches_python(db_engine: Engine, sample_run: uuid.UUID) -> None:
    """The dbt macro and pipeline.readers.normalize_name must agree on every name,
    or the capacity join would silently differ from the audit."""
    macro = (DBT_DIR / "macros" / "normalize_name.sql").read_text(encoding="utf-8")
    expr = jinja2.Environment().from_string(macro + "{{ normalize_name('n.name') }}").render()
    names_sql = """
        SELECT DISTINCT name FROM (
            SELECT school_name AS name FROM raw.enrolment_school
            UNION SELECT authority_name FROM raw.enrolment_school
            UNION SELECT school_name FROM raw.capacity
            UNION SELECT authority_name FROM raw.capacity
            UNION SELECT unnest(ARRAY['École St. Gérard & Ste. Anne', 'St.Paul', 'A  -  B'])
        ) AS n
    """
    with db_engine.connect() as conn:
        rows = conn.execute(text(f"SELECT n.name, {expr.strip()} FROM ({names_sql}) AS n")).all()
    mismatches = [(name, sql) for name, sql in rows if sql != normalize_name(name)]
    assert len(rows) > 300
    assert mismatches == []
