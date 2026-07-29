#!/usr/bin/env python3
"""Build render-input-knowledge.tsv from the cumulative registry.

Output: code<TAB>brand<TAB>url  for every brand in the registry, so we
re-render known-good URLs fresh each run. Brand names that also appear in
today's ranking get their current code; registry-only brands fall back to a
code derived from their URL host so render artifacts stay stable & unique.
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

base = Path(__file__).resolve().parent.parent
registry = json.loads((base / "data" / "brand-urls.json").read_text(encoding="utf-8"))

# Map today's Korean brand name -> code (preferred when available)
today = {}
for line in (base / "brands.tsv").read_text(encoding="utf-8").splitlines():
    f = line.split("\t")
    if len(f) >= 2:
        today[f[1]] = f[0]


def _code_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    host = re.sub(r"\.(co\.kr|kr|com|net|or\.kr)$", "", host)
    return re.sub(r"[^a-z0-9]+", "", host) or "brand"


rows = []
for brand, url in registry.items():
    code = today.get(brand) or _code_from_url(url)
    rows.append((code, brand, url))

for code, brand, url in rows:
    print(f"{code}\t{brand}\t{url}")

print(f"{len(rows)} known-brand render targets", file=sys.stderr)
