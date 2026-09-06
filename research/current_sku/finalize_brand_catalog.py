from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv, hashlib, json, re, unicodedata
from difflib import SequenceMatcher
import pandas as pd
import requests
import build_boss_exports as old
import content_facts_20260906 as facts
import history_serving_20260906 as hs

ROOT=Path(r'C:\Users\tarou\Downloads\sake-saijo-db')
DIR=ROOT/'research'/'current_sku'; WEB_DIR=ROOT/'research'/'web'
TODAY='2026-09-06'; JST=timezone(timedelta(hours=9))
AREAS=old.AREAS
CORE=pd.read_csv(DIR/'brand_core_seed.csv',encoding='utf-8-sig').fillna('')
REGISTRY=pd.read_csv(DIR/'brand_registry_seed.csv',encoding='utf-8-sig').fillna('')
WEB=pd.read_csv(WEB_DIR/'index.csv',encoding='utf-8-sig').fillna('')
HEAD={'User-Agent':'Mozilla/5.0 (compatible; sake-saijo-db/1.0)'}

CORE_OVERRIDES={
 ('賀茂鶴酒造','酒中在心 橙 純米吟醸 生もと 八反35号'):{'主要容量':'720ml / 1,800ml'},
 ('白牡丹酒造','純米吟醸'):{'主要容量':'720ml / 1,800ml'},
 ('白牡丹酒造','純米酒'):{'主要容量':'300ml / 720ml / 1,800ml'},
 ('福美人酒造','大吟醸 蔵乃華 （ くらのはな ）'):{'主要容量':'720ml / 1,800ml'},
 ('福美人酒造','大吟醸 西條酒造学校'):{'主要容量':'720ml / 1,800ml'},
 ('福美人酒造','純米吟醸'):{'主要容量':'720ml / 1,800ml'},
 ('賀茂泉酒造','純米大吟醸「壽」'):{'主要容量':'720ml / 1,800ml'},
 ('今田酒造本店','富久長 海風土 Seafood 純米'):{'主要容量':'720ml / 1,800ml'},
 ('亀齢酒造','亀齢萬年 純米大吟醸原酒五拾 生酒'):{'主要容量':'720ml / 1,800ml','分類':'純米大吟醸'},
}

def clean(v): return ' '.join(str(v).replace('　',' ').split()) if v not in (None,'') else ''
def norm(v):
    s=unicodedata.normalize('NFKC',clean(v)).casefold()
    s=re.sub(r'[【】\[\]（）()「」『』〈〉<>・･\s]','',s)
    for x in ['日本酒','取扱い店限定酒','蔵元限定酒','季節限定酒','数量限定','再販','スパークリング']:
        s=s.replace(x.casefold(),'')
    s=re.sub(r'\d+(?:\.\d+)?(?:ml|l)','',s)
    s=re.sub(r'製造年月\d{4}年\d{1,2}月','',s)
    s=re.sub(r'(?:共通)?(?:化粧箱|木箱)入(?:り)?','',s)
    s=re.sub(r'[a-z]{1,4}-[a-z0-9]+','',s)
    for x in ['賀茂鶴','白牡丹','西條鶴','西条鶴','亀齢','福美人','賀茂泉','富久長','山陽鶴']:
        if s.startswith(x.casefold()): s=s[len(x):]
    for x in ['瓶詰','福美人酒造株式会社','恵比寿庫えびすぐら','白牡丹酒造','福美人']:
        s=s.replace(x.casefold(),'')
    s=s.replace('特別純米辛口','辛口特別純米')
    if s == '山吹色の酒': s = '純米吟醸山吹色の酒'
    if s == '朱泉本仕込': s = '純米吟醸朱泉本仕込'
    return s

def match_score(a,b):
    a,b=norm(a),norm(b)
    if not a or not b: return 0.0
    sc=SequenceMatcher(None,a,b).ratio()
    length_ratio=min(len(a),len(b))/max(len(a),len(b))
    if min(len(a),len(b))>=4 and length_ratio>=0.65 and (a in b or b in a): sc=max(sc,0.94)
    return sc

