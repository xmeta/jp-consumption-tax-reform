#!/usr/bin/env python3
"""Population-overlap diagnostic for the F71561 stage-1 filing bridge.

This script does NOT declare the filing rate point-identified.  It computes a
conservative overlap bound conditional on two unresolved bridge conditions:

1. NTA 2024 return-filer persons must be mapped to the same domestic-person
   universe as the F71561 mother population.  Script 47 bounds several timing
   and quasi-final-return contamination channels, but non-resident filing
   remains unresolved.
2. A return filer inside the F71561 mother population must belong to the broad
   F71561-compatible candidate tax-unit universe used by the stage-1 model.

The output is therefore a CONDITIONAL diagnostic, not a READY identification
result.  The useful result is the very large residual contamination required
to erase the score_power=2.0 rejection.
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
    single_mother = v["f71561_single_mother_households_2024_design"]
    okunoto_general = v["okunoto_general_household_persons_2020"]
    filers = v["nta_return_filers_2024"]

    two_plus_general = general - single
    # The exact Okunoto two-plus person count is not needed for a lower
    # bound. Subtracting all Okunoto general-household persons is a
    # conservative upper bound on its two-plus contribution.
    mother_person_lower = (
        two_plus_general - okunoto_general + single_mother
    )
    out_of_mother_domestic_upper = total - mother_person_lower
    overlap_filer_lower_conditional = max(
        0.0, filers - out_of_mother_domestic_upper
    )
    candidate_tax_unit_upper = total
    filing_rate_lower_conditional = (
        overlap_filer_lower_conditional / candidate_tax_unit_upper
    )

    rows = []
    for key, label in [
        ("threshold_score_power_0p5", "score_power_0.5"),
        ("threshold_score_power_1p0", "score_power_1.0"),
        ("threshold_score_power_2p0", "score_power_2.0"),
    ]:
        threshold = v[key]
        contamination_break_even = (
            overlap_filer_lower_conditional
            - candidate_tax_unit_upper * threshold
        )
        rows.append({
            "prior": label,
            "Amax_threshold": threshold,
            "conditional_stage1_lower": filing_rate_lower_conditional,
            "conditional_rejected_without_untracked_contamination":
                filing_rate_lower_conditional > threshold,
            "additional_untracked_filers_needed_to_erase_rejection":
                max(0.0, contamination_break_even),
            "status":
                "CONDITIONAL_ONLY_PENDING_POPULATION_BRIDGE",
        })

    diagnostics = {
        "two_plus_general_household_persons_2020": two_plus_general,
        "f71561_mother_person_lower_bound": mother_person_lower,
        "out_of_mother_domestic_person_upper_bound":
            out_of_mother_domestic_upper,
        "conditional_return_filer_overlap_lower":
            overlap_filer_lower_conditional,
        "candidate_tax_unit_upper_bound": candidate_tax_unit_upper,
        "conditional_stage1_filing_rate_lower":
            filing_rate_lower_conditional,
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
