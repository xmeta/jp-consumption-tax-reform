#!/usr/bin/env python3
from pathlib import Path
from decimal import Decimal
import csv, hashlib, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
W=ROOT/'data/derived/bsws_2019_industry_hourly_wage_bridge.csv'
C=ROOT/'data/derived/meti_vat_internal_labor_cost_wage_sensitivity.csv'
SNAP=ROOT/'data/raw/estat/bsws_2019_industry_major_wage_db_snapshot.json'
XLS=ROOT/'data/raw/estat/bsws_2019_industry_wage_table1.xls'

def read(p):
    with p.open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

w=read(W); c=read(C)
assert len(w)==17 and len(c)==34
assert sha(SNAP)=='510b65c6a47d54d4074594fe376458920e5a74edc105acc7aa14aea49993a8a1'
assert sha(XLS)=='9583495007287b89e163a3202c4d3f6e757dfcfc355076dcde0321e0276ac811'
assert all(r['rieti_exact_formula_status']=='NOT_IDENTIFIED_FROM_PAPER' for r in w)
assert all(r['identification_status']=='OFFICIAL_COMPONENTS_DERIVED_TRANSPARENT_WAGE_CANDIDATES' for r in w)

total=next(r for r in w if r['industry_code']=='01')
assert total['scheduled_actual_hours_month']=='160'
assert total['overtime_actual_hours_month']=='13'
assert total['regular_cash_earnings_thousand_yen_month']=='338'
assert total['scheduled_cash_earnings_thousand_yen_month']=='307.7'
assert Decimal(total['scheduled_hour_rate_yen'])==Decimal('1923.125')
assert Decimal(total['regular_cash_effective_hour_rate_yen'])==Decimal('1953.757225433526')

# Recompute both formulas independently from the checked-in official components.
for r in w:
    sh=Decimal(r['scheduled_actual_hours_month']); oh=Decimal(r['overtime_actual_hours_month'])
    reg=Decimal(r['regular_cash_earnings_thousand_yen_month']); sched=Decimal(r['scheduled_cash_earnings_thousand_yen_month'])
    assert abs(Decimal(r['scheduled_hour_rate_yen'])-(sched*1000/sh)) < Decimal('1e-10')
    assert abs(Decimal(r['regular_cash_effective_hour_rate_yen'])-(reg*1000/(sh+oh))) < Decimal('1e-10')

major=[r for r in w if r['industry_code']!='01']
assert min(major,key=lambda r:Decimal(r['scheduled_hour_rate_yen']))['industry_code']=='83'
assert max(major,key=lambda r:Decimal(r['scheduled_hour_rate_yen']))['industry_code']=='32'
assert min(major,key=lambda r:Decimal(r['regular_cash_effective_hour_rate_yen']))['industry_code']=='83'
assert max(major,key=lambda r:Decimal(r['regular_cash_effective_hour_rate_yen']))['industry_code']=='32'

for r in c:
    assert r['identification_status']=='MECHANICAL_WAGE_CONVERSION_SENSITIVITY_NOT_ANNUAL_NOT_POPULATION_ESTIMATE'
    assert r['model_calibration_permission']=='DO_NOT_USE_AS_NATIONAL_C_VAT'
    lhs=Decimal(r['mechanical_internal_labor_cost_lower_yen_per_respondent_reported_period'])
    rhs=Decimal(r['hourly_rate_yen'])*Decimal(r['meti_mean_hours_lower_bound'])
    assert abs(lhs-rhs) < Decimal('1e-8')

def row(code,formula): return next(r for r in c if r['industry_code']==code and r['wage_formula']==formula)
assert Decimal(row('01','scheduled_hour_rate')['mechanical_internal_labor_cost_lower_yen_per_respondent_reported_period'])==Decimal('29089.488523778772')
assert Decimal(row('01','regular_cash_effective_hour_rate')['mechanical_internal_labor_cost_lower_yen_per_respondent_reported_period'])==Decimal('29552.836340590659')
assert Decimal(row('83','scheduled_hour_rate')['mechanical_internal_labor_cost_lower_yen_per_respondent_reported_period'])==Decimal('22179.061696357215')
assert Decimal(row('32','regular_cash_effective_hour_rate')['mechanical_internal_labor_cost_lower_yen_per_respondent_reported_period'])==Decimal('43137.555653408743')

subprocess.run([sys.executable,str(ROOT/'scripts/build_bsws_2019_industry_hourly_wage_bridge.py'),'--check'],cwd=ROOT,check=True)
subprocess.run([sys.executable,str(ROOT/'scripts/build_meti_vat_internal_labor_cost_bridge.py'),'--check'],cwd=ROOT,check=True)
print('BSWS/VAT wage bridge tests: OK (17 industries x 2 transparent formulas; 34 mechanical cost scenarios; no national c_VAT calibration)')
