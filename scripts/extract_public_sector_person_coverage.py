#!/usr/bin/env python3
"""Build 2024 public-sector person-coverage diagnostics.

The observed National Personnel Authority and local-public-employee counts are
external workforce benchmarks. They are not the NTA withholding-table
"Public Offices" person denominator.
"""
from pathlib import Path
import argparse
import csv
import io
import re

from pypdf import PdfReader
from extract_nta_shinkoku_income_class_primary_type import Xlsx, integer_cell

ROOT = Path(__file__).resolve().parents[1]
NATIONAL_SUMMARY = ROOT / "data/raw/jinji_2024_national_public_staff_summary.csv"
NATIONAL_T1 = ROOT / "data/raw/jinji_2024_national_public_staff_by_pay_schedule_age.csv"
NATIONAL_SCOPE = ROOT / "data/raw/jinji_2024_national_public_salary_survey_results.pdf"
LOCAL_T1 = ROOT / "data/raw/estat/000040324410.xlsx"
LOCAL_META = ROOT / "data/raw/estat/estat_2024_local_public_salary_survey_metadata.html"
SOURCE_CATALOG = ROOT / "data/source_catalog.csv"
SOURCE_COVERAGE = ROOT / "data/derived/nta_salary_source_system_coverage_2024.csv"
OUT = ROOT / "data/derived/public_sector_person_coverage_audit_2024.csv"


def read_csv(path, encoding="utf-8"):
    with path.open(encoding=encoding, newline="") as f:
        return list(csv.reader(f))


def read_dicts(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def metric(metric_id, value, unit, population, source_ids, locator, status, note):
    return {
        "metric_id": metric_id,
        "value": value,
        "unit": unit,
        "population": population,
        "source_ids": source_ids,
        "source_locator": locator,
        "identification_status": status,
        "note": note,
    }


def pdf_text(path):
    return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)
