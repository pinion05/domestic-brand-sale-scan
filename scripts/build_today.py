#!/usr/bin/env python3
"""Build docs/sales-2026-08-27.json from analysis.json (post-verdict)."""
import json
from datetime import datetime, timezone, timedelta

# manual max overrides verified in today's rendered artifacts
MAX_OVERRIDE = {"무아르무스": 30}   # TIME SALE 20~30% countdown, not the 10% channel coupon
OFFER_OVERRIDE = {"무아르무스": "TIME SALE 30% · 20%"}

now = datetime.now(timezone(timedelta(hours=9)))
a = json.load(open('analysis.json', encoding='utf-8'))
yd = json.load(open('docs/sales-2026-08-26.json', encoding='utf-8'))
y_in = {s['brand']: s for s in yd['sales']}

sales, pages = [], []
for x in a['exact']:
    b = x['brand']
    mx = MAX_OVERRIDE.get(b, x['max'])
    offer = OFFER_OVERRIDE.get(b) or x['offer']
    sales.append({'brand': b, 'url': x['url'], 'offer': offer, 'max': mx,
                  'tier': 'exact', 'condition': x['condition']})
for x in a['page']:
    pages.append({'brand': x['brand'], 'url': x['url'],
                  'offer': x['offer'].split('(')[0].rstrip(' ,') or '시즌오프',
                  'max': None, 'tier': 'page',
                  'condition': '시즌오프 메뉴/배너 가시 — 할인율 미표기'})
sales.sort(key=lambda s: (-(s['max'] or 0), s['brand']))
pages.sort(key=lambda s: s['brand'])
all_sales = sales + pages

excl = {
    '멤버십/쿠폰 노이즈': a.get('excluded_membership', []),
    '도메인 불일치·글로벌·비패션': a.get('excluded_identity', []),
    '과거 캠페인·렌더 실패': a.get('excluded_stale', []),
}

doc = {
    'verifiedAt': now.strftime('%Y-%m-%dT%H:%M:%S+09:00'),
    'verifiedLabel': now.strftime('%Y-%m-%d %H:%M KST'),
    'source': {
        'rankingPages': 10,
        'brandCandidates': 441,
        'renderedUrls': 371,
        'finalBrands': len(all_sales),
        'exactOffers': len(sales),
        'openSalePages': len(pages),
    },
    'sales': all_sales,
    'excluded': [{'label': k, 'items': sorted(v)} for k, v in excl.items()],
}
path = 'docs/sales-2026-08-27.json'
json.dump(doc, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f"wrote {path}: {len(all_sales)} brands ({len(sales)} exact + {len(pages)} page)")
today_set = {s['brand'] for s in all_sales}
print("NEW:", sorted(today_set - set(y_in)))
print("GONE:", sorted(set(y_in) - today_set))
