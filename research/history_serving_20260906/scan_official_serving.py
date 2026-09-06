from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import re, requests, pandas as pd
from html import unescape
ROOT=Path(r'C:\Users\tarou\Downloads\sake-saijo-db')
OUT=ROOT/'research'/'history_serving_20260906'
OFFICIAL=('kamotsuru.jp','hakubotan.co.jp','saijotsuru.co.jp','kireikireikirei.jimdofree.com','fukubijin.co.jp','kamoizumi.co.jp','sanyotsuru.jp','fukucho.jp','tsukasyuzou.jp','kamokin.com')
KEYS=('飲み方','飲み頃','おすすめ温度','冷酒','常温','ぬる燗','熱燗','燗酒','ロック','オンザロック','冷やして')
frames=[pd.read_csv(p,encoding='utf-8-sig').fillna('') for p in ROOT.glob('東広島市_*現行日本酒一覧.csv')]
df=pd.concat(frames,ignore_index=True)
def official(url):
    try: host=urlparse(url).netloc.lower()
    except: return False
    return any(host==d or host.endswith('.'+d) for d in OFFICIAL)
rows=df[df['出典URL'].map(official)][['酒蔵','ブランド','商品名','出典URL']].drop_duplicates().to_dict('records')
def fetch(r):
    out=dict(r); out.update(http_status='',serving_terms='',serving_snippet='',scan_error='')
    try:
        x=requests.get(r['出典URL'],headers={'User-Agent':'Mozilla/5.0 sake-saijo-db/1.0'},timeout=12)
        out['http_status']=x.status_code
        x.raise_for_status()
        text=unescape(re.sub(r'<script[\\s\\S]*?</script>|<style[\\s\\S]*?</style>|<[^>]+>',' ',x.text,flags=re.I)); text=' '.join(text.split())
        terms=[k for k in KEYS if k in text]
        out['serving_terms']=' / '.join(terms)
        hits=[]
        for k in terms[:5]:
            i=text.find(k); hits.append(text[max(0,i-90):i+180])
        out['serving_snippet']=' || '.join(dict.fromkeys(hits))[:240]
    except Exception as e:
        out['scan_error']=type(e).__name__+': '+str(e)[:180]
    return out
results=[]
with ThreadPoolExecutor(max_workers=10) as ex:
    futs=[ex.submit(fetch,r) for r in rows]
    for f in as_completed(futs): results.append(f.result())
pd.DataFrame(results).sort_values(['酒蔵','ブランド','商品名']).to_csv(OUT/'official_serving_scan.csv',index=False,encoding='utf-8-sig')
print('official rows',len(results),'with serving terms',sum(bool(x['serving_terms']) for x in results),'errors',sum(bool(x['scan_error']) for x in results))


