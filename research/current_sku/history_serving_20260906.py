from pathlib import Path
import re, pandas as pd
ROOT=Path(r'C:\Users\tarou\Downloads\sake-saijo-db')
RDIR=ROOT/'research'/'history_serving_20260906'
BH=pd.read_csv(RDIR/'brewery_history.csv',encoding='utf-8-sig').fillna('')
BR=pd.read_csv(RDIR/'brand_history.csv',encoding='utf-8-sig').fillna('')
SCAN=pd.read_csv(RDIR/'official_serving_scan.csv',encoding='utf-8-sig').fillna('')
BHM=BH.set_index('酒蔵')['酒蔵の歴史'].to_dict()
BRM={(r['酒蔵'],r['ブランド']):r['銘柄の歴史'] for _,r in BR.iterrows()}
SCANM={(r['酒蔵'],r['ブランド'],r['商品名']):(r['serving_terms'],r['出典URL']) for _,r in SCAN.iterrows()}
OV={
('賀茂鶴酒造','酒中在心 鶯 純米大吟醸 山田錦'):'10〜15℃程度の冷酒で、華やかな香りと米のふくらみをまず楽しむのがおすすめ。常温に近づくにつれて旨味が広がるため、冷酒から少しずつ温度を上げながら飲むと変化が分かりやすい。',
('賀茂鶴酒造','酒中在心 橙 純米吟醸 生もと 八反35号'):'冷酒から常温、ぬる燗まで温度による変化を楽しめる。まず10〜15℃程度で酸と旨味のバランスを見て、食中は常温、米の旨味をより出したいときは40℃前後のぬる燗がおすすめ。',
('賀茂鶴酒造','酒中在心 藍 特別純米酒 生もと 雄町'):'蔵元が常温を一押しとしているため、まず冷やし過ぎず常温で旨味とキレを味わうのがおすすめ。軽く冷やすと輪郭が締まり、40℃前後のぬる燗では生酛らしい旨味がやわらかく広がる。',
('賀茂鶴酒造','酒中在心 茜 純米酒 広島錦'):'燗で持ち味が出る純米酒。40℃前後のぬる燗から試し、よりキレを出したいときは45〜50℃程度まで温めるのがおすすめ。食中酒として、温度を上げながら味の締まり方を比べるとよい。',
('今田酒造本店','FUKUCHO LEGACY I'):'冷酒または常温で、長期熟成由来の複雑さと貴醸酒の甘やかさをゆっくり味わうのがおすすめ。冷やし過ぎず、小ぶりのワイングラスなどで少量ずつ温度変化を追うと余韻を感じやすい。',
('今田酒造本店','FUKUCHO LEGACY II'):'冷酒または常温で、熟成酒の複雑味と白麹由来の酸味のバランスを楽しむのがおすすめ。食事と合わせる場合は冷酒から始め、少し温度が上がった状態で甘味と酸のまとまりを比べるとよい。',
}
OV.update({
('柄酒造','9代目於多福 純米 火入れ'):'蔵元表示どおり冷酒を第一候補にし、10〜15℃程度で米の旨味とすっきりした辛口の輪郭を楽しむのがおすすめ。常温でもまとまりが出るため、普段の食中酒なら冷酒から常温への変化も試しやすい。',
('柄酒造','9代目於多福 純米吟醸 火入れ'):'蔵元が冷酒を最も推しているため、10〜15℃程度に冷やして香りと辛口のバランスを楽しむのがおすすめ。冷やし過ぎず、グラスの中で常温に近づく変化も追うと旨味が分かりやすい。',
('柄酒造','9代目於多福 特別純米 火入れ'):'ラインナップ中でも特に辛口のため、まず10〜15℃程度の冷酒でシャープな後口を楽しむのがおすすめ。常温でも飲めるので、食中では温度を少し戻しながら米の旨味とのバランスを見るとよい。',
('柄酒造','9代目於多福 純米大吟醸 火入れ'):'香りを活かすため、10〜15℃程度の冷酒が第一候補。冷やし過ぎずにゆっくり飲み、常温へ近づくにつれて香りと米の旨味が広がる変化を楽しむのがおすすめ。',
('賀茂泉酒造','COKUN'):'8度の低アルコールと甘酸っぱさを活かすため、よく冷やしてワイングラスや小ぶりのグラスで飲むのがおすすめ。食前酒や軽いデザート酒のように少量ずつ楽しむと、ベリー系を思わせる酸味と甘味が分かりやすい。',
('賀茂泉酒造','純米吟醸生原酒 ROCK HOPPER'):'しっかり冷やした冷酒で、爽やかな香りと生原酒のふくらみを楽しむのがおすすめ。原酒の飲みごたえが強く感じられるときは、大きめの氷を一つ入れたロックにすると軽快さが出る。',
('賀茂泉酒造','Rock Hopper Moon Walk'):'秋酒らしいまろやかさを活かすため、10〜15℃程度の冷酒から始め、少しずつ常温に近づけて飲むのがおすすめ。17度の原酒なので、味が強く感じる場合は大きめの氷を一つ入れる飲み方も合う。',
})
def num(v):
    s=str(v).translate(str.maketrans('０１２３４５６７８９＋－．','0123456789+-.'))
    m=re.search(r'[+-]?\d+(?:\.\d+)?',s)
    return float(m.group()) if m else None

