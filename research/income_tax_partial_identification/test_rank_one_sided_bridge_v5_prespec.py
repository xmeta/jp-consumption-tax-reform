#!/usr/bin/env python3
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CONFIG = HERE / "rank_one_sided_bridge_v5_config.csv"
SPEC = HERE / "rank_one_sided_bridge_v5_spec.adoc"
CLAIMS = ROOT / "paper1/data/claim_registry.csv"

EXPECTED = {
    "spec_version": "rank_one_sided_bridge_v5",
    "input_pseudofiler_scenarios": "all_13_committed_pseudofiler_scenarios",
    "input_nta_artifact": "nta_income_class_primary_type_filing_status_2024.csv",
    "tax_flow_diagnostic_artifact": "nta_positive_self_assessed_balance_tax_flow_income_class_primary_type_2024.csv",
    "nta_income_class_count": "25",
    "bridge_scheme": "rank_transport_one_sided_subset_compatibility",
    "directional_constraint": "transported_nta_positive_balance_minus_pseudo_calculated_tax_positive_le_eta",
    "eta_lower_bound": "0",
    "eta_upper_bound": "1",
    "rank_bin_mass": "0.1",
    "within_class_positive_allocation": "free_within_overlap_capacity",
    "transport_positive_allocation": "free_within_transport_capacity",
    "rank_cost": "absolute_decile_index_distance",
    "delta_grid": "0;0.25;0.5;1;2;3;4;5",
    "delta_unrestricted": "5",
    "zero_violation_threshold": "solve_minimum_delta_at_eta_0",
    "frontier_endpoint_rule": "eta_star_at_each_delta",
    "overall_weight_scheme": "equal_decile",
    "tax_flow_diagnostic_role": "semantic_direction_only_no_rate_calibration",
    "cross_year_status": "2024_observed_tax_flow_vs_2026_pseudo_tax_model",
    "v3_outer_set_regression": "eta_star_le_v3_epsilon_star_same_delta",
    "delta_monotonicity": "eta_star_nonincreasing",
    "solver": "scipy.optimize.linprog",
    "solver_method": "highs-ds",
    "solver_crosscheck_method": "highs-ipm",
    "equality_residual_tolerance": "1e-8",
    "inequality_residual_tolerance": "1e-8",
    "v3_outer_set_tolerance": "1e-8",
    "frontier_monotonicity_tolerance": "1e-8",
    "zero_violation_tolerance": "1e-8",
    "numpy_version": "2.5.3",
    "scipy_version": "1.18.1",
    "historical_v6_restricted_lp_reproduced": "false",
    "p1c13_v1_modified": "false",
    "p1c14_v2_modified": "false",
    "p1c15_v3_modified": "false",
    "p1c16_v4_modified": "false",
    "paper1_claim_before_ci": "false",
    "paper1_claim_before_separate_promotion": "false",
}


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read_csv(CONFIG)
cfg = {r["key"]: r["value"] for r in rows}
assert len(cfg) == len(rows), "duplicate config key"
for key, value in EXPECTED.items():
    assert cfg.get(key) == value, (key, cfg.get(key), value)

assert cfg["endpoint_metrics"] == (
    "taxable_income_weighted_mean_MTR;"
    "income_tax_liability_weighted_mean_MTR;"
    "pseudo_positive_modeled_annual_income_tax_share;"
    "transported_nta_positive_self_assessed_balance_rate"
)

text = SPEC.read_text(encoding="utf-8")
for required in (
    "PRESPECIFIED_NO_V5_RESULT",
    "r_d^{B}-r_d^{PF}",
    r"\eta^\star_{v5}(\Delta)",
    "V5",
    "No file with those names exists in this pre-specification commit.",
    "no v5 frontier has been computed",
    "no zero-violation threshold has been computed",
    "no v5 MTR endpoint has been computed",
):
    assert required in text, required

# This commit must contain no v5 implementation or generated result.
assert not (HERE / "run_rank_one_sided_bridge_v5.py").exists()
for name in (
    "rank_one_sided_bridge_v5_minimum_violation_frontier.csv",
    "rank_one_sided_bridge_v5_minimum_decile_diagnostics.csv",
    "rank_one_sided_bridge_v5_zero_violation_threshold.csv",
    "rank_one_sided_bridge_v5_transport_plans.csv",
    "rank_one_sided_bridge_v5_endpoints.csv",
):
    assert not (HERE / name).exists(), name

claims = read_csv(CLAIMS)
assert len(claims) == 16
assert all(r["claim_id"] != "P1-C17" for r in claims)

# v1-v4 outputs remain present and untouched by the pre-specification.
for path in (
    HERE / "replacement_transport_lp_minimum_relaxation.csv",
    HERE / "rank_bridge_lp_v2_minimum_relaxation.csv",
    HERE / "rank_bridge_lp_v3_minimum_relaxation_frontier.csv",
    HERE / "rank_epsilon_surface_v4_feasibility.csv",
):
    assert path.exists(), path

print(
    "rank one-sided bridge v5 pre-specification: OK "
    "(8 fixed delta budgets; one-sided eta; no implementation/results; "
    "Paper 1 remains 16 claims)"
)
