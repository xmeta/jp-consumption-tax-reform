#!/usr/bin/env python3
if not __debug__:
    raise RuntimeError("optimized Python is not supported for executable tests")
from pathlib import Path
from decimal import Decimal
import csv
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PATHS = ROOT / "data/derived/vat_dynamic_fiscal_paths.csv"
SUMMARY = ROOT / "data/derived/vat_dynamic_fiscal_summary.csv"
D = Decimal


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rows = read(PATHS)
summary = {r["scenario_id"]: r for r in read(SUMMARY)}
modeled = {
    "current_8_10",
    "full_abolition_jgb",
    "full_abolition_income_tax",
    "full_abolition_asset_tax",
    "full_abolition_mixed",
}
assert len(rows) == 450
assert len(summary) == 8
for sid in modeled:
    rr = [r for r in rows if r["scenario_id"] == sid]
    assert len(rr) == 90
    assert len({r["assumption_set_id"] for r in rr}) == 9
    assert {int(r["year"]) for r in rr} == set(range(1, 11))

for r in rows:
    opening = D(r["opening_incremental_debt_yen"])
    redemptions = D(r["redemptions_yen"])
    net_new = D(r["net_new_issuance_yen"])
    gross_new = D(r["gross_new_issuance_yen"])
    closing = D(r["closing_incremental_debt_yen"])
    assert gross_new == redemptions + net_new
    assert closing == opening - redemptions + gross_new
    assert r["total_debt_gdp_status"] == "NOT_COMPUTED_BASELINE_TOTAL_DEBT_STOCK_OUTSIDE_THIS_INCREMENTAL_MODULE"
    assert r["market_feedback_status"] == "NOT_IDENTIFIED_INTEREST_AND_GDP_PATHS_ARE_EXOGENOUS_SENSITIVITIES"

for sid in ("current_8_10", "full_abolition_income_tax", "full_abolition_asset_tax"):
    assert all(D(r["closing_incremental_debt_yen"]) == 0 for r in rows if r["scenario_id"] == sid)
    assert all(D(r["incremental_interest_expense_yen"]) == 0 for r in rows if r["scenario_id"] == sid)

jgb_y1_g0 = [
    r for r in rows
    if r["scenario_id"] == "full_abolition_jgb"
    and r["year"] == "1"
    and r["nominal_gdp_growth"] == "0"
]
assert len(jgb_y1_g0) == 3
assert all(r["closing_incremental_debt_yen"] == "25021206715000" for r in jgb_y1_g0)
assert all(r["incremental_debt_gdp_ratio"] == "0.038948683327" for r in jgb_y1_g0)

by_key = {(r["scenario_id"], r["assumption_set_id"], r["year"]): r for r in rows}
for aid in {r["assumption_set_id"] for r in rows}:
    for year in range(1, 11):
        full = D(by_key[("full_abolition_jgb", aid, str(year))]["closing_incremental_debt_yen"])
        mixed = D(by_key[("full_abolition_mixed", aid, str(year))]["closing_incremental_debt_yen"])
        assert abs(mixed * 2 - full) < D("0.000001")

low = by_key[("full_abolition_jgb", "r01_g04", "10")]
high = by_key[("full_abolition_jgb", "r04_g00", "10")]
assert D(high["incremental_debt_gdp_ratio"]) > D(low["incremental_debt_gdp_ratio"])
assert D(high["cumulative_incremental_interest_yen"]) > D(low["cumulative_incremental_interest_yen"])
assert any(D(r["redemptions_yen"]) > 0 for r in rows if r["scenario_id"] == "full_abolition_jgb" and r["year"] != "1")

assert summary["full_abolition_jgb"]["static_fy2024_jgb_gdp_pct_benchmark"] == "3.894868333"
assert summary["full_abolition_jgb"]["dynamic_fiscal_status"] == "MODEL_CONTINGENT_INCREMENTAL_DEBT_PATH_SENSITIVITY"
assert summary["full_abolition_mixed"]["dynamic_fiscal_status"] == "MODEL_CONTINGENT_HALF_PRIMARY_JGB_SHARE_SENSITIVITY"
assert summary["full_abolition_income_tax"]["year10_incremental_debt_gdp_ratio_min"] == "0"
assert summary["full_abolition_asset_tax"]["year10_incremental_debt_gdp_ratio_max"] == "0"
for sid in ("reduced_5", "zero_rate_admin_retained", "full_abolition"):
    assert summary[sid]["modeled_assumption_sets"] == "0"
    assert summary[sid]["year10_incremental_debt_gdp_ratio_min"] == ""
    assert summary[sid]["identification_status"] == "NOT_MODELED"

subprocess.run(
    [sys.executable, str(ROOT / "research/vat_policy_integration/build_dynamic_fiscal_jgb_paths.py"), "--check"],
    cwd=ROOT,
    check=True,
)
print("dynamic fiscal/JGB tests: OK (stock-flow identity; 9 rate-growth sensitivities; static benchmark preserved; total debt not inferred)")
