#!/usr/bin/env python3
"""Mechanically combine METI VAT-hours lower bound with BSWS wage candidates."""
from pathlib import Path
from decimal import Decimal, getcontext
import argparse, csv, io

getcontext().prec=40
ROOT=Path(__file__).resolve().parents[1]
HOURS=ROOT/'data/derived/meti_2021_vat_internal_hours_bounds.csv'
WAGES=ROOT/'data/derived/bsws_2019_industry_hourly_wage_bridge.csv'
OUT=ROOT/'data/derived/meti_vat_internal_labor_cost_wage_sensitivity.csv'

def read(path):
    with path.open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))

def fmt(x):
    s=f'{x.quantize(Decimal("0.000000000001")):f}'.rstrip('0').rstrip('.')
    return s or '0'

def render(rows):
    b=io.StringIO(); w=csv.DictWriter(b,fieldnames=list(rows[0]),lineterminator='\n')
    w.writeheader(); w.writerows(rows); return b.getvalue()

def build():
    hb={r['bound_id']:r for r in read(HOURS)}['no_top_code_cap']
    h=Decimal(hb['mean_hours_lower_bound'])
    rows=[]
    for w in read(WAGES):
        for formula,col in [('scheduled_hour_rate','scheduled_hour_rate_yen'),('regular_cash_effective_hour_rate','regular_cash_effective_hour_rate_yen')]:
            rate=Decimal(w[col]); cost=h*rate
            rows.append({
              'industry_code':w['industry_code'],'industry_name':w['industry_name'],
              'wage_formula':formula,'hourly_rate_yen':fmt(rate),
              'meti_mean_hours_lower_bound':fmt(h),
              'mechanical_internal_labor_cost_lower_yen_per_respondent_reported_period':fmt(cost),
              'hours_source_id':'METI-2021-SME-TAX-SURVEY','wage_source_id':w['source_id'],
              'identification_status':'MECHANICAL_WAGE_CONVERSION_SENSITIVITY_NOT_ANNUAL_NOT_POPULATION_ESTIMATE',
              'model_calibration_permission':'DO_NOT_USE_AS_NATIONAL_C_VAT',
              'note':'Multiplies the conditional METI Q8-3 respondent-subset hours lower bound by a 2019 BSWS industry wage candidate. Q8-3 period, respondent industry mix, population selection, temporal alignment, and VAT-specific external outsourcing remain unresolved.'
            })
    if len(rows)!=34: raise RuntimeError(f'expected 34 scenarios, got {len(rows)}')
    return rows

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); args=ap.parse_args()
    text=render(build())
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding='utf-8')!=text: raise SystemExit(f'stale generated artifact: {OUT.relative_to(ROOT)}')
        print('METI VAT internal labor-cost wage sensitivity: current (34 scenarios; not annual or population estimate)')
    else:
        OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(text,encoding='utf-8')
        print(f'wrote {OUT.relative_to(ROOT)}: 34 rows')
if __name__=='__main__': main()