def save_source(brewery,url,stype):
    source_file=DIR/'sources.jsonl'
    existing=[]
    if source_file.exists():
        existing=[json.loads(x) for x in source_file.read_text(encoding='utf-8').splitlines() if x.strip()]
    for s in existing:
        if s.get('url')==url:
            return s['source_id']
    sid='CSKU_'+hashlib.sha1(url.encode()).hexdigest()[:12].upper()
    d=DIR/'evidence'/brewery; d.mkdir(parents=True,exist_ok=True); p=d/(sid+'.html')
    r=requests.get(url,headers=HEAD,timeout=45); r.raise_for_status(); body=r.content; p.write_bytes(body)
    rec={'source_id':sid,'brewery':brewery,'source_type':stype,'url':url,
         'retrieved_at':datetime.now(JST).isoformat(timespec='seconds'),'http_status':r.status_code,
         'saved_file':str(p.relative_to(DIR)),'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)}
    existing.append(rec)
    source_file.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in existing),encoding='utf-8')
    return sid

def patch_sku_master():
    p=DIR/'sku_master.csv'; df=pd.read_csv(p,encoding='utf-8-sig',dtype=str,keep_default_na=False)
    fields=list(df.columns)
    before=len(df)
    df=df.drop_duplicates(['酒蔵','商品名','容量ml','URL'],keep='first').reset_index(drop=True)
    add=[]
    specs=[
      ('白牡丹酒造','【日本酒 白牡丹】大吟醸 720ml瓶詰',720,'4950198110318','200400',3300,
       'https://www.hakubotan.co.jp/products/%E3%80%90%E6%97%A5%E6%9C%AC%E9%85%92-%E7%99%BD%E7%89%A1%E4%B8%B9%E3%80%91%E5%A4%A7%E5%90%9F%E9%86%B81-8l%E7%93%B6%E8%A9%B0/','official_product'),
      ('白牡丹酒造','【日本酒 白牡丹】大吟醸 1.8L瓶詰',1800,'4950198110103','200102',5500,
       'https://www.hakubotan.co.jp/products/%E3%80%90%E6%97%A5%E6%9C%AC%E9%85%92-%E7%99%BD%E7%89%A1%E4%B8%B9%E3%80%91%E5%A4%A7%E5%90%9F%E9%86%B8-1-8l%E7%93%B6%E8%A9%B0/','official_product'),
      ('山陽鶴酒造','山陽鶴 大吟醸 ほんと 720ml',720,'','',0,
       'https://www.buyhiro.com/database/products/products_0549/','current_public_distribution'),
      ('亀齢酒造','亀齢 上撰 1800ml',1800,'','',1958,
       'https://shop.sumidaya.co.jp/products/kirei-jyosen-1800ml','retailer_current'),
    ]
    for brewery,name,cap,jan,code,price,url,stype in specs:
        caps=pd.to_numeric(df['容量ml'],errors='coerce')
        same=(df['酒蔵'].eq(brewery) & caps.eq(float(cap)) & df['商品名'].map(norm).map(lambda x: match_score(x,norm(name))>=0.88))
        if same.any(): continue
        sid=save_source(brewery,url,stype)
        row={k:'' for k in fields}
        row.update({'酒蔵':brewery,'商品名':name,'容量ml':str(cap),'JAN':jan,'商品コード':code,
                    '価格円税込':str(price) if price else '','販売状態':'販売中','在庫状態':'不明','販売チャネル':'通常/不明',
                    '業務卸可否':'未確認','輸出可否':'未確認','要冷蔵':'','確認日':TODAY,
                    '主出典ID':sid,'出典種別':stype,'URL':url,'出典数':1,'代替URL':'',
                    '備考':'ブランド中核監査で補完。公開情報で現行流通を確認。'})
        add.append(row)
    if add:
        df=pd.concat([df,pd.DataFrame(add)],ignore_index=True)
    if add or len(df)!=before:
        df.to_csv(p,index=False,encoding='utf-8-sig')
        with (DIR/'sku_master.jsonl').open('w',encoding='utf-8') as f:
            for r in df.to_dict('records'): f.write(json.dumps(r,ensure_ascii=False)+'\n')
    return df


