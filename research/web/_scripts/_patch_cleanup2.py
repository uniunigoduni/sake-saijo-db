from pathlib import Path
p=Path(r'C:\Users\tarou\Downloads\sake-saijo-db\research\web\_scripts\collect_catalog.py')
t=p.read_text(encoding='utf-8')
needle='''    name = re.sub(r'^(?:福美人\\s+)', '', name)\n'''
insert='''    name = re.sub(r'[【〖](?:凍結生酒|日本酒\\s+(?:白牡丹|藝陽男山)|新|蔵元限定|限定酒|あまくちの純米|自宅用におすすめ|ギフトにおすすめ)[】〗]', '', name)\n    name = re.sub(r'\\s+1\\.8(?=\\s*[（(])', ' ', name)\n    name = re.sub(r'\\s+(?:パック|ライトカップ)\\s*(?:詰)?$', '', name)\n    name = re.sub(r'\\s+瓶$', '', name)\n    name = re.sub(r'^超特撰\\s+2本$', '超特撰', name)\n    name = re.sub(r'^純米吟醸\\s+恋華アソート$', '恋華アソート', name)\n    name = re.sub(r'^(?:福美人\\s+)', '', name)\n    name = re.sub(r'\\s*【[^】]*(?:おすすめ|限定)[^】]*】', '', name)\n    name = re.sub(r'\\s*\\[\\s*豪華.*$', '', name)\n    name = re.sub(r'^大吟醸\\s+特製ゴールド賀茂鶴\\s+(?:丸瓶|角瓶)$', '大吟醸 特製ゴールド賀茂鶴', name)\n    name = re.sub(r'^賀茂鶴\\s+吟醸辛口$', '吟醸辛口', name)\n    name = re.sub(r'^亀齢\\s+大吟醸\\s+創$', '大吟醸 創', name)\n    name = re.sub(r'^亀齢\\s+辛口純米\\s+八拾\\(生酒\\)\\(亀齢酒造\\)$', '亀齢 辛口純米 八拾 生酒', name)\n'''
if needle not in t: raise SystemExit('needle missing')
t=t.replace(needle,insert)
p.write_text(t,encoding='utf-8')
print('cleanup2 patched')
t=p.read_text(encoding='utf-8')
needle='''    # 賀茂泉：公式直売所の最新案内に出る季節・蔵元限定商品\n'''
insert='''    # 公式アーカイブで確認できる過去の限定酒\n    history_pages = [\n        ("https://www.kamotsuru.jp/sakematsuri/limited/", [\n            ("酒まつり2020 純米大吟醸 広系酒33号", "2020年10月限定販売。現在状態不明"),\n            ("酒まつり2020 大吟醸 のん太ラベル", "2020年10月限定販売。現在状態不明"),\n            ("見学室直売所 一周年記念酒 雄町", "2020年限定・シリアルナンバー入。現在状態不明"),\n            ("熟成大吟醸（2020酒まつり）", "2020年本数限定・シリアルナンバー入。現在状態不明"),\n        ]),\n        ("https://www.kamotsuru.jp/news/9491/", [\n            ("酒まつり限定 純米大吟醸 山田錦（2018）", "2018酒まつり限定。現在状態不明"),\n        ]),\n    ]\n    for hu, items in history_pages:\n        try:\n            hsid,hbody=save_source(brewery,hu,"official_historical")\n            for hname,hnote in items: add_record(brewery,hname,"不明",hsid,hbody,hnote,hu)\n        except Exception as e: print('kamotsuru archive history',hu,e,flush=True)\n\n'''+needle
if needle not in t: raise SystemExit('kamotsuru history insertion missing')
t=t.replace(needle,insert)
p.write_text(t,encoding='utf-8')
print('kamotsuru archives patched')
t=p.read_text(encoding='utf-8')
needle='''def collect_sanyotsuru():\n'''
insert='''def collect_extra_history():\n    extra = [\n        ("白牡丹酒造", "https://www.hakubotan.co.jp/酒まつり限定　にごり酒　ご予約受付中＆送料無料キャンペーン　/",\n         [("酒まつり限定 純米にごり酒", "2024年公式案内。例年の酒まつり限定、現在状態不明")]),\n        ("亀齢酒造", "https://kireikireikirei.jimdofree.com/酒まつり情報-２０２５/",\n         [("亀齢 酒まつり限定 ひやおろし", "2025酒まつり限定、現在状態不明"),\n          ("亀齢 酒まつり限定 純米原酒", "2025酒まつり限定、現在状態不明")]),\n        ("西條鶴醸造", "https://saijotsuru.co.jp/?mode=f12",\n         [("鑑評会出品酒", "2025酒まつり限定販売、現在状態不明")]),\n        ("西條鶴醸造", "https://saijotsuru.co.jp/?mode=f10",\n         [("斗ビン取り純米大吟醸", "2022酒まつり限定販売、現在状態不明"),\n          ("愛山純米酒75", "2022酒まつりで販売確認。現行の愛山70とは別仕様、現在状態不明")]),\n    ]\n    for brewery,u,items in extra:\n        try:\n            sid,body=save_source(brewery,u,"official_historical")\n            for name,note in items: add_record(brewery,name,"不明",sid,body,note,u)\n        except Exception as e: print('extra history',brewery,u,e,flush=True)\n\n'''+needle
if needle not in t: raise SystemExit('extra history insertion missing')
t=t.replace(needle,insert)
t=t.replace('collect_fukubijin,collect_kirei,collect_sanyotsuru,collect_manual_official]', 'collect_fukubijin,collect_kirei,collect_extra_history,collect_sanyotsuru,collect_manual_official]')
p.write_text(t,encoding='utf-8')
print('extra histories patched')
