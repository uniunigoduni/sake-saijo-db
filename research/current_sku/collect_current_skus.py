from __future__ import annotations
import csv, hashlib, json, re, time, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import requests
from lxml import html

ROOT=Path(r'C:\Users\tarou\Downloads\sake-saijo-db\research\current_sku')
EVID=ROOT/'evidence'; LOG=ROOT/'logs'
EVID.mkdir(parents=True,exist_ok=True); LOG.mkdir(parents=True,exist_ok=True)
HEAD={'User-Agent':'Mozilla/5.0 sake-saijo-db-current-sku/0.1'}
rows=[]; sources=[]; excluded=[]

def now(): return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
def compact(s): return ' '.join((s or '').split())
def sid_for(url): return 'CSKU_'+hashlib.sha1(url.encode()).hexdigest()[:12].upper()
def fetch(brewery,url,stype='official_product'):
    sid=sid_for(url); d=EVID/brewery; d.mkdir(parents=True,exist_ok=True)
    ext='.json' if 'products.json' in url else '.html'; p=d/(sid+ext)
    if p.exists(): body=p.read_bytes(); status='cached'
    else:
        r=requests.get(url,headers=HEAD,timeout=45); r.raise_for_status(); body=r.content; p.write_bytes(body); status=r.status_code; time.sleep(.08)
    sources.append({'source_id':sid,'brewery':brewery,'source_type':stype,'url':url,'retrieved_at':now(),'http_status':status,'saved_file':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)})
    return sid,body,p
def text_of(body):
    try: return compact(html.fromstring(body).text_content())
    except Exception: return body.decode('utf-8','replace')
def title_of(body,fallback=''):
    try:
        d=html.fromstring(body)
        vals=[compact(d.xpath('string(//h1)')),compact(d.xpath('string(//h2)')),compact(d.xpath('string(//title)'))]
        return next((x for x in vals if x),fallback)
    except Exception: return fallback
def ec_title_of(body,fallback=''):
    try:
        d=html.fromstring(body)
        og=compact(d.xpath('string(//meta[@property="og:title"]/@content)'))
        ttl=compact(d.xpath('string(//title)'))
        for v in [og,ttl]:
            if not v: continue
            if '福美人酒造株式会社' in v and fallback: continue
            v=re.split(r'\s[-|｜]\s',v,maxsplit=1)[0].strip()
            if v and v not in ['ランキング','商品一覧']: return v
    except Exception:
        pass
    return fallback

def capacity_ml(s):
    s=unicodedata.normalize('NFKC',s or '')
    m=re.search(r'(?<!\d)(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(ml|mL|ML|L|l)(?![A-Za-z])',s)
    if not m: return ''
    v=float(m.group(1).replace(',',''))
    return int(round(v*1000)) if m.group(2).lower()=='l' else int(round(v))
def price_yen(s):
    pats=[r'(?:価格[:：]?\s*)?[¥￥]\s*([\d,]+)',r'([\d,]+)円\s*\(税込\)',r'([\d,]+)円\(税']
    for pat in pats:
        m=re.search(pat,s or '')
        if m:
            try:return int(m.group(1).replace(',',''))
            except:return ''
    return ''
def jan_code(s):
    for pat in [r'JAN(?:コード)?\s*[:：]?\s*(\d{8,14})',r'JAN[- ]?CODE\s*[:：]?\s*(\d{8,14})']:
        m=re.search(pat,s or '',re.I)
        if m:return m.group(1)
    m=re.search(r'(?<!\d)(4[59]\d{11})(?!\d)',s or '')
    return m.group(1) if m else ''
def channel_from(name,text=''):
    s=(name or '')
    for token,label in [('輸出限定','輸出限定'),('アメリカ限定','海外限定'),('取扱い店限定','取扱店限定'),('流通限定','流通限定'),('蔵元限定','蔵元限定'),('酒蔵限定','酒蔵限定'),('ネットショップ限定','EC限定'),('オンラインショップ限定','EC限定'),('季節限定','季節限定'),('数量限定','数量限定')]:
        if token in s:return label
    return '通常/不明'
