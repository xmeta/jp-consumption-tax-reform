#!/usr/bin/env python3
"""Build the 2024 salary-receipt to final-return bridge diagnostic.

This audit combines:
- NTA Sample Survey Table 7 salary-receipt classes within the
  positive-self-assessed-balance target;
- NTA annual complete-survey Table 2-3 employment-income persons; and
- the existing Private Salary Survey Table 19 / Table 2-2(1) bridge artifacts.

It does not identify a person-level intersection between payroll and returns.
"""
from pathlib import Path
import argparse
import csv
import io
import re

from pypdf import PdfReader
from extract_nta_shinkoku_income_class_primary_type import Xlsx, integer_cell

ROOT = Path(__file__).resolve().parents[1]
T7 = ROOT / "data/raw/nta/nta_2024_shinkoku_sample_table7_salary_receipts.xlsx"
T23 = ROOT / "data/raw/nta/nta_2024_annual_income_type_persons_amounts.pdf"
NOTES = ROOT / "data/raw/nta/nta_2024_annual_self_assessment_table_notes.pdf"
CATALOG = ROOT / "data/source_catalog.csv"
T19_AUDIT = ROOT / "data/derived/nta_salary_return_overlap_audit_2024.csv"
T22 = ROOT / "data/derived/nta_income_class_primary_type_filing_status_2024.csv"
OUT_CLASS = ROOT / "data/derived/nta_positive_balance_salary_receipt_class_2024.csv"
OUT_SUMMARY = ROOT / "data/derived/nta_salary_receipt_return_bridge_2024.csv"

BLOCKS = [
    ("all", "合計", list(range(9, 21)), 21),
    ("business", "事業所得者", list(range(24, 36)), 36),
    ("real_estate", "不動産所得者", list(range(39, 51)), 51),
    ("salary", "給与所得者", list(range(54, 66)), 66),
    ("miscellaneous", "雑所得者", list(range(69, 81)), 81),
    ("other", "他の区分に該当しない所得者", list(range(84, 96)), 96),
]
UPPER_YEN = [
    1_000_000, 1_500_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000,
    7_000_000, 10_000_000, 20_000_000, 30_000_000, 50_000_000, None,
]
def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def clean_label(value):
    return re.sub(r"\s+", " ", str(value).replace("\u3000", " ")).strip()


def pdf_text(path, pages=None):
    reader = PdfReader(path)
    use = range(len(reader.pages)) if pages is None else pages
    return "\n".join((reader.pages[i].extract_text() or "") for i in use)


def parse_t23_employment():
    text = re.sub(r"\s+", " ", pdf_text(T23, [0]))
    pat = re.compile(
        r"Employment income\s+"
        r"13,184,714\s+11,425,783\s+1,758,931\s+"
        r"3,143,364\s+2,384,138\s+759,226\s+"
        r"8,532,771\s+7,700,263\s+832,508"
    )
    if not pat.search(text):
        raise RuntimeError("annual Table 2-3 employment-income row not found")
    return {
        "all": (13_184_714, 11_425_783, 1_758_931),
        "positive_balance": (3_143_364, 2_384_138, 759_226),
        "refund": (8_532_771, 7_700_263, 832_508),
    }


def check_notes():
    text = re.sub(r"\s+", "", pdf_text(NOTES, [0, 1]))
    required = [
        "給与所得者",
        "各種所得の金額のうち給与所得の金額が他の各種所得の金額のいずれよりも大きい者",
        "そのため、２－１、２－２と２－３では、人員の合計が異なる。",
        "全数調査",
    ]
    for phrase in required:
        if re.sub(r"\s+", "", phrase) not in text:
            raise RuntimeError(f"annual table-note phrase not found: {phrase}")
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


