#!/usr/bin/env python3
"""Generate docs/sales-YYYY-MM-DD.json from analysis.json."""
import json
import subprocess
from datetime import datetime
from pathlib import Path

base = Path(__file__).resolve().parent.parent
analysis = json.loads((base / "analysis.json").read_text(encoding="utf-8"))

today = datetime.now().strftime("%Y-%m-%d")
now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
now_label = datetime.now().strftime("%Y-%m-%d %H:%M KST")

exact = analysis["exact"]
page = analysis["page"]

sales = []
# Deduplicate by brand name (keep highest-max / first occurrence).
seen_brands = set()
for s in sorted(exact, key=lambda x: (-(x["max"] or 0), x["brand"])):
    if s["brand"] in seen_brands:
        continue
    seen_brands.add(s["brand"])
    sales.append({
        "brand": s["brand"],
        "url": s["url"],
        "offer": s["offer"],
        "max": s["max"],
        "tier": "exact",
        "condition": s["condition"],
    })
for s in sorted(page, key=lambda x: x["brand"]):
    if s["brand"] in seen_brands:
        continue
    seen_brands.add(s["brand"])
    sales.append({
        "brand": s["brand"],
        "url": s["url"],
        "offer": s["offer"],
        "max": s["max"],
        "tier": "page",
        "condition": s["condition"],
    })

# Count pages fetched
pages_count = len(list((base / "pages").glob("p*.json")))
brand_candidates = len((base / "brands.tsv").read_text(encoding="utf-8").splitlines())
rendered_urls = len((base / "render-input-full.tsv").read_text(encoding="utf-8").splitlines())

# Excluded groups
excluded = [
    {
        "label": "현재 화면에 구체 세일 없음",
        "items": sorted(analysis["rejected_novisual"]),
    },
    {
        "label": "도메인 불일치·글로벌·비패션",
        "items": sorted(analysis["rejected_global"]),
    },
]

doc = {
    "verifiedAt": now_iso,
    "verifiedLabel": now_label,
    "source": {
        "rankingPages": pages_count,
        "brandCandidates": brand_candidates,
        "renderedUrls": rendered_urls,
        "finalBrands": len(sales),
        "exactOffers": len([s for s in sales if s["tier"] == "exact"]),
        "openSalePages": len([s for s in sales if s["tier"] == "page"]),
    },
    "sales": sales,
    "excluded": excluded,
}

out = base / "docs" / f"sales-{today}.json"
out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"→ {out} ({len(exact)} exact + {len(page)} page = {len(exact)+len(page)} brands)")
