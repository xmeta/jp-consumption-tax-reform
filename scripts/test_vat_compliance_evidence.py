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
 "meti2019_vat_hours_explicit_fiscal_period_design":"1",
 "meti2019_vat_hours_public_numeric_result":"0",
 "meti2019_public_microdata_attachment_listed":"0",
 "meti2020_corporate_survey_target_n":"18000",
 "meti2020_corporate_survey_response_n":"3255",
 "meti2020_vat_hours_public_numeric_result":"0",
 "meti2020_public_microdata_attachment_listed":"0",
 "rieti2021_sme_survey_answers_fy2019_scope":"1",
 "ichikawa2019_10m_vat_exemption_threshold_yen":"10000000",
 "ichikawa2019_10m_national_bunching_region_firm_count":"308435",
 "ichikawa2019_10m_national_bunching_region_value_added_share":"0.413",
 "ichikawa2019_10m_vat_rate_table4":"0.08",
 "ichikawa2019_10m_estimated_excess_buncher_firm_count":"56651",
 "ichikawa2019_10m_estimated_tax_windfall_yen_per_year":"16850000000",
 "ichikawa2019_10m_lost_sales_all_excess_real_adjustment_scenario_yen":"84980000000",
 "ichikawa2019_10m_lost_sales_missing_mass_scenario_yen":"3140000000",
 "ichikawa2019_2014_hike_bunching_post_minus_pre_window_1m":"-0.037",
 "ichikawa2019_2014_hike_bunching_post_minus_pre_window_1p5m":"-0.159",
 "ichikawa2019_2014_hike_bunching_post_minus_pre_window_2m":"0.033",
 "ichikawa2019_2014_hike_bunching_post_minus_pre_window_2p5m":"-0.019",
 "rieti2021_threshold_bunching_1989_1991_delta_ratio":"0.550",
 "rieti2021_threshold_bunching_1992_1994_delta_ratio":"0.543",
 "rieti2021_threshold_bunching_1997_1999_delta_ratio":"0.542",
 "rieti2021_threshold_theta_1992_all":"0.130",
 "rieti2021_threshold_theta_1997_all":"0.140",
 "rieti2021_threshold_theta_1992_firms":"0.091",
 "rieti2021_threshold_theta_1997_firms":"0.111",
 "rieti2021_threshold_theta_1992_sole_proprietors":"0.116",
 "rieti2021_threshold_theta_1997_sole_proprietors":"0.130",
 "meti2021_public_microdata_attachment_listed":"0",
 "smrj_fy2019_light_rate_subsidy_grant_count":"94875",
 "smrj_fy2019_light_rate_subsidy_amount_yen":"22914612620",
 "smrj_fy2019_light_rate_subsidy_lower_bound_per_grant_record":"241524.243689064559",
 "smrj_cumulative_light_rate_subsidy_grant_count":"174781",
 "smrj_cumulative_light_rate_subsidy_amount_yen":"44659886587",
 "smrj_cumulative_light_rate_subsidy_lower_bound_per_grant_record":"255519.11584783243",
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

