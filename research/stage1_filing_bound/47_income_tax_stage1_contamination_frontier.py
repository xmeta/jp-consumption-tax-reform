#!/usr/bin/env python3
"""Adversarial mismatch allowance for the F71561 stage-1 benchmark.

This script does not identify total 2020-to-2024 frame mismatch.  It allocates
large, observable timing/death channels entirely against the nominal overlap
benchmark, then reports how much additional untracked overlap loss would still
be needed to cross each recovered prior threshold.
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
    tracked_allowance = births + inflows + deaths
    n = diagnostics["candidate_person_upper"]
    nominal_overlap = diagnostics["nominal_return_filer_overlap_benchmark"]

    rows = []
    for row in base_rows:
        threshold = row["Amax_threshold"]
        total_break_even = max(0.0, nominal_overlap - n * threshold)
        residual = max(0.0, total_break_even - tracked_allowance)
        rows.append({
            "prior": row["prior"],
            "Amax_threshold": threshold,
            "tracked_mismatch_allowance": tracked_allowance,
            "mismatch_break_even_from_nominal": total_break_even,
            "residual_untracked_mismatch_to_erase_rejection": residual,
            "residual_share_of_candidate_upper": residual / n,
            "status": "ROBUSTNESS_FRONTIER_TRACKED_ALLOWANCE",
        })

    summary = {
        "births_2020_2024_upper": births,
        "international_inflows_2020_2024_upper": inflows,
        "quasi_final_death_upper_2024": deaths,
        "tracked_mismatch_allowance": tracked_allowance,
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
