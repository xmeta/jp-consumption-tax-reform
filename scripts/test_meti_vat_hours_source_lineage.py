#!/usr/bin/env python3

if not __debug__:
    raise RuntimeError('optimized Python is not supported for executable tests; assertions must remain active')
from pathlib import Path
import csv, hashlib, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/derived/meti_vat_internal_hours_source_lineage.csv'
CAT=ROOT/'data/source_catalog.csv'

def read(p):
    with p.open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
rows=read(OUT); assert len(rows)==3
by={r['survey_year']:r for r in rows}
assert set(by)=={'2019','2020','2021'}

r=by['2019']
assert (r['target_n'],r['response_n'],r['vat_hours_question'])==('5000','1113','Q6-1')
assert r['period_definition_status']=='EXPLICIT_TARGET_FISCAL_YEAR'
assert r['process_granularity']=='THREE_PROCESS_COLUMNS'
assert r['published_numeric_vat_hours']=='NO'
assert r['public_microdata_attachment']=='NO_LISTED_ATTACHMENT'
assert r['model_use']=='PERIOD_DESIGN_EVIDENCE_NOT_NUMERIC_CALIBRATION'

r=by['2020']
assert (r['target_n'],r['response_n'],r['vat_hours_question'])==('18000','3255','Q11-3')
assert r['respondent_selector']=='Q11-1_NO'
assert r['period_definition_status']=='QUESTION_NOT_EXPLICIT_RIETI_ANALYSIS_SCOPES_2019_FY'
assert r['process_granularity']=='VAT_TAX_TYPE_TOTAL'
assert r['published_numeric_vat_hours']=='NO'
assert r['public_microdata_attachment']=='NO_LISTED_ATTACHMENT'
assert r['model_use']=='LATENT_MICRODATA_EVIDENCE_NOT_PUBLIC_VAT_CALIBRATION'

r=by['2021']
assert (r['target_n'],r['response_n'],r['vat_hours_question'])==('20000','4410','Q8-3')
assert r['period_definition_status']=='TAX_ITEM_PERIOD_NOT_EXPLICIT'
assert 'CONFLICT' in r['respondent_selector']
assert r['published_numeric_vat_hours']=='YES'
assert r['published_vat_hours_item_n']=='1514'
assert r['public_microdata_attachment']=='NO_LISTED_ATTACHMENT'
assert r['numeric_lower_bound_hours']=='15.126155878468'
assert r['model_use']=='PUBLIC_NUMERIC_HOURS_BOUND_PERIOD_UNRESOLVED'

# No historical row has all three ingredients needed for a clean annual public VAT-hours estimate.
complete=[r for r in rows if r['period_definition_status']=='EXPLICIT_TARGET_FISCAL_YEAR' and r['published_numeric_vat_hours']=='YES' and 'CONFLICT' not in r['respondent_selector']]
assert complete==[]

cat={r['source_id']:r for r in read(CAT)}
hashes={
 'METI-2019-SME-TAX-REPORT-ARCHIVED':'148db29d866f77bb50c71eb23e229d64b1605fccf737ce1e7c39b072d85b1cd0',
 'METI-2020-SME-TAX-REPORT-ARCHIVED':'66c0af8b84c6b35a2396da67bb1add2d30c5eea4cba51f1bfad7f5cf62166763',
 'METI-2019-REPORT-LISTING-20210213-ARCHIVED':'413ebf3d9f9b431e5ddfbcf902cc2a526689a0d0667b40389bfaf0d85af0568d',
 'METI-2020-REPORT-LISTING-20211202-ARCHIVED':'9cb8d5dc819522da8a9eac75fa84f61037d8edba0e4d12257bfbb08981c2392e',
 'METI-2021-REPORT-LISTING-20220718-ARCHIVED':'ae840c57ce054e48209b2b721a19d533d36d36f5c8f79efa3df79e54a59a7c1e',
}
for sid,h in hashes.items():
    assert cat[sid]['sha256']==h,(sid,cat[sid]['sha256'])
    assert (ROOT/cat[sid]['raw_file']).exists()

subprocess.run([sys.executable,str(ROOT/'scripts/build_meti_vat_hours_source_lineage.py'),'--check'],cwd=ROOT,check=True)
print('METI VAT-hours source-lineage tests: OK (2019-2021; no clean public annual numeric VAT-hours row)')
