from pathlib import Path
p=Path(r'C:\Users\tarou\Downloads\sake-saijo-db\research\web\_scripts\collect_catalog.py')
t=p.read_text(encoding='utf-8')
start=t.index('def normalize_name(name: str) -> str:')
end=t.index('\ndef infer_designation', start)
new='''def normalize_name(name: str) -> str:\n    name = " ".join(name.split())\n    name = re.sub(r'^[〖【](?:日本酒\\s+)?(?:白牡丹|藝陽男山)[〗】]\\s*', '', name)\n    name = re.sub(r'^[〖【](?:お試し価格|期間限定お試し価格|オリジナルラベル)[^〗】]*[〗】]\\s*', '', name)\n    name = re.sub(r'^[〖【][^〗】]*(?:限定|数量限定|季節限定|取扱い店限定酒|蔵元限定酒)[〗】]\\s*', '', name)\n    name = re.sub(r'^(?:季節限定|輸出限定)\\s*', '', name)\n    name = re.sub(r'[〖【](?:製造年月|製造年月日)[^〗】]*[〗】]', '', name)\n    name = re.sub(r'[［\\[](?:箱なし|箱入り?|豪華[^］\\]]*)[］\\]]', '', name)\n    name = re.sub(r'\\s*\\d+(?:[.,]\\d+)?\\s*(?:ml|mL|ML|ｍｌ|ＭＬ|L|l|Ｌ|ℓ)\\s*', ' ', name)\n    name = re.sub(r'\\s*(?:瓶詰|パック詰|ライトカップ詰)\\s*', ' ', name)\n    name = re.sub(r'\\s*[（(][A-Z0-9-]+[）)]', '', name)\n    name = re.sub(r'\\s*(?:化粧箱入|木箱入|共通化粧箱入り?|特製桐箱入).*$', '', name)\n    name = re.sub(r'\\s*[〖【](?:流通限定|輸出専用|ネットショップ限定)[〗】]', '', name)\n    name = re.sub(r'\\s+[0-9,]+(?:円)?(?:\\(税込\\))?$', '', name)\n    name = re.sub(r'^(?:福美人\\s+)', '', name)\n    name = re.sub(r'^祝いの席におきたい樽酒.*$', '樽酒', name)\n    name = re.sub(r'^大吟醸 特製ゴールド賀茂鶴(?:\\s*2本|丸瓶|角瓶).*$', '大吟醸 特製ゴールド賀茂鶴', name)\n    name = re.sub(r'^特別本醸造 超特撰特等酒(?:\\s*2本).*$', '特別本醸造 超特撰特等酒', name)\n    name = re.sub(r'^【オリジナルラベル】', '', name)\n    return " ".join(name.split()).strip(' ・[]')\n'''
t=t[:start]+new+t[end:]
p.write_text(t,encoding='utf-8')
print('normalize patched')
t=p.read_text(encoding='utf-8')
old='''            sid, body = save_source(brewery, u, "official_product")\n            title = txt.split('円(')[0]\n            add_record(brewery, title, "販売中", sid, body, source_url=u)\n'''
new='''            sid, body = save_source(brewery, u, "official_product")\n            title = detail_title(brewery, sid, txt)\n            if any(x in title for x in ["セット","のみくらべ","ギフト","梅酒","甘酒","リキュール"]):\n                continue\n            add_record(brewery, title, "販売中", sid, body, source_url=u)\n'''
if old not in t: raise SystemExit('hakubotan pattern missing')
t=t.replace(old,new)
t=t.replace("if any(x in txt for x in ['セット','酒粕','梅酒','食品','グッズ']):", "if any(x in txt for x in ['セット','酒粕','梅酒','食品','グッズ','最新情報']):")
t=t.replace("if not name:\n            continue", "if not name or '梅酒' in name:\n            continue", 1)
p.write_text(t,encoding='utf-8')
print('collectors patched')
t=p.read_text(encoding='utf-8')
old='''def write_outputs():\n    write_sources()\n    rows = []\n'''
new='''def write_outputs():\n    write_sources()\n    for brewery in BREWERY_CODES:\n        for old_md in (ROOT / brewery).glob("*.md"):\n            if old_md.name != "brewery.md":\n                old_md.unlink()\n    rows = []\n'''
if old not in t: raise SystemExit('write_outputs pattern missing')
t=t.replace(old,new)
needle='''    # 賀茂泉：公式直売所の最新案内に出る季節・蔵元限定商品\n'''
insert='''    # 2012年「瀬戸内紀行」限定セットに含まれた3銘柄\n    u = "https://www.kamotsuru.jp/news/4267/"\n    try:\n        sid, body = save_source(brewery, u, "official_historical")\n        hist = [\n            ("安芸の宮島", "", "66%", "15～16度", "+1.5", "", "上燗 / 人肌燗 / 常温 / 冷"),\n            ("純米吟醸 厳島", "純米吟醸", "55%", "16～17度", "+4", "八反100%", "人肌燗 / 常温 / 冷 / ロック"),\n            ("鞆の浦", "普通酒（生貯蔵酒）", "69%", "14～15度", "+3", "", "常温 / 冷"),\n        ]\n        for name,designation,polish,alc,meter,rice,temp in hist:\n            add_record(brewery, name, "不明", sid, "", "2012年限定セット『瀬戸内紀行』構成酒。現在の販売状態は確認できず", u)\n            r=records[(brewery,normalize_name(name))]\n            r.update({"designation":designation,"polishing_ratio":polish,"alcohol":alc,"sake_meter":meter,"rice":rice,"serving_temperature":temp})\n    except Exception as e: print('kamotsuru set historical',e,flush=True)\n\n'''+needle
if needle not in t: raise SystemExit('manual insertion point missing')
t=t.replace(needle,insert)
p.write_text(t,encoding='utf-8')
print('output and history patched')
