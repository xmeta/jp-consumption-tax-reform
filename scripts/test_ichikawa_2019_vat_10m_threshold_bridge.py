#!/usr/bin/env python3
from pathlib import Path
import csv, subprocess, sys
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[1]
N=ROOT/'data/derived/ichikawa_2019_vat_10m_threshold_nationalized_estimates.csv'
P=ROOT/'data/derived/ichikawa_2019_vat_10m_threshold_prepost_bunching.csv'
C=ROOT/'data/source_catalog.csv'

def read(p):
    with p.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))

n={r['metric_id']:r for r in read(N)}; p=read(P); c={r['source_id']:r for r in read(C)}
expected={
 'vat_exemption_threshold_yen':'10000000',
 'national_bunching_region_firm_count':'308435',
 'national_bunching_region_value_added_share':'0.413',
 'vat_rate_table4':'0.08',
 'estimated_excess_buncher_firm_count':'56651',
 'estimated_tax_windfall_yen_per_year':'16850000000',
 'lost_sales_all_excess_real_adjustment_scenario_yen':'84980000000',
 'lost_sales_missing_mass_scenario_yen':'3140000000',
}
assert set(n)==set(expected)
for k,v in expected.items(): assert n[k]['value']==v,(k,n[k]['value'],v)
for k in ['lost_sales_all_excess_real_adjustment_scenario_yen','lost_sales_missing_mass_scenario_yen']:
    assert n[k]['identification_status']=='MECHANISM_SENSITIVE_SCENARIO_ESTIMATE'
    assert n[k]['model_use']=='DO_NOT_TREAT_AS_EMPIRICAL_BOUND_OR_GDP_LOSS'
assert n['estimated_tax_windfall_yen_per_year']['model_use']=='TAX_REVENUE_CONTEXT_NOT_WELFARE_LOSS'
assert len(p)==4
assert [r['bunching_window_below_threshold_million_yen'] for r in p]==['1','1.5','2','2.5']
assert [r['post_minus_pre'] for r in p]==['-0.037','-0.159','0.033','-0.019']
for r in p:
    assert r['paper_ci_overlap_rule_no_detectable_change']=='YES'
    assert r['model_use']=='COMPLIANCE_MOTIVE_EVIDENCE_NOT_TAX_RATE_ELASTICITY_OR_MACRO_A_ALLOC'
assert Decimal(n['lost_sales_all_excess_real_adjustment_scenario_yen']['value']) / Decimal(n['lost_sales_missing_mass_scenario_yen']['value']) > Decimal('27')
assert c['ICHIKAWA-ARUDCHELVAN-ONJI-2019-VAT-10M-BUNCHING']['sha256']=='93f68057104b6a4bb693c5fafbea8386ad830f6f3714291968d9937784517b28'
subprocess.run([sys.executable,str(ROOT/'scripts/build_ichikawa_2019_vat_10m_threshold_bridge.py'),'--check'],cwd=ROOT,check=True)
print('Ichikawa 2019 VAT 10m-threshold tests: OK (56,651 excess bunchers; 84.98bn vs 3.14bn lost-sales scenarios; mechanism not promoted to macro a_alloc)')
