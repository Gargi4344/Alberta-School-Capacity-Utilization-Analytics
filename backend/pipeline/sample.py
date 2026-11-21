"""Build data/sample/: a small, real subset of data/raw/ for CI and offline demos.

Rows are copied cell by cell, so the sample keeps every layout quirk of the real
files (headers, blank rows, footnotes, text vs number codes). Only the chosen
authorities are kept. Boundary polygons are simplified to keep the files small.

Only Open Government Licence - Alberta files are sampled. The optional Edmonton
Public Schools points have their own terms, so they are not copied into the repo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import openpyxl
from shapely.geometry import mapping, shape

from pipeline.download import load_sources
from pipeline.readers import normalize_code, normalize_header, normalize_name

SIMPLIFY_DEGREES = 0.002  # about 150-200 m: plenty for an authority choropleth


def _copy_rows(src: Path, dest: Path, keep: Any) -> int:
    """Copy rows of the first sheet for which keep(header, row) is true; return data rows."""
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    out = openpyxl.Workbook()
    ws_out = out.active
    ws_out.title = wb.sheetnames[0]
    header: list[str] | None = None
    kept = 0
    for row in wb.worksheets[0].iter_rows(values_only=True):
        if header is None:
            ws_out.append(list(row))
            normalized = [normalize_header(c) for c in row]
            if {"authority_code", "net_capacity"} & set(normalized):
                header = normalized
            continue
        first = row[0] if row else None
        if isinstance(first, str) and first.startswith("*"):  # footnote: keep it
            ws_out.append(list(row))
        elif keep(header, row):
            ws_out.append(list(row))
            kept += 1
    wb.close()
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest)
    return kept


def _filter_geojson(src: Path, dest: Path, keep: Any, simplify: bool) -> int:
    fc = json.loads(src.read_text(encoding="utf-8"))
    feats = []
    for f in fc["features"]:
        if not keep(f["properties"]):
            continue
        if simplify and f.get("geometry"):
            geom = shape(f["geometry"]).simplify(SIMPLIFY_DEGREES, preserve_topology=True)
            f = {**f, "geometry": json.loads(json.dumps(mapping(geom)))}
        feats.append(f)
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":"))
    dest.write_text(text, encoding="utf-8")
    return len(feats)


class _BoundaryFilter:
    """Keep the sample authorities, plus one feature without a code so the loader's
    "drop features without a code" rule is exercised by the sample too."""

    def __init__(self, codes: set[str | None]) -> None:
        self.codes = codes
        self.kept_codeless = False

    def __call__(self, props: dict[str, Any]) -> bool:
        if normalize_code(props.get("Code")) in self.codes:
            return True
        if props.get("Code") is None and not self.kept_codeless:
            self.kept_codeless = True
            return True
        return False


def build_sample(raw_dir: Path, sample_dir: Path) -> dict[str, int]:
    codes = {normalize_code(c) for c in load_sources()["sample_authorities"]}
    names: set[str] = set()  # capacity has no codes: collect every name these codes used
    written: dict[str, int] = {}

    def keep_enrolment(header: list[str], row: tuple) -> bool:
        i = header.index("authority_code")
        if i < len(row) and normalize_code(row[i]) in codes:
            names.add(normalize_name(row[header.index("authority_name")]))
            return True
        return False

    for src in sorted((raw_dir / "enrolment").glob("*.xlsx")):
        written[src.name] = _copy_rows(src, sample_dir / "enrolment" / src.name, keep_enrolment)

    def keep_capacity(header: list[str], row: tuple) -> bool:
        i = header.index("authority_name")
        return i < len(row) and row[i] is not None and normalize_name(row[i]) in names

    for src in sorted((raw_dir / "capacity").glob("*.xlsx")):
        written[src.name] = _copy_rows(src, sample_dir / "capacity" / src.name, keep_capacity)

    for src in sorted((raw_dir / "boundaries").glob("*_authorities_*.geojson")):
        written[src.name] = _filter_geojson(
            src, sample_dir / "boundaries" / src.name, _BoundaryFilter(codes), simplify=True
        )
    return written