def modes(row):
    raw=str(row.get('おすすめの飲み方','') or row.get('飲み方','')).strip()
    if raw and raw!='要確認': return [x.strip() for x in raw.split('/') if x.strip()], '既存の飲み方情報'
    terms,url=SCANM.get((row.get('酒蔵',''),row.get('ブランド',''),row.get('商品名','')),('',''))
    generic=any(x in url for x in ('/line_up/Limited/','/collections/','/SHOP/346437/','/SHOP/346519/','/SHOP/346440/'))
    if terms and not generic:
        xs=[x.strip() for x in terms.split('/') if x.strip() and x.strip() not in ('飲み方','飲み頃','冷やして')]
        if xs: return xs, '公式ページ再走査'
    return [], '推論'

def style_reason(row):
    name=str(row.get('商品名','')); cat=str(row.get('分類','')); sm=num(row.get('日本酒度','')); alc=num(row.get('アルコール度数',''))
    if any(x in name for x in ('スパークリング','微発泡','にごり')): return '発泡感やにごりの口当たりを活かす'
    if any(x in name for x in ('生酒','生原酒','しぼりたて','あらばしり','生貯蔵')): return 'フレッシュさを活かす'
    if any(x in name for x in ('ひやおろし','秋あがり')): return '熟成でまとまった旨味を引き出す'
    if '古酒' in name or '熟成' in name or 'LEGACY' in name: return '熟成由来の複雑さをゆっくり開かせる'
    if '大吟醸' in cat: return '繊細な香りと上品な旨味を活かす'
    if '吟醸' in cat: return '吟醸香と軽快な旨味のバランスを活かす'
    if '純米' in cat: return '米の旨味と酸のふくらみを引き出す'
    if '本醸造' in cat or '普通酒' in cat: return '日常酒らしいキレと旨味を引き出す'
    if alc is not None and alc<=10: return '低アルコールの軽やかさを活かす'
    if sm is not None and sm>=5: return '辛口のキレを活かす'
    return '香味のまとまりを引き出す'
def inferred_temp(row):
    name=str(row.get('商品名','')); cat=str(row.get('分類','')); sm=num(row.get('日本酒度','')); alc=num(row.get('アルコール度数',''))
    if any(x in name for x in ('スパークリング','微発泡','にごり','生酒','生原酒','しぼりたて','あらばしり','生貯蔵','夏')): return 'よく冷やした5〜10℃程度の冷酒'
    if 'お燗' in name: return '40〜50℃程度の燗酒'
    if any(x in name for x in ('ひやおろし','秋あがり')): return '常温から40℃前後のぬる燗'
    if '古酒' in name or '熟成' in name or 'LEGACY' in name: return '10〜15℃程度の冷酒から常温'
    if '大吟醸' in cat: return '10〜15℃程度の冷酒'
    if '吟醸' in cat: return '10〜15℃程度の冷酒'
    if '純米' in cat:
        return '10〜15℃程度の冷酒' if (sm is not None and sm>=5) else '常温から40℃前後のぬる燗'
    if '本醸造' in cat or '普通酒' in cat: return '常温から40〜50℃程度の燗酒'
    if alc is not None and alc<=10: return 'よく冷やした冷酒'
    return '10〜15℃程度の冷酒から常温'

