#!/usr/bin/env python3
"""Extract observed Japan VAT-compliance evidence without turning it into GDP gains."""
from pathlib import Path
import argparse, csv, io, re
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/source_catalog.csv"
OUT_EVIDENCE = ROOT / "data/derived/vat_compliance_observed_evidence.csv"
OUT_IDENT = ROOT / "data/derived/vat_compliance_identification_status.csv"

def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def render(rows):
    b=io.StringIO()
    w=csv.DictWriter(b,fieldnames=list(rows[0]),lineterminator="\n")
    w.writeheader(); w.writerows(rows)
    return b.getvalue()

def norm(s):
    return re.sub(r"\s+", "", s or "")

def evidence(metric_id, value, unit, evidence_type, population, sample_n,
             source_id, locator, status, permission, note):
    return {
        "metric_id":metric_id,"value":value,"unit":unit,
        "evidence_type":evidence_type,"population":population,
        "sample_n":sample_n,"source_id":source_id,"source_locator":locator,
        "identification_status":status,"model_calibration_permission":permission,
        "note":note,
    }

def require_tokens(text, tokens, label):
    n=norm(text)
    for token in tokens:
        if norm(token) not in n:
            raise RuntimeError(f"{label}: missing token {token!r}")

def build():
    cat={r["source_id"]:r for r in read_csv(CATALOG)}
    required=[
      "JCCI-2024-INVOICE-BACKOFFICE-SURVEY",
      "JCCI-2025-INVOICE-SURVEY",
      "RIETI-2019-VAT-COMPLIANCE-FIRM-GROWTH",
      "RIETI-2021-SME-VAT-COMPLIANCE",
      "RIETI-2021-QUANT-TAX-COMPLIANCE-COST",
      "MOF-CONSUMPTION-TAX-SME-EXEMPTION-THRESHOLD",
      "NTA-CONSUMPTION-TAX-BASIC",
      "NTA-INVOICE-SYSTEM-OVERVIEW",
    ]
    for sid in required:
        if sid not in cat: raise RuntimeError(f"missing catalog source {sid}")
        p=ROOT/cat[sid]["raw_file"]
        if not p.exists(): raise RuntimeError(f"missing raw source {p}")

    j24=PdfReader(ROOT/cat["JCCI-2024-INVOICE-BACKOFFICE-SURVEY"]["raw_file"])
    j25=PdfReader(ROOT/cat["JCCI-2025-INVOICE-SURVEY"]["raw_file"])
    p24=j24.pages[10].extract_text() or ""
    p25=j25.pages[12].extract_text() or ""
    p25size=j25.pages[15].extract_text() or ""
    p24size=j24.pages[18].extract_text() or ""

    require_tokens(p24, ["n=2,365","48.8%","82.2%","66.0%","57.8%","54.3%","46.6%","44.1%"],"JCCI2024 p10")
    require_tokens(p25, ["n=2,137","45.8","73.4","39.7","34.5","28.7","27.2","74.8","63.7","55.1","53.2"],"JCCI2025 p12")
    require_tokens(p25size, ["n=907","79.4%","23.6%","76.4%","62.2%","37.0%","63.0%","40.1%","52.3%","47.7%","14.5%","71.0%","29.0%"],"JCCI2025 p15")
    require_tokens(p24size, ["n=1,213","92.0%","21.9%","78.1%"],"JCCI2024 p18")

    r19=PdfReader(ROOT/cat["RIETI-2019-VAT-COMPLIANCE-FIRM-GROWTH"]["raw_file"])
    r21=PdfReader(ROOT/cat["RIETI-2021-SME-VAT-COMPLIANCE"]["raw_file"])
    rquant=PdfReader(ROOT/cat["RIETI-2021-QUANT-TAX-COMPLIANCE-COST"]["raw_file"])
    t19="\n".join((p.extract_text() or "") for p in r19.pages)
    t21="\n".join((p.extract_text() or "") for p in r21.pages)
    tq="\n".join((p.extract_text() or "") for p in rquant.pages)
    require_tokens(t19,["bunching","compliance cost is higher","10 million JPY"],"RIETI19")
    require_tokens(t21,["compliance costs rather than tax rates","10 million JPY"],"RIETI21")
    require_tokens(tq,["0.06％","0.17%","消費税","外部委託費用"],"RIETI21-P018")

    mof=(ROOT/cat["MOF-CONSUMPTION-TAX-SME-EXEMPTION-THRESHOLD"]["raw_file"]).read_text(encoding="utf-8",errors="ignore")
    nta_basic=(ROOT/cat["NTA-CONSUMPTION-TAX-BASIC"]["raw_file"]).read_text(encoding="utf-8",errors="ignore")
    nta_inv=(ROOT/cat["NTA-INVOICE-SYSTEM-OVERVIEW"]["raw_file"]).read_text(encoding="utf-8",errors="ignore")
    # HTML tokens deliberately broad enough to survive markup changes in saved snapshots.
    for text,tokens,label in [
      (mof,["1,000万円","免税"],"MOF threshold"),
      (nta_basic,["仕入","申告"],"NTA basic"),
      (nta_inv,["適格請求書","仕入税額控除"],"NTA invoice"),
    ]:
        require_tokens(text,tokens,label)

    rows=[]
    # JCCI invoice burden incidence. These are response shares, not resource shares.
    rows += [
      evidence("jcci2024_invoice_cost_increase_share","0.488","ratio","SURVEY_RESPONSE_SHARE",
               "invoice issuers responding to burden question","2365",
               "JCCI-2024-INVOICE-BACKOFFICE-SURVEY","PDF p.11 / printed p.10",
               "OBSERVED_SURVEY_RESPONSE","INCIDENCE_ONLY_NOT_RESOURCE_SHARE",
               "Share reporting increased non-tax costs after invoice-system introduction."),
      evidence("jcci2024_invoice_admin_burden_increase_share","0.822","ratio","SURVEY_RESPONSE_SHARE",
               "invoice issuers responding to burden question","2365",
               "JCCI-2024-INVOICE-BACKOFFICE-SURVEY","PDF p.11 / printed p.10",
               "OBSERVED_SURVEY_RESPONSE","INCIDENCE_ONLY_NOT_RESOURCE_SHARE",
               "Share reporting increased administrative burden."),
      evidence("jcci2025_invoice_cost_increase_share","0.458","ratio","SURVEY_RESPONSE_SHARE",
               "invoice issuers responding to burden question","2137",
               "JCCI-2025-INVOICE-SURVEY","PDF p.13 / printed p.12",
               "OBSERVED_SURVEY_RESPONSE","INCIDENCE_ONLY_NOT_RESOURCE_SHARE",
               "Share reporting increased cost excluding the tax burden itself."),
      evidence("jcci2025_invoice_admin_burden_increase_share","0.734","ratio","SURVEY_RESPONSE_SHARE",
               "invoice issuers responding to burden question","2137",
               "JCCI-2025-INVOICE-SURVEY","PDF p.13 / printed p.12",
               "OBSERVED_SURVEY_RESPONSE","INCIDENCE_ONLY_NOT_RESOURCE_SHARE",
               "Share reporting increased administrative burden."),
    ]
    # Selected burden items, conditional on reporting an increase.
    for metric,val,note in [
      ("jcci2024_supplier_registration_check_share","0.660","Supplier registration-status confirmation/management."),
      ("jcci2024_registration_number_check_share","0.578","Invoice registration-number check on receipt."),
      ("jcci2024_required_fields_check_share","0.543","Required invoice fields check on issuance."),
      ("jcci2024_tax_rate_amount_check_share","0.466","Consumption-tax rate/amount check on receipt."),
      ("jcci2024_invoice_storage_share","0.441","Invoice storage."),
    ]:
        rows.append(evidence(metric,val,"ratio","MULTIPLE_RESPONSE_SHARE",
          "respondents reporting increased administrative burden","1945",
          "JCCI-2024-INVOICE-BACKOFFICE-SURVEY","PDF p.11 / printed p.10",
          "OBSERVED_CONDITIONAL_SURVEY_RESPONSE","TASK_INCIDENCE_ONLY",note))
    for metric,val,note in [
      ("jcci2025_supplier_registration_check_share","0.748","Supplier registration-status confirmation/management."),
      ("jcci2025_registration_number_check_share","0.637","Invoice registration-number check on receipt."),
      ("jcci2025_tax_rate_amount_check_share","0.551","Consumption-tax rate/amount check on receipt."),
      ("jcci2025_required_fields_check_share","0.532","Required invoice fields check on issuance."),
    ]:
        rows.append(evidence(metric,val,"ratio","MULTIPLE_RESPONSE_SHARE",
          "respondents reporting increased administrative burden","1569",
          "JCCI-2025-INVOICE-SURVEY","PDF p.13 / printed p.12",
          "OBSERVED_CONDITIONAL_SURVEY_RESPONSE","TASK_INCIDENCE_ONLY",note))
    # Firm-size bookkeeping vulnerability from 2025; not a measure of VAT hours.
    size_rows=[
      ("le_10m","907","0.794","0.236","0.764"),
      ("gt10m_le50m","686","0.622","0.370","0.630"),
      ("gt50m_le100m","262","0.401","0.523","0.477"),
      ("gt100m","855","0.145","0.710","0.290"),
    ]
    for band,n,one,dedicated,noded in size_rows:
        rows += [
          evidence(f"jcci2025_{band}_one_accounting_worker_share",one,"ratio","SURVEY_RESPONSE_SHARE",
            f"firms in sales band {band}",n,"JCCI-2025-INVOICE-SURVEY","PDF p.16 / printed p.15",
            "OBSERVED_FIRM_SIZE_BACKOFFICE_STRUCTURE","VULNERABILITY_PROXY_NOT_VAT_HOURS",
            "Share reporting one person engaged in accounting administration."),
          evidence(f"jcci2025_{band}_dedicated_accounting_employee_share",dedicated,"ratio","SURVEY_RESPONSE_SHARE",
            f"firms in sales band {band}",n,"JCCI-2025-INVOICE-SURVEY","PDF p.16 / printed p.15",
            "OBSERVED_FIRM_SIZE_BACKOFFICE_STRUCTURE","VULNERABILITY_PROXY_NOT_VAT_HOURS",
            "Share with a dedicated accounting employee."),
          evidence(f"jcci2025_{band}_no_dedicated_accounting_employee_share",noded,"ratio","SURVEY_RESPONSE_SHARE",
            f"firms in sales band {band}",n,"JCCI-2025-INVOICE-SURVEY","PDF p.16 / printed p.15",
            "OBSERVED_FIRM_SIZE_BACKOFFICE_STRUCTURE","VULNERABILITY_PROXY_NOT_VAT_HOURS",
            "Share without a dedicated accounting employee."),
        ]

    # Broad all-tax compliance-cost survey: explicitly not VAT-specific.
    rows += [
      evidence("rieti2021_all_tax_compliance_sales_share_large","0.0006","sales_ratio",
        "SURVEY_DERIVED_ALL_TAX_COMPLIANCE_COST","capital >100m yen firms","2152",
        "RIETI-2021-QUANT-TAX-COMPLIANCE-COST","PDF p.8 / printed p.7",
        "OBSERVED_STUDY_ESTIMATE_ALL_TAX_TYPES","DO_NOT_USE_AS_VAT_SPECIFIC_C_VAT",
        "Average tax-compliance-cost/sales ratio. Cost definition covers multiple taxes including consumption tax."),
      evidence("rieti2021_all_tax_compliance_sales_share_sme","0.0017","sales_ratio",
        "SURVEY_DERIVED_ALL_TAX_COMPLIANCE_COST","capital <=100m yen firms","628",
        "RIETI-2021-QUANT-TAX-COMPLIANCE-COST","PDF p.8 / printed p.7",
        "OBSERVED_STUDY_ESTIMATE_ALL_TAX_TYPES","DO_NOT_USE_AS_VAT_SPECIFIC_C_VAT",
        "Average tax-compliance-cost/sales ratio; authors note SME wage-imputation caveat and sample-composition caveats."),
      evidence("rieti2021_tax_compliance_definition","1","boolean",
        "STUDY_METHOD_DEFINITION","surveyed firms","",
        "RIETI-2021-QUANT-TAX-COMPLIANCE-COST","PDF p.4 / printed p.3",
        "OBSERVED_STUDY_METHOD","DEFINITION_ONLY",
        "Compliance cost = tax-procedure labor time times hourly wage plus external outsourcing; covers corporate-related taxes, consumption tax, fixed-asset tax and business-office tax."),
      evidence("rieti2019_vat_threshold_bunching_compliance_heterogeneity","1","boolean",
        "EMPIRICAL_RESEARCH_RESULT","Japanese firms near VAT exemption threshold","",
        "RIETI-2019-VAT-COMPLIANCE-FIRM-GROWTH","abstract / empirical analysis",
        "EMPIRICAL_RESEARCH_EVIDENCE","ALLOCATION_CHANNEL_MOTIVATION_NOT_POINT_CALIBRATION",
        "Study reports bunching below the VAT threshold and stronger bunching with higher compliance-cost proxies among relevant firms."),
      evidence("rieti2021_vat_output_response_compliance_vs_rate","1","boolean",
        "EMPIRICAL_RESEARCH_RESULT","small manufacturing enterprises across Japanese VAT reforms","",
        "RIETI-2021-SME-VAT-COMPLIANCE","abstract / local-estimate analysis",
        "EMPIRICAL_RESEARCH_EVIDENCE","ALLOCATION_CHANNEL_MOTIVATION_NOT_POINT_CALIBRATION",
        "Study reports local output responses mainly associated with compliance costs rather than tax rates for small enterprises."),
      evidence("mof_current_vat_exemption_threshold","10000000","yen_taxable_sales",
        "OFFICIAL_INSTITUTIONAL_PARAMETER","businesses under current consumption-tax rules","",
        "MOF-CONSUMPTION-TAX-SME-EXEMPTION-THRESHOLD","saved official web page",
        "OBSERVED_CURRENT_INSTITUTION","THRESHOLD_DEFINITION_ONLY",
        "Current general base-period taxable-sales threshold for business exemption."),
      evidence("nta_vat_filing_input_credit_mechanism","1","boolean",
        "OFFICIAL_INSTITUTIONAL_RULE","taxable businesses","",
        "NTA-CONSUMPTION-TAX-BASIC","saved Tax Answer No.6101",
        "OBSERVED_CURRENT_INSTITUTION","INSTITUTIONAL_REGIME_DEFINITION",
        "Consumption-tax administration includes sales tax, eligible input tax, return filing and payment mechanics."),
      evidence("nta_invoice_retention_input_credit_mechanism","1","boolean",
        "OFFICIAL_INSTITUTIONAL_RULE","businesses claiming input tax credit","",
        "NTA-INVOICE-SYSTEM-OVERVIEW","saved official invoice overview",
        "OBSERVED_CURRENT_INSTITUTION","INSTITUTIONAL_REGIME_DEFINITION",
        "Qualified-invoice retention/verification is part of the current input-tax-credit system."),
    ]

    ident=[
      {"quantity":"invoice_burden_incidence","status":"OBSERVED_SURVEY_RESPONSE","point_identified":"NO_POPULATION_CAUSAL_POINT","model_use":"DESCRIPTIVE_EVIDENCE","note":"JCCI respondent shares establish widespread reported burden, not national resource-cost shares."},
      {"quantity":"firm_size_backoffice_vulnerability","status":"OBSERVED_SURVEY_RESPONSE","point_identified":"NO_NATIONAL_CAUSAL_POINT","model_use":"HETEROGENEITY_MOTIVATION","note":"Small firms are much more likely to have one-person/no-dedicated accounting; not VAT-specific hours."},
      {"quantity":"all_tax_compliance_cost_sales_ratio","status":"OBSERVED_STUDY_ESTIMATE_ALL_TAX_TYPES","point_identified":"NO_VAT_COMPONENT","model_use":"SCALE_CONTEXT_ONLY","note":"0.06% large and 0.17% SME averages include multiple tax types and use study-specific imputation."},
      {"quantity":"vat_specific_real_resource_cost_share_of_output","status":"NOT_IDENTIFIED","point_identified":"NO","model_use":"STRESS_TEST_PARAMETER_ONLY","note":"No current source here identifies a Japan-wide VAT-only resource-cost share of baseline output."},
      {"quantity":"productive_redeployment_fraction_rho","status":"NOT_IDENTIFIED","point_identified":"NO","model_use":"STRESS_TEST_PARAMETER_ONLY","note":"Saved compliance resources need not convert one-for-one into measured output."},
      {"quantity":"allocative_efficiency_dividend","status":"NOT_IDENTIFIED","point_identified":"NO","model_use":"STRESS_TEST_PARAMETER_ONLY","note":"Bunching evidence motivates a separate allocation channel but does not identify a macro output percentage."},
      {"quantity":"zero_rate_equals_full_abolition","status":"FALSE_BY_POLICY_DEFINITION","point_identified":"NOT_APPLICABLE","model_use":"PROHIBITED_EQUIVALENCE","note":"Policy state must separately encode VAT administrative/invoice obligations."},
      {"quantity":"compliance_savings_one_for_one_gdp","status":"PROHIBITED","point_identified":"NO","model_use":"DO_NOT_ASSUME","note":"Use explicit redeployment fraction and separate allocation term."},
      {"quantity":"income_gini_and_FGT2_effect","status":"NOT_MODELED_PHASE1","point_identified":"NO","model_use":"FUTURE_INCIDENCE_LINK_REQUIRED","note":"Firm-side resource release is not yet linked to households/deciles."},
      {"quantity":"fiscal_debt_effect","status":"NOT_MODELED_IN_COMPLIANCE_ONLY_MODULE","point_identified":"NO","model_use":"FINANCING_CHANNEL_SEPARATE","note":"Revenue replacement/JGB/income-tax/asset-tax choices remain separate instruments."},
    ]
    return rows,ident

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--check",action="store_true"); args=ap.parse_args()
    rows,ident=build()
    outs=[(OUT_EVIDENCE,render(rows)),(OUT_IDENT,render(ident))]
    if args.check:
        stale=[]
        for p,e in outs:
            if not p.exists() or p.read_text(encoding="utf-8")!=e: stale.append(str(p.relative_to(ROOT)))
        if stale: raise SystemExit("stale generated artifacts: "+", ".join(stale))
        print(f"VAT compliance evidence: current ({len(rows)} evidence rows; VAT-specific macro resource share not identified)")
    else:
        for p,e in outs:
            p.parent.mkdir(parents=True,exist_ok=True); p.write_text(e,encoding="utf-8")
            print(f"wrote {p.relative_to(ROOT)}: {len(rows) if p==OUT_EVIDENCE else len(ident)} rows")

if __name__=="__main__": main()