def build():
    catalog = {r["source_id"]: r for r in read_dicts(SOURCE_CATALOG)}

    summary = read_csv(NATIONAL_SUMMARY, "cp932")
    t1 = read_csv(NATIONAL_T1, "cp932")
    national = int(summary[5][1])
    national_t1 = int(t1[4][2])
    if national != 250_434 or national_t1 != national:
        raise RuntimeError("National Personnel Authority 2024 person anchor changed")

    scope = re.sub(r"\s+", "", pdf_text(NATIONAL_SCOPE))
    required = [
        "令和６年４月１日現在の人員は250,434人",
        "給与法等の適用を受ける常勤職員",
        "新規採用者（11,110人）",
        "在外公館に勤務する職員",
        "休職者",
    ]
    for phrase in required:
        if re.sub(r"\s+", "", phrase) not in scope:
            raise RuntimeError(f"NPA scope anchor missing: {phrase}")

    meta = LOCAL_META.read_text(encoding="utf-8", errors="ignore")
    for phrase in ("令和６年地方公務員給与実態調査", "第１表", "職員数"):
        if phrase not in meta:
            raise RuntimeError(f"local-public metadata anchor missing: {phrase}")

    x = Xlsx(LOCAL_T1)
    try:
        rows = x.rows("(1)全地方公共団体")
        total = rows[40]
        core = rows[34]
        enterprise = rows[35]
        other_enterprise_and_other = rows[38]
        local_independent = rows[39]

        local_total = integer_cell(total["G"])
        local_regular = integer_cell(total["H"])
        local_general = integer_cell(total["I"])
        local_education = integer_cell(total["J"])
        local_police = integer_cell(total["K"])
        local_temporary = integer_cell(total["M"])

        if local_total != 2_813_939:
            raise RuntimeError("local public employee total anchor changed")
        if local_regular != 2_754_139 or local_temporary != 59_800:
            raise RuntimeError("local regular/temporary anchors changed")
        if local_total != local_regular + local_temporary:
            raise RuntimeError("local total != regular + temporary")
        if local_regular != local_general + local_education + local_police:
            raise RuntimeError("local regular component identity failed")
        if local_total != sum(integer_cell(r["G"]) for r in (
            core, enterprise, other_enterprise_and_other, local_independent
        )):
            raise RuntimeError("local functional subtotal identity failed")
    finally:
        x.close()

    coverage = {r["metric_id"]: r for r in read_dicts(SOURCE_COVERAGE)}
    nta_public_payment = int(coverage["source_salary_public_offices_payment"]["value"])
    nta_public_withholding = int(coverage["source_salary_public_offices_withholding"]["value"])
    if (nta_public_payment, nta_public_withholding) != (28_282_710, 917_029):
        raise RuntimeError("NTA Public Offices amount anchors changed")

    observed_external_subtotal = national + local_total
    assert observed_external_subtotal == 3_064_373
    rows = [
        metric(
            "national_public_salary_survey_covered_persons",
            national, "persons_exact",
            "2024 National Personnel Authority salary-survey covered employees",
            "JINJI-2024-PUBLIC-SALARY-SURVEY-SUMMARY;JINJI-2024-PUBLIC-SALARY-SURVEY-T1;JINJI-2024-PUBLIC-SALARY-SURVEY-RESULTS",
            "summary row All pay schedules; Table 1 total; results PDF p.1",
            "EXTERNAL_NATIONAL_PUBLIC_WORKFORCE_BENCHMARK",
            "Covered employees under specified national pay statutes as of 2024-04-01; exclusions mean this is not all national public-sector salary recipients.",
        ),
        metric(
            "local_public_employee_survey_total",
            local_total, "persons_exact",
            "2024 Local Public Employee Salary Survey, all local public bodies",
            "ESTAT-LOCAL-PUBLIC-SALARY-2024-T1;ESTAT-LOCAL-PUBLIC-SALARY-2024-METADATA",
            "(1)全地方公共団体!G40",
            "EXTERNAL_LOCAL_PUBLIC_WORKFORCE_BENCHMARK",
            "Survey-defined local public employee total; not asserted identical to NTA Public Offices salary recipients.",
        ),
        metric(
            "local_public_employee_regular_subtotal",
            local_regular, "persons_exact",
            "2024 Local Public Employee Salary Survey, all local public bodies",
            "ESTAT-LOCAL-PUBLIC-SALARY-2024-T1",
            "(1)全地方公共団体!H40",
            "EXTERNAL_LOCAL_PUBLIC_WORKFORCE_COMPONENT",
            "Regular-category subtotal c-e.",
        ),
        metric(
            "local_public_employee_general_staff",
            local_general, "persons_exact",
            "2024 Local Public Employee Salary Survey",
            "ESTAT-LOCAL-PUBLIC-SALARY-2024-T1",
            "(1)全地方公共団体!I40",
            "EXTERNAL_LOCAL_PUBLIC_WORKFORCE_COMPONENT",
            "General staff component.",
        ),
        metric(
            "local_public_employee_education",
            local_education, "persons_exact",
            "2024 Local Public Employee Salary Survey",
            "ESTAT-LOCAL-PUBLIC-SALARY-2024-T1",
            "(1)全地方公共団体!J40",
            "EXTERNAL_LOCAL_PUBLIC_WORKFORCE_COMPONENT",
            "Education public employee component.",
        ),
        metric(
            "local_public_employee_police",
            local_police, "persons_exact",
            "2024 Local Public Employee Salary Survey",
            "ESTAT-LOCAL-PUBLIC-SALARY-2024-T1",
            "(1)全地方公共団体!K40",
            "EXTERNAL_LOCAL_PUBLIC_WORKFORCE_COMPONENT",
            "Police component.",
        ),
        metric(
            "local_public_employee_temporary",
            local_temporary, "persons_exact",
            "2024 Local Public Employee Salary Survey",
            "ESTAT-LOCAL-PUBLIC-SALARY-2024-T1",
            "(1)全地方公共団体!M40",
            "EXTERNAL_LOCAL_PUBLIC_WORKFORCE_COMPONENT",
            "Temporary-staff component published separately from H regular subtotal.",
        ),
        metric(
            "observed_national_plus_local_public_workforce_subtotal",
            observed_external_subtotal, "persons_external_subtotal",
            "NPA covered national employees plus Local Public Employee Salary Survey total",
            "JINJI-2024-PUBLIC-SALARY-SURVEY-SUMMARY;ESTAT-LOCAL-PUBLIC-SALARY-2024-T1",
            "250,434 + 2,813,939",
            "EXTERNAL_PUBLIC_WORKFORCE_BENCHMARK_NOT_NTA_DENOMINATOR",
            "Arithmetic subtotal across two external workforce statistics; coverage definitions differ and do not reproduce the NTA Public Offices population.",
        ),
        metric(
            "nta_public_offices_salary_payment",
            nta_public_payment, "million_yen",
            "FY2024 NTA source-withholding Public Offices salary/wages/bonus",
            "NTA-FY2024-WITHHOLDING-STATUS",
            "Table (7) E19",
            "NTA_ADMINISTRATIVE_AMOUNT_NO_PERSON_DENOMINATOR",
            "Amount observed; corresponding person count is absent from the current NTA table.",
        ),
        metric(
            "nta_public_offices_salary_withholding",
            nta_public_withholding, "million_yen",
            "FY2024 NTA source-withholding Public Offices salary/wages/bonus",
            "NTA-FY2024-WITHHOLDING-STATUS",
            "Table (7) H19",
            "NTA_ADMINISTRATIVE_AMOUNT_NO_PERSON_DENOMINATOR",
            "Tax amount observed; corresponding person count is absent.",
        ),
        metric(
            "nta_public_offices_salary_person_count",
            "NOT_IDENTIFIED", "status",
            "FY2024 NTA source-withholding Public Offices salary recipients",
            "NTA-FY2024-WITHHOLDING-STATUS;JINJI-2024-PUBLIC-SALARY-SURVEY-RESULTS;ESTAT-LOCAL-PUBLIC-SALARY-2024-T1",
            "cross-source",
            "NTA_PUBLIC_OFFICES_PERSON_COUNT_NOT_IDENTIFIED",
            "External public-workforce counts do not share the NTA withholding-table population definition.",
        ),
        metric(
            "nta_public_offices_average_salary_using_external_subtotal",
            "PROHIBITED", "status",
            "NTA Public Offices payment divided by external national+local workforce subtotal",
            "NTA-FY2024-WITHHOLDING-STATUS;JINJI-2024-PUBLIC-SALARY-SURVEY-SUMMARY;ESTAT-LOCAL-PUBLIC-SALARY-2024-T1",
            "28,282,710 million yen / 3,064,373 external persons",
            "DO_NOT_DIVIDE_CROSS_FRAME_AMOUNT_BY_PERSON_SUBTOTAL",
            "Population frames do not match; the resulting quotient is not an identified average salary.",
        ),
        metric(
            "table7_gt20m_public_sector_person_adjustment",
            "PROHIBITED", "status",
            "Positive-balance Table 7 salary receipts >20m",
            "NTA-2024-SHINKOKU-T7-XLSX;JINJI-2024-PUBLIC-SALARY-SURVEY-SUMMARY;ESTAT-LOCAL-PUBLIC-SALARY-2024-T1",
            "cross-source",
            "NO_PUBLIC_SECTOR_HIGH_SALARY_CROSSTAB",
            "External public employee totals contain no compatible >20m salary-receipt x final-return-status cross-tab.",
        ),
    ]
    return rows
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    rows = build()
    expected = render(rows)
    if args.check:
        actual = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if actual != expected:
            raise SystemExit(f"stale generated artifact: {OUT.relative_to(ROOT)}")
        print(
            "public-sector person coverage audit: current "
            "(national covered=250,434; local total=2,813,939; external subtotal=3,064,373; "
            "NTA Public Offices person count not identified)"
        )
        return
    OUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} metrics")


if __name__ == "__main__":
    main()
