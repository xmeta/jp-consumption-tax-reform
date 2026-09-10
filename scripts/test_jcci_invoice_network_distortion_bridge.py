#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv, subprocess, sys
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/derived/jcci_invoice_network_distortion_bridge.csv'
CAT=ROOT/'data/source_catalog.csv'

def read(p):
    with p.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
rows=read(OUT); by={(r['survey_year'],r['metric_id']):r for r in rows}; cat={r['source_id']:r for r in read(CAT)}
assert len(rows)==37
anchors={
 ('2024','former_exempt_b2b_invoice_registration_share'):'0.733',
 ('2024','nonregistered_exempt_b2b_future_registration_consider_share'):'0.640',
 ('2024','nonregistered_exempt_b2b_register_if_customer_requests_share'):'0.477',
 ('2024','post_intro_exempt_supplier_almost_all_continue_share'):'0.740',
 ('2024','post_intro_exempt_supplier_all_transactions_ended_share'):'0.052',
 ('2024','post_intro_exempt_supplier_reported_contraction_category_share'):'0.259',
 ('2024','future_exempt_supplier_continue_share'):'0.471',
 ('2024','future_exempt_supplier_stop_or_review_share'):'0.294',
 ('2025','former_exempt_b2b_invoice_registration_share'):'0.786',
 ('2025','nonregistered_exempt_b2b_future_registration_consider_share'):'0.508',
 ('2025','nonregistered_exempt_b2b_register_if_customer_requests_share'):'0.459',
 ('2025','taxable_firms_with_exempt_supplier_purchases_share'):'0.437',
 ('2025','exempt_supplier_purchase_amount_ge_1m_yen_share'):'0.576',
 ('2025','current_price_unchanged_self_absorb_share'):'0.875',
 ('2025','current_pass_to_sales_price_share'):'0.093',
 ('2025','current_lower_purchase_price_by_denied_credit_share'):'0.054',
 ('2025','current_lower_purchase_price_by_full_tax_share'):'0.022',
 ('2025','future_exempt_supplier_price_review_share'):'0.305',
 ('2025','future_exempt_supplier_all_stop_share'):'0.020',
 ('2025','future_exempt_supplier_mostly_stop_share'):'0.098',
 ('2025','future_price_or_supplier_review_share'):'0.423',
 ('2025','future_supplier_reduction_or_exit_share'):'0.118',
 ('2025','continue_reason_no_alternative_supplier_share'):'0.446',
 ('2025','continue_reason_search_effort_not_worth_it_share'):'0.391',
 ('2025','continue_reason_labor_shortage_requires_exempt_suppliers_share'):'0.380',
}
for k,v in anchors.items(): assert by[k]['value']==v,(k,by[k]['value'],v)
assert by[('2024','post_intro_exempt_supplier_reported_contraction_category_share')]['model_use']=='INCIDENCE_ONLY_NOT_CAUSAL_OUTPUT_LOSS'
assert by[('2025','future_price_or_supplier_review_share')]['model_use']=='INTENTION_NOT_REALIZED_NETWORK_EFFECT'
assert by[('2025','future_supplier_reduction_or_exit_share')]['model_use']=='INTENTION_NOT_REALIZED_NETWORK_EFFECT'
for k in [('2025','current_price_unchanged_self_absorb_share'),('2025','current_pass_to_sales_price_share'),('2025','current_lower_purchase_price_by_denied_credit_share'),('2025','current_lower_purchase_price_by_full_tax_share')]:
    assert by[k]['evidence_type']=='MULTIPLE_RESPONSE_SHARE'
    assert by[k]['model_use']=='INCIDENCE_ONLY_NOT_UNIQUE_FIRM_SHARE_OR_OUTPUT_EFFECT'
for k in [('2025','continue_reason_no_alternative_supplier_share'),('2025','continue_reason_search_effort_not_worth_it_share'),('2025','continue_reason_labor_shortage_requires_exempt_suppliers_share')]:
    assert by[k]['model_use']=='SUBSTITUTION_FRICTION_CONTEXT_NOT_MACRO_OUTPUT_EFFECT'
# Do not infer a panel trend from 73.3% -> 78.6%; survey explicitly says respondents differ.
assert 'not the same businesses' in by[('2025','former_exempt_b2b_invoice_registration_share')]['note']
assert cat['JCCI-2024-INVOICE-BACKOFFICE-SURVEY']['sha256']=='7ab80915efa7659e6f25cc152b7b5d2eef3c70038333eb6bc043642759d56126'
assert cat['JCCI-2025-INVOICE-SURVEY']['sha256']=='d89a599e900146c7c8ec5e1f4b0702b9dd7d292b47042e9e57186dda4525605e'
subprocess.run([sys.executable,str(ROOT/'scripts/build_jcci_invoice_network_distortion_bridge.py'),'--check'],cwd=ROOT,check=True)
print('JCCI invoice-network distortion tests: OK (realized 2024 network contraction categories + 2025 future review/exit intentions + substitution frictions; no cross-year panel inference)')
