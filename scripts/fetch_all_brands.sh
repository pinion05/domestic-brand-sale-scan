#!/usr/bin/env bash
# 무신사 실시간 랭킹 전체 페이지를 긁어 JSON으로 저장 (Phase 1 수집 자동화).
# 핵심: 첫 /pans/ranking 는 overview — 실제 리스트는 /sections/200 엔드포인트.
# 페이지네이션은 **최상위 link.next** 를 따라간다 (data.link.next 아님, hasNext도 무시 — 거짓).
# Usage: fetch_all_brands.sh [outdir]
set -euo pipefail
BASE="https://client.musinsa.com/api/home/web/v5/pans/ranking/sections/200?storeCode=musinsa&gf=A&ageBand=AGE_BAND_ALL"
OUT="${1:-./pages}"
rm -rf "$OUT"; mkdir -p "$OUT"

url="${BASE}&page=1"; i=1
while [ -n "$url" ] && [ "$url" != "null" ]; do
  curl -s "$url" -o "$OUT/p${i}.json"
  url="$(python3 -c "import json;d=json.load(open('$OUT/p${i}.json'));print((d.get('link') or {}).get('next') or '')")"
  i=$((i+1))
  [ "$i" -gt 50 ] && { echo "안전 상한(50) 도달, 중단" >&2; break; }
done
echo "$((i-1)) pages → $OUT/p*.json"
