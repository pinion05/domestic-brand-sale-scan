#!/usr/bin/env python3
"""Search official-store CANDIDATES for brand codes that slug probing missed.

Requires BRAVE_API_KEY. Results are candidates only and still require rendered
brand-identity verification.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Dict, Iterable, List
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

BLOCKED_DOMAINS = {
    "musinsa.com", "29cm.co.kr", "wconcept.co.kr", "zigzag.kr", "kream.co.kr",
    "bunjang.co.kr", "fruitsfamily.com", "con-f.co.kr", "ocokorea.com",
    "4910.kr", "sta1.com", "eqlstore.com", "ssg.com", "lotteon.com",
    "gmarket.co.kr", "auction.co.kr", "11st.co.kr", "coupang.com",
    "daangn.com", "shilladfs.com", "instagram.com", "facebook.com",
    "youtube.com", "tiktok.com", "twitter.com", "x.com", "naver.com",
}


def _blocked(hostname: str) -> bool:
    host = hostname.lower().split(":", 1)[0].removeprefix("www.")
    return any(host == domain or host.endswith(f".{domain}") for domain in BLOCKED_DOMAINS)


def filter_candidates(results: Iterable[dict]) -> List[dict]:
    """Remove marketplaces/social sites while preserving search-result order."""
    filtered = []
    seen_hosts = set()
    for result in results:
        url = result.get("url") or ""
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        host = parsed.hostname.lower().removeprefix("www.")
        if _blocked(host) or host in seen_hosts:
            continue
        seen_hosts.add(host)
        filtered.append(result)
    return filtered


def brave_search(query: str, api_key: str, count: int = 5) -> List[dict]:
    params = urlencode({"q": query, "count": count, "country": "KR", "search_lang": "ko"})
    request = Request(
        f"https://api.search.brave.com/res/v1/web/search?{params}",
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
            "User-Agent": "domestic-brand-sale-scan/1.0",
        },
    )
    for attempt in range(4):
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.load(response)
            return (payload.get("web") or {}).get("results") or []
        except HTTPError as error:
            if error.code == 429 and attempt < 3:
                time.sleep(1.5 * (2 ** attempt))
                continue
            raise
    return []


def _load_brands(path: Path) -> List[tuple]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) >= 2:
            rows.append((fields[0], fields[1]))
    return rows


def _mapped_codes(path: Path) -> set:
    mapped = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        fields = line.split("\t")
        if len(fields) >= 2 and fields[1] != "-":
            mapped.add(fields[0])
    return mapped


def _load_codes(path: Path) -> set:
    return {
        line.split("\t", 1)[0].strip()
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip()
    }


def select_search_targets(brands: List[tuple], mapped_codes: set, forced_codes: set) -> List[tuple]:
    """Return normal misses plus candidates manually rejected after identity review."""
    return [
        (code, name)
        for code, name in brands
        if code not in mapped_codes or code in forced_codes
    ]


def _clean(value: str) -> str:
    return " ".join((value or "").replace("\t", " ").split())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brands", type=Path, help="brands.tsv from parse_brands.py")
    parser.add_argument("scan", type=Path, help="scan.tsv from scan.sh")
    parser.add_argument("--limit", type=int, default=0, help="search only the first N misses (0=all)")
    parser.add_argument("--delay", type=float, default=1.1, help="seconds between Brave requests")
    parser.add_argument("--max-results", type=int, default=3, help="candidate results emitted per brand")
    parser.add_argument("--cache", type=Path, help="optional JSON checkpoint/cache")
    parser.add_argument(
        "--codes",
        type=Path,
        help="codes rejected during identity review; force them into search even if slug probing returned 200",
    )
    args = parser.parse_args(argv)

    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        parser.error("BRAVE_API_KEY is required")

    cache: Dict[str, list] = {}
    if args.cache and args.cache.exists():
        cache = json.loads(args.cache.read_text(encoding="utf-8"))

    mapped = _mapped_codes(args.scan)
    forced = _load_codes(args.codes) if args.codes else set()
    misses = select_search_targets(_load_brands(args.brands), mapped, forced)
    if args.limit > 0:
        misses = misses[: args.limit]

    for index, (code, brand_name) in enumerate(misses):
        if code in cache:
            results = cache[code]
        else:
            search_succeeded = False
            try:
                results = brave_search(f'"{brand_name}" 공식몰', api_key)
                search_succeeded = True
            except Exception as error:
                print(f"{code}: search failed: {error}", file=sys.stderr)
                results = []
            # Do not checkpoint transient/rate-limit failures as permanent misses.
            if search_succeeded:
                cache[code] = results
                if args.cache:
                    args.cache.parent.mkdir(parents=True, exist_ok=True)
                    args.cache.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            if index + 1 < len(misses):
                time.sleep(max(0.0, args.delay))

        for result in filter_candidates(results)[: args.max_results]:
            print(
                code,
                brand_name,
                result.get("url", ""),
                _clean(result.get("title", "")),
                sep="\t",
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
