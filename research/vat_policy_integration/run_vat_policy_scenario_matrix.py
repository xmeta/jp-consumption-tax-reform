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
HOUSEHOLD_TAX = ROOT / "data/derived/vat_household_tax_content_envelope.csv"
RATE_SCOPE = ROOT / "data/derived/estat_2024_annual_income_decile_vat_rate_scope_diagnostic.csv"
PASS_THROUGH = ROOT / "data/derived/vat_pass_through_evidence.csv"
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
    if not (len(scenarios) == 8):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:53')
    if not ({r['scenario_id'] for r in scenarios} == EXPECTED_SCENARIOS):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:54')
    fiscal = {r["scenario_id"]: r for r in read(FISCAL)}
    jgb_gdp = {r["scenario_id"]: r for r in read(JGB_GDP)}
    household_exp = read(HOUSEHOLD_EXP)
    household_tax = read(HOUSEHOLD_TAX)
    rate_scope = read(RATE_SCOPE)
    pass_through = {r["evidence_id"]: r for r in read(PASS_THROUGH)}
    if not (set(fiscal) == EXPECTED_SCENARIOS):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:59')
    if not (set(jgb_gdp) == EXPECTED_SCENARIOS):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:60')
    if not (len(household_exp) == 10):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:61')
    if not ({int(r['annual_income_decile']) for r in household_exp} == set(range(1, 11))):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:62')
    if not (all((r['rank_bridge_status'] == 'NOT_LINKED_DO_NOT_TREAT_AS_OBJECTIVE_DECILE' for r in household_exp))):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:63')
    if not (len(household_tax) == 80):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:64')
    if len(rate_scope) != 10 or {int(r["annual_income_decile"]) for r in rate_scope} != set(range(1, 11)):
        raise RuntimeError("unexpected VAT rate-scope diagnostic")
    if not all(r["actual_vat_base_status"].startswith("NOT_IDENTIFIED_") for r in rate_scope):
        raise RuntimeError("rate-scope proxy was promoted to an identified VAT base")
    required_pass_through = {
        "PT-2014-POS-HETEROGENEITY",
        "PT-2019-BOJ-FULL-PASS-THROUGH-ASSUMPTION",
        "QR-2019-BOJ-DEMAND-CHANNELS",
        "QR-2014-CAO-FRONTLOAD-REBOUND",
        "BASE-2019-MOF-RATE-SCOPE",
    }
    if set(pass_through) != required_pass_through:
        raise RuntimeError("unexpected VAT pass-through evidence set")
    if pass_through["PT-2019-BOJ-FULL-PASS-THROUGH-ASSUMPTION"]["identification_status"] != "MECHANICAL_ASSUMPTION_NOT_EMPIRICAL_ESTIMATE":
        raise RuntimeError("BOJ full-pass-through assumption was promoted incorrectly")
    if pass_through["PT-2014-POS-HETEROGENEITY"]["pass_through_point"]:
        raise RuntimeError("historical heterogeneous POS evidence must not become a point parameter")
    scope_by_decile = {int(r["annual_income_decile"]): r for r in rate_scope}
    tax_by_scenario = {}
    for r in household_tax:
        tax_by_scenario.setdefault(r["scenario_id"], []).append(r)
    if not (set(tax_by_scenario) == EXPECTED_SCENARIOS):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:68')
    if not (all((len(v) == 10 for v in tax_by_scenario.values()))):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:69')
    distribution_status = "ANNUAL_INCOME_DECILE_RATE_ONLY_TAX_CONTENT_ENVELOPE_AVAILABLE_OBJECTIVE_RANK_AND_ACTUAL_INCIDENCE_REQUIRED"
    inflation_status = "HISTORICAL_PASS_THROUGH_EVIDENCE_AVAILABLE_POLICY_PASS_THROUGH_AND_MACRO_LINK_NOT_IDENTIFIED"
    historical_pass_through_status = "JAPAN_HISTORICAL_RATE_INCREASE_EVIDENCE_HETEROGENEOUS_POLICY_RATE_CUT_OR_ABOLITION_PARAMETER_NOT_IDENTIFIED"
    vat_base_mix_status = "ANNUAL_INCOME_DECILE_SURVEY_RATE_SCOPE_PROXY_AVAILABLE_TRANSACTION_LEVEL_VAT_BASE_NOT_IDENTIFIED"
    quantity_response_status = "HISTORICAL_INTERTEMPORAL_RESPONSE_EVIDENCE_AVAILABLE_STEADY_STATE_RATE_CUT_OR_ABOLITION_RESPONSE_NOT_IDENTIFIED"

    sens = read(SENS)
    if not (len(sens) == 1200):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:74')
    by_regime = {}
    for row in sens:
        by_regime.setdefault(row["regime_id"], []).append(row)
    if not ({k: len(v) for k, v in by_regime.items()} == {'current_8_10_admin_retained': 300, 'reduced_5_admin_retained': 300, 'zero_rate_admin_retained': 300, 'full_vat_abolition': 300}):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:78')
    ident = {r["quantity"]: r for r in read(IDENT)}
    if not (ident['vat_specific_real_resource_cost_share_of_output']['status'] == 'NOT_IDENTIFIED'):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:85')
    if not (ident['productive_redeployment_fraction_rho']['status'] == 'NOT_IDENTIFIED'):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:86')
    if not (ident['allocative_efficiency_dividend']['status'] == 'NOT_IDENTIFIED'):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:87')
    if not (ident['income_gini_and_FGT2_effect']['status'] == 'NOT_MODELED_PHASE1'):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:88')
    if not (ident['fiscal_debt_effect']['model_use'] == 'FINANCING_CHANNEL_SEPARATE'):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:89')

    rows = []
    for scenario in scenarios:
        fiscal_ref = fiscal[scenario["scenario_id"]]
        jgb_ref = jgb_gdp[scenario["scenario_id"]]
        tax_rows = sorted(tax_by_scenario[scenario["scenario_id"]], key=lambda r: int(r["annual_income_decile"]))
        tax_d1 = tax_rows[0]
        tax_d10 = tax_rows[-1]
        scope_d1 = scope_by_decile[1]
        scope_d10 = scope_by_decile[10]
        if not (tax_d1['annual_income_decile'] == '1' and tax_d10['annual_income_decile'] == '10'):
            raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:98')
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
                "annual_income_decile1_current_embedded_tax_upper_bound_yen_month": tax_d1["current_embedded_consumption_tax_upper_bound_yen_month_ceiling"],
                "annual_income_decile10_current_embedded_tax_upper_bound_yen_month": tax_d10["current_embedded_consumption_tax_upper_bound_yen_month_ceiling"],
                "annual_income_decile1_price_relief_upper_envelope_yen_month": tax_d1["mechanical_price_relief_upper_envelope_yen_month_ceiling"],
                "annual_income_decile10_price_relief_upper_envelope_yen_month": tax_d10["mechanical_price_relief_upper_envelope_yen_month_ceiling"],
                "price_relief_share_current_spending_envelope": tax_d1["mechanical_price_relief_share_current_spending_envelope"],
                "household_tax_content_envelope_status": tax_d1["tax_content_bound_status"],
                "household_price_relief_envelope_status": tax_d1["price_relief_envelope_status"],
                "historical_pass_through_evidence_status": historical_pass_through_status,
                "policy_pass_through_parameter": "",
                "policy_pass_through_parameter_status": "BASELINE_NO_POLICY_CHANGE" if scenario["scenario_id"] == "current_8_10" else "NOT_IDENTIFIED_FOR_RATE_CUT_OR_ABOLITION",
                "vat_base_mix_status": vat_base_mix_status,
                "annual_income_decile1_reduced_rate_scope_proxy_core_yen_month": scope_d1["reduced_rate_scope_proxy_core_yen_month"],
                "annual_income_decile10_reduced_rate_scope_proxy_core_yen_month": scope_d10["reduced_rate_scope_proxy_core_yen_month"],
                "annual_income_decile1_reduced_rate_scope_proxy_with_all_newspaper_yen_month": scope_d1["reduced_rate_scope_proxy_with_all_newspaper_yen_month"],
                "annual_income_decile10_reduced_rate_scope_proxy_with_all_newspaper_yen_month": scope_d10["reduced_rate_scope_proxy_with_all_newspaper_yen_month"],
                "quantity_response_status": "BASELINE_NO_POLICY_CHANGE" if scenario["scenario_id"] == "current_8_10" else quantity_response_status,
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
                "inflation_effect_status": inflation_status,
                "fiscal_balance_effect": "",
                "fiscal_balance_effect_status": fiscal_status,
                "debt_gdp_effect": "",
                "debt_gdp_effect_status": debt_status,
                "interest_rate_jgb_market_effect": "",
                "interest_rate_jgb_market_effect_status": "BASELINE_NO_POLICY_CHANGE" if scenario["financing_strategy"] == "baseline" else "NOT_MODELED_FINANCING_AND_MARKET_FEEDBACK_REQUIRED",
                "joint_outcome_status": "PARTIAL_E2E_REPORT_INSTITUTIONAL_STATIC_FISCAL_AND_HOUSEHOLD_RATE_ENVELOPE_NUMERIC_OTHER_CHANNELS_EXPLICITLY_UNIDENTIFIED",
                "identification_status": "MODEL_CONTINGENT_SCENARIO_MATRIX_NOT_POLICY_FORECAST",
            })
    if not (len(rows) == 2400):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:181')

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
    if not (all((value == base for value in abolition.values()))):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:203')

    zero = [r for r in rows if r["scenario_id"] == "zero_rate_admin_retained"]
    abol = [r for r in rows if r["scenario_id"] == "full_abolition"]
    if not (all((float(r['institutional_gdp_level_effect']) == 0 for r in zero))):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:207')
    if not (max((float(r['institutional_gdp_level_effect']) for r in abol)) == 0.006):
        raise RuntimeError('scientific runtime invariant failed: research/vat_policy_integration/run_vat_policy_scenario_matrix.py:208')

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
            "annual_income_decile1_current_embedded_tax_upper_bound_yen_month": first["annual_income_decile1_current_embedded_tax_upper_bound_yen_month"],
            "annual_income_decile10_current_embedded_tax_upper_bound_yen_month": first["annual_income_decile10_current_embedded_tax_upper_bound_yen_month"],
            "annual_income_decile1_price_relief_upper_envelope_yen_month": first["annual_income_decile1_price_relief_upper_envelope_yen_month"],
            "annual_income_decile10_price_relief_upper_envelope_yen_month": first["annual_income_decile10_price_relief_upper_envelope_yen_month"],
            "price_relief_share_current_spending_envelope": first["price_relief_share_current_spending_envelope"],
            "household_tax_content_envelope_status": first["household_tax_content_envelope_status"],
            "household_price_relief_envelope_status": first["household_price_relief_envelope_status"],
            "historical_pass_through_evidence_status": first["historical_pass_through_evidence_status"],
            "policy_pass_through_parameter": first["policy_pass_through_parameter"],
            "policy_pass_through_parameter_status": first["policy_pass_through_parameter_status"],
            "vat_base_mix_status": first["vat_base_mix_status"],
            "annual_income_decile1_reduced_rate_scope_proxy_core_yen_month": first["annual_income_decile1_reduced_rate_scope_proxy_core_yen_month"],
            "annual_income_decile10_reduced_rate_scope_proxy_core_yen_month": first["annual_income_decile10_reduced_rate_scope_proxy_core_yen_month"],
            "annual_income_decile1_reduced_rate_scope_proxy_with_all_newspaper_yen_month": first["annual_income_decile1_reduced_rate_scope_proxy_with_all_newspaper_yen_month"],
            "annual_income_decile10_reduced_rate_scope_proxy_with_all_newspaper_yen_month": first["annual_income_decile10_reduced_rate_scope_proxy_with_all_newspaper_yen_month"],
            "quantity_response_status": first["quantity_response_status"],
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
