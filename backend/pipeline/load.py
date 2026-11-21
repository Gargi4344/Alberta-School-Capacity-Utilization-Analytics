"""Extract and load: source files -> raw schema.

Each loader fully replaces its tables inside one transaction (TRUNCATE + INSERT), so
a run is repeatable and a failed run leaves the previous load untouched.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
import pandas as pd
from sqlalchemy import Connection, func, select

from app.db.models import RAW_TABLES
from pipeline.readers import read_boundaries, read_capacity, read_enrolment, read_school_points


@dataclass
class LoadResult:
    rows_in: int = 0
    rows_out: int = 0
    per_file: dict[str, int] = field(default_factory=dict)
    notes: dict[str, int] = field(default_factory=dict)


def _with_lineage(df: pd.DataFrame, path: Path, run_id: uuid.UUID) -> pd.DataFrame:
    return df.assign(source_file=path.name, run_id=run_id)


def _truncate(conn: Connection, *tables: str) -> None:
    names = ", ".join(f"raw.{t}" for t in tables)
    conn.exec_driver_sql(f"TRUNCATE {names} RESTART IDENTITY")  # fixed names, no user input


def _count(conn: Connection, table: str) -> int:
    return conn.execute(select(func.count()).select_from(RAW_TABLES[table])).scalar_one()


def _dtypes(df: pd.DataFrame, table: str) -> dict:
    """Use the table's declared column types, so pandas never guesses (e.g. uuid as text)."""
    return {c.name: c.type for c in RAW_TABLES[table].columns if c.name in df.columns}


def _append(conn: Connection, df: pd.DataFrame, table: str) -> None:
    df.to_sql(
        table,
        conn,
        schema="raw",
        if_exists="append",
        index=False,
        method="multi",
        chunksize=500,
        dtype=_dtypes(df, table),
    )


def load_enrolment(conn: Connection, folder: Path, run_id: uuid.UUID) -> LoadResult:
    files = sorted(folder.glob("*.xlsx"))
    if not files:
        raise FileNotFoundError(f"no enrolment workbooks in {folder}")
    _truncate(conn, "enrolment_school", "enrolment_authority")
    res = LoadResult()
    for path in files:
        df = read_enrolment(path)
        table = "enrolment_school" if df.attrs["level"] == "school" else "enrolment_authority"
        _append(conn, _with_lineage(df, path, run_id), table)
        res.rows_in += len(df)
        res.per_file[path.name] = len(df)
    res.rows_out = _count(conn, "enrolment_school") + _count(conn, "enrolment_authority")
    return res


def load_capacity(conn: Connection, folder: Path, run_id: uuid.UUID) -> LoadResult:
    files = sorted(folder.glob("*.xlsx"))
    if not files:
        raise FileNotFoundError(f"no capacity workbooks in {folder}")
    _truncate(conn, "capacity")
    res = LoadResult()
    for path in files:
        df = read_capacity(path)
        _append(conn, _with_lineage(df, path, run_id), "capacity")
        res.rows_in += len(df)
        res.per_file[path.name] = len(df)
    res.rows_out = _count(conn, "capacity")
    return res


def _append_geo(conn: Connection, gdf: gpd.GeoDataFrame, table: str) -> None:
    gdf.to_postgis(
        table, conn, schema="raw", if_exists="append", index=False, dtype=_dtypes(gdf, table)
    )


def load_boundaries(conn: Connection, folder: Path, run_id: uuid.UUID) -> LoadResult:
    files = sorted(folder.glob("*_authorities_*.geojson"))
    if not files:
        raise FileNotFoundError(f"no authority boundary files in {folder}")
    _truncate(conn, "authority_boundary")
    res = LoadResult()
    repaired = 0
    for path in files:
        gdf = read_boundaries(path)
        _append_geo(conn, _with_lineage(gdf, path, run_id), "authority_boundary")
        res.rows_in += len(gdf)
        res.per_file[path.name] = len(gdf)
        repaired += int(gdf.was_invalid.sum())
    res.rows_out = _count(conn, "authority_boundary")
    res.notes["invalid_geometries_repaired"] = repaired
    return res


def load_school_points(conn: Connection, folder: Path, run_id: uuid.UUID) -> LoadResult:
    _truncate(conn, "school_point")
    res = LoadResult()
    for path in sorted(folder.glob("*_schools_*.geojson")):
        gdf = read_school_points(path)
        _append_geo(conn, _with_lineage(gdf, path, run_id), "school_point")
        res.rows_in += len(gdf)
        res.per_file[path.name] = len(gdf)
    res.rows_out = _count(conn, "school_point")
    return res
