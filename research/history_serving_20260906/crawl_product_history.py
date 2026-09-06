from pathlib import Path
import json,re,time,random,concurrent.futures
from urllib.parse import quote,urlparse
import pandas as pd, requests
from lxml import html
ROOT=Path(r'C:\Users\tarou\Downloads\sake-saijo-db')
RDIR=ROOT/'research'/'history_serving_20260906'
FILES=list(ROOT.glob('東広島市_*_現行日本酒一覧.csv'))
DF=pd.concat([pd.read_csv(f,encoding='utf-8-sig').fillna('') for f in FILES],ignore_index=True)
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36'}
HISTKW=re.compile(r'(発売|新発売|販売開始|出荷|誕生|開発|復刻|刷新|リニューアル|受賞|金賞|最高金賞|トロフィ|採用|限定|初めて|初の|開始|創業|復活|酒米|酵母|杜氏|仕込|醸造|周年|20\d{2}年|19\d{2}年)')
DATE_RE=re.compile(r'((?:19|20)\d{2})[年./-]\s*(\d{1,2})?[月./-]?\s*(\d{1,2})?日?')

def clean(s): return re.sub(r'\s+',' ',str(s or '')).strip()

def page_info(url):
    out={'status':'','title':'','description':'','published':'','modified':'','history_excerpt':'','error':''}
    if not url: return out
    try:
        r=requests.get(url,headers=UA,timeout=18); out['status']=str(r.status_code)
        if r.status_code!=200: return out
        doc=html.fromstring(r.content)
        out['title']=clean(' '.join(doc.xpath('//title/text()')))
        out['description']=clean(' '.join(doc.xpath('//meta[@name="description"]/@content | //meta[@property="og:description"]/@content')))
        pub=doc.xpath('//meta[@property="article:published_time"]/@content | //time/@datetime')
        mod=doc.xpath('//meta[@property="article:modified_time"]/@content')
        out['published']=clean(pub[0] if pub else '')[:40]; out['modified']=clean(mod[0] if mod else '')[:40]
        txt=clean(' '.join(doc.xpath('//body//text()[not(ancestor::script) and not(ancestor::style)]')))
        parts=re.split(r'(?<=[。！？])\s*|\s{2,}',txt)
        cand=[]
        for p in parts:
            p=clean(p)
            if 25<=len(p)<=280 and HISTKW.search(p):
                cand.append(p)
            if len(cand)>=4: break
        out['history_excerpt']=' | '.join(cand)[:900]
    except Exception as e: out['error']=type(e).__name__+': '+str(e)[:160]
    return out

def google_info(brewery,product):
    q=f'"{product}" "{brewery}" 発売 OR 新発売 OR 受賞 OR リニューアル OR 限定'
    out={'query':q,'results':'','error':''}
    try:
        u='https://www.google.com/search?q='+quote(q)+'&num=10&hl=ja'
        r=requests.get(u,headers=UA,timeout=18)
        doc=html.fromstring(r.content)
        items=[]
        for h3 in doc.xpath('//h3'):
            a=h3.getparent()
            while a is not None and a.tag!='a': a=a.getparent()
            if a is None: continue
            href=a.get('href','')
            title=clean(' '.join(h3.xpath('.//text()')))
            block=h3
            for _ in range(4):
                if block.getparent() is not None: block=block.getparent()
            text=clean(' '.join(block.xpath('.//text()')))
            if title and href.startswith('http'):
                items.append({'title':title,'url':href,'snippet':text[:500]})
            if len(items)>=5: break
        out['results']=json.dumps(items,ensure_ascii=False)
    except Exception as e: out['error']=type(e).__name__+': '+str(e)[:160]
    return out

def one(row):
    p=page_info(row['出典URL']); g=google_info(row['酒蔵'],row['商品名'])
    return {**{k:row.get(k,'') for k in ['酒蔵','ブランド','商品名','分類','使用米','精米歩合','流通区分','備考','出典URL']},
            **{'page_'+k:v for k,v in p.items()},**{'search_'+k:v for k,v in g.items()}}

if __name__=='__main__':
    rows=DF.to_dict('records'); done=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs={ex.submit(one,r):i for i,r in enumerate(rows)}
        for n,f in enumerate(concurrent.futures.as_completed(futs),1):
            try: done.append(f.result())
            except Exception as e: print('ERR',futs[f],e)
            if n%20==0: print('done',n,'/',len(rows),flush=True)
    out=pd.DataFrame(done).sort_values(['酒蔵','商品名'])
    out.to_csv(RDIR/'product_history_web_research.csv',index=False,encoding='utf-8-sig')
    print('saved',len(out),'page_ok',int((out.page_status=='200').sum()),
          'search_with_results',int(out.search_results.str.len().gt(2).sum()))
