#!/usr/bin/env python3
"""Reproduce NTA primary-income-type stage-2 rates and Table 3-1 point check.

The exact person counts are transcribed from the official FY2024 NTA Annual
Statistics Report, Table 2-2(1), printed pp.61-62 (PDF pp.71-72).
The rounded thousand-person counts are transcribed from the official 2024
final-return press release, Table 3-1, printed p.14 (PDF p.15).

The press table explicitly notes that totals and components can disagree due to
rounding.  Therefore the five displayed positive-liability category counts are
renormalized by their own displayed sum (5,174 thousand), not silently forced
to the separately displayed grand total (5,175 thousand), when comparing
composition across publications.

This is a deterministic cross-publication point check, not a statistical
confidence interval and not an identified mapping from F71561 households to
filers.
"""
from pathlib import Path
import argparse
import csv
import io
import sys

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/source_catalog.csv"
OUT_STAGE2 = ROOT / "data/derived/nta_primary_type_stage2_2024.csv"
OUT_T31 = ROOT / "data/derived/nta_table31_primary_type_rounded_2024.csv"
OUT_VALID = (
    ROOT
    / "research/income_tax_partial_identification"
    / "nta_table31_composition_validation.csv"
)

# Exact persons, NTA FY2024 Annual Statistics Report Table 2-2(1).
# category, total final-return persons, positive-liability persons, refund persons,
# source printed page.
ANNUAL = [
    ("business", 3_785_184, 1_174_065, 962_359, "61"),
    ("real_estate", 1_497_102, 804_398, 174_282, "61"),
    ("salary", 11_423_587, 2_385_726, 7_697_018, "62"),
    ("miscellaneous", 5_819_853, 411_376, 4_300_467, "62"),
    ("other", 836_458, 382_695, 393_370, "62"),
]

# Displayed thousand-person values, NTA final-return press release Table 3-1.
# category, final-return total, positive-liability, refund, zero/no-liability.
PRESS = [
    ("business", 3_789, 1_180, 963, 1_645),
    ("real_estate", 1_497, 806, 174, 516),
    ("salary", 11_442, 2_389, 7_711, 1_343),
    ("miscellaneous", 5_825, 417, 4_292, 1_116),
    ("other", 837, 382, 394, 61),
]
PRESS_GRAND = {
    "final_return_thousand": 23_389,
    "positive_liability_thousand": 5_175,
    "refund_thousand": 13_533,
    "zero_thousand": 4_681,
}

LABELS = {
    "business": "事業所得者",
    "real_estate": "不動産所得者",
    "salary": "給与所得者",
    "miscellaneous": "雑所得者",
    "other": "上記以外",
}


