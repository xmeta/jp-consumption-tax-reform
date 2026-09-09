#!/usr/bin/env python3
"""Analytical unresolved-frame robustness frontier for F71561 stage 1.

The published 2024 survey mother population is a 2020-Census-based frame
benchmark, not a directly observed 2024 person set. This module therefore
leaves all additional untracked overlap loss as an explicit budget C_U.

No recovered V6 threshold is required by this script.
"""
from pathlib import Path
import csv
import importlib.util

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "untracked_frontier.csv"

spec = importlib.util.spec_from_file_location(
    "frontier47",
    ROOT / "47_income_tax_stage1_contamination_frontier.py",
)
frontier47 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frontier47)


def compute(v):
    d, _ = frontier47.overlap.compute(v)
    tracked, _ = frontier47.compute(v)

    p = d["candidate_person_upper"]
    b0 = d["nominal_return_filer_overlap_benchmark"]
    allowance = tracked["tracked_mismatch_allowance"]
    br = max(0.0, b0 - allowance)

    return {
        "nominal_overlap_benchmark": b0,
        "tracked_mismatch_allowance": allowance,
        "residual_benchmark_after_tracked_allowance": br,
        "candidate_person_upper": p,
        "robustness_rate_at_C_U_0": br / p,
        "status": "ROBUSTNESS_FRONTIER_C_U_UNRESOLVED",
    }


def robustness_rate(c_u, residual_benchmark, candidate_upper):
    return max(0.0, residual_benchmark - c_u) / candidate_upper


def critical_budget(a, residual_benchmark, candidate_upper):
    if not 0.0 <= a <= 1.0:
        raise ValueError("threshold A must lie in [0, 1]")
    return max(0.0, residual_benchmark - candidate_upper * a)


def main():
    v = frontier47.overlap.load_inputs()
    summary = compute(v)
    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=list(summary), lineterminator="\n"
        )
        w.writeheader()
        w.writerow(summary)

    for k, val in summary.items():
        print(f"{k}={val}")


if __name__ == "__main__":
    main()
