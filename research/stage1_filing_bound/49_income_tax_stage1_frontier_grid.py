#!/usr/bin/env python3
"""Publication grid for the unresolved total-mismatch budget C_U."""
from pathlib import Path
import csv
import importlib.util

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "untracked_frontier_grid.csv"

spec = importlib.util.spec_from_file_location(
    "frontier48",
    ROOT / "48_income_tax_stage1_untracked_frontier.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def compute_grid(v):
    summary = m.compute(v)
    p = summary["candidate_person_upper"]
    br = summary["residual_benchmark_after_tracked_allowance"]

    grid = [
        ("C_U=0", 0.0),
        ("C_U=1m", 1_000_000.0),
        ("C_U=2m", 2_000_000.0),
        ("C_U=4m", 4_000_000.0),
        ("C_U=6m", 6_000_000.0),
        ("C_U=8m", 8_000_000.0),
        ("C_U=10m", 10_000_000.0),
        ("C_U=11m", 11_000_000.0),
        ("C_U=12m", 12_000_000.0),
    ]

    out = []
    for label, c_u in grid:
        remaining = max(0.0, br - c_u)
        rate = m.robustness_rate(c_u, br, p)
        out.append({
            "scenario": label,
            "C_U": c_u,
            "remaining_overlap_benchmark": remaining,
            "robustness_rate": rate,
            "robustness_rate_pct": 100 * rate,
        })
    return out


def main():
    v = m.frontier47.overlap.load_inputs()
    rows = compute_grid(v)
    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        w.writeheader()
        w.writerows(rows)

    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