def catalog():
    with CATALOG.open(encoding="utf-8", newline="") as f:
        return {r["source_id"]: r for r in csv.DictReader(f)}


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def build():
    cat = catalog()
    annual_src = cat["NTA-R06"]
    press_src = cat["NTA-2024-RETURN-PRESS-T31"]

    exact_total = sum(x[1] for x in ANNUAL)
    exact_positive = sum(x[2] for x in ANNUAL)
    exact_refund = sum(x[3] for x in ANNUAL)

    displayed_category_positive = sum(x[2] for x in PRESS)
    displayed_category_total = sum(x[1] for x in PRESS)
    displayed_category_refund = sum(x[3] for x in PRESS)
    displayed_category_zero = sum(x[4] for x in PRESS)

    stage2 = []
    t31 = []
    valid = []

    press_by = {x[0]: x for x in PRESS}

    for category, total, positive, refund, printed_page in ANNUAL:
        residual = total - positive - refund
        stage2.append({
            "primary_income_type": category,
            "primary_income_type_ja": LABELS[category],
            "final_return_persons_exact": total,
            "positive_liability_persons_exact": positive,
            "refund_persons_exact": refund,
            "zero_or_other_persons_exact_residual": residual,
            "positive_liability_rate": f"{positive / total:.12g}",
            "positive_liability_composition_exact":
                f"{positive / exact_positive:.12g}",
            "annual_all_category_final_return_persons_exact": exact_total,
            "annual_all_category_positive_liability_persons_exact":
                exact_positive,
            "annual_all_category_refund_persons_exact": exact_refund,
            "source_id": "NTA-R06",
            "source_locator":
                f"Table 2-2(1), printed p.{printed_page}; total row for {LABELS[category]}",
            "source_file": annual_src["raw_file"],
            "source_sha256": annual_src["sha256"],
            "evidence_status": "RAW_OFFICIAL_TRANSCRIPTION_VERIFIED",
            "interpretation":
                "external NTA primary-type stage-2 positive-liability diagnostic; not F71561 selection identification",
        })

        _, ptotal, ppositive, prefund, pzero = press_by[category]
        t31.append({
            "primary_income_type": category,
            "primary_income_type_ja": LABELS[category],
            "final_return_thousand_displayed": ptotal,
            "positive_liability_thousand_displayed": ppositive,
            "refund_thousand_displayed": prefund,
            "zero_thousand_displayed": pzero,
            "positive_composition_displayed_category_normalized":
                f"{ppositive / displayed_category_positive:.12g}",
            "positive_composition_using_displayed_grand_total":
                f"{ppositive / PRESS_GRAND['positive_liability_thousand']:.12g}",
            "displayed_five_category_positive_sum_thousand":
                displayed_category_positive,
            "displayed_positive_grand_total_thousand":
                PRESS_GRAND["positive_liability_thousand"],
            "five_category_minus_grand_total_thousand":
                displayed_category_positive
                - PRESS_GRAND["positive_liability_thousand"],
            "source_id": "NTA-2024-RETURN-PRESS-T31",
            "source_locator": "Table 3-1, printed p.14 / PDF p.15",
            "source_file": press_src["raw_file"],
            "source_sha256": press_src["sha256"],
            "rounding_note":
                "source states totals/components can differ due to rounding; composition comparison renormalizes displayed five categories by their own sum",
        })

        exact_share = positive / exact_positive
        displayed_share = ppositive / displayed_category_positive
        diff_pp = (displayed_share - exact_share) * 100.0
        valid.append({
            "primary_income_type": category,
            "primary_income_type_ja": LABELS[category],
            "annual_positive_persons_exact": positive,
            "annual_positive_composition_exact": f"{exact_share:.12g}",
            "table31_positive_thousand_displayed": ppositive,
            "table31_positive_composition_five_category_normalized":
                f"{displayed_share:.12g}",
            "difference_percentage_point_table31_minus_annual":
                f"{diff_pp:.12g}",
            "absolute_difference_percentage_point":
                f"{abs(diff_pp):.12g}",
            "annual_source_id": "NTA-R06",
            "table31_source_id": "NTA-2024-RETURN-PRESS-T31",
            "validation_status": "CROSS_PUBLICATION_POINT_CHECK_ONLY",
        })

    # Reconciliation metadata are repeated by row in the source table output so
    # downstream users cannot overlook the public-table rounding mismatch.
    assert exact_total == 23_362_184
    assert exact_positive == 5_158_260
    assert exact_refund == 13_527_496
    assert displayed_category_positive == 5_174
    assert displayed_category_total == 23_390
    assert displayed_category_refund == 13_534
    assert displayed_category_zero == 4_681

    max_abs = max(float(r["absolute_difference_percentage_point"]) for r in valid)
    for r in valid:
        r["max_absolute_difference_percentage_point"] = f"{max_abs:.12g}"
        r["historical_v6_recovery_target_pp"] = "0.08444"
        r["recovery_target_difference_pp"] = f"{max_abs - 0.08444:.12g}"
        r["interpretation"] = (
            "reproduced rounded-table composition check; not statistical coverage, "
            "not independent-sample validation, not filer-MTR identification"
        )

    return [
        (OUT_STAGE2, stage2),
        (OUT_T31, t31),
        (OUT_VALID, valid),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    outputs = build()
    if args.check:
        stale = []
        for path, rows in outputs:
            expected = render(rows)
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if expected != actual:
                stale.append(str(path.relative_to(ROOT)))
        if stale:
            print("ERROR: stale NTA stage2/holdout outputs: " + ", ".join(stale))
            sys.exit(1)
        print("NTA stage2/holdout extracts: current (5 primary types)")
        return

    for path, rows in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(rows), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}: {len(rows)} rows")


if __name__ == "__main__":
    main()
