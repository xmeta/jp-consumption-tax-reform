#!/usr/bin/env python3
"""Build SME Agency FY2025 invoice-transaction evidence.

The report surveys a targeted small-business frame and asks about the largest
customer relationship.  Outputs preserve survey incidence and industry
heterogeneity without treating them as population causal effects or GDP losses.
"""
from pathlib import Path
import argparse, csv, io, re, unicodedata
from decimal import Decimal
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT/'data/source_catalog.csv'
OUT_OVERALL=ROOT/'data/derived/smea_fy2025_invoice_transaction_overall.csv'
OUT_INDUSTRY=ROOT/'data/derived/smea_fy2025_invoice_transaction_industry.csv'
SOURCE_ID='SMEA-FY2025-INVOICE-TRANSACTION-SURVEY-ARCHIVED'
EXPECTED_SHA='5d35852bc1602c575425532244d7475393dc7385d24cc0cbfcc32f553af57d7b'


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

def count_bounds(n,pct):
    """Integer counts consistent with a percentage rounded to one decimal.

    Uses the half-open interval [p-0.05,p+0.05), adequate for published one-decimal
    percentages away from exact half ties.  The report itself notes rounding.
    """
    p=Decimal(str(pct)); lo=p-Decimal('0.05'); hi=p+Decimal('0.05')
    vals=[]
    for k in range(n+1):
        q=Decimal(100)*Decimal(k)/Decimal(n)
        if lo <= q < hi: vals.append(k)
    if not vals: raise RuntimeError(f'no count compatible with n={n}, pct={pct}')
    return min(vals),max(vals)

def metric(metric_id,value,unit,n,locator,status,model_use,note,pct=None):
    lo=hi=''
    if pct is not None:
        lo_i,hi_i=count_bounds(n,pct); lo=str(lo_i); hi=str(hi_i)
    return {
      'metric_id':metric_id,'value':str(value),'unit':unit,'denominator_n':str(n) if n else '',
      'rounded_count_lower':lo,'rounded_count_upper':hi,'source_id':SOURCE_ID,
      'source_locator':locator,'identification_status':status,'model_use':model_use,'note':note
    }

