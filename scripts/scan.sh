#!/usr/bin/env bash
# Probe same-slug domain CANDIDATES and count sale phrases.
# A 200 response is not proof of an official store; render and identity-check it.
# Usage: scan.sh [--all] <brand_code>
# Output TSV: code \t candidate-domain(or -) \t httpcode \t keywordcounts(or -)
set -u

all=0
if [ "${1:-}" = "--all" ]; then
  all=1
  shift
fi
code="${1:?Usage: scan.sh [--all] <brand_code>}"
script_dir="$(cd "$(dirname "$0")" && pwd)"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0 Safari/537.36"
found=0

# Korean ccTLDs are higher-confidence candidates. --all avoids silently
# accepting the first unrelated domain that happens to return HTTP 200.
for dom in "$code.co.kr" "$code.kr" "$code.com"; do
  url="https://$dom"
  body_file=$(mktemp "${TMPDIR:-/tmp}/sale-scan.XXXXXX")
  # One GET both catches sites that reject HEAD and avoids downloading twice.
  hc=$(curl -s -L --max-time 12 -A "$UA" "$url" -o "$body_file" -w "%{http_code}" 2>/dev/null)
  if [ "$hc" = "200" ] || [ "$hc" = "201" ]; then
    hits=$(python3 "$script_dir/extract_sale_signals.py" < "$body_file")
    [ -n "$hits" ] || hits="-"
    printf '%s\t%s\t%s\t%s\n' "$code" "$dom" "$hc" "$hits"
    found=1
    rm -f "$body_file"
    [ "$all" -eq 1 ] || exit 0
  else
    rm -f "$body_file"
  fi
done

[ "$found" -eq 1 ] || printf '%s\t-\t-\t-\n' "$code"
