#!/usr/bin/env python3
"""Extract 10m-JPY VAT-threshold nationalized and pre/post bunching estimates.

Ichikawa, Arudchelvan and Onji (2019), TDB-CAREE DP J-2019-01.
The output preserves the paper's mechanism uncertainty: lost-sales figures are
scenario estimates, not empirical bounds on GDP or macro allocative efficiency.
"""
from pathlib import Path
import argparse, csv, io, re, unicodedata
from decimal import Decimal, getcontext
from pypdf import PdfReader

getcontext().prec = 40
ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT/'data/source_catalog.csv'
OUT_N=ROOT/'data/derived/ichikawa_2019_vat_10m_threshold_nationalized_estimates.csv'
OUT_P=ROOT/'data/derived/ichikawa_2019_vat_10m_threshold_prepost_bunching.csv'
SOURCE_ID='ICHIKAWA-ARUDCHELVAN-ONJI-2019-VAT-10M-BUNCHING'
EXPECTED_SHA='93f68057104b6a4bb693c5fafbea8386ad830f6f3714291968d9937784517b28'


def read_csv(path):
    with path.open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))

def render(rows):
    b=io.StringIO(); w=csv.DictWriter(b,fieldnames=list(rows[0]),lineterminator='\n')
    w.writeheader(); w.writerows(rows); return b.getvalue()

def norm(s):
    s=unicodedata.normalize('NFKC',s or '')
    return re.sub(r'\s+','',s).replace('−','-').replace('–','-')

def require(text,tokens,label):
    n=norm(text)
    for tok in tokens:
        if norm(tok) not in n: raise RuntimeError(f'{label}: missing token {tok!r}')

def fmt(x):
    s=f'{x:.12f}'.rstrip('0').rstrip('.')
    return s or '0'

def metric(metric_id,value,unit,locator,status,model_use,note):
    return {
      'metric_id':metric_id,'value':value,'unit':unit,'source_id':SOURCE_ID,
      'source_locator':locator,'identification_status':status,'model_use':model_use,'note':note
    }