def stock_from(s):
    if re.search(r'在庫\s*[:：]?\s*[○◎]|在庫あり|販売中|発売中',s or ''): return '在庫あり'
    if re.search(r'SOLD\s*OUT|品切れ|売り切れ|在庫なし',s or '',re.I): return '売切'
    return '不明'
def is_sake_name(name,text=''):
    # 商品ページ全体には梅酒・酒粕・グッズ等の共通ナビが入るため、除外語は商品名だけで判定する。
    n=name or ''; s=n+' '+(text or '')
    bad=['梅酒','リキュール','甘酒','酒粕','食品','グッズ','手提','木枡','前掛け','ボディーソープ','シャンプー','エッセンス','石けん','入浴','カレー']
    if any(x in n for x in bad): return False,'非清酒'
    if 'COKUN+' in n or 'COKUN＋' in n: return False,'その他の醸造酒'
    if any(x in n for x in ['セット','飲み比べ','のみくらべ','アソート','詰合','詰め合わせ']): return False,'セット商品'
    good=['日本酒','清酒','純米','吟醸','大吟醸','本醸造','普通酒','生酒','原酒','にごり','上撰','大吟峰','賀茂鶴','西條鶴','亀齢','賀茂金秀','桜吹雪','於多福','富久長','FUKUCHO','Fukucho','八反草','海風土','秋櫻','美穂','山吹色の酒','朱泉','緑泉','造賀','Rock Hopper','RockHopper','NAO','COKUN','延寿','皇寿','壽']
    return (True,'') if any(x in n for x in good) else (False,'清酒判定不能')
def add_row(brewery,name,url,sid,text='',status='販売中',stock='不明',price='',cap='',jan='',sku='',source_type='official',note=''):
    ok,reason=is_sake_name(name,text)
    if not ok:
        excluded.append({'brewery':brewery,'product_name':name,'reason':reason,'source_url':url}); return
    rows.append({'酒蔵':brewery,'商品名':compact(name),'容量ml':cap or capacity_ml(name+' '+text),'JAN':jan or jan_code(text),'商品コード':sku,'価格円税込':price or price_yen(text),'販売状態':status,'在庫状態':stock,'販売チャネル':channel_from(name,text),'業務卸可否':'未確認','輸出可否':'未確認','要冷蔵':'要冷蔵' if '要冷蔵' in text or '生酒' in name else '不明','確認日':now()[:10],'主出典ID':sid,'出典種別':source_type,'URL':url,'備考':note})
def nearest_text(a,limit=700):
    n=a
    for _ in range(5):
        n=n.getparent()
        if n is None: break
        t=compact(n.text_content())
        if len(t)<=limit:return t
    return ''
def crawl_colorme(brewery,base,max_pages=10,stype='official_ec'):
    found={}
    for page in range(1,max_pages+1):
        u=f'{base}/?mode=srh&keyword=&page={page}'
        try: sid,body,_=fetch(brewery,u,'official_shop_catalog')
        except Exception as e: print('catalog error',brewery,page,repr(e)); break
        d=html.fromstring(body); before=len(found)
        for a in d.xpath('//a[contains(@href,"pid=")]'):
            href=urljoin(u,a.get('href') or ''); txt=compact(a.text_content())
            if not txt: continue
            card=nearest_text(a); found[href]=(txt,card)
        if len(found)==before: break
    for url,(fallback,card) in found.items():
        try:
            sid,body,_=fetch(brewery,url,'official_shop_product'); text=text_of(body); name=ec_title_of(body,fallback)
            name=re.sub(r'\s*[-|｜]\s*[^-|｜]{0,40}$','',name) if len(name)>100 else name
            stock=stock_from(card+' '+text); status='不明' if stock=='売切' else '販売中'
            add_row(brewery,name,url,sid,text,status,stock,price=price_yen(card) or price_yen(text),source_type=stype,note='公式EC掲載')
        except Exception as e: print('product error',brewery,url,repr(e))
    print('colorme',brewery,len(found))
