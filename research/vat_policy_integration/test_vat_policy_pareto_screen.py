#!/usr/bin/env python3
if not __debug__:
    raise RuntimeError("optimized Python is not supported for executable tests; assertions must remain active")

from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SCREEN = ROOT / "data/derived/vat_policy_pareto_screen.csv"
PAIRWISE = ROOT / "data/derived/vat_policy_pareto_pairwise.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


screen = read(SCREEN)
pairwise = read(PAIRWISE)
objectives = read(ROOT / "research/vat_policy_integration/pareto_objectives.csv")
assert [(r["objective_id"], r["direction"]) for r in objectives] == [("cumulative_real_growth", "maximize"), ("growth_decline_penalty", "minimize"), ("fgt2_effect", "minimize"), ("income_gini_effect", "minimize"), ("wealth_gini_effect", "minimize"), ("intergenerational_gap_effect", "minimize")]
assert all(r["required_for_headline"] == "true" for r in objectives)
assert len(screen) == 8
assert len(pairwise) == 28
assert {r["scenario_id"] for r in screen} == {
    "current_8_10", "reduced_5", "zero_rate_admin_retained", "full_abolition",
    "full_abolition_jgb", "full_abolition_income_tax",
    "full_abolition_asset_tax", "full_abolition_mixed",
}

assert all(
    r["pareto_classification"] == "UNRESOLVED_NOT_ENOUGH_IDENTIFIED_OBJECTIVES"
    for r in screen
)
assert all(r["robustly_dominated_by"] == "" for r in screen)
assert all(r["normative_weights_used"] == "false" for r in screen)
assert all(r["headline_optimum_claim_allowed"] == "false" for r in screen)
assert all(
    r["dominance_status"] == "INDETERMINATE_MISSING_REQUIRED_OBJECTIVES"
    for r in pairwise
)
assert all(r["normative_weights_used"] == "false" for r in pairwise)
assert all(r["missing_required_objectives"] for r in pairwise)

by_id = {r["scenario_id"]: r for r in screen}
assert all(row["required_objective_count"] == "6" for row in screen)
assert all(row["bounded_required_objective_count"] == "0" for row in screen)
assert all(row["bounded_required_objectives"] == "" for row in screen)
assert all("cumulative_real_growth" in row["missing_required_objectives"] for row in screen)

subprocess.run(
    [sys.executable, str(ROOT / "research/vat_policy_integration/build_vat_policy_pareto_screen.py"), "--check"],
    cwd=ROOT,
    check=True,
)
print("VAT policy Pareto screen tests: OK")
