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
assert len(rows) == 50
assert len(summary) == 8
for sid in modeled:
    rr = [r for r in rows if r["scenario_id"] == sid]
    assert len(rr) == 10
    assert {r["assumption_set_id"] for r in rr} == {"r02_g02"}
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

jgb_y1 = [r for r in rows if r["scenario_id"] == "full_abolition_jgb" and r["year"] == "1"]
assert len(jgb_y1) == 1
assert jgb_y1[0]["closing_incremental_debt_yen"] == "25021206715000"
assert jgb_y1[0]["effective_interest_rate"] == "0.02"
assert jgb_y1[0]["nominal_gdp_growth"] == "0.02"

by_key = {(r["scenario_id"], r["year"]): r for r in rows}
for year in range(1, 11):
    full = D(by_key[("full_abolition_jgb", str(year))]["closing_incremental_debt_yen"])
    mixed = D(by_key[("full_abolition_mixed", str(year))]["closing_incremental_debt_yen"])
    assert abs(mixed * 2 - full) < D("0.000001")
assert any(D(r["redemptions_yen"]) > 0 for r in rows if r["scenario_id"] == "full_abolition_jgb" and r["year"] != "1")

jgb = summary["full_abolition_jgb"]
assert jgb["static_fy2024_jgb_gdp_pct_benchmark"] == "3.894868333"
assert jgb["dynamic_fiscal_status"] == "MODEL_CONTINGENT_INCREMENTAL_DEBT_PATH_SENSITIVITY"
assert jgb["modeled_assumption_sets"] == "9"
assert jgb["reported_path_assumption_set_id"] == "r02_g02"
assert jgb["year10_incremental_debt_gdp_ratio_min"] == "0.275285239955"
assert jgb["year10_incremental_debt_gdp_ratio_max"] == "0.467622064324"
assert D(jgb["year10_cumulative_incremental_interest_yen_max"]) > D(jgb["year10_cumulative_incremental_interest_yen_min"])
assert summary["full_abolition_mixed"]["dynamic_fiscal_status"] == "MODEL_CONTINGENT_HALF_PRIMARY_JGB_SHARE_SENSITIVITY"
assert summary["full_abolition_mixed"]["year10_incremental_debt_gdp_ratio_min"] == "0.137642619977"
assert summary["full_abolition_mixed"]["year10_incremental_debt_gdp_ratio_max"] == "0.233811032162"
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
print("dynamic fiscal/JGB tests: OK (stock-flow identity; central 10-year paths; 9-set sensitivity envelope; static benchmark preserved)")
