#!/usr/bin/env python3
"""Audit whether NTA public long-term tables identify calculated-tax-positive persons.

The long-term Sample Survey for Self-Assessment Income Tax publishes both
"taxpayer count" and calculated-tax amounts by total-income class.  This audit
checks the semantics of that taxpayer-count series against the official survey
target and the independently reproduced FY2024 annual-statistics population.

Key distinction:
- the Sample Survey target is persons with positive self-assessed balance;
- calculated income tax is an upstream amount before tax credits/withholding;
- the public long-term workbook does not publish a person count for
  calculated-tax-positive persons outside the positive-balance survey target.

The resulting 5,158,260..23,362,184 person bound is valid only inside the
FY2024 Table 2-2(1) filed/processed population.  It is not a general-population
upper bound and must not be used as a direct pseudo-filer calibration.
"""
from pathlib import Path
import argparse
import csv
import io
import math

from extract_nta_shinkoku_income_class_primary_type import Xlsx, integer_cell

ROOT = Path(__file__).resolve().parents[1]
S1 = ROOT / "data/raw/nta/nta_jikeiretsu_shinkoku_sample_table1.xlsx"
S2 = ROOT / "data/raw/nta/nta_jikeiretsu_shinkoku_sample_table2.xlsx"
CATALOG = ROOT / "data/source_catalog.csv"
STAGE2 = ROOT / "data/derived/nta_primary_type_stage2_2024.csv"
OUT = ROOT / "data/derived/nta_calculated_tax_positive_denominator_audit_2024.csv"

