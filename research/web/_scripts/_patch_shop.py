from pathlib import Path
p=Path(r'C:\Users\tarou\Downloads\sake-saijo-db\research\web\_scripts\collect_catalog.py')
t=p.read_text(encoding='utf-8')
needle="""    name = re.sub(r'^[〖【](?:日本酒\\s+)?(?:白牡丹|藝陽男山)[〗】]\\s*', '', name)\n"""
insert="""    name = re.sub(r'^\\*+', '', name).strip()\n    name = re.sub(r'^[〖【](?:日本酒\\s+)?(?:白牡丹|藝陽男山)[〗】]\\s*', '', name)\n"""
if needle not in t: raise SystemExit('normalize start missing')
t=t.replace(needle,insert)
needle2="""    name = re.sub(r'^賀茂鶴\\s+吟醸辛口$', '吟醸辛口', name)\n"""
insert2=needle2+"""    name = re.sub(r'^ROCK HOPPER$', '純米吟醸生原酒 ROCK HOPPER', name, flags=re.I)\n    name = re.sub(r'^純米吟醸生原酒\\s+RockHopper$', '純米吟醸生原酒 ROCK HOPPER', name, flags=re.I)\n    name = re.sub(r'\\s*木箱入$', '', name)\n    name = re.sub(r'^大吟醸\\s+いちの雫1\\.8\\s*（しずく酒）$', '大吟醸 いちの雫（しずく酒）', name)\n    name = re.sub(r'^純米サンフレカップ\\s*詰$', '純米サンフレカップ', name)\n    name = re.sub(r'^【純米原酒プレミアム13】', '', name)\n"""
if needle2 not in t: raise SystemExit('normalize insertion missing')
t=t.replace(needle2,insert2)
p.write_text(t,encoding='utf-8')
print('normalize shop patched')
t=p.read_text(encoding='utf-8')
needle="""    print('kamoizumi parsed',flush=True)\n\ndef collect_fukubijin():\n"""
insert="""    shop_url = "https://online.kamoizumi.com/?mode=srh"\n    try:\n        ssid, _ = save_source(brewery, shop_url, "official_shop_catalog")\n        sdoc = html.fromstring((ROOT / brewery / "evidence" / f"{ssid}.html").read_bytes())\n        found = {}\n        for a in sdoc.xpath('//a[@href]'):\n            href = a.get('href') or ''\n            txt = ' '.join(a.text_content().split())\n            if 'pid=' in href and txt and not any(x in txt for x in ['セット','マスク','梅酒','グッズ','頒布会']):\n                found[urljoin(shop_url, href)] = txt\n        for pu,ptxt in found.items():\n            if any(x in ptxt for x in ['菰巻樽','酒粕','甘酒']):\n                continue\n            try:\n                psid,pbody=save_source(brewery,pu,"official_shop_product")\n                add_record(brewery,ptxt,"販売中",psid,pbody,"公式オンラインショップで販売確認",pu)\n            except Exception as e: print('kamoizumi shop product',pu,e,flush=True)\n        print('kamoizumi shop products',len(found),flush=True)\n    except Exception as e: print('kamoizumi shop error',e,flush=True)\n    print('kamoizumi parsed',flush=True)\n\ndef collect_fukubijin():\n"""
if needle not in t: raise SystemExit('kamoizumi collector end missing')
t=t.replace(needle,insert)
# Drop clear packaging/set pseudo-products from current collectors.
t=t.replace("if any(x in title for x in [\"セット\",\"のみくらべ\",\"ギフト\",\"梅酒\",\"甘酒\",\"リキュール\"]):", "if any(x in title for x in [\"セット\",\"のみくらべ\",\"ギフト\",\"アソート\",\"梅酒\",\"甘酒\",\"リキュール\"]):")
t=t.replace("if any(x in txt for x in ['セット','梅酒','甘酒','しゃもじ']): continue", "if any(x in txt for x in ['セット','梅酒','甘酒','しゃもじ','オリジナルラベル']): continue")
p.write_text(t,encoding='utf-8')
print('kamoizumi shop collector patched')
