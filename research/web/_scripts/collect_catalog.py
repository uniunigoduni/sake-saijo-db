from __future__ import annotations
import csv, hashlib, json, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import requests
from lxml import html

ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "sources.jsonl"
USER_AGENT = "sake-saijo-db web-research/0.1"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})
CHECKED = "2026-09-05"

BREWERY_CODES = {
    "賀茂鶴酒造":"KAMOTSURU", "白牡丹酒造":"HAKUBOTAN", "西條鶴醸造":"SAIJOTSURU",
    "亀齢酒造":"KIREI", "福美人酒造":"FUKUBIJIN", "賀茂泉酒造":"KAMOIZUMI", "山陽鶴酒造":"SANYOTSURU",
}
records: dict[tuple[str,str], dict] = {}
sources: dict[str, dict] = {}
def now_iso():
    return datetime.now(timezone.utc).isoformat()

def source_id(url: str) -> str:
    return "SRC_" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:12].upper()

def clean_filename(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]+', '_', s).strip().rstrip('.')
    return s[:120] or "unnamed"

def save_source(brewery: str, url: str, source_type="official"):
    sid = source_id(url)
    if sid in sources:
        return sid, sources[sid].get("text", "")
    folder = ROOT / brewery / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    cached = next((x for x in [folder / f"{sid}.html", folder / f"{sid}.pdf"] if x.exists() and x.stat().st_size > 0), None)
    if cached is not None:
        data = cached.read_bytes()
        text = ""
        if cached.suffix.lower() == ".html":
            try: text = " ".join(html.fromstring(data).text_content().split())
            except Exception: text = data.decode("utf-8", errors="ignore")
        row = {"source_id":sid,"brewery":brewery,"url":url,"final_url":url,"source_type":source_type,
               "retrieved_at":datetime.fromtimestamp(cached.stat().st_mtime, timezone.utc).isoformat(),
               "http_status":"cached","content_type":"text/html" if cached.suffix.lower()==".html" else "application/pdf",
               "saved_file":str(cached.relative_to(ROOT)).replace('\\','/'),"sha256":hashlib.sha256(data).hexdigest(),
               "bytes":len(data),"text":text}
        sources[sid]=row
        return sid,text
    r = SESSION.get(url, timeout=(15, 60), allow_redirects=True)
    data = r.content
    ctype = r.headers.get("content-type", "")
    ext = ".pdf" if "pdf" in ctype or r.url.lower().endswith(".pdf") else ".html"
    folder = ROOT / brewery / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sid}{ext}"
    path.write_bytes(data)
    text = ""
    if ext == ".html":
        try:
            doc = html.fromstring(data)
            text = " ".join(doc.text_content().split())
        except Exception:
            text = data.decode("utf-8", errors="ignore")
    row = {
        "source_id": sid, "brewery": brewery, "url": url, "final_url": r.url,
        "source_type": source_type, "retrieved_at": now_iso(), "http_status": r.status_code,
        "content_type": ctype, "saved_file": str(path.relative_to(ROOT)).replace('\\','/'),
        "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "text": text,
    }
    sources[sid] = row
    return sid, text

