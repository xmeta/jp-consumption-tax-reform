#!/usr/bin/env python3
from pathlib import Path
import csv, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/"data/derived/vat_compliance_observed_evidence.csv"
I=ROOT/"data/derived/vat_compliance_identification_status.csv"
C=ROOT/"data/source_catalog.csv"

def read(p):
    with p.open(encoding="utf-8",newline="") as f: return list(csv.DictReader(f))

ev={r["metric_id"]:r for r in read(E)}
ident={r["quantity"]:r for r in read(I)}
cat={r["source_id"]:r for r in read(C)}

anchors={
 "meti2021_corporate_survey_target_n":"20000",
 "meti2021_corporate_survey_valid_response_n":"4410",
 "meti2021_vat_internal_hours_sample_n":"1514",
 "meti2021_vat_internal_hours_topcoded_share":"0.067",
 "meti2021_vat_internal_hours_mean_lower_bound":"15.126155878468",
 "meti2021_hours_selection_label_internal_inconsistency":"1",
 "meti2021_all_tax_external_outsourcing_scope":"1",
 "rieti2021_bsws_industry_hourly_wage_method":"1",
 "bsws2019_industry_total_scheduled_hour_rate_yen":"1923.125",
 "bsws2019_industry_total_regular_cash_effective_hour_rate_yen":"1953.757225433526",
 "meti2021_vat_internal_labor_cost_industry_total_scheduled_bridge":"29089.488523778772500",
 "meti2021_vat_internal_labor_cost_industry_total_effective_bridge":"29552.836340590658784668718168",
 "jcci2024_invoice_cost_increase_share":"0.488",
 "jcci2024_invoice_admin_burden_increase_share":"0.822",
 "jcci2025_invoice_cost_increase_share":"0.458",
 "jcci2025_invoice_admin_burden_increase_share":"0.734",
 "jcci2025_le_10m_one_accounting_worker_share":"0.794",
 "jcci2025_le_10m_no_dedicated_accounting_employee_share":"0.764",
 "jcci2025_gt100m_one_accounting_worker_share":"0.145",
 "jcci2025_gt100m_dedicated_accounting_employee_share":"0.710",
 "rieti2021_all_tax_compliance_sales_share_large":"0.0006",
 "rieti2021_all_tax_compliance_sales_share_sme":"0.0017",
 "mof_current_vat_exemption_threshold":"10000000",
}
for k,v in anchors.items():
    assert ev[k]["value"]==v,(k,ev[k]["value"],v)

assert ev["rieti2021_all_tax_compliance_sales_share_sme"]["model_calibration_permission"]=="DO_NOT_USE_AS_VAT_SPECIFIC_C_VAT"
assert ev["jcci2025_invoice_admin_burden_increase_share"]["model_calibration_permission"]=="INCIDENCE_ONLY_NOT_RESOURCE_SHARE"
assert ev["rieti2019_vat_threshold_bunching_compliance_heterogeneity"]["model_calibration_permission"]=="ALLOCATION_CHANNEL_MOTIVATION_NOT_POINT_CALIBRATION"
assert ev["rieti2021_vat_output_response_compliance_vs_rate"]["model_calibration_permission"]=="ALLOCATION_CHANNEL_MOTIVATION_NOT_POINT_CALIBRATION"

