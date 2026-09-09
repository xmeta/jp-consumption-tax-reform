#!/usr/bin/env python3
"""Run a compliance-only VAT abolition productivity sensitivity module.

This module intentionally excludes the ordinary VAT-demand channel, financing,
household incidence and macro feedbacks.  Its job is narrower: keep the
institutional abolition dividend separate from a statutory rate reduction.
"""
from pathlib import Path
import argparse, csv, io, itertools, math

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
REGIMES=HERE/"regimes.csv"
AXES=HERE/"sensitivity_axes.csv"
IDENT=ROOT/"data/derived/vat_compliance_identification_status.csv"
OUT=ROOT/"data/derived/vat_compliance_productivity_sensitivity.csv"
SUMMARY=ROOT/"data/derived/vat_compliance_productivity_regime_summary.csv"

def read(p):
    with p.open(encoding="utf-8",newline="") as f: return list(csv.DictReader(f))

def render(rows):
    b=io.StringIO(); w=csv.DictWriter(b,fieldnames=list(rows[0]),lineterminator="\n")
    w.writeheader(); w.writerows(rows); return b.getvalue()

def fmt(x):
    if isinstance(x,str): return x
    return f"{x:.12f}".rstrip("0").rstrip(".")

def parse_axes():
    raw={r["parameter_id"]:r for r in read(AXES)}
    needed=[
      "vat_admin_resource_share_of_baseline_output",
      "productive_redeployment_fraction",
      "allocative_efficiency_dividend_share",
      "transition_years",
    ]
    assert set(raw)==set(needed)
    for r in raw.values():
        assert r["identification_status"]=="STRESS_TEST_NOT_EMPIRICAL_BOUND"
    vals={}
    for k,r in raw.items():
        if k=="transition_years":
            vals[k]=[int(x) for x in r["values"].split(";")]
        else:
            vals[k]=[float(x) for x in r["values"].split(";")]
    return vals

