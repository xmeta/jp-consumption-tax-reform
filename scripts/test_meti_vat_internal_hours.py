#!/usr/bin/env python3
from pathlib import Path
import csv, itertools, subprocess, sys
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'data/derived/meti_2021_vat_internal_hours_distribution.csv'
BOUNDS=ROOT/'data/derived/meti_2021_vat_internal_hours_bounds.csv'
CAT=ROOT/'data/source_catalog.csv'

def read(path):
    with path.open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))

d=read(DIST); b={r['bound_id']:r for r in read(BOUNDS)}
cat={r['source_id']:r for r in read(CAT)}
assert len(d)==9
assert [r['published_percent'] for r in d]==['21.1','1.3','32.4','19.2','8.1','3.6','2.4','5.1','6.7']
assert all(r['sample_n']=='1514' for r in d)
assert sum(Decimal(r['published_percent']) for r in d)==Decimal('99.9')
assert d[-1]['upper_open_ended']=='YES' and d[-1]['upper_hours_supremum']==''
assert all(r['joint_feasible_count_vectors']=='28' for r in d)
assert all(r['selection_scope_status']=='RESULTS_SELECTOR_CONFLICTS_WITH_QUESTIONNAIRE_AND_COUNTS' for r in d)

# Independently reconstruct integer counts compatible with one-decimal published shares.
def options(pct,n=1514):
    p=Decimal(pct); lo=p-Decimal('0.05'); hi=p+Decimal('0.05')
    return [k for k in range(n+1) if lo <= Decimal(100)*Decimal(k)/Decimal(n) < hi]
opts=[options(r['published_percent']) for r in d]
feasible=[c for c in itertools.product(*opts) if sum(c)==1514]
assert len(feasible)==28
assert [min(x) for x in opts]==[319,19,490,290,122,54,36,77,101]
assert [max(x) for x in opts]==[320,20,491,291,123,55,37,77,102]

lower=[Decimal(x) for x in ['0','0','1','10','20','30','40','50','100']]
def mean(c,v): return sum(Decimal(n)*x for n,x in zip(c,v))/Decimal(1514)
lb=min(mean(c,lower) for c in feasible)
assert abs(lb-Decimal(b['no_top_code_cap']['mean_hours_lower_bound'])) < Decimal('1e-12')
assert abs(lb-Decimal('15.126155878468')) < Decimal('1e-12')
assert b['no_top_code_cap']['finite_upper_bound']=='NO'
assert b['no_top_code_cap']['mean_hours_upper_supremum']==''

expected={100:'24.03500660502',150:'27.4035667107',250:'34.140686922061',500:'50.983487450462',1000:'84.669088507266'}
for cap,s in expected.items():
    vals=[Decimal(x) for x in ['0','1','10','20','30','40','50','100',str(cap)]]
    ub=max(mean(c,vals) for c in feasible)
    row=b[f'top_code_cap_{cap}h']
    assert abs(ub-Decimal(row['mean_hours_upper_supremum'])) < Decimal('1e-12')
    assert row['mean_hours_upper_supremum']==s
    assert row['finite_upper_bound']=='STRESS_CAP_ASSUMPTION'

# The printed p.66 selector cannot literally define the n=1,514 subset:
# 17.0% of the p.65 n=3,965 base permits only 673..676 integer observations.
yes=[k for k in range(3966) if Decimal('16.95') <= Decimal(100)*Decimal(k)/Decimal(3965) < Decimal('17.05')]
assert min(yes)==673 and max(yes)==676
assert 1514 > max(yes)

sid='METI-2021-SME-TAX-SURVEY'
assert cat[sid]['sha256']=='e6a5767910f2c1e024ec0b281e6f300949e735cdc6c9b052e164b6890948e563'
assert cat[sid]['bytes']=='8447353'
assert (ROOT/cat[sid]['raw_file']).exists()

subprocess.run([sys.executable,str(ROOT/'scripts/extract_meti_vat_internal_hours.py'),'--check'],cwd=ROOT,check=True)
print('METI VAT internal-hours tests: OK (9 bins; 28 feasible rounded-count vectors; conditional lower bound 15.126155878468 h/respondent for reported period; uncapped upper bound open)')
