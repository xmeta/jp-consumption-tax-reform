#!/usr/bin/env python3
from pathlib import Path
import csv
import hashlib

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived"
OUT = ROOT / "data/derived_catalog.csv"

SPECS = [
    (
        "ESTAT-71411-MAIN-INCOME-BY-DISPOSABLE-DECILE",
        "estat_71411_main_income_by_disposable_decile_2024.csv",
        "scripts/extract_estat_rank_bridge_diagnostics.py",
        "ESTAT-7141-1-2024",
        "DERIVED_REPRODUCED_EXTERNAL_DIAGNOSTIC",
        "Table 7-141-1 household-member composition by main annual-income type across OECD-new equivalized-disposable-income deciles; no NTA category identity imposed",
    ),
    (
        "ESTAT-7171-MAIN-INCOME-DISPOSABLE-QUANTILES",
        "estat_7171_main_income_disposable_quantiles_2024.csv",
        "scripts/extract_estat_rank_bridge_diagnostics.py",
        "ESTAT-7171-2024",
        "DERIVED_REPRODUCED_EXTERNAL_DIAGNOSTIC",
        "Table 7-171 OECD-new equivalized-disposable-income quantiles by main annual-income type; within-NSFCW diagnostic only",
    ),
    (
        "STAGE1-OFFICIAL-INPUTS",
        "stage1_official_inputs.csv",
        "manual_transcription_verified",
        "NTA-R06;STAT-CENSUS-2020-SUMMARY;STAT-CENSUS-2020-BASIC;"
        "STAT-F71561-DESIGN;ISHIKAWA-CENSUS-2020;STAT-MIGRATION-2024;"
        "MHLW-VITAL-2020-T1;MHLW-VITAL-2022-T1;MHLW-VITAL-2024-T1",
        "DERIVED_VERIFIED_TRANSCRIPTION",
        "Normalized official values used by the stage-1 robustness analysis",
    ),
    (
        "ESTAT-71531-DECILES-LONG",
        "estat_71531_deciles_long.csv",
        "scripts/extract_estat_income_tax_tables.py",
        "ESTAT-7153-1-2024",
        "DERIVED_REPRODUCED",
        "Table 7-153-1 decile-by-income-component long extract with source cells",
    ),
    (
        "ESTAT-71561-HOUSEHOLD-TYPES",
        "estat_71561_household_types.csv",
        "scripts/extract_estat_income_tax_tables.py",
        "ESTAT-7156-1-2024",
        "DERIVED_REPRODUCED",
        "49 household-type headers and hierarchy; original leaves derived structurally",
    ),
    (
        "ESTAT-71561-DECILES-LONG",
        "estat_71561_deciles_long.csv",
        "scripts/extract_estat_income_tax_tables.py",
        "ESTAT-7156-1-2024",
        "DERIVED_REPRODUCED",
        "Table 7-156-1 decile x household-type x component long extract with source cells",
    ),
    (
        "ESTAT-71561-LEAF-COMPAT",
        "income_tax_household_type_leaf_deciles_2024.csv",
        "scripts/extract_estat_income_tax_tables.py",
        "ESTAT-7156-1-2024",
        "DERIVED_REPRODUCED",
        "14 structural leaf household types x 10 deciles; compatibility layer for income-tax research",
    ),
    (
        "ESTAT-71531-TAX-SOCIAL-INSTRUMENTS",
        "income_tax_decile_tax_social_instruments_2024.csv",
        "scripts/build_income_tax_decile_instruments.py",
        "ESTAT-7153-1-2024",
        "DERIVED_REPRODUCED",
        "Decile income tax, resident tax and social-insurance contribution moments",
    ),
    (
        "ESTAT-71561-LEAF-AUDIT",
        "estat_71561_leaf_aggregation_audit.csv",
        "scripts/build_income_tax_decile_instruments.py",
        "ESTAT-7153-1-2024;ESTAT-7156-1-2024",
        "DERIVED_REPRODUCED",
        "Leaf aggregation versus total-table rounding diagnostic",
    ),
    (
        "ESTAT-71911-SIZE-AGE-BRIDGE",
        "estat_71911_decile_household_size_age_bridge.csv",
        "scripts/extract_estat_f71911_bridge.py",
        "ESTAT-7191-1-2024",
        "DERIVED_REPRODUCED",
        "F71911 decile household-size top-code sensitivity and age-65+ bridge with source cells",
    ),
    (
        "ESTAT-71911-INCOME-TAX-BRIDGE",
        "income_tax_bridge_deciles_2024.csv",
        "scripts/extract_estat_f71911_bridge.py",
        "ESTAT-7191-1-2024",
        "DERIVED_REPRODUCED_SENSITIVITY_INPUT",
        "Backward-compatible pseudo-filer sensitivity bridge; exact mean household size is not identified because 6+ is top-coded",
    ),
    (
        "NTA-2024-T17-SOCIAL-SCHEDULE",
        "nta_salary_class_social_deduction_schedule_2024.csv",
        "scripts/extract_nta_table17_and_f71551.py",
        "NTA-MINKAN-2024-T17",
        "DERIVED_REPRODUCED_EXTERNAL_SENSITIVITY",
        "Salary-class mean social-insurance deduction per full-year employee, with recipient mean retained separately",
    ),
    (
        "NTA-2024-T17-FAMILY-SCHEDULE",
        "nta_salary_class_family_deduction_validation_2024.csv",
        "scripts/extract_nta_table17_and_f71551.py",
        "NTA-MINKAN-2024-T17;NTA-2026-DEPENDENT-DEDUCTION",
        "DERIVED_REPRODUCED_EXTERNAL_SENSITIVITY",
        "2024 dependent composition by salary class revalued at 2026 dependent-deduction amounts; no 2026 eligibility forecast",
    ),
    (
        "ESTAT-71551-PENSION-AGE-PROXY",
        "income_tax_age_income_source_shares_2024.csv",
        "scripts/extract_nta_table17_and_f71551.py",
        "ESTAT-7155-1-2024",
        "DERIVED_REPRODUCED_SENSITIVITY_PROXY",
        "F71551 age65+ public-pension amount proxy from overlapping age-recap aggregate cells; not a filer/person identified share",
    ),
    (
        "NTA-2024-PRIMARY-TYPE-STAGE2",
        "nta_primary_type_stage2_2024.csv",
        "scripts/extract_nta_stage2_holdout.py",
        "NTA-R06;NTA-2024-SHINKOKU-SAMPLE",
        "DERIVED_REPRODUCED_EXTERNAL_DIAGNOSTIC",
        "Exact NTA primary-income-type positive-self-assessed-balance rates; external diagnostic only, not F71561 selection identification",
    ),
    (
        "NTA-2024-POSITIVE-SELF-ASSESSED-BALANCE-INCOME-CLASS-PRIMARY-TYPE",
        "nta_positive_self_assessed_balance_income_class_primary_type_2024.csv",
        "scripts/extract_nta_shinkoku_income_class_primary_type.py",
        "NTA-2024-SHINKOKU-T2-XLSX;NTA-2024-SHINKOKU-T2-PDF;NTA-R06",
        "DERIVED_REPRODUCED_OFFICIAL_SURVEY_ESTIMATE_CROSSTAB",
        "25 total-income classes x five primary income-earner categories among positive-self-assessed-balance taxpayers; survey-estimated cells with exact row/column reconciliation",
    ),
    (
        "NTA-2024-POSITIVE-SELF-ASSESSED-BALANCE-TAX-FLOW-INCOME-CLASS-PRIMARY-TYPE",
        "nta_positive_self_assessed_balance_tax_flow_income_class_primary_type_2024.csv",
        "scripts/extract_nta_positive_balance_tax_flow.py",
        "NTA-2024-SHINKOKU-T1-XLSX;NTA-2024-SHINKOKU-T4-XLSX;NTA-2024-SHINKOKU-T5-XLSX",
        "DERIVED_REPRODUCED_OFFICIAL_SURVEY_TAX_FLOW_DIAGNOSTIC",
        "25 total-income classes x five primary income-earner categories within the positive-self-assessed-balance survey target; calculated tax, tax credits, withholding exposure/amount, self-assessed balance, and source-cell provenance",
    ),
    (
        "NTA-2024-CALCULATED-TAX-POSITIVE-DENOMINATOR-AUDIT",
        "nta_calculated_tax_positive_denominator_audit_2024.csv",
        "scripts/extract_nta_calculated_tax_denominator_audit.py",
        "NTA-SHINKOKU-JIKEIRETSU-T1-XLSX;NTA-SHINKOKU-JIKEIRETSU-T2-XLSX;NTA-2024-SHINKOKU-SAMPLE;NTA-R06",
        "DERIVED_REPRODUCED_OFFICIAL_DENOMINATOR_SEMANTICS_AUDIT",
        "Long-term Sample Survey taxpayer-count semantics audit: 2024 taxpayer count equals the 5,158,260 positive-self-assessed-balance survey target, not a public calculated-tax-positive person count; Table 2-2(1)-scope bound retained with explicit scope warning",
    ),
    (
        "NTA-2024-PRIVATE-SALARY-TAXPAYER-STATUS-BY-SALARY-CLASS",
        "nta_private_salary_taxpayer_status_by_salary_class_2024.csv",
        "scripts/extract_nta_private_salary_taxpayer_status.py",
        "NTA-MINKAN-2024-T16;NTA-MINKAN-METHODOLOGY",
        "DERIVED_REPRODUCED_OFFICIAL_PRIVATE_SALARY_TAXPAYER_STATUS_DIAGNOSTIC",
        "Four Table 16 panels x 14 salary classes; taxpayer/non-taxpayer counts and tax amounts split by year-end adjustment and 乙欄 exclusion; external wage-side diagnostic only, no additive join to self-assessed returns",
    ),
    (
        "NTA-2024-PRIVATE-SALARY-TAXPAYER-STATUS-SUMMARY",
        "nta_private_salary_taxpayer_status_summary_2024.csv",
        "scripts/extract_nta_private_salary_taxpayer_status.py",
        "NTA-MINKAN-2024-T16;NTA-MINKAN-METHODOLOGY",
        "DERIVED_REPRODUCED_OFFICIAL_PRIVATE_SALARY_TAXPAYER_STATUS_DIAGNOSTIC",
        "Five Table 16 summaries including 35,556,416 year-end-adjusted taxpayers among 52,797,680 private salary earners after 乙欄 exclusion; not a strict final calculated-tax-positive subset and not additive to positive self-assessed returns",
    ),
    (
        "NTA-2024-PRIVATE-SALARY-NOT-YEAR-END-ADJUSTED-BY-SALARY-CLASS",
        "nta_private_salary_not_year_end_adjusted_by_salary_class_2024.csv",
        "scripts/extract_nta_salary_return_overlap.py",
        "NTA-MINKAN-2024-T19",
        "DERIVED_REPRODUCED_OFFICIAL_PRIVATE_SALARY_NO_YEAR_END_ADJUSTMENT_DIAGNOSTIC",
        "Table 19 full-year/less-than-year x taxpayer/nontaxpayer/all x 14 salary classes; persons, salary and tax split by 乙欄, previous-employer salary unknown and other reasons; no person-level final-return linkage",
    ),
    (
        "NTA-2024-SALARY-RETURN-OVERLAP-AUDIT",
        "nta_salary_return_overlap_audit_2024.csv",
        "scripts/extract_nta_salary_return_overlap.py",
        "NTA-MINKAN-2024-T16;NTA-MINKAN-2024-T19;NTA-2024-SALARY-FILING-REQUIREMENT;NTA-R06;NTA-2024-SHINKOKU-T1-XLSX;NTA-2024-SHINKOKU-T5-XLSX",
        "DERIVED_REPRODUCED_OFFICIAL_CROSS_SYSTEM_OVERLAP_AUDIT",
        "Payroll-side no-year-end-adjustment decomposition, >20m statutory filing candidate, all salary-primary return statuses and withholding exposure; exact cross-source person overlap remains NOT_IDENTIFIED and additive unions are prohibited",
    ),
    (
        "NTA-2024-POSITIVE-BALANCE-SALARY-RECEIPT-CLASS",
        "nta_positive_balance_salary_receipt_class_2024.csv",
        "scripts/extract_nta_salary_receipt_return_bridge.py",
        "NTA-2024-SHINKOKU-T7-XLSX;NTA-2024-SHINKOKU-T7-PDF",
        "DERIVED_REPRODUCED_OFFICIAL_SURVEY_SALARY_RECEIPT_BRIDGE",
        "Six Table 7 income-earner blocks x 12 salary-receipt classes within the positive-self-assessed-balance sample; salary-receipt persons/amount and salary-source-withholding exposure with source-cell provenance",
    ),
    (
        "NTA-2024-SALARY-RECEIPT-RETURN-BRIDGE",
        "nta_salary_receipt_return_bridge_2024.csv",
        "scripts/extract_nta_salary_receipt_return_bridge.py",
        "NTA-MINKAN-2024-T19;NTA-2024-SHINKOKU-T7-XLSX;NTA-2024-SHINKOKU-T7-PDF;NTA-2024-ANNUAL-T23-INCOME-TYPE;NTA-2024-ANNUAL-TABLE-NOTES;NTA-R06",
        "DERIVED_REPRODUCED_OFFICIAL_SALARY_RECEIPT_RETURN_BRIDGE_AUDIT",
        "Same-threshold >20m payroll/positive-balance salary-receipt diagnostic plus complete-survey Table 2-3 employment-income main/secondary semantics; exact cross-source person overlap remains NOT_IDENTIFIED",
    ),
    (
        "NTA-2024-SALARY-SOURCE-SYSTEM-COVERAGE",
        "nta_salary_source_system_coverage_2024.csv",
        "scripts/extract_nta_salary_source_system_coverage.py",
        "NTA-FY2024-WITHHOLDING-STATUS;NTA-MINKAN-2024-T1;NTA-MINKAN-METHODOLOGY;NTA-2024-SHINKOKU-T7-XLSX",
        "DERIVED_REPRODUCED_OFFICIAL_MONETARY_COVERAGE_DIAGNOSTIC",
        "FY2024 source-withholding salary payment/tax amounts split into Public Offices/Others/Total compared with Private Salary Survey Table 1; public-office person share remains NOT_IDENTIFIED and applying amount shares to Table 7 person counts is prohibited",
    ),
    (
        "NTA-2024-ANNUAL-INCOME-CLASS-PRIMARY-TYPE-FILING-STATUS",
        "nta_income_class_primary_type_filing_status_2024.csv",
        "scripts/extract_nta_annual_income_class_filing_status.py",
        "NTA-R06;NTA-2024-SHINKOKU-T2-XLSX",
        "DERIVED_REPRODUCED_ADMINISTRATIVE_CROSSTAB",
        "Exact annual-statistics final-return, positive-self-assessed-balance, refund, and residual counts for 25 total-net-income classes x five primary income-earner categories; 125 positive cells cross-check exactly to Sample Survey Table 2",
    ),
    (
        "NTA-2024-T31-ROUNDED-PRIMARY-TYPES",
        "nta_table31_primary_type_rounded_2024.csv",
        "scripts/extract_nta_stage2_holdout.py",
        "NTA-2024-RETURN-PRESS-T31",
        "DERIVED_REPRODUCED_POINT_CHECK_INPUT",
        "Displayed thousand-person Table 3-1 counts with explicit five-category versus grand-total rounding mismatch",
    ),
    (
        "NTA-2026-STATUTORY-PARAMETERS",
        "income_tax_2026_statutory_parameters.csv",
        "scripts/build_income_tax_2026_statutory_parameters.py",
        "NTA-2026-TAX-REFORM;NTA-2026-INCOME-TAX;NTA-SALARY-DEDUCTION-1410;NTA-INCOME-TAX-RATE-2260;NTA-2026-PENSION-TAX;NTA-2026-PENSION-DETAIL;NTA-2026-DEPENDENT-DEDUCTION",
        "DERIVED_REPRODUCED_VERIFIED_RULES",
        "Versioned 2026 statutory tax parameters with official source locators and raw SHA-256 values",
    ),
]


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def row_count(path):
    with path.open(encoding="utf-8", newline="") as f:
        return max(0, sum(1 for _ in f) - 1)


def main():
    rows = []
    registered = set()
    for aid, rel, generator, source_ids, status, description in SPECS:
        path = DERIVED / rel
        if not path.exists():
            raise SystemExit(f"missing derived artifact: {path}")
        if rel in registered:
            raise SystemExit(f"duplicate derived path: {rel}")
        registered.add(rel)
        rows.append({
            "artifact_id": aid,
            "derived_file": str(path.relative_to(ROOT)),
            "generator": generator,
            "source_ids": source_ids,
            "row_count": row_count(path),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "status": status,
            "description": description,
        })

    actual = {
        p.name for p in DERIVED.iterdir()
        if p.is_file()
    }
    if actual != registered:
        raise SystemExit(
            "derived catalog mismatch: "
            f"unregistered={sorted(actual-registered)} "
            f"missing={sorted(registered-actual)}"
        )

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=list(rows[0]), lineterminator="\n"
        )
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} artifacts")


if __name__ == "__main__":
    main()
