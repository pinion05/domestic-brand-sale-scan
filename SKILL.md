---
name: domestic-brand-sale-scan
description: 'Use when investigating which Korean domestic fashion brands currently run sales on their own official stores, especially broad multi-brand sweeps, 공홈 세일/블프/시즌오프 research, or requests that must exclude platform-internal promotions.'
---

# Domestic Brand Sale Scan

## Overview
Find which Korean domestic fashion brands are running sales on their **official stores** (공홈), not platforms. Pipeline: enumerate brands at scale via Musinsa's API → map each to its official store → scan sale keywords → verify hits by rendering.

**Core insights:**
- **The Musinsa API/URL is ONE EXAMPLE — the real method is "capture the platform's own brand-list API → map brand identifier → official domain."** Other Korean commerce platforms need their own API captured fresh.
- `brands.tsv` contains **domestic-fashion candidates**, not proven Korean brands. The parser subtracts known global/non-fashion slugs; identity and nationality still require verification.
- English slugs often resemble official domains, but **HTTP 200 only means domain candidate**. A wrong company/parked site can return 200.
- `sale`/`coupon`/`clearance` are shopping-skin noise. Keep concrete phrases, then require browser-visible evidence and a current-year/date check.
- Raw HTML may retain stale hidden campaigns; SPA raw HTML may contain nothing. Rendering is the final evidence surface.

**Tool requirement:** `agent-browser` is needed to **discover** the brand-list API (Phase 1, `network requests`) and to **render SPA stores** for verification (Phase 5). Once the API URL is known, Phase 1 enumeration runs with plain `curl` (the ranking API returns JSON) — so agent-browser is *discover + verify*, NOT *call*. curl-only still fails on SPA store verification (29CM, imweb) and on platforms whose API you haven't captured.

## When to Use
- "국내/도메스틱 패션 브랜드 중 세일/블프 중인 곳 조사"
- User wants **official-store** sales, NOT platform-internal (Musinsa/29CM/W컨셉) sales
- Many brands needed (broad sweep), not a single brand lookup

**When NOT to use:** one specific brand's sale (just open its official store). Platform-wide sales (use `web_search`).

## Pipeline

### Phase 1 — Enumerate brands (API, not scraping)
`agent-browser`로 랭킹 페이지를 열고 XHR 캡처:
```bash
agent-browser open "https://www.musinsa.com/main/musinsa/ranking"
agent-browser network requests --clear; agent-browser open "https://www.musinsa.com/main/musinsa/ranking"
agent-browser network requests | grep client.musinsa
# overview(첫 화면): /pans/ranking?storeCode=musinsa&gf=A&ageBand=AGE_BAND_ALL
# 실제 리스트+페이지네이션: /pans/ranking/sections/200?...page=N
```
**⚠️ 페이지네이션 — 여기를 잘못하면 브랜드가 ~1/3로 떨어진다 (가장 흔한 함정):**
- `/pans/ranking`(overview) 응답엔 다음 페이지가 **없다**. 실제 리스트는 `/sections/200` 엔드포인트.
- 페이지네이션 키 = **최상위 `link.next`** (`d['link']['next']`). ❌ `data.link.next`(=null), ❌ `hasNext`(False인데 next가 있음 → 무시).
- **반드시 `./scripts/fetch_all_brands.sh` 사용** — 첫 페이지부터 `link.next` 끝까지(≈10페이지) 자동 루프. 수동으로 1페이지만 부르면 금지(브랜드 ~1/3 이하로 급감).

```bash
./scripts/fetch_all_brands.sh pages/                    # → pages/p1..p10.json
./scripts/parse_brands.py pages/p*.json > brands.tsv    # best-effort 국내 패션 후보 (~370)
```
`parse_brands.py`는 `brandName` + `/brand/{slug}`를 추출하고 알려진 글로벌/비패션 slug만 제외한다. **실시간 랭킹은 전체 브랜드 카탈로그가 아니다.** 넓은 조사라면 여러 플랫폼 결과, 이전 실행 캐시, 주요 브랜드 seed를 합집합으로 사용한다.

**⚠️ Platform generalization:** the `client.musinsa.com` URL + `parse_brands.py` schema (`data.modules[].items[].info`, `onClickBrandName.url=/brand/{slug}`) are **Musinsa-specific**. For 29CM/W컨셉/에이블리: capture THAT platform's brand-list API the same way (`network requests` on its ranking/brand page), and rewrite the parser for its response shape. Note the **identifier type**:
- Musinsa, W컨셉, 에이블리 → English slug (`/brand/{slug}`) → Phase 2 probe works
- 29CM → numeric `frontBrandNo` (`/store/brand/36324`) → Phase 2 probe is MEANINGLESS, use search
- Capture `brandName` (Korean) regardless — it's the fallback key for search mapping.

### Scoping by style/category (스트릿/여성복/아메카지 한정)
Musinsa's ranking API has **no style filter** — `categoryCode` is product-type (상의/아우터/바지), not style (스트릿/캐주얼/아메카지), and brand items carry no style tag. So a style-scoped request ("스트릿 only") must be **post-filtered with a curated slug whitelist**, intersected with `brands.tsv`. Without it, SPA/womenswear (spao, 8seconds, mixxo, mindbridge) **silently leak in** and the user's intent is lost.

```python
STREET = set('''thisisneverthat lmc thiseez cargobros matinkim ghostrepublic
mahagrid discusathletic untapped millo suare drawfit schisminducing kiimuir
mmlg badblood ootd they yeomim kinchi ufo cargobrosfiles'''.split())
# brands.tsv codes ∩ STREET  → scoped list, then run Phase 2-5 on it
```
This whitelist is the **quality bottleneck** — curate it per request from your knowledge of the scene. If the user names a style, build the list first and state it.