def build():
    ident={r["quantity"]:r for r in read(IDENT)}
    assert ident["vat_specific_real_resource_cost_share_of_output"]["status"]=="NOT_IDENTIFIED"
    assert ident["productive_redeployment_fraction_rho"]["status"]=="NOT_IDENTIFIED"
    assert ident["allocative_efficiency_dividend"]["status"]=="NOT_IDENTIFIED"
    assert ident["compliance_savings_one_for_one_gdp"]["status"]=="PROHIBITED"
    assert ident["income_gini_and_FGT2_effect"]["status"]=="NOT_MODELED_PHASE1"
    assert ident["fiscal_debt_effect"]["model_use"]=="FINANCING_CHANNEL_SEPARATE"

    regimes=read(REGIMES)
    assert len(regimes)==4
    by={r["regime_id"]:r for r in regimes}
    assert set(by)=={
      "current_8_10_admin_retained",
      "reduced_5_admin_retained",
      "zero_rate_admin_retained",
      "full_vat_abolition",
    }
    for rid in ("current_8_10_admin_retained","reduced_5_admin_retained","zero_rate_admin_retained"):
        assert by[rid]["vat_admin_state"]=="retained"
        assert by[rid]["invoice_system_state"]=="retained"
        assert float(by[rid]["vat_admin_removal_fraction"])==0
    assert by["full_vat_abolition"]["vat_admin_state"]=="abolished"
    assert by["full_vat_abolition"]["invoice_system_state"]=="abolished"
    assert float(by["full_vat_abolition"]["vat_admin_removal_fraction"])==1
    # The decisive institutional distinction.
    assert float(by["zero_rate_admin_retained"]["vat_standard_rate"])==0
    assert float(by["full_vat_abolition"]["vat_standard_rate"])==0
    assert by["zero_rate_admin_retained"]["vat_admin_state"] != by["full_vat_abolition"]["vat_admin_state"]

    a=parse_axes()
    combos=list(itertools.product(
      a["vat_admin_resource_share_of_baseline_output"],
      a["productive_redeployment_fraction"],
      a["allocative_efficiency_dividend_share"],
      a["transition_years"],
    ))
    rows=[]
    for reg in regimes:
        removal=float(reg["vat_admin_removal_fraction"])
        for c_vat,rho,a_alloc,years in combos:
            released=removal*c_vat
            compliance=released*rho
            allocation=removal*a_alloc
            level=compliance+allocation
            annualized=(1+level)**(1/years)-1
            rows.append({
              "regime_id":reg["regime_id"],
              "vat_standard_rate":reg["vat_standard_rate"],
              "vat_reduced_rate":reg["vat_reduced_rate"],
              "vat_admin_state":reg["vat_admin_state"],
              "invoice_system_state":reg["invoice_system_state"],
              "vat_admin_removal_fraction":fmt(removal),
              "vat_admin_resource_share_of_baseline_output":fmt(c_vat),
              "productive_redeployment_fraction":fmt(rho),
              "allocative_efficiency_dividend_share":fmt(a_alloc),
              "transition_years":years,
              "released_vat_admin_resource_share":fmt(released),
              "compliance_productivity_level_effect":fmt(compliance),
              "allocative_efficiency_level_effect":fmt(allocation),
              "total_institutional_level_effect":fmt(level),
              "annualized_transition_growth_contribution":fmt(annualized),
              "ordinary_vat_demand_effect":"0",
              "ordinary_vat_demand_effect_status":"EXCLUDED_FROM_COMPLIANCE_MODULE",
              "income_gini_effect_status":"NOT_MODELED_PHASE1",
              "wealth_gini_effect_status":"NOT_MODELED_PHASE1",
              "fgt2_effect_status":"NOT_MODELED_PHASE1",
              "fiscal_balance_effect_status":"FINANCING_CHANNEL_SEPARATE",
              "debt_gdp_effect_status":"FINANCING_CHANNEL_SEPARATE",
              "identification_status":"MODEL_CONTINGENT_STRESS_TEST_ONLY",
            })

    # Guard architecture, not just a few selected rows.
    for r in rows:
        if r["vat_admin_state"]=="retained":
            assert float(r["released_vat_admin_resource_share"])==0
            assert float(r["compliance_productivity_level_effect"])==0
            assert float(r["allocative_efficiency_level_effect"])==0
            assert float(r["total_institutional_level_effect"])==0
            assert float(r["annualized_transition_growth_contribution"])==0
        assert float(r["ordinary_vat_demand_effect"])==0

    summary=[]
    for reg in regimes:
        rr=[r for r in rows if r["regime_id"]==reg["regime_id"]]
        levels=[float(r["total_institutional_level_effect"]) for r in rr]
        growth=[float(r["annualized_transition_growth_contribution"]) for r in rr]
        summary.append({
          "regime_id":reg["regime_id"],
          "vat_admin_state":reg["vat_admin_state"],
          "grid_points":len(rr),
          "minimum_total_institutional_level_effect":fmt(min(levels)),
          "maximum_total_institutional_level_effect":fmt(max(levels)),
          "minimum_annualized_transition_growth_contribution":fmt(min(growth)),
          "maximum_annualized_transition_growth_contribution":fmt(max(growth)),
          "range_status":"STRESS_TEST_RANGE_NOT_EMPIRICAL_BOUND",
          "demand_channel_status":"EXCLUDED_FROM_COMPLIANCE_MODULE",
          "distribution_channel_status":"NOT_MODELED_PHASE1",
          "financing_channel_status":"SEPARATE_NOT_MODELED",
        })
    return rows,summary
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--check",action="store_true"); args=ap.parse_args()
    rows,summary=build()
    outs=[(OUT,render(rows)),(SUMMARY,render(summary))]
    if args.check:
        stale=[]
        for p,e in outs:
            if not p.exists() or p.read_text(encoding="utf-8")!=e: stale.append(str(p.relative_to(ROOT)))
        if stale: raise SystemExit("stale generated artifacts: "+", ".join(stale))
        print(
          "VAT compliance-productivity sensitivity: current "
          f"({len(rows)} rows; 0% admin-retained has zero institutional dividend; abolition separate)"
        )
    else:
        for p,e in outs:
            p.parent.mkdir(parents=True,exist_ok=True); p.write_text(e,encoding="utf-8")
            print(f"wrote {p.relative_to(ROOT)}: {len(rows) if p==OUT else len(summary)} rows")

if __name__=="__main__": main()
