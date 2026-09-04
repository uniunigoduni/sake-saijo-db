from __future__ import annotations
import json, re
from pathlib import Path
import requests
from lxml import html
import collect_catalog as c

EXTRA_CODES = {
    "金光酒造":"KANEMITSU",
    "今田酒造本店":"IMADA",
    "柄酒造":"TSUKA",
}
EXTRA_BRANDS = {
    "金光酒造":"賀茂金秀 / 桜吹雪",
    "今田酒造本店":"富久長",
    "柄酒造":"於多福 / 関西一",
}
c.BREWERY_CODES.update(EXTRA_CODES)
c.BRANDS.update(EXTRA_BRANDS)

HEADERS = {"User-Agent":"Mozilla/5.0 sake-saijo-db/0.2"}

def compact(s: str) -> str:
    return " ".join((s or "").split())
def clean_kamokin_alt(alt: str) -> str:
    name = compact(alt)
    name = re.sub(r'(720|1800)$', '', name)
    name = name.replace('さくらふぶき', '桜吹雪')
    name = re.sub(r'^賀茂金秀', '賀茂金秀 ', name)
    name = name.replace('純米吟醸雄町', '純米吟醸 雄町').replace('純米吟醸愛山', '純米吟醸 愛山')
    name = name.replace('賀茂金秀 SUITOH', '賀茂金秀 SUITOH 雄町')
    name = re.sub(r'^桜吹雪', '桜吹雪 ', name)
    return compact(name)

def collect_kanemitsu():
    brewery = "金光酒造"
    company = "https://www.kamokin.com/about_us/company.html"
    try:
        c.save_source(brewery, company, "official_company")
    except Exception as e:
        print('kanemitsu company', repr(e), flush=True)
    pages = [
        ("https://www.kamokin.com/line_up/regular.html", "販売中", "official_regular_lineup"),
        ("https://www.kamokin.com/line_up/Limited/limited.html", "不明", "official_limited_lineup"),
    ]
    for url, status, stype in pages:
        sid, body = c.save_source(brewery, url, stype)
        doc = html.fromstring((c.ROOT / brewery / 'evidence' / f'{sid}.html').read_bytes())
        names = {clean_kamokin_alt(i.get('alt')) for i in doc.xpath('//img[@alt]')}
        names = {x for x in names if x and not x.startswith('Enable JavaScript')}
        for name in sorted(names):
            note = "公式定番ラインナップ掲載" if status == "販売中" else "公式限定ラインナップ掲載。現在の在庫・販売時期は断定せず"
            c.add_record(brewery, name, status, sid, "", note, url)
        print('kanemitsu', stype, len(names), flush=True)

    jsp = "https://j-s-p.or.jp/kuramoto/kanemitsu"
    try:
        sid, body = c.save_source(brewery, jsp, "brewery_association_profile")
        for name in ["賀茂金秀 純米大吟醸35", "賀茂金秀 純米吟醸 雄町", "賀茂金秀 特別純米13"]:
            c.add_record(brewery, name, "販売中", sid, body, "日本酒造組合中央会系JSP蔵元ページの代表商品", jsp)
    except Exception as e:
        print('kanemitsu jsp', repr(e), flush=True)

def product_page_url(base: str, handle: str) -> str:
    return base.rstrip('/') + '/products/' + handle

def clean_shop_title(title: str, prefix: str = '') -> str:
    name = compact(title)
    if prefix and name.startswith(prefix):
        name = name[len(prefix):].strip()
    name = re.sub(r'\s*[【\[]特別栽培米[】\]]', '', name)
    name = re.sub(r'\s*\d+(?:\.\d+)?\s*(?:ml|mL|ML|L|l|Ｌ|ｍｌ)', '', name)
    name = re.sub(r'\s*[・/]\s*$', '', name)
    return compact(name)
def collect_imada():
    brewery = "今田酒造本店"
    base = "https://fukucho.jp"
    catalog = base + "/collections/all"
    api = base + "/products.json?limit=250"
    c.save_source(brewery, "https://fukucho.jp/pages/company", "official_company")
    c.save_source(brewery, catalog, "official_shop_catalog")
    c.save_source(brewery, api, "official_shop_api")
    data = requests.get(api, timeout=60, headers=HEADERS).json()
    kept = 0
    for p in data.get('products', []):
        if p.get('product_type') != '日本酒':
            continue
        title = clean_shop_title(p.get('title',''), '富久長')
        if not title:
            continue
        url = product_page_url(base, p.get('handle',''))
        available = any(v.get('available') for v in p.get('variants', []))
        status = "販売中" if available else "不明"
        note = "公式オンラインショップで在庫あり" if available else "公式商品ページ掲載・現在在庫なし。終売とは確認できない"
        if 'アメリカ限定' in p.get('tags', []):
            note += " / アメリカ限定商品"
        try:
            sid, body = c.save_source(brewery, url, "official_product")
            c.add_record(brewery, title, status, sid, body, note, url)
            kept += 1
        except Exception as e:
            print('imada product', url, repr(e), flush=True)
    print('imada sake products', kept, flush=True)
def clean_tsuka_title(title: str) -> str:
    name = compact(title)
    fired = name.startswith('【火入れ】')
    name = re.sub(r'^【火入れ】', '', name).strip()
    name = re.sub(r'\s*\d+(?:\.\d+)?\s*(?:ml|mL|ML|L|l|Ｌ|ｍｌ)', '', name)
    name = re.sub(r'\s*[・/]\s*$', '', name)
    name = re.sub(r'（桐箱入り）', '', name)
    if fired and '火入れ' not in name:
        name += ' 火入れ'
    return compact(name)

