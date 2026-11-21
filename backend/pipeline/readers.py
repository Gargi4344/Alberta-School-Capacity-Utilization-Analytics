"""Read the raw Alberta Education workbooks into tidy, canonical DataFrames.

The published files drift between years (header spelling, camelCase headers in
2025/26, an optional "School Year" column, empty unnamed columns, codes stored as
text or numbers, a footnote row at the bottom). These readers absorb that drift
so later steps see one stable shape. See docs/source_mapping.md.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import make_valid
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from pipeline.download import parse_school_year

GRADE_COLUMNS = ["ungraded", "ecs", *[f"grade_{g}" for g in range(1, 13)]]

_HEADER_ALIASES = {
    "school_year_name": "school_year",
    "school_authority_category": "authority_category",
    "school_authority_name": "authority_name",
    "school_authority_code": "authority_code",
    "adj_total_enrol": "adj_total_enrolment",
    "utiliz": "utilization_rate",
}


def normalize_header(value: object) -> str:
    """'School Authority Code', 'SchoolAuthorityCode', 'School Name\\n' -> snake_case."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if text.lower().startswith("unnamed:"):
        return ""
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)  # camelCase -> words
    text = re.sub(r"[^0-9A-Za-z]+", "_", text).strip("_").lower()
    return _HEADER_ALIASES.get(text, text)


def normalize_code(value: object) -> str | None:
    """Codes appear as '0052', 52 or 52.0; return a 4-digit zero-padded string."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    if not text.isdigit():
        return None
    return text.zfill(4)


def normalize_name(value: object) -> str:
    """Matching key for names: ASCII, lower case, punctuation removed, 'St.' -> 'saint'."""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"\bste\.?\s", " sainte ", text)
    text = re.sub(r"\bst\.?\s", " saint ", text)
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _year_from_path(path: Path) -> str:
    year = parse_school_year(path.name)
    if year is None:
        raise ValueError(f"cannot find a school year in file name {path.name!r}")
    return year


def read_enrolment(path: Path) -> pd.DataFrame:
    """One row per school (or authority) for the school year in the file name."""
    df = pd.read_excel(path, dtype=object)
    df.columns = [normalize_header(c) for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c]]
    level = "school" if "school_code" in df.columns else "authority"
    df["source_row"] = df.index + 2  # Excel row number (header is row 1)

    # Drop the footnote row(s) ("*First Nation school level enrolment ...") and blanks.
    cat = df["authority_category"].astype("string").str.strip()
    df = df[cat.notna() & ~cat.str.startswith("*")].copy()

    year = _year_from_path(path)
    df["school_year"] = year  # the file name is authoritative; the column exists only 2022-24
    df["authority_code"] = df["authority_code"].map(normalize_code)
    for col in ("authority_category", "authority_name", "school_name"):
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()
    if level == "school":
        df["school_code"] = df["school_code"].map(normalize_code)

    for col in [*GRADE_COLUMNS, "total"]:
        if col not in df.columns:
            df[col] = 0  # 'ungraded' first appears in 2025/26
        df[col] = pd.to_numeric(df[col], errors="raise").fillna(0).astype("int64")

    keys = ["school_year", "authority_category", "authority_code", "authority_name"]
    if level == "school":
        keys += ["school_code", "school_name"]
    out = df[[*keys, *GRADE_COLUMNS, "total", "source_row"]].reset_index(drop=True)
    out.attrs["level"] = level
    return out


def read_capacity(path: Path) -> pd.DataFrame:
    """One row per school x facility, as published (no codes in the source)."""
    probe = pd.read_excel(path, header=None, nrows=15, dtype=object)
    header_row = next(
        i
        for i, row in probe.iterrows()
        if any(normalize_header(v) == "net_capacity" for v in row.tolist())
    )
    df = pd.read_excel(path, header=header_row, dtype=object)
    df.columns = [normalize_header(c) for c in df.columns]
    df["source_row"] = df.index + header_row + 2  # Excel row number
    df = df[pd.to_numeric(df["net_capacity"], errors="coerce").notna()].copy()
    for col in ("authority_name", "school_name", "facility_name", "facility_location"):
        df[col] = df[col].astype("string").str.strip()
    df["net_capacity"] = pd.to_numeric(df["net_capacity"]).astype("int64")
    df["adj_total_enrolment"] = pd.to_numeric(df["adj_total_enrolment"]).astype("float64")
    df["utilization_rate"] = pd.to_numeric(df["utilization_rate"]).astype("float64")
    df["school_year"] = _year_from_path(path)
    cols = [
        "school_year",
        "authority_name",
        "school_name",
        "facility_name",
        "facility_location",
        "net_capacity",
        "adj_total_enrolment",
        "utilization_rate",
        "source_row",
    ]
    return df[cols].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Geospatial sources
# ---------------------------------------------------------------------------


def _as_multipolygon(geom: BaseGeometry) -> MultiPolygon:
    """Repair invalid geometry and return it as a MultiPolygon (the column type)."""
    if not geom.is_valid:
        geom = make_valid(geom)
    if isinstance(geom, MultiPolygon):
        return geom
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    parts: list[Polygon] = []
    for part in getattr(geom, "geoms", []):  # GeometryCollection from make_valid
        if isinstance(part, Polygon):
            parts.append(part)
        elif isinstance(part, MultiPolygon):
            parts.extend(part.geoms)
    return MultiPolygon(parts)


def read_boundaries(path: Path) -> gpd.GeoDataFrame:
    """Authority polygons. Features without a Code (areas outside any authority) are dropped."""
    gdf = gpd.read_file(path)
    layer = "separate" if "separate" in path.stem else "public"
    year_match = re.search(r"(20\d{2})", path.stem)
    out = gpd.GeoDataFrame(
        {
            "authority_code": gdf["Code"].map(normalize_code),
            "authority_name": gdf["Name"].astype("string").str.strip(),
            "layer": layer,
            "boundary_year": int(year_match.group(1)) if year_match else None,
            "source_feature": range(len(gdf)),
            "was_invalid": (~gdf.geometry.is_valid).to_numpy(),
        },
        geometry=gdf.geometry.map(_as_multipolygon),
        crs=gdf.crs or "EPSG:4326",
    )
    out = out[out.authority_code.notna()].to_crs("EPSG:4326")
    return out.rename_geometry("geom").reset_index(drop=True)


def read_school_points(path: Path) -> gpd.GeoDataFrame:
    """Edmonton Public school points, keyed by the Alberta Education school number."""
    gdf = gpd.read_file(path)
    out = gpd.GeoDataFrame(
        {
            "school_code": gdf["abed_school_number_t"].map(normalize_code),
            "school_name": gdf["school_name"].astype("string").str.strip(),
            "grades": gdf["grades"].astype("string"),
            "school_type": gdf["school_type"].astype("string"),
            "address": gdf["address"].astype("string"),
            "source_feature": range(len(gdf)),
        },
        geometry=gdf.geometry,
        crs=gdf.crs or "EPSG:4326",
    )
    out = out[out.school_code.notna()].to_crs("EPSG:4326")
    return out.rename_geometry("geom").reset_index(drop=True)
