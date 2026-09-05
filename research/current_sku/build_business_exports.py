from pathlib import Path
import json, math, re, unicodedata
from difflib import SequenceMatcher
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
import build_boss_exports as old

ROOT=Path(r"C:\Users\tarou\Downloads\sake-saijo-db")
DIR=ROOT/'research'/'current_sku'; WEB_DIR=ROOT/'research'/'web'
SKU=pd.read_csv(DIR/'sku_master.csv',encoding='utf-8-sig').fillna('')
WEB=pd.read_csv(WEB_DIR/'index.csv',encoding='utf-8-sig').fillna('')
OLD=pd.concat([pd.read_csv(DIR/'boss_西条エリア7蔵_products.csv',encoding='utf-8-sig'),pd.read_csv(DIR/'boss_安芸津・黒瀬エリア3蔵_products.csv',encoding='utf-8-sig')],ignore_index=True).fillna('')
CLUES=pd.read_csv(DIR/'source_clues.csv',encoding='utf-8-sig').fillna('') if (DIR/'source_clues.csv').exists() else pd.DataFrame()
AREAS=old.AREAS

MANUAL_ALIAS={
 ('金光酒造','賀茂金秀 SUITOH'):'賀茂金秀 SUITOH 雄町',
 ('賀茂泉酒造','COKUN(こくん)'):'COKUN',
 ('賀茂泉酒造','純米吟醸生原酒 RockHopper'):'純米吟醸生原酒 ROCK HOPPER',
 ('白牡丹酒造','大吟醸 いちの雫 (しずく酒)'):'大吟醸 いちの雫（しずく酒）',
}
EXPLICIT_SWEET={
 ('賀茂鶴酒造','豊醇冷酒'):('やや甘口','公式EC商品説明'),
 ('賀茂鶴酒造','白壁の郷'):('甘口','公式EC商品説明'),
 ('賀茂鶴酒造','酒中在心 茜 純米酒 広島錦'):('中口','公式EC「甘からず、辛からず」'),
 ('賀茂泉酒造','純米及川'):('やや辛口','公式EC商品説明'),
 ('賀茂泉酒造','純米大吟醸'):('やや辛口','公式EC商品説明'),
 ('亀齢酒造','亀齢萬年 山田錦 生酒'):('辛口','現行酒販店商品説明'),
 ('亀齢酒造','亀齢萬年 山田錦おりがらみ 生酒'):('辛口','現行酒販店商品説明'),
 ('亀齢酒造','亀齢 純米吟醸 原形精米 migaki 無濾過生酒'):('辛口','現行酒販店商品説明'),
 ('亀齢酒造','亀齢 純米吟醸 原形精米 migaki 萌えいぶき 生酒'):('中口','現行酒販店商品説明'),
 ('亀齢酒造','亀齢萬年 純米大吟醸原酒五拾 生酒'):('辛口','現行酒販店商品説明'),
 ('今田酒造本店','秋櫻〈コスモス〉 純米 ひやおろし'):('辛口','公式商品説明'),
 ('今田酒造本店','純米にごり スパークリング 白美 HAKUBI'):('やや辛口','公式商品説明'),
 ('今田酒造本店','純米吟醸 美穂 Biho'):('やや辛口','公式商品説明'),
}

def clean(v): return ' '.join(str(v).replace('　',' ').split()) if v not in (None,'') else ''
def core_name(b,n):
    s=unicodedata.normalize('NFKC',clean(n)).lstrip('*').strip()
    s=re.sub(r'^【(?:再販|火入れ|生酒|凍結生酒|日本酒[^】]*)】','',s).strip()
    s=re.sub(r'\s*-\s*(?:白牡丹酒造|賀茂鶴酒造|福美人酒造).*$','',s)
    s=re.sub(r'(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?:ml|mL|ML|L|l|ℓ|mℓ|ｍｌ)\b','',s)
    s=re.sub(r'\((?:[A-Z]{1,4}-[A-Z0-9-]+)\)|（(?:[A-Z]{1,4}-[A-Z0-9-]+)）','',s)
    s=re.sub(r'(?:化粧箱|木箱|桐箱|クリアケース|ダンボール輸送箱)(?:入|入り)?','',s)
    s=re.sub(r'(?:瓶詰|パック詰|ライトカップ詰|カップ詰|紙パック)','',s)
    s=re.sub(r'\b(?:丸瓶|角瓶|共通)\b','',s)
    s=re.sub(r'\s*\[(?:\s*豪華\s*)?\]','',s)
    s=re.sub(r'\s+',' ',s).strip(' -｜|')
    s=MANUAL_ALIAS.get((b,s),s)
    return s
def norm(s):
    s=unicodedata.normalize('NFKC',clean(s)).casefold()
    s=re.sub(r'[【】\[\]（）()「」『』〈〉<>・･\s]','',s)
    s=re.sub(r'(?:賀茂鶴|白牡丹|西條鶴|西条鶴|亀齢|福美人|賀茂泉|富久長|於多福)','',s)
    s=re.sub(r'\d+(?:\.\d+)?(?:ml|l)','',s)
    return s
def is_bundle(n):
    n=clean(n)
    return bool(re.search(r'セット|飲み比べ|のみくらべ|アソート|詰合|詰め合わせ|オリジナルラベル|\d+本(?:入|化粧箱|木箱|ダンボール)',n))
def best_match(name, df, col='商品名', threshold=0.70):
    a=norm(name); best=None; score=0
    for _,r in df.iterrows():
        b=norm(r[col])
        if not a or not b: continue
        sc=SequenceMatcher(None,a,b).ratio()
        if min(len(a),len(b))>=4 and (a in b or b in a): sc=max(sc,0.91)
        if sc>score: score=sc; best=r
    return (best,score) if best is not None and score>=threshold else (None,score)
def fmt_cap(vals):
    xs=sorted({int(float(v)) for v in vals if str(v).strip() and float(v)>0})
    return ' / '.join(f'{x:,}ml' for x in xs)
def fmt_price(vals):
    xs=sorted({int(float(v)) for v in vals if str(v).strip() and float(v)>0})
    if not xs:return ''
    return f'{xs[0]:,}円' if len(xs)==1 else f'{xs[0]:,}～{xs[-1]:,}円'
def flow_type(g,name):
    chans='|'.join(g['販売チャネル'].astype(str).tolist())
    if '海外限定' in chans or '輸出限定' in chans:return '輸出・海外向け'
    if '流通限定' in chans or '取扱店限定' in chans or '取扱い店限定' in name:return '限定流通'
    if '蔵元限定' in chans or '酒蔵限定' in chans or 'EC限定' in chans or '蔵元限定' in name or '酒蔵限定' in name:return '蔵元限定'
    if '季節限定' in chans or '数量限定' in chans or any(t in name for t in old.SEASONAL_TOKENS):return '季節・数量限定'
    return '一般流通'
