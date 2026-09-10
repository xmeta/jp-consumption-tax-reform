#!/usr/bin/env python3
"""Build post-2023 invoice-era transaction-network evidence from JCCI surveys.

The bridge keeps observed transaction adjustment, stated future intentions,
registration pressure, and substitution-friction responses separate.  It does
not infer a macro output effect or a causal cross-year trend.
"""
from pathlib import Path
import argparse, csv, io, re, unicodedata
from decimal import Decimal, getcontext
from pypdf import PdfReader

getcontext().prec=40
ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT/'data/source_catalog.csv'
OUT=ROOT/'data/derived/jcci_invoice_network_distortion_bridge.csv'
S24='JCCI-2024-INVOICE-BACKOFFICE-SURVEY'
S25='JCCI-2025-INVOICE-SURVEY'
HASHES={
 S24:'7ab80915efa7659e6f25cc152b7b5d2eef3c70038333eb6bc043642759d56126',
 S25:'d89a599e900146c7c8ec5e1f4b0702b9dd7d292b47042e9e57186dda4525605e',
}


def read_csv(path):
    with path.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))

def render(rows):
    b=io.StringIO(); w=csv.DictWriter(b,fieldnames=list(rows[0]),lineterminator='\n')
    w.writeheader(); w.writerows(rows); return b.getvalue()

def norm(s):
    s=unicodedata.normalize('NFKC',s or '')
    return re.sub(r'[\s,，]+','',s).replace('−','-').replace('–','-')

def require(text,tokens,label):
    n=norm(text)
    for tok in tokens:
        if norm(tok) not in n: raise RuntimeError(f'{label}: missing token {tok!r}')

def fmt(x):
    s=f'{x:.12f}'.rstrip('0').rstrip('.')
    return s or '0'

def row(year,metric,value,unit,n,scope,sid,locator,evidence_type,status,model_use,note):
    return {
      'survey_year':year,'metric_id':metric,'value':value,'unit':unit,
      'denominator_n':n,'response_scope':scope,'source_id':sid,'source_locator':locator,
      'evidence_type':evidence_type,'identification_status':status,'model_use':model_use,'note':note
    }

