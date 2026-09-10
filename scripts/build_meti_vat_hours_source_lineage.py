#!/usr/bin/env python3
"""Audit 2019-2021 METI VAT-internal-hours survey lineage and public-data gaps."""
from pathlib import Path
import argparse, csv, io, re
from pypdf import PdfReader
from extract_meti_vat_internal_hours import build as build_meti_2021_hours

ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT/'data/source_catalog.csv'
OUT=ROOT/'data/derived/meti_vat_internal_hours_source_lineage.csv'

S2019='METI-2019-SME-TAX-REPORT-ARCHIVED'
L2019='METI-2019-REPORT-LISTING-20210213-ARCHIVED'
S2020='METI-2020-SME-TAX-REPORT-ARCHIVED'
L2020='METI-2020-REPORT-LISTING-20211202-ARCHIVED'
S2021='METI-2021-SME-TAX-SURVEY'
L2021='METI-2021-REPORT-LISTING-20220718-ARCHIVED'
RIETI='RIETI-2021-QUANT-TAX-COMPLIANCE-COST'


def read_csv(path):
    with path.open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))

def render(rows):
    b=io.StringIO(); w=csv.DictWriter(b,fieldnames=list(rows[0]),lineterminator='\n')
    w.writeheader(); w.writerows(rows); return b.getvalue()

def norm(s): return re.sub(r'\s+','',s or '')

def require(text,tokens,label):
    n=norm(text)
    for tok in tokens:
        if norm(tok) not in n: raise RuntimeError(f'{label}: missing token {tok!r}')

def listing_no_attachment(reader,page_no,current_id,next_id,expected_url,label):
    t=reader.pages[page_no-1].extract_text() or ''
    n=norm(t)
    a=n.find(current_id); b=n.find(next_id,a+len(current_id))
    if a<0 or b<0: raise RuntimeError(f'{label}: listing row boundary not found')
    row=n[a:b]
    if norm(expected_url) not in row: raise RuntimeError(f'{label}: report URL missing')
    if current_id+'-1' in row or current_id+'-1.zip' in row:
        raise RuntimeError(f'{label}: data attachment unexpectedly listed')
    return True