def prose(row):
    key=(row.get('酒蔵',''),row.get('商品名',''))
    if key in OV: return OV[key], '公式・個別確認'
    ms,basis=modes(row); name=str(row.get('商品名','')); cat=str(row.get('分類','')); reason=style_reason(row)
    joined=' / '.join(ms)
    if ms:
        if any(x in name for x in ('生酒','生原酒','しぼりたて','あらばしり','スパークリング','微発泡','にごり')) and ('冷酒' in joined or '冷やして' in joined):
            return f'まずは5〜10℃程度までしっかり冷やし、{reason}のがおすすめ。温度が上がり過ぎないうちに飲み、原酒で強く感じる場合に「ロック」の記載がある商品は大きめの氷を一つ加えると飲みやすい。',basis
        if '大吟醸' in cat or '吟醸' in cat:
            if '冷酒' in joined or '冷やして' in joined:
                tail='。常温も適温に含まれるため、グラスの中で少し温度を上げて香りと旨味の変化を比べるとよい' if '常温' in joined else ''
                return f'10〜15℃程度の冷酒を起点に、{reason}のがおすすめ{tail}。',basis
        if any(x in joined for x in ('ぬる燗','熱燗','燗酒','上燗')):
            if '冷酒' in joined:
                return f'冷酒では輪郭をすっきりと、40℃前後のぬる燗から燗酒では{reason}飲み方がおすすめ。食事に合わせるなら冷酒と燗の両方を試し、好みの温度帯を探すとよい。',basis
            return f'常温から40℃前後のぬる燗を中心に、{reason}のがおすすめ。より熱い燗も適温に含まれる場合は、45〜50℃程度まで上げて後口の締まり方を比べるとよい。',basis
        if '常温' in joined and '冷酒' not in joined:
            return f'冷やし過ぎず常温を基準に、{reason}のがおすすめ。香りを強く出し過ぎず、食事と一緒にゆっくり温度変化を楽しむとよい。',basis
        if '冷酒' in joined or '冷やして' in joined:
            return f'10〜15℃程度に冷やして、{reason}のがおすすめ。冷やし過ぎると香りや旨味が閉じやすいため、少しずつ温度が上がる変化も楽しむとよい。',basis
    temp=inferred_temp(row)
    return f'公開情報で明確な推奨温度を確認できないため酒質からの目安。{temp}を起点に、{reason}飲み方がおすすめ。少量ずつ温度を変え、香り・甘味・酸味・キレのバランスが最も整うところを探すとよい。','推論'