def crawl_shopserve_search(brewery,url,stype='official_ec'):
    sid,body,_=fetch(brewery,url,'official_shop_catalog'); d=html.fromstring(body); found={}
    for a in d.xpath('//a[@href]'):
        href=urljoin(url,a.get('href') or ''); txt=compact(a.text_content())
        if re.search(r'/SHOP/[^/]+\.html(?:\?|$)',href) and txt:
            found[href]=(txt,nearest_text(a))
    for pu,(fallback,card) in found.items():
        try:
            psid,pbody,_=fetch(brewery,pu,'official_shop_product'); text=text_of(pbody); name=fallback
            stock=stock_from(card+' '+text); status='不明' if stock=='売切' else '販売中'
            add_row(brewery,name,pu,psid,text,status,stock,price=price_yen(card) or price_yen(text),source_type=stype,note='公式EC掲載')
        except Exception as e: print('shopserve product error',brewery,pu,repr(e))
    print('shopserve',brewery,len(found))

def crawl_fukubijin():
    brewery='福美人酒造'; pages=[
      'https://www.fukubijin.co.jp/SHOP/g23585/list.html','https://www.fukubijin.co.jp/SHOP/g23586/list.html',
      'https://www.fukubijin.co.jp/SHOP/g23587/list.html','https://www.fukubijin.co.jp/SHOP/g23588/list.html','https://www.fukubijin.co.jp/product.html']
    found={}
    for u in pages:
        sid,body,_=fetch(brewery,u,'official_shop_catalog'); d=html.fromstring(body)
        for a in d.xpath('//a[@href]'):
            href=urljoin(u,a.get('href') or ''); txt=compact(a.text_content())
            if re.search(r'/SHOP/[^/]+\.html(?:\?|$)',href) and txt: found[href]=(txt,nearest_text(a))
    for pu,(fallback,card) in found.items():
        psid,pbody,_=fetch(brewery,pu,'official_shop_product'); text=text_of(pbody); name=fallback; stock=stock_from(card+' '+text)
        add_row(brewery,name,pu,psid,text,'不明' if stock=='売切' else '販売中',stock,price=price_yen(card) or price_yen(text),source_type='official_ec',note='公式EC掲載')
    print('fukubijin',len(found))
def crawl_shopify(brewery,base,product_type):
    api=base.rstrip('/')+'/products.json?limit=250'; sid,body,_=fetch(brewery,api,'official_shop_api')
    data=json.loads(body.decode('utf-8')); count=0
    for p in data.get('products',[]):
        if p.get('product_type')!=product_type: continue
        page=base.rstrip('/')+'/products/'+p.get('handle',''); psid,pbody,_=fetch(brewery,page,'official_shop_product'); text=text_of(pbody)
        pname=compact(p.get('title','')); tags=' '.join(p.get('tags',[]) if isinstance(p.get('tags'),list) else [str(p.get('tags',''))])
        for v in p.get('variants',[]):
            vtitle=compact(v.get('title',''))
            name=pname if vtitle in ('','Default Title') else f'{pname} {vtitle}'
            cap=capacity_ml(name+' '+str(v.get('option1',''))); avail=bool(v.get('available')); stock='在庫あり' if avail else '売切'
            note='公式Shopify商品APIで販売可能' if avail else '公式Shopify掲載だが当該バリアント在庫なし'
            if 'アメリカ限定' in tags: note+=' / アメリカ限定'
            add_row(brewery,name,page,psid,text,'販売中' if avail else '不明',stock,price=int(float(v.get('price') or 0)) if v.get('price') else '',cap=cap,jan=str(v.get('barcode') or ''),sku=str(v.get('sku') or ''),source_type='official_ec_api',note=note)
            if rows and rows[-1].get('URL')==page:
                if 'アメリカ限定' in tags: rows[-1]['販売チャネル']='海外限定'
                elif '季節限定' in tags: rows[-1]['販売チャネル']='季節限定'
            count+=1
    print('shopify',brewery,count)

def add_manual_current(brewery,name,url,cap='',price='',channel='通常/不明',note='',source_type='official'):
    sid,body,_=fetch(brewery,url,source_type); text=text_of(body); add_row(brewery,name,url,sid,text,'販売中','不明',price=price,cap=cap,source_type=source_type,note=note)
    if rows and rows[-1]['URL']==url: rows[-1]['販売チャネル']=channel
