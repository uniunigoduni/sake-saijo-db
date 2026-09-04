from pathlib import Path
p=Path(r'C:\Users\tarou\Downloads\sake-saijo-db\research\web\_scripts\collect_catalog.py')
t=p.read_text(encoding='utf-8')
t=t.replace("(?:ml|mL|ML|ｍｌ|ＭＬ|L|l|Ｌ|ℓ)", "(?:ml|mL|ML|ｍｌ|ｍl|Ｍl|ＭＬ|L|l|Ｌ|ℓ)")
needle="""    shop_url = "https://online.kamoizumi.com/?mode=srh"\n    try:\n        ssid, _ = save_source(brewery, shop_url, "official_shop_catalog")\n        sdoc = html.fromstring((ROOT / brewery / "evidence" / f"{ssid}.html").read_bytes())\n        found = {}\n        for a in sdoc.xpath('//a[@href]'):\n            href = a.get('href') or ''\n            txt = ' '.join(a.text_content().split())\n            if 'pid=' in href and txt and not any(x in txt for x in ['セット','マスク','梅酒','グッズ','頒布会']):\n                found[urljoin(shop_url, href)] = txt\n"""
repl="""    shop_url = "https://online.kamoizumi.com/?cid=&keyword=&mode=srh&page={}"\n    try:\n        found = {}\n        for page_num in range(1, 6):\n            page_url = shop_url.format(page_num)\n            ssid, _ = save_source(brewery, page_url, "official_shop_catalog")\n            sdoc = html.fromstring((ROOT / brewery / "evidence" / f"{ssid}.html").read_bytes())\n            for a in sdoc.xpath('//a[@href]'):\n                href = a.get('href') or ''\n                txt = ' '.join(a.text_content().split())\n                if 'pid=' in href and txt and not any(x in txt for x in ['セット','マスク','梅酒','グッズ','頒布会','石けん','クリーム','ローション','シャンプー','トリートメント','入浴','カレー','前掛け','紙袋','ビニール袋','木桝']):\n                    found[urljoin(page_url, href)] = txt\n"""
if needle not in t: raise SystemExit('shop block not found')
t=t.replace(needle,repl)
p.write_text(t,encoding='utf-8')
print('shop pagination patched')
t=p.read_text(encoding='utf-8')
needle="""    name = re.sub(r'^【純米原酒プレミアム13】', '', name)\n"""
insert=needle+"""    name = re.sub(r'^純米吟醸生原酒\\s*RockHopper$', '純米吟醸生原酒 ROCK HOPPER', name, flags=re.I)\n    name = re.sub(r'^純米吟醸[「『]朱泉本仕込[」』].*$', '朱泉本仕込', name)\n    name = re.sub(r'^純米吟醸[「『]緑泉本仕込[」』].*$', '緑泉本仕込', name)\n    name = re.sub(r'^純米吟醸[「『]山吹色の酒[」』].*$', '山吹色の酒', name)\n    name = re.sub(r'^純米大吟醸[「『](延寿|皇寿|壽|寿)[」』].*$', lambda m: {'壽':'壽','寿':'壽'}.get(m.group(1),m.group(1)), name)\n    name = re.sub(r'^造賀純米酒$', '造賀', name)\n    name = re.sub(r'^(朱泉|緑泉)普通酒(?:紙パック)?$', r'\\1普通酒', name)\n    name = re.sub(r'^純米酒\\s+一\\s*[（(]はじめ[）)]$', '純米酒 一', name)\n"""
if needle not in t: raise SystemExit('canonical insertion missing')
t=t.replace(needle,insert)
p.write_text(t,encoding='utf-8')
print('canonical mappings patched')
