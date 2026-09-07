#!/usr/bin/env python3
"""Adversarial contamination frontier for the F71561 stage-1 bridge.

The objective is not to guess non-resident or quasi-final-return counts.
Instead, this script asks how much contamination would be required to erase
the score_power=2.0 rejection after deliberately overbounding observable
timing and death-related channels.
"""
from pathlib import Path
import csv
import importlib.util

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "contamination_frontier.csv"

spec = importlib.util.spec_from_file_location(
    "stage1_overlap",
    ROOT / "46_income_tax_stage1_population_overlap.py",
)
overlap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlap)


def compute(v):
    diagnostics, base_rows = overlap.compute(v)
    births = sum(v[f"births_{year}"] for year in range(2020, 2025))
    inflows = sum(
        v[f"international_inflow_{year}"] for year in range(2020, 2025)
    )
    deaths = v["deaths_2024"]
    tracked_upper = births + inflows + deaths
    n = diagnostics["candidate_tax_unit_upper_bound"]
    base_overlap = diagnostics["conditional_return_filer_overlap_lower"]

    rows = []
    for row in base_rows:
        threshold = row["Amax_threshold"]
        total_break_even = max(0.0, base_overlap - n * threshold)
        residual = max(0.0, total_break_even - tracked_upper)
        rows.append({
            "prior": row["prior"],
            "Amax_threshold": threshold,
            "tracked_contamination_upper": tracked_upper,
            "total_break_even_contamination": total_break_even,
            "residual_unresolved_contamination_to_erase_rejection": residual,
            "residual_share_of_candidate_upper": residual / n,
            "status": "ROBUSTNESS_FRONTIER_NOT_IDENTIFIED",
        })

    summary = {
        "births_2020_2024_upper": births,
        "international_inflows_2020_2024_upper": inflows,
        "quasi_final_death_upper_2024": deaths,
        "tracked_contamination_upper": tracked_upper,
    }
    return summary, rows


def main():
    v = overlap.load_inputs()
    summary, rows = compute(v)
    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        w.writeheader()
        w.writerows(rows)

    for k, val in summary.items():
        print(f"{k}={val}")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
