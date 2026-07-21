#!/usr/bin/env python3
"""Filter raw scan hits to CONCRETE sale signals only (de-noise skin noise).

Input: scan TSV (code<TAB>domain<TAB>http<TAB>signals)
Output: code<TAB>brand<TAB>url  (render-ready targets)

Kept (concrete):
  시즌오프, season off, 블랙프라이데이, black friday, final sale,
  end of season sale, X%할인, X% OFF, up to X%, ~X%, 최대 X%

Dropped (skin noise):
  sale alone, coupon/쿠폰, clearance, outlet (unless accompanied by concrete %)
"""
import re
import sys

# Concrete signal regex (matches extract_sale_signals.py _CONCRETE)
CONCRETE = re.compile(
    r"(?:end[\s_-]*of[\s_-]*season[\s_-]*sale"
    r"|시즌\s*오프|season[\s_-]*off"
    r"|블랙[\s_-]*프라이데이|black[\s_-]*friday"
    r"|final[\s_-]*sale"
    r"|up\s*to\s*\d{1,3}\s*%|최대\s*\d{1,3}\s*%|~\s*\d{1,3}\s*%"
    r"|\d{1,3}\s*%\s*(?:할인|off|오프))",
    re.IGNORECASE,
)

# Map brand name lookup from new-brands.tsv (code -> korean name)
def load_brand_names(path):
    names = {}
    try:
        for line in open(path, encoding="utf-8"):
            f = line.rstrip("\n").split("\t")
            if len(f) >= 2:
                names[f[0]] = f[1]
    except FileNotFoundError:
        pass
    return names

def parse_signals(field):
    """Parse 'phrase(count),phrase(count)' into list of phrases."""
    out = []
    for tok in field.split(","):
        tok = tok.strip()
        m = re.match(r"^(.*?)\(\d+\)$", tok)
        out.append(m.group(1) if m else tok)
    return out

def main():
    names = load_brand_names("new-brands.tsv")
    seen = set()
    for line in sys.stdin:
        f = line.rstrip("\n").split("\t")
        if len(f) < 4:
            continue
        code, domain, http, sig = f[0], f[1], f[2], f[3]
        if http not in ("200", "201"):
            continue
        if sig == "-" or not sig.strip():
            continue
        phrases = parse_signals(sig)
        concrete_hits = [p for p in phrases if CONCRETE.search(p)]
        if not concrete_hits:
            continue
        url = f"https://{domain}/"
        key = (code, domain)
        if key in seen:
            continue
        seen.add(key)
        brand = names.get(code, code)
        print(f"{code}\t{brand}\t{url}")

if __name__ == "__main__":
    main()