def build():
    cat={r['source_id']:r for r in read_csv(CAT)}
    for sid in (S24,S25):
        if sid not in cat: raise RuntimeError(f'missing source {sid}')
        if cat[sid]['sha256']!=HASHES[sid]: raise RuntimeError(f'{sid}: unexpected sha256')
    r24=PdfReader(ROOT/cat[S24]['raw_file']); r25=PdfReader(ROOT/cat[S25]['raw_file'])
    if len(r24.pages)!=25: raise RuntimeError(f'{S24}: unexpected pages {len(r24.pages)}')
    if len(r25.pages)!=21: raise RuntimeError(f'{S25}: unexpected pages {len(r25.pages)}')

    p24_5=r24.pages[4].extract_text() or ''
    p24_7=r24.pages[6].extract_text() or ''
    p24_10=r24.pages[9].extract_text() or ''
    p25_5=r25.pages[4].extract_text() or ''
    p25_7=r25.pages[6].extract_text() or ''
    p25_10=r25.pages[9].extract_text() or ''
    p25_11=r25.pages[10].extract_text() or ''

    require(p24_5,['BtoB中心事業者では73.3%','BtoB中心事業者(n=348)'],'JCCI2024 p5')
    require(p24_7,['BtoB中心事業者の64.0%が今後登録を検討','取引先から要請があれば検討','47.7%','(n=86)'],'JCCI2024 p7')
    require(p24_10,[
      '制度導入後もほぼすべての免税事業者からの仕入等を継続する事業者は、74.0%',
      '今後も継続予定の事業者は47.1%',
      'あり43.4%','(n=1,808)','(n=782)','(n=732)',
      '一部のみ継続7.9%','ごく一部のみ継続12.8%','全ての取引を終了5.2%',
      '一切行わない3.8%','一部を除いて行わない10.7%','引下げ段階で見直し12.7%',
      '終了段階で見直し2.2%','未定23.5%'
    ],'JCCI2024 p10')

    require(p25_5,['BtoB中心事業者では78.6%','BtoB中心事業者(n=285)','今回と同一事業者の回答ではありません'],'JCCI2025 p5')
    require(p25_7,['BtoB中心事業者の50.8%が今後登録を検討','取引先から要請があれば検討','45.9%','(n=61)'],'JCCI2025 p7')
    require(p25_10,[
      '免税事業者から仕入等を行う本則課税事業者は43.7%',
      '57.6%は仕入額が100万円以上','(n=1,151)','(n=503)'
    ],'JCCI2025 p10')
    require(p25_11,[
      '今後、取引価格や仕入先の見直しを行う事業者は42.3%',
      '取引価格を変更せず','自社で負担した','販売先への取引価格','に転嫁した',
      '控除ができなくなる分の全部','又は一部を引下げた','消費税相当分(10%又は','8%)を引下げた',
      '87.5%','9.3%','5.4%','2.2%',
      '価格を維持したまま取引を継続21.5%','取引価格を見直す30.5%',
      '仕入等を一切行わない2.0%','一部を除いて仕入等を行わない9.8%',
      'まだわからない35.1%','その他1.1%',
      '代替となる取引先がない','44.6%','他を探す手間に見合わない','39.1%',
      '人手不足等により免税事業者とも取引を行う必要がある','38.0%',
      '小規模事業者を応援したい','34.8%','既存の取引の方が安い','14.1%','(n=92)'
    ],'JCCI2025 p11')

    rows=[]
    # Registration pressure / response. Cross-year samples are explicitly not the same firms.
    rows += [
      row('2024','former_exempt_b2b_invoice_registration_share','0.733','ratio','348','former exempt BtoB-centered businesses',S24,'PDF p.5 / printed p.4','SURVEY_RESPONSE_SHARE','OBSERVED_INVOICE_REGISTRATION_RESPONSE','REGISTRATION_RESPONSE_CONTEXT_ONLY','Share registered as qualified invoice issuers after system introduction.'),
      row('2024','nonregistered_exempt_b2b_future_registration_consider_share','0.640','ratio','86','nonregistered former-exempt BtoB-centered businesses',S24,'PDF p.7 / printed p.6','SURVEY_RESPONSE_SHARE','OBSERVED_STATED_REGISTRATION_INTENTION','INTENTION_NOT_REALIZED_BEHAVIOR','Share considering some future registration path.'),
      row('2024','nonregistered_exempt_b2b_register_if_customer_requests_share','0.477','ratio','86','nonregistered former-exempt BtoB-centered businesses',S24,'PDF p.7 / printed p.6','SURVEY_RESPONSE_SHARE','OBSERVED_STATED_REGISTRATION_INTENTION','CUSTOMER_PRESSURE_CHANNEL_CONTEXT','Share saying they would consider registration if requested by a customer.'),
      row('2025','former_exempt_b2b_invoice_registration_share','0.786','ratio','285','former exempt BtoB-centered businesses',S25,'PDF p.5 / printed p.4','SURVEY_RESPONSE_SHARE','OBSERVED_INVOICE_REGISTRATION_RESPONSE','REGISTRATION_RESPONSE_CONTEXT_ONLY','Share registered as qualified invoice issuers. JCCI explicitly states the 2024 and 2025 respondents are not the same businesses, so the cross-year difference is not a panel transition estimate.'),
      row('2025','nonregistered_exempt_b2b_future_registration_consider_share','0.508','ratio','61','nonregistered former-exempt BtoB-centered businesses',S25,'PDF p.7 / printed p.6','SURVEY_RESPONSE_SHARE','OBSERVED_STATED_REGISTRATION_INTENTION','INTENTION_NOT_REALIZED_BEHAVIOR','Share considering some future registration path.'),
      row('2025','nonregistered_exempt_b2b_register_if_customer_requests_share','0.459','ratio','61','nonregistered former-exempt BtoB-centered businesses',S25,'PDF p.7 / printed p.6','SURVEY_RESPONSE_SHARE','OBSERVED_STATED_REGISTRATION_INTENTION','CUSTOMER_PRESSURE_CHANNEL_CONTEXT','Share saying they would consider registration if requested by a customer.'),
    ]

    # 2024 actual post-introduction supplier-network status among firms that had exempt suppliers before introduction.
    actual24=[('almost_all_continue','0.740'),('some_only_continue','0.079'),('very_few_only_continue','0.128'),('all_transactions_ended','0.052')]
    for metric,val in actual24:
        rows.append(row('2024',f'post_intro_exempt_supplier_{metric}_share',val,'ratio','782','taxable/registered respondents that had purchases from exempt businesses before invoice introduction',S24,'PDF p.10 / printed p.9','SURVEY_RESPONSE_SHARE','OBSERVED_POST_INTRODUCTION_NETWORK_STATUS','NETWORK_ADJUSTMENT_INCIDENCE_NOT_OUTPUT_EFFECT','Mutually exclusive reported post-introduction supplier-relationship status.'))
    contraction=Decimal('0.079')+Decimal('0.128')+Decimal('0.052')
    rows.append(row('2024','post_intro_exempt_supplier_reported_contraction_category_share',fmt(contraction),'ratio','782','same as 2024 post-introduction supplier-status question',S24,'PDF p.10 / printed p.9; derived sum','DERIVED_ROUNDED_CATEGORY_SUM','OBSERVED_POST_INTRODUCTION_NETWORK_CONTRACTION_CATEGORY_SUM','INCIDENCE_ONLY_NOT_CAUSAL_OUTPUT_LOSS','Sum of some-only, very-few-only, and all-ended categories = 25.9%. Categories imply fewer exempt-supplier relationships than nearly-all continuation, but the survey does not quantify transaction value lost or macro output effects; published percentages are rounded.'))

    # 2024 stated future response under scheduled transition-rule changes.
    future24=[('continue','0.471'),('none','0.038'),('mostly_none','0.107'),('review_at_2026_credit_reduction','0.127'),('review_at_2029_transition_end','0.022'),('undecided','0.235')]
    for metric,val in future24:
        rows.append(row('2024',f'future_exempt_supplier_{metric}_share',val,'ratio','732','respondents still purchasing from exempt businesses',S24,'PDF p.10 / printed p.9','SURVEY_RESPONSE_SHARE','OBSERVED_STATED_FUTURE_NETWORK_INTENTION','INTENTION_NOT_REALIZED_NETWORK_EFFECT','Mutually exclusive future policy response; scheduled input-tax-credit transition changes are part of the question context.'))
    planned24=Decimal('0.038')+Decimal('0.107')+Decimal('0.127')+Decimal('0.022')
    rows.append(row('2024','future_exempt_supplier_stop_or_review_share',fmt(planned24),'ratio','732','respondents still purchasing from exempt businesses',S24,'PDF p.10 / printed p.9; derived sum','DERIVED_ROUNDED_CATEGORY_SUM','STATED_FUTURE_STOP_OR_REVIEW_INTENTION','INTENTION_NOT_REALIZED_NETWORK_EFFECT','Sum of all-stop, mostly-stop, review-at-2026 and review-at-2029 categories = 29.4%; not a forecast of realized supplier exit.'))

    # 2025 current exposure and price-incidence responses.
    rows += [
      row('2025','taxable_firms_with_exempt_supplier_purchases_share','0.437','ratio','1151','qualified-invoice-registered general-taxation businesses',S25,'PDF p.10 / printed p.9','SURVEY_RESPONSE_SHARE','OBSERVED_CURRENT_EXEMPT_SUPPLIER_EXPOSURE','NETWORK_EXPOSURE_CONTEXT_ONLY','Share currently purchasing from exempt businesses.'),
      row('2025','exempt_supplier_purchase_amount_ge_1m_yen_share','0.576','ratio','503','respondents with purchases from exempt businesses',S25,'PDF p.10 / printed p.9','SURVEY_RESPONSE_SHARE','OBSERVED_CURRENT_EXEMPT_SUPPLIER_EXPOSURE','EXPOSURE_SCALE_CONTEXT_ONLY','Share reporting annual purchases from exempt businesses of at least 1 million yen.'),
    ]
    current25=[
      ('current_price_unchanged_self_absorb_share','0.875','CURRENT_COST_ABSORPTION_INCIDENCE'),
      ('current_pass_to_sales_price_share','0.093','DOWNSTREAM_PRICE_PASS_THROUGH_INCIDENCE'),
      ('current_lower_purchase_price_by_denied_credit_share','0.054','SUPPLIER_PRICE_PRESSURE_INCIDENCE'),
      ('current_lower_purchase_price_by_full_tax_share','0.022','SUPPLIER_PRICE_PRESSURE_INCIDENCE'),
    ]
    for metric,val,status in current25:
        rows.append(row('2025',metric,val,'ratio','503','respondents with purchases from exempt businesses; multiple response',S25,'PDF p.11 / printed p.10','MULTIPLE_RESPONSE_SHARE',status,'INCIDENCE_ONLY_NOT_UNIQUE_FIRM_SHARE_OR_OUTPUT_EFFECT','Multiple-response current treatment of purchases from exempt businesses; shares must not be summed as mutually exclusive firm fractions.'))

    future25=[('price_maintain_continue','0.215'),('price_review','0.305'),('all_stop','0.020'),('mostly_stop','0.098'),('undecided','0.351'),('other','0.011')]
    for metric,val in future25:
        rows.append(row('2025',f'future_exempt_supplier_{metric}_share',val,'ratio','502','respondents with purchases from exempt businesses',S25,'PDF p.11 / printed p.10','SURVEY_RESPONSE_SHARE','OBSERVED_STATED_FUTURE_NETWORK_INTENTION','INTENTION_NOT_REALIZED_NETWORK_EFFECT','Mutually exclusive future policy response.'))
    rows.append(row('2025','future_price_or_supplier_review_share','0.423','ratio','502','respondents with purchases from exempt businesses',S25,'PDF p.11 / printed p.10','SURVEY_HEADLINE_AND_CATEGORY_SUM','STATED_FUTURE_PRICE_OR_SUPPLIER_REVIEW_INTENTION','INTENTION_NOT_REALIZED_NETWORK_EFFECT','JCCI headline share; equals price review 30.5% + mostly stop 9.8% + all stop 2.0% = 42.3%.'))
    supplier_reduce=Decimal('0.020')+Decimal('0.098')
    rows.append(row('2025','future_supplier_reduction_or_exit_share',fmt(supplier_reduce),'ratio','502','respondents with purchases from exempt businesses',S25,'PDF p.11 / printed p.10; derived sum','DERIVED_ROUNDED_CATEGORY_SUM','STATED_FUTURE_SUPPLIER_REDUCTION_INTENTION','INTENTION_NOT_REALIZED_NETWORK_EFFECT','All-stop plus mostly-stop = 11.8%. This is stated intention, not realized exit or a causal output effect.'))

    frictions=[
      ('continue_reason_no_alternative_supplier_share','0.446','SUBSTITUTION_FRICTION_NO_ALTERNATIVE'),
      ('continue_reason_search_effort_not_worth_it_share','0.391','SUBSTITUTION_FRICTION_SEARCH_COST'),
      ('continue_reason_labor_shortage_requires_exempt_suppliers_share','0.380','SUBSTITUTION_FRICTION_CAPACITY_CONSTRAINT'),
      ('continue_reason_support_small_local_business_share','0.348','RELATIONSHIP_OR_LOCAL_SUPPORT_MOTIVE'),
      ('continue_reason_existing_supplier_still_cheaper_share','0.141','RELATIVE_PRICE_ADVANTAGE'),
    ]
    for metric,val,status in frictions:
        rows.append(row('2025',metric,val,'ratio','92','respondents planning to continue at unchanged price; multiple response',S25,'PDF p.11 / printed p.10','MULTIPLE_RESPONSE_SHARE',status,'SUBSTITUTION_FRICTION_CONTEXT_NOT_MACRO_OUTPUT_EFFECT','Reason for continuing exempt-supplier transactions at unchanged price; multiple response.'))

    return rows


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); args=ap.parse_args()
    text=render(build())
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding='utf-8')!=text:
            raise SystemExit(f'stale generated artifact: {OUT.relative_to(ROOT)}')
        print('JCCI invoice-network distortion bridge: current (post-introduction status, future intentions, registration pressure, substitution frictions; no macro a_alloc calibration)')
    else:
        OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(text,encoding='utf-8')
        print(f'wrote {OUT.relative_to(ROOT)}: {len(build())} rows')
if __name__=='__main__': main()
