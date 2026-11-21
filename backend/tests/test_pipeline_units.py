"""Unit tests for Phase 1 pieces that need no database."""

import json
from pathlib import Path

from openpyxl import Workbook

from pipeline.readers import read_boundaries, read_school_points
from pipeline.runlog import root_cause
from pipeline.verify import count_geojson_features, count_xlsx_rows

SQUARE = [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]
# A "bow tie": the ring crosses itself, which is invalid. The loader must repair it.
BOWTIE = [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]


def _geojson(path: Path, features: list[dict]) -> Path:
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return path


def _polygon(code: object, name: str, rings: list) -> dict:
    return {
        "type": "Feature",
        "properties": {"Code": code, "Name": name},
        "geometry": {"type": "Polygon", "coordinates": rings},
    }


def test_read_boundaries_repairs_invalid_and_drops_codeless(tmp_path: Path) -> None:
    path = _geojson(
        tmp_path / "public_authorities_2025.geojson",
        [
            _polygon("0052", "Clearview", SQUARE),
            _polygon("3020", "Edmonton", BOWTIE),
            _polygon(None, None, SQUARE),
        ],
    )
    gdf = read_boundaries(path)
    assert list(gdf.authority_code) == ["0052", "3020"]
    assert set(gdf.geom.geom_type) == {"MultiPolygon"}
    assert gdf.geom.is_valid.all()
    assert list(gdf.was_invalid) == [False, True]
    assert set(gdf.layer) == {"public"}
    assert set(gdf.boundary_year) == {2025}
    assert gdf.crs.to_epsg() == 4326


def test_read_school_points_drops_blank_school_numbers(tmp_path: Path) -> None:
    def point(number: str, name: str) -> dict:
        props = {"abed_school_number_t": number, "school_name": name, "grades": "K to Gr 6"}
        props |= {"school_type": "EL", "address": "1 Main St"}
        geom = {"type": "Point", "coordinates": [-113.5, 53.5]}
        return {"type": "Feature", "properties": props, "geometry": geom}

    # Real case: "Ellerslie Campus South" has a blank number (a campus, not a school).
    path = _geojson(
        tmp_path / "epsb_schools_2025.geojson",
        [point("1003", "Jackson Heights"), point(" ", "Ellerslie Campus South")],
    )
    gdf = read_school_points(path)
    assert list(gdf.school_code) == ["1003"]
    assert count_geojson_features(path, "abed_school_number_t") == 1


def test_count_xlsx_rows_counts_only_rows_with_a_number(tmp_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append([None])  # blank rows above the header, like the capacity file
    ws.append(["School Name", "Net Capacity"])
    ws.append(["A", 300])
    ws.append(["B", 250.0])
    ws.append([None, None])
    ws.append(["*Footnote text", None])
    path = tmp_path / "x.xlsx"
    wb.save(path)
    assert count_xlsx_rows(path) == 2


def test_root_cause_returns_innermost_error_first_line() -> None:
    try:
        try:
            raise ValueError('column "run_id" is of type uuid\nLINE 1: INSERT ...')
        except ValueError as inner:
            raise RuntimeError("Execution failed on sql 'INSERT INTO ... (10 KB)'") from inner
    except RuntimeError as outer:
        assert root_cause(outer) == 'ValueError: column "run_id" is of type uuid'
