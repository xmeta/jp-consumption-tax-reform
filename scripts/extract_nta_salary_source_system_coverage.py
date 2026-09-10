#!/usr/bin/env python3
"""Audit salary-source-system monetary coverage against the Private Salary Survey.

The output is deliberately a monetary coverage diagnostic.  It must not be
used to infer person shares, private/public person overlap, or to adjust
return-side person counts.
"""
from pathlib import Path
import argparse
import csv
import io
import re

from extract_nta_shinkoku_income_class_primary_type import Xlsx, integer_cell

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/nta/nta_fy2024_withholding_income_tax_status.xlsx"
MINKAN_T1 = ROOT / "data/raw/nta/nta_minkan2024_table1_salary_persons_amount_tax.xlsx"
METHODOLOGY = ROOT / "data/raw/nta/nta_private_salary_survey_methodology.html"
CATALOG = ROOT / "data/source_catalog.csv"
OUT = ROOT / "data/derived/nta_salary_source_system_coverage_2024.csv"

SOURCE_SHEET = "(6)(7)特定口座内上場株式等の譲渡所得、給与退職所得"


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def fmt_ratio(x):
    return f"{x:.12f}".rstrip("0").rstrip(".")


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
def check_methodology():
    text = METHODOLOGY.read_bytes().decode("shift_jis", errors="replace")
    anchors = [
        "各年12月31日現在の源泉徴収義務者（民間の事業所に限る）に勤務している給与所得者",
        "標本の抽出は、標本事業所の抽出及び標本給与所得者の抽出の2段階",
        "年間給与額が2,000万円を超える者は、全数を抽出した",
    ]
    for anchor in anchors:
        if anchor not in text:
            raise RuntimeError(f"Private Salary Survey methodology anchor missing: {anchor}")