assert ident["vat_specific_internal_hours_respondent_subset"]["status"]=="PARTIALLY_IDENTIFIED_CONDITIONAL_ON_RESPONDENT_SUBSET"
assert ident["vat_specific_internal_hours_respondent_subset"]["point_identified"]=="LOWER_BOUND_ONLY_TOP_CODED"
assert ident["vat_specific_internal_hours_respondent_subset"]["model_use"]=="HOURS_EVIDENCE_NOT_NATIONAL_C_VAT"
assert ident["rieti_exact_bsws_hourly_wage_formula"]["status"]=="NOT_IDENTIFIED_FROM_PAPER"
assert ident["rieti_exact_bsws_hourly_wage_formula"]["model_use"]=="TRANSPARENT_ALTERNATIVE_FORMULAS_ONLY"
assert ident["vat_specific_internal_labor_cost_respondent_reported_period"]["status"]=="MECHANICAL_WAGE_CONVERSION_ONLY"
assert ident["vat_specific_internal_labor_cost_respondent_reported_period"]["point_identified"]=="NO_ANNUAL_OR_POPULATION_POINT"
assert ident["vat_specific_real_resource_cost_share_of_output"]["status"]=="NOT_IDENTIFIED"
assert ident["vat_specific_real_resource_cost_share_of_output"]["model_use"]=="STRESS_TEST_PARAMETER_ONLY"
assert ident["productive_redeployment_fraction_rho"]["status"]=="NOT_IDENTIFIED"
assert ident["allocative_efficiency_dividend"]["status"]=="NOT_IDENTIFIED"
assert ident["zero_rate_equals_full_abolition"]["status"]=="FALSE_BY_POLICY_DEFINITION"
assert ident["compliance_savings_one_for_one_gdp"]["status"]=="PROHIBITED"
assert ident["income_gini_and_FGT2_effect"]["status"]=="NOT_MODELED_PHASE1"
assert ident["fiscal_debt_effect"]["model_use"]=="FINANCING_CHANNEL_SEPARATE"
hashes={
 "ESTAT-BSWS-2019-INDUSTRY-WAGE-T1":"9583495007287b89e163a3202c4d3f6e757dfcfc355076dcde0321e0276ac811",
 "ESTAT-BSWS-2019-INDUSTRY-WAGE-DB-SNAPSHOT":"510b65c6a47d54d4074594fe376458920e5a74edc105acc7aa14aea49993a8a1",
 "METI-2021-SME-TAX-SURVEY":"e6a5767910f2c1e024ec0b281e6f300949e735cdc6c9b052e164b6890948e563",
 "JCCI-2024-INVOICE-BACKOFFICE-SURVEY":"7ab80915efa7659e6f25cc152b7b5d2eef3c70038333eb6bc043642759d56126",
 "JCCI-2025-INVOICE-SURVEY":"d89a599e900146c7c8ec5e1f4b0702b9dd7d292b47042e9e57186dda4525605e",
 "RIETI-2019-VAT-COMPLIANCE-FIRM-GROWTH":"458d092bddb5a49af25f2f36cd202c5b96876df710aefa651187851dbdb75eca",
 "RIETI-2021-SME-VAT-COMPLIANCE":"397ef1b7202d6aec440e422587aa3ab09a1144ce0108db79fbc61166e64fe49b",
 "RIETI-2021-QUANT-TAX-COMPLIANCE-COST":"69f2dab66a34d0765f019f4590a8ca423a4226ff665d689f6d117a71cb210fc4",
 "MOF-CONSUMPTION-TAX-SME-EXEMPTION-THRESHOLD":"0ba2fec17b051245e96babcb54853b98edc6cc6dd5f5556562cf5501c94c4146",
 "NTA-CONSUMPTION-TAX-BASIC":"b5ecdc37b7b5de3376fe64c7bb30f420b0938fe4835dd4d1d7bdfb46184921f1",
 "NTA-INVOICE-SYSTEM-OVERVIEW":"f2cb2875e430e1565dbb03685d7952c5c40a3cac9b5ed6486b55f8c12c58c8a1",
}
for sid,h in hashes.items():
    assert cat[sid]["sha256"]==h,(sid,cat[sid]["sha256"],h)
    assert (ROOT/cat[sid]["raw_file"]).exists()

# Strong guards against category errors.
for k in ("rieti2021_all_tax_compliance_sales_share_large",
          "rieti2021_all_tax_compliance_sales_share_sme"):
    assert "ALL_TAX" in ev[k]["identification_status"]
    assert "VAT_SPECIFIC" in ev[k]["model_calibration_permission"]
for k in ("jcci2024_invoice_admin_burden_increase_share",
          "jcci2025_invoice_admin_burden_increase_share"):
    assert ev[k]["unit"]=="ratio"
    assert ev[k]["evidence_type"]=="SURVEY_RESPONSE_SHARE"

subprocess.run([sys.executable,str(ROOT/"scripts/extract_vat_compliance_evidence.py"),"--check"],cwd=ROOT,check=True)
assert ev["meti2021_vat_internal_hours_mean_lower_bound"]["unit"]=="hours_per_responding_corporation_reported_period"
assert ev["meti2021_vat_internal_hours_mean_lower_bound"]["model_calibration_permission"]=="HOURS_BOUND_ONLY_NOT_C_VAT"
assert ev["meti2021_all_tax_external_outsourcing_scope"]["model_calibration_permission"]=="DO_NOT_ATTRIBUTE_TO_VAT"
assert ev["meti2021_corporate_survey_target_n"]["model_calibration_permission"]=="FRAME_CONTEXT_NOT_POPULATION_WEIGHT"
assert ev["meti2021_corporate_survey_valid_response_n"]["model_calibration_permission"]=="FRAME_CONTEXT_NOT_VAT_ITEM_RESPONSE_RATE"
assert ev["rieti2021_bsws_industry_hourly_wage_method"]["model_calibration_permission"]=="METHOD_BRIDGE_ONLY"
assert ev["bsws2019_industry_total_scheduled_hour_rate_yen"]["model_calibration_permission"]=="WAGE_CONVERSION_SENSITIVITY_ONLY"
assert ev["meti2021_vat_internal_labor_cost_industry_total_scheduled_bridge"]["model_calibration_permission"]=="DO_NOT_USE_AS_NATIONAL_C_VAT"
assert len(ev)==45 and len(ident)==13
print("VAT compliance evidence tests: OK (45 observed-evidence rows; hours-to-yen mechanical bridge added; national VAT resource share remains NOT_IDENTIFIED)")
