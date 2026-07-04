---
name: domestic-brand-sale-scan
description: 'Use when investigating which Korean domestic fashion brands are currently running sales/Black Friday on their OWN official stores (공홈), not platform-internal sales. Enumerate many brands at scale from a commerce platform (Musinsa primary source; 29CM/W컨셉/에이블리 also work), map each brand code to official-store domain, scan for live sale signals, verify by rendering. Triggers — 국내/도메스틱 브랜드 세일 조사, 도메스틱 브랜드 블프, which Korean brands are on sale now, 브랜드 메이커 공홈 세일.'
---

# Domestic Brand Sale Scan

## Overview
Find which Korean domestic fashion brands are running sales on their **official stores** (공홈), not platforms. Pipeline: enumerate brands at scale via Musinsa's API → map each to its official store → scan sale keywords → verify hits by rendering.

**Core insights:**
- **The Musinsa API/URL is ONE EXAMPLE — the real method is "capture the platform's own brand-list API → map brand identifier → official domain."** Other Korean commerce platforms (29CM, W컨셉, 에이블리, 지그재그) work the same way, but each needs its API captured fresh and its identifier type handled (see Phase 1/2).
- Brand **English slug** codes often equal official-store domains (~50% hit) — probe first, it's fast. **Slug-only**: numeric IDs / Korean-name IDs don't resolve to domains.
- `sale`/`coupon`/`clearance` keywords are cafe24/imweb shopping-skin noise — **filter to concrete signals only** (시즌오프, `%OFF`, 블랙프라이데이).
- API capture beats scraping product cards (SPA = unstable).

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
./scripts/parse_brands.py pages/p*.json > brands.tsv    # 글로벌 필터 → 도메스틱 (~370)
```
`parse_brands.py`는 `data.modules[].items[].info.brandName` + `onClickBrandName.url=/brand/{slug}` 추출 (sections 응답과 동일 구조).

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

### Phase 2 — Map official stores (code → domain, ~50%)
```bash
awk -F'\t' '{print $1}' brands.tsv | xargs -P 20 -I{} bash scripts/scan.sh {} > scan.tsv
```
Misses (e.g. discusathletic, untapped) → search `"{브랜드명} 공식몰"` or try `code` + suffix (`studio`, `archive`, `kr`). Verify domain is the real brand (not a parked/other-company `.com`).

**⚠️ Slug-only — falls back to search otherwise.** If the platform's identifier is a numeric ID or Korean name (29CM `frontBrandNo`, some W컨셉 IDs), **skip `scan.sh` entirely** — `36324.com` is meaningless. Go straight to search-based mapping: `web_search "{브랜드명} 공식몰"` or fetch Naver `"{브랜드명} 공식스토어"`, then probe the found domain with the same keyword scan.

### Phase 3-4 — Scan + de-noise sale keywords
`scan.sh` already counts keywords. **Filter to concrete signals only** (broad ones are skin noise):

| Keep (concrete) | Drop (skin noise) |
|---|---|
| 시즌오프, season off | `sale` alone (cart/footer text) |
| 블랙프라이데이, black friday | `coupon` / 쿠폰 (member menu) |
| final sale | `clearance` (cafe24 default) |
| `X%할인`, `X% OFF`, `up to X%` | bare `outlet` |
| `세일` keyword ≥15 hits (AFTER de-noise) | |

**⚠️ Pressure guard:** under speed/token pressure, cut Phase 1 **page count** or Phase 2 **target count** — NEVER the noise filter (Phase 3-4) or render-verify (Phase 5). Skipping them invalidates results: most raw `sale`/`coupon`/`clearance` are skin noise. The `세일 ≥15` threshold counts **concrete signals after de-noise**, not raw keyword totals (a brand with `sale(157)` raw is meaningless until filtered).

### Phase 5 — Verify by rendering
- cafe24 (server-rendered) → curl body is enough. **Confirm cafe24 first** (`cafe24` in footer/img host `*.cafe24.com`/URL) — don't skip render on *assumption* under pressure.
- **imweb / Next SPAs → must render:**
```bash
agent-browser open "<url>"; agent-browser wait --load networkidle; agent-browser wait 2500
agent-browser read | grep -oiE '시즌오프|up to [0-9]+%|[0-9]+%[ ]?off|black[ ]?friday' | sort | uniq -c
```

## Gotchas
| Issue | Fix |
|---|---|
| Scraping product cards (SPA) | Use API via `network requests` capture |
| `sale`/`clearance` everywhere | Filter to concrete signals (table above) |
| `code.com` ≠ brand (other company) | Verify domain; `.co.kr`/`.kr` higher Korean-confidence |
| curl on SPA = empty | `agent-browser read` after networkidle |
| context-mode blocks inline curl | `curl -s -o file` then parse in workspace |
| Expecting summer "Black Friday" | Jul/Aug = 인디 brands do **시즌오프/아카이브세일**, 블프 is Nov. Set expectations. |
| `agent-browser` unavailable | Phase 1 (API capture) & 5 (SPA verify) are BLOCKED. curl-only works only for server-rendered platforms w/ HTML sitemaps. State limit, don't silently degrade. |
| Numeric/Korean brand IDs (29CM) | `scan.sh` code.com probe is slug-only; use search mapping (`브랜드명 공식몰`) instead |
| Applying to a new platform | Re-capture THAT platform's brand-list API (`network requests`); don't reuse the Musinsa URL/parser verbatim |
| Speed/token pressure | Cut page/target **COUNT**, never the noise filter or render-verify — skipping them invalidates results |
| Japanese/global brands leaking into domestic list | `parse_brands.py` blocklist is best-effort; spot-check top hits for 국적 (mizuno=日, 등) |

## Reference result (2026-07, full run)
333 domestic brands → 234 store hits → 9 concrete signals → verified strong sales: 마뗑킴·마하그리드 (UP TO 80% OFF), IDWS 아이돈워너셀 (블랙프라이데이 BF-26), 올리브데올리브 (시즌오프 70%). Took ~10 min automated; manual brand-by-brand would've been hours. (2026-07 재검증: `fetch_all_brands.sh` 자동화 후 ~370개 재현 — 실시간 랭킹이라 ±변동. 수동 1페이지 호출 시 ~100개로 급감 = 페이지네이션 함정.)

## Files
- `scripts/fetch_all_brands.sh` — 전체 페이지 긁기 (최상위 `link.next` 루프, `/sections/200`) — **Phase 1 필수**
- `scripts/parse_brands.py` — Musinsa API JSON → domestic brand TSV
- `scripts/scan.sh` — code → official-domain probe + sale-keyword count