def normalize_name(name: str) -> str:
    name = " ".join(name.split())
    name = re.sub(r'^\*+', '', name).strip()
    name = re.sub(r'^[〖【](?:日本酒\s+)?(?:白牡丹|藝陽男山)[〗】]\s*', '', name)
    name = re.sub(r'^[〖【](?:お試し価格|期間限定お試し価格|オリジナルラベル)[^〗】]*[〗】]\s*', '', name)
    name = re.sub(r'^[〖【][^〗】]*(?:限定|数量限定|季節限定|取扱い店限定酒|蔵元限定酒)[〗】]\s*', '', name)
    name = re.sub(r'^(?:季節限定|輸出限定)\s*', '', name)
    name = re.sub(r'[〖【](?:製造年月|製造年月日)[^〗】]*[〗】]', '', name)
    name = re.sub(r'[［\[](?:箱なし|箱入り?|豪華[^］\]]*)[］\]]', '', name)
    name = re.sub(r'\s*\d+(?:[.,]\d+)?\s*(?:ml|mL|ML|ｍｌ|ｍl|Ｍl|ＭＬ|L|l|Ｌ|ℓ)\s*', ' ', name)
    name = re.sub(r'\s*(?:瓶詰|パック詰|ライトカップ詰)\s*', ' ', name)
    name = re.sub(r'\s*[（(][A-Z0-9-]+[）)]', '', name)
    name = re.sub(r'\s*(?:化粧箱入|木箱入|共通化粧箱入り?|特製桐箱入).*$', '', name)
    name = re.sub(r'\s*[〖【](?:流通限定|輸出専用|ネットショップ限定)[〗】]', '', name)
    name = re.sub(r'\s+[0-9,]+(?:円)?(?:\(税込\))?$', '', name)
    name = re.sub(r'[【〖](?:凍結生酒|日本酒\s+(?:白牡丹|藝陽男山)|新|蔵元限定|限定酒|あまくちの純米|自宅用におすすめ|ギフトにおすすめ)[】〗]', '', name)
    name = re.sub(r'\s+1\.8(?=\s*[（(])', ' ', name)
    name = re.sub(r'\s+(?:パック|ライトカップ)\s*(?:詰)?$', '', name)
    name = re.sub(r'\s+瓶$', '', name)
    name = re.sub(r'^超特撰\s+2本$', '超特撰', name)
    name = re.sub(r'^純米吟醸\s+恋華アソート$', '恋華アソート', name)
    name = re.sub(r'^(?:福美人\s+)', '', name)
    name = re.sub(r'\s*【[^】]*(?:おすすめ|限定)[^】]*】', '', name)
    name = re.sub(r'\s*\[\s*豪華.*$', '', name)
    name = re.sub(r'^大吟醸\s+特製ゴールド賀茂鶴\s+(?:丸瓶|角瓶)$', '大吟醸 特製ゴールド賀茂鶴', name)
    name = re.sub(r'^賀茂鶴\s+吟醸辛口$', '吟醸辛口', name)
    name = re.sub(r'^ROCK HOPPER$', '純米吟醸生原酒 ROCK HOPPER', name, flags=re.I)
    name = re.sub(r'^純米吟醸生原酒\s+RockHopper$', '純米吟醸生原酒 ROCK HOPPER', name, flags=re.I)
    name = re.sub(r'\s*木箱入$', '', name)
    name = re.sub(r'^大吟醸\s+いちの雫1\.8\s*（しずく酒）$', '大吟醸 いちの雫（しずく酒）', name)
    name = re.sub(r'^純米サンフレカップ\s*詰$', '純米サンフレカップ', name)
    name = re.sub(r'^【純米原酒プレミアム13】', '', name)
    name = re.sub(r'^純米吟醸生原酒\s*RockHopper$', '純米吟醸生原酒 ROCK HOPPER', name, flags=re.I)
    name = re.sub(r'^純米吟醸[「『]朱泉本仕込[」』].*$', '朱泉本仕込', name)
    name = re.sub(r'^純米吟醸[「『]緑泉本仕込[」』].*$', '緑泉本仕込', name)
    name = re.sub(r'^純米吟醸[「『]山吹色の酒[」』].*$', '山吹色の酒', name)
    name = re.sub(r'^純米大吟醸[「『](延寿|皇寿|壽|寿)[」』].*$', lambda m: {'壽':'壽','寿':'壽'}.get(m.group(1),m.group(1)), name)
    name = re.sub(r'^造賀純米酒$', '造賀', name)
    name = re.sub(r'^(朱泉|緑泉)普通酒(?:紙パック)?$', r'\1普通酒', name)
    name = re.sub(r'^純米酒\s+一\s*[（(]はじめ[）)]$', '純米酒 一', name)
    name = re.sub(r'^亀齢\s+大吟醸\s+創$', '大吟醸 創', name)
    name = re.sub(r'^亀齢\s+辛口純米\s+八拾\(生酒\)\(亀齢酒造\)$', '亀齢 辛口純米 八拾 生酒', name)
    name = re.sub(r'^祝いの席におきたい樽酒.*$', '樽酒', name)
    name = re.sub(r'^大吟醸 特製ゴールド賀茂鶴(?:\s*2本|丸瓶|角瓶).*$', '大吟醸 特製ゴールド賀茂鶴', name)
    name = re.sub(r'^特別本醸造 超特撰特等酒(?:\s*2本).*$', '特別本醸造 超特撰特等酒', name)
    name = re.sub(r'^【オリジナルラベル】', '', name)
    return " ".join(name.split()).strip(' ・[]')

def infer_designation(name: str) -> str:
    for k in ["純米大吟醸","大吟醸","特別純米酒","特別純米","純米吟醸","吟醸酒","吟醸","特別本醸造","本醸造","純米酒","純米"]:
        if k in name:
            return {"特別純米":"特別純米酒","吟醸":"吟醸酒","純米":"純米酒"}.get(k,k)
    return ""
