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
# Rendered URLs = rows actually rendered this run (main + missing summaries)
def _summary_rows(path):
    return max(0, len(path.read_text(encoding="utf-8").splitlines()) - 1) if path.exists() else 0
rendered_urls = _summary_rows(base / "rendered" / "summary.tsv") + _summary_rows(base / "rendered-missing" / "summary.tsv")

# Excluded groups (analysis.json uses rejected_* keys from analyze_results.py)
excluded = [
    {
        "label": "현재 화면에 구체 세일 없음",
        "items": sorted(analysis.get("rejected_novisual", [])),
    },
    {
        "label": "도메인 불일치·글로벌·비패션",
        "items": sorted(analysis.get("rejected_global", [])),
    },
    {
        "label": "멤버십/쿠폰 노이즈",
        "items": sorted(analysis.get("rejected_noise", [])),
    },
    {
        "label": "과거 캠페인·렌더 실패",
        "items": sorted(analysis.get("rejected_stale", [])),
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
