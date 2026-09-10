#!/usr/bin/env python3
"""Join VAT institutional stress results to the Issue #26 policy matrix.

This is an integration adapter, not a new macro model. It carries only the
existing institutional VAT-ablation stress component numerically and keeps
missing macro channels explicit rather than imputing them.
"""
from pathlib import Path
import argparse
import csv
import io

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCENARIOS = HERE / "scenarios.csv"
SENS = ROOT / "data/derived/vat_compliance_productivity_sensitivity.csv"
IDENT = ROOT / "data/derived/vat_compliance_identification_status.csv"
FISCAL = ROOT / "data/derived/vat_policy_fiscal_replacement_reference.csv"
JGB_GDP = ROOT / "data/derived/vat_jgb_debt_gdp_reference.csv"
HOUSEHOLD_EXP = ROOT / "data/derived/estat_2024_annual_income_decile_expenditure_diagnostic.csv"
OUT = ROOT / "data/derived/vat_policy_scenario_matrix.csv"
SUMMARY = ROOT / "data/derived/vat_policy_scenario_summary.csv"

EXPECTED_SCENARIOS = {
    "current_8_10", "reduced_5", "zero_rate_admin_retained", "full_abolition",
    "full_abolition_jgb", "full_abolition_income_tax",
    "full_abolition_asset_tax", "full_abolition_mixed",
}
ABOLITION_SCENARIOS = {
    "full_abolition", "full_abolition_jgb", "full_abolition_income_tax",
    "full_abolition_asset_tax", "full_abolition_mixed",
}
def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return b.getvalue()


def fmt(x):
    return f"{x:.12f}".rstrip("0").rstrip(".")