assert ident["historical_vat_hours_survey_lineage"]["status"]=="DESIGN_SCOPE_OBSERVED_NUMERIC_PUBLICATION_GAP"
assert ident["historical_vat_hours_survey_lineage"]["point_identified"]=="NO_COMMON_PUBLIC_ANNUAL_NUMERIC_SERIES"
assert ident["historical_vat_hours_survey_lineage"]["model_use"]=="DO_NOT_ANNUALIZE_2021_BOUND_FROM_LINEAGE"
assert ident["vat_specific_internal_hours_respondent_subset"]["status"]=="PARTIALLY_IDENTIFIED_CONDITIONAL_ON_RESPONDENT_SUBSET"
assert ident["vat_specific_internal_hours_respondent_subset"]["point_identified"]=="LOWER_BOUND_ONLY_TOP_CODED"
assert ident["vat_specific_internal_hours_respondent_subset"]["model_use"]=="HOURS_EVIDENCE_NOT_NATIONAL_C_VAT"
assert ident["rieti_exact_bsws_hourly_wage_formula"]["status"]=="NOT_IDENTIFIED_FROM_PAPER"
assert ident["rieti_exact_bsws_hourly_wage_formula"]["model_use"]=="TRANSPARENT_ALTERNATIVE_FORMULAS_ONLY"
assert ident["vat_specific_internal_labor_cost_respondent_reported_period"]["status"]=="MECHANICAL_WAGE_CONVERSION_ONLY"
assert ident["vat_specific_internal_labor_cost_respondent_reported_period"]["point_identified"]=="NO_ANNUAL_OR_POPULATION_POINT"
assert ident["vat_transition_system_implementation_cost_selected_grant_records"]["status"]=="PARTIALLY_BOUNDED_FROM_BELOW_BY_SUBSIDY_FLOW"
assert ident["vat_transition_system_implementation_cost_selected_grant_records"]["model_use"]=="TRANSITION_COST_ONLY_NOT_PERSISTENT_C_VAT"
assert ident["vat_specific_persistent_external_software_adviser_cost"]["status"]=="NOT_IDENTIFIED"
assert ident["vat_specific_persistent_external_software_adviser_cost"]["model_use"]=="REQUIRES_RECURRING_VAT_SPECIFIC_MONETARY_EVIDENCE"
assert ident["vat_specific_real_resource_cost_share_of_output"]["status"]=="NOT_IDENTIFIED"
assert ident["vat_specific_real_resource_cost_share_of_output"]["model_use"]=="STRESS_TEST_PARAMETER_ONLY"
assert ident["productive_redeployment_fraction_rho"]["status"]=="NOT_IDENTIFIED"
assert ident["vat_threshold_local_marginal_buncher_sales_response"]["status"]=="STUDY_ESTIMATED_UPPER_BOUND_LOCAL_HISTORICAL"
assert ident["vat_threshold_local_marginal_buncher_sales_response"]["model_use"]=="LOCAL_DISTORTION_EVIDENCE_NOT_MACRO_A_ALLOC"
assert ident["vat_threshold_structural_compliance_cost_theta"]["status"]=="MODEL_CONTINGENT_LOCAL_PARAMETER_ESTIMATED"
assert ident["vat_threshold_structural_compliance_cost_theta"]["model_use"]=="DO_NOT_EQUATE_WITH_REAL_RESOURCE_C_VAT_OR_MACRO_A_ALLOC"
assert ident["vat_10m_threshold_excess_buncher_scale"]["status"]=="MODEL_AND_EXTERNAL_STATS_NATIONALIZED_ESTIMATE"
assert ident["vat_10m_threshold_excess_buncher_scale"]["model_use"]=="BEHAVIORAL_DISTORTION_SCALE_NOT_OUTPUT_LOSS"
assert ident["vat_10m_threshold_tax_windfall"]["point_identified"]=="16.85_BILLION_YEN_PER_YEAR"
assert ident["vat_10m_threshold_tax_windfall"]["model_use"]=="TAX_REVENUE_CONTEXT_NOT_WELFARE_LOSS"
assert ident["vat_10m_threshold_lost_sales_mechanism_scenarios"]["status"]=="MECHANISM_SENSITIVE_SCENARIOS_NOT_IDENTIFICATION_BOUNDS"
assert ident["vat_10m_threshold_lost_sales_mechanism_scenarios"]["model_use"]=="DO_NOT_MAP_TO_GDP_OR_WELFARE_ONE_FOR_ONE"
assert ident["vat_10m_threshold_adjustment_mechanism"]["status"]=="NOT_IDENTIFIED_INDIRECT_EVIDENCE_AGAINST_WIDESPREAD_REAL_SUPPRESSION"
assert ident["vat_10m_threshold_adjustment_mechanism"]["model_use"]=="REAL_ADJUSTMENT_VS_AVOIDANCE_MIX_UNKNOWN"
assert ident["current_invoice_era_threshold_allocation_effect"]["status"]=="PRE_INVOICE_10M_THRESHOLD_BEHAVIOR_OBSERVED_CURRENT_INVOICE_ERA_NOT_IDENTIFIED"
assert ident["current_invoice_era_threshold_allocation_effect"]["point_identified"]=="NO_CURRENT_INVOICE_ERA_MACRO_EFFECT"
assert ident["allocative_efficiency_dividend"]["status"]=="NOT_IDENTIFIED"
assert ident["allocative_efficiency_dividend"]["point_identified"]=="NO_MACRO_OUTPUT_PERCENTAGE"
assert ident["zero_rate_equals_full_abolition"]["status"]=="FALSE_BY_POLICY_DEFINITION"
assert ident["compliance_savings_one_for_one_gdp"]["status"]=="PROHIBITED"
assert ident["income_gini_and_FGT2_effect"]["status"]=="NOT_MODELED_PHASE1"
assert ident["fiscal_debt_effect"]["model_use"]=="FINANCING_CHANNEL_SEPARATE"
hashes={
 "METI-2019-SME-TAX-REPORT-ARCHIVED":"148db29d866f77bb50c71eb23e229d64b1605fccf737ce1e7c39b072d85b1cd0",
 "METI-2019-REPORT-LISTING-20210213-ARCHIVED":"413ebf3d9f9b431e5ddfbcf902cc2a526689a0d0667b40389bfaf0d85af0568d",
 "METI-2020-SME-TAX-REPORT-ARCHIVED":"66c0af8b84c6b35a2396da67bb1add2d30c5eea4cba51f1bfad7f5cf62166763",
 "METI-2020-REPORT-LISTING-20211202-ARCHIVED":"9cb8d5dc819522da8a9eac75fa84f61037d8edba0e4d12257bfbb08981c2392e",
 "METI-2021-REPORT-LISTING-20220718-ARCHIVED":"ae840c57ce054e48209b2b721a19d533d36d36f5c8f79efa3df79e54a59a7c1e",
 "SMRJ-FY2019-LIGHT-RATE-SUBSIDY-PERFORMANCE":"7b30ebbb9dc0da5b94e56c0e8df1d935672bfb4f0729564bc76390bcf033d4c3",
 "ESTAT-BSWS-2019-INDUSTRY-WAGE-T1":"9583495007287b89e163a3202c4d3f6e757dfcfc355076dcde0321e0276ac811",
 "ESTAT-BSWS-2019-INDUSTRY-WAGE-DB-SNAPSHOT":"510b65c6a47d54d4074594fe376458920e5a74edc105acc7aa14aea49993a8a1",
 "METI-2021-SME-TAX-SURVEY":"e6a5767910f2c1e024ec0b281e6f300949e735cdc6c9b052e164b6890948e563",
 "JCCI-2024-INVOICE-BACKOFFICE-SURVEY":"7ab80915efa7659e6f25cc152b7b5d2eef3c70038333eb6bc043642759d56126",
 "JCCI-2025-INVOICE-SURVEY":"d89a599e900146c7c8ec5e1f4b0702b9dd7d292b47042e9e57186dda4525605e",
 "ICHIKAWA-ARUDCHELVAN-ONJI-2019-VAT-10M-BUNCHING":"93f68057104b6a4bb693c5fafbea8386ad830f6f3714291968d9937784517b28",
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
assert ev["meti2019_vat_hours_explicit_fiscal_period_design"]["model_calibration_permission"]=="PERIOD_DESIGN_EVIDENCE_NOT_NUMERIC_CALIBRATION"
assert ev["meti2019_public_microdata_attachment_listed"]["model_calibration_permission"]=="NO_PUBLIC_MICRODATA_CALIBRATION"
assert ev["meti2020_vat_hours_public_numeric_result"]["model_calibration_permission"]=="DO_NOT_IMPUTE_FROM_RIETI_ALL_TAX_RESULTS"
assert ev["rieti2021_sme_survey_answers_fy2019_scope"]["model_calibration_permission"]=="SCOPE_LINKAGE_ONLY_NOT_PUBLIC_VAT_MICRODATA"
assert ev["meti2021_public_microdata_attachment_listed"]["model_calibration_permission"]=="NO_PUBLIC_MICRODATA_CALIBRATION"
assert ev["smrj_fy2019_light_rate_subsidy_amount_yen"]["model_calibration_permission"]=="LOWER_BOUND_ON_SELECTED_TRANSITION_EXPENDITURE_ONLY"
assert ev["smrj_cumulative_light_rate_subsidy_lower_bound_per_grant_record"]["model_calibration_permission"]=="DO_NOT_GENERALIZE_TO_FIRMS_OR_PERSISTENT_C_VAT"
for k in ("ichikawa2019_10m_lost_sales_all_excess_real_adjustment_scenario_yen","ichikawa2019_10m_lost_sales_missing_mass_scenario_yen"):
    assert ev[k]["identification_status"]=="MECHANISM_SENSITIVE_SCENARIO_ESTIMATE"
    assert ev[k]["model_calibration_permission"]=="DO_NOT_TREAT_AS_EMPIRICAL_BOUND_OR_GDP_LOSS"
assert ev["ichikawa2019_10m_estimated_tax_windfall_yen_per_year"]["model_calibration_permission"]=="TAX_REVENUE_CONTEXT_NOT_WELFARE_LOSS"
for k in ("ichikawa2019_2014_hike_bunching_post_minus_pre_window_1m","ichikawa2019_2014_hike_bunching_post_minus_pre_window_1p5m","ichikawa2019_2014_hike_bunching_post_minus_pre_window_2m","ichikawa2019_2014_hike_bunching_post_minus_pre_window_2p5m"):
    assert ev[k]["model_calibration_permission"]=="COMPLIANCE_MOTIVE_EVIDENCE_NOT_TAX_RATE_ELASTICITY_OR_MACRO_A_ALLOC"
for k in ("rieti2021_threshold_bunching_1989_1991_delta_ratio","rieti2021_threshold_bunching_1992_1994_delta_ratio","rieti2021_threshold_bunching_1997_1999_delta_ratio"):
    assert ev[k]["model_calibration_permission"]=="THRESHOLD_DISTORTION_EVIDENCE_NOT_MACRO_A_ALLOC"
for k in ("rieti2021_threshold_theta_1992_all","rieti2021_threshold_theta_1997_all","rieti2021_threshold_theta_1992_firms","rieti2021_threshold_theta_1997_firms","rieti2021_threshold_theta_1992_sole_proprietors","rieti2021_threshold_theta_1997_sole_proprietors"):
    assert ev[k]["unit"]=="share_of_value_added_in_study_model"
    assert ev[k]["model_calibration_permission"]=="LOCAL_THRESHOLD_STRUCTURAL_EVIDENCE_NOT_C_VAT_OR_MACRO_A_ALLOC"
assert len(ev)==81 and len(ident)==23
print("VAT compliance evidence tests: OK (81 evidence rows; 10m threshold mechanism sensitivity quantified; national c_VAT and macro a_alloc remain NOT_IDENTIFIED)")