def build():
    catalog = {r["source_id"]: r for r in read_csv(CATALOG)}
    src = catalog["NTA-FY2024-WITHHOLDING-STATUS"]
    m1src = catalog["NTA-MINKAN-2024-T1"]
    meth = catalog["NTA-MINKAN-METHODOLOGY"]
    check_methodology()

    x = Xlsx(SOURCE)
    try:
        rows = x.rows(SOURCE_SHEET)
        salary = rows[19]
        day = rows[20]
        total = rows[21]

        public_pay = integer_cell(salary.get("E"))
        public_tax = integer_cell(salary.get("H"))
        other_pay = integer_cell(salary.get("J"))
        other_tax = integer_cell(salary.get("M"))
        total_pay = integer_cell(salary.get("P"))
        total_tax = integer_cell(salary.get("T"))

        day_public_pay = integer_cell(day.get("E"))
        day_public_tax = integer_cell(day.get("H"))
        day_other_pay = integer_cell(day.get("J"))
        day_other_tax = integer_cell(day.get("M"))
        day_total_pay = integer_cell(day.get("P"))
        day_total_tax = integer_cell(day.get("T"))

        source_total_pay_with_day = integer_cell(total.get("P"))
        source_total_tax_with_day = integer_cell(total.get("T"))

        if public_pay + other_pay != total_pay:
            raise RuntimeError("source salary payment public+other identity failed")
        if public_tax + other_tax != total_tax:
            raise RuntimeError("source salary tax public+other identity failed")
        if abs((day_public_pay + day_other_pay) - day_total_pay) > 1:
            raise RuntimeError("source day-labor payment public+other residual exceeds 1 million yen")
        if day_public_tax + day_other_tax != day_total_tax:
            raise RuntimeError("source day-labor tax public+other identity failed")
        if abs((total_pay + day_total_pay) - source_total_pay_with_day) > 1:
            raise RuntimeError("source salary+day-labor payment total residual exceeds 1 million yen")
        if total_tax + day_total_tax != source_total_tax_with_day:
            raise RuntimeError("source salary+day-labor tax total identity failed")

        note_text = str(rows[30].get("A", ""))
        if "Public Offices" not in note_text or "government organizations" not in note_text:
            raise RuntimeError("source Public Offices definition anchor missing")
    finally:
        x.close()
    x = Xlsx(MINKAN_T1)
    try:
        rows = x.rows("その１")
        current = rows[24]
        history = rows[12]
        private_avg_monthly_persons = integer_cell(current.get("J"))
        private_salary = integer_cell(current.get("K"))
        private_tax = integer_cell(current.get("M"))
        if private_salary != integer_cell(history.get("K")):
            raise RuntimeError("Private Salary Survey Table 1 current/history salary mismatch")
        if private_tax != integer_cell(history.get("M")):
            raise RuntimeError("Private Salary Survey Table 1 current/history tax mismatch")
        if private_avg_monthly_persons != 60_184_788:
            raise RuntimeError("Private Salary Survey average-monthly person anchor changed")
    finally:
        x.close()

    public_pay_share = public_pay / total_pay
    public_tax_share = public_tax / total_tax
    private_to_other_pay = private_salary / other_pay
    private_to_other_tax = private_tax / other_tax

    if not ((public_pay, other_pay, total_pay) == (28282710, 325610351, 353893061)):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_source_system_coverage.py:137')
    if not ((public_tax, other_tax, total_tax) == (917029, 11021742, 11938771)):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_source_system_coverage.py:138')
    if not ((day_total_pay, day_total_tax) == (1232032, 20909)):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_source_system_coverage.py:139')
    if not ((private_salary, private_tax) == (241438813, 11183370)):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_source_system_coverage.py:140')

    metrics = [
        metric(
            "source_salary_public_offices_payment",
            public_pay, "million_yen",
            "FY2024 source-withholding salary/wages/bonus payments classified as Public Offices",
            "NTA-FY2024-WITHHOLDING-STATUS",
            f"{SOURCE_SHEET}!E19",
            "ADMINISTRATIVE_AMOUNT_PUBLIC_OFFICES",
            "Payment amount only; no person count is published in this table.",
        ),
        metric(
            "source_salary_other_payment",
            other_pay, "million_yen",
            "FY2024 source-withholding salary/wages/bonus payments classified as Others",
            "NTA-FY2024-WITHHOLDING-STATUS",
            f"{SOURCE_SHEET}!J19",
            "ADMINISTRATIVE_AMOUNT_OTHER",
            "Others is the complement of Public Offices in this source table; it is not asserted identical to the Private Salary Survey target.",
        ),
        metric(
            "source_salary_total_payment",
            total_pay, "million_yen",
            "FY2024 source-withholding salary/wages/bonus payments",
            "NTA-FY2024-WITHHOLDING-STATUS",
            f"{SOURCE_SHEET}!P19",
            "ADMINISTRATIVE_AMOUNT_TOTAL",
            "Public Offices plus Others.",
        ),
        metric(
            "source_salary_public_offices_withholding",
            public_tax, "million_yen",
            "FY2024 source withholding on salary/wages/bonus classified as Public Offices",
            "NTA-FY2024-WITHHOLDING-STATUS",
            f"{SOURCE_SHEET}!H19",
            "ADMINISTRATIVE_TAX_AMOUNT_PUBLIC_OFFICES",
            "Withholding tax amount only; no person count.",
        ),
        metric(
            "source_salary_other_withholding",
            other_tax, "million_yen",
            "FY2024 source withholding on salary/wages/bonus classified as Others",
            "NTA-FY2024-WITHHOLDING-STATUS",
            f"{SOURCE_SHEET}!M19",
            "ADMINISTRATIVE_TAX_AMOUNT_OTHER",
            "Do not equate Others to the Private Salary Survey population.",
        ),
        metric(
            "source_salary_total_withholding",
            total_tax, "million_yen",
            "FY2024 source withholding on salary/wages/bonus",
            "NTA-FY2024-WITHHOLDING-STATUS",
            f"{SOURCE_SHEET}!T19",
            "ADMINISTRATIVE_TAX_AMOUNT_TOTAL",
            "Public Offices plus Others.",
        ),
        metric(
            "source_day_labor_total_payment",
            day_total_pay, "million_yen",
            "FY2024 source-system wages of day laborers",
            "NTA-FY2024-WITHHOLDING-STATUS",
            f"{SOURCE_SHEET}!P20",
            "ADMINISTRATIVE_AMOUNT_SEPARATE_ROW",
            "Published separately from salary/wages/bonus in the source-withholding table.",
        ),
        metric(
            "source_day_labor_total_withholding",
            day_total_tax, "million_yen",
            "FY2024 source-system withholding on wages of day laborers",
            "NTA-FY2024-WITHHOLDING-STATUS",
            f"{SOURCE_SHEET}!T20",
            "ADMINISTRATIVE_TAX_AMOUNT_SEPARATE_ROW",
            "Published separately from salary/wages/bonus.",
        ),
        metric(
            "private_salary_survey_average_monthly_salary_earners",
            private_avg_monthly_persons, "persons_estimated_average_monthly",
            "Private Salary Survey 2024",
            "NTA-MINKAN-2024-T1;NTA-MINKAN-METHODOLOGY",
            "Table 1!J24; methodology target",
            "SURVEY_STOCK_AVERAGE_NOT_ANNUAL_UNIQUE_PERSON_COUNT",
            "Average-monthly survey estimate; do not compare as a distinct-person union with filed-or-processed income-tax persons.",
        ),
        metric(
            "private_salary_survey_salary_amount",
            private_salary, "million_yen_estimated",
            "Private Salary Survey 2024 target",
            "NTA-MINKAN-2024-T1;NTA-MINKAN-METHODOLOGY",
            "Table 1!K24",
            "PRIVATE_SALARY_SURVEY_AMOUNT",
            "Survey estimate for its own private-employer year-end target and aggregation design.",
        ),
        metric(
            "private_salary_survey_tax_amount",
            private_tax, "million_yen_estimated",
            "Private Salary Survey 2024 target",
            "NTA-MINKAN-2024-T1;NTA-MINKAN-METHODOLOGY",
            "Table 1!M24",
            "PRIVATE_SALARY_SURVEY_TAX_AMOUNT",
            "Survey estimate under Private Salary Survey definitions.",
        ),
        metric(
            "source_public_offices_payment_share",
            fmt_ratio(public_pay_share), "amount_ratio",
            "FY2024 source-system salary/wages/bonus payment amount",
            "NTA-FY2024-WITHHOLDING-STATUS",
            "E19/P19",
            "AMOUNT_SHARE_NOT_PERSON_SHARE",
            "Public Offices payment share; must not be used as a public-employee person share or as a Table 7 correction factor.",
        ),
        metric(
            "source_public_offices_withholding_share",
            fmt_ratio(public_tax_share), "amount_ratio",
            "FY2024 source-system salary/wages/bonus withholding amount",
            "NTA-FY2024-WITHHOLDING-STATUS",
            "H19/T19",
            "AMOUNT_SHARE_NOT_PERSON_SHARE",
            "Public Offices tax-amount share; not a person share.",
        ),
        metric(
            "private_salary_to_source_other_payment_ratio",
            fmt_ratio(private_to_other_pay), "descriptive_amount_ratio",
            "Cross-statistic comparison",
            "NTA-MINKAN-2024-T1;NTA-FY2024-WITHHOLDING-STATUS;NTA-MINKAN-METHODOLOGY",
            "Private Table 1 K24 / source Others J19",
            "CROSS_STATISTIC_RATIO_NOT_COVERAGE_RATE",
            "Different survey frames and aggregation designs; not an identified coverage or inclusion probability.",
        ),
        metric(
            "private_salary_to_source_other_tax_ratio",
            fmt_ratio(private_to_other_tax), "descriptive_amount_ratio",
            "Cross-statistic comparison",
            "NTA-MINKAN-2024-T1;NTA-FY2024-WITHHOLDING-STATUS;NTA-MINKAN-METHODOLOGY",
            "Private Table 1 M24 / source Others M19",
            "CROSS_STATISTIC_RATIO_NOT_SUBSET_RATE",
            "Ratio exceeds one, directly warning against treating the two published aggregates as nested subsets.",
        ),
        metric(
            "source_other_minus_private_salary_payment",
            other_pay - private_salary, "million_yen_difference",
            "Cross-statistic comparison",
            "NTA-MINKAN-2024-T1;NTA-FY2024-WITHHOLDING-STATUS",
            "source Others J19 - Private Table 1 K24",
            "DIFFERENCE_NOT_MISSING_PRIVATE_PAYROLL",
            "Do not interpret this difference as missing private salary, missing persons, or an overlap residual.",
        ),
        metric(
            "source_total_minus_private_salary_payment",
            total_pay - private_salary, "million_yen_difference",
            "Cross-statistic comparison",
            "NTA-MINKAN-2024-T1;NTA-FY2024-WITHHOLDING-STATUS",
            "source Total P19 - Private Table 1 K24",
            "DIFFERENCE_NOT_MISSING_PRIVATE_PAYROLL",
            "Includes public-office coverage and other cross-statistic frame differences.",
        ),
        metric(
            "source_other_minus_private_salary_tax",
            other_tax - private_tax, "million_yen_difference",
            "Cross-statistic comparison",
            "NTA-MINKAN-2024-T1;NTA-FY2024-WITHHOLDING-STATUS",
            "source Others M19 - Private Table 1 M24",
            "NEGATIVE_DIFFERENCE_PROVES_NON_NESTED_PUBLISHED_AGGREGATES",
            "Negative published difference is incompatible with a naive nested-subset reading.",
        ),
        metric(
            "public_offices_salary_person_share",
            "NOT_IDENTIFIED", "status",
            "Public Offices versus other salary recipients",
            "NTA-FY2024-WITHHOLDING-STATUS",
            "Table (7)",
            "NO_PERSON_COUNT_IN_SOURCE_TABLE",
            "Payment and withholding amounts do not identify the corresponding person share.",
        ),
        metric(
            "table7_gt20m_private_sector_adjustment_from_public_amount_share",
            "PROHIBITED", "status",
            "Positive-balance Table 7 >20m salary-receipt persons",
            "NTA-FY2024-WITHHOLDING-STATUS;NTA-2024-SHINKOKU-T7-XLSX",
            "cross-source",
            "DO_NOT_APPLY_AMOUNT_SHARE_TO_PERSON_COUNT",
            "The public-office amount share cannot be used to adjust the 235,287 Table 7 person estimate.",
        ),
    ]
    return metrics
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
            "NTA salary source-system coverage diagnostic: current "
            "(public salary payment share=7.991880%; private/source-other payment ratio=74.149612%; "
            "no person-share inference)"
        )
        return
    OUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} metrics")


if __name__ == "__main__":
    main()
