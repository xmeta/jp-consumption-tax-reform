#!/usr/bin/env python3
"""Build an auditable source-dimension matrix for the salary-to-return bridge.

The result is deliberately a bounded negative-source audit:
it states only that no direct bridge is present in the official source families
enumerated here.  It does not claim that no unpublished administrative linkage
exists.
"""
from pathlib import Path
import argparse
import csv
import io

from extract_nta_shinkoku_income_class_primary_type import Xlsx

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/source_catalog.csv"
OUT_MATRIX = ROOT / "data/derived/nta_salary_filing_bridge_source_matrix_2024.csv"
OUT_AUDIT = ROOT / "data/derived/nta_salary_filing_bridge_identification_audit_2024.csv"

REQUIRED_SOURCE_IDS = [
    "NTA-MINKAN-2024-T16",
    "NTA-MINKAN-2024-T19",
    "NTA-2024-SALARY-FILING-REQUIREMENT",
    "NTA-2024-SHINKOKU-T7-XLSX",
    "NTA-2024-PROCESSING-STATUS",
    "NTA-2024-RETURN-PRESS-T31",
    "NTA-2024-ANNUAL-T23-INCOME-TYPE",
    "NTA-FY2024-WITHHOLDING-STATUS",
    "NTA-NAGOYA-2024-SHINKOKU-21-XLSX",
    "NTA-NAGOYA-2024-SHINKOKU-22-XLSX",
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


def workbook_text(path):
    x = Xlsx(path)
    try:
        parts = []
        for sheet in x.targets:
            parts.append(sheet)
            for row in x.rows(sheet).values():
                parts.extend(str(v) for v in row.values() if v not in (None, ""))
        return "\n".join(parts)
    finally:
        x.close()


def matrix_row(
    family_id,
    source_id,
    side,
    person_population,
    salary_receipt_class,
    salary_receipts_gt20m,
    year_end_adjustment,
    submitted_return,
    processing_status,
    positive_refund_status,
    salary_source_withholding,
    employer_sector,
    geography,
    cross_family_person_link,
    note,
):
    return {
        "source_family_id": family_id,
        "source_id": source_id,
        "population_side": side,
        "person_population": person_population,
        "salary_receipt_class_dimension": salary_receipt_class,
        "salary_receipts_gt20m_dimension": salary_receipts_gt20m,
        "year_end_adjustment_dimension": year_end_adjustment,
        "submitted_return_dimension": submitted_return,
        "processing_status_dimension": processing_status,
        "positive_refund_dimension": positive_refund_status,
        "salary_source_withholding_person_dimension": salary_source_withholding,
        "employer_sector_dimension": employer_sector,
        "geographic_tax_office_dimension": geography,
        "cross_family_person_link": cross_family_person_link,
        "direct_bridge_status": "NO_DIRECT_PERSON_BRIDGE",
        "note": note,
    }


def build():
    catalog = {r["source_id"]: r for r in read_csv(CATALOG)}
    missing = [sid for sid in REQUIRED_SOURCE_IDS if sid not in catalog]
    if missing:
        raise RuntimeError(f"source catalog missing required IDs: {missing}")
    for sid in REQUIRED_SOURCE_IDS:
        r = catalog[sid]
        path = ROOT / r["raw_file"]
        if not path.exists() or not r["sha256"]:
            raise RuntimeError(f"missing raw/provenance for {sid}")

    # Verify the regional workbooks structurally, rather than relying only on
    # prose metadata in the catalog.
    nagoya21 = workbook_text(
        ROOT / catalog["NTA-NAGOYA-2024-SHINKOKU-21-XLSX"]["raw_file"]
    )
    nagoya22 = workbook_text(
        ROOT / catalog["NTA-NAGOYA-2024-SHINKOKU-22-XLSX"]["raw_file"]
    )
    for token in ("申告及び処理の状況", "確定申告", "税務署別課税状況"):
        if token not in nagoya21:
            raise RuntimeError(f"Nagoya 2-1 expected token missing: {token}")
    for token in ("所得階級別人員", "給与所得者", "税務署別"):
        if token not in nagoya22:
            raise RuntimeError(f"Nagoya 2-2 expected token missing: {token}")
    for forbidden in ("年末調整", "給与収入階級"):
        if forbidden in nagoya21 or forbidden in nagoya22:
            raise RuntimeError(f"unexpected direct bridge dimension in regional workbook: {forbidden}")

    rows = [
        matrix_row(
            "private_salary_table16",
            "NTA-MINKAN-2024-T16",
            "PAYROLL_PRIVATE_SURVEY",
            "SURVEY_ESTIMATED_SALARY_EARNERS",
            "YES",
            "NO_EXPLICIT_GT20_PANEL",
            "YES",
            "NO",
            "NO",
            "PAYROLL_TAXPAYER_NONTAXPAYER_NOT_RETURN_STATUS",
            "NO_RETURN_PERSON_LINK",
            "PRIVATE_SECTOR_ONLY",
            "NO",
            "NO",
            "Salary-class and year-end-adjustment payroll evidence; no return-side person linkage.",
        ),
        matrix_row(
            "private_salary_table19",
            "NTA-MINKAN-2024-T19",
            "PAYROLL_PRIVATE_SURVEY",
            "SURVEY_ESTIMATED_SALARY_EARNERS",
            "YES",
            "YES_EXPLICIT_GT20_PANEL",
            "YES_NO_YEAR_END_ADJUSTMENT",
            "NO",
            "NO",
            "NO_RETURN_STATUS",
            "NO_RETURN_PERSON_LINK",
            "PRIVATE_SECTOR_ONLY",
            "NO",
            "NO",
            "Direct payroll-side >20m candidate count and no-year-end-adjustment reasons; no return person match.",
        ),
        matrix_row(
            "salary_filing_legal_rule",
            "NTA-2024-SALARY-FILING-REQUIREMENT",
            "LEGAL_METADATA",
            "NO_STATISTICAL_PERSON_COUNT",
            "LEGAL_CONCEPT",
            "YES_LEGAL_THRESHOLD",
            "YES_LEGAL_MULTIPLE_PAYROLL_CONTEXT",
            "LEGAL_FILING_REQUIREMENT_ONLY",
            "NO",
            "NO",
            "NO",
            "NO",
            "NO",
            "NO",
            "Establishes filing obligation/caveats, not observed compliance or a person-level statistical bridge.",
        ),
        matrix_row(
            "positive_balance_salary_receipt_table7",
            "NTA-2024-SHINKOKU-T7-XLSX",
            "RETURN_SIDE_POSITIVE_BALANCE_SAMPLE",
            "SURVEY_ESTIMATED_POSITIVE_BALANCE_PERSONS",
            "YES",
            "YES",
            "NO",
            "NO",
            "NO_PROCESSING_CATEGORY",
            "POSITIVE_BALANCE_TARGET_ONLY_NO_REFUND",
            "YES_WITHIN_POSITIVE_BALANCE_TARGET",
            "NO_PRIVATE_PUBLIC_EMPLOYER_SPLIT",
            "NO",
            "NO",
            "Same salary-receipt threshold on return side, but only within the positive-self-assessed-balance sample target.",
        ),
        matrix_row(
            "annual_processing_table21",
            "NTA-2024-PROCESSING-STATUS",
            "RETURN_SIDE_ADMINISTRATIVE",
            "EXACT_FILED_OR_PROCESSED_PERSONS",
            "NO",
            "NO",
            "NO",
            "FINAL_RETURN_PROCESSING_ROW_NOT_SUBMISSION_COUNT",
            "YES_EXACT",
            "YES_EXACT_POSITIVE_REFUND_RESIDUAL",
            "NO",
            "NO_PRIVATE_PUBLIC_EMPLOYER_SPLIT",
            "NO_NATIONAL_TABLE",
            "NO",
            "Exact processing categories by income-earner type, but no salary-receipt or year-end-adjustment dimension.",
        ),
        matrix_row(
            "submitted_return_press_table31",
            "NTA-2024-RETURN-PRESS-T31",
            "RETURN_SIDE_SUBMISSION_PUBLICATION",
            "ROUNDED_THOUSAND_PERSONS",
            "NO",
            "NO",
            "NO",
            "YES_ROUNDED_SUBMITTED_RETURN_COUNT",
            "NO",
            "YES_ROUNDED_POSITIVE_REFUND_ZERO",
            "NO",
            "NO",
            "NO",
            "NO",
            "Submitted-return counts by main income category; no salary-receipt threshold or payroll adjustment status.",
        ),
        matrix_row(
            "annual_income_type_table23",
            "NTA-2024-ANNUAL-T23-INCOME-TYPE",
            "RETURN_SIDE_ADMINISTRATIVE",
            "EXACT_FILED_OR_PROCESSED_PERSONS",
            "NO",
            "NO",
            "NO",
            "NO_PURE_SUBMISSION_COUNT",
            "FILED_OR_PROCESSED_AGGREGATE_ONLY",
            "YES_EXACT_POSITIVE_REFUND",
            "NO",
            "NO",
            "NO",
            "NO",
            "Employment income as main/secondary income is observed, but not salary receipts, year-end adjustment, or processing categories.",
        ),
        matrix_row(
            "withholding_public_other_table7",
            "NTA-FY2024-WITHHOLDING-STATUS",
            "WITHHOLDING_SYSTEM",
            "NO_CURRENT_PERSON_COUNT",
            "NO",
            "NO",
            "NO",
            "NO",
            "NO",
            "NO_RETURN_STATUS",
            "WITHHOLDING_AMOUNT_ONLY",
            "YES_PUBLIC_OFFICES_VS_OTHERS_AMOUNTS",
            "NO",
            "NO",
            "Employer-sector payment and withholding amounts are observed, but the current person denominator and return link are absent.",
        ),
        matrix_row(
            "nagoya_regional_table21",
            "NTA-NAGOYA-2024-SHINKOKU-21-XLSX",
            "RETURN_SIDE_REGIONAL_ADMINISTRATIVE",
            "EXACT_REGIONAL_FILED_OR_PROCESSED_PERSONS",
            "NO",
            "NO",
            "NO",
            "NO_PURE_SUBMISSION_COUNT",
            "YES_EXACT",
            "YES_POSITIVE_REFUND",
            "NO",
            "NO",
            "YES_TAX_OFFICE",
            "NO",
            "Regional processing/tax-office detail adds geography, not salary receipts or year-end adjustment.",
        ),
        matrix_row(
            "nagoya_regional_table22",
            "NTA-NAGOYA-2024-SHINKOKU-22-XLSX",
            "RETURN_SIDE_REGIONAL_ADMINISTRATIVE",
            "EXACT_REGIONAL_FILED_OR_PROCESSED_PERSONS",
            "TOTAL_NET_INCOME_CLASS_NOT_SALARY_RECEIPT",
            "NO",
            "NO",
            "NO_PURE_SUBMISSION_COUNT",
            "NO_PROCESSING_CATEGORY_CROSS_TAB",
            "YES_POSITIVE_REFUND",
            "NO",
            "NO",
            "YES_TAX_OFFICE",
            "NO",
            "Regional salary-primary tables use total-net-income classes; they do not add salary-receipt or year-end-adjustment dimensions.",
        ),
    ]

    # The bridge requires dimensions to coexist in one statistical population
    # or a common person linkage.  Legal rules alone never count as a bridge.
    def is_yes(v):
        return v.startswith("YES")

    gt20_and_submission = [
        r for r in rows
        if is_yes(r["salary_receipts_gt20m_dimension"])
        and is_yes(r["submitted_return_dimension"])
    ]
    gt20_and_processing = [
        r for r in rows
        if is_yes(r["salary_receipts_gt20m_dimension"])
        and is_yes(r["processing_status_dimension"])
    ]
    yea_and_processing = [
        r for r in rows
        if is_yes(r["year_end_adjustment_dimension"])
        and is_yes(r["processing_status_dimension"])
    ]
    employer_and_return = [
        r for r in rows
        if is_yes(r["employer_sector_dimension"])
        and (
            is_yes(r["submitted_return_dimension"])
            or is_yes(r["processing_status_dimension"])
        )
    ]
    person_links = [r for r in rows if is_yes(r["cross_family_person_link"])]

    if not (not gt20_and_submission):
        raise RuntimeError('scientific runtime invariant failed: scripts/build_nta_salary_filing_bridge_source_matrix.py:330')
    if not (not gt20_and_processing):
        raise RuntimeError('scientific runtime invariant failed: scripts/build_nta_salary_filing_bridge_source_matrix.py:331')
    if not (not yea_and_processing):
        raise RuntimeError('scientific runtime invariant failed: scripts/build_nta_salary_filing_bridge_source_matrix.py:332')
    if not (not employer_and_return):
        raise RuntimeError('scientific runtime invariant failed: scripts/build_nta_salary_filing_bridge_source_matrix.py:333')
    if not (not person_links):
        raise RuntimeError('scientific runtime invariant failed: scripts/build_nta_salary_filing_bridge_source_matrix.py:334')

    audit = [
        {
            "metric_id": "examined_official_source_families",
            "value": len(rows),
            "unit": "source_families",
            "identification_status": "ENUMERATED_OFFICIAL_SOURCE_FAMILIES",
            "note": "Current 2024 payroll, legal, return, withholding and representative regional source families in the reproducible matrix.",
        },
        {
            "metric_id": "sources_with_gt20_and_submitted_return_person_count",
            "value": len(gt20_and_submission),
            "unit": "source_families",
            "identification_status": "DIRECT_BRIDGE_NOT_FOUND",
            "note": "No examined source jointly reports salary receipts >20m and observed submitted-return person counts.",
        },
        {
            "metric_id": "sources_with_gt20_and_processing_status",
            "value": len(gt20_and_processing),
            "unit": "source_families",
            "identification_status": "DIRECT_BRIDGE_NOT_FOUND",
            "note": "No examined source jointly reports salary receipts >20m and Final return/amended/correction processing status.",
        },
        {
            "metric_id": "sources_with_year_end_adjustment_and_processing_status",
            "value": len(yea_and_processing),
            "unit": "source_families",
            "identification_status": "DIRECT_BRIDGE_NOT_FOUND",
            "note": "No examined source jointly reports payroll year-end-adjustment status and return processing status.",
        },
        {
            "metric_id": "sources_with_employer_sector_and_return_status",
            "value": len(employer_and_return),
            "unit": "source_families",
            "identification_status": "DIRECT_BRIDGE_NOT_FOUND",
            "note": "No examined source jointly reports public/private employer sector and return submission/processing status.",
        },
        {
            "metric_id": "cross_family_person_link_sources",
            "value": len(person_links),
            "unit": "source_families",
            "identification_status": "PERSON_LINK_NOT_FOUND",
            "note": "No examined public source exposes a common person identifier or compatible person-level linkage across payroll and return families.",
        },
        {
            "metric_id": "table7_gt20_positive_balance_is_full_filing_bridge",
            "value": "NO",
            "unit": "status",
            "identification_status": "POSITIVE_BALANCE_CONDITIONAL_ONLY",
            "note": "Table 7 is valuable same-threshold evidence but is conditioned on positive self-assessed balance and excludes refund/no-positive-balance cases.",
        },
        {
            "metric_id": "salary_gt20_legal_rule_is_observed_person_link",
            "value": "NO",
            "unit": "status",
            "identification_status": "LEGAL_RULE_NOT_OBSERVED_COMPLIANCE_LINK",
            "note": "The legal filing requirement does not identify which payroll-survey records appear in submitted or processed return populations.",
        },
        {
            "metric_id": "regional_tables_close_salary_filing_bridge",
            "value": "NO",
            "unit": "status",
            "identification_status": "REGIONAL_DETAIL_ADDS_GEOGRAPHY_NOT_REQUIRED_CROSS_TAB",
            "note": "Representative regional 2-1/2-2 workbooks add tax-office/income-class detail but not salary-receipt x year-end-adjustment x processing status.",
        },
        {
            "metric_id": "direct_salary_receipt_processing_status_bridge",
            "value": "NOT_FOUND_IN_EXAMINED_OFFICIAL_SOURCE_FAMILIES",
            "unit": "status",
            "identification_status": "PUBLIC_AGGREGATE_BRIDGE_NOT_IDENTIFIED",
            "note": "Bounded negative-source result; does not claim that unpublished NTA administrative data lack such a linkage.",
        },
    ]
    return rows, audit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    rows, audit = build()
    outputs = [(OUT_MATRIX, render(rows)), (OUT_AUDIT, render(audit))]
    if args.check:
        stale = []
        for path, expected in outputs:
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if actual != expected:
                stale.append(str(path.relative_to(ROOT)))
        if stale:
            raise SystemExit("stale generated artifacts: " + ", ".join(stale))
        print(
            "NTA salary-filing bridge source matrix: current "
            f"({len(rows)} source families; direct bridge not found)"
        )
        return
    for path, expected in outputs:
        path.write_text(expected, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
