#!/usr/bin/env python3
"""Build render-input-knowledge.tsv from today's brands.tsv ∩ registry.

Output: code<TAB>brand<TAB>url  (only brands present in BOTH today's ranking
and the cumulative registry, so we re-render known-good URLs fresh each run).
"""
import json
import sys
from pathlib import Path

base = Path(__file__).resolve().parent.parent
registry = json.loads((base / "data" / "brand-urls.json").read_text(encoding="utf-8"))

# Map today's Korean brand name -> code
today = {}
for line in (base / "brands.tsv").read_text(encoding="utf-8").splitlines():
    f = line.split("\t")
    if len(f) >= 2:
        today[f[1]] = f[0]

rows = []
for brand, url in registry.items():
    code = today.get(brand)
    if code:
        rows.append((code, brand, url))

for code, brand, url in rows:
    print(f"{code}\t{brand}\t{url}")

print(f"{len(rows)} known-brand render targets", file=sys.stderr)
