#!/usr/bin/env python3
"""Extract 2024 NTA tax-flow diagnostics within positive self-assessed-balance taxpayers.

Sources:
- Table 1 (R06_01.xlsx): calculated tax, tax credits, withholding, self-assessed balance;
- Table 4 (R06_04.xlsx): tax-credit persons/amounts and components;
- Table 5 (R06_05.xlsx): withholding persons/amounts and components.

The target population is already restricted to persons with positive
self-assessed income tax.  This artifact therefore does not identify the number
of calculated-tax-positive persons outside that population.  It is a
within-NTA tax-flow diagnostic, not a direct F71561-to-filer bridge.
"""
from pathlib import Path
import argparse
import csv
import io

from extract_nta_shinkoku_income_class_primary_type import (
    Xlsx,
    UPPER_YEN,
    integer_cell,
    normalize_label,
)

ROOT = Path(__file__).resolve().parents[1]
T1 = ROOT / "data/raw/nta/nta_2024_shinkoku_sample_table1_summary.xlsx"
T4 = ROOT / "data/raw/nta/nta_2024_shinkoku_sample_table4_tax_credits.xlsx"
T5 = ROOT / "data/raw/nta/nta_2024_shinkoku_sample_table5_withholding.xlsx"
CATALOG = ROOT / "data/source_catalog.csv"
CROSS = ROOT / "data/derived/nta_positive_self_assessed_balance_income_class_primary_type_2024.csv"
OUT = ROOT / "data/derived/nta_positive_self_assessed_balance_tax_flow_income_class_primary_type_2024.csv"

# category, Japanese label, Table 1 start row, Table 4 start row, Table 5 start row
LAYOUT = [
    ("business", "事業所得者", 36, 36, 37),
    ("real_estate", "不動産所得者", 70, 70, 72),
    ("salary", "給与所得者", 98, 98, 100),
    ("miscellaneous", "雑所得者", 132, 132, 135),
    ("other", "他の区分に該当しない所得者", 160, 160, 163),
]


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    if v in ("", "-", None, " "):
        return 0.0
    return float(v)


def normalize_table4_label(s):
    # A few Table 4 business-income cells contain stored phonetic annotations
    # such as `1億円オク` / `100億円超オクチョウ`.  Strip only these suffixes;
    # the income-class text itself remains checked against Tables 1, 2 and 5.
    out = normalize_label(s)
    for suffix in ("オクチョウ", "オク"):
        if out.endswith(suffix):
            out = out[:-len(suffix)]
            break
    return out


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def fmt(x):
    if abs(x - round(x)) < 1e-12:
        return str(int(round(x)))
    return f"{x:.12g}"


