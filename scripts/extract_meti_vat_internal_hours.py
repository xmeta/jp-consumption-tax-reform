#!/usr/bin/env python3
"""Extract METI 2021 VAT-specific internal tax-procedure hours and partial bounds."""
from pathlib import Path
import argparse, csv, io, itertools, re
from decimal import Decimal
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT/'data/source_catalog.csv'
DIST=ROOT/'data/derived/meti_2021_vat_internal_hours_distribution.csv'
BOUNDS=ROOT/'data/derived/meti_2021_vat_internal_hours_bounds.csv'
SOURCE_ID='METI-2021-SME-TAX-SURVEY'

# (id, exact PDF label, lower endpoint, upper supremum, open-ended)
BINS=[
 ('h0','０時間',Decimal('0'),Decimal('0'),False),
 ('lt1','１時間未満',Decimal('0'),Decimal('1'),False),
 ('ge1_lt10','１時間以上～10時間未満',Decimal('1'),Decimal('10'),False),
 ('ge10_lt20','10時間以上～20時間未満',Decimal('10'),Decimal('20'),False),
 ('ge20_lt30','20時間以上～30時間未満',Decimal('20'),Decimal('30'),False),
 ('ge30_lt40','30時間以上～40時間未満',Decimal('30'),Decimal('40'),False),
 ('ge40_lt50','40時間以上～50時間未満',Decimal('40'),Decimal('50'),False),
 ('ge50_lt100','50時間以上～100時間未満',Decimal('50'),Decimal('100'),False),
 ('ge100','100時間以上',Decimal('100'),None,True),
]
CAPS=[100,150,250,500,1000]

def read_csv(path):
    with path.open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))

def render(rows):
    b=io.StringIO(); w=csv.DictWriter(b,fieldnames=list(rows[0]),lineterminator='\n')
    w.writeheader(); w.writerows(rows); return b.getvalue()

def norm(s): return re.sub(r'\s+','',s or '')

def fmt(x):
    if x is None: return ''
    s=f'{float(x):.12f}'.rstrip('0').rstrip('.')
    return s or '0'

def pct_for_label(text,label):
    n=norm(text)
    m=re.search(re.escape(label)+r'([0-9]+(?:\.[0-9]+)?)%',n)
    if not m: raise RuntimeError(f'missing METI VAT bin {label!r}')
    return Decimal(m.group(1))

def compatible_counts(sample_n,pct):
    lo=pct-Decimal('0.05'); hi=pct+Decimal('0.05')
    out=[]
    for k in range(sample_n+1):
        actual=Decimal(100)*Decimal(k)/Decimal(sample_n)
        if lo <= actual < hi: out.append(k)
    if not out: raise RuntimeError(f'no count compatible with n={sample_n}, pct={pct}')
    return out