def extract_specs(text: str) -> dict:
    out = {}
    pats = {
        "polishing_ratio": r'(?:精米歩合|精白歩合)\s*[：:]?\s*([0-9０-９]+(?:\.[0-9]+)?\s*[%％])',
        "alcohol": r'(?:アルコール(?:分|度数)?|ALC)\s*[：:]?\s*([0-9０-９]+(?:\.[0-9]+)?(?:\s*[～〜~-]\s*[0-9０-９]+(?:\.[0-9]+)?)?\s*度(?:以上\s*[0-9０-９]+度未満)?)',
        "sake_meter": r'日本酒度\s*[：:]?\s*([+＋\-−ー]?[0-9０-９]+(?:\.[0-9]+)?)',
        "acidity": r'酸度\s*[：:]?\s*([0-9０-９]+(?:\.[0-9]+)?)',
        "amino_acid": r'アミノ酸度\s*[：:]?\s*([0-9０-９]+(?:\.[0-9]+)?)',
        "rice": r'(?:使用米|原料米)\s*[：:]?\s*([^。\n]{1,80})',
    }
    for key, pat in pats.items():
        m = re.search(pat, text, re.I)
        if m:
            out[key] = " ".join(m.group(1).split())
    temp_hits = []
    for word in ["冷酒","冷やして","常温","ぬる燗","熱燗","燗酒","ロック"]:
        if word in text:
            temp_hits.append(word)
    if temp_hits:
        out["serving_temperature"] = " / ".join(dict.fromkeys(temp_hits))
    return out

def add_record(brewery: str, raw_name: str, status: str, sid: str, text="", note="", source_url=""):
    name = normalize_name(raw_name)
    if not name or len(name) < 2:
        return
    key = (brewery, name)
    rec = records.setdefault(key, {
        "brewery": brewery, "brand": "", "product_name": name, "formal_name": name,
        "status": status, "status_checked_at": CHECKED, "designation": infer_designation(name),
        "polishing_ratio":"", "alcohol":"", "sake_meter":"", "acidity":"", "amino_acid":"",
        "sweetness":"", "rice":"", "yeast":"", "method":"", "serving_temperature":"",
        "vessel":"", "pairing":"", "scene":"", "volume":"", "price":"", "release_period":"",
        "discontinued_period":"", "notes":"", "source_ids":[], "source_urls":[],
    })
    if status == "販売中": rec["status"] = "販売中"
    if status == "終売": rec["status"] = "終売"
    if sid not in rec["source_ids"]: rec["source_ids"].append(sid)
    if source_url and source_url not in rec["source_urls"]: rec["source_urls"].append(source_url)
    specs = extract_specs(text)
    for k,v in specs.items():
        if v and not rec.get(k): rec[k] = v
    if note and note not in rec["notes"]: rec["notes"] = (rec["notes"] + " / " + note).strip(" /")
def collect_hakubotan():
    brewery = "白牡丹酒造"
    urls = ["https://www.hakubotan.co.jp/products/" + ("" if i == 1 else f"page/{i}/") for i in range(1,8)]
    product_urls = {}
    for u in urls:
        sid, _ = save_source(brewery, u, "official_catalog")
        doc = html.fromstring((ROOT / brewery / "evidence" / f"{sid}.html").read_bytes())
        for a in doc.xpath('//a[@href]'):
            href = a.get('href') or ''
            txt = ' '.join(a.text_content().split())
            if '/products/' in href and txt and '日本酒' in txt and '/page/' not in href:
                product_urls[href] = txt
    for n,(u,txt) in enumerate(product_urls.items(),1):
        try:
            sid, body = save_source(brewery, u, "official_product")
            title = detail_title(brewery, sid, txt)
            if any(x in title for x in ["セット","のみくらべ","ギフト","アソート","梅酒","甘酒","リキュール"]):
                continue
            add_record(brewery, title, "販売中", sid, body, source_url=u)
        except Exception as e:
            print('hakubotan error',u,e,flush=True)
        if n % 20 == 0: print('hakubotan',n,'/',len(product_urls),flush=True)

def nearest_text(a):
    node = a
    for _ in range(5):
        node = node.getparent()
        if node is None: break
        t = ' '.join(node.text_content().split())
        if len(t) < 500:
            return t
    return ''