def build():
    catalog = {r["source_id"]: r for r in read_csv(CATALOG)}
    s1 = catalog["NTA-2024-SHINKOKU-T1-XLSX"]
    s4 = catalog["NTA-2024-SHINKOKU-T4-XLSX"]
    s5 = catalog["NTA-2024-SHINKOKU-T5-XLSX"]

    books = []
    try:
        for path, sheet in ((T1, "第１表"), (T4, "第４表"), (T5, "第５表")):
            x = Xlsx(path)
            books.append(x)
        r1 = books[0].rows("第１表")
        r4 = books[1].rows("第４表")
        r5 = books[2].rows("第５表")
    finally:
        for x in books:
            x.close()

    cross = {
        (int(r["income_class_index"]), r["primary_income_type"]): r
        for r in read_csv(CROSS)
    }

    out = []
    prev_upper = None
    for i in range(25):
        upper = UPPER_YEN[i]
        for category, ja, t1_start, t4_start, t5_start in LAYOUT:
            a = r1[t1_start + i]
            b = r4[t4_start + i]
            c = r5[t5_start + i]
            key = (i + 1, category)
            base = cross[key]

            label1 = normalize_label(a.get("C", ""))
            label4 = normalize_table4_label(b.get("C", ""))
            label5 = normalize_label(c.get("C", ""))
            if not (label1 == label4 == label5 == base["income_class_label"]):
                raise RuntimeError(
                    f"{key}: income-class label mismatch: "
                    f"{label1!r}, {label4!r}, {label5!r}, "
                    f"{base['income_class_label']!r}"
                )

            persons = integer_cell(a.get("D"))
            if persons != int(base["positive_self_assessed_balance_persons_estimated"]):
                raise RuntimeError(f"{key}: Table 1 persons != Table 2 cross-tab")

            calculated = num(a.get("H"))
            tax_credits = num(a.get("I"))
            withholding_persons = integer_cell(a.get("J"))
            withholding_tax = num(a.get("K"))
            self_assessed = num(a.get("L"))

            credit_persons = integer_cell(b.get("M"))
            credit_amount = num(b.get("N"))
            if credit_amount != tax_credits:
                raise RuntimeError(f"{key}: Table 1 vs Table 4 tax-credit amount mismatch")

            if integer_cell(c.get("D")) != withholding_persons:
                raise RuntimeError(f"{key}: Table 1 vs Table 5 withholding-person mismatch")
            if num(c.get("E")) != withholding_tax:
                raise RuntimeError(f"{key}: Table 1 vs Table 5 withholding-amount mismatch")

            post_credit = calculated - tax_credits
            implied_reconstruction = withholding_tax + self_assessed - post_credit
            implied_reconstruction_rate = (
                implied_reconstruction / post_credit if post_credit > 0 else 0.0
            )
            pre_withholding_total = withholding_tax + self_assessed

            out.append({
                "income_class_index": i + 1,
                "income_class_label": label1,
                "lower_bound_yen_exclusive": "" if prev_upper is None else prev_upper,
                "upper_bound_yen_inclusive": "" if upper is None else upper,
                "is_topcoded": "True" if upper is None else "False",
                "primary_income_type": category,
                "primary_income_type_ja": ja,
                "positive_self_assessed_balance_persons_estimated": persons,
                "calculated_income_tax_million_yen": fmt(calculated),
                "tax_credits_million_yen": fmt(tax_credits),
                "post_credit_income_tax_million_yen": fmt(post_credit),
                "tax_credit_persons_estimated": credit_persons,
                "tax_credit_exposure_share_within_positive_balance": fmt(
                    credit_persons / persons if persons else 0.0
                ),
                "dividend_credit_million_yen": fmt(num(b.get("E"))),
                "housing_credit_million_yen": fmt(num(b.get("G"))),
                "other_credit_million_yen": fmt(num(b.get("I"))),
                "special_2024_tax_reduction_million_yen": fmt(num(b.get("L"))),
                "source_withholding_persons_estimated": withholding_persons,
                "source_withholding_exposure_share_within_positive_balance": fmt(
                    withholding_persons / persons if persons else 0.0
                ),
                "source_withholding_tax_million_yen": fmt(withholding_tax),
                "salary_withholding_persons_estimated": integer_cell(c.get("F")),
                "salary_withholding_tax_million_yen": fmt(num(c.get("G"))),
                "non_salary_withholding_persons_estimated": integer_cell(c.get("H")),
                "non_salary_withholding_tax_million_yen": fmt(num(c.get("I"))),
                "pension_withholding_persons_estimated": integer_cell(c.get("J")),
                "pension_withholding_tax_million_yen": fmt(num(c.get("K"))),
                "self_assessed_balance_million_yen": fmt(self_assessed),
                "implied_reconstruction_special_income_tax_million_yen": fmt(
                    implied_reconstruction
                ),
                "implied_reconstruction_special_income_tax_rate_on_post_credit": fmt(
                    implied_reconstruction_rate
                ),
                "self_assessed_balance_share_of_pre_withholding_tax": fmt(
                    self_assessed / pre_withholding_total if pre_withholding_total > 0 else 0.0
                ),
                "table1_source_cells": (
                    f"D{t1_start+i};H{t1_start+i};I{t1_start+i};"
                    f"J{t1_start+i};K{t1_start+i};L{t1_start+i}"
                ),
                "table4_source_cells": (
                    f"E{t4_start+i};G{t4_start+i};I{t4_start+i};"
                    f"L{t4_start+i};M{t4_start+i};N{t4_start+i}"
                ),
                "table5_source_cells": (
                    f"D{t5_start+i};E{t5_start+i};F{t5_start+i};"
                    f"G{t5_start+i};H{t5_start+i};I{t5_start+i};"
                    f"J{t5_start+i};K{t5_start+i}"
                ),
                "source_ids": (
                    "NTA-2024-SHINKOKU-T1-XLSX;"
                    "NTA-2024-SHINKOKU-T4-XLSX;"
                    "NTA-2024-SHINKOKU-T5-XLSX"
                ),
                "source_sha256_table1": s1["sha256"],
                "source_sha256_table4": s4["sha256"],
                "source_sha256_table5": s5["sha256"],
                "cell_nature": "SURVEY_ESTIMATED_POSITIVE_SELF_ASSESSED_BALANCE_TAX_FLOW_CELL",
                "evidence_status": "REPRODUCED_OFFICIAL_SURVEY_TAX_FLOW_DIAGNOSTIC",
                "target_population": (
                    "2024 NTA Sample Survey for Self-Assessment Income Tax: "
                    "persons with positive self-assessed income tax"
                ),
                "identification_warning": (
                    "The sample is already conditioned on positive self-assessed balance; "
                    "it does not identify calculated-tax-positive persons outside that target, "
                    "does not identify F71561 household-to-filer linkage, and amount-flow "
                    "identities are not person-level transition observations."
                ),
            })
        prev_upper = upper

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text = render(build())
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            raise SystemExit(f"stale generated artifact: {OUT}")
        print("NTA positive-balance tax-flow extract: current (25 classes x 5 types)")
    else:
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}: 125 rows")


if __name__ == "__main__":
    main()