### Phase 2 — Map official-store candidates
Probe every responding slug domain; do not silently accept the first HTTP 200:
```bash
awk -F'\t' '{print $1}' brands.tsv \
  | xargs -P 20 -I{} bash scripts/scan.sh --all {} > scan.tsv
```
`scan.sh --all` tries `.co.kr`, `.kr`, then `.com` and preserves full phrases (`UP TO 80%`, `FINAL SALE`) instead of truncating them to `Up`/`FINAL`.

Map misses through rate-limited search (results are still candidates):
```bash
./scripts/map_misses.py brands.tsv scan.tsv \
  --cache search-cache.json > fallback-candidates.tsv
```
Verify each candidate using page brand name plus Korean company/address/business details. Search-result rank and HTTP 200 are insufficient. If a responding slug domain later fails identity review, put its code in `rejected-codes.txt` and force fallback search:
```bash
./scripts/map_misses.py brands.tsv scan.tsv --codes rejected-codes.txt \
  --cache search-cache.json > rejected-fallback.tsv
```
Numeric/Korean platform IDs (e.g. 29CM `frontBrandNo`) skip slug probing and go directly to search mapping.

### Phase 3-4 — Scan + de-noise sale keywords
`scan.sh` pipes bodies through `extract_sale_signals.py`, which merges case variants and retains complete multiword matches. **Filter to concrete signals only**:

| Keep (concrete) | Drop (skin noise) |
|---|---|
| 시즌오프, season off | `sale` alone (cart/footer text) |
| 블랙프라이데이, black friday | `coupon` / 쿠폰 (member menu) |
| final sale, end of season sale | `clearance` (cafe24 default) |
| `X%할인`, `X% OFF`, `up to X%`, `~X%` | bare `outlet` |
| browser-visible `세일` ≥15 hits | |

**⚠️ Pressure guard:** under speed/token pressure, cut Phase 1 **page count** or Phase 2 **target count** — NEVER the noise filter (Phase 3-4) or render-verify (Phase 5). Skipping them invalidates results: most raw `sale`/`coupon`/`clearance` are skin noise. The `세일 ≥15` threshold is applied only to browser-visible Korean `세일`, never raw `sale` totals (a brand with `sale(157)` raw is meaningless until rendered).

### Phase 5 — Render, currentness-check, identity-check
Render concrete slug hits and **all search-mapped SPA candidates**:
```bash
./scripts/render_verify.sh scan.tsv rendered/ --jobs 5
./scripts/render_verify.sh fallback-candidates.tsv fallback-rendered/ --jobs 5
```
The renderer preserves TSV brand names with spaces, continues after recoverable `agent-browser open` timeouts, and writes `summary.tsv` plus visible text artifacts. Status meanings:

| Status | Meaning / action |
|---|---|
| `visible-candidate` | Concrete phrase is browser-visible; still verify brand identity and terms |
| `no-concrete-visible-signal` | Reject raw-only hit; do not report it |
| `stale-year:YYYY` | Reject unless another clearly current campaign is visible |
| `render-failed` | Retry; never downgrade to curl-only for an SPA |

**Evidence strength:** date/expiry + `%` + terms = strong; current-season phrase + discounted products = medium; menu-only `SEASON OFF` = weak and report without a maximum; raw-only or past-year = reject.

## Gotchas
| Issue | Fix |
|---|---|
| `UP TO 80%` becomes `Up` | Use current `scan.sh`/`extract_sale_signals.py`; never tokenize matches with `awk '{print $2}'` |
| A responding slug domain is unrelated | Use `scan.sh --all`; identity-review it, then search rejected codes with `map_misses.py --codes` |
| Store rejects HTTP HEAD with 405 | Current `scan.sh` uses one GET for status + body; do not restore HEAD probing |
| Global/beauty brands leak into `brands.tsv` | Treat rows as candidates; verify nationality/category |
| Raw HTML contains sale, rendered page does not | Reject as hidden/stale |
| Render shows a past-year sale | Reject with current-year guard |
| curl on SPA is empty | Render every search-mapped SPA candidate |
| Brand names with spaces break `xargs -n` | Use `render_verify.py` TSV parsing or NUL-delimited arguments |
| `agent-browser open` times out | Page may still be usable; continue wait/read, then retry if text is empty |
| Brave returns 429 | Keep sequential `--delay`/backoff and use `--cache` |
| One ranking omits known brands | Union multiple platforms, prior cache, and curated seeds |
| `agent-browser` unavailable | API discovery and SPA verification are blocked; state the limit |
| Speed pressure | Cut target count, never de-noise/render verification |

## Historical benchmark — never reuse as current evidence
A 2026-07-20 run traversed 10 pages → 378 candidates → 260 responding slug-domain candidates; search mapped 36 additional misses and rendering produced 30 visible domestic-fashion sale candidates. Rankings and campaigns change hourly, so every new answer must rerun collection and rendering.

## Files
- `scripts/fetch_all_brands.sh` — full pagination via top-level `link.next`
- `scripts/parse_brands.py` — Musinsa JSON → best-effort domestic-fashion candidate TSV
- `scripts/extract_sale_signals.py` — full-phrase, case-folded signal counts
- `scripts/scan.sh` — single-GET slug-domain candidate probing (`--all` recommended)
- `scripts/map_misses.py` — Brave fallback with filtering, delay, retry, cache, rejected-code override
- `scripts/render_verify.py` / `.sh` — concurrent rendering, timeout recovery, visible/current-year summary
- `tests/test_scripts.py` — regression tests
