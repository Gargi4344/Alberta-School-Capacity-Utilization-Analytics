"""End-to-end Phase 1 tests: the real pipeline on data/sample/ against PostgreSQL."""

import shutil
import uuid
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from app.db.models import RAW_TABLES, PipelineRun
from pipeline.run import run_pipeline
from pipeline.verify import expected_counts
from tests.conftest import SAMPLE_DIR

pytestmark = pytest.mark.db


def _count(engine: Engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(RAW_TABLES[table])).scalar_one()


def _steps(engine: Engine, run_id: uuid.UUID) -> dict[str, PipelineRun]:
    with Session(engine) as session:
        rows = session.scalars(select(PipelineRun).where(PipelineRun.run_id == run_id)).all()
    return {r.step: r for r in rows}


@pytest.fixture(scope="module")
def sample_run(db_engine: Engine) -> uuid.UUID:
    run_id = uuid.uuid4()
    run_pipeline(db_engine, SAMPLE_DIR, "sample", run_id)
    return run_id


def test_raw_row_counts_match_source_files(db_engine: Engine, sample_run: uuid.UUID) -> None:
    expected = expected_counts(SAMPLE_DIR)
    with db_engine.connect() as conn:
        loaded: dict[str, int] = {}
        for table in RAW_TABLES.values():
            q = select(table.c.source_file, func.count()).group_by(table.c.source_file)
            loaded.update(dict(conn.execute(q).all()))
    assert loaded == expected
    assert len(expected) == 23  # 20 enrolment + 1 capacity + 2 boundary files


def test_every_step_is_logged_with_the_run_id(db_engine: Engine, sample_run: uuid.UUID) -> None:
    steps = _steps(db_engine, sample_run)
    assert set(steps) == {
        "load_enrolment",
        "load_capacity",
        "load_boundaries",
        "load_school_points",
        "verify_raw_counts",
    }
    for s in steps.values():
        assert s.status == "success"
        assert s.source == "sample"
        assert s.finished_at is not None and s.finished_at >= s.started_at
        assert s.rows_in == s.rows_out
    assert steps["load_school_points"].message == "optional source not present; table emptied"
    assert steps["load_school_points"].rows_out == 0


def test_raw_rows_carry_lineage(db_engine: Engine, sample_run: uuid.UUID) -> None:
    with db_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT total, source_file, source_row, run_id FROM raw.enrolment_school "
                "WHERE school_code = '4601' AND school_year = '2025-26'"
            )
        ).one()
    # Big Valley School (Clearview), 2025/26: total 86 in the published file.
    assert row.total == 86
    assert row.source_file == "ecc-school-enrolment-data-2025-2026.xlsx"
    assert row.source_row > 1
    assert row.run_id == sample_run


def test_geometries_are_valid_multipolygons_in_wgs84(
    db_engine: Engine, sample_run: uuid.UUID
) -> None:
    with db_engine.connect() as conn:
        r = conn.execute(
            text(
                "SELECT count(*) n, bool_and(ST_IsValid(geom)) valid, "
                "min(ST_SRID(geom)) srid, bool_and(GeometryType(geom) = 'MULTIPOLYGON') multi, "
                "count(*) FILTER (WHERE authority_code IS NULL) no_code "
                "FROM raw.authority_boundary"
            )
        ).one()
    assert r.n == 5  # 3 public + 2 separate sample authorities; code-less feature dropped
    assert (r.valid, r.srid, r.multi, r.no_code) == (True, 4326, True, 0)


def test_rerun_replaces_instead_of_appending(db_engine: Engine, sample_run: uuid.UUID) -> None:
    before = {t: _count(db_engine, t) for t in RAW_TABLES}
    second = uuid.uuid4()
    run_pipeline(db_engine, SAMPLE_DIR, "sample", second)
    after = {t: _count(db_engine, t) for t in RAW_TABLES}
    assert after == before
    with db_engine.connect() as conn:
        run_ids = conn.execute(text("SELECT DISTINCT run_id FROM raw.enrolment_school")).all()
    assert [r.run_id for r in run_ids] == [second]


def test_failed_step_is_logged_and_keeps_previous_load(
    db_engine: Engine, sample_run: uuid.UUID, tmp_path: Path
) -> None:
    broken = tmp_path / "sample"
    shutil.copytree(SAMPLE_DIR, broken)
    capacity_file = next((broken / "capacity").glob("*.xlsx"))
    capacity_file.write_bytes(b"this is not an Excel file")
    before = _count(db_engine, "capacity")

    run_id = uuid.uuid4()
    with pytest.raises(Exception):  # noqa: B017 - any read error must stop the run
        run_pipeline(db_engine, broken, "sample", run_id)

    steps = _steps(db_engine, run_id)
    assert steps["load_enrolment"].status == "success"
    assert steps["load_capacity"].status == "failed"
    assert steps["load_capacity"].message  # root cause recorded, not empty
    assert "verify_raw_counts" not in steps  # the run stopped at the failure
    assert _count(db_engine, "capacity") == before  # transaction rolled back


def test_health_reports_last_successful_run(
    db_url: str, sample_run: uuid.UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.session import get_engine

    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()
    get_engine.cache_clear()
    try:
        from app.main import app

        body = TestClient(app).get("/api/v1/health").json()
    finally:
        get_settings.cache_clear()
        get_engine.cache_clear()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["last_pipeline_run"] is not None
