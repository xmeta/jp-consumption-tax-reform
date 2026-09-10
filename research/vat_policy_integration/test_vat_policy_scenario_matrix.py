#!/usr/bin/env python3
from pathlib import Path
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "data/derived/vat_policy_scenario_matrix.csv"
SUMMARY = ROOT / "data/derived/vat_policy_scenario_summary.csv"
SCENARIOS = ROOT / "research/vat_policy_integration/scenarios.csv"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(MATRIX)
summary = {r["scenario_id"]: r for r in read(SUMMARY)}
scenarios = {r["scenario_id"]: r for r in read(SCENARIOS)}
expected = {
    "current_8_10", "reduced_5", "zero_rate_admin_retained", "full_abolition",
    "full_abolition_jgb", "full_abolition_income_tax",
    "full_abolition_asset_tax", "full_abolition_mixed",
}
assert set(scenarios) == expected
assert set(summary) == expected
assert len(rows) == 2400
for sid in expected:
    assert sum(r["scenario_id"] == sid for r in rows) == 300

assert all(
    r["identification_status"] == "MODEL_CONTINGENT_SCENARIO_MATRIX_NOT_POLICY_FORECAST"
    for r in rows
)
assert all(
    r["joint_outcome_status"]
    == "PARTIAL_E2E_REPORT_INSTITUTIONAL_AND_STATIC_FISCAL_REFERENCE_NUMERIC_OTHER_CHANNELS_EXPLICITLY_UNIDENTIFIED"
    for r in rows
)

blank_numeric = [
    "overall_real_gdp_level_effect",
    "annual_real_growth_rate_effect",
    "growth_decline_penalty_effect",
    "income_gini_effect",
    "wealth_gini_effect",
    "intergenerational_gap_effect",
    "fgt2_effect",
    "real_disposable_income_by_decile_effect",
    "inflation_effect",
    "fiscal_balance_effect",
    "debt_gdp_effect",
    "interest_rate_jgb_market_effect",
]
for col in blank_numeric:
    assert all(r[col] == "" for r in rows), col
assert all(r["fy2024_consumption_tax_receipts_reference_yen"] == "25021206715000" for r in rows)
assert all(r["fy2024_nominal_gdp_reference_yen"] == "642414700000000" for r in rows)
assert all(
    r["static_incremental_jgb_financing_share_of_fy2024_nominal_gdp"] == "0.038948683327"
    for r in rows if r["scenario_id"] == "full_abolition_jgb"
)
assert all(
    r["static_incremental_jgb_financing_pct_of_fy2024_nominal_gdp"] == "3.894868333"
    for r in rows if r["scenario_id"] == "full_abolition_jgb"
)
assert all(
    r["static_incremental_jgb_financing_share_of_fy2024_nominal_gdp"] == ""
    for r in rows if r["scenario_id"] != "full_abolition_jgb"
)
assert all(r["static_consumption_tax_receipt_effect_yen"] == "" for r in rows if r["scenario_id"] == "reduced_5")
assert all(r["static_consumption_tax_receipt_effect_yen"] == "0" for r in rows if r["scenario_id"] == "current_8_10")
assert all(
    r["static_consumption_tax_receipt_effect_yen"] == "-25021206715000"
    for r in rows if r["scenario_id"] in {
        "zero_rate_admin_retained", "full_abolition", "full_abolition_jgb",
        "full_abolition_income_tax", "full_abolition_asset_tax", "full_abolition_mixed",
    }
)
assert all(r["full_jgb_financing_reference_yen"] == "25021206715000" for r in rows if r["scenario_id"] == "full_abolition_jgb")
for sid in ("current_8_10", "reduced_5", "zero_rate_admin_retained"):
    rr = [r for r in rows if r["scenario_id"] == sid]
    assert all(float(r["institutional_gdp_level_effect"]) == 0 for r in rr)
    assert all(float(r["institutional_transition_growth_contribution"]) == 0 for r in rr)

for sid in (
    "full_abolition", "full_abolition_jgb", "full_abolition_income_tax",
    "full_abolition_asset_tax", "full_abolition_mixed",
):
    assert summary[sid]["institutional_gdp_level_effect_min"] == "0"
    assert summary[sid]["institutional_gdp_level_effect_max"] == "0.006"

assert summary["zero_rate_admin_retained"]["institutional_gdp_level_effect_max"] == "0"
assert summary["current_8_10"]["static_consumption_tax_receipt_effect_yen"] == "0"
assert summary["reduced_5"]["static_consumption_tax_receipt_effect_yen"] == ""
assert summary["reduced_5"]["fiscal_reference_status"] == "NOT_IDENTIFIED_RATE_BASE_MIX_AND_BEHAVIOR_REQUIRED"
for sid in (
    "zero_rate_admin_retained", "full_abolition", "full_abolition_jgb",
    "full_abolition_income_tax", "full_abolition_asset_tax", "full_abolition_mixed",
):
    assert summary[sid]["fy2024_consumption_tax_receipts_reference_yen"] == "25021206715000"
    assert summary[sid]["static_consumption_tax_receipt_effect_yen"] == "-25021206715000"
    assert summary[sid]["gross_replacement_requirement_reference_yen"] == "25021206715000"
    assert summary[sid]["fiscal_balance_status"] == "STATIC_CENTRAL_REVENUE_REFERENCE_AVAILABLE_FULL_FISCAL_BALANCE_NOT_MODELED"
assert summary["full_abolition_jgb"]["full_jgb_financing_reference_yen"] == "25021206715000"
assert summary["full_abolition_jgb"]["fy2024_nominal_gdp_reference_yen"] == "642414700000000"
assert summary["full_abolition_jgb"]["static_incremental_jgb_financing_share_of_fy2024_nominal_gdp"] == "0.038948683327"
assert summary["full_abolition_jgb"]["static_incremental_jgb_financing_pct_of_fy2024_nominal_gdp"] == "3.894868333"
assert summary["full_abolition_jgb"]["debt_gdp_reference_status"] == "STATIC_INCREMENTAL_JGB_FINANCING_SHARE_OF_FY2024_NOMINAL_GDP"
assert summary["full_abolition_jgb"]["debt_gdp_status"] == "STATIC_JGB_AMOUNT_REFERENCE_AVAILABLE_DEBT_GDP_AND_DYNAMIC_PATH_NOT_MODELED"
for sid in ("full_abolition_income_tax", "full_abolition_asset_tax", "full_abolition_mixed"):
    assert summary[sid]["replacement_tax_target_reference_yen"] == "25021206715000"


def signature(sid):
    return [
        (
            r["stress_point_id"],
            r["institutional_gdp_level_effect"],
            r["institutional_transition_growth_contribution"],
        )
        for r in rows if r["scenario_id"] == sid
    ]


base = signature("full_abolition")
for sid in (
    "full_abolition_jgb", "full_abolition_income_tax",
    "full_abolition_asset_tax", "full_abolition_mixed",
):
    assert signature(sid) == base

subprocess.run(
    [
        sys.executable,
        str(ROOT / "research/vat_policy_integration/run_vat_policy_scenario_matrix.py"),
        "--check",
    ],
    cwd=ROOT,
    check=True,
)
print(
    "VAT policy scenario matrix tests: OK "
    "(8 requested scenarios; 2400 rows; joint GDP/growth/Gini/FGT2/fiscal/debt "
    "reporting with static FY2024 VAT fiscal replacement reference and no unmodeled-channel imputation)"
)
