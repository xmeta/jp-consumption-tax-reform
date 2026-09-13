#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv, subprocess, sys, math, re
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[2]
S=ROOT/"data/derived/vat_compliance_productivity_sensitivity.csv"
R=ROOT/"data/derived/vat_compliance_productivity_regime_summary.csv"
REG=ROOT/"research/vat_compliance_productivity/regimes.csv"
AX=ROOT/"research/vat_compliance_productivity/sensitivity_axes.csv"
DESIGN=ROOT/"research/vat_compliance_productivity/firm_level_identification_design.csv"
SOURCE_CATALOG=ROOT/"data/source_catalog.csv"
ACCESS_AUDIT=ROOT/"research/vat_compliance_productivity/firm_level_linkage_access_audit.csv"
LIT_AUDIT=ROOT/"research/vat_compliance_productivity/invoice_2023_causal_literature_audit.csv"
INVOICE_DESIGN=ROOT/"research/vat_compliance_productivity/invoice_2023_natural_experiment_design.csv"
TDB_ACCESS=ROOT/"research/vat_compliance_productivity/tdb_caree_invoice_causal_access_audit.csv"
PREANALYSIS_PLAN=ROOT/"research/vat_compliance_productivity/invoice_2023_preanalysis_plan.adoc"
TDB_INQUIRY=ROOT/"research/vat_compliance_productivity/tdb_caree_invoice_causal_inquiry.adoc"

def read(p):
    with p.open(encoding="utf-8",newline="") as f: return list(csv.DictReader(f))


def xlsx_xml_text(path):
    with ZipFile(path) as zf:
        return "\n".join(
            zf.read(name).decode("utf-8", errors="ignore")
            for name in zf.namelist()
            if name.endswith(".xml")
        )


def emicro_result_count(path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r'<span style="padding-inline: var\(--gap-1\);">\s*(\d+)\s*件', text)
    assert match, path
    return int(match.group(1)), text

rows=read(S); summary={r["regime_id"]:r for r in read(R)}
regimes={r["regime_id"]:r for r in read(REG)}
axes={r["parameter_id"]:r for r in read(AX)}
designs=read(DESIGN)
sources={r["source_id"] for r in read(SOURCE_CATALOG)}
access_audit={r["audit_item"]:r for r in read(ACCESS_AUDIT)}
invoice_lit=read(LIT_AUDIT)
invoice_design=read(INVOICE_DESIGN)
tdb_access=read(TDB_ACCESS)
preanalysis_plan=PREANALYSIS_PLAN.read_text(encoding="utf-8")
tdb_inquiry=TDB_INQUIRY.read_text(encoding="utf-8")

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
historic = next(r for r in designs if r["design_id"] == "METI_BURDEN_X_BSBSA_SECURE_LINK")
assert historic["feasibility"] == "STOP_STANDARD_EMICRO_RETROSPECTIVE_LINKAGE"
assert "NOT_ESTABLISHED_FROM_PUBLIC_MATERIALS" in historic["linkage_key"]
assert next(r for r in designs if r["design_id"] == "INVOICE_REGISTRY_X_BSBSA")["feasibility"] == "TECHNICAL_LINK_KEY_CONFIRMED_MICRODATA_IDENTIFIER_APPROVAL_PENDING"

# Issue #82 access-route resolution.  Zero-result historic-survey queries are
# paired with a positive control on the same official catalog surfaces.
query_cases = [
    ("emicro_2026_remote_sme_tax_survey_query.html", "中小企業税制に関するアンケート調査", 0),
    ("emicro_2026_onsite_sme_tax_survey_query.html", "中小企業税制に関するアンケート調査", 0),
    ("emicro_2026_remote_bsbsa_query.html", "企業活動基本調査", 32),
    ("emicro_2026_onsite_bsbsa_query.html", "企業活動基本調査", 32),
]
for name, keyword, expected in query_cases:
    count, html = emicro_result_count(ROOT / "data/raw/vat_linkage" / name)
    assert count == expected, (name, count)
    assert f'value="{keyword}"' in html
assert access_audit["remote_catalog_eligibility"]["status"] == "NOT_LISTED_STANDARD_EMICRO_REMOTE"
assert access_audit["onsite_catalog_eligibility"]["status"] == "NOT_LISTED_STANDARD_EMICRO_ONSITE"
assert access_audit["remote_positive_control"]["observed_value"] == "32 records"
assert access_audit["onsite_positive_control"]["observed_value"] == "32 records"
assert access_audit["stable_firm_link_key"]["status"] == "NOT_ESTABLISHED_FROM_PUBLIC_MATERIALS"
assert access_audit["cross_survey_linkage_permission"]["status"] == "NOT_ESTABLISHED"
assert access_audit["route_decision"]["status"] == "STOP_STANDARD_EMICRO_RETROSPECTIVE_LINKAGE"
assert access_audit["national_parameter_status"]["status"] == "NOT_IDENTIFIED"
for r in designs:
    ids = [x for x in r["source_ids"].split(";") if x]
    assert ids and set(ids) <= sources, (r["design_id"], set(ids) - sources)

# Issue #111: direct invoice-era survey evidence remains descriptive, while
# the ranked causal frontier rejects post-treatment exposure and stale 2026 rules.
assert len(invoice_lit) == 8
frontier = invoice_lit[0]
assert frontier["evidence_id"] == "SEARCH-FRONTIER-2026-09-13"
assert frontier["causal_identification_status"] == "NO_DIRECT_QUASI_EXPERIMENTAL_STUDY_FOUND_IN_BOUNDED_SEARCH"
assert "not a proof" in frontier["search_or_scope_note"].lower()
for r in invoice_lit:
    ids = [x for x in r["source_ids"].split(";") if x]
    assert ids and set(ids) <= sources, (r["evidence_id"], set(ids) - sources)
