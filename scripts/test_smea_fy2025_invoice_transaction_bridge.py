#!/usr/bin/env python3
from pathlib import Path
import csv, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
O=ROOT/'data/derived/smea_fy2025_invoice_transaction_overall.csv'
I=ROOT/'data/derived/smea_fy2025_invoice_transaction_industry.csv'
C=ROOT/'data/source_catalog.csv'

def read(p):
    with p.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))

o={r['metric_id']:r for r in read(O)}; ind={r['industry_code']:r for r in read(I)}; cat={r['source_id']:r for r in read(C)}
assert len(o)==18 and len(ind)==7
expect={
 'survey_target_businesses':'50000','survey_responses':'15425','survey_response_rate':'0.309',
 'invoice_start_became_taxable_share':'0.118','currently_exempt_share':'0.729','invoice_registered_share':'0.228',
 'customer_required_registration_for_continuation_share':'0.143','future_registration_consider_share':'0.095',
 'post_invoice_price_reduced_or_transaction_stopped_share':'0.038','post_invoice_price_unchanged_share':'0.798',
 'post_invoice_price_increased_share':'0.119','invoice_price_negotiation_no_opportunity_share':'0.128',
 'previous_2023dec_post_invoice_price_reduced_or_stopped_share':'0.036',
}
for k,v in expect.items(): assert o[k]['value']==v,(k,o[k]['value'],v)
assert o['customer_required_registration_for_continuation_share']['rounded_count_lower']=='2184'
assert o['customer_required_registration_for_continuation_share']['rounded_count_upper']=='2198'
assert o['post_invoice_price_reduced_or_transaction_stopped_share']['rounded_count_lower']=='553'
assert o['post_invoice_price_reduced_or_transaction_stopped_share']['rounded_count_upper']=='567'
assert o['invoice_price_negotiation_no_opportunity_share']['rounded_count_lower']=='1873'
assert o['invoice_price_negotiation_no_opportunity_share']['rounded_count_upper']=='1887'
assert o['post_invoice_price_reduced_or_transaction_stopped_share']['model_use']=='OBSERVED_REALIZED_PRICE_OR_TRANSACTION_ADVERSE_OUTCOME'
assert o['previous_2023dec_post_invoice_price_reduced_or_stopped_share']['model_use']=='CROSS_SECTION_COMPARISON_ONLY_NOT_PANEL_TREND'
assert ind['construction']['customer_required_registration_for_continuation_share']=='0.327'
assert ind['construction']['post_invoice_price_reduced_or_transaction_stopped_share']=='0.059'
assert ind['transport_postal']['post_invoice_price_reduced_or_transaction_stopped_share']=='0.079'
assert ind['wholesale']['post_invoice_price_reduced_or_transaction_stopped_share']=='0.064'
assert ind['services']['post_invoice_price_reduced_or_transaction_stopped_share']=='0.033'
for r in ind.values():
    assert r['identification_status']=='OBSERVED_INDUSTRY_HETEROGENEITY_SURVEY_RESPONSE'
    assert r['model_use']=='HETEROGENEITY_CONTEXT_NOT_POPULATION_CAUSAL_EFFECT'
assert cat['SMEA-FY2025-INVOICE-TRANSACTION-SURVEY-ARCHIVED']['sha256']=='5d35852bc1602c575425532244d7475393dc7385d24cc0cbfcc32f553af57d7b'
subprocess.run([sys.executable,str(ROOT/'scripts/build_smea_fy2025_invoice_transaction_bridge.py'),'--check'],cwd=ROOT,check=True)
print('SMEA FY2025 invoice transaction tests: OK (15,425 responses; 14.3% registration pressure; 3.8% largest-customer price reduction/stop; industry heterogeneity guarded)')