def crawl_hakubotan_official_catalog():
    brewery='白牡丹酒造'; found={}
    for page in range(1,8):
        u='https://www.hakubotan.co.jp/products/' + ('' if page==1 else f'page/{page}/')
        sid,body,_=fetch(brewery,u,'official_product_catalog'); d=html.fromstring(body)
        for a in d.xpath('//a[@href]'):
            href=urljoin(u,a.get('href') or ''); txt=compact(a.text_content())
            if '/products/' in href and '/page/' not in href and txt and href.rstrip('/')!=u.rstrip('/'):
                found[href]=(txt,nearest_text(a,1200))
    for pu,(fallback,card) in found.items():
        try:
            sid,body,_=fetch(brewery,pu,'official_product_catalog_detail'); text=text_of(body); name=title_of(body,fallback)
            special=next((label for token,label in [('輸出専用','輸出限定'),('輸出限定','輸出限定'),('流通限定','流通限定'),('ネットショップ限定','EC限定'),('蔵元限定','蔵元限定'),('季節限定','季節限定'),('数量限定','数量限定')] if token in (name+' '+card+' '+text)), '通常/不明')
            if special not in ('輸出限定','流通限定','EC限定','季節限定','数量限定'): continue
            stock=stock_from(text); status='販売中' if stock=='在庫あり' else '不明'
            add_row(brewery,name,pu,sid,text,status,stock,source_type='official_catalog',note='公式商品カタログの限定区分')
            if rows and rows[-1]['URL']==pu: rows[-1]['販売チャネル']=special
        except Exception as e: print('hakubotan catalog detail',pu,repr(e))
    print('hakubotan official catalog',len(found))

def crawl_retailer_category(brewery,url,name_tokens):
    sid,body,_=fetch(brewery,url,'current_retailer_catalog'); d=html.fromstring(body); found={}
    for a in d.xpath('//a[@href]'):
        href=urljoin(url,a.get('href') or ''); txt=compact(a.text_content())
        if '/product/' in href and txt and any(t in txt for t in name_tokens): found[href]=(txt,nearest_text(a,900))
    for pu,(fallback,card) in found.items():
        try:
            psid,pbody,_=fetch(brewery,pu,'current_retailer_product'); text=text_of(pbody); name=ec_title_of(pbody,fallback)
            stock=stock_from(card+' '+text); status='販売中' if stock=='在庫あり' else '不明'
            add_row(brewery,name,pu,psid,text,status,stock,source_type='retailer_current',note='現行酒販店ECで流通確認。蔵元の業務卸可否は未確認')
        except Exception as e: print('retailer error',brewery,pu,repr(e))
    print('retailer',brewery,len(found))
