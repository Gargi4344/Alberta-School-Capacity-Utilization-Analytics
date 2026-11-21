from urllib.parse import parse_qs, urlparse

import pytest

from pipeline.download import arcgis_query_url, parse_school_year, select_resources


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2025/2026 student enrolment by school and grade level", "2025-26"),
        ("ecc-school-enrolment-data-2016-2017.xlsx", "2016-17"),
        ("educ-school-capacity-2023-2024-school-year.xlsx", "2023-24"),
        ("2019-20", "2019-20"),
        ("1999 to 2004", None),
        ("2021-2023", None),  # not consecutive years
    ],
)
def test_parse_school_year(text: str, expected: str | None) -> None:
    assert parse_school_year(text) == expected


def test_select_resources_filters_format_and_sorts_by_year() -> None:
    package = {
        "resources": [
            {
                "name": "2025/2026 student enrolment by school and grade level",
                "format": "XLSX",
                "url": "https://example.org/download/ecc-school-enrolment-data-2025-2026.xlsx",
            },
            {"name": "Data dictionary", "format": "PDF", "url": "https://example.org/a.pdf"},
            {
                "name": "2016/2017 student enrolment by school and grade level",
                "format": "xlsx",
                "url": "https://example.org/download/edc-school-enrolment-data-2016-2017.xlsx",
            },
            {"name": "broken", "format": "XLSX", "url": ""},
        ]
    }
    res = select_resources(package, "enrolment", ["XLSX"])
    assert [r.school_year for r in res] == ["2016-17", "2025-26"]
    assert res[0].filename == "edc-school-enrolment-data-2016-2017.xlsx"
    assert all(r.key == "enrolment" for r in res)


def test_arcgis_query_url_requests_wgs84_geojson_with_paging() -> None:
    url = arcgis_query_url("https://example.org/MapServer/3/", offset=1000)
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    assert parsed.path.endswith("/MapServer/3/query")
    assert q["outSR"] == ["4326"]
    assert q["f"] == ["geojson"]
    assert q["where"] == ["1=1"]
    assert q["resultOffset"] == ["1000"]