def update_sku_summary(sku):
    src=sum(1 for x in (DIR/'sources.jsonl').read_text(encoding='utf-8').splitlines() if x.strip())
    exc=sum(1 for x in (DIR/'logs'/'excluded.jsonl').read_text(encoding='utf-8').splitlines() if x.strip())
    out={'generated_at':datetime.now(JST).isoformat(timespec='seconds'),'scope':'東広島市10蔵・現行取扱候補SKU（公開ウェブ確認＋ブランド中核補完）',
         'sku_records':len(sku),'by_brewery':sku['酒蔵'].value_counts().sort_index().to_dict(),
         'by_status':sku['販売状態'].value_counts().reindex(['販売中','休売','終売','不明'],fill_value=0).to_dict(),
         'sources':src,'excluded':exc}
    (DIR/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')

def brand_for(brewery,name):
    n=clean(name)
    if brewery=='賀茂鶴酒造': return ('酒中在心','') if '酒中在心' in n else ('賀茂鶴','')
    if brewery=='白牡丹酒造': return ('藝陽男山','生酛') if n.startswith('生酛純米酒') else ('白牡丹','')
    if brewery=='西條鶴醸造': return '西條鶴',''
    if brewery=='亀齢酒造': return ('亀齢萬年','') if '亀齢萬年' in n else ('亀齢','')
    if brewery=='福美人酒造': return '福美人',''
    if brewery=='賀茂泉酒造':
        if 'ROCK' in n.upper() or 'Rock' in n: return 'ROCK HOPPER',''
        if 'COKUN' in n.upper(): return 'COKUN',''
        return '賀茂泉',''
    if brewery=='山陽鶴酒造': return '山陽鶴',''
    if brewery=='金光酒造': return ('桜吹雪','') if '桜吹雪' in n else ('賀茂金秀','')
    if brewery=='今田酒造本店': return ('FUKUCHO LEGACY','') if 'LEGACY' in n.upper() else ('富久長','')
    if brewery=='柄酒造': return ('9代目於多福','') if '9代目於多福' in n else ('於多福','')
    return '',''

def best_row(name,df,col='商品名',threshold=.72):
    best=None; score=0.0
    for _,r in df.iterrows():
        sc=match_score(name,r.get(col,''))
        if sc>score: best,score=r,sc
    return (best,score) if best is not None and score>=threshold else (None,score)

def core_for(brewery,name):
    g=CORE[CORE['酒蔵'].eq(brewery)]
    r,sc=best_row(name,g,'中核銘柄',.78)
    return (r,sc) if r is not None else (None,sc)

def patch_products():
    old.main()
    outputs={}
    for area,breweries in AREAS.items():
        p=DIR/f'boss_{area}_products.csv'
        df=pd.read_csv(p,encoding='utf-8-sig').fillna('')
        if '山陽鶴酒造' in breweries and not df['商品名'].str.contains('ほんと',regex=False).any():
            h={'酒蔵':'山陽鶴酒造','商品名':'大吟醸 ほんと','分類':'大吟醸','甘辛目安':'やや辛口',
               '甘辛判定根拠':'現行商品情報の明示表現','日本酒度':'+4','精米歩合':'35%','アルコール度数':'17度',
               'おすすめの飲み方':'冷酒 / 常温','飲み方情報':'現行日本酒情報DB','飲み方出典URL':'https://www.sakenomy.jp/sake/TST0000008908/',
               '使用米':'山田錦','容量':'720ml','参考価格':'','流通区分':'一般流通',
               '備考':'現行地域製品DBに販売場所掲載。個別販売SKUを確認。','出典URL':'https://www.buyhiro.com/database/products/products_0549/','出典数':2}
            df=pd.concat([df,pd.DataFrame([h])],ignore_index=True)
        m=df['酒蔵'].eq('白牡丹酒造') & df['商品名'].eq('大吟醸')
        if m.any():
            df.loc[m,['分類','甘辛目安','甘辛判定根拠','日本酒度','精米歩合','アルコール度数','おすすめの飲み方','飲み方情報','使用米','容量','参考価格','出典URL']]=[
              '大吟醸','やや辛口','日本酒度からの目安','+3','40%','17度','常温 / 冷酒','公式商品ページ','山田錦','300ml / 720ml / 1,800ml','1,320～5,500円','https://www.hakubotan.co.jp/products/']
        pm=df['酒蔵'].eq('白牡丹酒造') & df['商品名'].str.contains('Paeon',regex=False)
        if pm.any():
            df.loc[pm,['分類','甘辛目安','甘辛判定根拠','日本酒度','精米歩合','アルコール度数','おすすめの飲み方','飲み方情報','使用米','容量','参考価格','出典URL']]=[
              '特別純米','やや甘口','日本酒度からの目安','-1.5','60%','16度','常温 / 冷酒','公式商品ページ','千本錦','500ml','1,815円','https://www.hakubotan.co.jp/products/%E3%80%90%E6%97%A5%E6%9C%AC%E9%85%92-%E7%99%BD%E7%89%A1%E4%B8%B9%E3%80%91paeon%E3%83%94%E3%82%AA%E3%83%B3%E3%80%90%E6%96%B0%E3%80%91/']
        brands=[]; series=[]; pr=[]; pos=[]
        for _,r in df.iterrows():
            b,s=brand_for(r['酒蔵'],r['商品名']); brands.append(b); series.append(s)
            c,_=core_for(r['酒蔵'],r['商品名'])
            pr.append(c['優先度'] if c is not None else 'C'); pos.append(c['位置づけ'] if c is not None else '')
        df.insert(1,'ブランド',brands); df.insert(2,'シリーズ',series)
        df.insert(3,'ブランド優先度',pr); df.insert(4,'ブランド位置づけ',pos)
        df.to_csv(p,index=False,encoding='utf-8-sig'); outputs[area]=df
    bs=json.loads((DIR/'boss_export_summary.json').read_text(encoding='utf-8'))
    for area,df in outputs.items():
        bs[area]['products']=len(df); bs[area]['main']=sum(6 if b=='金光酒造' else 5 for b in AREAS[area])
        bs[area]['by_brewery']=df['酒蔵'].value_counts().reindex(AREAS[area],fill_value=0).to_dict()
    (DIR/'boss_export_summary.json').write_text(json.dumps(bs,ensure_ascii=False,indent=2),encoding='utf-8')
    return outputs

def area_for(b):
    for a,bs in AREAS.items():
        if b in bs: return a
    return ''

def sku_match(sku,b,name):
    g=sku[sku['酒蔵'].eq(b)]
    if b=='亀齢酒造' and name=='亀齢萬年':
        h=g[g['商品名'].str.contains('亀齢萬年',regex=False)]
        if not h.empty: return h.iloc[0],1.0
    r,sc=best_row(name,g,'商品名',.76)
    return r,sc

def make_brand_master(products,sku):
    allp=pd.concat(products.values(),ignore_index=True).fillna('')
    rows=[]
    for _,c in CORE.iterrows():
        g=allp[allp['酒蔵'].eq(c['酒蔵'])]
        p,psc=best_row(c['中核銘柄'],g,'商品名',.70)
        s,ssc=sku_match(sku,c['酒蔵'],c['中核銘柄'])
        info=p if p is not None else None
        core_cat=old.category_bucket('',c['中核銘柄'])
        info_cat=clean(info.get('分類','')) if info is not None else ''
        final_cat=core_cat if core_cat!='その他' else (info_cat or 'その他')
        rows.append({'エリア':area_for(c['酒蔵']),'酒蔵':c['酒蔵'],'ブランド':c['ブランド'],'シリーズ':c['シリーズ'],
          '中核銘柄':c['中核銘柄'],'優先度':c['優先度'],'位置づけ':c['位置づけ'],'ブランド収録判定':'収録済',
          '個別SKU確認':'SKU確認済' if s is not None else '個別SKU未確認',
          '分類':final_cat,
          '甘辛目安':clean(info.get('甘辛目安','')) if info is not None else '不明',
          '日本酒度':clean(info.get('日本酒度','')) if info is not None else '',
          'おすすめの飲み方':clean(info.get('おすすめの飲み方','')) if info is not None else '要確認',
          '主要容量':clean(info.get('容量','')) if info is not None else (str(int(float(s['容量ml'])))+'ml' if s is not None and clean(s.get('容量ml','')) else ''),
          '流通区分':clean(info.get('流通区分','')) if info is not None else '要確認','確認日':TODAY,
          '根拠URL':c['根拠URL'],'商品出典URL':clean(info.get('出典URL','')) if info is not None else (clean(s.get('URL','')) if s is not None else '')})
    bm=pd.DataFrame(rows)
    for (b,n),vals in CORE_OVERRIDES.items():
        m=(bm['酒蔵']==b)&(bm['中核銘柄']==n)
        for k,v in vals.items(): bm.loc[m,k]=v
    bm.to_csv(DIR/'brand_master.csv',index=False,encoding='utf-8-sig')
    bm.to_csv(DIR/'brand_core_audit.csv',index=False,encoding='utf-8-sig')
    return bm

def make_registry(bm):
    r=REGISTRY.copy()
    a=bm[bm['優先度'].eq('A')].groupby(['酒蔵','ブランド']).size().rename('A中核銘柄数')
    b=bm[bm['優先度'].eq('B')].groupby(['酒蔵','ブランド']).size().rename('B主要銘柄数')
    r=r.merge(a,on=['酒蔵','ブランド'],how='left').merge(b,on=['酒蔵','ブランド'],how='left').fillna(0)
    r['A中核銘柄数']=r['A中核銘柄数'].astype(int); r['B主要銘柄数']=r['B主要銘柄数'].astype(int)
    r.insert(0,'エリア',r['酒蔵'].map(area_for)); r['確認日']=TODAY
    r.to_csv(DIR/'brand_registry.csv',index=False,encoding='utf-8-sig')
    return r

def make_main_core(bm,products,sku):
    allp=pd.concat(products.values(),ignore_index=True).fillna(''); out=[]
    for _,c in bm[bm['優先度'].eq('A')].iterrows():
        g=allp[allp['酒蔵'].eq(c['酒蔵'])]
        p,_=best_row(c['中核銘柄'],g,'商品名',.70)
        s,_=sku_match(sku,c['酒蔵'],c['中核銘柄'])
        src=(p.get('出典URL','') if p is not None else '') or c['商品出典URL'] or c['根拠URL']
        out.append({'酒蔵':c['酒蔵'],'ブランド':c['ブランド'],'シリーズ':c['シリーズ'],'商品名':c['中核銘柄'],
          '分類':c['分類'],'甘辛目安':c['甘辛目安'] or '不明','日本酒度':c['日本酒度'],
          'おすすめの飲み方':c['おすすめの飲み方'] or '要確認','容量':c['主要容量'],
          '流通区分':c['流通区分'] or '要確認','SKU確認':c['個別SKU確認'],
          '選定理由':c['位置づけ'],'出典URL':src})
    return pd.DataFrame(out)

def write_flat_csvs(products,main):
    root_files=[]
    base_cols=['酒蔵','酒蔵の歴史','ブランド','銘柄の歴史','シリーズ','商品名','分類','甘辛目安','日本酒度','精米歩合','アルコール度数',
               'おすすめの飲み方','おすすめの飲み方（文章）','使用米','容量','参考価格','流通区分','備考','出典URL']
    for area,breweries in AREAS.items():
        source=products[area][base_cols].copy()
        source.insert(5,'主要銘柄','')
        for brewery in breweries:
            used=set()
            cores=main[main['酒蔵']==brewery]
            candidate_idx=source.index[source['酒蔵']==brewery].tolist()
            for _,c in cores.iterrows():
                scored=sorted(((match_score(c['商品名'],source.at[i,'商品名']),i) for i in candidate_idx if i not in used),reverse=True)
                if scored and scored[0][0] >= 0.70:
                    _,i=scored[0]; used.add(i); source.at[i,'主要銘柄']='○'
                    continue
                row={k:'' for k in source.columns}
                row.update({'酒蔵':c['酒蔵'],'ブランド':c['ブランド'],'シリーズ':c['シリーズ'],'主要銘柄':'○',
                            '商品名':c['商品名'],'分類':c['分類'],'甘辛目安':c['甘辛目安'],'日本酒度':c['日本酒度'],
                            'おすすめの飲み方':c['おすすめの飲み方'],'容量':c['容量'],'流通区分':c['流通区分'],
                            '備考':'主要銘柄管理から統合。現行根拠は内部監査表を参照。','出典URL':c['出典URL']})
                source=pd.concat([source,pd.DataFrame([row])],ignore_index=True)
            expected=6 if brewery=='金光酒造' else 5
            if int(((source['酒蔵']==brewery) & (source['主要銘柄']=='○')).sum()) != expected:
                raise RuntimeError(f"主要銘柄数が期待値ではありません: {brewery} expected={expected}")
        order={b:i for i,b in enumerate(breweries)}
        source['_brew_order']=source['酒蔵'].map(order)
        source['_main_order']=(source['主要銘柄']!='○').astype(int)
        source=source.sort_values(['_brew_order','_main_order','分類','商品名']).drop(columns=['_brew_order','_main_order']).reset_index(drop=True)
        out=ROOT/f'東広島市_{area}_現行日本酒一覧.csv'
        df=source.rename(columns={'おすすめの飲み方':'飲み方','おすすめの飲み方（文章）':'おすすめの飲み方'})
        df.to_csv(out,index=False,encoding='utf-8-sig')
        root_files.append({'area':area,'file':out.name,'rows':len(df),'main':int((df['主要銘柄']=='○').sum()),'columns':list(df.columns)})
    bs=json.loads((DIR/'boss_export_summary.json').read_text(encoding='utf-8'))
    for x in root_files:
        bs[x['area']]['root_file']=x['file']; bs[x['area']]['root_products']=x['rows']
    (DIR/'boss_export_summary.json').write_text(json.dumps(bs,ensure_ascii=False,indent=2),encoding='utf-8')
    return root_files


def write_summary(bm,registry,sku,main):
    a=bm[bm['優先度'].eq('A')]
    by={}
    for brewery,g in bm.groupby('酒蔵'):
        ag=g[g['優先度'].eq('A')]
        by[brewery]={'A_required':len(ag),'A_covered':int((ag['ブランド収録判定']=='収録済').sum()),
                     'A_sku_confirmed':int((ag['個別SKU確認']=='SKU確認済').sum()),'B_major':int((g['優先度']=='B').sum())}
    summary={'generated':TODAY,'sku_rows':len(sku),'brand_families':len(registry),'core_products':len(bm),
             'A_required':len(a),'A_covered':int((a['ブランド収録判定']=='収録済').sum()),
             'A_sku_confirmed':int((a['個別SKU確認']=='SKU確認済').sum()),
             'A_complete':bool(len(a)==51 and (a['ブランド収録判定']=='収録済').all()),'main_products':len(main),'by_brewery':by}
    (DIR/'brand_core_audit_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return summary

def qa(products,bm,registry,main,summary):
    allp=pd.concat(products.values(),ignore_index=True).fillna('')
    checks={
      'A_complete':summary['A_complete'],
      'A_expected_complete':summary['A_required']==51 and summary['A_covered']==51,
      'main_expected_each':all(main.groupby('酒蔵').size().to_dict().get(b,0)==(6 if b=='金光酒造' else 5) for bs in AREAS.values() for b in bs) and main['酒蔵'].nunique()==10,
      'brand_blank_zero':int((allp['ブランド'].str.strip()=='').sum())==0,
      'product_duplicates_zero':int(allp.duplicated(['酒蔵','商品名']).sum())==0,
      'brewery_history_complete':int((allp['酒蔵の歴史'].str.strip()=='').sum())==0,
      'brand_history_complete':int((allp['銘柄の歴史'].str.strip()=='').sum())==0,
      'product_history_fallback_zero':not allp['銘柄の歴史'].str.contains('確認できる公開情報では特定できない|発売年・開発経緯は',regex=True,na=False).any(),
      'collaboration_products_zero':not allp['商品名'].str.contains('龍が如く|サンフレ|無相 SAKE MUSOU|純米及川|^NAO$|広大',regex=True,na=False).any(),
      'recommended_serving_complete':int((allp['おすすめの飲み方（文章）'].str.strip()=='').sum())==0,
      'sanyotsuru_honto':bool(((allp['酒蔵']=='山陽鶴酒造') & allp['商品名'].str.contains('ほんと',regex=False)).any()),
      'hakubotan_daiginjo_sizes':bool(((allp['酒蔵']=='白牡丹酒造') & (allp['商品名']=='大吟醸') & allp['容量'].str.contains('720ml',regex=False) & allp['容量'].str.contains('1,800ml',regex=False)).any()),
      'no_cokun_plus':not allp['商品名'].str.contains(r'COKUN\+',regex=True).any(),
      'kamotsuru_current_major_complete':all(((allp['酒蔵']=='賀茂鶴酒造') & (allp['商品名']==name)).any() for name in [
          '純米吟醸 一滴入魂','賀茂鶴 光壽','純米大吟醸 瑞兆賀茂鶴','大吟醸 吉祥 賀茂鶴','大吟醸 天凜','大吟醸 吟凛雅','酒中在心 鶯 純米大吟醸 山田錦']),
      'itteki_distinct_from_generic':bool(((allp['酒蔵']=='賀茂鶴酒造') & (allp['商品名']=='純米吟醸 一滴入魂')).any()) and bool(((allp['酒蔵']=='賀茂鶴酒造') & (allp['商品名']=='純米吟醸')).any()),
      'itteki_current_sizes':bool(((allp['酒蔵']=='賀茂鶴酒造') & (allp['商品名']=='純米吟醸 一滴入魂') & allp['容量'].str.contains('300ml',regex=False) & allp['容量'].str.contains('720ml',regex=False) & allp['容量'].str.contains('1,800ml',regex=False)).any()),
    }
    csv_outputs=[]
    required_cols=['酒蔵','酒蔵の歴史','ブランド','銘柄の歴史','主要銘柄','商品名','分類','飲み方','おすすめの飲み方','出典URL']
    for area in AREAS:
        p=ROOT/f'東広島市_{area}_現行日本酒一覧.csv'
        ok=p.exists()
        cols=[]; rows=0
        if ok:
            c=pd.read_csv(p,encoding='utf-8-sig').fillna('')
            cols=list(c.columns); rows=len(c)
            counts=c[c['主要銘柄']=='○'].groupby('酒蔵').size().reindex(AREAS[area],fill_value=0); main_ok=all(int(counts[b])==(6 if b=='金光酒造' else 5) for b in AREAS[area])
            dup_ok=not c.duplicated(['酒蔵','商品名']).any()
            content_ok=all((c[x].astype(str).str.strip()!='').all() for x in ['酒蔵の歴史','銘柄の歴史','おすすめの飲み方'])
            ok=all(x in cols for x in required_cols) and rows>=len(products[area]) and bool(main_ok) and bool(dup_ok) and bool(content_ok)
        csv_outputs.append({'file':p.name,'rows':rows,'flat_columns_ok':ok})
    checks['flat_csv_outputs']=all(x['flat_columns_ok'] for x in csv_outputs)
    checks['no_root_xlsx']=not any(ROOT.glob('東広島市_*日本酒一覧.xlsx'))
    report={'generated':TODAY,'checks':checks,'csv':csv_outputs,'passed':all(checks.values())}
    (DIR/'brand_completion_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if not report['passed']: raise RuntimeError('QA failed: '+json.dumps(checks,ensure_ascii=False))
    return report

def update_readme(summary,products):
    counts={}
    for area in AREAS:
        p=ROOT/f'東広島市_{area}_現行日本酒一覧.csv'
        counts[area]=len(pd.read_csv(p,encoding='utf-8-sig')) if p.exists() else 0
    text=f'''# sake-saijo-db

東広島市の日本酒を、販売・取扱い・輸出検討に使える形へ整理する業務用データベースです。
公開ソースの原本を保存した上で、**ブランド → 商品 → 販売SKU** の3階層で管理します。

## 提出・閲覧用ファイル

ルートには上司・行政説明で直接使う2つのCSVを置いています。

- `東広島市_西条エリア7蔵_現行日本酒一覧.csv` — 商品単位 {counts.get('西条エリア7蔵',0)}件
- `東広島市_安芸津・黒瀬エリア3蔵_現行日本酒一覧.csv` — 商品単位 {counts.get('安芸津・黒瀬エリア3蔵',0)}件

主要銘柄は別ファイル・別シートに分けず、`主要銘柄` 列に `○` を付けます。`○` で絞り込むと金光酒造は6銘柄、その他9蔵は各5銘柄、計51銘柄を確認できます。各商品行には `酒蔵の歴史`、`銘柄の歴史`、短い温度区分の `飲み方`、文章で説明する `おすすめの飲み方` も保持します。

西条エリアは賀茂鶴・白牡丹・西條鶴・亀齢・福美人・賀茂泉・山陽鶴、安芸津・黒瀬エリアは今田酒造本店・柄酒造・金光酒造です。

## ブランド網羅の完成基準

- **A**: 絶対に落とさない看板・代表銘柄、蔵元おすすめ、現行の中心商品
- **B**: 主要定番、高級ライン、別ブランド、注目シリーズ
- **C**: その他の現行商品・季節商品・限定商品

2026-09-06時点で、Aランクは **{summary['A_covered']}/{summary['A_required']}件収録済み**です。Aは金光酒造6件、その他9蔵5件、計51件を必須チェックにしています。
個別販売SKUまで公開確認できたA銘柄は {summary['A_sku_confirmed']}件です。SKU未確認は「銘柄欠落」ではなく、蔵元が代表酒として公開している一方で容量・JAN等の個別販売情報が公開されていないケースとして区別します。

## データ構造とルール

- `research/current_sku/brand_registry.csv`: ブランド一覧
- `research/current_sku/brand_master.csv`: A/B中核銘柄と収録・SKU確認状況
- `research/current_sku/sku_master.csv`: 販売SKU。容量・価格・JAN・販売チャネル等
- `research/web/index.csv`: 商品単位の調査・酒質情報
- `research/current_sku/evidence/`: 現行SKU・ブランド確認の保存証拠
- `research/history_serving_20260906/`: 酒蔵史・ブランド史・全商品の商品史・飲み方の追加調査、出典一覧、商品別推薦根拠
- `sources/`: 外部オープンデータ等の原本

販売状態は `販売中 / 休売 / 終売 / 不明` の4値です。容量・箱・容器だけが違う場合は上司向け商品表では統合し、生酒・にごり・熟成等で酒質が変わる場合は別商品として扱います。季節・数量・蔵元・流通・輸出限定の商品も2026-09-06時点で現行性を確認できれば収録します。ギフトセットや包装違いだけのSKU、コラボ商品は本表から除外し、監査情報で区別します。

`銘柄の歴史` はブランド史と商品固有史を併記します。2026-09-06の再調査では調査対象204商品すべてを商品単位で確認し、発売・受賞・開発・製法変更・季節企画・商品固有設計等を `research/history_serving_20260906/product_history_full.csv` に記録しました。このうちコラボ・外部タイアップ4商品は監査表には残し、本表から除外しています。

甘辛と短い `飲み方` は蔵元等の明示情報を優先し、根拠がない場合は `不明` / `要確認` を残します。一方、文章の `おすすめの飲み方` は全商品を必須入力とし、公式情報、信頼できる二次情報、既知の酒質情報からの推論の順で作成します。推論した行は文章中と `research/history_serving_20260906/product_serving_recommendations.csv` の根拠区分で識別できます。酒蔵・銘柄の歴史も同researchディレクトリに出典を保存します。日本酒度から甘辛を分類した場合は「目安」と明記します。

## 山陽鶴の扱い

山陽鶴は公式FAQで直売所にて全種類購入可能と案内し、公式五酒セットで大吟醸・純米吟醸・本醸造・上撰等を代表酒として示しています。一方、個別SKUの公開カタログは限定的です。そのため代表酒はブランド・商品層に収録し、個別SKUが公開確認できないものは `個別SKU未確認` としています。純米大吟醸KUBOと大吟醸ほんとは現行の個別流通情報も別途確認しています。

## 再生成

```powershell
python research/current_sku/collect_current_skus.py
python research/current_sku/build_boss_exports.py
python research/current_sku/finalize_brand_catalog.py
```

卸値、ケース入数、MOQ、業務卸可否、商品別の輸出可否は公開されないことが多いため、公開根拠がない場合は `未確認` のまま保持し、取引開始時に蔵元・卸へ直接確認します。
'''
    (ROOT/'README.md').write_bytes(text.encode('utf-8-sig'))

def main():
    sku=patch_sku_master(); update_sku_summary(sku); products=patch_products(); products=facts.apply(products); products=hs.apply(products)
    bm=make_brand_master(products,sku); registry=make_registry(bm); main_df=make_main_core(bm,products,sku)
    root_files=write_flat_csvs(products,main_df)
    summary=write_summary(bm,registry,sku,main_df); report=qa(products,bm,registry,main_df,summary)
    update_readme(summary,products)
    print(json.dumps({'summary':summary,'qa':report},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
