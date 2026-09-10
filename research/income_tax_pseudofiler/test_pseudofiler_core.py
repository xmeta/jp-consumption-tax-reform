#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv
import math
import subprocess
import sys

from run_pseudofiler_core import leaf_num, modeled_leaf_rows, num

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

SCENARIOS = {
    "central", "f71911_topcode10", "size_lower", "size_upper",
    "business_proportional", "other_wage_split2",
    "no_social_deduction_proxy", "nta_salary_social",
    "nta_salary_dependents", "pension_head_merge",
    "pension_age_split_separate", "pension_member_split",
    "pension_member_split_f71551",
}
MTR_FIELDS = [
    "pseudo_filer_share_MTR_0p0",
    "pseudo_filer_share_MTR_0p05",
    "pseudo_filer_share_MTR_0p1",
    "pseudo_filer_share_MTR_0p2",
    "pseudo_filer_share_MTR_0p23",
    "pseudo_filer_share_MTR_0p33",
    "pseudo_filer_share_MTR_0p4",
    "pseudo_filer_share_MTR_0p45",
]


def read(name):
    with (HERE / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


cal = read("pseudofiler_calibration.csv")
scen = read("pseudofiler_mtr_scenarios.csv")
summ = read("pseudofiler_mtr_summary.csv")
groups = read("household_worker_groups.csv")
with (ROOT / "data/derived/estat_71561_income_tax_target_definition_audit_2024.csv").open(
    encoding="utf-8", newline=""
) as f:
    target_audit = list(csv.DictReader(f))

try:
    num("X")
except ValueError:
    pass
else:
    raise AssertionError("suppressed X must not be numerically coerced")

fixture = {
    "household_count_approx": "",
    "household_count_approx_missing_marker": "X",
    "income_tax_kY": "123",
    "income_tax_kY_missing_marker": "",
}
modeled, suppressed = modeled_leaf_rows([fixture])
assert modeled == [] and suppressed == [fixture]
assert leaf_num({"v": "", "v_missing_marker": "-"}, "v") == 0.0
try:
    modeled_leaf_rows([{
        "household_count_approx": "10",
        "household_count_approx_missing_marker": "",
        "income_tax_kY": "",
        "income_tax_kY_missing_marker": "X",
    }])
except ValueError:
    pass
else:
    raise AssertionError("monetary X with usable count must fail closed")

assert len(cal) == 130
assert len(scen) == 130
assert len(summ) == 10
assert len(groups) == 40
assert len(target_audit) == 7
assert {int(r["decile"]) for r in summ} == set(range(1, 11))
assert "observed_leaf_weighted_income_tax_kY" not in cal[0]
assert "published_imputed_leaf_weighted_income_tax_kY" in cal[0]
assert "observed_income_tax_liability_share" not in groups[0]
assert "published_imputed_income_tax_share" in groups[0]

audit = {r["audit_item"]: r for r in target_audit}
assert audit["collection_status"]["alignment_status"] == "PUBLISHED_IMPUTED_NOT_DIRECT_OBSERVATION"
assert audit["reconstruction_special_income_tax"]["alignment_status"] == "TARGET_INCLUDES_MODEL_EXCLUDES"
assert audit["interest_dividend_tax"]["alignment_status"] == "TARGET_INCLUDES_MODEL_EXCLUDES"
assert audit["fixed_2024_tax_reduction"]["alignment_status"] == "TARGET_INCLUDES_2024_CREDIT_MODEL_DOES_NOT"
assert audit["calibration_decision"]["numeric_reconciliation_status"] == "NO_NUMERIC_TRANSFORM; CONCEPT_DIFFERENCE_NOT_IDENTIFIED"
assert {r["scenario"] for r in scen} == SCENARIOS

for d in range(1, 11):
    assert len([r for r in scen if int(r["decile"]) == d]) == 13

for r in cal:
    assert r["model_status"] == "SENSITIVITY_ONLY_NOT_IDENTIFIED"
    assert r["target_inside_logical_bounds"] == "True"
    assert float(r["nuisance_income_scale"]) > 0
    assert float(r["continuous_proxy_fit_error_kY"]) >= 0
    assert r["calibration_target_concept"] == "STATISTICS_BUREAU_PUBLISHED_IMPUTED_2024_INCOME_TAX"
    assert r["target_model_alignment_status"] == "NAMED_CROSS_CONCEPT_SENSITIVITY"
    assert r["target_numeric_reconciliation_status"] == "NO_NUMERIC_TRANSFORM; CONCEPT_DIFFERENCE_NOT_IDENTIFIED"

# Central specification can continuously match the published tax moment in all
# deciles.  Extreme sensitivity cases can hit statutory basic-deduction jumps;
# those are retained as nearest-achievable diagnostics, not silently smoothed.
central_cal = [r for r in cal if r["scenario"] == "central"]
assert max(float(r["continuous_proxy_fit_error_kY"]) for r in central_cal) < 1e-8
assert max(abs(float(r["exact_statutory_rounding_gap_kY"])) for r in central_cal) < 0.1
assert max(float(r["continuous_proxy_fit_error_kY"]) for r in cal) < 3.5

for r in scen:
    assert r["model_status"] == "SENSITIVITY_ONLY_NOT_IDENTIFIED"
    for f in [
        "pseudo_filer_weighted_mean_MTR",
        "taxable_income_weighted_mean_MTR",
        "income_tax_liability_weighted_mean_MTR",
    ]:
        x = float(r[f])
        assert 0.0 <= x <= 0.45, (r["decile"], r["scenario"], f, x)
    ps = sum(float(r[f]) for f in MTR_FIELDS)
    assert math.isclose(ps, 1.0, abs_tol=1e-9), (
        r["decile"], r["scenario"], ps
    )

for r in summ:
    assert r["structural_MTR_identified"] == "False"
    assert r["model_status"] == "SENSITIVITY_ONLY_NOT_IDENTIFIED"
    assert int(r["scenario_count"]) == 13
    assert "not point input" in r["recommended_use"]
    assert r["suppression_assumption"] == (
        "DROP_F71561_ROWS_WITH_SUPPRESSED_HOUSEHOLD_COUNT"
    )
    assert float(r["suppressed_count_share_upper_bound_exclusive"]) < 0.002
    assert r["target_model_alignment_status"] == "NAMED_CROSS_CONCEPT_SENSITIVITY"
    assert r["target_numeric_reconciliation_status"] == "NO_NUMERIC_TRANSFORM; CONCEPT_DIFFERENCE_NOT_IDENTIFIED"

assert sum(int(r["suppressed_leaf_rows_omitted"]) for r in summ) == 11
assert sum(int(r["suppressed_monetary_x_cells_without_numeric_bound"]) for r in summ) == 126
assert max(float(r["suppressed_count_share_upper_bound_exclusive"]) for r in summ) < 0.0016
assert any(r["suppression_residual_status"] == "MONETARY_X_IMPACT_NOT_IDENTIFIED" for r in summ)

# Deterministic generator check.
subprocess.run(
    [sys.executable, str(HERE / "run_pseudofiler_core.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "pseudo-filer core tests: OK "
    "(13 scenarios x 10 deciles; suppressed X rows explicit; published-imputed target semantics guarded)"
)