YEAR_PREFIX = "令和６年分"


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def find_year_row(rows, prefix=YEAR_PREFIX):
    matches = [
        rn
        for rn, vals in rows.items()
        if str(vals.get("A", "")).startswith(prefix)
    ]
    if matches != [79]:
        raise RuntimeError(f"unexpected {prefix} row(s): {matches}")
    return matches[0]


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def build():
    catalog = {r["source_id"]: r for r in read_csv(CATALOG)}
    required_sources = (
        "NTA-SHINKOKU-JIKEIRETSU-T1-XLSX",
        "NTA-SHINKOKU-JIKEIRETSU-T2-XLSX",
        "NTA-2024-SHINKOKU-SAMPLE",
        "NTA-R06",
    )
    for sid in required_sources:
        if sid not in catalog:
            raise RuntimeError(f"missing source catalog entry: {sid}")

    x1 = Xlsx(S1)
    x2 = Xlsx(S2)
    try:
        r1 = x1.rows("合計")
        r1n = find_year_row(r1)
        t1 = r1[r1n]

        sheets = {}
        for sh in (
            "納税者数（合計）",
            "算出税額（合計）",
            "税額控除額（合計）",
            "源泉徴収税額（合計）",
            "申告納税額（合計）",
        ):
            rr = x2.rows(sh)
            rn = find_year_row(rr)
            sheets[sh] = (rn, rr[rn])
    finally:
        x1.close()
        x2.close()

    # Long-term Table 1, 2024 row.
    sample_taxpayers = integer_cell(t1.get("B"))
    calculated_tax = integer_cell(t1.get("F"))
    tax_credits = integer_cell(t1.get("G"))
    withholding_persons = integer_cell(t1.get("H"))
    withholding_tax = integer_cell(t1.get("I"))
    self_assessed_balance = integer_cell(t1.get("J"))

    # Long-term Table 2 totals.
    t2_taxpayers = integer_cell(sheets["納税者数（合計）"][1].get("AE"))
    t2_calculated_tax = integer_cell(sheets["算出税額（合計）"][1].get("AE"))
    t2_tax_credits = integer_cell(sheets["税額控除額（合計）"][1].get("AE"))
    t2_withholding_tax = integer_cell(sheets["源泉徴収税額（合計）"][1].get("AE"))
    t2_self_assessed_balance = integer_cell(
        sheets["申告納税額（合計）"][1].get("AE")
    )

    if sample_taxpayers != t2_taxpayers:
        raise RuntimeError("long-term Table 1 and Table 2 taxpayer counts differ")
    if calculated_tax != t2_calculated_tax:
        raise RuntimeError("long-term Table 1 and Table 2 calculated tax differ")
    if tax_credits != t2_tax_credits:
        raise RuntimeError("long-term Table 1 and Table 2 tax credits differ")
    if withholding_tax != t2_withholding_tax:
        raise RuntimeError("long-term Table 1 and Table 2 withholding tax differ")
    if self_assessed_balance != t2_self_assessed_balance:
        raise RuntimeError("long-term Table 1 and Table 2 self-assessed balance differ")

    # Existing independently reproduced FY2024 annual-statistics totals.
    stage2 = read_csv(STAGE2)
    if len(stage2) != 5:
        raise RuntimeError("unexpected stage2 primary-type row count")
    first = stage2[0]
    table22_population = int(first["annual_all_category_table22_population_persons_exact"])
    annual_positive = int(
        first["annual_all_category_positive_self_assessed_balance_persons_exact"]
    )
    annual_refund = int(first["annual_all_category_refund_persons_exact"])
    for r in stage2[1:]:
        if int(r["annual_all_category_table22_population_persons_exact"]) != table22_population:
            raise RuntimeError("inconsistent Table 2-2(1) population total")
        if int(r["annual_all_category_positive_self_assessed_balance_persons_exact"]) != annual_positive:
            raise RuntimeError("inconsistent annual positive-balance total")
        if int(r["annual_all_category_refund_persons_exact"]) != annual_refund:
            raise RuntimeError("inconsistent annual refund total")

    if sample_taxpayers != annual_positive:
        raise RuntimeError(
            "long-term Sample Survey taxpayer count does not match independently "
            "reproduced positive-self-assessed-balance total"
        )

    residual = table22_population - annual_positive - annual_refund
    if residual < 0:
        raise RuntimeError("negative Table 2-2(1) residual")

    lower = annual_positive
    upper = table22_population
    lower_rate = lower / upper
    bound_width = upper - lower

    # Same-person same-year logic: B>0 implies pre-withholding/post-credit tax>0,
    # hence calculated tax >0.  The public Sample Survey, however, conditions
    # on B>0 and does not observe the remainder of calculated-tax-positive
    # persons.
    row = {
        "tax_year": 2024,
        "audit_status": "CALCULATED_TAX_POSITIVE_PERSON_COUNT_NOT_IDENTIFIED",
        "long_term_taxpayer_count_semantics":
            "POSITIVE_SELF_ASSESSED_BALANCE_SURVEY_TARGET_NOT_CALCULATED_TAX_POSITIVE_COUNT",
        "long_term_table1_taxpayer_persons": sample_taxpayers,
        "long_term_table1_taxpayer_source_cell": f"B{r1n}",
        "long_term_table2_taxpayer_persons": t2_taxpayers,
        "long_term_table2_taxpayer_source_cell":
            f"AE{sheets['納税者数（合計）'][0]}",
        "annual_positive_self_assessed_balance_persons": annual_positive,
        "annual_table22_population_persons": table22_population,
        "annual_refund_persons": annual_refund,
        "annual_neither_positive_nor_refund_persons": residual,
        "calculated_tax_million_yen": calculated_tax,
        "calculated_tax_source_cells":
            f"F{r1n};算出税額（合計）!AE{sheets['算出税額（合計）'][0]}",
        "tax_credits_million_yen": tax_credits,
        "tax_credits_source_cells":
            f"G{r1n};税額控除額（合計）!AE{sheets['税額控除額（合計）'][0]}",
        "source_withholding_persons": withholding_persons,
        "source_withholding_persons_source_cell": f"H{r1n}",
        "source_withholding_tax_million_yen": withholding_tax,
        "source_withholding_tax_source_cells":
            f"I{r1n};源泉徴収税額（合計）!AE{sheets['源泉徴収税額（合計）'][0]}",
        "self_assessed_balance_million_yen": self_assessed_balance,
        "self_assessed_balance_source_cells":
            f"J{r1n};申告納税額（合計）!AE{sheets['申告納税額（合計）'][0]}",
        "calculated_tax_positive_persons_public_value": "",
        "table22_scope_calculated_tax_positive_lower_bound_persons": lower,
        "table22_scope_calculated_tax_positive_upper_bound_persons": upper,
        "table22_scope_lower_bound_rate": f"{lower_rate:.12g}",
        "table22_scope_upper_bound_rate": "1",
        "table22_scope_bound_width_persons": bound_width,
        "same_person_same_year_direction":
            "POSITIVE_SELF_ASSESSED_BALANCE_IMPLIES_POSITIVE_CALCULATED_TAX",
        "general_population_upper_bound_status":
            "NOT_PROVIDED_BY_THESE_SELF_ASSESSMENT_SOURCES",
        "cross_system_use":
            "DO_NOT_CALIBRATE_PSEUDO_CALCULATED_TAX_POSITIVE_RATE_FROM_LONG_TERM_TAXPAYER_COUNT",
        "source_ids":
            "NTA-SHINKOKU-JIKEIRETSU-T1-XLSX;"
            "NTA-SHINKOKU-JIKEIRETSU-T2-XLSX;"
            "NTA-2024-SHINKOKU-SAMPLE;"
            "NTA-R06",
        "source_sha256_s1": catalog["NTA-SHINKOKU-JIKEIRETSU-T1-XLSX"]["sha256"],
        "source_sha256_s2": catalog["NTA-SHINKOKU-JIKEIRETSU-T2-XLSX"]["sha256"],
        "source_sha256_sample_pdf": catalog["NTA-2024-SHINKOKU-SAMPLE"]["sha256"],
        "source_sha256_annual_report": catalog["NTA-R06"]["sha256"],
        "evidence_status": "REPRODUCED_OFFICIAL_DENOMINATOR_SEMANTICS_AUDIT",
        "identification_warning":
            "The long-term series' taxpayer count is the positive-self-assessed-balance survey target. "
            "It is not a person count for calculated tax > 0. The 23,362,184 upper bound applies only "
            "inside the FY2024 Table 2-2(1) filed/processed population and is not a general-population "
            "or F71561 upper bound.",
    }
    return [row]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    expected = render(build())
    if args.check:
        actual = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if actual != expected:
            raise SystemExit(f"stale generated artifact: {OUT}")
        print(
            "NTA calculated-tax-positive denominator audit: current "
            "(long-term taxpayer count = positive self-assessed balance target; "
            "calculated-tax-positive count not identified)"
        )
    else:
        OUT.write_text(expected, encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}: 1 row")


if __name__ == "__main__":
    main()
