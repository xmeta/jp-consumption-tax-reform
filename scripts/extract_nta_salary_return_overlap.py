#!/usr/bin/env python3
"""Audit the 2024 private-salary to final-return overlap evidence."""
from pathlib import Path
import argparse
import csv
import io
import re

from extract_nta_shinkoku_income_class_primary_type import Xlsx, integer_cell

ROOT = Path(__file__).resolve().parents[1]
T19 = ROOT / "data/raw/nta/nta_minkan2024_table19_not_year_end_adjusted.xlsx"
FILING_RULE = ROOT / "data/raw/nta/nta_2024_salary_final_return_requirement.html"
CATALOG = ROOT / "data/source_catalog.csv"
T16_SUMMARY = ROOT / "data/derived/nta_private_salary_taxpayer_status_summary_2024.csv"
FINAL_RETURN = ROOT / "data/derived/nta_income_class_primary_type_filing_status_2024.csv"
TAX_FLOW = ROOT / "data/derived/nta_positive_self_assessed_balance_tax_flow_income_class_primary_type_2024.csv"
PROCESSING_AUDIT = ROOT / "data/derived/nta_salary_processing_status_audit_2024.csv"
OUT_CLASS = ROOT / "data/derived/nta_private_salary_not_year_end_adjusted_by_salary_class_2024.csv"
OUT_SUMMARY = ROOT / "data/derived/nta_salary_return_overlap_audit_2024.csv"

PANELS = [("その１", "full_year"), ("その２", "less_than_year")]
BLOCKS = [
    ("taxpayer", list(range(7, 21)), 21),
    ("nontaxpayer", list(range(22, 36)), 36),
    ("all", list(range(37, 51)), 51),
]
SALARY_UPPER_YEN = [
    1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000, 6_000_000,
    7_000_000, 8_000_000, 9_000_000, 10_000_000, 15_000_000,
    20_000_000, 25_000_000, None,
]


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def clean_label(value):
    return re.sub(r"\s+", " ", str(value).replace("\u3000", " ")).strip()


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def quad(vals, cols, tolerance=1):
    a, b, c, total = (integer_cell(vals.get(k)) for k in cols)
    if abs(a + b + c - total) > tolerance:
        raise RuntimeError(f"published subtotal residual too large {cols}: {a}+{b}+{c}-{total}")
    return a, b, c, total


def make_class_row(duration, status, idx, upper, row_number, vals, source_sha):
    counts = quad(vals, ("D", "E", "F", "G"))
    salary = quad(vals, ("H", "I", "J", "K"))
    tax = quad(vals, ("L", "M", "N", "O"))
    lower = "" if idx == 1 else SALARY_UPPER_YEN[idx - 2]
    return {
        "tax_year": 2024,
        "employment_duration_group": duration,
        "tax_status": status,
        "salary_class_index": idx,
        "salary_class_label": clean_label(vals.get("C", "")),
        "salary_lower_bound_yen_exclusive": lower,
        "salary_upper_bound_yen_inclusive": "" if upper is None else upper,
        "salary_class_topcoded": upper is None,
        "secondary_payroll_persons": counts[0],
        "previous_employer_salary_unknown_persons": counts[1],
        "other_reason_persons": counts[2],
        "total_not_year_end_adjusted_persons": counts[3],
        "secondary_payroll_salary_million_yen": salary[0],
        "previous_employer_salary_unknown_million_yen": salary[1],
        "other_reason_salary_million_yen": salary[2],
        "total_salary_million_yen": salary[3],
        "secondary_payroll_tax_million_yen": tax[0],
        "previous_employer_salary_unknown_tax_million_yen": tax[1],
        "other_reason_tax_million_yen": tax[2],
        "total_tax_million_yen": tax[3],
        "source_id": "NTA-MINKAN-2024-T19",
        "source_cells": f"D{row_number}:O{row_number}",
        "source_sha256": source_sha,
        "cell_nature": "PRIVATE_SALARY_SURVEY_ESTIMATE",
        "identification_warning": (
            "Payroll-survey rows do not identify person-level overlap with filed-or-processed income-tax statistics."
        ),
    }


