#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv, subprocess, sys, math

ROOT=Path(__file__).resolve().parents[2]
S=ROOT/"data/derived/vat_compliance_productivity_sensitivity.csv"
R=ROOT/"data/derived/vat_compliance_productivity_regime_summary.csv"
REG=ROOT/"research/vat_compliance_productivity/regimes.csv"
AX=ROOT/"research/vat_compliance_productivity/sensitivity_axes.csv"

def read(p):
    with p.open(encoding="utf-8",newline="") as f: return list(csv.DictReader(f))

rows=read(S); summary={r["regime_id"]:r for r in read(R)}
regimes={r["regime_id"]:r for r in read(REG)}
axes={r["parameter_id"]:r for r in read(AX)}

assert len(rows)==1200
assert all(r["identification_status"]=="MODEL_CONTINGENT_STRESS_TEST_ONLY" for r in rows)
assert all(r["ordinary_vat_demand_effect_status"]=="EXCLUDED_FROM_COMPLIANCE_MODULE" for r in rows)
assert all(float(r["ordinary_vat_demand_effect"])==0 for r in rows)
assert all(r["income_gini_effect_status"]=="NOT_MODELED_PHASE1" for r in rows)
assert all(r["fgt2_effect_status"]=="NOT_MODELED_PHASE1" for r in rows)
assert all(r["fiscal_balance_effect_status"]=="FINANCING_CHANNEL_SEPARATE" for r in rows)
assert all(r["debt_gdp_effect_status"]=="FINANCING_CHANNEL_SEPARATE" for r in rows)

retained={"current_8_10_admin_retained","reduced_5_admin_retained","zero_rate_admin_retained"}
for rid in retained:
    rr=[r for r in rows if r["regime_id"]==rid]
    assert len(rr)==300
    assert all(float(r["vat_admin_removal_fraction"])==0 for r in rr)
    assert all(float(r["released_vat_admin_resource_share"])==0 for r in rr)
    assert all(float(r["compliance_productivity_level_effect"])==0 for r in rr)
    assert all(float(r["allocative_efficiency_level_effect"])==0 for r in rr)
    assert all(float(r["total_institutional_level_effect"])==0 for r in rr)
    assert all(float(r["annualized_transition_growth_contribution"])==0 for r in rr)

abol=[r for r in rows if r["regime_id"]=="full_vat_abolition"]
assert len(abol)==300
for r in abol:
    c=float(r["vat_admin_resource_share_of_baseline_output"])
    rho=float(r["productive_redeployment_fraction"])
    alloc=float(r["allocative_efficiency_dividend_share"])
    years=int(r["transition_years"])
    expected=c*rho+alloc
    assert abs(float(r["compliance_productivity_level_effect"])-c*rho)<1e-12
    assert abs(float(r["allocative_efficiency_level_effect"])-alloc)<1e-12
    assert abs(float(r["total_institutional_level_effect"])-expected)<1e-12
    annual=(1+expected)**(1/years)-1
    assert abs(float(r["annualized_transition_growth_contribution"])-annual)<1e-11
# 0% rate with administration retained is institutionally distinct from abolition.
z=regimes["zero_rate_admin_retained"]; a=regimes["full_vat_abolition"]
assert float(z["vat_standard_rate"])==float(a["vat_standard_rate"])==0
assert z["vat_admin_state"]=="retained"
assert a["vat_admin_state"]=="abolished"
assert z["invoice_system_state"]=="retained"
assert a["invoice_system_state"]=="abolished"

# Match identical stress parameters and prove the compliance-only outcome differs.
key=("0.005","1","0.001","1")
def pick(rid):
    for r in rows:
        if r["regime_id"]==rid and (
          r["vat_admin_resource_share_of_baseline_output"],
          r["productive_redeployment_fraction"],
          r["allocative_efficiency_dividend_share"],
          r["transition_years"])==key:
            return r
    raise AssertionError(rid)
rz=pick("zero_rate_admin_retained"); ra=pick("full_vat_abolition")
assert float(rz["total_institutional_level_effect"])==0
assert float(ra["total_institutional_level_effect"])==0.006

assert len(summary)==4
for rid in retained:
    assert summary[rid]["minimum_total_institutional_level_effect"]=="0"
    assert summary[rid]["maximum_total_institutional_level_effect"]=="0"
assert summary["full_vat_abolition"]["minimum_total_institutional_level_effect"]=="0"
assert summary["full_vat_abolition"]["maximum_total_institutional_level_effect"]=="0.006"
assert summary["full_vat_abolition"]["range_status"]=="STRESS_TEST_RANGE_NOT_EMPIRICAL_BOUND"

# Every free axis is explicitly non-identified stress testing, never an empirical bound.
assert set(axes)=={
 "vat_admin_resource_share_of_baseline_output",
 "productive_redeployment_fraction",
 "allocative_efficiency_dividend_share",
 "transition_years",
}
assert all(r["identification_status"]=="STRESS_TEST_NOT_EMPIRICAL_BOUND" for r in axes.values())

subprocess.run([
 sys.executable,
 str(ROOT/"research/vat_compliance_productivity/run_vat_compliance_productivity.py"),
 "--check"],cwd=ROOT,check=True)

print("VAT compliance-productivity tests: OK (4 regimes x 300 stress points; 0% retained != institutional abolition; demand/distribution/financing separated)")
