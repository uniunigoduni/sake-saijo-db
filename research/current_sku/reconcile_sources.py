from pathlib import Path
import csv, glob, html, json, re
from difflib import SequenceMatcher
import pandas as pd

ROOT = Path(r"C:\Users\tarou\Downloads\sake-saijo-db")
OUT = ROOT / "research" / "current_sku"
SRC = ROOT / "sources"
prod = pd.concat([
    pd.read_csv(OUT / "boss_西条エリア7蔵_products.csv", encoding="utf-8-sig"),
    pd.read_csv(OUT / "boss_安芸津・黒瀬エリア3蔵_products.csv", encoding="utf-8-sig"),
], ignore_index=True)
BREWER_ALIASES = {
 "賀茂鶴酒造":{"賀茂鶴酒造"}, "白牡丹酒造":{"白牡丹酒造"},
 "西條鶴醸造":{"西條鶴醸造","西條鶴酒造"}, "亀齢酒造":{"亀齢酒造"},
 "福美人酒造":{"福美人酒造"}, "賀茂泉酒造":{"賀茂泉酒造"},
 "山陽鶴酒造":{"山陽鶴酒造"}, "金光酒造":{"金光酒造"},
 "今田酒造本店":{"今田酒造本店"}, "柄酒造":{"柄酒造"},
}
BRANDS={"賀茂鶴酒造":["賀茂鶴"],"白牡丹酒造":["白牡丹","藝陽男山"],"西條鶴醸造":["西條鶴","神髄","蔵楽"],"亀齢酒造":["亀齢","亀齢萬年"],"福美人酒造":["福美人"],"賀茂泉酒造":["賀茂泉","造賀","NAO"],"山陽鶴酒造":["山陽鶴"],"金光酒造":["賀茂金秀","桜吹雪","神のいたずら"],"今田酒造本店":["富久長","海風土","美穂"],"柄酒造":["於多福","関西一"]}
clues=[]
def clean(v):
    if v is None or (isinstance(v,float) and pd.isna(v)): return ""
    return " ".join(str(v).replace("　"," ").split())
def norm(s):
    s=clean(s).lower().replace("さいじょうつる","")
    s=re.sub(r"[（(].*?[）)]","",s)
    s=re.sub(r"[【】\[\]「」『』〈〉<>・･\s]","",s)
    s=re.sub(r"\d+(?:\.\d+)?(?:ml|mℓ|ｍｌ|l|ℓ)","",s,flags=re.I)
    for p in ["賀茂鶴","白牡丹","西條鶴","西条鶴","亀齢","福美人","賀茂泉","富久長","於多福"]:
        if s.startswith(p.lower()): s=s[len(p):]
    return s
def add(src,b,n,meter="",temp="",polish="",alc="",extra="",ref=""):
    n=clean(n)
    if n: clues.append({"source":src,"酒蔵":b,"候補名":n,"日本酒度":clean(meter),"飲用温度":clean(temp),"精米歩合":clean(polish),"ALC":clean(alc),"補足":clean(extra),"source_ref":ref})
def brewer_for(name):
    for b,als in BREWER_ALIASES.items():
        if name in als: return b
    return ""
def by_brand(text):
    hits=[b for b,brands in BRANDS.items() if any(x in text for x in brands)]
    return hits[0] if len(hits)==1 else ""

# sake_dataset: 数値スペックの古い手がかり。現行判定には使わない。
ds=json.load(open(SRC/'sake_dataset'/'sake_dataset_repo__json__sake_dataset_v1.json',encoding='utf-8'))['dataset']
for r in ds:
    b=brewer_for(clean(r.get('brewer')))
    if not b and clean(r.get('city'))!='東広島市': continue
    if not b: b=by_brand(clean(r.get('brand+name')))
    if not b: continue
    sm=r.get('sake_meter_value') or {}; ar=r.get('alcohol_rate') or {}
    add('sake_dataset',b,r.get('brand+name'),sm.get('mean',''),'',r.get('rice_polishing_rate',''),ar.get('mean',''),r.get('sake_class',''),'sake_dataset_v1.json')
# sake_suggest: 広島県かつ酒蔵名を厳密一致させ、他県同名銘柄を排除。
for f in glob.glob(str(SRC/'sake_suggest'/'*api_page_*.json')):
    x=json.load(open(f,encoding='utf-8'))
    for r in x.get('sakes',[]):
        if clean(r.get('prefecture')) not in {'広島','広島県'}: continue
        b=brewer_for(clean(r.get('brewery_name')))
        if not b: continue
        add('sake_suggest',b,r.get('sake_name'),r.get('sake_meter_value'),r.get('serving_temperature'),r.get('rice_polishing_ratio'),r.get('alcohol_content'),r.get('category'),Path(f).name)