PH={
('賀茂鶴酒造','大吟醸 特製ゴールド賀茂鶴'):'1958（昭和33）年、大吟醸酒の先駆けとして発売。1974年の昭和天皇ご夫妻の金婚式を機に桜の花びら型金箔が考案され、1997年から市販品にも採用された。2014年には日米首脳の会食でも供され、現在まで続くロングセラーである。',
('賀茂鶴酒造','純米吟醸 一滴入魂'):'2014年・2018年のワイングラスでおいしい日本酒アワード金賞、2016年の全国燗酒コンテスト最高金賞などを受賞。2020年度にはANA国際線ビジネスクラスにも採用され、冷酒・燗の双方で評価を積み重ねてきた純米吟醸である。',
('賀茂鶴酒造','純米大吟醸 瑞兆賀茂鶴'):'現代の名工・黄綬褒章受章者の幸田邦昭名誉杜氏が、50余年の経験を注いで醸した酒を商品化し、2010年4月12日に販売を開始した純米大吟醸。発売当初は限定1000本として案内された。',
('白牡丹酒造','Paeon(ピオン)'):'「しぼりたてのフレッシュなお酒で食卓に小さな幸せを」を掲げる白牡丹の新シリーズ。千本錦と広島令和一号酵母を使い、ワイングラスでおいしい日本酒アワード2026のプレミアム純米部門で最高金賞を受賞した。',
('白牡丹酒造','純米吟醸萌えいぶき'):'広島県・JA・広島県酒造組合などが約10年かけて開発した酒造好適米「萌えいぶき」を100%使用し、2024年4月22日に出荷を開始した純米吟醸。新しい広島酒米の特徴を商品として示す位置づけを持つ。',
('西條鶴醸造','純米大吟醸原酒「神髄」'):'西條鶴が「全てを凝縮した一本」と位置づける代表的な純米大吟醸原酒。モンドセレクションで1999年から25年連続金賞以上を受賞し、2023年には25年間の品質維持に対するプレステージトロフィーを受賞した。',
('柄酒造','9代目於多福 protos. 火入れ'):'9代目杜氏が数学の「素数」をテーマにスペックを設計した9代目於多福シリーズの商品で、火入れ720mlは2026年7月22日に発売開始された。伝統銘柄に新しい発想を重ねる現行シリーズを象徴する一本。',
('柄酒造','9代目於多福 純米 つきあかり'):'9代目於多福の季節商品として2026年9月3日に発売開始された純米酒。9代目蔵元・杜氏が展開する新しい於多福ラインの直近の商品である。',
('福美人酒造','大吟醸 西條酒造学校'):'福美人が創業当初から高い醸造技術で全国の酒造技術者を育て、「西條酒造学校」と呼ばれた歴史を商品名に受け継ぐ大吟醸。蔵そのものの技術史を銘柄名として伝える商品である。',
('賀茂泉酒造','朱泉本仕込'):'賀茂泉は1965年頃から純米醸造の復活に取り組み、1972年に「本仕込賀茂泉」を発売した。現行の「朱泉本仕込」は蔵が「賀茂泉を代表するお酒」と明記する、本仕込・純米醸造の歴史を現在へ伝える中心商品である。',
}

def apply(products):
    audit=[]
    for area,df in list(products.items()):
        df=df.copy().fillna('')
        df['酒蔵の歴史']=df['酒蔵'].map(BHM).fillna('')
        histories=[]
        for _,r in df.iterrows():
            key=(r['酒蔵'],r['商品名'])
            if key in PH:
                histories.append(PH[key])
            elif r['酒蔵']=='今田酒造本店' and '八反草' in r['商品名']:
                histories.append('富久長は100年以上姿を消していた広島最古の在来酒米「八反草」を、ひと握りの種もみから増やし2001年より復活栽培した。'+('この純米吟醸はその八反草を伝統の吟醸造りで醸し、現在は富久長のフラッグシップとして国内外で支持されている。' if r['商品名']=='八反草 純米吟醸' else 'この商品は、復活した八反草の個性を異なる精米・酒母・季節設計で表現する一連の商品群に位置づけられる。'))
            elif r['酒蔵']=='白牡丹酒造' and r['ブランド']=='藝陽男山':
                histories.append(BRM.get((r['酒蔵'],r['ブランド']),'')+' 現行の夏仕込み系列は、2023年夏に白牡丹が初めて仕込んだ生酛純米酒の挑戦を継続・発展させた商品群である。')
            else:
                base=BRM.get((r['酒蔵'],r['ブランド']),'')
                histories.append(base+' 個別商品「'+str(r['商品名'])+'」の発売年・開発経緯は、確認できる公開情報では特定できない。')
        df['銘柄の歴史']=histories
        recs=[]
        for _,r in df.iterrows():
            text,basis=prose(r); recs.append(text)
            terms,scanurl=SCANM.get((r['酒蔵'],r['ブランド'],r['商品名']),('',''))
            audit.append({'エリア':area,'酒蔵':r['酒蔵'],'ブランド':r['ブランド'],'商品名':r['商品名'],
                          '元の飲み方':r.get('おすすめの飲み方',''),'元の飲み方情報':r.get('飲み方情報',''),'元の飲み方出典URL':r.get('飲み方出典URL',''),
                          'おすすめの飲み方':text,'根拠区分':basis,'公式ページ検出語':terms,
                          '商品出典URL':r.get('出典URL',''),'公式再走査URL':scanurl})
        df['おすすめの飲み方（文章）']=recs
        products[area]=df
        df.to_csv(ROOT/'research'/'current_sku'/f'boss_{area}_products.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(audit).to_csv(RDIR/'product_serving_recommendations.csv',index=False,encoding='utf-8-sig')
    return products