def collect_saijotsuru():
    brewery = "西條鶴醸造"
    found = {}
    for i in range(1,4):
        u = f"https://saijotsuru.co.jp/?mode=srh&page={i}"
        sid, _ = save_source(brewery, u, "official_shop_catalog")
        doc = html.fromstring((ROOT / brewery / "evidence" / f"{sid}.html").read_bytes())
        for a in doc.xpath('//a[contains(@href,"pid=")]'):
            href = urljoin(u, a.get('href'))
            txt = ' '.join(a.text_content().split())
            if not txt or any(x in txt for x in ['梅酒','セット','のみ比べ']):
                continue
            card = nearest_text(a)
            soldout = 'SOLD OUT' in card
            found[href] = (txt, soldout)
    for u,(txt,soldout) in found.items():
        try:
            sid, body = save_source(brewery, u, "official_product")
            status = "不明" if soldout else "販売中"
            note = "公式ショップでSOLD OUT表示" if soldout else ""
            add_record(brewery, txt, status, sid, body, note, u)
        except Exception as e:
            print('saijotsuru error',u,e,flush=True)
    print('saijotsuru products',len(found),flush=True)

def collect_kamotsuru():
    brewery = "賀茂鶴酒造"
    list_url = "https://shop.kamotsuru.jp/SHOP/list.php?Search=1"
    sid, _ = save_source(brewery, list_url, "official_shop_catalog")
    doc = html.fromstring((ROOT / brewery / "evidence" / f"{sid}.html").read_bytes())
    found = {}
    for a in doc.xpath('//a[@href]'):
        href = a.get('href') or ''
        txt = ' '.join(a.text_content().split())
        if re.search(r'/SHOP/[^/]+\.html$', href) and txt:
            if any(x in txt for x in ['セット','酒粕','梅酒','食品','グッズ','最新情報']):
                continue
            found[urljoin(list_url,href)] = txt
    for u,txt in found.items():
        try:
            sid, body = save_source(brewery, u, "official_product")
            add_record(brewery, txt, "販売中", sid, body, source_url=u)
        except Exception as e:
            print('kamotsuru error',u,e,flush=True)
    print('kamotsuru products',len(found),flush=True)
def collect_kamoizumi():
    brewery = "賀茂泉酒造"
    u = "https://www.kamoizumi.co.jp/sake/index.php"
    sid, body = save_source(brewery, u, "official_catalog")
    doc = html.fromstring((ROOT / brewery / "evidence" / f"{sid}.html").read_bytes())
    for h in doc.xpath('//h4'):
        name = ' '.join(h.text_content().split()).strip('「」 ')
        if not name or '梅酒' in name:
            continue
        node = h.getparent()
        text = ' '.join(node.text_content().split()) if node is not None else body
        if len(text) > 1200:
            text = body[body.find(name):body.find(name)+1200] if name in body else text[:1200]
        add_record(brewery, name, "販売中", sid, text, source_url=u)
    shop_url = "https://online.kamoizumi.com/?cid=&keyword=&mode=srh&page={}"
    try:
        found = {}
        for page_num in range(1, 6):
            page_url = shop_url.format(page_num)
            ssid, _ = save_source(brewery, page_url, "official_shop_catalog")
            sdoc = html.fromstring((ROOT / brewery / "evidence" / f"{ssid}.html").read_bytes())
            for a in sdoc.xpath('//a[@href]'):
                href = a.get('href') or ''
                txt = ' '.join(a.text_content().split())
                if 'pid=' in href and txt and not any(x in txt for x in ['セット','マスク','梅酒','グッズ','頒布会','石けん','クリーム','ローション','シャンプー','トリートメント','入浴','カレー','前掛け','紙袋','ビニール袋','木桝']):
                    found[urljoin(page_url, href)] = txt
        for pu,ptxt in found.items():
            if any(x in ptxt for x in ['菰巻樽','酒粕','甘酒']):
                continue
            try:
                psid,pbody=save_source(brewery,pu,"official_shop_product")
                add_record(brewery,ptxt,"販売中",psid,pbody,"公式オンラインショップで販売確認",pu)
            except Exception as e: print('kamoizumi shop product',pu,e,flush=True)
        print('kamoizumi shop products',len(found),flush=True)
    except Exception as e: print('kamoizumi shop error',e,flush=True)
    print('kamoizumi parsed',flush=True)

