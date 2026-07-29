#!/usr/bin/env python3
"""Generate docs/changelog.json by comparing all daily sales JSON files.

For each day, computes:
- diff vs previous day (added / removed brands)
- cumulative brand count trend

Output: docs/changelog.json
Schema:
{
  "generatedAt": "ISO+09:00",
  "entries": [
    {
      "date": "YYYY-MM-DD",
      "total": int,
      "exact": int,
      "page": int,
      "added": ["브랜드명", ...],
      "removed": ["브랜드명", ...],
      "prevTotal": int|null,
      "delta": int
    }
  ]
}
"""
import json
import sys
import glob
import os
import subprocess


def main():
    files = sorted(glob.glob("docs/sales-*.json"))
    if not files:
        print("No sales JSON found.", file=os.stderr)
        return

    days = []
    prev_brands = None
    prev_total = None

    for fpath in files:
        with open(fpath, encoding="utf-8") as h:
            data = json.load(h)

        date = os.path.basename(fpath).replace("sales-", "").replace(".json", "")
        sales = data.get("sales", [])
        source = data.get("source", {})

        brands = set(s["brand"] for s in sales)
        total = source.get("finalBrands", len(sales))
        exact = source.get("exactOffers", len([s for s in sales if s.get("tier") == "exact"]))
        page = source.get("openSalePages", len([s for s in sales if s.get("tier") == "page"]))

        added = sorted(brands - prev_brands) if prev_brands else []
        removed = sorted(prev_brands - brands) if prev_brands else []
        delta = total - prev_total if prev_total is not None else 0

        entry = {
            "date": date,
            "total": total,
            "exact": exact,
            "page": page,
            "added": added,
            "removed": removed,
            "prevTotal": prev_total,
            "delta": delta,
        }
        days.append(entry)
        prev_brands = brands
        prev_total = total

    # Latest first
    days.reverse()

    kst_label = subprocess.check_output(
        ["sh", "-c", "TZ=Asia/Seoul date '+%Y-%m-%dT%H:%M:%S+09:00'"]
    ).decode().strip()

    changelog = {
        "generatedAt": kst_label,
        "entries": days,
    }

    out_path = "docs/changelog.json"
    with open(out_path, "w", encoding="utf-8") as out:
        json.dump(changelog, out, ensure_ascii=False, indent=2)

    print(f"wrote {out_path} ({len(days)} entries)")
    latest = days[0] if days else None
    if latest:
        print(f"  latest: {latest['date']} total={latest['total']} "
              f"(+{len(latest['added'])} new, -{len(latest['removed'])} gone)")


if __name__ == "__main__":
    main()
