#!/usr/bin/env python3
"""Build docs/sales-2026-08-28.json from analysis.json (post-verdict)."""
import json
from datetime import datetime, timezone, timedelta

now = datetime.now(timezone(timedelta(hours=9)))
a = json.load(open('analysis.json', encoding='utf-8'))
yd = json.load(open('docs/sales-2026-08-27.json', encoding='utf-8'))

sales, pages = [], []
for x in a['exact']:
    sales.append({'brand': x['brand'], 'url': x['url'], 'offer': x['offer'], 'max': x['max'],
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
        'brandCandidates': 461,
        'renderedUrls': 436,
        'finalBrands': len(all_sales),
        'exactOffers': len(sales),
        'openSalePages': len(pages),
    },
    'sales': all_sales,
    'excluded': [{'label': k, 'items': sorted(v)} for k, v in excl.items()],
}
path = 'docs/sales-2026-08-28.json'
json.dump(doc, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f"wrote {path}: {len(all_sales)} brands ({len(sales)} exact + {len(pages)} page)")
today_set = {s['brand'] for s in all_sales}
print("NEW:", sorted(today_set - {s['brand'] for s in yd['sales']}))
print("GONE:", sorted({s['brand'] for s in yd['sales']} - today_set))