def collect_kanemitsu():
    brewery='金光酒造'; reg='https://www.kamokin.com/line_up/regular.html'; sid,body,_=fetch(brewery,reg,'official_regular_lineup'); text=text_of(body)
    regular=[('賀茂金秀 純米大吟醸35',720,6930),('賀茂金秀 純米大吟醸35',1800,11000),('賀茂金秀 純米大吟醸40',720,3300),('賀茂金秀 純米大吟醸40',1800,6160),('賀茂金秀 純米吟醸 雄町',720,2200),('賀茂金秀 純米吟醸 雄町',1800,3960),('賀茂金秀 特別純米',720,1870),('賀茂金秀 特別純米',1800,3388),('賀茂金秀 特別純米 辛口',720,1870),('賀茂金秀 特別純米 辛口',1800,3388),('賀茂金秀 特別純米13',720,1925),('賀茂金秀 特別純米13',1800,3465)]
    for name,cap,price in regular: add_row(brewery,f'{name} {cap}ml',reg,sid,text,'販売中','不明',price=price,cap=cap,source_type='official_regular',note='公式で年間を通して販売と明記')
    lim='https://www.kamokin.com/line_up/Limited/limited.html'; lsid,lbody,_=fetch(brewery,lim,'official_limited_lineup'); ltext=text_of(lbody)
    limited=[('賀茂金秀 純米吟醸 愛山',720,2420,'10月中旬'),('賀茂金秀 純米吟醸 愛山',1800,4565,'10月中旬'),('賀茂金秀 SUITOH',720,2090,'1月中旬'),('賀茂金秀 SUITOH',1800,3740,'1月中旬'),('賀茂金秀 麗酸 雄町60',720,2035,'7月下旬'),('賀茂金秀 純米しぼりたて生',720,1843,'11月下旬'),('賀茂金秀 純米しぼりたて生',1800,3245,'11月下旬'),('桜吹雪 特別純米うすにごり生',720,2035,'2月中旬'),('桜吹雪 特別純米うすにごり生',1800,3630,'2月中旬'),('賀茂金秀 辛口夏純',720,1870,'5月中旬'),('賀茂金秀 辛口夏純',1800,3300,'5月中旬'),('賀茂金秀 特別純米秋あがり',720,1958,'9月上旬'),('賀茂金秀 特別純米秋あがり',1800,3476,'9月上旬'),('賀茂金秀 純米 お燗酒',1800,2948,'10月中旬')]
    for name,cap,price,start in limited: add_row(brewery,f'{name} {cap}ml',lim,lsid,ltext,'不明','不明',price=price,cap=cap,source_type='official_limited',note=f'公式限定商品。販売開始時期 {start}、現在在庫は未確認')
    print('kanemitsu',len(regular)+len(limited))
def collect_sanyotsuru_current():
    brewery='山陽鶴酒造'
    # 公開ウェブで個別SKUを現行確認できる高確度例。通年申込可・提供元が蔵元。
    u='https://www.furusato.aeon.co.jp/gift-in-return/aaa72316281ae6d75280fb28cb3cae46/'
    try:
        sid,body,_=fetch(brewery,u,'current_public_distribution'); text=text_of(body)
        add_row(brewery,'純米大吟醸 KUBO 720ml',u,sid,text,'販売中','不明',cap=720,source_type='current_public_distribution',note='ふるさと納税で通年申込可・提供元 山陽鶴酒造。一般卸可否は未確認')
    except Exception as e: print('sanyotsuru KUBO',repr(e))
    # 公式の現行セットは別商品として証拠保存。個別瓶販売とはみなさない。
    try: fetch(brewery,'https://sanyotsuru.jp/archives/product/gosyu','official_current_bundle')
    except Exception as e: print('sanyotsuru bundle',repr(e))

def collect_context_sources():
    for brewery,url,stype in [
      ('今田酒造本店','https://fukucho.jp/pages/stockist','official_stockists'),
      ('今田酒造本店','https://fukucho.jp/collections/asia','official_export_catalog'),
      ('山陽鶴酒造','https://sanyotsuru.jp/archives/faq','official_direct_sales'),
      ('山陽鶴酒造','https://sanyotsuru.jp/archives/product/gosyu','official_current_product'),
      ('亀齢酒造','https://kireikireikirei.jimdofree.com/','official_direct_sales')]:
        try: fetch(brewery,url,stype)
        except Exception as e: print('context error',brewery,url,repr(e))

def normalize_core(name):
    s=compact(name).replace('ｍｌ','ml').replace('ＭＬ','ml')
    s=re.sub(r'(?<!\d)\d+(?:\.\d+)?\s*(?:ml|mL|ML|L|l|Ｌ)(?![A-Za-z])','',s)
    s=re.sub(r'[【\[].*?(?:限定|日本酒).*?[】\]]','',s)
    s=re.sub(r'\s+',' ',s).strip(' -｜|')
    return s.casefold()