def build():
    cat={r['source_id']:r for r in read_csv(CAT)}
    for sid in [S2019,L2019,S2020,L2020,S2021,L2021,RIETI]:
        if sid not in cat: raise RuntimeError(f'missing source catalog row: {sid}')
        if not (ROOT/cat[sid]['raw_file']).exists(): raise RuntimeError(f'missing raw source: {sid}')

    r19=PdfReader(ROOT/cat[S2019]['raw_file'])
    l19=PdfReader(ROOT/cat[L2019]['raw_file'])
    r20=PdfReader(ROOT/cat[S2020]['raw_file'])
    l20=PdfReader(ROOT/cat[L2020]['raw_file'])
    r21=PdfReader(ROOT/cat[S2021]['raw_file'])
    l21=PdfReader(ROOT/cat[L2021]['raw_file'])
    rr=PdfReader(ROOT/cat[RIETI]['raw_file'])
    expected_pages={S2019:210,L2019:19,S2020:168,L2020:21,S2021:117,L2021:10,RIETI:14}
    for sid,r in [(S2019,r19),(L2019,l19),(S2020,r20),(L2020,l20),(S2021,r21),(L2021,l21),(RIETI,rr)]:
        if len(r.pages)!=expected_pages[sid]: raise RuntimeError(f'{sid}: unexpected pages {len(r.pages)}')

    # 2019 corporate equipment survey: public design has an explicit fiscal-year scope.
    p19_over=r19.pages[3].extract_text() or ''
    p19_q6='\n'.join((r19.pages[i-1].extract_text() or '') for i in [153,154])
    p19_results='\n'.join((r19.pages[i-1].extract_text() or '') for i in range(6,31))
    require(p19_over,['調査期間：2019年7月～8月','対象エリア：全国','法人向け設備投資5,000件','法人向け設備投資1,113件（22.3％）'],'METI2019 overview')
    require(p19_q6,['Q6-1','平成30年4月1日から平成31年3月31日','(内)消費税','データ収集・システム入力・決算書の作成','申告書の作成','提出'],'METI2019 Q6')
    if '消費税' in p19_results: raise RuntimeError('METI2019 corporate-equipment published-results section unexpectedly contains consumption-tax results')
    listing_no_attachment(l19,9,'000249','000250','https://www.meti.go.jp/meti_lib/report/2019FY/000249.pdf','METI2019 listing')

    # 2020 corporate survey: Q11 collects VAT hours, but Q11-3 itself has no explicit period.
    p20_over=r20.pages[3].extract_text() or ''
    p20_q11='\n'.join((r20.pages[i-1].extract_text() or '') for i in [136,137])
    p20_corp_results='\n'.join((r20.pages[i-1].extract_text() or '') for i in range(6,53))
    require(p20_over,['調査期間：2020年8月','対象エリア：全国','法人企業18,000件','法人企業向け3,255件（18.1％）'],'METI2020 overview')
    require(p20_q11,['Q11-3','消費税','社内のおおよその延べ時間','Q11-1で「②いいえ」','外部委託費用（年間）','平成31年4月1日から令和2年3月31日'],'METI2020 Q11')
    # The explicit FY phrase occurs in Q11-4 outsourcing text, after Q11-3; do not transfer it silently to Q11-3.
    q11_3_start=norm(p20_q11).find('Q11-3')
    q11_4_start=norm(p20_q11).find('Q11-4')
    q11_3_block=norm(p20_q11)[q11_3_start:q11_4_start]
    if '平成31年4月1日から令和2年3月31日' in q11_3_block:
        raise RuntimeError('METI2020 Q11-3 unexpectedly has explicit FY period')
    if '税務手続き関連の事務負担' in p20_corp_results:
        raise RuntimeError('METI2020 corporate published-results section unexpectedly contains Q11 tax-burden results')
    listing_no_attachment(l20,2,'000409','000457','https://www.meti.go.jp/meti_lib/report/2020FY/000409.pdf','METI2020 listing')

    # RIETI links the 18,000 / 3,255 survey to FY2019 corporate behavior, but only publishes pooled all-tax estimates.
    pr4=rr.pages[3].extract_text() or ''
    pr5=rr.pages[4].extract_text() or ''
    require(pr4,['約18,000社','3,255社','2019年度の企業行動','賃金構造基本統計調査'],'RIETI method p4')
    require(pr5,['消費税','固定資産税','事業所税'],'RIETI tax scope p5')

    # 2021 gives public VAT-hour percentages and n, but the tax-item question period is not explicitly annual.
    p21_5=r21.pages[4].extract_text() or ''
    p21_65=r21.pages[64].extract_text() or ''
    p21_66=r21.pages[65].extract_text() or ''
    p21_67=r21.pages[66].extract_text() or ''
    require(p21_5,['調査対象数：20,000件','有効回答数：4,410件'],'METI2021 overview')
    require(p21_65,['(ｎ＝3,965)','はい','17.0%','いいえ','83.0%'],'METI2021 p65')
    require(p21_66,['回答対象：（１）で「はい」'],'METI2021 p66')
    require(p21_67,['・消費税','(ｎ＝1,514)','100時間以上','6.7%'],'METI2021 p67')
    listing_no_attachment(l21,3,'000139','000140','https://www.meti.go.jp/meti_lib/report/2021FY/000139.pdf','METI2021 listing')
    _, bounds=build_meti_2021_hours()
    lower={r['bound_id']:r for r in bounds}['no_top_code_cap']['mean_hours_lower_bound']

    rows=[
      {
        'survey_year':'2019','survey_family':'FY2019_METI_SME_SPECIAL_TAX_MEASURES','source_id':S2019,
        'target_n':'5000','response_n':'1113','vat_hours_question':'Q6-1','respondent_selector':'corporate_equipment_survey_respondents',
        'period_definition_status':'EXPLICIT_TARGET_FISCAL_YEAR','period_definition':'fiscal_year_ending_between_2018-04-01_and_2019-03-31',
        'vat_internal_hours_collected':'YES','process_granularity':'THREE_PROCESS_COLUMNS','published_numeric_vat_hours':'NO',
        'published_vat_hours_item_n':'','public_microdata_attachment':'NO_LISTED_ATTACHMENT','numeric_lower_bound_hours':'',
        'analytic_linkage':'SURVEY_DESIGN_ONLY_PUBLIC_NUMBERS_OMITTED','model_use':'PERIOD_DESIGN_EVIDENCE_NOT_NUMERIC_CALIBRATION',
        'note':'Q6-1 explicitly scopes answers to the target fiscal year and collects VAT internal hours by data/system/financial-statement work, return preparation, and submission; public corporate-equipment results omit VAT-hour values; archived METI listing row 000249 has no data attachment.'
      },
      {
        'survey_year':'2020','survey_family':'FY2020_METI_SME_SPECIAL_TAX_MEASURES','source_id':S2020,
        'target_n':'18000','response_n':'3255','vat_hours_question':'Q11-3','respondent_selector':'Q11-1_NO',
        'period_definition_status':'QUESTION_NOT_EXPLICIT_RIETI_ANALYSIS_SCOPES_2019_FY','period_definition':'RIETI_states_survey_answers_concern_FY2019_corporate_behavior',
        'vat_internal_hours_collected':'YES','process_granularity':'VAT_TAX_TYPE_TOTAL','published_numeric_vat_hours':'NO',
        'published_vat_hours_item_n':'','public_microdata_attachment':'NO_LISTED_ATTACHMENT','numeric_lower_bound_hours':'',
        'analytic_linkage':'RIETI_21P018_USES_SURVEY_MICRODATA_BUT_PUBLISHES_ALL_TAX_AGGREGATES','model_use':'LATENT_MICRODATA_EVIDENCE_NOT_PUBLIC_VAT_CALIBRATION',
        'note':'Q11-3 collects VAT-specific internal hours after financial statements for Q11-1=No respondents. Its own block does not state a period; Q11-4 separately states FY2019 for annual outsourcing. RIETI says survey answers concern FY2019 corporate behavior. METI public results omit corporate Q11 hours and listing row 000409 has no data attachment.'
      },
      {
        'survey_year':'2021','survey_family':'FY2021_METI_SME_TAX_SURVEY','source_id':S2021,
        'target_n':'20000','response_n':'4410','vat_hours_question':'Q8-3','respondent_selector':'QUESTIONNAIRE_Q8-1_NO_RESULTS_PAGE_SAYS_YES_AND_COUNTS_CONFLICT',
        'period_definition_status':'TAX_ITEM_PERIOD_NOT_EXPLICIT','period_definition':'reported_Q8-3_period_not_identified_as_annual',
        'vat_internal_hours_collected':'YES','process_granularity':'VAT_TAX_TYPE_TOTAL_DISTRIBUTION','published_numeric_vat_hours':'YES',
        'published_vat_hours_item_n':'1514','public_microdata_attachment':'NO_LISTED_ATTACHMENT','numeric_lower_bound_hours':lower,
        'analytic_linkage':'PUBLIC_ROUNDED_DISTRIBUTION_PARTIALLY_IDENTIFIES_RESPONDENT_SUBSET_LOWER_BOUND','model_use':'PUBLIC_NUMERIC_HOURS_BOUND_PERIOD_UNRESOLVED',
        'note':'Published VAT distribution n=1,514 yields a rounding-compatible mean lower bound, but Q8-3 does not explicitly identify an annual period; results-page selector conflicts with questionnaire routing and is also incompatible with the published Q8-1 yes count. Archived METI listing row 000139 has no data attachment.'
      }
    ]
    complete=[r for r in rows if r['period_definition_status']=='EXPLICIT_TARGET_FISCAL_YEAR' and r['published_numeric_vat_hours']=='YES' and 'CONFLICT' not in r['respondent_selector']]
    if complete:
        raise RuntimeError('unexpected historical survey row simultaneously identifies period, public VAT numbers, and unambiguous selection')
    return rows

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); args=ap.parse_args()
    text=render(build())
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding='utf-8')!=text: raise SystemExit(f'stale generated artifact: {OUT.relative_to(ROOT)}')
        print('METI VAT-hours source lineage: current (2019-2021; no public row jointly supplies explicit fiscal period + numeric VAT hours + unambiguous selection)')
    else:
        OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(text,encoding='utf-8')
        print(f'wrote {OUT.relative_to(ROOT)}: 3 survey-lineage rows')
if __name__=='__main__': main()
