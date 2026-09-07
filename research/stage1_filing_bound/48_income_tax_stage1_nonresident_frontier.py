#!/usr/bin/env python3
"""Analytical unresolved-nonresident frontier for F71561 stage 1.

All currently bounded timing/death channels are allocated adversarially first.
The remaining contamination parameter C_NR is left free.  No point estimate or
unsupported upper bound is assigned to C_NR.
"""
from pathlib import Path
import csv
import importlib.util

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "nonresident_frontier.csv"

spec = importlib.util.spec_from_file_location(
    "frontier47",
    ROOT / "47_income_tax_stage1_contamination_frontier.py",
)
frontier47 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frontier47)


def compute(v):
    d, base_rows = frontier47.overlap.compute(v)
    tracked, _ = frontier47.compute(v)
    tracked_upper = tracked["tracked_contamination_upper"]
    p = d["candidate_tax_unit_upper_bound"]
    b0 = d["conditional_return_filer_overlap_lower"]
    residual_numerator_at_zero = max(0.0, b0 - tracked_upper)
    rows = []
    for row in base_rows:
        a = row["Amax_threshold"]
        critical_c_nr = max(0.0, residual_numerator_at_zero - p * a)
        rows.append({
            "prior": row["prior"],
            "Amax_threshold": a,
            "lower_bound_at_C_NR_0": residual_numerator_at_zero / p,
            "critical_C_NR_strict": critical_c_nr,
            "critical_C_NR_share_of_candidate_upper": critical_c_nr / p,
            "rejection_rule":
                "reject_if_C_NR_below_critical" if critical_c_nr > 0
                else "not_rejected_even_at_C_NR_0",
            "status": "PARTIAL_FRONTIER_C_NR_UNRESOLVED",
        })

    summary = {
        "conditional_overlap_before_tracked_contamination": b0,
        "tracked_contamination_upper": tracked_upper,
        "residual_numerator_at_C_NR_0": residual_numerator_at_zero,
        "candidate_person_upper": p,
        "lower_bound_at_C_NR_0": residual_numerator_at_zero / p,
    }
    return summary, rows


def lower_bound(c_nr, residual_numerator, candidate_upper):
    return max(0.0, residual_numerator - c_nr) / candidate_upper


def main():
    v = frontier47.overlap.load_inputs()
    summary, rows = compute(v)
    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=list(rows[0]), lineterminator="\n"
        )
        w.writeheader()
        w.writerows(rows)

    for k, val in summary.items():
        print(f"{k}={val}")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
