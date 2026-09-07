#!/usr/bin/env python3
"""Publication grid for the unresolved C_NR robustness frontier."""
from pathlib import Path
import csv
import importlib.util

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "nonresident_frontier_grid.csv"

spec = importlib.util.spec_from_file_location(
    "frontier48",
    ROOT / "48_income_tax_stage1_nonresident_frontier.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def compute_grid(v):
    summary, rows = m.compute(v)
    p = summary["candidate_person_upper"]
    n0 = summary["residual_numerator_at_C_NR_0"]
    thresholds = {r["prior"]: r["Amax_threshold"] for r in rows}
    critical = next(
        r["critical_C_NR_strict"]
        for r in rows
        if r["prior"] == "score_power_2.0"
    )
    grid = [
        ("C_NR=0", 0.0),
        ("C_NR=1m", 1_000_000.0),
        ("C_NR=2m", 2_000_000.0),
        ("C_NR=4m", 4_000_000.0),
        ("C_NR=6m", 6_000_000.0),
        ("C_NR=8m", 8_000_000.0),
        ("score2_break_even", critical),
        ("C_NR=9m", 9_000_000.0),
    ]

    out = []
    for label, c_nr in grid:
        lb = m.lower_bound(c_nr, n0, p)
        row = {
            "scenario": label,
            "C_NR": c_nr,
            "lower_bound": lb,
            "lower_bound_pct": 100 * lb,
        }
        for prior, a in thresholds.items():
            key = prior.replace(".", "_")
            row[f"reject_{key}"] = lb > a
        out.append(row)
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