def metric(metric_id, value, unit, population, source_ids, locator, status, interpretation):
    return {
        "metric_id": metric_id, "value": value, "unit": unit, "population": population,
        "source_ids": source_ids, "source_locator": locator,
        "identification_status": status, "interpretation": interpretation,
    }
def build():
    catalog = {r["source_id"]: r for r in read_csv(CATALOG)}
    source = catalog["NTA-MINKAN-2024-T19"]
    filing_source = catalog["NTA-2024-SALARY-FILING-REQUIREMENT"]

    filing_text = FILING_RULE.read_text(encoding="utf-8")
    if "2,000万円" not in filing_text or "確定申告" not in filing_text or "還付" not in filing_text:
        raise RuntimeError("2024 salary filing-requirement anchors not found")

    x = Xlsx(T19)
    class_rows = []
    totals = {}
    try:
        for sheet, duration in PANELS:
            rows = x.rows(sheet)
            for status, row_numbers, total_row in BLOCKS:
                panel = []
                for idx, (rn, upper) in enumerate(zip(row_numbers, SALARY_UPPER_YEN), start=1):
                    row = make_class_row(duration, status, idx, upper, rn, rows[rn], source["sha256"])
                    class_rows.append(row)
                    panel.append(row)

                total_counts = quad(rows[total_row], ("D", "E", "F", "G"))
                total_salary = quad(rows[total_row], ("H", "I", "J", "K"))
                total_tax = quad(rows[total_row], ("L", "M", "N", "O"))
                for field, expected, tol in [
                    ("total_not_year_end_adjusted_persons", total_counts[3], 2),
                    ("total_salary_million_yen", total_salary[3], 3),
                    ("total_tax_million_yen", total_tax[3], 2),
                ]:
                    if abs(sum(int(r[field]) for r in panel) - expected) > tol:
                        raise RuntimeError(f"{sheet}/{status}: class-total mismatch for {field}")
                totals[(duration, status)] = {
                    "counts": total_counts, "salary": total_salary, "tax": total_tax,
                    "row": total_row,
                }

        high = x.rows("その３\u3000その４")
        high_total = high[12]
    finally:
        x.close()
    # Table 19 must reconcile exactly to the corresponding Table 16 panels.
    t16 = {r["summary_scope"]: r for r in read_csv(T16_SUMMARY)}
    for duration, all_scope, excl_scope in [
        ("full_year", "full_year_all_payroll_records", "full_year_otsuran_excluded"),
        ("less_than_year", "less_than_year_all_payroll_records", "less_than_year_otsuran_excluded"),
    ]:
        taxpayer = totals[(duration, "taxpayer")]
        nontax = totals[(duration, "nontaxpayer")]
        all_status = totals[(duration, "all")]
        if not (int(t16[all_scope]['not_year_end_adjusted_taxpayer_persons']) == taxpayer['counts'][3]):
            raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:151')
        if not (int(t16[all_scope]['not_year_end_adjusted_nontaxpayer_persons']) == nontax['counts'][3]):
            raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:152')
        if not (int(t16[all_scope]['not_year_end_adjusted_total_persons']) == all_status['counts'][3]):
            raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:153')
        if not (int(t16[all_scope]['not_year_end_adjusted_tax_million_yen']) == taxpayer['tax'][3]):
            raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:154')
        nonsecondary_taxpayer = taxpayer["counts"][1] + taxpayer["counts"][2]
        nonsecondary_nontax = nontax["counts"][1] + nontax["counts"][2]
        if not (int(t16[excl_scope]['not_year_end_adjusted_taxpayer_persons']) == nonsecondary_taxpayer):
            raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:157')
        if not (int(t16[excl_scope]['not_year_end_adjusted_nontaxpayer_persons']) == nonsecondary_nontax):
            raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:158')
        if not (abs(int(t16[excl_scope]['not_year_end_adjusted_tax_million_yen']) - (taxpayer['tax'][1] + taxpayer['tax'][2])) <= 1):
            raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:159')

    gt20_persons = integer_cell(high_total.get("D"))
    gt20_salary = integer_cell(high_total.get("E"))
    gt20_tax = integer_cell(high_total.get("F"))
    full_year_taxpayer = [r for r in class_rows if r["employment_duration_group"] == "full_year"
                         and r["tax_status"] == "taxpayer"]
    if not (gt20_persons == sum((int(r['other_reason_persons']) for r in full_year_taxpayer[-2:]))):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:168')
    if not (gt20_persons == 320983):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:169')
    if not (gt20_salary == 10403325):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:170')
    if not (gt20_tax == 2858384):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:171')
    salary_return = [r for r in read_csv(FINAL_RETURN) if r["primary_income_type"] == "salary"]
    fr_total = sum(int(r["table22_population_persons"]) for r in salary_return)
    fr_positive = sum(int(r["positive_self_assessed_balance_persons"]) for r in salary_return)
    fr_refund = sum(int(r["refund_persons"]) for r in salary_return)
    fr_residual = sum(int(r["neither_positive_nor_refund_residual"]) for r in salary_return)
    if not (fr_total == fr_positive + fr_refund + fr_residual):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:177')

    processing = {r["metric_id"]: r for r in read_csv(PROCESSING_AUDIT)}
    processed_total = int(processing["salary_table22_filed_or_processed_population"]["value"])
    pure_final_return = int(processing["salary_final_return_row_population"]["value"])
    if not (processed_total == fr_total == 11423587):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:182')
    if not (pure_final_return == 11293442):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:183')
    if not (processed_total != pure_final_return):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:184')

    salary_flow = [r for r in read_csv(TAX_FLOW) if r["primary_income_type"] == "salary"]
    flow_positive = sum(int(r["positive_self_assessed_balance_persons_estimated"]) for r in salary_flow)
    any_withholding = sum(int(r["source_withholding_persons_estimated"]) for r in salary_flow)
    salary_withholding = sum(int(r["salary_withholding_persons_estimated"]) for r in salary_flow)
    if not (flow_positive == fr_positive):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:190')
    if not (salary_withholding <= any_withholding <= fr_positive):
        raise RuntimeError('scientific runtime invariant failed: scripts/extract_nta_salary_return_overlap.py:191')

    metrics = [
        metric("private_salary_full_year_no_year_end_adjustment_taxpayers",
               totals[("full_year", "taxpayer")]["counts"][3], "persons",
               "Private Salary Survey full-year salary earners", "NTA-MINKAN-2024-T19",
               "その1!G21", "OBSERVED_WITHIN_PAYROLL_SURVEY", "All taxpayer records without year-end adjustment."),
        metric("private_salary_full_year_no_year_end_adjustment_secondary_payroll",
               totals[("full_year", "taxpayer")]["counts"][0], "persons",
               "Private Salary Survey full-year taxpayers", "NTA-MINKAN-2024-T19",
               "その1!D21", "OBSERVED_WITHIN_PAYROLL_SURVEY", "Secondary-payroll (乙欄) component."),
        metric("private_salary_full_year_salary_receipts_gt20m",
               gt20_persons, "persons", "Private Salary Survey full-year salary earners",
               "NTA-MINKAN-2024-T19;NTA-2024-SALARY-FILING-REQUIREMENT",
               "その3!D12;2024 filing guidance", "LEGAL_FILING_CANDIDATE_NOT_OBSERVED_MATCH",
               "Salary receipts above 20m create a statutory filing bridge, but public tables do not observe the cross-source person match."),
        metric("salary_primary_table22_filed_or_processed_population", fr_total, "persons",
               "Table 2-2(1) primary income category salary, filed or processed cases",
               "NTA-R06;NTA-2024-PROCESSING-STATUS",
               "Table 2-2(1) salary category; 2-1(1) Part 4 Total Actual",
               "OBSERVED_FILED_OR_PROCESSED_POPULATION",
               "Canonical meaning of 11,423,587; includes final returns and subsequent processing categories."),
        metric("salary_primary_final_return_row_population", pure_final_return, "persons",
               "Pure Final return row, primary income category salary",
               "NTA-2024-PROCESSING-STATUS",
               "2-1(1) Part 4 Final return",
               "OBSERVED_FINAL_RETURN_ROW",
               "Pure Final return row before adding amended returns and correction/determination categories."),
        metric("salary_primary_final_return_population", fr_total, "persons",
               "Deprecated alias for Table 2-2(1) filed-or-processed salary population",
               "NTA-R06;NTA-2024-PROCESSING-STATUS",
               "Table 2-2(1) salary category; 2-1(1) Part 4 Total Actual",
               "DEPRECATED_ALIAS_NOT_PURE_FINAL_RETURN_ROW",
               "Backward-compatible metric name only; use salary_primary_table22_filed_or_processed_population."),
        metric("salary_primary_positive_self_assessed_balance", fr_positive, "persons",
               "Table 2-2(1) filed-or-processed salary-primary cases", "NTA-R06",
               "Table 2-2(1), salary category", "OBSERVED_FILED_OR_PROCESSED_SUBSET",
               "Positive self-assessed balance subset of the filed-or-processed population."),
        metric("salary_primary_refund", fr_refund, "persons",
               "Table 2-2(1) filed-or-processed salary-primary cases", "NTA-R06",
               "Table 2-2(1), salary category", "OBSERVED_FILED_OR_PROCESSED_SUBSET",
               "Refund subset of the filed-or-processed population."),
        metric("salary_primary_neither_positive_nor_refund", fr_residual, "persons",
               "Table 2-2(1) filed-or-processed salary-primary cases", "NTA-R06",
               "Table 2-2(1), salary category", "OBSERVED_FILED_OR_PROCESSED_RESIDUAL",
               "Residual status within the filed-or-processed population."),
        metric("salary_primary_positive_balance_any_withholding", any_withholding, "persons",
               "Positive-self-assessed-balance salary-primary returns",
               "NTA-2024-SHINKOKU-T1-XLSX;NTA-2024-SHINKOKU-T5-XLSX",
               "25 salary-primary cells", "OBSERVED_WITHIN_POSITIVE_BALANCE_SURVEY",
               "Positive-balance salary-primary returns with any source withholding."),
        metric("salary_primary_positive_balance_salary_withholding", salary_withholding, "persons",
               "Positive-self-assessed-balance salary-primary returns",
               "NTA-2024-SHINKOKU-T5-XLSX", "25 salary-primary cells",
               "OBSERVED_WITHIN_POSITIVE_BALANCE_SURVEY",
               "Positive-balance salary-primary returns with salary-source withholding."),
        metric("private_salary_to_final_return_person_overlap", "NOT_IDENTIFIED", "status",
               "Cross-source payroll survey x filed-or-processed income-tax statistics",
               "NTA-MINKAN-2024-T16;NTA-MINKAN-2024-T19;NTA-R06",
               "cross-source", "DO_NOT_SUM_OR_INFER_EXACT_OVERLAP",
               "Private/public sector identity and person-level linkage are absent from published aggregates."),
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
            "NTA salary-return overlap audit: current "
            "(84 class rows; >20m=320,983; salary-primary filed/processed=11,423,587; "
            "pure final-return row=11,293,442; exact overlap not identified)"
        )
        return
    for path, expected in outputs:
        path.write_text(expected, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
