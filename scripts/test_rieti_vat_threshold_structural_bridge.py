#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv, subprocess, sys
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
B = ROOT/'data/derived/rieti_vat_threshold_bunching_response.csv'
S = ROOT/'data/derived/rieti_vat_threshold_structural_estimates.csv'
CAT = ROOT/'data/source_catalog.csv'

def read(p):
    with p.open(encoding='utf-8', newline='') as f: return list(csv.DictReader(f))

b = read(B); s = read(S); cat={r['source_id']:r for r in read(CAT)}
assert len(b) == 3
assert len(s) == 6
assert [r['sample_id'] for r in b] == ['1989_1991','1992_1994','1997_1999']
assert [r['published_delta_y_over_threshold'] for r in b] == ['0.550','0.543','0.542']
assert [r['marginal_buncher_sales_response_upper_million_yen'] for r in b] == ['16.498','16.277','16.261']
for r in b:
    assert r['threshold_million_yen'] == '30'
    assert r['identification_status'] == 'LOCAL_HISTORICAL_MARGINAL_BUNCHER_RESPONSE_UPPER_BOUND'
    assert r['model_use'] == 'THRESHOLD_DISTORTION_EVIDENCE_NOT_MACRO_A_ALLOC'
    assert Decimal(r['recomputed_delta_y_over_threshold']) > Decimal('0.54')
    assert Decimal(r['recomputed_delta_y_over_threshold']) < Decimal('0.551')

idx={(r['reform_id'],r['population_group']):r for r in s}
expected={
 ('1992','all'):('0.130','0.027','1.365'),
 ('1997','all'):('0.140','0.040','1.47'),
 ('1992','firms'):('0.091','0.036','0.9555'),
 ('1997','firms'):('0.111','0.055','1.1655'),
 ('1992','sole_proprietors'):('0.116','0.018','1.218'),
 ('1997','sole_proprietors'):('0.130','0.037','1.365'),
}
for k,(theta,se,implied) in expected.items():
    r=idx[k]
    assert r['compliance_cost_theta']==theta
    assert r['compliance_cost_theta_se']==se
    assert r['mechanical_value_added_at_30m_sales_million_yen']=='10.5'
    assert r['mechanical_compliance_cost_at_30m_sales_million_yen']==implied
    assert r['real_resource_cost_interpretation']=='NO'
    assert r['model_use']=='LOCAL_THRESHOLD_STRUCTURAL_EVIDENCE_NOT_C_VAT_OR_MACRO_A_ALLOC'
assert idx[('1992','all')]['tax_elasticity_se']=='0.67'  # exact Table 5 transcription; unusually large but source-confirmed
assert cat['RIETI-2021-SME-VAT-COMPLIANCE']['sha256']=='397ef1b7202d6aec440e422587aa3ab09a1144ce0108db79fbc61166e64fe49b'
subprocess.run([sys.executable,str(ROOT/'scripts/build_rieti_vat_threshold_structural_bridge.py'),'--check'],cwd=ROOT,check=True)
print('RIETI VAT-threshold structural-bridge tests: OK (local historical distortion evidence kept separate from c_VAT and macro a_alloc)')
