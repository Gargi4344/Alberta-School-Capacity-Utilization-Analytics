"""Reader tests use small workbooks that copy the real layout quirks of each era."""

from pathlib import Path

import pytest
from openpyxl import Workbook

from pipeline.readers import (
    normalize_code,
    normalize_header,
    normalize_name,
    read_capacity,
    read_enrolment,
)

FOOTNOTE = "*First Nation school level enrolment statistics have been removed from this report."
GRADES = ["Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5", "Grade 6", "Grade 7"]
GRADES += ["Grade 8", "Grade 9", "Grade 10", "Grade 11", "Grade 12"]


def _xlsx(path: Path, rows: list[list[object]]) -> Path:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("School Authority Code", "authority_code"),
        ("SchoolAuthorityCode", "authority_code"),
        ("School Name\n", "school_name"),
        ("School Year Name", "school_year"),
        ("Utiliz. %", "utilization_rate"),
        ("Adj Total Enrol", "adj_total_enrolment"),
        ("Grade 10", "grade_10"),
        (None, ""),
        ("Unnamed: 7", ""),
    ],
)
def test_normalize_header(raw: object, expected: str) -> None:
    assert normalize_header(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0052", "0052"), (52, "0052"), (52.0, "0052"), (" 3020 ", "3020"), (None, None), ("x", None)],
)
def test_normalize_code(raw: object, expected: str | None) -> None:
    assert normalize_code(raw) == expected


def test_normalize_name_matches_accents_and_saint() -> None:
    assert normalize_name("École St. Gerard") == normalize_name("Ecole Saint Gerard")
    assert normalize_name("  Big  Valley School ") == "big valley school"


def test_read_enrolment_2016_layout(tmp_path: Path) -> None:
    # 2016/17: codes as text with leading zeros, an empty unnamed column, blanks for 0.
    header = ["School Authority Category", "School Authority Name", "School Authority Code"]
    header += ["School Name\n", "School Code", "ECS", "Grade 1", None, *GRADES[1:], "Total"]
    row = ["Public", "Clearview School Division No. 71 ", "0052", "Botha School", "4602", 16, 8]
    row += [None, 7, 8, 5, 11, 8, None, None, None, None, None, None, 63]
    path = _xlsx(tmp_path / "edc-school-enrolment-data-2016-2017.xlsx", [header, row, [FOOTNOTE]])

    df = read_enrolment(path)
    assert df.attrs["level"] == "school"
    assert len(df) == 1  # footnote dropped
    rec = df.iloc[0]
    assert rec.school_year == "2016-17"
    assert rec.authority_code == "0052"
    assert rec.school_code == "4602"
    assert rec.authority_name == "Clearview School Division No. 71"
    assert rec.ungraded == 0  # column absent before 2025/26
    assert rec.grade_7 == 0  # blank -> 0
    assert rec.total == 63


def test_read_enrolment_2025_camel_case_and_numeric_codes(tmp_path: Path) -> None:
    header = ["SchoolAuthorityCategory", "SchoolAuthorityName", "SchoolAuthorityCode"]
    header += ["SchoolName", "SchoolCode", "Ungraded", "ECS", *GRADES, "Total"]
    row = ["Public", "The Clearview School Division", 52, "Lone Pine Colony School", 392, 1, 0]
    row += [0, 4, 2, 3, 1, 4, 2, 5, 0, 0, 0, 0, 22]
    path = _xlsx(tmp_path / "ecc-school-enrolment-data-2025-2026.xlsx", [header, row, [FOOTNOTE]])

    rec = read_enrolment(path).iloc[0]
    assert (rec.authority_code, rec.school_code, rec.school_year) == ("0052", "0392", "2025-26")
    assert rec.ungraded == 1


def test_read_enrolment_authority_level_with_school_year_column(tmp_path: Path) -> None:
    header = ["School Year", "School Authority Category", "School Authority Name"]
    header += ["School Authority Code", "ECS", *GRADES, "Total"]
    row = ["2022/2023", "Provincial", "Northern Lakes College ", "9240", *([None] * 13), 0]
    path = _xlsx(tmp_path / "educ-authority-enrolment-data-2022-2023.xlsx", [header, row])

    df = read_enrolment(path)
    assert df.attrs["level"] == "authority"
    assert "school_code" not in df.columns
    assert df.iloc[0].authority_name == "Northern Lakes College"
    assert df.iloc[0].school_year == "2022-23"


def test_read_capacity_finds_header_below_blank_rows(tmp_path: Path) -> None:
    header = ["School Authority Name", "School Name", "Facility Name", "Facility Location"]
    header += ["Net Capacity", "Adj Total Enrol", "Utiliz. %"]
    row = ["Aurora School Ltd.", "Aurora Primary", "AURORA ELEMENTARY", "EDMONTON", 858, 728, 0.85]
    path = _xlsx(
        tmp_path / "educ-school-capacity-2023-2024-school-year.xlsx",
        [[None], ["", "", ""], header, row, ["Source: Alberta Education"]],
    )
    df = read_capacity(path)
    assert len(df) == 1
    rec = df.iloc[0]
    assert rec.school_year == "2023-24"
    assert rec.net_capacity == 858
    assert rec.utilization_rate == pytest.approx(0.85)