def collect_fukubijin():
    brewery = "福美人酒造"
    pages = [
        "https://www.fukubijin.co.jp/SHOP/g23585/list.html",
        "https://www.fukubijin.co.jp/SHOP/g23586/list.html",
        "https://www.fukubijin.co.jp/SHOP/g23587/list.html",
        "https://www.fukubijin.co.jp/SHOP/g23588/list.html",
        "https://www.fukubijin.co.jp/product.html",
    ]
    found = {}
    for u in pages:
        sid, _ = save_source(brewery, u, "official_shop_catalog")
        doc = html.fromstring((ROOT / brewery / "evidence" / f"{sid}.html").read_bytes())
        for a in doc.xpath('//a[@href]'):
            href = a.get('href') or ''
            txt = ' '.join(a.text_content().split())
            if '/SHOP/' in href and re.search(r'/SHOP/[^/]+\.html$', href) and txt:
                if any(x in txt for x in ['セット','梅酒','甘酒','しゃもじ','オリジナルラベル']): continue
                found[urljoin(u,href)] = txt
    for u,txt in found.items():
        try:
            sid, body = save_source(brewery, u, "official_product")
            add_record(brewery, txt, "販売中", sid, body, source_url=u)
        except Exception as e:
            print('fukubijin error',u,e,flush=True)
    print('fukubijin products',len(found),flush=True)
def detail_title(brewery: str, sid: str, fallback: str) -> str:
    p = ROOT / brewery / "evidence" / f"{sid}.html"
    try:
        doc = html.fromstring(p.read_bytes())
        for xp in ['//h1', '//h2', '//title']:
            vals = [' '.join(x.text_content().split()) for x in doc.xpath(xp)]
            vals = [v for v in vals if v and len(v) < 220]
            if vals:
                return vals[0]
    except Exception:
        pass
    return fallback

def collect_kirei():
    brewery = "亀齢酒造"
    official_urls = [
        "https://kireikireikirei.jimdofree.com/",
        "https://kireikireikirei.jimdofree.com/商品案内/",
        "https://kireikireikirei.jimdofree.com/酒蔵土産売場-まねきや/",
        "https://kireikireikirei.jimdofree.com/亀齢-蔵開き-2026年4月11日-土/",
    ]
    saved = {}
    for u in official_urls:
        try: saved[u] = save_source(brewery, u, "official")
        except Exception as e: print('kirei official error',u,e,flush=True)
    if official_urls[2] in saved:
        sid, body = saved[official_urls[2]]
        for name in ["吉田屋の酒", "大吟醸 創", "純米大吟醸 亀香"]:
            add_record(brewery, name, "販売中", sid, body, "公式直売所の主な販売酒", official_urls[2])
    if official_urls[3] in saved:
        sid, body = saved[official_urls[3]]
        for name in ["亀齢 純米大吟醸 千本錦", "亀齢 万事酒盃中 おりがらみ", "亀齢萬年 生酒 純米六拾"]:
            add_record(brewery, name, "不明", sid, body, "2026年蔵開き限定酒", official_urls[3])
    retailer = "https://www.hiroshimasake.com/product-list/6"
    try:
        sid, _ = save_source(brewery, retailer, "current_retailer_catalog")
        doc = html.fromstring((ROOT / brewery / "evidence" / f"{sid}.html").read_bytes())
        found = {}
        for a in doc.xpath('//a[@href]'):
            txt = ' '.join(a.text_content().split())
            href = a.get('href') or ''
            if ('亀齢' in txt or '亀齢萬年' in txt) and '/product/' in href:
                found[urljoin(retailer, href)] = txt
        for u, txt in found.items():
            try:
                psid, body = save_source(brewery, u, "current_retailer_product")
                title = detail_title(brewery, psid, txt)
                add_record(brewery, title, "販売中", psid, body,
                           "現行小売店で販売確認（メーカー公式の販売状態ではない）", u)
            except Exception as e:
                print('kirei retailer error',u,e,flush=True)
        print('kirei retailer products',len(found),flush=True)
    except Exception as e:
        print('kirei retailer catalog error',e,flush=True)

def collect_extra_history():
    extra = [
        ("白牡丹酒造", "https://www.hakubotan.co.jp/酒まつり限定　にごり酒　ご予約受付中＆送料無料キャンペーン　/",
         [("酒まつり限定 純米にごり酒", "2024年公式案内。例年の酒まつり限定、現在状態不明")]),
        ("亀齢酒造", "https://kireikireikirei.jimdofree.com/酒まつり情報-２０２５/",
         [("亀齢 酒まつり限定 ひやおろし", "2025酒まつり限定、現在状態不明"),
          ("亀齢 酒まつり限定 純米原酒", "2025酒まつり限定、現在状態不明")]),
        ("西條鶴醸造", "https://saijotsuru.co.jp/?mode=f12",
         [("鑑評会出品酒", "2025酒まつり限定販売、現在状態不明")]),
        ("西條鶴醸造", "https://saijotsuru.co.jp/?mode=f10",
         [("斗ビン取り純米大吟醸", "2022酒まつり限定販売、現在状態不明"),
          ("愛山純米酒75", "2022酒まつりで販売確認。現行の愛山70とは別仕様、現在状態不明")]),
    ]
    for brewery,u,items in extra:
        try:
            sid,body=save_source(brewery,u,"official_historical")
            for name,note in items: add_record(brewery,name,"不明",sid,body,note,u)
        except Exception as e: print('extra history',brewery,u,e,flush=True)

