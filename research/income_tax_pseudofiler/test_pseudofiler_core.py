#!/usr/bin/env python3
from pathlib import Path
import csv
import math
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

SCENARIOS = {
    "central", "f71911_topcode10", "size_lower", "size_upper",
    "business_proportional", "other_wage_split2",
    "no_social_deduction_proxy", "pension_head_merge",
    "pension_member_split",
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

assert len(cal) == 90
assert len(scen) == 90
assert len(summ) == 10
assert len(groups) == 40
assert {int(r["decile"]) for r in summ} == set(range(1, 11))
assert {r["scenario"] for r in scen} == SCENARIOS

for d in range(1, 11):
    assert len([r for r in scen if int(r["decile"]) == d]) == 9

for r in cal:
    assert r["model_status"] == "SENSITIVITY_ONLY_NOT_IDENTIFIED"
    assert r["target_inside_logical_bounds"] == "True"
    assert float(r["nuisance_income_scale"]) > 0
    assert float(r["continuous_proxy_fit_error_kY"]) >= 0

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
    assert int(r["scenario_count"]) == 9
    assert "not point input" in r["recommended_use"]

# Deterministic generator check.
subprocess.run(
    [sys.executable, str(HERE / "run_pseudofiler_core.py"), "--check"],
    cwd=ROOT,
    check=True,
)

print(
    "pseudo-filer core tests: OK "
    "(9 scenarios x 10 deciles; central moments matched; MTR shares coherent)"
)