def build():
    catalog = {r["source_id"]: r for r in read_csv(CATALOG)}
    t7src = catalog["NTA-2024-SHINKOKU-T7-XLSX"]
    t7pdf = catalog["NTA-2024-SHINKOKU-T7-PDF"]
    check_notes()
    t23 = parse_t23_employment()

    x = Xlsx(T7)
    class_rows = []
    block_totals = {}
    try:
        rows = x.rows("第７表")
        for category, category_ja, row_numbers, total_row in BLOCKS:
            q = []
            for idx, (rn, upper) in enumerate(zip(row_numbers, UPPER_YEN), start=1):
                vals = rows[rn]
                label = clean_label(vals.get("C") if category == "all" else vals.get("D"))
                persons = integer_cell(vals.get("E"))
                amount = integer_cell(vals.get("F"))
                wh_persons = integer_cell(vals.get("G"))
                wh_amount = integer_cell(vals.get("H"))
                no_wh = integer_cell(vals.get("I"))
                if persons != wh_persons + no_wh:
                    raise RuntimeError(f"Table 7 person identity failed at row {rn}")
                lower = "" if idx == 1 else UPPER_YEN[idx - 2]
                row = {
                    "tax_year": 2024,
                    "income_earner_category": category,
                    "income_earner_category_ja": category_ja,
                    "salary_receipt_class_index": idx,
                    "salary_receipt_class_label": label,
                    "salary_receipt_lower_bound_yen_exclusive": lower,
                    "salary_receipt_upper_bound_yen_inclusive": "" if upper is None else upper,
                    "salary_receipt_class_topcoded": upper is None,
                    "salary_receipt_persons_estimated": persons,
                    "salary_receipt_million_yen_estimated": amount,
                    "salary_withholding_persons_estimated": wh_persons,
                    "salary_withholding_million_yen_estimated": wh_amount,
                    "no_salary_withholding_persons_estimated": no_wh,
                    "source_id": "NTA-2024-SHINKOKU-T7-XLSX",
                    "source_cells": f"E{rn}:I{rn}",
                    "source_sha256_xlsx": t7src["sha256"],
                    "visual_crosscheck_source_id": "NTA-2024-SHINKOKU-T7-PDF",
                    "source_sha256_pdf": t7pdf["sha256"],
                    "cell_nature": "SURVEY_ESTIMATED_POSITIVE_SELF_ASSESSED_BALANCE_SALARY_RECEIPT_CELL",
                    "identification_warning": (
                        "Sample-survey estimate within positive-self-assessed-balance taxpayers; "
                        "not a complete-survey count and not a person-level match to Private Salary Survey Table 19."
                    ),
                }
                class_rows.append(row)
                q.append(row)
            total = rows[total_row]
            expected = {
                "salary_receipt_persons_estimated": integer_cell(total.get("E")),
                "salary_receipt_million_yen_estimated": integer_cell(total.get("F")),
                "salary_withholding_persons_estimated": integer_cell(total.get("G")),
                "salary_withholding_million_yen_estimated": integer_cell(total.get("H")),
                "no_salary_withholding_persons_estimated": integer_cell(total.get("I")),
            }
            for field, target in expected.items():
                observed = sum(int(r[field]) for r in q)
                tolerance = 2 if field.endswith("_million_yen_estimated") else 0
                if abs(observed - target) > tolerance:
                    raise RuntimeError(
                        f"Table 7 class sum mismatch {category}/{field}: "
                        f"{observed}!={target} tolerance={tolerance}"
                    )
            block_totals[category] = expected
    finally:
        x.close()

    high = [
        r for r in class_rows
        if int(r["salary_receipt_class_index"]) >= 10
    ]
    high_all = [r for r in high if r["income_earner_category"] == "all"]
    high_salary = [r for r in high if r["income_earner_category"] == "salary"]
    high_non_salary = [r for r in high if r["income_earner_category"] not in ("all", "salary")]

    def s(rows_, field):
        return sum(int(r[field]) for r in rows_)

    if not (s(high_all, 'salary_receipt_persons_estimated') == 235287):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_receipt_return_bridge.py:190')
    if not (s(high_salary, 'salary_receipt_persons_estimated') == 225050):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_receipt_return_bridge.py:191')
    if not (s(high_non_salary, 'salary_receipt_persons_estimated') == 10237):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_receipt_return_bridge.py:192')
    if not (s(high_all, 'salary_withholding_persons_estimated') == 227606):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_receipt_return_bridge.py:193')
    if not (s(high_all, 'no_salary_withholding_persons_estimated') == 7681):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_receipt_return_bridge.py:194')

    t19 = {r["metric_id"]: r for r in read_csv(T19_AUDIT)}
    private_gt20 = int(t19["private_salary_full_year_salary_receipts_gt20m"]["value"])
    if not (private_gt20 == 320983):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_receipt_return_bridge.py:198')

    t22_salary = [r for r in read_csv(T22) if r["primary_income_type"] == "salary"]
    t22_all = sum(int(r["table22_population_persons"]) for r in t22_salary)
    t22_pos = sum(int(r["positive_self_assessed_balance_persons"]) for r in t22_salary)
    t22_ref = sum(int(r["refund_persons"]) for r in t22_salary)
    if not ((t22_all, t22_pos, t22_ref) == (11423587, 2385726, 7697018)):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_receipt_return_bridge.py:204')
    metrics = [
        metric(
            "private_salary_full_year_receipts_gt20m",
            private_gt20, "persons_estimated",
            "Private Salary Survey full-year private-sector salary earners",
            "NTA-MINKAN-2024-T19",
            "Table 19 panel 3 total",
            "PAYROLL_SIDE_SURVEY_ESTIMATE",
            "Same >20m salary-receipt threshold as the return-side Table 7 bridge, but no common person identifier.",
        ),
        metric(
            "positive_balance_salary_receipts_gt20m_all_categories",
            s(high_all, "salary_receipt_persons_estimated"), "persons_estimated",
            "Positive-self-assessed-balance taxpayers with salary receipts",
            "NTA-2024-SHINKOKU-T7-XLSX;NTA-2024-SHINKOKU-T7-PDF",
            "Table 7 total rows >20m: 3,000万円以下, 5,000万円以下, 5,000万円超",
            "RETURN_SIDE_SURVEY_ESTIMATE_SAME_SALARY_RECEIPT_THRESHOLD",
            "Direct return-side salary-receipt threshold estimate; not an exact administrative count or overlap count.",
        ),
        metric(
            "positive_balance_salary_receipts_gt20m_salary_category",
            s(high_salary, "salary_receipt_persons_estimated"), "persons_estimated",
            "Positive-self-assessed-balance taxpayers classified as salary income earners",
            "NTA-2024-SHINKOKU-T7-XLSX",
            "Table 7 salary-earner block rows >20m",
            "RETURN_SIDE_SURVEY_ESTIMATE",
            "Salary-earner-category subset of the >20m salary-receipt estimate.",
        ),
        metric(
            "positive_balance_salary_receipts_gt20m_non_salary_categories",
            s(high_non_salary, "salary_receipt_persons_estimated"), "persons_estimated",
            "Positive-self-assessed-balance taxpayers classified outside salary income-earner category",
            "NTA-2024-SHINKOKU-T7-XLSX",
            "Table 7 non-salary-earner blocks rows >20m",
            "RETURN_SIDE_SURVEY_ESTIMATE",
            "Demonstrates that salary receipts >20m are not confined to the salary income-earner category.",
        ),
        metric(
            "positive_balance_salary_receipts_gt20m_with_salary_withholding",
            s(high_all, "salary_withholding_persons_estimated"), "persons_estimated",
            "Positive-self-assessed-balance taxpayers with salary receipts >20m",
            "NTA-2024-SHINKOKU-T7-XLSX",
            "Table 7 total rows >20m, source-withholding-person columns",
            "RETURN_SIDE_SURVEY_ESTIMATE",
            "Salary-source withholding exposure within the >20m return-side salary-receipt group.",
        ),
        metric(
            "positive_balance_salary_receipts_gt20m_without_salary_withholding",
            s(high_all, "no_salary_withholding_persons_estimated"), "persons_estimated",
            "Positive-self-assessed-balance taxpayers with salary receipts >20m",
            "NTA-2024-SHINKOKU-T7-XLSX",
            "Table 7 total rows >20m, no-withholding column",
            "RETURN_SIDE_SURVEY_ESTIMATE",
            "Published complement to salary-source withholding persons.",
        ),
        metric(
            "annual_return_employment_income_persons_all",
            t23["all"][0], "persons_exact",
            "2024 filed-or-processed income-tax population with employment income",
            "NTA-2024-ANNUAL-T23-INCOME-TYPE;NTA-2024-ANNUAL-TABLE-NOTES",
            "Table 2-3(1), employment-income row",
            "COMPLETE_SURVEY_INCOME_TYPE_COUNT",
            "Counts persons with employment income as main or secondary; excludes withholding-only nonfilers.",
        ),
        metric(
            "annual_return_employment_income_persons_main",
            t23["all"][1], "persons_exact",
            "2024 filed-or-processed income-tax population",
            "NTA-2024-ANNUAL-T23-INCOME-TYPE;NTA-2024-ANNUAL-TABLE-NOTES",
            "Table 2-3(1), employment-income Main",
            "COMPLETE_SURVEY_T23_MAIN_DEFINITION",
            "Do not equate to Table 2-2 salary income-earner category; official aggregation rules differ.",
        ),
        metric(
            "annual_return_employment_income_persons_secondary",
            t23["all"][2], "persons_exact",
            "2024 filed-or-processed income-tax population",
            "NTA-2024-ANNUAL-T23-INCOME-TYPE",
            "Table 2-3(1), employment-income Secondary",
            "COMPLETE_SURVEY_T23_SECONDARY_DEFINITION",
            "Persons with employment income that is not their largest income type under Table 2-3 rules.",
        ),
        metric(
            "annual_positive_balance_employment_income_persons",
            t23["positive_balance"][0], "persons_exact",
            "Positive-self-assessed-balance subset of filed-or-processed income-tax population with employment income",
            "NTA-2024-ANNUAL-T23-INCOME-TYPE",
            "Table 2-3(1), employment-income positive-balance columns",
            "COMPLETE_SURVEY_INCOME_TYPE_COUNT",
            "Main plus secondary employment-income persons.",
        ),
        metric(
            "annual_positive_balance_employment_income_persons_main",
            t23["positive_balance"][1], "persons_exact",
            "Positive-self-assessed-balance subset of filed-or-processed income-tax population",
            "NTA-2024-ANNUAL-T23-INCOME-TYPE",
            "Table 2-3(1), employment-income positive-balance Main",
            "COMPLETE_SURVEY_T23_MAIN_DEFINITION",
            "Main employment-income count under Table 2-3 rules.",
        ),
        metric(
            "annual_positive_balance_employment_income_persons_secondary",
            t23["positive_balance"][2], "persons_exact",
            "Positive-self-assessed-balance subset of filed-or-processed income-tax population",
            "NTA-2024-ANNUAL-T23-INCOME-TYPE",
            "Table 2-3(1), employment-income positive-balance Secondary",
            "COMPLETE_SURVEY_T23_SECONDARY_DEFINITION",
            "Secondary employment-income count under Table 2-3 rules.",
        ),
        metric(
            "annual_refund_employment_income_persons",
            t23["refund"][0], "persons_exact",
            "Refund subset of filed-or-processed income-tax population with employment income",
            "NTA-2024-ANNUAL-T23-INCOME-TYPE",
            "Table 2-3(1), employment-income refund columns",
            "COMPLETE_SURVEY_INCOME_TYPE_COUNT",
            "Main plus secondary employment-income persons.",
        ),
        metric(
            "annual_refund_employment_income_persons_main",
            t23["refund"][1], "persons_exact",
            "Refund subset of filed-or-processed income-tax population",
            "NTA-2024-ANNUAL-T23-INCOME-TYPE",
            "Table 2-3(1), employment-income refund Main",
            "COMPLETE_SURVEY_T23_MAIN_DEFINITION",
            "Main employment-income count among refund returns.",
        ),
        metric(
            "annual_refund_employment_income_persons_secondary",
            t23["refund"][2], "persons_exact",
            "Refund subset of filed-or-processed income-tax population",
            "NTA-2024-ANNUAL-T23-INCOME-TYPE",
            "Table 2-3(1), employment-income refund Secondary",
            "COMPLETE_SURVEY_T23_SECONDARY_DEFINITION",
            "Secondary employment-income count among refund returns.",
        ),
        metric(
            "t23_main_minus_t22_salary_category_all",
            t23["all"][1] - t22_all, "persons_difference",
            "2024 filed-or-processed income-tax population",
            "NTA-2024-ANNUAL-T23-INCOME-TYPE;NTA-2024-ANNUAL-TABLE-NOTES;NTA-R06",
            "Table 2-3 Main employment minus Table 2-2 salary income-earner category",
            "DEFINITION_DIFFERENCE_NOT_RECONCILIATION_ERROR",
            "Official notes explicitly state Tables 2-1/2-2 and 2-3 use different person aggregation rules.",
        ),
        metric(
            "t23_main_minus_t22_salary_category_positive_balance",
            t23["positive_balance"][1] - t22_pos, "persons_difference",
            "Positive-self-assessed-balance subset of filed-or-processed income-tax population",
            "NTA-2024-ANNUAL-T23-INCOME-TYPE;NTA-2024-ANNUAL-TABLE-NOTES;NTA-R06",
            "Table 2-3 Main employment minus Table 2-2 salary category",
            "DEFINITION_DIFFERENCE_NOT_RECONCILIATION_ERROR",
            "The difference is expected under distinct official aggregation definitions.",
        ),
        metric(
            "t23_main_minus_t22_salary_category_refund",
            t23["refund"][1] - t22_ref, "persons_difference",
            "Refund subset of filed-or-processed income-tax population",
            "NTA-2024-ANNUAL-T23-INCOME-TYPE;NTA-2024-ANNUAL-TABLE-NOTES;NTA-R06",
            "Table 2-3 Main employment minus Table 2-2 salary category",
            "DEFINITION_DIFFERENCE_NOT_RECONCILIATION_ERROR",
            "The difference is expected under distinct official aggregation definitions.",
        ),
        metric(
            "private_salary_to_positive_balance_gt20m_person_overlap",
            "NOT_IDENTIFIED", "status",
            "Private Salary Survey >20m x positive-balance Table 7 >20m",
            "NTA-MINKAN-2024-T19;NTA-2024-SHINKOKU-T7-XLSX",
            "cross-source",
            "SAME_THRESHOLD_BUT_NO_PERSON_LINK",
            "The salary-receipt threshold now aligns, but private/public coverage, survey estimation, and person linkage remain unresolved.",
        ),
    ]
    return class_rows, metrics
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    class_rows, metrics = build()
    outputs = [(OUT_CLASS, render(class_rows)), (OUT_SUMMARY, render(metrics))]
    if args.check:
        stale = []
        for path, expected in outputs:
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if actual != expected:
                stale.append(str(path.relative_to(ROOT)))
        if stale:
            raise SystemExit("stale generated artifacts: " + ", ".join(stale))
        print(
            "NTA salary-receipt return bridge: current "
            "(72 Table 7 cells; positive-balance salary receipts >20m=235,287 estimated; "
            "annual employment-income return persons=13,184,714 exact; overlap not identified)"
        )
        return
    for path, expected in outputs:
        path.write_text(expected, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