# SAKEOpenData: rawは壊れたJSONのまま保存し、各フラットobjectを正規表現で読むだけにする。
od=(SRC/'sakeopendata'/'sakeopendata_repo__json__bottles__hiroshima.json').read_text(encoding='utf-8')
for block in re.findall(r'\{.*?\}',od,re.S):
    def field(k):
        m=re.search(r'"'+re.escape(k)+r'"\s*:\s*"(.*?)"',block,re.S); return m.group(1) if m else ''
    b=brewer_for(field('brewery'))
    if not b: continue
    name=field('brand') + ((' '+field('subname')) if field('subname') else '')
    add('sakeopendata',b,name,field('sakeMeterValue'),field('matchDrinkingTemperature'),field('ricePolishingRate'),field('alcoholContent'),field('type'),field('url'))

# Sakenowa: 広島県areaId=34の酒蔵IDだけをブランド候補として使う。
sb=json.load(open(SRC/'sakenowa'/'sakenowa_breweries.json',encoding='utf-8'))['breweries']
sbrands=json.load(open(SRC/'sakenowa'/'sakenowa_brands.json',encoding='utf-8'))['brands']
id_to_b={r['id']:brewer_for(r['name']) for r in sb if r.get('areaId')==34 and brewer_for(r['name'])}
for r in sbrands:
    if r.get('breweryId') in id_to_b: add('sakenowa',id_to_b[r['breweryId']],r.get('name'),extra='ブランド候補',ref='sakenowa_brands.json')
# Jsake: 商品ページタイトルに対象ブランドが現れるものを候補化。
manifest=[]
with open(SRC/'jsake'/'manifest.jsonl',encoding='utf-8') as f:
    for line in f:
        try: manifest.append(json.loads(line))
        except Exception: pass
for r in manifest:
    fp=SRC/'jsake'/clean(r.get('file'))
    if not fp.exists() or fp.suffix.lower()!='.html': continue
    try: text=fp.read_text(encoding='utf-8',errors='ignore')
    except Exception: continue
    tm=re.search(r'<title[^>]*>(.*?)</title>',text,re.I|re.S)
    title=html.unescape(re.sub(r'<[^>]+>',' ',tm.group(1))).strip() if tm else ''
    if not title: continue
    b=by_brand(title)
    if not b: continue
    title=re.sub(r'\s*[|｜].*$','',title).strip()
    add('jsake',b,title,extra='ページタイトル候補',ref=clean(r.get('url')))

clue=pd.DataFrame(clues).drop_duplicates().reset_index(drop=True)
clue.to_csv(OUT/'source_clues.csv',index=False,encoding='utf-8-sig')
match_rows=[]
for _,c in clue.iterrows():
    candidates=prod[prod['酒蔵']==c['酒蔵']]
    cn=norm(c['候補名']); best_name=''; best=0.0
    for _,p in candidates.iterrows():
        pn=norm(p['商品名'])
        if not cn or not pn: continue
        score=SequenceMatcher(None,cn,pn).ratio()
        if min(len(cn),len(pn))>=4 and (cn in pn or pn in cn): score=max(score,0.92)
        if score>best: best=score; best_name=p['商品名']
    status='一致' if best>=0.74 else ('候補' if best>=0.55 else '未一致')
    d=c.to_dict(); d.update({'照合状態':status,'照合先':best_name,'類似度':round(best,3)}); match_rows.append(d)
matches=pd.DataFrame(match_rows)
matches.to_csv(OUT/'source_matches.csv',index=False,encoding='utf-8-sig')
unmatched=matches[(matches['照合状態']!='一致') & ~((matches['source']=='sakenowa') & (matches['補足']=='ブランド候補'))].copy()
unmatched.to_csv(OUT/'source_unmatched_candidates.csv',index=False,encoding='utf-8-sig')
summary={
 'clues':len(clue), 'matches':int((matches['照合状態']=='一致').sum()),
 'candidate_or_unmatched':len(unmatched),
 'by_source':clue.groupby('source').size().to_dict(),
 'unmatched_by_brewery':unmatched.groupby('酒蔵').size().to_dict(),
}
(OUT/'source_reconciliation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
print('\nUNMATCHED TOP')
print(unmatched[['source','酒蔵','候補名','照合状態','照合先','類似度']].head(100).to_string(index=False))

