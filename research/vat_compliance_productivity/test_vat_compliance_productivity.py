#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv, subprocess, sys, math
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[2]
S=ROOT/"data/derived/vat_compliance_productivity_sensitivity.csv"
R=ROOT/"data/derived/vat_compliance_productivity_regime_summary.csv"
REG=ROOT/"research/vat_compliance_productivity/regimes.csv"
AX=ROOT/"research/vat_compliance_productivity/sensitivity_axes.csv"
DESIGN=ROOT/"research/vat_compliance_productivity/firm_level_identification_design.csv"
SOURCE_CATALOG=ROOT/"data/source_catalog.csv"

def read(p):
    with p.open(encoding="utf-8",newline="") as f: return list(csv.DictReader(f))


def xlsx_xml_text(path):
    with ZipFile(path) as zf:
        return "\n".join(
            zf.read(name).decode("utf-8", errors="ignore")
            for name in zf.namelist()
            if name.endswith(".xml")
        )

rows=read(S); summary={r["regime_id"]:r for r in read(R)}
regimes={r["regime_id"]:r for r in read(REG)}
axes={r["parameter_id"]:r for r in read(AX)}
designs=read(DESIGN)
sources={r["source_id"] for r in read(SOURCE_CATALOG)}

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


# The official schema snapshots used for linkage feasibility must retain the
# exact identifying/output fields on which the design relies.
theme2 = xlsx_xml_text(ROOT / "data/raw/vat_linkage/nta_joint_research_theme2_sample.xlsx")
theme4 = xlsx_xml_text(ROOT / "data/raw/vat_linkage/nta_joint_research_theme4_sample.xlsx")
assert "法人番号" in theme2 and "売上金額" in theme2 and "主業種番号" in theme2
assert "法人番号" in theme4 and "課税標準額" in theme4 and "控除対象仕入税額" in theme4
invoice_rule = (ROOT / "data/raw/vat_linkage/nta_invoice_registration_number_rule.html").read_text(encoding="utf-8", errors="ignore")
assert "T＋法人番号" in invoice_rule or "T+法人番号" in invoice_rule

# Issue #47 identification bridge: design evidence must not silently promote
# any current national stress parameter to identified status.
assert len(designs) == 5
assert [int(r["design_rank"]) for r in designs] == [1, 2, 3, 4, 5]
assert {r["design_id"] for r in designs} == {
    "METI_BURDEN_X_BSBSA_SECURE_LINK",
    "PROSPECTIVE_VAT_BURDEN_REDEPLOYMENT_PANEL",
    "NTA_THEME5_2_CORP_VAT_PANEL",
    "INVOICE_REGISTRY_X_BSBSA",
    "NTA_THEME5_2_X_EXTERNAL_FIRM_STATS",
}
assert max(int(r["dimensions_shrunk_count_if_success"]) for r in designs) == 2
assert max(int(r["national_dimensions_identified_count_if_success"]) for r in designs) == 1
assert all(int(r["national_dimensions_identified_count_if_success"]) < 3 for r in designs)
assert next(r for r in designs if r["design_id"] == "NTA_THEME5_2_CORP_VAT_PANEL")["c_vat_after_success"].startswith("UNCHANGED_NOT_IDENTIFIED")
assert next(r for r in designs if r["design_id"] == "NTA_THEME5_2_CORP_VAT_PANEL")["rho_after_success"].startswith("UNCHANGED_NOT_IDENTIFIED")
assert next(r for r in designs if r["design_id"] == "METI_BURDEN_X_BSBSA_SECURE_LINK")["feasibility"] == "BLOCKED_ON_HISTORIC_BURDEN_MICRODATA_LINK_KEY"
assert next(r for r in designs if r["design_id"] == "INVOICE_REGISTRY_X_BSBSA")["feasibility"] == "TECHNICAL_LINK_KEY_CONFIRMED_MICRODATA_IDENTIFIER_APPROVAL_PENDING"
for r in designs:
    ids = [x for x in r["source_ids"].split(";") if x]
    assert ids and set(ids) <= sources, (r["design_id"], set(ids) - sources)

subprocess.run([
 sys.executable,
 str(ROOT/"research/vat_compliance_productivity/run_vat_compliance_productivity.py"),
 "--check"],cwd=ROOT,check=True)

print("VAT compliance-productivity tests: OK (4 regimes x 300 stress points; Issue #47 linkage design guarded; no national identification promotion)")