def collect_tsuka():
    brewery = "柄酒造"
    base = "https://www.tsukasyuzou.jp"
    api = base + "/products.json?limit=250"
    c.save_source(brewery, base + "/pages/greeting", "official_company")
    c.save_source(brewery, base + "/collections/all", "official_shop_catalog")
    c.save_source(brewery, api, "official_shop_api")
    data = requests.get(api, timeout=60, headers=HEADERS).json()
    kept = 0
    for p in data.get('products', []):
        if p.get('product_type') != '酒類':
            continue
        title = clean_tsuka_title(p.get('title',''))
        url = product_page_url(base, p.get('handle',''))
        available = any(v.get('available') for v in p.get('variants', []))
        status = "販売中" if available else "不明"
        note = "公式オンラインショップで販売確認" if available else "公式商品ページ掲載・現在在庫なし。終売とは確認できない"
        try:
            sid, body = c.save_source(brewery, url, "official_product")
            c.add_record(brewery, title, status, sid, body, note, url)
            kept += 1
        except Exception as e:
            print('tsuka product', url, repr(e), flush=True)
    print('tsuka sake products', kept, flush=True)

def clean_secondary_name(name: str, prefixes: tuple[str,...]) -> str:
    out = compact(name)
    for prefix in prefixes:
        if out.startswith(prefix):
            out = out[len(prefix):].strip()
            break
    return out

def secondary_canonical(brewery: str, raw: str) -> str:
    name = compact(raw)
    if brewery == "金光酒造":
        name = clean_kamokin_alt(name)
        if name.startswith("賀茂金秀 桜吹雪 "):
            name = name[len("賀茂金秀 "):]
        return name
    if brewery == "今田酒造本店":
        name = clean_secondary_name(name, ("富久長",))
        mapping = {
            "純米吟醸 八反草":"八反草 純米吟醸",
            "純米吟醸 山田錦":"山田錦 純米吟醸",
            "辛口純米酒":"辛口純米",
            "ひやおろし 秋櫻 純米":"秋櫻〈コスモス〉 純米 ひやおろし",
            "ひやおろし 秋櫻 純米吟醸":"秋櫻〈コスモス〉 純米吟醸 ひやおろし",
        }
        return mapping.get(name, name)
    return name

def collect_secondary_history():
    configs = [
        ("金光酒造", "https://sakeai.com/brand/2782"),
        ("今田酒造本店", "https://sakeai.com/brand/3227"),
        ("柄酒造", "https://sakeai.com/brand/2797"),
    ]
    candidates = []
    for brewery, url in configs:
        try:
            sid, _ = c.save_source(brewery, url, "secondary_database")
            pth = c.ROOT / brewery / 'evidence' / f'{sid}.html'
            doc = html.fromstring(pth.read_bytes().decode('utf-8', errors='replace'))
            seen = set()
            for a in doc.xpath('//a[@href]'):
                href = a.get('href') or ''
                if not re.fullmatch(r'/sake/\d+', href): continue
                raw = compact(a.text_content())
                if not raw or len(raw) > 120 or raw in seen: continue
                seen.add(raw)
                name = secondary_canonical(brewery, raw)
                key = (brewery, c.normalize_name(name))
                if key in c.records:
                    c.add_record(brewery, name, "不明", sid, "", "二次DBでも存在確認", url)
                else:
                    candidates.append({'brewery':brewery,'name':name,'source_url':url,'source_id':sid})
            print('secondary checked', brewery, len(seen), flush=True)
        except Exception as e:
            print('secondary error', brewery, repr(e), flush=True)
    out=c.ROOT/'_research_log'/'secondary_candidates_higashihiroshima.jsonl'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in candidates),encoding='utf-8')
    print('secondary unmatched candidates', len(candidates), flush=True)

def qa_existing_records():
    bad_tokens = [
        'バリアケア', 'ボディーソープ', 'エッセンス', 'コンディショニングシャンプー',
        'トリートメントリンス', '透明石けん', '入浴液', 'アトピスマイル', '潤いマスク',
    ]
    drop = []
    for key, rec in c.records.items():
        if rec.get('brewery') == '賀茂泉酒造' and any(x in rec.get('product_name','') for x in bad_tokens):
            drop.append(key)
    for key in drop:
        c.records.pop(key, None)
    print('qa dropped non-sake', len(drop), flush=True)
def main():
    collectors = [
        c.collect_hakubotan, c.collect_saijotsuru, c.collect_kamotsuru,
        c.collect_kamoizumi, c.collect_fukubijin, c.collect_kirei,
        c.collect_extra_history, c.collect_sanyotsuru, c.collect_manual_official,
        collect_kanemitsu, collect_imada, collect_tsuka, collect_secondary_history,
    ]
    for fn in collectors:
        print('START', fn.__name__, flush=True)
        try:
            fn()
        except Exception as e:
            print('COLLECTOR ERROR', fn.__name__, repr(e), flush=True)
    qa_existing_records()
    rows = c.write_outputs()
    hits = c.scan_prompt_injection()
    stats = {b: sum(1 for x in rows if x['酒蔵'] == b) for b in c.BREWERY_CODES}
    status = {s: sum(1 for x in rows if x['販売状態'] == s) for s in ['販売中','休売','終売','不明']}
    summary = {
        'generated_at': c.now_iso(), 'scope': '東広島市内10蔵', 'records': len(rows),
        'by_brewery': stats, 'by_status': status, 'sources': len(c.sources),
        'prompt_injection_hits': len(hits),
    }
    (c.ROOT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=True), flush=True)

if __name__ == '__main__':
    main()
