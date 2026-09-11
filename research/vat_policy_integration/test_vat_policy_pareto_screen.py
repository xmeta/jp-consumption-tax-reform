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
assert [(r["objective_id"], r["direction"]) for r in objectives] == [("overall_real_gdp_level_effect", "maximize"), ("annual_real_growth_rate_effect", "maximize"), ("growth_decline_penalty", "minimize"), ("income_gini_effect", "minimize"), ("wealth_gini_effect", "minimize"), ("intergenerational_gap_effect", "minimize"), ("fgt2_effect", "minimize"), ("year10_incremental_policy_debt_gdp", "minimize")]
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
for sid in ("full_abolition_jgb", "full_abolition_income_tax", "full_abolition_asset_tax", "full_abolition_mixed"):
    assert by_id[sid]["bounded_required_objective_count"] == "1"
    assert by_id[sid]["bounded_required_objectives"] == "year10_incremental_policy_debt_gdp"
assert by_id["current_8_10"]["bounded_required_objective_count"] == "1"
assert by_id["current_8_10"]["bounded_required_objectives"] == "year10_incremental_policy_debt_gdp"
for sid in ("reduced_5", "zero_rate_admin_retained", "full_abolition"):
    assert by_id[sid]["bounded_required_objective_count"] == "0"

subprocess.run(
    [sys.executable, str(ROOT / "research/vat_policy_integration/build_vat_policy_pareto_screen.py"), "--check"],
    cwd=ROOT,
    check=True,
)
print("VAT policy Pareto screen tests: OK")
