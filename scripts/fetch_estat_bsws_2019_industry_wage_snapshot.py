#!/usr/bin/env python3
"""Refresh a checked-in e-Stat DB snapshot for the 2019 industry wage bridge."""
from pathlib import Path
from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.parse import urlencode
from http.cookiejar import CookieJar
import argparse, base64, gzip, json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/raw/estat/bsws_2019_industry_major_wage_db_snapshot.json'
SID='0003084009'
BASE='https://www.e-stat.go.jp'
DBVIEW=f'{BASE}/dbview?sid={SID}'

def enc(obj):
    raw=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode()
    return base64.b64encode(gzip.compress(raw,mtime=0)).decode()

def select_item(matter,code):
    x=next(v for v in matter['listData'].values() if v['code']==code)
    return {'name':x['name'],'code':x['code'],'unit':x.get('unitName'),'explanation':x.get('explanation')}

def block(matter,codes):
    return {'matterId':matter['matterId'],'tableName':matter['tableName'],
            'dispTableName':matter['dispTableName'],'positionNum':matter['positionNum'],
            'listData':[select_item(matter,c) for c in codes],'allSelected':0}

def fetch():
    headers={'User-Agent':'Mozilla/5.0','Referer':DBVIEW}
    opener=build_opener(HTTPCookieProcessor(CookieJar()))
    opener.open(Request(DBVIEW,headers=headers),timeout=30).read()
    model_raw=opener.open(Request(f'{BASE}/dbview/api_get_model?sid={SID}',data=b'',headers=headers,method='POST'),timeout=30).read().decode()
    model=json.loads(model_raw); ms=model['matters']
    rows=[block(ms['matter7'],['01']),block(ms['matter5'],['01']),block(ms['matter6'],['01'])]
    cols=[block(ms['matter18'],['36','38','40','42']),block(ms['matter3'],['01'])]
    industries=[x for x in ms['matter4']['listData'].values() if x['classLevel']<=2]
    responses=[]
    for ind in industries:
        tops=[block(ms['matter4'],[ind['code']]),block(ms['matter8'],['02']),block(ms['matter2'],['20190000000'])]
        payload={'rows':enc(rows),'cols':enc(cols),'tops':enc(tops),'apiTops':enc(tops),
          'annotationFlg':model['annotationFlg'],'rowNoDataDispFlg':model['rowNoDataDispFlg'],
          'colNoDataDispFlg':model['colNoDataDispFlg'],'commaType':model['commaType'],
          'replaceSpChars':model['replaceSpChars'],'graphAxis':model['graphAxis'],
          'graphBasis':model['graphBasis'],'graphSort':model['graphSort'],'graphTitle':model['graphTitle'],
          'graphType':model['graphType'],'inputNumberOfCols':model['inputNumberOfCols'],
          'inputNumberOfRows':model['inputNumberOfRows'],'movementId':0,
          'leftMoveFlg':model['leftMoveFlg'],'rightMoveFlg':model['rightMoveFlg'],
          'underMoveFlg':model['underMoveFlg'],'upMoveFlg':model['upMoveFlg'],
          'currentCols':'','currentRows':'','mode':'table','layoutName':''}
        raw=opener.open(Request(f'{BASE}/dbview/api_get_result?sid={SID}',data=urlencode(payload).encode(),headers=headers,method='POST'),timeout=30).read().decode()
        responses.append({'industry_code':ind['code'],'industry_name':ind['name'],'raw_response':raw})
    return {'snapshot_schema':'ESTAT_DBVIEW_RAW_RESPONSE_BUNDLE_V1','sid':SID,'dbview_url':DBVIEW,
            'stat_inf_id':'000031919751','survey_year':2019,
            'selection':{'employment':'general workers','enterprise_size':'10+ employees total',
              'age':'total','education':'total','sex':'total','ownership':'private establishments',
              'items':['scheduled actual work hours','overtime work hours','regular cash earnings','scheduled cash earnings']},
            'model_raw_response':model_raw,'industry_responses':responses}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--stdout',action='store_true'); args=ap.parse_args()
    obj=fetch(); text=json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if args.stdout: print(text,end='')
    else:
        OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(text,encoding='utf-8')
        print(f'wrote {OUT.relative_to(ROOT)}: {len(obj["industry_responses"])} industry rows')
if __name__=='__main__': main()
