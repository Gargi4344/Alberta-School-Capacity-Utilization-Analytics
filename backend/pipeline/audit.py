"""Source audit: the facts behind docs/source_mapping.md, recomputed from data/raw/.

Run with `uv run abcap audit`. Every number in the source mapping document comes
from this report, so the document can be re-checked when new files are published.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline.readers import normalize_code, normalize_name, read_capacity, read_enrolment


def _enrolment_frames(raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    files = sorted((raw_dir / "enrolment").glob("*.xlsx"))
    schools, authorities = [], []
    for path in files:
        df = read_enrolment(path)
        (schools if df.attrs["level"] == "school" else authorities).append(df)
    return pd.concat(schools, ignore_index=True), pd.concat(authorities, ignore_index=True)


def _geo_codes(path: Path) -> dict[str, Any]:
    features = json.loads(path.read_text(encoding="utf-8"))["features"]
    codes = [normalize_code(f["properties"].get("Code")) for f in features]
    return {
        "features": len(features),
        "features_without_code": sum(c is None for c in codes),
        "codes": sorted({c for c in codes if c}),
        "geometry_types": dict(Counter(f["geometry"]["type"] for f in features)),
    }


def audit(raw_dir: Path) -> dict[str, Any]:
    schools, auths = _enrolment_frames(raw_dir)
    report: dict[str, Any] = {"enrolment": {}, "capacity": {}, "boundaries": {}}

    # --- Enrolment: per-year shape and reconciliation school files vs authority files
    years = []
    for year, s in schools.groupby("school_year"):
        a = auths[auths.school_year == year]
        from_schools = s.groupby("authority_code")["total"].sum()
        from_auth = a.set_index("authority_code")["total"]
        joined = pd.concat([from_schools, from_auth], axis=1, keys=["s", "a"]).fillna(-1)
        years.append(
            {
                "school_year": year,
                "schools": len(s),
                "authorities": int(a.authority_code.nunique()),
                "provincial_total": int(s.total.sum()),
                "authority_file_total": int(a.total.sum()),
                "authorities_not_reconciling": int((joined.s != joined.a).sum()),
                "duplicate_school_codes": int(s.school_code.duplicated().sum()),
                "categories": s.authority_category.value_counts().to_dict(),
                "grade_sum_mismatches": int((s[[*_grades(s)]].sum(axis=1) != s.total).sum()),
            }
        )
    report["enrolment"]["years"] = years

    per_school = schools.groupby("school_code").agg(
        years=("school_year", "nunique"),
        names=("school_name", "nunique"),
        authorities=("authority_code", "nunique"),
    )
    n_years = schools.school_year.nunique()
    report["enrolment"]["school_codes"] = {
        "distinct": len(per_school),
        "in_every_year": int((per_school.years == n_years).sum()),
        "with_6_plus_years": int((per_school.years >= 6).sum()),
        "renamed": int((per_school.names > 1).sum()),
        "moved_authority": int((per_school.authorities > 1).sum()),
    }
    per_auth = auths.groupby("authority_code").authority_name.nunique()
    report["enrolment"]["authority_codes"] = {
        "distinct": int(per_auth.size),
        "renamed": int((per_auth > 1).sum()),
    }

    # --- Capacity: name-based join to enrolment for the same school year
    for path in sorted((raw_dir / "capacity").glob("*.xlsx")):
        cap = read_capacity(path)
        year = cap.school_year.iloc[0]
        enr = schools[schools.school_year == year]
        auth_lookup = (
            enr.drop_duplicates("authority_code")
            .assign(k=lambda d: d.authority_name.map(normalize_name))
            .set_index("k")["authority_code"]
        )
        cap["authority_code"] = cap.authority_name.map(normalize_name).map(auth_lookup)
        enr_keys = enr.assign(k=enr.school_name.map(normalize_name))
        key_counts = enr_keys.groupby(["authority_code", "k"]).size()
        cap["k"] = cap.school_name.map(normalize_name)
        matched = [
            key_counts.get((a, k), 0) == 1 for a, k in zip(cap.authority_code, cap.k, strict=True)
        ]
        cap["school_matched"] = matched
        calc = (cap.adj_total_enrolment / cap.net_capacity).round(2)
        report["capacity"][year] = {
            "file": path.name,
            "rows": len(cap),
            "authorities": int(cap.authority_name.nunique()),
            "authorities_matched": int(
                cap.drop_duplicates("authority_name").authority_code.notna().sum()
            ),
            "rows_school_matched": int(cap.school_matched.sum()),
            "unmatched": cap.loc[~cap.school_matched, ["authority_name", "school_name"]].to_dict(
                "records"
            ),
            "schools_with_multiple_facilities": int(
                (cap.groupby(["authority_name", "school_name"]).size() > 1).sum()
            ),
            "facilities_shared_by_schools": int(
                (cap.groupby(["authority_name", "facility_name"]).size() > 1).sum()
            ),
            "utilization_equals_adj_over_net": bool(
                ((calc - cap.utilization_rate).abs() <= 0.011).all()
            ),
            "utilization_min": float(cap.utilization_rate.min()),
            "utilization_max": float(cap.utilization_rate.max()),
            "enrolment_schools_in_matched_authorities": int(
                enr.authority_code.isin(set(cap.authority_code.dropna())).sum()
            ),
            "categories_covered": enr[enr.authority_code.isin(set(cap.authority_code.dropna()))]
            .drop_duplicates("authority_code")
            .authority_category.value_counts()
            .to_dict(),
        }

    # --- Boundaries: authority codes on polygons vs latest enrolment year
    latest = auths[auths.school_year == auths.school_year.max()]
    for path in sorted((raw_dir / "boundaries").glob("*_authorities_*.geojson")):
        info = _geo_codes(path)
        codes = set(info.pop("codes"))
        info["codes_matched_to_enrolment"] = len(codes & set(latest.authority_code))
        info["distinct_codes"] = len(codes)
        report["boundaries"][path.stem] = info
    polygon_codes = set()
    for path in (raw_dir / "boundaries").glob("*_authorities_*.geojson"):
        polygon_codes |= {
            normalize_code(f["properties"].get("Code"))
            for f in json.loads(path.read_text(encoding="utf-8"))["features"]
        }
    report["boundaries"]["coverage_by_category"] = {
        cat: {
            "authorities": len(g),
            "with_polygon": int(g.authority_code.isin(polygon_codes).sum()),
        }
        for cat, g in latest.groupby("authority_category")
    }

    epsb = raw_dir / "boundaries" / "epsb_schools_2025.geojson"
    if epsb.exists():
        feats = json.loads(epsb.read_text(encoding="utf-8"))["features"]
        codes = {normalize_code(f["properties"].get("abed_school_number_t")) for f in feats}
        latest_s = schools[schools.school_year == schools.school_year.max()]
        epsb_s = latest_s[latest_s.authority_code == "3020"]
        report["boundaries"]["epsb_points"] = {
            "features": len(feats),
            "epsb_schools_in_latest_enrolment": len(epsb_s),
            "epsb_schools_with_point": int(epsb_s.school_code.isin(codes).sum()),
        }
    return report


def _grades(df: pd.DataFrame) -> list[str]:
    from pipeline.readers import GRADE_COLUMNS

    return [c for c in GRADE_COLUMNS if c in df.columns]
