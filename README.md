# domestic-brand-sale-scan

국내 패션 브랜드 중 **자사 공식 스토어(공홈)** 에서 현재 세일·시즌오프·블랙프라이데이를 진행하는 곳을 대량 조사하는 파이프라인이다. 무신사·29CM 같은 플랫폼 내부 행사는 제외한다.

> 원래 `pi` 코딩 에이전트용 [스킬](SKILL.md)로 만들었지만, 수집·검색·검증 스크립트는 독립적으로 실행할 수 있다.

## 오늘의 검증 목록

**2026-07-20 16:36 KST 기준 공식몰 세일 52곳**을 날짜 고정 스냅샷으로 공개했다.

- **GitHub Pages:** https://pinion05.github.io/domestic-brand-sale-scan/
- **Markdown 보고서:** [`reports/2026-07-20.md`](reports/2026-07-20.md)

페이지에는 할인율이 확인된 30곳, 세일 페이지가 노출 중인 22곳, 제외 사유와 조사 범위를 함께 기록했다.

## 익명 트래픽 계측

GitHub Pages에는 Umami Cloud의 쿠키 없는 익명 계측을 적용했다. 브라우저의 Do Not Track 설정을 존중하며 Core Web Vitals를 함께 수집한다. 내부 검색에서는 **검색어 원문은 수집하지 않는다**.

| 이벤트 | 의미 | 주요 속성 |
|---|---|---|
| `official_store_click` | 공식몰 링크 이동 | 브랜드, 할인 유형, 최대 할인율, 목록 위치 |
| `filter_select` | 목록 필터 변경 | 필터, 결과 개수 |
| `search_used` | 내부 검색 사용 | 필터, 결과 개수 |
| `share_click` | 날짜별 보고서 공유 | 공유 방식, 보고서 날짜 |

홍보 링크는 다음 규칙으로 생성한다.

```text
utm_source=threads|instagram|x|telegram|community
utm_medium=social|messaging|community
utm_campaign=daily_sale_YYYYMMDD
utm_content=ends_today|top_discount|daily_report
```

사이트의 공유 버튼은 `utm_source=direct_share`, `utm_medium=referral`을 사용한다. 검색 노출과 클릭은 Google Search Console에서 별도로 확인하며 `docs/robots.txt`와 `docs/sitemap.xml`을 함께 배포한다. 현재 URL은 GitHub **프로젝트** Pages 경로이므로 `robots.txt`는 호스트 루트 정책으로 인정되지 않는다. sitemap은 Search Console에 직접 제출하고, `robots.txt`는 향후 커스텀 도메인 루트로 이전한다.

## 핵심 원칙

- `brands.tsv`는 **국내 패션 후보군**이다. 국적과 카테고리가 확정된 목록이 아니다.
- slug 도메인의 HTTP 200 응답은 **공식몰 후보**일 뿐이다. 브랜드명·법인·한국 사업자 정보를 확인해야 한다.
- raw HTML의 `sale`, `coupon`, `clearance`는 쇼핑몰 스킨 노이즈일 수 있다.
- raw HTML에만 남은 세일은 과거 캠페인일 수 있고, SPA의 raw HTML은 비어 있을 수 있다. 최종 근거는 브라우저 가시 텍스트다.
- 실시간 랭킹은 전체 브랜드 카탈로그가 아니다. 넓은 조사는 여러 플랫폼·이전 캐시·주요 브랜드 seed의 합집합이 필요하다.

## 파이프라인

```text
플랫폼 브랜드 API 전체 페이지 수집
  → 국내 패션 후보 추출
  → slug 도메인 후보 전체 프로브
  → 검색 fallback
  → 세일 문구 de-noise
  → agent-browser 병렬 렌더링
  → 현재 연도·브랜드 정체성·조건 최종 검증
```

## 스크립트

| 파일 | 역할 |
|---|---|
| `scripts/fetch_all_brands.sh` | 무신사 `/sections/200` 전체 페이지 수집. 최상위 `link.next`를 따라감 |
| `scripts/parse_brands.py` | API JSON → best-effort 국내 패션 후보 TSV |
| `scripts/extract_sale_signals.py` | gzip·CP949/EUC-KR 본문을 안전하게 디코딩하고 다단어 신호를 보존·집계 |
| `scripts/scan.sh` | `.co.kr`, `.kr`, `.com` slug 도메인 후보 프로브. `--all` 권장 |
| `scripts/map_misses.py` | Brave 검색 fallback, 마켓플레이스 필터, rate limit/backoff, 캐시 |
| `scripts/render_verify.py` | `agent-browser` 병렬 렌더링, 타임아웃 복구, 가시 신호·과거 연도 요약 |
| `scripts/render_verify.sh` | 렌더러 실행 래퍼 |
| `tests/test_scripts.py` | 회귀 테스트 |

## 요구 사항

