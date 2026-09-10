#!/usr/bin/env python3
from pathlib import Path
import csv, subprocess, sys
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/derived/vat_transition_system_subsidy_bounds.csv'
CAT=ROOT/'data/source_catalog.csv'

def read(p):
    with p.open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))
rows=read(OUT); assert len(rows)==2
by={r['scope_id']:r for r in rows}
assert set(by)=={'fy2019','cumulative_through_fy2019'}

r=by['fy2019']
assert r['application_count']=='122825'
assert r['grant_count']=='94875'
assert r['subsidy_amount_yen']=='22914612620'
# Recompute rather than depend on decimal display spelling.
assert abs(Decimal(r['average_subsidy_yen_per_grant_record'])-(Decimal(22914612620)/Decimal(94875))) < Decimal('0.000000000001')
assert r['eligible_transition_expenditure_lower_bound_yen']=='22914612620'

r=by['cumulative_through_fy2019']
assert r['application_count']=='221337'
assert r['grant_count']=='174781'
assert r['subsidy_amount_yen']=='44659886587'
assert abs(Decimal(r['average_subsidy_yen_per_grant_record'])-(Decimal(44659886587)/Decimal(174781))) < Decimal('0.000000000001')
assert r['eligible_transition_expenditure_lower_bound_yen']=='44659886587'

for r in rows:
    assert r['cost_duration_class']=='TRANSITION_IMPLEMENTATION_COST'
    assert r['persistent_annual_cost_identified']=='NO'
    assert r['population_representative']=='NO'
    assert r['model_use']=='TRANSITION_COST_CONTEXT_ONLY_NOT_PERSISTENT_C_VAT'
    assert Decimal(r['eligible_transition_expenditure_lower_bound_yen'])==Decimal(r['subsidy_amount_yen'])

cat={r['source_id']:r for r in read(CAT)}
assert cat['SMRJ-FY2019-LIGHT-RATE-SUBSIDY-PERFORMANCE']['sha256']=='7b30ebbb9dc0da5b94e56c0e8df1d935672bfb4f0729564bc76390bcf033d4c3'
assert (ROOT/cat['SMRJ-FY2019-LIGHT-RATE-SUBSIDY-PERFORMANCE']['raw_file']).exists()
subprocess.run([sys.executable,str(ROOT/'scripts/build_vat_transition_system_subsidy_bounds.py'),'--check'],cwd=ROOT,check=True)
print('VAT transition subsidy-bound tests: OK (official subsidy flows bound selected transition expenditure; no recurring c_VAT calibration)')