for r in invoice_lit:
    if r["direct_2023_invoice_effect"] == "YES_DIRECT_EVENT_CONTEXT":
        assert "NOT_CAUSAL" in r["causal_identification_status"] or "NOT_2023_EFFECT" in r["causal_identification_status"]

koizumi=next(r for r in invoice_lit if r["evidence_id"]=="KOIZUMI-2026-TAX-POLICY-NETWORK-CASCADE")
assert koizumi["direct_2023_invoice_effect"] == "NO"
assert koizumi["causal_identification_status"] == "CAUSAL_NETWORK_TAX_POLICY_TEMPLATE_NOT_2023_INVOICE_EFFECT"
assert koizumi["source_ids"] == "RIETI-2024-TAX-POLICY-PRODUCTION-NETWORKS"
assert "not its treatment-effect magnitude" in koizumi["search_or_scope_note"].lower()

assert [int(r["route_rank"]) for r in tdb_access] == [1,2,3]
by_route={r["route_id"]:r for r in tdb_access}
primary_route=by_route["TDB_CAREE_RESEARCH_ROUTE"]
assert primary_route["decision"] == "PRIMARY_PROVIDER_INQUIRY"
assert primary_route["identification_value"] == "HIGHEST"
assert "before treatment" in primary_route["network_coverage"].lower()
assert "pre-treatment network" in primary_route["next_action"].lower()
assert "provider confirmation" in primary_route["current_2026_status"].lower()
assert "deterministic" in primary_route["deterministic_invoice_link"].lower()
commercial=by_route["TDB_COMMERCIAL_TRANSACTION_ROUTE"]
assert "JPY 250,000" in commercial["current_cost_or_access_note"]
assert "JPY 10" in commercial["current_cost_or_access_note"]
assert "current-only network" in commercial["stop_rule"].lower()
assert by_route["BSBSA_PLUS_PUBLIC_INVOICE_WITHOUT_NETWORK"]["identification_value"] == "INSUFFICIENT_ALONE_FOR_RANK1_DESIGN"
for r in tdb_access:
    ids=[x for x in r["source_ids"].split(";") if x]
    assert ids and set(ids) <= sources, (r["route_id"], set(ids)-sources)

assert "caree@econ.hit-u.ac.jp" in tdb_inquiry
assert "https://www7.econ.hit-u.ac.jp/tdb-caree/qualification/" in tdb_inquiry
assert "has not been submitted" in tdb_inquiry
assert "submission route" in tdb_inquiry.lower()
assert "current eligibility" in tdb_inquiry.lower()

for required in (
    "supplier-customer graph observed no later than 2023-09-30",
    "TRANSITION_PARTIAL_EXPOSURE",
    "ANTICIPATION_WINDOW",
    "2022-10-01",
    "[0.05, 0.95]",
    "common support",
    "pre-trend",
    "placebo",
    "Network freeze",
    "NOT_IDENTIFIED",
):
    assert required.lower() in preanalysis_plan.lower(), required
for forbidden_rule in (
    "qualified-invoice registration observed after the policy was announced or implemented",
    "supplier composition measured after 2023-10-01",
    "current supplier networks backcast to 2023",
):
    assert forbidden_rule in preanalysis_plan
assert "Low-exposure firms were also subject to the invoice system" in preanalysis_plan
assert "not the average effect of introducing the system nationwide" in preanalysis_plan

assert [int(r["design_rank"]) for r in invoice_design] == [1, 2, 3, 4, 5]
by_invoice_design={r["design_id"]:r for r in invoice_design}
assert set(by_invoice_design) == {
    "PRE2023_SUPPLIER_EXPOSURE_X_2023_DID",
    "2026_LEGAL_FORM_RELIEF_DIFFERENTIAL_DID",
    "2026_UNREGISTERED_SUPPLIER_CREDIT_STEP_DID",
    "INVOICE_REGISTRY_X_BSBSA_ADOPTION_EVENT_STUDY",
    "VAT_10M_THRESHOLD_DIFF_IN_DISCONTINUITIES_2023",
}
primary=by_invoice_design["PRE2023_SUPPLIER_EXPOSURE_X_2023_DID"]
assert primary["publicly_executable_2026_09"] == "NO"
assert "pre-2023" in primary["treatment_or_exposure"].lower()
assert "post-treatment registration" in primary["stop_rule"].lower()
step=by_invoice_design["2026_UNREGISTERED_SUPPLIER_CREDIT_STEP_DID"]
assert "80% to 70%" in step["policy_variation"]
assert "80-to-50" in step["stop_rule"]
assert "NTA-2026-INVOICE-REFORM" in step["source_ids"]
registry=by_invoice_design["INVOICE_REGISTRY_X_BSBSA_ADOPTION_EVENT_STUDY"]
assert registry["identification_strength"] == "DIAGNOSTIC_ONLY_UNLESS_EXOGENOUS_VARIATION_ADDED"
assert "naive" in registry["stop_rule"].lower()
for r in invoice_design:
    ids = [x for x in r["source_ids"].split(";") if x]
    assert ids and set(ids) <= sources, (r["design_id"], set(ids) - sources)

subprocess.run([
 sys.executable,
 str(ROOT/"research/vat_compliance_productivity/run_vat_compliance_productivity.py"),
 "--check"],cwd=ROOT,check=True)

print("VAT compliance-productivity tests: OK (4 regimes x 300 stress points; Issues #47/#82 linkage design/access stop guarded; no national identification promotion)")