def build():
    cat={r['source_id']:r for r in read_csv(CAT)}
    if SOURCE_ID not in cat: raise RuntimeError(f'missing catalog source {SOURCE_ID}')
    raw=ROOT/cat[SOURCE_ID]['raw_file']
    reader=PdfReader(raw)
    if len(reader.pages)!=117: raise RuntimeError(f'unexpected METI PDF pages: {len(reader.pages)}')
    p65=reader.pages[64].extract_text() or ''
    p66=reader.pages[65].extract_text() or ''
    p67=reader.pages[66].extract_text() or ''
    p70=reader.pages[69].extract_text() or ''
    for token in ['(ｎ＝3,965)','はい','17.0%','いいえ','83.0%']:
        if norm(token) not in norm(p65): raise RuntimeError(f'METI p65 missing {token!r}')
    for token in ['回答対象：（１）で「はい」','税務手続き関連']:
        if norm(token) not in norm(p66): raise RuntimeError(f'METI p66 missing {token!r}')
    for token in ['・消費税','(ｎ＝1,514)','32.4%','21.1%','19.2%','100時間以上','6.7%']:
        if norm(token) not in norm(p67): raise RuntimeError(f'METI p67 missing {token!r}')
    for token in ['外部委託費用（年間）','(ｎ＝3,755)','34.8%']:
        if norm(token) not in norm(p70): raise RuntimeError(f'METI p70 missing {token!r}')

    sample_n=1514
    marker='(ｎ＝1,514)'
    vat_block=p67[p67.index(marker)+len(marker):]
    pcts=[pct_for_label(vat_block,label) for _,label,_,_,_ in BINS]
    options=[compatible_counts(sample_n,p) for p in pcts]
    feasible=[c for c in itertools.product(*options) if sum(c)==sample_n]
    if not feasible: raise RuntimeError('no joint integer count vector matches rounded shares')

    lower=[b[2] for b in BINS]
    def mean(counts,values):
        return sum(Decimal(c)*v for c,v in zip(counts,values))/Decimal(sample_n)
    lower_bound=min(mean(c,lower) for c in feasible)

    yes_options=compatible_counts(3965,Decimal('17.0'))
    selection_consistent=sample_n <= max(yes_options)
    if selection_consistent:
        raise RuntimeError('expected METI p66 selection-label/count inconsistency disappeared')
    selection_status='SOURCE_REPORTED_SELECTION_LABEL_INCONSISTENT_WITH_COUNTS'

    dist=[]
    for (bid,label,lo,hi,open_end),pct,opts in zip(BINS,pcts,options):
        dist.append({
          'bin_id':bid,'published_label':label,'lower_hours':fmt(lo),
          'upper_hours_supremum':fmt(hi),'upper_open_ended':'YES' if open_end else 'NO',
          'published_percent':fmt(pct),'sample_n':sample_n,
          'rounded_percent_lower_inclusive':fmt(pct-Decimal('0.05')),
          'rounded_percent_upper_exclusive':fmt(pct+Decimal('0.05')),
          'compatible_count_min':min(opts),'compatible_count_max':max(opts),
          'joint_feasible_count_vectors':len(feasible),'source_id':SOURCE_ID,
          'source_locator':'PDF p.67 / printed p.67','selection_scope_status':selection_status,
        })

    bounds=[{
      'bound_id':'no_top_code_cap','top_code_cap_hours':'',
      'mean_hours_lower_bound':fmt(lower_bound),'mean_hours_upper_supremum':'',
      'finite_upper_bound':'NO','joint_feasible_count_vectors':len(feasible),
      'sample_n':sample_n,'source_id':SOURCE_ID,
      'identification_status':'CONDITIONAL_RESPONDENT_SUBSET_LOWER_BOUND_ONLY',
      'note':'100+ hours is top-coded, so no finite upper bound follows without an added cap; bound is not a national-firm mean.',
    }]
    for cap in CAPS:
        upper=[b[3] if not b[4] else Decimal(cap) for b in BINS]
        upper_sup=max(mean(c,upper) for c in feasible)
        bounds.append({
          'bound_id':f'top_code_cap_{cap}h','top_code_cap_hours':cap,
          'mean_hours_lower_bound':fmt(lower_bound),'mean_hours_upper_supremum':fmt(upper_sup),
          'finite_upper_bound':'STRESS_CAP_ASSUMPTION','joint_feasible_count_vectors':len(feasible),
          'sample_n':sample_n,'source_id':SOURCE_ID,
          'identification_status':'CONDITIONAL_RESPONDENT_SUBSET_CAP_SENSITIVITY',
          'note':'Upper endpoint uses interval suprema plus an assumed cap for the 100+ bin; not an empirical upper bound.',
        })
    return dist,bounds

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); args=ap.parse_args()
    dist,bounds=build(); outs=[(DIST,render(dist)),(BOUNDS,render(bounds))]
    if args.check:
        stale=[str(p.relative_to(ROOT)) for p,e in outs if not p.exists() or p.read_text(encoding='utf-8')!=e]
        if stale: raise SystemExit('stale generated artifacts: '+', '.join(stale))
        print(f'METI VAT internal hours: current ({len(dist)} bins; lower bound {bounds[0]["mean_hours_lower_bound"]} h; no finite uncapped upper bound)')
    else:
        for p,e in outs:
            p.parent.mkdir(parents=True,exist_ok=True); p.write_text(e,encoding='utf-8')
            print(f'wrote {p.relative_to(ROOT)}')
if __name__=='__main__': main()
