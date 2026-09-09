#!/usr/bin/env python3
"""Build transparent 2019 BSWS industry hourly-wage conversion candidates."""
from pathlib import Path
from decimal import Decimal, getcontext
import argparse, csv, html, io, json, re

getcontext().prec = 40
ROOT=Path(__file__).resolve().parents[1]
SNAP=ROOT/'data/raw/estat/bsws_2019_industry_major_wage_db_snapshot.json'
OUT=ROOT/'data/derived/bsws_2019_industry_hourly_wage_bridge.csv'
SOURCE_ID='ESTAT-BSWS-2019-INDUSTRY-WAGE-DB-SNAPSHOT'
EXPECTED_HEADINGS=['所定内実労働時間数','超過実労働時間数','きまって支給する現金給与額','所定内給与額']

def fmt(x, places=12):
    q=Decimal(1).scaleb(-places)
    s=f'{x.quantize(q):f}'.rstrip('0').rstrip('.')
    return s or '0'

def render(rows):
    b=io.StringIO(); w=csv.DictWriter(b,fieldnames=list(rows[0]),lineterminator='\n')
    w.writeheader(); w.writerows(rows); return b.getvalue()

def extract_values(raw_response):
    obj=json.loads(raw_response); table=obj['table']
    for h in EXPECTED_HEADINGS:
        if h not in table: raise RuntimeError(f'missing BSWS heading {h!r}')
    vals=[html.unescape(x.strip()).replace(',','') for x in re.findall(r'<td class="stat-dbview-value">\s*([^<\n]+)',table)]
    if len(vals)!=4: raise RuntimeError(f'expected 4 BSWS values, got {len(vals)}: {vals}')
    return [Decimal(x) for x in vals]

def build():
    obj=json.loads(SNAP.read_text(encoding='utf-8'))
    if obj.get('snapshot_schema')!='ESTAT_DBVIEW_RAW_RESPONSE_BUNDLE_V1': raise RuntimeError('unexpected snapshot schema')
    if obj.get('sid')!='0003084009' or obj.get('stat_inf_id')!='000031919751': raise RuntimeError('unexpected e-Stat identifiers')
    if obj.get('survey_year')!=2019: raise RuntimeError('unexpected survey year')
    rows=[]
    for item in obj['industry_responses']:
        sched_h, overtime_h, regular_k, scheduled_k=extract_values(item['raw_response'])
        if sched_h<=0 or sched_h+overtime_h<=0: raise RuntimeError('nonpositive hours')
        scheduled_rate=scheduled_k*Decimal(1000)/sched_h
        effective_rate=regular_k*Decimal(1000)/(sched_h+overtime_h)
        rows.append({
          'industry_code':item['industry_code'],'industry_name':item['industry_name'],
          'scheduled_actual_hours_month':fmt(sched_h,3),'overtime_actual_hours_month':fmt(overtime_h,3),
          'regular_cash_earnings_thousand_yen_month':fmt(regular_k,3),
          'scheduled_cash_earnings_thousand_yen_month':fmt(scheduled_k,3),
          'scheduled_hour_rate_yen':fmt(scheduled_rate),
          'regular_cash_effective_hour_rate_yen':fmt(effective_rate),
          'survey_year':'2019','population_scope':'general_workers_private_establishments_enterprise_size_10plus_total_age_education_sex_total',
          'source_id':SOURCE_ID,'stat_inf_id':'000031919751','db_sid':'0003084009',
          'identification_status':'OFFICIAL_COMPONENTS_DERIVED_TRANSPARENT_WAGE_CANDIDATES',
          'rieti_exact_formula_status':'NOT_IDENTIFIED_FROM_PAPER',
          'note':'Two transparent formulas from official BSWS components; RIETI 21-P-018 states it used industry hourly wages from BSWS but does not identify its exact formula/table in the paper.'
        })
    if len(rows)!=17: raise RuntimeError(f'expected 17 industry rows, got {len(rows)}')
    return rows

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); args=ap.parse_args()
    text=render(build())
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding='utf-8')!=text: raise SystemExit(f'stale generated artifact: {OUT.relative_to(ROOT)}')
        print('BSWS 2019 industry hourly-wage bridge: current (17 industry rows; 2 transparent formulas; RIETI exact formula not identified)')
    else:
        OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(text,encoding='utf-8')
        print(f'wrote {OUT.relative_to(ROOT)}: 17 rows')
if __name__=='__main__': main()
