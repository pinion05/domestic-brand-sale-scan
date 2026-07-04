#!/bin/bash
# Probe official store for a brand code, count sale keywords.
# Usage: scan.sh <brand_code>
# Output TSV: code \t domain(or -) \t httpcode \t keywordcounts(or -)
code="$1"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0 Safari/537.36"
KW='세일|시즌[ :]*오프|할인|행사|sale|쿠폰|coupon|clearance|outlet|아웃렛|블랙[ -]?프라이데이|black[ -]?friday|final[ -]?sale|up to [0-9]+%|[0-9]+%[ ]*(할인|off|오프)'
for dom in "$code.com" "$code.co.kr" "$code.kr"; do
  url="https://$dom"
  hc=$(curl -sI -L --max-time 7 -A "$UA" "$url" -o /dev/null -w "%{http_code}" 2>/dev/null)
  if [ "$hc" = "200" ] || [ "$hc" = "201" ]; then
    body=$(curl -s -L --max-time 12 -A "$UA" "$url" 2>/dev/null)
    hits=$(printf '%s' "$body" | grep -oiE "$KW" | sort | uniq -c | sort -rn \
           | awk '{print $2"("$1")"}' | tr '\n' ',' | sed 's/,$//')
    printf '%s\t%s\t%s\t%s\n' "$code" "$dom" "$hc" "$hits"
    exit 0
  fi
done
printf '%s\t-\t-\t-\n' "$code"