def collect_sanyotsuru():
    brewery = "山陽鶴酒造"
    urls = {
        "set":"https://sanyotsuru.jp/archives/product/gosyu",
        "end":"https://sanyotsuru.jp/archives/news/20260414",
        "event26":"https://sanyotsuru.jp/archives/news/20260409",
        "event24":"https://sanyotsuru.jp/archives/news/2024kurabiraki",
        "home":"https://sanyotsuru.jp/",
    }
    saved = {}
    for k,u in urls.items():
        try: saved[k] = save_source(brewery, u, "official")
        except Exception as e: print('sanyotsuru error',u,e,flush=True)
    if 'set' in saved:
        sid, body = saved['set']
        for name in ["大吟醸", "純米吟醸", "本醸造", "上撰"]:
            add_record(brewery, name, "販売中", sid, body, "公式五酒セットに現行代表酒として掲載", urls['set'])
    if 'end' in saved:
        sid, body = saved['end']
        add_record(brewery, "清酒にごり おり酒", "終売", sid, body,
                   "2026-04-14公式発表。在庫限りで終売", urls['end'])
    if 'event26' in saved:
        sid, body = saved['event26']
        for name in ["純米酒 生しぼりたて", "純米吟醸 しぼりたて"]:
            add_record(brewery, name, "不明", sid, body, "2026年蔵開き限定酒", urls['event26'])
    if 'event24' in saved:
        sid, body = saved['event24']
        add_record(brewery, "大吟醸 しぼりたて", "不明", sid, body, "2024年蔵開き限定酒", urls['event24'])
def collect_manual_official():
    # 賀茂鶴：公式に終売が明記された旧商品・限定商品
    brewery = "賀茂鶴酒造"
    entries = [
        ("https://www.kamotsuru.jp/news/6771/", "純米吟醸酒（GNP-A1）", "終売", "2016年3月、後継GP-A1発売をもって販売終了"),
        ("https://shop.kamotsuru.jp/SHOP/346437/346496/list.html", "純米吟醸 熟成酒", "終売", "公式オンラインストアに『終売しました』と明記"),
        ("https://www.kamotsuru.jp/news/2874/", "瑞兆（2010年限定・精米歩合20%）", "終売", "2010年限定1000本、なくなり次第終売と公式告知"),
    ]
    for u,name,status,note in entries:
        try:
            sid, body = save_source(brewery, u, "official_historical")
            add_record(brewery, name, status, sid, body, note, u)
        except Exception as e: print('kamotsuru historical',u,e,flush=True)

    # 2012年「瀬戸内紀行」限定セットに含まれた3銘柄
    u = "https://www.kamotsuru.jp/news/4267/"
    try:
        sid, body = save_source(brewery, u, "official_historical")
        hist = [
            ("安芸の宮島", "", "66%", "15～16度", "+1.5", "", "上燗 / 人肌燗 / 常温 / 冷"),
            ("純米吟醸 厳島", "純米吟醸", "55%", "16～17度", "+4", "八反100%", "人肌燗 / 常温 / 冷 / ロック"),
            ("鞆の浦", "普通酒（生貯蔵酒）", "69%", "14～15度", "+3", "", "常温 / 冷"),
        ]
        for name,designation,polish,alc,meter,rice,temp in hist:
            add_record(brewery, name, "不明", sid, "", "2012年限定セット『瀬戸内紀行』構成酒。現在の販売状態は確認できず", u)
            r=records[(brewery,normalize_name(name))]
            r.update({"designation":designation,"polishing_ratio":polish,"alcohol":alc,"sake_meter":meter,"rice":rice,"serving_temperature":temp})
    except Exception as e: print('kamotsuru set historical',e,flush=True)

    # 公式アーカイブで確認できる過去の限定酒
    history_pages = [
        ("https://www.kamotsuru.jp/sakematsuri/limited/", [
            ("酒まつり2020 純米大吟醸 広系酒33号", "2020年10月限定販売。現在状態不明"),
            ("酒まつり2020 大吟醸 のん太ラベル", "2020年10月限定販売。現在状態不明"),
            ("見学室直売所 一周年記念酒 雄町", "2020年限定・シリアルナンバー入。現在状態不明"),
            ("熟成大吟醸（2020酒まつり）", "2020年本数限定・シリアルナンバー入。現在状態不明"),
        ]),
        ("https://www.kamotsuru.jp/news/9491/", [
            ("酒まつり限定 純米大吟醸 山田錦（2018）", "2018酒まつり限定。現在状態不明"),
        ]),
    ]
    for hu, items in history_pages:
        try:
            hsid,hbody=save_source(brewery,hu,"official_historical")
            for hname,hnote in items: add_record(brewery,hname,"不明",hsid,hbody,hnote,hu)
        except Exception as e: print('kamotsuru archive history',hu,e,flush=True)

    # 賀茂泉：公式直売所の最新案内に出る季節・蔵元限定商品
    brewery = "賀茂泉酒造"
    u = "https://kamoizumi.co.jp/syusenkan/s_detail.php?id=510"
    try:
        sid, body = save_source(brewery, u, "official_shop_news")
        add_record(brewery, "蔵元限定 山田錦 純米吟醸生酒", "販売中", sid, body, "2026-08-07公式直売所で販売中", u)
        add_record(brewery, "青泉 本仕込 生酒", "販売中", sid, body, "2026-08-07公式直売所で販売案内", u)
        add_record(brewery, "ROCK HOPPER", "不明", sid, body, "2026-08-07時点で720ml完売。終売とは確認できない", u)
    except Exception as e: print('kamoizumi shop news',e,flush=True)