def build():
    cat={r['source_id']:r for r in read_csv(CAT)}
    if SOURCE_ID not in cat: raise RuntimeError(f'missing source {SOURCE_ID}')
    src=cat[SOURCE_ID]
    if src['sha256']!=EXPECTED_SHA: raise RuntimeError(f'{SOURCE_ID}: unexpected sha256 {src["sha256"]}')
    r=PdfReader(ROOT/src['raw_file'])
    if len(r.pages)!=27: raise RuntimeError(f'{SOURCE_ID}: unexpected pages {len(r.pages)}')
    p3=r.pages[2].extract_text() or ''; p4=r.pages[3].extract_text() or ''
    p6=r.pages[5].extract_text() or ''; p7=r.pages[6].extract_text() or ''; p8=r.pages[7].extract_text() or ''
    p9=r.pages[8].extract_text() or ''; p10=r.pages[9].extract_text() or ''; p11=r.pages[10].extract_text() or ''; p12=r.pages[11].extract_text() or ''
    p14=r.pages[13].extract_text() or ''; p15=r.pages[14].extract_text() or ''; p16=r.pages[15].extract_text() or ''
    p19=r.pages[18].extract_text() or ''; p20=r.pages[19].extract_text() or ''; p22=r.pages[21].extract_text() or ''; p23=r.pages[22].extract_text() or ''

    require(p3,['令和7年7月8日','8月1日','対象事業者数:50,000者','2023年1~12月期売上が1千万円以下','無回答は除外'], 'SMEA FY2025 p3')
    require(p4,['2025年7月調査','15,425','30.9%','2025年7月調査は50,000となっている'], 'SMEA FY2025 p4')
    require(p6,['N数15,140','15.3%','11.8%','72.9%','インボイス制度開始を機に課税事業者になった'], 'SMEA FY2025 p6')
    require(p7,['N数15,372','22.8%','77.2%','インボイス登録をした'], 'SMEA FY2025 p7')
    require(p8,['N数15,321','14.3%','85.7%','今後の取引継続の条件としてインボイス登録'], 'SMEA FY2025 p8')
    require(p9,['N数15,333','22.2%','9.5%','68.3%','登録する方向で検討している'], 'SMEA FY2025 p9')
    require(p10,['N数14,595','72.4%','10.8%','16.8%','最も取引額の大きい発注側事業者'], 'SMEA FY2025 p10')
    require(p11,['N数14,732','4.5%','79.8%','3.8%','11.9%','取引価格は減額、または取引停止となった'], 'SMEA FY2025 p11')
    require(p12,['N数14,690','2.7%','3.2%','12.8%','81.4%','価格交渉の場が設けられなかった'], 'SMEA FY2025 p12')
    require(p22,['N数2,83314,595','86.7%','72.4%','14.3ポイント減少'], 'SMEA FY2025 p22')
    require(p23,['N数3,67414,732','3.7%4.5%','50.6%','79.8%','3.6%','3.8%','42.1%','11.9%'], 'SMEA FY2025 p23')

    overall=[
      metric('survey_target_businesses','50000','businesses',0,'PDF p.3 / printed p.2','OBSERVED_SURVEY_FRAME','FRAME_CONTEXT_ONLY','TSR database frame selected businesses with 2023 sales <=10m JPY or specified post-2023 startup/capital conditions.'),
      metric('survey_responses','15425','responses',0,'PDF p.4 / printed p.3','OBSERVED_SURVEY_RESPONSE_COUNT','FRAME_CONTEXT_ONLY','Overall returned questionnaires; question-specific valid N differs because nonresponses are excluded.'),
      metric('survey_response_rate','0.309','ratio',50000,'PDF p.4 / printed p.3','OBSERVED_SURVEY_RESPONSE_RATE','RESPONSE_CONTEXT_NOT_POPULATION_WEIGHT','Published 30.9% response rate; nonresponse prevents treating sample shares as exact population shares.',30.9),
      metric('invoice_start_became_taxable_share','0.118','ratio',15140,'PDF p.6 / printed p.5','SURVEY_RESPONSE_SHARE','OBSERVED_TAX_STATUS_TRANSITION_SELF_REPORT','Share saying they became taxable businesses due to invoice-system introduction.',11.8),
      metric('currently_exempt_share','0.729','ratio',15140,'PDF p.6 / printed p.5','SURVEY_RESPONSE_SHARE','TARGET_FRAME_STATUS_CONTEXT','Share reporting exempt-business status in July 2025.',72.9),
      metric('invoice_registered_share','0.228','ratio',15372,'PDF p.7 / printed p.6','SURVEY_RESPONSE_SHARE','OBSERVED_REGISTRATION_STATUS','Share reporting invoice registration.',22.8),
      metric('customer_required_registration_for_continuation_share','0.143','ratio',15321,'PDF p.8 / printed p.7','SURVEY_RESPONSE_SHARE','OBSERVED_CUSTOMER_REGISTRATION_PRESSURE','Share reporting that a customer required invoice registration as a condition for continuing transactions.',14.3),
      metric('future_registration_consider_share','0.095','ratio',15333,'PDF p.9 / printed p.8','SURVEY_RESPONSE_SHARE','STATED_REGISTRATION_INTENTION','Share considering future invoice registration; intention is not realized transition.',9.5),
      metric('future_registration_no_plan_share','0.683','ratio',15333,'PDF p.9 / printed p.8','SURVEY_RESPONSE_SHARE','STATED_REGISTRATION_INTENTION','Share saying they have no plan to register.',68.3),
      metric('pre_invoice_price_included_tax_share','0.724','ratio',14595,'PDF p.10 / printed p.9','SURVEY_RESPONSE_SHARE','PRE_INVOICE_TRANSACTION_CONTEXT','For the largest customer relationship, share saying transaction price included consumption-tax amount before invoice introduction.',72.4),
      metric('post_invoice_price_reduced_or_transaction_stopped_share','0.038','ratio',14732,'PDF p.11 / printed p.10','SURVEY_RESPONSE_SHARE','OBSERVED_REALIZED_PRICE_OR_TRANSACTION_ADVERSE_OUTCOME','For the largest customer relationship, share reporting price reduction or transaction stop after invoice introduction. Combined outcome cannot separate reduction from stop and does not quantify yen value or causality.',3.8),
      metric('post_invoice_price_unchanged_share','0.798','ratio',14732,'PDF p.11 / printed p.10','SURVEY_RESPONSE_SHARE','OBSERVED_REALIZED_TRANSACTION_PRICE_STATUS','Largest-customer relationship unchanged price after invoice introduction.',79.8),
      metric('post_invoice_price_increased_share','0.119','ratio',14732,'PDF p.11 / printed p.10','SURVEY_RESPONSE_SHARE','OBSERVED_REALIZED_TRANSACTION_PRICE_STATUS','Largest-customer relationship increased price after invoice introduction.',11.9),
      metric('invoice_price_negotiation_no_opportunity_share','0.128','ratio',14690,'PDF p.12 / printed p.11','SURVEY_RESPONSE_SHARE','OBSERVED_NEGOTIATION_ACCESS_FRICTION','Share reporting no opportunity for price negotiation associated with invoice-system introduction.',12.8),
      metric('invoice_price_negotiation_not_needed_share','0.814','ratio',14690,'PDF p.12 / printed p.11','SURVEY_RESPONSE_SHARE','OBSERVED_NEGOTIATION_STATUS','Share reporting price negotiation was unnecessary.',81.4),
      metric('invoice_price_negotiation_customer_initiated_share','0.032','ratio',14690,'PDF p.12 / printed p.11','SURVEY_RESPONSE_SHARE','OBSERVED_NEGOTIATION_STATUS','Share where customer initiated price negotiation and an opportunity was provided.',3.2),
      metric('invoice_price_negotiation_supplier_initiated_share','0.027','ratio',14690,'PDF p.12 / printed p.11','SURVEY_RESPONSE_SHARE','OBSERVED_NEGOTIATION_STATUS','Share where respondent initiated price negotiation and an opportunity was provided.',2.7),
      metric('previous_2023dec_post_invoice_price_reduced_or_stopped_share','0.036','ratio',3674,'PDF p.23 / printed p.22','PRIOR_CROSS_SECTION_SURVEY_SHARE','CROSS_SECTION_COMPARISON_ONLY_NOT_PANEL_TREND','Prior December 2023 cross-section reported 3.6% price reduction or transaction stop; different survey wave/sample, so 3.6% -> 3.8% is not a panel transition estimate.',3.6),
    ]

    # Industry arrays transcribed in the report's fixed order.
    industries=[
      ('manufacturing','製造業',980,'0.230',1008,'0.459',1005,'0.265',991,'0.046',987,'0.154'),
      ('construction','建設業',1588,'0.277',1609,'0.588',1604,'0.327',1592,'0.059',1581,'0.199'),
      ('transport_postal','運輸業，郵便業',153,'0.176',154,'0.338',154,'0.273',152,'0.079',150,'0.153'),
      ('wholesale','卸売業',658,'0.199',673,'0.432',672,'0.253',660,'0.064',656,'0.143'),
      ('retail','小売業',1819,'0.115',1844,'0.235',1830,'0.153',1779,'0.034',1781,'0.126'),
      ('services','サービス業',7005,'0.081',7107,'0.134',7085,'0.092',6715,'0.033',6702,'0.118'),
      ('other','その他',2935,'0.061',2975,'0.125',2969,'0.088',2841,'0.032',2831,'0.097'),
    ]
    require(p14,['製造業980','建設業1,588','運輸業，郵便業153','卸売業658','小売業1,819','サービス業7,005','その他2,935','23.0','27.7','17.6','19.9','11.5','8.1','6.1'], 'SMEA FY2025 p14 industry')
    require(p15,['製造業1,008','建設業1,609','45.9','58.8','33.8','43.2','23.5','13.4','12.5'], 'SMEA FY2025 p15 industry')
    require(p16,['製造業1,005','建設業1,604','26.5','32.7','27.3','25.3','15.3','9.2','8.8'], 'SMEA FY2025 p16 industry')
    require(p19,['製造業991','建設業1,592','4.6','5.9','7.9','6.4','3.4','3.3','3.2'], 'SMEA FY2025 p19 industry')
    require(p20,['製造業987','建設業1,581','15.4','19.9','15.3','14.3','12.6','11.8','9.7'], 'SMEA FY2025 p20 industry')

    ind=[]
    for code,label,n1,transition,n2,registered,n3,req,n6,adverse,n7,noopp in industries:
        ind.append({
          'industry_code':code,'industry_label':label,
          'tax_status_n':n1,'invoice_start_became_taxable_share':transition,
          'registration_n':n2,'invoice_registered_share':registered,
          'registration_request_n':n3,'customer_required_registration_for_continuation_share':req,
          'largest_customer_price_outcome_n':n6,'post_invoice_price_reduced_or_transaction_stopped_share':adverse,
          'price_negotiation_n':n7,'invoice_price_negotiation_no_opportunity_share':noopp,
          'source_id':SOURCE_ID,'source_locator':'PDF pp.14-20 / printed pp.13-19',
          'identification_status':'OBSERVED_INDUSTRY_HETEROGENEITY_SURVEY_RESPONSE',
          'model_use':'HETEROGENEITY_CONTEXT_NOT_POPULATION_CAUSAL_EFFECT',
          'note':'Industry-specific response shares within the targeted TSR survey frame. Denominators vary by question; do not combine as panel transitions or population weights.'
        })
    return overall,ind


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); args=ap.parse_args()
    overall,ind=build(); outs=[(OUT_OVERALL,render(overall)),(OUT_INDUSTRY,render(ind))]
    if args.check:
        stale=[str(p.relative_to(ROOT)) for p,t in outs if not p.exists() or p.read_text(encoding='utf-8')!=t]
        if stale: raise SystemExit('stale generated artifacts: '+', '.join(stale))
        print('SMEA FY2025 invoice transaction bridge: current (18 overall metrics; 7 industries; realized price/transaction incidence only, no macro output calibration)')
    else:
        for p,t in outs:
            p.parent.mkdir(parents=True,exist_ok=True); p.write_text(t,encoding='utf-8')
        print(f'wrote {OUT_OVERALL.relative_to(ROOT)}: {len(overall)} rows')
        print(f'wrote {OUT_INDUSTRY.relative_to(ROOT)}: {len(ind)} rows')
if __name__=='__main__': main()
