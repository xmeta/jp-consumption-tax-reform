#!/usr/bin/env python3
"""Build conservative VAT-system transition-cost lower bounds from official subsidy flows."""
from pathlib import Path
import argparse, csv, io, re, unicodedata
from decimal import Decimal, getcontext
from pypdf import PdfReader

getcontext().prec=40
ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT/'data/source_catalog.csv'
OUT=ROOT/'data/derived/vat_transition_system_subsidy_bounds.csv'
SOURCE_ID='SMRJ-FY2019-LIGHT-RATE-SUBSIDY-PERFORMANCE'


def read_csv(path):
    with path.open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))

def render(rows):
    b=io.StringIO(); w=csv.DictWriter(b,fieldnames=list(rows[0]),lineterminator='\n')
    w.writeheader(); w.writerows(rows); return b.getvalue()

def compact(s):
    s=unicodedata.normalize('NFKC',s or '')
    return re.sub(r'[\s,，]+','',s)

def fmt(x):
    s=f'{x:.12f}'.rstrip('0').rstrip('.')
    return s or '0'

def build():
    cat={r['source_id']:r for r in read_csv(CAT)}
    if SOURCE_ID not in cat: raise RuntimeError(f'missing source {SOURCE_ID}')
    raw=ROOT/cat[SOURCE_ID]['raw_file']
    r=PdfReader(raw)
    if len(r.pages)!=221: raise RuntimeError(f'unexpected SMRJ PDF pages: {len(r.pages)}')
    # The program-performance block spans physical PDF pages 31-32.
    t=compact('\n'.join((r.pages[i-1].extract_text() or '') for i in [31,32]))
    required=[
      '消費税軽減税率制度の実施に伴い対応が必要',
      '複数税率対応レジの導入',
      '受発注システムの改修',
      '請求書管理システムの改修',
      '経費の一部を補助',
      '申請件数122825件','累計221337件',
      '交付件数94875件','累計174781件',
      '交付金額22914612620円','累計44659886587円',
    ]
    for tok in required:
        if compact(tok) not in t: raise RuntimeError(f'SMRJ pp31-32 missing {tok!r}')

    vals=[
      ('fy2019',122825,94875,22914612620,'FY2019 only'),
      ('cumulative_through_fy2019',221337,174781,44659886587,'program cumulative through FY2019'),
    ]
    rows=[]
    for scope,apps,grants,amount,label in vals:
        avg=Decimal(amount)/Decimal(grants)
        rows.append({
          'scope_id':scope,
          'scope_label':label,
          'application_count':apps,
          'grant_count':grants,
          'subsidy_amount_yen':amount,
          'average_subsidy_yen_per_grant_record':fmt(avg),
          'eligible_transition_expenditure_lower_bound_yen':amount,
          'eligible_transition_expenditure_lower_bound_yen_per_grant_record':fmt(avg),
          'cost_duration_class':'TRANSITION_IMPLEMENTATION_COST',
          'covered_activity':'multi-rate registers; ordering-system modifications; invoice-management-system modifications; related eligible implementation expense',
          'source_id':SOURCE_ID,
          'source_locator':'PDF pp.31-32',
          'identification_status':'OBSERVED_SUBSIDY_FLOW_IMPLIES_ELIGIBLE_EXPENDITURE_LOWER_BOUND_FOR_GRANT_RECORDS',
          'persistent_annual_cost_identified':'NO',
          'population_representative':'NO',
          'model_use':'TRANSITION_COST_CONTEXT_ONLY_NOT_PERSISTENT_C_VAT',
          'note':'SMRJ states that the subsidy covers part of eligible expenses. Therefore eligible expenditure among grant records is at least the subsidy flow. This is not total private cost, not a unique-firm mean, not population representative, and not an annual recurring VAT compliance cost.'
        })
    return rows

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); args=ap.parse_args()
    text=render(build())
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding='utf-8')!=text:
            raise SystemExit(f'stale generated artifact: {OUT.relative_to(ROOT)}')
        print('VAT transition subsidy bounds: current (FY2019 + cumulative; subsidy-flow lower bounds only, not persistent c_VAT)')
    else:
        OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(text,encoding='utf-8')
        print(f'wrote {OUT.relative_to(ROOT)}: 2 transition-cost rows')
if __name__=='__main__': main()
