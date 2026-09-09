#!/usr/bin/env python3
"""Extract observed Japan VAT-compliance evidence without turning it into GDP gains."""
from pathlib import Path
import argparse, csv, io, re
from decimal import Decimal
from pypdf import PdfReader
from extract_meti_vat_internal_hours import build as build_meti_hours
from build_bsws_2019_industry_hourly_wage_bridge import build as build_bsws_wages

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
      "METI-2021-SME-TAX-SURVEY",
      "ESTAT-BSWS-2019-INDUSTRY-WAGE-T1",
      "ESTAT-BSWS-2019-INDUSTRY-WAGE-DB-SNAPSHOT",
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

    meti_dist, meti_bounds = build_meti_hours()
    meti_bound = {r["bound_id"]: r for r in meti_bounds}
    meti_bin = {r["bin_id"]: r for r in meti_dist}
    meti = PdfReader(ROOT/cat["METI-2021-SME-TAX-SURVEY"]["raw_file"])
    meti_p5 = meti.pages[4].extract_text() or ""
    require_tokens(meti_p5,["対象エリア：全国","調査対象数：20,000件","回収数：4,412件","有効回答数：4,410件","株式会社帝国データバンク"],"METI2021 p5")
    wage_rows=build_bsws_wages()
    wage_total=next(r for r in wage_rows if r["industry_code"]=="01")
    major_wages=[r for r in wage_rows if r["industry_code"]!="01"]
    h_lb=Decimal(meti_bound["no_top_code_cap"]["mean_hours_lower_bound"])
    w_sched=Decimal(wage_total["scheduled_hour_rate_yen"])
    w_eff=Decimal(wage_total["regular_cash_effective_hour_rate_yen"])

    rows=[]
    # METI directly measures VAT-specific internal tax-procedure hours for a
    # respondent subset.  It does not identify a national c_VAT.
    rows += [
      evidence("meti2021_corporate_survey_target_n","20000","corporations",
        "OFFICIAL_SURVEY_DESIGN_COUNT","corporations sampled from Teikoku Databank business database under stated industry conditions","20000",
        "METI-2021-SME-TAX-SURVEY","PDF p.5 / printed p.5",
        "OBSERVED_SURVEY_FRAME","FRAME_CONTEXT_NOT_POPULATION_WEIGHT",
        "Survey area is nationwide; 20,000 corporation targets were extracted from the Teikoku Databank business database under stated main-industry conditions."),
      evidence("meti2021_corporate_survey_valid_response_n","4410","corporations",
        "OFFICIAL_SURVEY_RESPONSE_COUNT","valid corporate survey responses","4410",
        "METI-2021-SME-TAX-SURVEY","PDF p.5 / printed p.5",
        "OBSERVED_SURVEY_FRAME","FRAME_CONTEXT_NOT_VAT_ITEM_RESPONSE_RATE",
        "Published valid responses are 4,410 (22.1% valid response rate); the VAT-hours item has its own smaller n=1,514."),
      evidence("meti2021_vat_internal_hours_sample_n","1514","respondents",
        "OFFICIAL_SURVEY_RESPONSE_COUNT","corporations responding to the published consumption-tax internal-hours item","1514",
        "METI-2021-SME-TAX-SURVEY","PDF p.67 / printed p.67",
        "OBSERVED_CONDITIONAL_SURVEY_SUBSET","SAMPLE_SCOPE_ONLY",
        "Published n for the consumption-tax internal tax-procedure hours distribution."),
      evidence("meti2021_vat_internal_hours_topcoded_share","0.067","ratio",
        "SURVEY_RESPONSE_SHARE","corporations responding to the published consumption-tax internal-hours item","1514",
        "METI-2021-SME-TAX-SURVEY","PDF p.67 / printed p.67",
        "OBSERVED_CONDITIONAL_SURVEY_SUBSET","DIRECT_VAT_HOURS_DISTRIBUTION_NOT_NATIONAL_MEAN",
        "Published share in the open-ended 100 hours or more category."),
      evidence("meti2021_vat_internal_hours_mean_lower_bound",meti_bound["no_top_code_cap"]["mean_hours_lower_bound"],"hours_per_responding_corporation_reported_period",
        "DERIVED_PARTIAL_IDENTIFICATION_BOUND","corporations responding to the published consumption-tax internal-hours item","1514",
        "METI-2021-SME-TAX-SURVEY","PDF p.67 / printed p.67; derived with one-decimal rounding and integer-count constraints",
        "CONDITIONAL_RESPONDENT_SUBSET_LOWER_BOUND","HOURS_BOUND_ONLY_NOT_C_VAT",
        "Conservative mean lower bound using bin lower endpoints over all 28 integer count vectors compatible with n=1,514 and published rounded shares. Q8-3 does not explicitly label the tax-item hours as annual; not a national-firm mean."),
      evidence("meti2021_hours_selection_label_internal_inconsistency","1","boolean",
        "SOURCE_INTERNAL_CONSISTENCY_CHECK","published section 7 tax-procedure survey results","",
        "METI-2021-SME-TAX-SURVEY","PDF pp.65-67 / printed pp.65-67",
        "RESULTS_SELECTOR_CONFLICTS_WITH_QUESTIONNAIRE_AND_COUNTS","SAMPLE_SCOPE_CAUTION",
        "Results p.66 says the hours question targets Q8-1=yes, but the questionnaire Q8-3 targets Q8-1=No. Independently, p.65 n=3,965 at 17.0% implies only 673-676 yes responses under one-decimal rounding, fewer than VAT-item n=1,514. Treat results-page selector as conflicting source metadata, not as the sample definition."),
      evidence("meti2021_all_tax_external_outsourcing_scope","1","boolean",
        "OFFICIAL_SURVEY_SCOPE_DEFINITION","respondents to annual tax-procedure outsourcing-cost item","3755",
        "METI-2021-SME-TAX-SURVEY","PDF p.70 / printed p.70",
        "OBSERVED_ALL_TAX_EXTERNAL_OUTSOURCING","DO_NOT_ATTRIBUTE_TO_VAT",
        "Published external outsourcing expenditure is for tax-procedure work generally and is not disaggregated to consumption tax."),
    ]
    rows += [
      evidence("rieti2021_bsws_industry_hourly_wage_method","1","boolean",
        "STUDY_METHOD_DEFINITION","firms in RIETI tax-compliance-cost study","",
        "RIETI-2021-QUANT-TAX-COMPLIANCE-COST","PDF p.4 / printed p.2",
        "OBSERVED_STUDY_METHOD","METHOD_BRIDGE_ONLY",
        "RIETI states that tax-procedure hours were valued using industry-specific hourly wages from the MHLW Basic Survey on Wage Structure, but the paper does not identify the exact table/formula used to construct hourly wages."),
      evidence("bsws2019_industry_total_scheduled_hour_rate_yen",wage_total["scheduled_hour_rate_yen"],"yen_per_hour",
        "DERIVED_OFFICIAL_WAGE_COMPONENT_RATIO","2019 general workers, private establishments, enterprise-size 10+ total, industry total","",
        "ESTAT-BSWS-2019-INDUSTRY-WAGE-DB-SNAPSHOT","DB sid=0003084009 / statInfId=000031919751",
        "DERIVED_TRANSPARENT_WAGE_CANDIDATE","WAGE_CONVERSION_SENSITIVITY_ONLY",
        "Scheduled cash earnings divided by scheduled actual hours; transparent candidate, not asserted to be RIETI's exact unpublished formula."),
      evidence("bsws2019_industry_total_regular_cash_effective_hour_rate_yen",wage_total["regular_cash_effective_hour_rate_yen"],"yen_per_hour",
        "DERIVED_OFFICIAL_WAGE_COMPONENT_RATIO","2019 general workers, private establishments, enterprise-size 10+ total, industry total","",
        "ESTAT-BSWS-2019-INDUSTRY-WAGE-DB-SNAPSHOT","DB sid=0003084009 / statInfId=000031919751",
        "DERIVED_TRANSPARENT_WAGE_CANDIDATE","WAGE_CONVERSION_SENSITIVITY_ONLY",
        "Regular cash earnings divided by scheduled plus overtime actual hours; transparent candidate, not asserted to be RIETI's exact unpublished formula."),
      evidence("meti2021_vat_internal_labor_cost_industry_total_scheduled_bridge",str(h_lb*w_sched),"yen_per_responding_corporation_reported_period",
        "MECHANICAL_CROSS_SOURCE_WAGE_CONVERSION","METI VAT-hours respondent subset valued at 2019 BSWS industry-total scheduled-hour rate","1514",
        "METI-2021-SME-TAX-SURVEY","METI p.67 hours lower bound x e-Stat 2019 industry-total scheduled-hour wage candidate",
        "MECHANICAL_WAGE_CONVERSION_NOT_ANNUAL_NOT_POPULATION_ESTIMATE","DO_NOT_USE_AS_NATIONAL_C_VAT",
        "Mechanical conversion only; Q8-3 period is not explicitly annual, respondent industry composition is unknown, wage year differs, and VAT-specific external outsourcing is missing."),
      evidence("meti2021_vat_internal_labor_cost_industry_total_effective_bridge",str(h_lb*w_eff),"yen_per_responding_corporation_reported_period",
        "MECHANICAL_CROSS_SOURCE_WAGE_CONVERSION","METI VAT-hours respondent subset valued at 2019 BSWS industry-total regular-cash effective hourly rate","1514",
        "METI-2021-SME-TAX-SURVEY","METI p.67 hours lower bound x e-Stat 2019 industry-total effective hourly wage candidate",
        "MECHANICAL_WAGE_CONVERSION_NOT_ANNUAL_NOT_POPULATION_ESTIMATE","DO_NOT_USE_AS_NATIONAL_C_VAT",
        "Mechanical conversion only; Q8-3 period is not explicitly annual, respondent industry composition is unknown, wage year differs, and VAT-specific external outsourcing is missing."),
    ]
    assert len(major_wages)==16
    assert meti_bin["ge100"]["published_percent"] == "6.7"
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
      {"quantity":"vat_specific_internal_hours_respondent_subset","status":"PARTIALLY_IDENTIFIED_CONDITIONAL_ON_RESPONDENT_SUBSET","point_identified":"LOWER_BOUND_ONLY_TOP_CODED","model_use":"HOURS_EVIDENCE_NOT_NATIONAL_C_VAT","note":"METI n=1,514 directly measures VAT-specific internal hours for the reported Q8-3 response period. Published one-decimal shares plus integer counts imply a 15.126155878468 h/respondent lower bound; Q8-3 does not explicitly label tax-item hours as annual, 100+ top coding leaves the uncapped upper bound open, and results-page selector conflicts with the questionnaire and counts."},
      {"quantity":"rieti_exact_bsws_hourly_wage_formula","status":"NOT_IDENTIFIED_FROM_PAPER","point_identified":"NO","model_use":"TRANSPARENT_ALTERNATIVE_FORMULAS_ONLY","note":"RIETI 21-P-018 identifies the MHLW Basic Survey on Wage Structure as the industry-hourly-wage source but does not identify the exact table/formula. The repository therefore carries two transparent official-component ratios rather than claiming exact replication."},
      {"quantity":"vat_specific_internal_labor_cost_respondent_reported_period","status":"MECHANICAL_WAGE_CONVERSION_ONLY","point_identified":"NO_ANNUAL_OR_POPULATION_POINT","model_use":"SENSITIVITY_ONLY_NOT_C_VAT","note":"The METI conditional hours lower bound can be multiplied by official BSWS wage candidates, giving about 29.1-29.6k yen/respondent at the industry-total candidates for the reported Q8-3 period. The period is not explicitly annual and respondent industry composition, selection, temporal alignment, and VAT-specific outsourcing remain unresolved."},
      {"quantity":"vat_specific_real_resource_cost_share_of_output","status":"NOT_IDENTIFIED","point_identified":"NO","model_use":"STRESS_TEST_PARAMETER_ONLY","note":"METI partially identifies VAT-specific internal hours and the repository now supplies transparent official wage-conversion candidates, but Q8-3 period is not explicitly annual; national population reweighting/selection, respondent industry mix, temporal alignment, and VAT-specific external expenditure remain unavailable. Therefore Japan-wide c_VAT is not identified."},
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
