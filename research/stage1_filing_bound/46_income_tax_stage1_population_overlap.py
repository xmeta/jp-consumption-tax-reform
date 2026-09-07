#!/usr/bin/env python3
"""Nominal population-overlap benchmark for the F71561 stage-1 bridge.

The 2024 survey mother-population counts are estimated from the 2020 Census
frame.  They are not treated as a literal lower bound on the set of persons
present in 2024.

This script therefore computes the overlap that would obtain under exact
population-set correspondence.  Scripts 47 and 48 then allocate tracked and
untracked overlap loss against this benchmark.

Nothing in this file point-identifies the filing rate.
"""
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parent
INPUTS = ROOT / "inputs.csv"
OUTPUT = ROOT / "results.csv"


def load_inputs(path=INPUTS):
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return {row["name"]: float(row["value"]) for row in rows}


def compute(v):
    total = v["census_total_population_2020"]
    general = v["census_general_household_persons_2020"]
    single = v["census_single_households_2020"]
    single_frame = v["f71561_single_mother_households_2024_design"]
    okunoto_general = v["okunoto_general_household_persons_2020"]
    filers = v["nta_final_return_filers_2024"]

    two_plus_general = general - single

    # Published-frame benchmark.  Subtracting all Okunoto general-household
    # persons is conservative relative to subtracting only its two-plus part.
    mother_frame_benchmark = (
        two_plus_general - okunoto_general + single_frame
    )
    nominal_outside = total - mother_frame_benchmark
    nominal_overlap = max(0.0, filers - nominal_outside)
    candidate_upper = total
    c0_pretracked_rate = nominal_overlap / candidate_upper

    rows = []
    for key, label in [
        ("threshold_score_power_0p5", "score_power_0.5"),
        ("threshold_score_power_1p0", "score_power_1.0"),
        ("threshold_score_power_2p0", "score_power_2.0"),
    ]:
        threshold = v[key]
        break_even = nominal_overlap - candidate_upper * threshold
        rows.append({
            "prior": label,
            "Amax_threshold": threshold,
            "c0_pretracked_rate": c0_pretracked_rate,
            "reject_at_zero_untracked_before_tracked_allowance":
                c0_pretracked_rate > threshold,
            "mismatch_break_even_before_tracked_allowance":
                max(0.0, break_even),
            "status": "NOMINAL_BRIDGE_BENCHMARK",
        })

    diagnostics = {
        "two_plus_general_household_persons_2020": two_plus_general,
        "f71561_mother_person_benchmark": mother_frame_benchmark,
        "nominal_outside_person_benchmark": nominal_outside,
        "nominal_return_filer_overlap_benchmark": nominal_overlap,
        "candidate_person_upper": candidate_upper,
        "c0_pretracked_participation_benchmark": c0_pretracked_rate,
    }
    return diagnostics, rows


def main():
    diagnostics, rows = compute(load_inputs())
    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        fieldnames = list(rows[0])
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    for k, val in diagnostics.items():
        print(f"{k}={val}")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