def build():
    cat={r['source_id']:r for r in read_csv(CAT)}
    if SOURCE_ID not in cat: raise RuntimeError(f'missing source {SOURCE_ID}')
    src=cat[SOURCE_ID]
    if src['sha256']!=EXPECTED_SHA: raise RuntimeError(f'{SOURCE_ID}: unexpected sha256 {src["sha256"]}')
    r=PdfReader(ROOT/src['raw_file'])
    if len(r.pages)!=33: raise RuntimeError(f'{SOURCE_ID}: unexpected page count {len(r.pages)}')

    p14=r.pages[13].extract_text() or ''
    p15=r.pages[14].extract_text() or ''
    p16=r.pages[15].extract_text() or ''
    p17=r.pages[16].extract_text() or ''
    p18=r.pages[17].extract_text() or ''
    p23=r.pages[22].extract_text() or ''
    p24=r.pages[23].extract_text() or ''

    require(p14,[
      '売上高 800 万円以上 1,000 万円未満の企業数を 308,435 社',
      '付加価値率を 41.3%',
      '超過企業数は補論 7.2',
      '1 社あたり 150 万円',
    ],'Ichikawa2019 p14/Table4 setup')
    require(p15,[
      '超過集積企業数 56,651 社','益税額 168.5 億円','849.8 億円','31.4 億円',
      'ミッシングマス','過大評価の可能性',
    ],'Ichikawa2019 p15/Table4')
    require(p16,['800 万円のビンは 1,100 万円のビンより','およそ 30%低く','統計的に強い差異ではない'],'Ichikawa2019 p16 growth evidence')
    require(p17,['2014 年に税率が 3%引き上げ','どの集積領域においても','帰無仮説Δ','事務負担回避仮説'],'Ichikawa2019 p17 quasi experiment')
    require(p18,[
      '2004 -2013','1 0.721 0.060','1.5 0.871 0.091','2 0.900 0.121','2.5 1.104 0.162',
      '2014 -201 8','1 0.684 0.064','1.5 0.712 0.092','2 0.933 0.131','2.5 1.085 0.172',
      'ミッシングマスの小ささ','実質的反応と整合的でない',
    ],'Ichikawa2019 p18/Table5')
    require(p23,['ミッシングマスの少なさ','実質的反応が限定的','租税回避の直接的根拠は検出されていない'],'Ichikawa2019 p23 mechanism')
    require(p24,[
      'およそ 5 万 7 千社','毎年 170 億円規模','統計的に強い結果ではない',
      '租税回避を示す直接的エビデンスは検出されなかった','850 億円規模','30 億円規模',
      '集積メカニズムの峻別',
    ],'Ichikawa2019 p24 conclusion')

    national=[
      metric('vat_exemption_threshold_yen','10000000','yen','PDF pp.4,8','OBSERVED_INSTITUTION_IN_STUDY_PERIOD','INSTITUTIONAL_CONTEXT','Study analyzes the 10m-JPY exemption threshold introduced by the 2004 reform.'),
      metric('national_bunching_region_firm_count','308435','firms','PDF p.14 / Table 4 setup','NATIONALIZED_EXTERNAL_STATISTICS_INPUT','DENOMINATOR_FOR_STUDY_NATIONALIZATION_ONLY','Estimated from the 2016 Economic Census for firms in the 8m to below-10m JPY sales region; paper notes TDB small-firm coverage can bias bunching downward.'),
      metric('national_bunching_region_value_added_share','0.413','ratio','PDF p.14 / Table 4 setup','NATIONALIZED_EXTERNAL_STATISTICS_INPUT','TAX_WINDFALL_CALCULATION_ONLY','Value-added share in the nationalized bunching region, used by the paper for its tax-windfall calculation.'),
      metric('vat_rate_table4','0.08','ratio','PDF p.14 / Table 4 setup','SCENARIO_INPUT','TAX_WINDFALL_CALCULATION_ONLY','Paper uses an 8% VAT rate for the Table 4 nationalized calculation.'),
      metric('estimated_excess_buncher_firm_count','56651','firms','PDF p.15 Table 4','MODEL_AND_EXTERNAL_STATISTICS_NATIONALIZED_ESTIMATE','BEHAVIORAL_DISTORTION_SCALE_NOT_OUTPUT_LOSS','Nationalized excess-buncher estimate. It measures distorted firm-location in the sales distribution, not the number of firms proven to reduce real output.'),
      metric('estimated_tax_windfall_yen_per_year','16850000000','yen_per_year','PDF p.15 Table 4','MODEL_AND_EXTERNAL_STATISTICS_NATIONALIZED_ESTIMATE','TAX_REVENUE_CONTEXT_NOT_WELFARE_LOSS','Estimated tax windfall (lost tax collection), not a real-resource or GDP loss.'),
      metric('lost_sales_all_excess_real_adjustment_scenario_yen','84980000000','yen','PDF pp.14-15 Table 4 and footnote 12','MECHANISM_SENSITIVE_SCENARIO_ESTIMATE','DO_NOT_TREAT_AS_EMPIRICAL_BOUND_OR_GDP_LOSS','Assumes all estimated excess bunchers came from the 10m-11m transition region and each lost 1.5m JPY of real sales. Paper explicitly warns this can overstate lost sales if some bunching is tax avoidance.'),
      metric('lost_sales_missing_mass_scenario_yen','3140000000','yen','PDF p.15 Table 4 and footnote 13','MECHANISM_SENSITIVE_SCENARIO_ESTIMATE','DO_NOT_TREAT_AS_EMPIRICAL_BOUND_OR_GDP_LOSS','Uses observed missing mass and assumes 1.5m JPY lost sales per corresponding firm. This remains assumption-dependent and is not a formal lower bound on welfare/GDP loss.'),
    ]

    pre=[
      ('1','0.721','0.060','0.604','0.839'),('1.5','0.871','0.091','0.694','1.049'),
      ('2','0.900','0.121','0.663','1.138'),('2.5','1.104','0.162','0.786','1.422')]
    post=[
      ('1','0.684','0.064','0.559','0.809'),('1.5','0.712','0.092','0.531','0.892'),
      ('2','0.933','0.131','0.676','1.190'),('2.5','1.085','0.172','0.748','1.422')]
    rows=[]
    for (w,b0,se0,l0,h0),(w2,b1,se1,l1,h1) in zip(pre,post):
        if not (w == w2):
            raise RuntimeError('scientific runtime invariant failed: scripts/build_ichikawa_2019_vat_10m_threshold_bridge.py:107')
        overlap=max(Decimal(l0),Decimal(l1)) <= min(Decimal(h0),Decimal(h1))
        diff=Decimal(b1)-Decimal(b0)
        rows.append({
          'bunching_window_below_threshold_million_yen':w,
          'pre_period':'2004-2013','pre_relative_excess_bunching':b0,'pre_se':se0,'pre_ci95_low':l0,'pre_ci95_high':h0,
          'post_period':'2014-2018','post_relative_excess_bunching':b1,'post_se':se1,'post_ci95_low':l1,'post_ci95_high':h1,
          'post_minus_pre':fmt(diff),'paper_ci_overlap_rule_no_detectable_change':'YES' if overlap else 'NO',
          'source_id':SOURCE_ID,'source_locator':'PDF pp.17-18 Table 5',
          'identification_status':'QUASI_EXPERIMENT_DESCRIPTIVE_BUNCHING_COMPARISON',
          'model_use':'COMPLIANCE_MOTIVE_EVIDENCE_NOT_TAX_RATE_ELASTICITY_OR_MACRO_A_ALLOC',
          'note':'The paper treats overlapping 95% confidence intervals for the same bunching window as failure to reject no change. A 3-percentage-point VAT-rate increase did not produce a detectable bunching increase under that rule; this supports, but does not prove, the compliance-burden motive.'
        })
    if not all(r['paper_ci_overlap_rule_no_detectable_change']=='YES' for r in rows):
        raise RuntimeError('unexpected non-overlap in Table 5 pre/post comparison')
    return national,rows


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); args=ap.parse_args()
    n,p=build(); outs=[(OUT_N,render(n)),(OUT_P,render(p))]
    if args.check:
        stale=[str(path.relative_to(ROOT)) for path,text in outs if not path.exists() or path.read_text(encoding='utf-8')!=text]
        if stale: raise SystemExit('stale generated artifacts: '+', '.join(stale))
        print('Ichikawa 2019 VAT 10m-threshold bridge: current (nationalized scale + mechanism-sensitive lost-sales scenarios + pre/post bunching)')
    else:
        for path,text in outs:
            path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text,encoding='utf-8')
        print(f'wrote {OUT_N.relative_to(ROOT)}: {len(n)} rows')
        print(f'wrote {OUT_P.relative_to(ROOT)}: {len(p)} rows')
if __name__=='__main__': main()
