"""Independent row-count check: source files vs raw tables.

The counts here deliberately do NOT use pipeline.readers. They read each file with
openpyxl or plain json and apply the simplest possible rule, so a bug in the readers
shows up as a mismatch instead of being repeated on both sides.

  Excel  : rows below the header whose key numeric cell ("Total" or "Net Capacity")
           holds a number. The footnote row and blank rows have none.
  GeoJSON: features whose code property is non-blank.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import openpyxl
from sqlalchemy import Connection, func, select

from app.db.models import RAW_TABLES

_KEY_HEADERS = {"total", "net capacity"}


class RowCountMismatch(RuntimeError):
    pass


def count_xlsx_rows(path: Path) -> int:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = wb.worksheets[0].iter_rows(values_only=True)
        key_col = None
        count = 0
        for row in rows:
            if key_col is None:
                for i, cell in enumerate(row):
                    if isinstance(cell, str) and cell.strip().lower() in _KEY_HEADERS:
                        key_col = i
                        break
                continue
            if key_col < len(row) and isinstance(row[key_col], int | float):
                count += 1
        if key_col is None:
            raise ValueError(f"{path.name}: no 'Total' or 'Net Capacity' header found")
        return count
    finally:
        wb.close()


def count_geojson_features(path: Path, code_property: str) -> int:
    features = json.loads(path.read_text(encoding="utf-8"))["features"]
    return sum(1 for f in features if str(f["properties"].get(code_property) or "").strip())


def expected_counts(source_dir: Path) -> dict[str, int]:
    """Source file name -> expected number of raw rows."""
    out: dict[str, int] = {}
    for sub in ("enrolment", "capacity"):
        for path in sorted((source_dir / sub).glob("*.xlsx")):
            out[path.name] = count_xlsx_rows(path)
    for path in sorted((source_dir / "boundaries").glob("*_authorities_*.geojson")):
        out[path.name] = count_geojson_features(path, "Code")
    for path in sorted((source_dir / "boundaries").glob("*_schools_*.geojson")):
        out[path.name] = count_geojson_features(path, "abed_school_number_t")
    return out


def loaded_counts(conn: Connection) -> dict[str, int]:
    out: dict[str, int] = {}
    for table in RAW_TABLES.values():
        stmt = select(table.c.source_file, func.count()).group_by(table.c.source_file)
        for source_file, n in conn.execute(stmt):
            out[source_file] = out.get(source_file, 0) + n
    return out


@dataclass
class VerifyResult:
    files: int
    expected_rows: int
    loaded_rows: int
    mismatches: dict[str, dict[str, int | None]]
    per_file: dict[str, dict[str, int | None]]


def verify_raw_counts(conn: Connection, source_dir: Path) -> VerifyResult:
    expected = expected_counts(source_dir)
    loaded = loaded_counts(conn)
    per_file = {
        name: {"source": expected.get(name), "loaded": loaded.get(name)}
        for name in sorted(set(expected) | set(loaded))
    }
    mismatches = {k: v for k, v in per_file.items() if v["source"] != v["loaded"]}
    result = VerifyResult(
        files=len(per_file),
        expected_rows=sum(expected.values()),
        loaded_rows=sum(loaded.values()),
        mismatches=mismatches,
        per_file=per_file,
    )
    if mismatches:
        raise RowCountMismatch(f"{len(mismatches)} file(s) do not match: {mismatches}")
    return result
