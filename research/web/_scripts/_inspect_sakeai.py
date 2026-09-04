import json
import requests
from lxml import html

urls = [
    'https://sakeai.com/brand/3501',
    'https://sakeai.com/brand/3502',
    'https://sakeai.com/brand/2775',
    'https://sakeai.com/brand/2788',
]
for u in urls:
    text = requests.get(u, timeout=30).content.decode('utf-8', 'replace')
    doc = html.fromstring(text)
    vals = []
    for a in doc.xpath('//a[contains(@href,"/sake/")]'):
        name = ' '.join(a.text_content().split())
        href = a.get('href')
        if name and (name, href) not in vals:
            vals.append((name, href))
    print('\n' + u + ' count=' + str(len(vals)))
    print(json.dumps(vals, ensure_ascii=True, indent=1))
