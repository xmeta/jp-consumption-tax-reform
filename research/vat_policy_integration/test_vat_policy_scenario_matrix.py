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
    == "PARTIAL_E2E_REPORT_INSTITUTIONAL_COMPONENT_NUMERIC_OTHER_CHANNELS_EXPLICITLY_UNIDENTIFIED"
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
assert (
    summary["full_abolition_jgb"]["fiscal_balance_status"]
    == "JGB_FINANCING_DEFINED_NOT_QUANTIFIED"
)
assert (
    summary["full_abolition_income_tax"]["fiscal_balance_status"]
    == "INCOME_TAX_FINANCING_DEFINED_NOT_QUANTIFIED"
)
assert (
    summary["full_abolition_asset_tax"]["fiscal_balance_status"]
    == "WEALTH_ASSET_TAX_FINANCING_DEFINED_NOT_QUANTIFIED"
)
assert (
    summary["full_abolition_mixed"]["fiscal_balance_status"]
    == "MIXED_FINANCING_DEFINED_NOT_QUANTIFIED"
)


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
    "reporting with no unmodeled-channel imputation)"
)