def build():
    scenarios = read(SCENARIOS)
    assert len(scenarios) == 8
    assert {r["scenario_id"] for r in scenarios} == EXPECTED_SCENARIOS
    fiscal = {r["scenario_id"]: r for r in read(FISCAL)}
    jgb_gdp = {r["scenario_id"]: r for r in read(JGB_GDP)}
    household_exp = read(HOUSEHOLD_EXP)
    assert set(fiscal) == EXPECTED_SCENARIOS
    assert set(jgb_gdp) == EXPECTED_SCENARIOS
    assert len(household_exp) == 10
    assert {int(r["annual_income_decile"]) for r in household_exp} == set(range(1, 11))
    assert all(r["rank_bridge_status"] == "NOT_LINKED_DO_NOT_TREAT_AS_OBJECTIVE_DECILE" for r in household_exp)
    distribution_status = "ANNUAL_INCOME_DECILE_EXPENDITURE_OBSERVED_OBJECTIVE_RANK_BRIDGE_AND_VAT_INCIDENCE_REQUIRED"

    sens = read(SENS)
    assert len(sens) == 1200
    by_regime = {}
    for row in sens:
        by_regime.setdefault(row["regime_id"], []).append(row)
    assert {k: len(v) for k, v in by_regime.items()} == {
        "current_8_10_admin_retained": 300,
        "reduced_5_admin_retained": 300,
        "zero_rate_admin_retained": 300,
        "full_vat_abolition": 300,
    }
    ident = {r["quantity"]: r for r in read(IDENT)}
    assert ident["vat_specific_real_resource_cost_share_of_output"]["status"] == "NOT_IDENTIFIED"
    assert ident["productive_redeployment_fraction_rho"]["status"] == "NOT_IDENTIFIED"
    assert ident["allocative_efficiency_dividend"]["status"] == "NOT_IDENTIFIED"
    assert ident["income_gini_and_FGT2_effect"]["status"] == "NOT_MODELED_PHASE1"
    assert ident["fiscal_debt_effect"]["model_use"] == "FINANCING_CHANNEL_SEPARATE"

    rows = []
    for scenario in scenarios:
        fiscal_ref = fiscal[scenario["scenario_id"]]
        jgb_ref = jgb_gdp[scenario["scenario_id"]]
        for idx, source in enumerate(by_regime[scenario["vat_regime_id"]], 1):
            institutional = float(source["total_institutional_level_effect"])
            transition = float(source["annualized_transition_growth_contribution"])
            if scenario["scenario_id"] == "current_8_10":
                fiscal_status = "BASELINE_ZERO_STATIC_RECEIPT_CHANGE"
            elif scenario["scenario_id"] == "reduced_5":
                fiscal_status = "NOT_IDENTIFIED_RATE_BASE_MIX_AND_BEHAVIOR_REQUIRED"
            else:
                fiscal_status = "STATIC_CENTRAL_REVENUE_REFERENCE_AVAILABLE_FULL_FISCAL_BALANCE_NOT_MODELED"
            if scenario["scenario_id"] == "full_abolition_jgb":
                debt_status = "STATIC_JGB_AMOUNT_REFERENCE_AVAILABLE_DEBT_GDP_AND_DYNAMIC_PATH_NOT_MODELED"
            elif scenario["financing_strategy"] == "baseline":
                debt_status = "BASELINE_NO_POLICY_DEBT_CHANGE"
            else:
                debt_status = "NOT_MODELED_FINANCING_AND_GROWTH_PATH_REQUIRED"
            rows.append({
                "scenario_id": scenario["scenario_id"],
                "scenario_label": scenario["scenario_label"],
                "policy_role": scenario["policy_role"],
                "stress_point_id": idx,
                "vat_regime_id": scenario["vat_regime_id"],
                "vat_standard_rate": source["vat_standard_rate"],
                "vat_reduced_rate": source["vat_reduced_rate"],
                "vat_admin_state": source["vat_admin_state"],
                "invoice_system_state": source["invoice_system_state"],
                "financing_strategy": scenario["financing_strategy"],
                "financing_status": scenario["financing_status"],
                "fy2024_consumption_tax_receipts_reference_yen": fiscal_ref["fy2024_consumption_tax_receipts_reference_yen"],
                "static_consumption_tax_receipt_effect_yen": fiscal_ref["static_consumption_tax_receipt_effect_yen"],
                "gross_replacement_requirement_reference_yen": fiscal_ref["gross_replacement_requirement_reference_yen"],
                "full_jgb_financing_reference_yen": fiscal_ref["full_jgb_financing_reference_yen"],
                "replacement_tax_target_reference_yen": fiscal_ref["replacement_tax_target_reference_yen"],
                "fiscal_reference_status": fiscal_ref["fiscal_reference_status"],
                "fy2024_nominal_gdp_reference_yen": jgb_ref["fy2024_nominal_gdp_yen"],
                "static_incremental_jgb_financing_share_of_fy2024_nominal_gdp": jgb_ref["static_incremental_jgb_financing_share_of_fy2024_nominal_gdp"],
                "static_incremental_jgb_financing_pct_of_fy2024_nominal_gdp": jgb_ref["static_incremental_jgb_financing_pct_of_fy2024_nominal_gdp"],
                "debt_gdp_reference_status": jgb_ref["debt_gdp_reference_status"],
                "vat_admin_resource_share_of_baseline_output": source["vat_admin_resource_share_of_baseline_output"],
                "productive_redeployment_fraction": source["productive_redeployment_fraction"],
                "allocative_efficiency_dividend_share": source["allocative_efficiency_dividend_share"],
                "transition_years": source["transition_years"],
                "institutional_gdp_level_effect": fmt(institutional),
                "institutional_gdp_level_effect_status": "STRESS_TEST_COMPONENT_NOT_EMPIRICAL_BOUND",
                "institutional_transition_growth_contribution": fmt(transition),
                "institutional_transition_growth_status": "STRESS_TEST_COMPONENT_NOT_FULL_ANNUAL_GROWTH_FORECAST",
                "overall_real_gdp_level_effect": "",
                "overall_real_gdp_level_effect_status": "NOT_IDENTIFIED_FULL_POLICY_OUTCOME_DEMAND_AND_FINANCING_NOT_INTEGRATED",
                "annual_real_growth_rate_effect": "",
                "annual_real_growth_rate_effect_status": "NOT_IDENTIFIED_FULL_POLICY_OUTCOME_INSTITUTIONAL_COMPONENT_ONLY",
                "growth_decline_penalty_effect": "",
                "growth_decline_penalty_effect_status": "NOT_EVALUABLE_WITHOUT_FULL_GROWTH_PATH",
                "household_expenditure_diagnostic_rank": "HOUSEHOLD_ANNUAL_INCOME_DECILE",
                "distribution_objective_rank": "OECD_NEW_EQUIVALIZED_DISPOSABLE_INCOME_DECILE",
                "household_expenditure_diagnostic_status": distribution_status,
                "income_gini_effect": "",
                "income_gini_effect_status": distribution_status,
                "wealth_gini_effect": "",
                "wealth_gini_effect_status": "NOT_MODELED_HOUSEHOLD_WEALTH_LINK_REQUIRED",
                "intergenerational_gap_effect": "",
                "intergenerational_gap_effect_status": "NOT_MODELED_AGE_INCIDENCE_LINK_REQUIRED",
                "fgt2_effect": "",
                "fgt2_effect_status": distribution_status,
                "real_disposable_income_by_decile_effect": "",
                "real_disposable_income_by_decile_effect_status": distribution_status,
                "inflation_effect": "",
                "inflation_effect_status": "NOT_MODELED_DEMAND_PASS_THROUGH_AND_MACRO_LINK_REQUIRED",
                "fiscal_balance_effect": "",
                "fiscal_balance_effect_status": fiscal_status,
                "debt_gdp_effect": "",
                "debt_gdp_effect_status": debt_status,
                "interest_rate_jgb_market_effect": "",
                "interest_rate_jgb_market_effect_status": "BASELINE_NO_POLICY_CHANGE" if scenario["financing_strategy"] == "baseline" else "NOT_MODELED_FINANCING_AND_MARKET_FEEDBACK_REQUIRED",
                "joint_outcome_status": "PARTIAL_E2E_REPORT_INSTITUTIONAL_AND_STATIC_FISCAL_REFERENCE_NUMERIC_OTHER_CHANNELS_EXPLICITLY_UNIDENTIFIED",
                "identification_status": "MODEL_CONTINGENT_SCENARIO_MATRIX_NOT_POLICY_FORECAST",
            })
    assert len(rows) == 2400

    def key(row):
        return (
            row["stress_point_id"],
            row["vat_admin_resource_share_of_baseline_output"],
            row["productive_redeployment_fraction"],
            row["allocative_efficiency_dividend_share"],
            row["transition_years"],
        )

    abolition = {
        sid: {
            key(r): (
                r["institutional_gdp_level_effect"],
                r["institutional_transition_growth_contribution"],
            )
            for r in rows if r["scenario_id"] == sid
        }
        for sid in ABOLITION_SCENARIOS
    }
    base = abolition["full_abolition"]
    assert all(value == base for value in abolition.values())

    zero = [r for r in rows if r["scenario_id"] == "zero_rate_admin_retained"]
    abol = [r for r in rows if r["scenario_id"] == "full_abolition"]
    assert all(float(r["institutional_gdp_level_effect"]) == 0 for r in zero)
    assert max(float(r["institutional_gdp_level_effect"]) for r in abol) == 0.006

    summary = []
    for scenario in scenarios:
        rr = [r for r in rows if r["scenario_id"] == scenario["scenario_id"]]
        levels = [float(r["institutional_gdp_level_effect"]) for r in rr]
        growth = [float(r["institutional_transition_growth_contribution"]) for r in rr]
        first = rr[0]
        summary.append({
            "scenario_id": scenario["scenario_id"],
            "scenario_label": scenario["scenario_label"],
            "vat_regime_id": scenario["vat_regime_id"],
            "financing_strategy": scenario["financing_strategy"],
            "grid_points": len(rr),
            "institutional_gdp_level_effect_min": fmt(min(levels)),
            "institutional_gdp_level_effect_max": fmt(max(levels)),
            "institutional_transition_growth_contribution_min": fmt(min(growth)),
            "institutional_transition_growth_contribution_max": fmt(max(growth)),
            "fy2024_consumption_tax_receipts_reference_yen": first["fy2024_consumption_tax_receipts_reference_yen"],
            "static_consumption_tax_receipt_effect_yen": first["static_consumption_tax_receipt_effect_yen"],
            "gross_replacement_requirement_reference_yen": first["gross_replacement_requirement_reference_yen"],
            "full_jgb_financing_reference_yen": first["full_jgb_financing_reference_yen"],
            "replacement_tax_target_reference_yen": first["replacement_tax_target_reference_yen"],
            "fiscal_reference_status": first["fiscal_reference_status"],
            "fy2024_nominal_gdp_reference_yen": first["fy2024_nominal_gdp_reference_yen"],
            "static_incremental_jgb_financing_share_of_fy2024_nominal_gdp": first["static_incremental_jgb_financing_share_of_fy2024_nominal_gdp"],
            "static_incremental_jgb_financing_pct_of_fy2024_nominal_gdp": first["static_incremental_jgb_financing_pct_of_fy2024_nominal_gdp"],
            "debt_gdp_reference_status": first["debt_gdp_reference_status"],
            "overall_real_gdp_status": first["overall_real_gdp_level_effect_status"],
            "annual_real_growth_status": first["annual_real_growth_rate_effect_status"],
            "growth_decline_penalty_status": first["growth_decline_penalty_effect_status"],
            "household_expenditure_diagnostic_status": first["household_expenditure_diagnostic_status"],
            "income_gini_status": first["income_gini_effect_status"],
            "wealth_gini_status": first["wealth_gini_effect_status"],
            "intergenerational_gap_status": first["intergenerational_gap_effect_status"],
            "fgt2_status": first["fgt2_effect_status"],
            "real_disposable_income_by_decile_status": first["real_disposable_income_by_decile_effect_status"],
            "inflation_status": first["inflation_effect_status"],
            "fiscal_balance_status": first["fiscal_balance_effect_status"],
            "debt_gdp_status": first["debt_gdp_effect_status"],
            "interest_rate_jgb_market_status": first["interest_rate_jgb_market_effect_status"],
            "joint_outcome_status": first["joint_outcome_status"],
            "identification_status": "MODEL_CONTINGENT_SCENARIO_SUMMARY_NOT_POLICY_FORECAST",
        })
    return rows, summary
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows, summary = build()
    outputs = [(OUT, render(rows)), (SUMMARY, render(summary))]
    if args.check:
        stale = [
            str(path.relative_to(ROOT))
            for path, expected in outputs
            if not path.exists() or path.read_text(encoding="utf-8") != expected
        ]
        if stale:
            raise SystemExit("stale generated artifacts: " + ", ".join(stale))
        print(
            "VAT policy scenario matrix: current "
            "(8 scenarios x 300 = 2400 rows; joint outcome statuses explicit; "
            "no missing macro channel imputed)"
        )
    else:
        for path, expected in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8")
            print(
                f"wrote {path.relative_to(ROOT)}: "
                f"{len(rows) if path == OUT else len(summary)} rows"
            )


if __name__ == "__main__":
    main()