def dedupe():
    merged={}; rank={'販売中':3,'休売':2,'不明':1,'終売':0}; srank={'official_ec_api':5,'official_ec':4,'official_regular':4,'official_catalog':3,'retailer_current':2}
    for r in rows:
        key=(r['酒蔵'],normalize_core(r['商品名']),r['容量ml'])
        if key not in merged: merged[key]=dict(r); merged[key]['代替URL']=[]; merged[key]['出典数']=1; continue
        m=merged[key]; m['出典数']+=1; m['代替URL'].append(r['URL'])
        if rank.get(r['販売状態'],0)>rank.get(m['販売状態'],0): m['販売状態']=r['販売状態']
        if m['在庫状態']=='不明' and r['在庫状態']!='不明': m['在庫状態']=r['在庫状態']
        if srank.get(r['出典種別'],0)>srank.get(m['出典種別'],0):
            for f in ['主出典ID','出典種別','URL','備考']:
                m[f]=r[f]
        for f in ['JAN','商品コード','価格円税込']:
            if not m.get(f) and r.get(f): m[f]=r[f]
        chans=set((m['販売チャネル']+'|'+r['販売チャネル']).split('|')); m['販売チャネル']='|'.join(sorted(x for x in chans if x))
    return list(merged.values())
def write_outputs(final):
    fields=['酒蔵','商品名','容量ml','JAN','商品コード','価格円税込','販売状態','在庫状態','販売チャネル','業務卸可否','輸出可否','要冷蔵','確認日','主出典ID','出典種別','URL','出典数','代替URL','備考']
    with (ROOT/'sku_master.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in sorted(final,key=lambda x:(x['酒蔵'],x['商品名'],str(x['容量ml']))):
            z=dict(r); z['代替URL']=' | '.join(z.get('代替URL',[])); w.writerow({k:z.get(k,'') for k in fields})
    (ROOT/'sku_master.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in final),encoding='utf-8')
    uniq={s['source_id']:s for s in sources}; (ROOT/'sources.jsonl').write_text(''.join(json.dumps(s,ensure_ascii=False)+'\n' for s in uniq.values()),encoding='utf-8')
    (LOG/'excluded.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in excluded),encoding='utf-8')
    by={b:sum(1 for r in final if r['酒蔵']==b) for b in sorted({r['酒蔵'] for r in final})}; st={s:sum(1 for r in final if r['販売状態']==s) for s in ['販売中','休売','終売','不明']}
    summary={'generated_at':now(),'scope':'東広島市10蔵・現行取扱候補SKU（公開ウェブ確認）','sku_records':len(final),'by_brewery':by,'by_status':st,'sources':len(uniq),'excluded':len(excluded)}
    (ROOT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(summary,ensure_ascii=True))

def main():
    crawl_shopserve_search('賀茂鶴酒造','https://shop.kamotsuru.jp/SHOP/list.php?Search=1')
    crawl_colorme('白牡丹酒造','https://hakubotan.shop-pro.jp',6); crawl_hakubotan_official_catalog()
    crawl_colorme('西條鶴醸造','https://saijotsuru.co.jp',6)
    crawl_colorme('賀茂泉酒造','https://online.kamoizumi.com',8)
    crawl_fukubijin(); crawl_shopify('今田酒造本店','https://fukucho.jp','日本酒'); crawl_shopify('柄酒造','https://www.tsukasyuzou.jp','酒類')
    collect_kanemitsu()
    for b,u,toks in [
      ('賀茂鶴酒造','https://www.hiroshimasake.com/product-list/4',('賀茂鶴','ゴールド賀茂鶴')),
      ('賀茂泉酒造','https://www.hiroshimasake.com/product-list/5',('賀茂泉','ROCK HOPPER')),
      ('亀齢酒造','https://www.hiroshimasake.com/product-list/6',('亀齢','萬年')),
      ('西條鶴醸造','https://www.hiroshimasake.com/product-list/11',('西條鶴','神髄')),
      ('福美人酒造','https://www.hiroshimasake.com/product-list/16',('福美人',)),
      ('金光酒造','https://www.hiroshimasake.com/product-list/19',('金光酒造','桜吹雪'))]:
        crawl_retailer_category(b,u,toks)
    collect_sanyotsuru_current(); collect_context_sources(); final=dedupe()
    for r in final:
        if r['販売チャネル']=='海外限定' or '輸出限定' in r['販売チャネル']: r['輸出可否']='確認済み'
    write_outputs(final)
if __name__=='__main__': main()