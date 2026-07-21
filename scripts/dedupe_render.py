#!/usr/bin/env python3
"""Deduplicate render targets to one URL per code, preferring .co.kr > .kr > .com."""
import sys

def rank(domain_part):
    """Lower is better."""
    if domain_part.endswith(".co.kr"):
        return 0
    if domain_part.endswith(".kr"):
        return 1
    if domain_part.endswith(".com"):
        return 2
    return 3

best = {}  # code -> (rank, line)
for line in sys.stdin:
    line = line.rstrip("\n")
    f = line.split("\t")
    if len(f) < 3:
        continue
    code, brand, url = f[0], f[1], f[2]
    # extract domain from url
    domain = url.replace("https://", "").replace("http://", "").rstrip("/")
    r = rank(domain)
    if code not in best or r < best[code][0]:
        best[code] = (r, line)

for r, line in best.values():
    print(line)
