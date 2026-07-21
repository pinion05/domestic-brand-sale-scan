#!/usr/bin/env python3
"""Build render input for ALL registry brands (not just today's ranking ∩ registry).

code = from brands.tsv if available, else derived from URL hostname
(so each brand gets a unique artifact key even for Korean-only names).
Output: code<TAB>brand<TAB>url
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

base = Path(__file__).resolve().parent.parent
registry = json.loads((base / "data" / "brand-urls.json").read_text(encoding="utf-8"))

# Map Korean name -> code from brands.tsv
name_to_code = {}
for line in (base / "brands.tsv").read_text(encoding="utf-8").splitlines():
    f = line.split("\t")
    if len(f) >= 2:
        name_to_code[f[1]] = f[0]

def code_from_url(url):
    host = urlparse(url).hostname or "brand"
    # strip leading www. and TLD parts: e.g. graynoise.co.kr -> graynoise
    parts = host.replace("www.", "").split(".")
    return parts[0] if parts else host

seen = set()
count = 0
for brand, url in registry.items():
    code = name_to_code.get(brand) or code_from_url(url)
    # ensure uniqueness
    base_code = code
    n = 2
    while code in seen:
        code = f"{base_code}_{n}"
        n += 1
    seen.add(code)
    count += 1
    print(f"{code}\t{brand}\t{url}")

print(f"{count} registry brands", file=sys.stderr)