- Python 3.9+
- `curl`, `awk`, `xargs`, Bash
- [`agent-browser`](https://github.com/vercel-labs/agent-browser): API 발견 및 SPA 렌더링 검증
- `BRAVE_API_KEY`: 검색 fallback을 사용할 때만 필요

처음 `agent-browser`를 사용할 때는 설치 버전에 맞는 가이드를 먼저 확인한다.

```bash
agent-browser skills get core
```

## 사용법

### 1. 브랜드 전체 페이지 수집

무신사 랭킹 페이지에서 `agent-browser network requests`로 현재 API를 확인한 뒤 실행한다.

```bash
./scripts/fetch_all_brands.sh pages/
./scripts/parse_brands.py 'pages/p*.json' > brands.tsv
```

출력 형식:

```text
code<TAB>brandName<TAB>frequency
```

### 2. slug 도메인 후보 프로브

```bash
awk -F'\t' '{print $1}' brands.tsv \
  | xargs -P 20 -I{} bash scripts/scan.sh --all {} > scan.tsv
```

`scan.sh`는 HEAD가 차단되는 사이트도 놓치지 않도록 한 번의 압축 지원 GET으로 상태와 본문을 함께 확인한다. gzip 및 UTF-8/CP949/EUC-KR 본문을 처리하며 다단어 문구도 자르지 않는다.

```text
matinkim<TAB>matinkim.com<TAB>200<TAB>SEASON OFF(16),Up to 80%(2)
```

### 3. slug miss 검색 매핑

```bash
./scripts/map_misses.py brands.tsv scan.tsv \
  --cache search-cache.json > fallback-candidates.tsv
```

기본 검색 간격은 1.1초이며 429 응답에는 backoff한다. 일시적인 검색 실패는 캐시에 영구 miss로 저장하지 않는다.

slug 도메인이 응답했지만 다른 회사로 판정된 경우 해당 code를 다시 검색한다.

```bash
printf '%s\n' cornell > rejected-codes.txt
./scripts/map_misses.py brands.tsv scan.tsv \
  --codes rejected-codes.txt \
  --cache search-cache.json > rejected-fallback.tsv
```

검색 결과 역시 공식몰 확정값이 아닌 후보이므로 렌더링 후 정체성을 확인한다.

### 4. 브라우저 렌더링 검증

```bash
./scripts/render_verify.sh scan.tsv rendered/ --jobs 5
./scripts/render_verify.sh fallback-candidates.tsv fallback-rendered/ --jobs 5
```

각 디렉터리에 페이지 텍스트·제목·최종 URL·오류 로그와 `summary.tsv`가 생성된다. 브랜드명에 공백이 있어도 TSV 열이 깨지지 않으며, `agent-browser open`이 타임아웃돼도 살아 있는 세션에서 읽기를 계속 시도한다.

| 상태 | 의미 |
|---|---|
| `visible-candidate` | 구체적인 세일 문구가 화면에 보임. 브랜드 정체성과 조건은 추가 확인 |
| `no-concrete-visible-signal` | raw-only 또는 스킨 노이즈. 보고 대상에서 제외 |
| `stale-year:YYYY` | 과거 연도 캠페인 후보. 사업자·통신판매·저작권 연도는 무시하며, 다른 현재 캠페인이 없다면 제외 |
| `render-failed` | 재시도 필요. SPA를 curl 결과로 대체하면 안 됨 |

## 세일 신호 기준

| 유지 | 제거 |
|---|---|
| 시즌오프, `season off` | 단독 `sale` |
| 블랙프라이데이, `black friday` | `coupon` / 쿠폰 |
| `final sale`, `end of season sale` | 단독 `clearance` |
| `X% 할인`, `X% OFF`, `up to X%`, `~X%` | 단독 `outlet` |
| 브라우저 가시 텍스트의 `세일` 15회 이상 | raw HTML의 반복 횟수 |

증거 강도는 다음처럼 구분한다.

- **강함:** 현재 날짜·종료일·할인율·쿠폰 조건이 함께 노출
- **중간:** 현재 시즌 세일 문구와 할인 상품이 함께 노출
- **약함:** 메뉴에 `SEASON OFF`만 노출 — 최대 할인율을 추정하지 않음
- **제외:** raw-only, 과거 연도, 브랜드 정체성 불일치

## 테스트

```bash
python3 tests/test_scripts.py -v
python3 tests/test_pages.py -v
python3 -m py_compile scripts/*.py
bash -n scripts/*.sh
```

테스트는 gzip·CP949 입력, 다단어 문구 보존, 단어 내부 오탐 방지, slug 후보 전체 프로브, 글로벌·비패션 제외, 검색 캐시 복구, 공백 포함 TSV, 렌더 타임아웃과 캠페인/사업자 연도 구분을 검증한다. 페이지 테스트는 익명 계측 설정, 이벤트 개인정보 최소화, 공유 UTM, Search Console 및 sitemap 계약을 검증한다.

## 다른 플랫폼에 적용하기

무신사 API URL과 JSON 스키마는 무신사 전용이다. 29CM·W컨셉·에이블리 등에 적용할 때는 해당 플랫폼의 브랜드 목록 API를 새로 캡처하고 응답 형태에 맞는 파서를 작성한다.

- 영문 slug → 도메인 프로브 가능
- 숫자 ID·한글 ID → slug 프로브를 건너뛰고 검색 매핑
- 스타일 요청(스트릿·아메카지 등) → 플랫폼 데이터에 스타일 태그가 없다면 큐레이션된 slug whitelist로 후처리

## 과거 벤치마크

2026-07-20 실행에서 10페이지를 순회해 378개 초기 후보와 260개 응답 slug 도메인 후보를 얻었다. 검색 fallback과 렌더링 후 화면에 세일 신호가 보이는 국내 패션 후보 30개를 확인했다.

랭킹과 캠페인은 수시로 변하므로 이 숫자나 당시 브랜드명을 현재 결과로 재사용하면 안 된다.

## 라이선스

MIT — [LICENSE](LICENSE)
