#!/usr/bin/env python3
from pathlib import Path
import csv
import hashlib

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived"
OUT = ROOT / "data/derived_catalog.csv"

SPECS = [
    (
        "ESTAT-71411-MAIN-INCOME-BY-DISPOSABLE-DECILE",
        "estat_71411_main_income_by_disposable_decile_2024.csv",
        "scripts/extract_estat_rank_bridge_diagnostics.py",
        "ESTAT-7141-1-2024",
        "DERIVED_REPRODUCED_EXTERNAL_DIAGNOSTIC",
        "Table 7-141-1 household-member composition by main annual-income type across OECD-new equivalized-disposable-income deciles; no NTA category identity imposed",
    ),
    (
        "ESTAT-7171-MAIN-INCOME-DISPOSABLE-QUANTILES",
        "estat_7171_main_income_disposable_quantiles_2024.csv",
        "scripts/extract_estat_rank_bridge_diagnostics.py",
        "ESTAT-7171-2024",
        "DERIVED_REPRODUCED_EXTERNAL_DIAGNOSTIC",
        "Table 7-171 OECD-new equivalized-disposable-income quantiles by main annual-income type; within-NSFCW diagnostic only",
    ),
    (
        "STAGE1-OFFICIAL-INPUTS",
        "stage1_official_inputs.csv",
        "manual_transcription_verified",
        "NTA-R06;STAT-CENSUS-2020-SUMMARY;STAT-CENSUS-2020-BASIC;"
        "STAT-F71561-DESIGN;ISHIKAWA-CENSUS-2020;STAT-MIGRATION-2024;"
        "MHLW-VITAL-2020-T1;MHLW-VITAL-2022-T1;MHLW-VITAL-2024-T1",
        "DERIVED_VERIFIED_TRANSCRIPTION",
        "Normalized official values used by the stage-1 robustness analysis",
    ),
    (
        "ESTAT-71531-DECILES-LONG",
        "estat_71531_deciles_long.csv",
        "scripts/extract_estat_income_tax_tables.py",
        "ESTAT-7153-1-2024",
        "DERIVED_REPRODUCED",
        "Table 7-153-1 decile-by-income-component long extract with source cells",
    ),
    (
        "ESTAT-71561-HOUSEHOLD-TYPES",
        "estat_71561_household_types.csv",
        "scripts/extract_estat_income_tax_tables.py",
        "ESTAT-7156-1-2024",
        "DERIVED_REPRODUCED",
        "49 household-type headers and hierarchy; original leaves derived structurally",
    ),
    (
        "ESTAT-71561-DECILES-LONG",
        "estat_71561_deciles_long.csv",
        "scripts/extract_estat_income_tax_tables.py",
        "ESTAT-7156-1-2024",
        "DERIVED_REPRODUCED",
        "Table 7-156-1 decile x household-type x component long extract with source cells",
    ),
    (
        "ESTAT-71561-LEAF-COMPAT",
        "income_tax_household_type_leaf_deciles_2024.csv",
        "scripts/extract_estat_income_tax_tables.py",
        "ESTAT-7156-1-2024",
        "DERIVED_REPRODUCED",
        "14 structural leaf household types x 10 deciles; compatibility layer for income-tax research",
    ),
    (
        "ESTAT-71531-TAX-SOCIAL-INSTRUMENTS",
        "income_tax_decile_tax_social_instruments_2024.csv",
        "scripts/build_income_tax_decile_instruments.py",
        "ESTAT-7153-1-2024",
        "DERIVED_REPRODUCED",
        "Decile income tax, resident tax and social-insurance contribution moments",
    ),
    (
        "ESTAT-71561-LEAF-AUDIT",
        "estat_71561_leaf_aggregation_audit.csv",
        "scripts/build_income_tax_decile_instruments.py",
        "ESTAT-7153-1-2024;ESTAT-7156-1-2024",
        "DERIVED_REPRODUCED",
        "Leaf aggregation versus total-table rounding diagnostic",
    ),
    (
        "ESTAT-71911-SIZE-AGE-BRIDGE",
        "estat_71911_decile_household_size_age_bridge.csv",
        "scripts/extract_estat_f71911_bridge.py",
        "ESTAT-7191-1-2024",
        "DERIVED_REPRODUCED",
        "F71911 decile household-size top-code sensitivity and age-65+ bridge with source cells",
    ),
    (
        "ESTAT-71911-INCOME-TAX-BRIDGE",
        "income_tax_bridge_deciles_2024.csv",
        "scripts/extract_estat_f71911_bridge.py",
        "ESTAT-7191-1-2024",
        "DERIVED_REPRODUCED_SENSITIVITY_INPUT",
        "Backward-compatible pseudo-filer sensitivity bridge; exact mean household size is not identified because 6+ is top-coded",
    ),
    (
        "NTA-2024-T17-SOCIAL-SCHEDULE",
        "nta_salary_class_social_deduction_schedule_2024.csv",
        "scripts/extract_nta_table17_and_f71551.py",
        "NTA-MINKAN-2024-T17",
        "DERIVED_REPRODUCED_EXTERNAL_SENSITIVITY",
        "Salary-class mean social-insurance deduction per full-year employee, with recipient mean retained separately",
    ),
    (
        "NTA-2024-T17-FAMILY-SCHEDULE",
        "nta_salary_class_family_deduction_validation_2024.csv",
        "scripts/extract_nta_table17_and_f71551.py",
        "NTA-MINKAN-2024-T17;NTA-2026-DEPENDENT-DEDUCTION",
        "DERIVED_REPRODUCED_EXTERNAL_SENSITIVITY",
        "2024 dependent composition by salary class revalued at 2026 dependent-deduction amounts; no 2026 eligibility forecast",
    ),
    (
        "ESTAT-71551-PENSION-AGE-PROXY",
        "income_tax_age_income_source_shares_2024.csv",
        "scripts/extract_nta_table17_and_f71551.py",
        "ESTAT-7155-1-2024",
        "DERIVED_REPRODUCED_SENSITIVITY_PROXY",
        "F71551 age65+ public-pension amount proxy from overlapping age-recap aggregate cells; not a filer/person identified share",
    ),
    (
        "NTA-2024-PRIMARY-TYPE-STAGE2",
        "nta_primary_type_stage2_2024.csv",
        "scripts/extract_nta_stage2_holdout.py",
        "NTA-R06;NTA-2024-SHINKOKU-SAMPLE",
        "DERIVED_REPRODUCED_EXTERNAL_DIAGNOSTIC",
        "Exact NTA primary-income-type positive-self-assessed-balance rates; external diagnostic only, not F71561 selection identification",
    ),
    (
        "NTA-2024-POSITIVE-SELF-ASSESSED-BALANCE-INCOME-CLASS-PRIMARY-TYPE",
        "nta_positive_self_assessed_balance_income_class_primary_type_2024.csv",
        "scripts/extract_nta_shinkoku_income_class_primary_type.py",
        "NTA-2024-SHINKOKU-T2-XLSX;NTA-2024-SHINKOKU-T2-PDF;NTA-R06",
        "DERIVED_REPRODUCED_OFFICIAL_SURVEY_ESTIMATE_CROSSTAB",
        "25 total-income classes x five primary income-earner categories among positive-self-assessed-balance taxpayers; survey-estimated cells with exact row/column reconciliation",
    ),
    (
        "NTA-2024-POSITIVE-SELF-ASSESSED-BALANCE-TAX-FLOW-INCOME-CLASS-PRIMARY-TYPE",
        "nta_positive_self_assessed_balance_tax_flow_income_class_primary_type_2024.csv",
        "scripts/extract_nta_positive_balance_tax_flow.py",
        "NTA-2024-SHINKOKU-T1-XLSX;NTA-2024-SHINKOKU-T4-XLSX;NTA-2024-SHINKOKU-T5-XLSX",
        "DERIVED_REPRODUCED_OFFICIAL_SURVEY_TAX_FLOW_DIAGNOSTIC",
        "25 total-income classes x five primary income-earner categories within the positive-self-assessed-balance survey target; calculated tax, tax credits, withholding exposure/amount, self-assessed balance, and source-cell provenance",
    ),
    (
        "NTA-2024-CALCULATED-TAX-POSITIVE-DENOMINATOR-AUDIT",
        "nta_calculated_tax_positive_denominator_audit_2024.csv",
        "scripts/extract_nta_calculated_tax_denominator_audit.py",
        "NTA-SHINKOKU-JIKEIRETSU-T1-XLSX;NTA-SHINKOKU-JIKEIRETSU-T2-XLSX;NTA-2024-SHINKOKU-SAMPLE;NTA-R06",
        "DERIVED_REPRODUCED_OFFICIAL_DENOMINATOR_SEMANTICS_AUDIT",
        "Long-term Sample Survey taxpayer-count semantics audit: 2024 taxpayer count equals the 5,158,260 positive-self-assessed-balance survey target, not a public calculated-tax-positive person count; Table 2-2(1)-scope bound retained with explicit scope warning",
    ),
    (
        "NTA-2024-PRIVATE-SALARY-TAXPAYER-STATUS-BY-SALARY-CLASS",
        "nta_private_salary_taxpayer_status_by_salary_class_2024.csv",
        "scripts/extract_nta_private_salary_taxpayer_status.py",
        "NTA-MINKAN-2024-T16;NTA-MINKAN-METHODOLOGY",
        "DERIVED_REPRODUCED_OFFICIAL_PRIVATE_SALARY_TAXPAYER_STATUS_DIAGNOSTIC",
        "Four Table 16 panels x 14 salary classes; taxpayer/non-taxpayer counts and tax amounts split by year-end adjustment and 乙欄 exclusion; external wage-side diagnostic only, no additive join to self-assessed returns",
    ),
    (
        "NTA-2024-PRIVATE-SALARY-TAXPAYER-STATUS-SUMMARY",
        "nta_private_salary_taxpayer_status_summary_2024.csv",
        "scripts/extract_nta_private_salary_taxpayer_status.py",
        "NTA-MINKAN-2024-T16;NTA-MINKAN-METHODOLOGY",
        "DERIVED_REPRODUCED_OFFICIAL_PRIVATE_SALARY_TAXPAYER_STATUS_DIAGNOSTIC",
        "Five Table 16 summaries including 35,556,416 year-end-adjusted taxpayers among 52,797,680 private salary earners after 乙欄 exclusion; not a strict final calculated-tax-positive subset and not additive to positive self-assessed returns",
    ),
    (
        "NTA-2024-PRIVATE-SALARY-NOT-YEAR-END-ADJUSTED-BY-SALARY-CLASS",
        "nta_private_salary_not_year_end_adjusted_by_salary_class_2024.csv",
        "scripts/extract_nta_salary_return_overlap.py",
        "NTA-MINKAN-2024-T19",
        "DERIVED_REPRODUCED_OFFICIAL_PRIVATE_SALARY_NO_YEAR_END_ADJUSTMENT_DIAGNOSTIC",
        "Table 19 full-year/less-than-year x taxpayer/nontaxpayer/all x 14 salary classes; persons, salary and tax split by 乙欄, previous-employer salary unknown and other reasons; no person-level filed-or-processed income-tax linkage",
    ),
    (
        "NTA-2024-SALARY-RETURN-OVERLAP-AUDIT",
        "nta_salary_return_overlap_audit_2024.csv",
        "scripts/extract_nta_salary_return_overlap.py",
        "NTA-MINKAN-2024-T16;NTA-MINKAN-2024-T19;NTA-2024-SALARY-FILING-REQUIREMENT;NTA-R06;NTA-2024-PROCESSING-STATUS;NTA-2024-SHINKOKU-T1-XLSX;NTA-2024-SHINKOKU-T5-XLSX",
        "DERIVED_REPRODUCED_OFFICIAL_CROSS_SYSTEM_OVERLAP_AUDIT",
        "Payroll-side no-year-end-adjustment decomposition, >20m statutory filing candidate, salary-primary filed-or-processed status margins, pure Final return row and withholding exposure; exact cross-source person overlap remains NOT_IDENTIFIED and additive unions are prohibited",
    ),
    (
        "NTA-2024-POSITIVE-BALANCE-SALARY-RECEIPT-CLASS",
        "nta_positive_balance_salary_receipt_class_2024.csv",
        "scripts/extract_nta_salary_receipt_return_bridge.py",
        "NTA-2024-SHINKOKU-T7-XLSX;NTA-2024-SHINKOKU-T7-PDF",
        "DERIVED_REPRODUCED_OFFICIAL_SURVEY_SALARY_RECEIPT_BRIDGE",
        "Six Table 7 income-earner blocks x 12 salary-receipt classes within the positive-self-assessed-balance sample; salary-receipt persons/amount and salary-source-withholding exposure with source-cell provenance",
    ),
    (
        "NTA-2024-SALARY-PROCESSING-STATUS",
        "nta_salary_processing_status_2024.csv",
        "scripts/extract_nta_salary_processing_status.py",
        "NTA-2024-PROCESSING-STATUS;NTA-R06;NTA-2024-ANNUAL-TABLE-NOTES",
        "DERIVED_REPRODUCED_OFFICIAL_PROCESSING_STATUS",
        "Salary-primary 2024 processing rows: pure Final return, amended return, determination/correction, request for correction and filed-or-processed total with exact person-status identities",
    ),
    (
        "NTA-2024-SALARY-PROCESSING-STATUS-AUDIT",
        "nta_salary_processing_status_audit_2024.csv",
        "scripts/extract_nta_salary_processing_status.py",
        "NTA-2024-PROCESSING-STATUS;NTA-R06;NTA-2024-ANNUAL-TABLE-NOTES",
        "DERIVED_REPRODUCED_PROCESSING_SEMANTICS_AUDIT",
        "Canonicalizes 11,423,587 as filed-or-processed Table 2-2(1) salary population, separates pure Final return row 11,293,442 and deprecates the old final-return-population shorthand",
    ),
    (
        "NTA-2024-SALARY-RECEIPT-RETURN-BRIDGE",
        "nta_salary_receipt_return_bridge_2024.csv",
        "scripts/extract_nta_salary_receipt_return_bridge.py",
        "NTA-MINKAN-2024-T19;NTA-2024-SHINKOKU-T7-XLSX;NTA-2024-SHINKOKU-T7-PDF;NTA-2024-ANNUAL-T23-INCOME-TYPE;NTA-2024-ANNUAL-TABLE-NOTES;NTA-R06",
        "DERIVED_REPRODUCED_OFFICIAL_SALARY_RECEIPT_RETURN_BRIDGE_AUDIT",
        "Same-threshold >20m payroll/positive-balance salary-receipt diagnostic plus complete-survey Table 2-3 employment-income main/secondary semantics; exact cross-source person overlap remains NOT_IDENTIFIED",
    ),
    (
        "NTA-2024-SALARY-FILING-BRIDGE-SOURCE-MATRIX",
        "nta_salary_filing_bridge_source_matrix_2024.csv",
        "scripts/build_nta_salary_filing_bridge_source_matrix.py",
        "NTA-MINKAN-2024-T16;NTA-MINKAN-2024-T19;NTA-2024-SALARY-FILING-REQUIREMENT;NTA-2024-SHINKOKU-T7-XLSX;NTA-2024-PROCESSING-STATUS;NTA-2024-RETURN-PRESS-T31;NTA-2024-ANNUAL-T23-INCOME-TYPE;NTA-FY2024-WITHHOLDING-STATUS;NTA-NAGOYA-2024-SHINKOKU-21-XLSX;NTA-NAGOYA-2024-SHINKOKU-22-XLSX",
        "DERIVED_REPRODUCED_PUBLIC_SOURCE_DIMENSION_MATRIX",
        "Ten official 2024 payroll/legal/return/withholding/regional source families mapped across salary-receipt, year-end-adjustment, submission, processing, positive/refund, withholding, employer-sector and geography dimensions; no cross-family person link is observed",
    ),
    (
        "NTA-2024-SALARY-FILING-BRIDGE-IDENTIFICATION-AUDIT",
        "nta_salary_filing_bridge_identification_audit_2024.csv",
        "scripts/build_nta_salary_filing_bridge_source_matrix.py",
        "NTA-MINKAN-2024-T16;NTA-MINKAN-2024-T19;NTA-2024-SALARY-FILING-REQUIREMENT;NTA-2024-SHINKOKU-T7-XLSX;NTA-2024-PROCESSING-STATUS;NTA-2024-RETURN-PRESS-T31;NTA-2024-ANNUAL-T23-INCOME-TYPE;NTA-FY2024-WITHHOLDING-STATUS;NTA-NAGOYA-2024-SHINKOKU-21-XLSX;NTA-NAGOYA-2024-SHINKOKU-22-XLSX",
        "DERIVED_REPRODUCED_BOUNDED_NEGATIVE_SOURCE_AUDIT",
        "Bounded negative-source result: direct salary-receipt/year-end-adjustment x submitted-return/processing-status bridge is not found in the enumerated official source families; does not assert absence of unpublished administrative linkage",
    ),
    (
        "NTA-2024-SALARY-SOURCE-SYSTEM-COVERAGE",
        "nta_salary_source_system_coverage_2024.csv",
        "scripts/extract_nta_salary_source_system_coverage.py",
        "NTA-FY2024-WITHHOLDING-STATUS;NTA-MINKAN-2024-T1;NTA-MINKAN-METHODOLOGY;NTA-2024-SHINKOKU-T7-XLSX",
        "DERIVED_REPRODUCED_OFFICIAL_MONETARY_COVERAGE_DIAGNOSTIC",
        "FY2024 source-withholding salary payment/tax amounts split into Public Offices/Others/Total compared with Private Salary Survey Table 1; public-office person share remains NOT_IDENTIFIED and applying amount shares to Table 7 person counts is prohibited",
    ),
    (
        "PUBLIC-SECTOR-PERSON-COVERAGE-2024",
        "public_sector_person_coverage_audit_2024.csv",
        "scripts/extract_public_sector_person_coverage.py",
        "JINJI-2024-PUBLIC-SALARY-SURVEY-SUMMARY;JINJI-2024-PUBLIC-SALARY-SURVEY-T1;JINJI-2024-PUBLIC-SALARY-SURVEY-RESULTS;ESTAT-LOCAL-PUBLIC-SALARY-2024-T1;ESTAT-LOCAL-PUBLIC-SALARY-2024-METADATA;NTA-FY2024-WITHHOLDING-STATUS",
        "DERIVED_REPRODUCED_EXTERNAL_PUBLIC_WORKFORCE_COVERAGE_AUDIT",
        "2024 national covered public employees and local public employees as external person benchmarks; arithmetic subtotal 3,064,373 is explicitly not an NTA Public Offices denominator and cross-frame average/high-salary adjustments are prohibited",
    ),
    (
        "NTA-WITHHOLDING-SALARY-PERSON-SERIES-1991-2024",
        "nta_withholding_salary_person_series_1991_2024.csv",
        "scripts/extract_nta_withholding_person_series.py",
        "NTA-WITHHOLDING-LONG-TERM;NTA-WITHHOLDING-2006-STATUS;NTA-WITHHOLDING-2007-STATUS;NTA-FY2024-WITHHOLDING-STATUS",
        "DERIVED_REPRODUCED_HISTORICAL_PERSON_SERIES_WITH_DISCONTINUITY",
        "1991-2024 salary-source Public Offices/Others series: person fields are sample-survey estimates through 2006 and not published from 2007 onward while payment amounts continue",
    ),
    (
        "NTA-WITHHOLDING-PERSON-SERIES-DISCONTINUITY-AUDIT",
        "nta_withholding_person_series_discontinuity_audit.csv",
        "scripts/extract_nta_withholding_person_series.py",
        "NTA-WITHHOLDING-LONG-TERM;NTA-WITHHOLDING-2006-STATUS;NTA-WITHHOLDING-2007-STATUS;NTA-FY2024-WITHHOLDING-STATUS",
        "DERIVED_REPRODUCED_HISTORICAL_IDENTIFICATION_AUDIT",
        "Documents 2006 as the last published Public Offices/Others person-estimate year, 2007 as the first missing year, 18 missing years through 2024, and prohibits 2006 person-share extrapolation",
    ),
    (
        "NTA-2024-ANNUAL-INCOME-CLASS-PRIMARY-TYPE-FILING-STATUS",
        "nta_income_class_primary_type_filing_status_2024.csv",
        "scripts/extract_nta_annual_income_class_filing_status.py",
        "NTA-R06;NTA-2024-SHINKOKU-T2-XLSX",
        "DERIVED_REPRODUCED_ADMINISTRATIVE_CROSSTAB",
        "Exact annual-statistics filed-or-processed, positive-self-assessed-balance, refund, and residual counts for 25 total-net-income classes x five primary income-earner categories; 125 positive cells cross-check exactly to Sample Survey Table 2",
    ),
    (
        "NTA-2024-FINAL-RETURN-SUBMISSION-PROCESSING-RECONCILIATION",
        "nta_final_return_submission_processing_reconciliation_2024.csv",
        "scripts/extract_nta_final_return_processing_reconciliation.py",
        "NTA-2024-RETURN-PRESS-T31;NTA-2024-PROCESSING-STATUS;NTA-R06",
        "DERIVED_REPRODUCED_CROSS_PUBLICATION_POPULATION_SEMANTICS_AUDIT",
        "Six income categories comparing rounded press-release submitted-return counts with exact Table 2-1 Final return processing rows and filed-or-processed totals; statistical objects are explicitly non-equated",
    ),
    (
        "NTA-2024-FINAL-RETURN-PROCESSING-SEMANTICS-AUDIT",
        "nta_final_return_processing_semantics_audit_2024.csv",
        "scripts/extract_nta_final_return_processing_reconciliation.py",
        "NTA-2024-RETURN-PRESS-T31;NTA-2024-PROCESSING-STATUS;NTA-R06",
        "DERIVED_REPRODUCED_STAGE1_NUMERATOR_SEMANTICS_AUDIT",
        "Retains 23,090,075 as the exact Table 2-1 Final return processing-row benchmark while prohibiting interpretation as the separate press-release count of submitted returns",
    ),
    (
        "NTA-2024-T31-ROUNDED-PRIMARY-TYPES",
        "nta_table31_primary_type_rounded_2024.csv",
        "scripts/extract_nta_stage2_holdout.py",
        "NTA-2024-RETURN-PRESS-T31",
        "DERIVED_REPRODUCED_POINT_CHECK_INPUT",
        "Displayed thousand-person Table 3-1 counts with explicit five-category versus grand-total rounding mismatch",
    ),
    (
        "METI-2021-VAT-INTERNAL-HOURS-DISTRIBUTION",
        "meti_2021_vat_internal_hours_distribution.csv",
        "scripts/extract_meti_vat_internal_hours.py",
        "METI-2021-SME-TAX-SURVEY",
        "DERIVED_REPRODUCED_CONDITIONAL_VAT_HOURS_DISTRIBUTION",
        "Nine published consumption-tax internal-hours bins for n=1,514 respondents, with one-decimal rounding intervals, compatible integer counts, and explicit source-selection-scope inconsistency flag",
    ),
    (
        "METI-2021-VAT-INTERNAL-HOURS-BOUNDS",
        "meti_2021_vat_internal_hours_bounds.csv",
        "scripts/extract_meti_vat_internal_hours.py",
        "METI-2021-SME-TAX-SURVEY",
        "DERIVED_PARTIAL_IDENTIFICATION_CONDITIONAL_VAT_HOURS",
        "Respondent-subset VAT internal-hours mean lower bound 15.126155878468 h per respondent for the reported Q8-3 period; Q8-3 does not explicitly label tax-item hours as annual; uncapped upper bound open due 100+ top code",
    ),
    (
        "METI-VAT-INTERNAL-HOURS-SOURCE-LINEAGE",
        "meti_vat_internal_hours_source_lineage.csv",
        "scripts/build_meti_vat_hours_source_lineage.py",
        "METI-2019-SME-TAX-REPORT-ARCHIVED;METI-2019-REPORT-LISTING-20210213-ARCHIVED;METI-2020-SME-TAX-REPORT-ARCHIVED;METI-2020-REPORT-LISTING-20211202-ARCHIVED;METI-2021-SME-TAX-SURVEY;METI-2021-REPORT-LISTING-20220718-ARCHIVED;RIETI-2021-QUANT-TAX-COMPLIANCE-COST",
        "DERIVED_SURVEY_LINEAGE_IDENTIFICATION_AUDIT",
        "2019-2021 METI VAT-hours survey lineage: 2019 has explicit fiscal-year design but no public VAT-hour numbers; 2020 collected VAT hours but public report/data listing omit numeric microdata; 2021 publishes numeric distribution but tax-item period and selector metadata remain unresolved",
    ),
    (
        "VAT-TRANSITION-SYSTEM-SUBSIDY-BOUNDS",
        "vat_transition_system_subsidy_bounds.csv",
        "scripts/build_vat_transition_system_subsidy_bounds.py",
        "SMRJ-FY2019-LIGHT-RATE-SUBSIDY-PERFORMANCE",
        "DERIVED_SELECTED_GRANT_RECORD_TRANSITION_EXPENDITURE_LOWER_BOUND",
        "FY2019 and cumulative reduced-rate transition support: observed subsidy flows imply selected grant-record eligible expenditure of at least the subsidy amount; explicitly transition-only, nonrepresentative, and not persistent c_VAT",
    ),
    (
        "SMEA-FY2025-INVOICE-TRANSACTION-OVERALL",
        "smea_fy2025_invoice_transaction_overall.csv",
        "scripts/build_smea_fy2025_invoice_transaction_bridge.py",
        "SMEA-FY2025-INVOICE-TRANSACTION-SURVEY-ARCHIVED",
        "DERIVED_POST_2023_REALIZED_TRANSACTION_OUTCOME_EVIDENCE",
        "Eighteen overall survey/frame metrics from the SME Agency FY2025 50,000-business invoice-transaction survey, including rounded-count-compatible ranges for registration pressure, largest-customer price reduction/transaction stop, and negotiation access",
    ),
    (
        "SMEA-FY2025-INVOICE-TRANSACTION-INDUSTRY",
        "smea_fy2025_invoice_transaction_industry.csv",
        "scripts/build_smea_fy2025_invoice_transaction_bridge.py",
        "SMEA-FY2025-INVOICE-TRANSACTION-SURVEY-ARCHIVED",
        "DERIVED_POST_2023_TRANSACTION_OUTCOME_INDUSTRY_HETEROGENEITY",
        "Seven-industry response table for tax-status transition, invoice registration, customer registration requirement, largest-customer price reduction/transaction stop, and negotiation-access failure; denominators remain question-specific",
    ),
    (
        "JCCI-INVOICE-NETWORK-DISTORTION-BRIDGE",
        "jcci_invoice_network_distortion_bridge.csv",
        "scripts/build_jcci_invoice_network_distortion_bridge.py",
        "JCCI-2024-INVOICE-BACKOFFICE-SURVEY;JCCI-2025-INVOICE-SURVEY",
        "DERIVED_POST_2023_INVOICE_NETWORK_RESPONSE_EVIDENCE",
        "Thirty-seven 2024/2025 JCCI survey metrics separating realized supplier-network status, future price/supplier intentions, invoice-registration pressure and substitution frictions; no cross-year panel trend or macro output effect inferred",
    ),
    (
        "ICHIKAWA-2019-VAT-10M-THRESHOLD-NATIONALIZED-ESTIMATES",
        "ichikawa_2019_vat_10m_threshold_nationalized_estimates.csv",
        "scripts/build_ichikawa_2019_vat_10m_threshold_bridge.py",
        "ICHIKAWA-ARUDCHELVAN-ONJI-2019-VAT-10M-BUNCHING",
        "DERIVED_10M_THRESHOLD_NATIONALIZED_BEHAVIOR_AND_MECHANISM_SCENARIOS",
        "Eight metrics from the 10m-JPY threshold study: nationalized excess-buncher scale, tax windfall, and two mechanism-sensitive lost-sales scenarios; lost sales are explicitly not treated as GDP or welfare bounds",
    ),
    (
        "ICHIKAWA-2019-VAT-10M-THRESHOLD-PREPOST-BUNCHING",
        "ichikawa_2019_vat_10m_threshold_prepost_bunching.csv",
        "scripts/build_ichikawa_2019_vat_10m_threshold_bridge.py",
        "ICHIKAWA-ARUDCHELVAN-ONJI-2019-VAT-10M-BUNCHING",
        "DERIVED_2014_VAT_HIKE_PREPOST_BUNCHING_COMPARISON",
        "Four same-window pre/post comparisons around the 2014 3-percentage-point VAT hike; all overlap under the paper's 95-percent-CI decision rule and are used only as evidence on motives, not as a tax elasticity or macro a_alloc estimate",
    ),
    (
        "RIETI-VAT-THRESHOLD-BUNCHING-RESPONSE",
        "rieti_vat_threshold_bunching_response.csv",
        "scripts/build_rieti_vat_threshold_structural_bridge.py",
        "RIETI-2021-SME-VAT-COMPLIANCE",
        "DERIVED_LOCAL_HISTORICAL_MARGINAL_BUNCHER_RESPONSE",
        "Three historical 30m-JPY threshold-period rows used by RIETI structural estimation; preserves excess-bunching estimates and convergence-method marginal-buncher sales-response upper bounds without treating them as aggregate output loss",
    ),
    (
        "RIETI-VAT-THRESHOLD-STRUCTURAL-ESTIMATES",
        "rieti_vat_threshold_structural_estimates.csv",
        "scripts/build_rieti_vat_threshold_structural_bridge.py",
        "RIETI-2021-SME-VAT-COMPLIANCE",
        "DERIVED_MODEL_CONTINGENT_LOCAL_STRUCTURAL_PARAMETERS",
        "Six Table-5 structural estimate rows for 1992/1997 reforms and all/firms/sole-proprietor groups; theta remains a broad model compliance-cost share of value added, not national real-resource c_VAT or macro a_alloc",
    ),
    (
        "BSWS-2019-INDUSTRY-HOURLY-WAGE-BRIDGE",
        "bsws_2019_industry_hourly_wage_bridge.csv",
        "scripts/build_bsws_2019_industry_hourly_wage_bridge.py",
        "ESTAT-BSWS-2019-INDUSTRY-WAGE-DB-SNAPSHOT;ESTAT-BSWS-2019-INDUSTRY-WAGE-T1",
        "DERIVED_OFFICIAL_WAGE_COMPONENT_BRIDGE",
        "Seventeen industry-total/major-industry rows with two transparent hourly-wage ratios from 2019 BSWS components; RIETI exact hourly-wage formula is not claimed identified",
    ),
    (
        "METI-VAT-INTERNAL-LABOR-COST-WAGE-SENSITIVITY",
        "meti_vat_internal_labor_cost_wage_sensitivity.csv",
        "scripts/build_meti_vat_internal_labor_cost_bridge.py",
        "METI-2021-SME-TAX-SURVEY;ESTAT-BSWS-2019-INDUSTRY-WAGE-DB-SNAPSHOT",
        "DERIVED_MECHANICAL_WAGE_CONVERSION_SENSITIVITY",
        "Thirty-four METI-hours x BSWS-wage scenarios; reported-period respondent sensitivity only, explicitly not annual, population, GDP-share, or national c_VAT estimate",
    ),
    (
        "VAT-COMPLIANCE-OBSERVED-EVIDENCE",
        "vat_compliance_observed_evidence.csv",
        "scripts/extract_vat_compliance_evidence.py",
        "METI-2019-SME-TAX-REPORT-ARCHIVED;METI-2019-REPORT-LISTING-20210213-ARCHIVED;METI-2020-SME-TAX-REPORT-ARCHIVED;METI-2020-REPORT-LISTING-20211202-ARCHIVED;METI-2021-SME-TAX-SURVEY;METI-2021-REPORT-LISTING-20220718-ARCHIVED;SMRJ-FY2019-LIGHT-RATE-SUBSIDY-PERFORMANCE;ESTAT-BSWS-2019-INDUSTRY-WAGE-T1;ESTAT-BSWS-2019-INDUSTRY-WAGE-DB-SNAPSHOT;JCCI-2024-INVOICE-BACKOFFICE-SURVEY;JCCI-2025-INVOICE-SURVEY;SMEA-FY2025-INVOICE-TRANSACTION-SURVEY-ARCHIVED;ICHIKAWA-ARUDCHELVAN-ONJI-2019-VAT-10M-BUNCHING;RIETI-2019-VAT-COMPLIANCE-FIRM-GROWTH;RIETI-2021-SME-VAT-COMPLIANCE;RIETI-2021-QUANT-TAX-COMPLIANCE-COST;MOF-CONSUMPTION-TAX-SME-EXEMPTION-THRESHOLD;NTA-CONSUMPTION-TAX-BASIC;NTA-INVOICE-SYSTEM-OVERVIEW",
        "DERIVED_REPRODUCED_VAT_COMPLIANCE_EVIDENCE_REGISTRY",
        "Japan-specific observed VAT/invoice burden, firm-size back-office structure, all-tax compliance-cost context, threshold/bunching research evidence, and official institutional rules; observed response shares are not converted into GDP effects",
    ),
    (
        "VAT-COMPLIANCE-IDENTIFICATION-STATUS",
        "vat_compliance_identification_status.csv",
        "scripts/extract_vat_compliance_evidence.py",
        "METI-2019-SME-TAX-REPORT-ARCHIVED;METI-2019-REPORT-LISTING-20210213-ARCHIVED;METI-2020-SME-TAX-REPORT-ARCHIVED;METI-2020-REPORT-LISTING-20211202-ARCHIVED;METI-2021-SME-TAX-SURVEY;METI-2021-REPORT-LISTING-20220718-ARCHIVED;SMRJ-FY2019-LIGHT-RATE-SUBSIDY-PERFORMANCE;ESTAT-BSWS-2019-INDUSTRY-WAGE-T1;ESTAT-BSWS-2019-INDUSTRY-WAGE-DB-SNAPSHOT;JCCI-2024-INVOICE-BACKOFFICE-SURVEY;JCCI-2025-INVOICE-SURVEY;SMEA-FY2025-INVOICE-TRANSACTION-SURVEY-ARCHIVED;ICHIKAWA-ARUDCHELVAN-ONJI-2019-VAT-10M-BUNCHING;RIETI-2019-VAT-COMPLIANCE-FIRM-GROWTH;RIETI-2021-SME-VAT-COMPLIANCE;RIETI-2021-QUANT-TAX-COMPLIANCE-COST;MOF-CONSUMPTION-TAX-SME-EXEMPTION-THRESHOLD;NTA-CONSUMPTION-TAX-BASIC;NTA-INVOICE-SYSTEM-OVERVIEW",
        "DERIVED_REPRODUCED_VAT_COMPLIANCE_IDENTIFICATION_AUDIT",
        "Separates observed burden evidence from non-identified VAT-specific macro resource cost, productive redeployment, and allocative-efficiency parameters; prohibits zero-rate/abolition equivalence and one-for-one GDP conversion",
    ),
    (
        "VAT-COMPLIANCE-PRODUCTIVITY-SENSITIVITY",
        "vat_compliance_productivity_sensitivity.csv",
        "research/vat_compliance_productivity/run_vat_compliance_productivity.py",
        "JCCI-2024-INVOICE-BACKOFFICE-SURVEY;JCCI-2025-INVOICE-SURVEY;SMEA-FY2025-INVOICE-TRANSACTION-SURVEY-ARCHIVED;ICHIKAWA-ARUDCHELVAN-ONJI-2019-VAT-10M-BUNCHING;RIETI-2019-VAT-COMPLIANCE-FIRM-GROWTH;RIETI-2021-SME-VAT-COMPLIANCE;RIETI-2021-QUANT-TAX-COMPLIANCE-COST;MOF-CONSUMPTION-TAX-SME-EXEMPTION-THRESHOLD;NTA-CONSUMPTION-TAX-BASIC;NTA-INVOICE-SYSTEM-OVERVIEW",
        "MODEL_CONTINGENT_STRESS_TEST_NOT_EMPIRICAL_BOUND",
        "Four institutional VAT regimes x 300 stress points; rate effects, household distribution and financing are excluded; only full institutional abolition activates the compliance/allocation level-effect channel",
    ),
    (
        "VAT-COMPLIANCE-PRODUCTIVITY-REGIME-SUMMARY",
        "vat_compliance_productivity_regime_summary.csv",
        "research/vat_compliance_productivity/run_vat_compliance_productivity.py",
        "JCCI-2024-INVOICE-BACKOFFICE-SURVEY;JCCI-2025-INVOICE-SURVEY;SMEA-FY2025-INVOICE-TRANSACTION-SURVEY-ARCHIVED;ICHIKAWA-ARUDCHELVAN-ONJI-2019-VAT-10M-BUNCHING;RIETI-2019-VAT-COMPLIANCE-FIRM-GROWTH;RIETI-2021-SME-VAT-COMPLIANCE;RIETI-2021-QUANT-TAX-COMPLIANCE-COST;MOF-CONSUMPTION-TAX-SME-EXEMPTION-THRESHOLD;NTA-CONSUMPTION-TAX-BASIC;NTA-INVOICE-SYSTEM-OVERVIEW",
        "MODEL_CONTINGENT_STRESS_TEST_SUMMARY",
        "Regime-level range summary: current, 5%, and zero-rate administration-retained regimes have zero institutional dividend by construction; abolition range is a chosen stress grid, not an empirical bound",
    ),
    (
        "NTA-2026-STATUTORY-PARAMETERS",
        "income_tax_2026_statutory_parameters.csv",
        "scripts/build_income_tax_2026_statutory_parameters.py",
        "NTA-2026-TAX-REFORM;NTA-2026-INCOME-TAX;NTA-SALARY-DEDUCTION-1410;NTA-INCOME-TAX-RATE-2260;NTA-2026-PENSION-TAX;NTA-2026-PENSION-DETAIL;NTA-2026-DEPENDENT-DEDUCTION",
        "DERIVED_REPRODUCED_VERIFIED_RULES",
        "Versioned 2026 statutory tax parameters with official source locators and raw SHA-256 values",
    ),
]


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def row_count(path):
    with path.open(encoding="utf-8", newline="") as f:
        return max(0, sum(1 for _ in f) - 1)


def main():
    rows = []
    registered = set()
    for aid, rel, generator, source_ids, status, description in SPECS:
        path = DERIVED / rel
        if not path.exists():
            raise SystemExit(f"missing derived artifact: {path}")
        if rel in registered:
            raise SystemExit(f"duplicate derived path: {rel}")
        registered.add(rel)
        rows.append({
            "artifact_id": aid,
            "derived_file": str(path.relative_to(ROOT)),
            "generator": generator,
            "source_ids": source_ids,
            "row_count": row_count(path),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "status": status,
            "description": description,
        })

    actual = {
        p.name for p in DERIVED.iterdir()
        if p.is_file()
    }
    if actual != registered:
        raise SystemExit(
            "derived catalog mismatch: "
            f"unregistered={sorted(actual-registered)} "
            f"missing={sorted(registered-actual)}"
        )

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=list(rows[0]), lineterminator="\n"
        )
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} artifacts")


if __name__ == "__main__":
    main()
