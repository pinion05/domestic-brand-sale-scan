#!/usr/bin/env python3
"""Build docs/sales-YYYY-MM-DD.json from final-verdicts.json."""
import json
from datetime import datetime, timezone, timedelta
from collections import Counter

TODAY = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d')
f = json.load(open('final-verdicts.json', encoding='utf-8'))
yd = json.load(open('docs/sales-2026-08-25.json', encoding='utf-8'))
y_in = {s['brand']: s for s in yd['sales']}

sales = []
for brand, d in f.items():
    if d['verdict'] == 'sale':
        offer = d.get('note') or d['sig'].split('(')[0].rstrip(' ,')
        sales.append({
            'brand': brand,
            'url': d['url'],
            'offer': offer if len(offer) < 80 else d['sig'][:60],
            'max': d.get('pct'),
            'tier': 'exact',
            'condition': d['sig'][:70],
        })
pages = []
for brand, d in f.items():
    if d['verdict'] == 'page':
        pages.append({
            'brand': brand,
            'url': d['url'],
            'offer': d['sig'].split('(')[0].rstrip(' ,'),
            'max': None,
            'tier': 'page',
            'condition': '시즌오프 메뉴/배너 가시 — 할인율 미표기',
        })

# sort: exact by max desc (then name), page by name
sales.sort(key=lambda s: (-(s['max'] or 0), s['brand']))
pages.sort(key=lambda s: s['brand'])
all_sales = sales + pages

excl = {
    '멤버십/쿠폰 노이즈': sorted(b for b, d in f.items() if d['verdict'] == 'member'),
    '도메인 불일치·글로벌·비패션': sorted(
        f"{b} → {d.get('note', '')}" for b, d in f.items() if d['verdict'] == 'reject-id'),
    '과거 캠페인·렌더 실패': sorted(
        f"{b} → {d.get('note', '')}" for b, d in f.items() if d['verdict'] in ('reject-stale', 'new')),
}

now = datetime.now(timezone(timedelta(hours=9)))
doc = {
    'verifiedAt': now.strftime('%Y-%m-%dT%H:%M:%S+09:00'),
    'verifiedLabel': now.strftime('%Y-%m-%d %H:%M KST'),
    'source': {
        'rankingPages': 10,
        'brandCandidates': 440,
        'renderedUrls': 414,
        'finalBrands': len(all_sales),
        'exactOffers': len(sales),
        'openSalePages': len(pages),
    },
    'sales': all_sales,
    'excluded': [{'label': k, 'items': v} for k, v in excl.items()],
}
path = f'docs/sales-{TODAY}.json'
json.dump(doc, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f"wrote {path}: {len(all_sales)} brands ({len(sales)} exact + {len(pages)} page)")
# diff vs yesterday
today_set = {s['brand'] for s in all_sales}
print("NEW:", sorted(today_set - set(y_in)))
print("GONE:", sorted(set(y_in) - today_set))