BRANDS = {
    "賀茂鶴酒造":"賀茂鶴", "白牡丹酒造":"白牡丹", "西條鶴醸造":"西條鶴",
    "亀齢酒造":"亀齢", "福美人酒造":"福美人", "賀茂泉酒造":"賀茂泉", "山陽鶴酒造":"山陽鶴",
}
INDEX_FIELDS = [
    "record_id","酒蔵","ブランド","商品名","正式名称","販売状態","販売状態確認日","特定名称",
    "精米歩合","アルコール度数","日本酒度","酸度","アミノ酸度","甘辛度","使用米","酵母","製法",
    "おすすめ温度","おすすめ酒器","料理ペアリング","おすすめシーン","容量","価格","発売時期","終売時期",
    "備考","詳細ファイル","主出典ID","出典数",
]

def record_id(brewery: str, name: str) -> str:
    return BREWERY_CODES[brewery] + "_" + hashlib.sha1(name.encode('utf-8')).hexdigest()[:10].upper()

def write_sources():
    with SOURCES_FILE.open('w', encoding='utf-8') as f:
        for sid in sorted(sources):
            row = {k:v for k,v in sources[sid].items() if k != 'text'}
            f.write(json.dumps(row, ensure_ascii=False) + '\n')

def md_value(v):
    if isinstance(v, list): return ' / '.join(str(x) for x in v)
    return str(v or '')
def write_product_md(rec: dict) -> str:
    rid = record_id(rec['brewery'], rec['product_name'])
    fname = clean_filename(rec['product_name']) + '.md'
    rel = Path(rec['brewery']) / fname
    p = ROOT / rel
    lines = [
        f"# {rec['formal_name']}", "", "## 基本情報", "",
        f"- ID: {rid}", f"- 酒蔵: {rec['brewery']}", f"- ブランド: {BRANDS[rec['brewery']]}",
        f"- 商品名: {rec['product_name']}", f"- 販売状態: {rec['status']}",
        f"- 販売状態確認日: {rec['status_checked_at']}", f"- 特定名称: {rec['designation']}",
        f"- 精米歩合: {rec['polishing_ratio']}", f"- アルコール度数: {rec['alcohol']}",
        f"- 日本酒度: {rec['sake_meter']}", f"- 酸度: {rec['acidity']}", f"- アミノ酸度: {rec['amino_acid']}",
        f"- 使用米: {rec['rice']}", f"- 酵母: {rec['yeast']}", f"- 製法: {rec['method']}",
        f"- おすすめ温度: {rec['serving_temperature']}", f"- おすすめ酒器: {rec['vessel']}",
        f"- 料理ペアリング: {rec['pairing']}", f"- おすすめシーン: {rec['scene']}", "", "## 情報源", "",
    ]
    for sid in rec['source_ids']:
        src = sources.get(sid, {})
        lines += [f"### {sid}", f"- 種類: {src.get('source_type','')}", f"- URL: {src.get('url','')}",
                  f"- 取得日時: {src.get('retrieved_at','')}", f"- HTTP: {src.get('http_status','')}",
                  f"- 保存ファイル: {src.get('saved_file','')}", f"- SHA-256: {src.get('sha256','')}", ""]
    lines += ["## メモ", "", rec['notes'] or ""]
    p.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return str(rel).replace('\\','/')
def write_outputs():
    write_sources()
    for brewery in BREWERY_CODES:
        for old_md in (ROOT / brewery).glob("*.md"):
            if old_md.name != "brewery.md":
                old_md.unlink()
    rows = []
    by_brewery = {b:[] for b in BREWERY_CODES}
    for (brewery,name),rec in sorted(records.items(), key=lambda x:(x[0][0],x[0][1])):
        rec['brand'] = BRANDS[brewery]
        detail = write_product_md(rec)
        rid = record_id(brewery, name)
        row = {
            "record_id":rid, "酒蔵":brewery, "ブランド":rec['brand'], "商品名":name, "正式名称":rec['formal_name'],
            "販売状態":rec['status'], "販売状態確認日":rec['status_checked_at'], "特定名称":rec['designation'],
            "精米歩合":rec['polishing_ratio'], "アルコール度数":rec['alcohol'], "日本酒度":rec['sake_meter'],
            "酸度":rec['acidity'], "アミノ酸度":rec['amino_acid'], "甘辛度":rec['sweetness'], "使用米":rec['rice'],
            "酵母":rec['yeast'], "製法":rec['method'], "おすすめ温度":rec['serving_temperature'], "おすすめ酒器":rec['vessel'],
            "料理ペアリング":rec['pairing'], "おすすめシーン":rec['scene'], "容量":rec['volume'], "価格":rec['price'],
            "発売時期":rec['release_period'], "終売時期":rec['discontinued_period'], "備考":rec['notes'],
            "詳細ファイル":detail, "主出典ID":rec['source_ids'][0] if rec['source_ids'] else '', "出典数":len(rec['source_ids']),
        }
        rows.append(row); by_brewery[brewery].append(row)
    with (ROOT/'index.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=INDEX_FIELDS); w.writeheader(); w.writerows(rows)
    with (ROOT/'records.jsonl').open('w',encoding='utf-8') as f:
        for row in rows: f.write(json.dumps(row,ensure_ascii=False)+'\n')
    for brewery,items in by_brewery.items():
        counts={s:sum(1 for x in items if x['販売状態']==s) for s in ['販売中','休売','終売','不明']}
        text=[f"# {brewery}","",f"登録銘柄数: {len(items)}",""]+[f"- {k}: {v}" for k,v in counts.items()]
        (ROOT/brewery/'brewery.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    return rows
INJECTION_PATTERNS = [
    "ignore previous instructions", "ignore all previous instructions", "system prompt", "developer message",
    "prompt injection", "以前の指示を無視", "上の指示を無視", "システムプロンプト",
]

def scan_prompt_injection():
    hits=[]
    for brewery in BREWERY_CODES:
        for p in (ROOT/brewery/'evidence').glob('*'):
            if p.suffix.lower() not in {'.html','.txt','.json','.xml'}: continue
            text=p.read_text(encoding='utf-8',errors='ignore').lower()
            found=[x for x in INJECTION_PATTERNS if x.lower() in text]
            if found: hits.append({"file":str(p.relative_to(ROOT)).replace('\\','/'),"patterns":found})
    out=ROOT/'potential_prompt_injection.jsonl'
    if hits:
        with out.open('w',encoding='utf-8') as f:
            for h in hits:f.write(json.dumps(h,ensure_ascii=False)+'\n')
    elif out.exists(): out.unlink()
    return hits

def main():
    collectors=[collect_hakubotan,collect_saijotsuru,collect_kamotsuru,collect_kamoizumi,
                collect_fukubijin,collect_kirei,collect_extra_history,collect_sanyotsuru,collect_manual_official]
    for fn in collectors:
        print('START',fn.__name__,flush=True)
        try: fn()
        except Exception as e: print('COLLECTOR ERROR',fn.__name__,repr(e),flush=True)
    rows=write_outputs()
    hits=scan_prompt_injection()
    stats={b:sum(1 for x in rows if x['酒蔵']==b) for b in BREWERY_CODES}
    status={s:sum(1 for x in rows if x['販売状態']==s) for s in ['販売中','休売','終売','不明']}
    summary={"generated_at":now_iso(),"records":len(rows),"by_brewery":stats,"by_status":status,
             "sources":len(sources),"prompt_injection_hits":len(hits)}
    (ROOT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()
