# domestic-brand-sale-scan

국내(도메스틱) 패션 브랜드 중 **공식 스토어(공홈)** 에서 세일/시즌오프/블랙프라이데이를 돌리는 곳을 대량으로 조사하는 파이프라인.

커머스 플랫폼(무신사/29CM/W컨셉/에이블리) 내부 세일이 아니라, 브랜드 **자사 공식몰** 의 세일만 찾는 게 핵심이다. 플랫폼의 브랜드 목록 API를 잡아 → 브랜드 식별자를 공식몰 도메인으로 매핑 → 세일 키워드를 스캔 → SPA 렌더링으로 검증한다.

> 원래 `pi` (코딩 에이전트) 의 [스킬](SKILL.md) 로 만들어졌지만, 스크립트 자체는 독립적으로 동작한다.

## 왜 필요한가

- "국내 브랜드 중 지금 세일/블프 하는 곳 조사해줘" → 브랜드가 수백 개라 한땀한땀 열어보긴 불가능
- 플랫폼(무신사 등) 화면에 보이는 세일은 플랫폼 내부 행사인 경우가 대부분. 진짜 **공홈 세일** 을 찾으려면 공식몰을 직접 봐야 한다
- 브랜드 영문 slug 코드가 공식몰 도메인과 일치하는 경우가 ~50% → 이걸 빠르게 프로브하면 된다

## 파이프라인

```
Phase 1  플랫폼 브랜드 목록 API 캡처 → 전체 페이지 긁기 (fetch_all_brands.sh)
Phase 2  브랜드 code → 공식몰 도메인 프로브 (scan.sh)
Phase 3  각 도메인 세일 키워드 카운트 (scan.sh)
Phase 4  노이즈 필터 (sale/coupon/clearance 스킨 텍스트 제거)
Phase 5  SPA 스토어는 렌더링으로 검증 (agent-browser)
```

### 핵심 함정들 (이걸 놓치면 결과가 1/3로 떨어진다)

1. **페이지네이션**: `/pans/ranking`(overview) 응답엔 다음 페이지가 없다. 실제 리스트는 `/sections/200` 엔드포인트고, 다음 페이지는 **최상위 `link.next`** (`d['link']['next']`) 를 따라가야 한다. `data.link.next` / `hasNext` 는 거짓. → 그래서 `fetch_all_brands.sh` 가 자동 루프를 돈다
2. **세일 키워드 노이즈**: `sale` / `coupon` / `clearance` 는 cafe24/imweb 쇼핑몰 스킨의 기본 텍스트라 어디서든 등장한다. **구체 신호만 남긴다**: `시즌오프`, `% OFF`, `up to X%`, `블랙프라이데이`, `final sale`
3. **브랜드 ID 타입**: 무신사/W컨셉/에이블리는 영문 slug (`/brand/{slug}`) 라 `code.com` 프로브가 통한다. 29CM는 숫자 `frontBrandNo` (`/store/brand/36324`) 라 프로브가 무의미 → 검색 매핑으로 가야 한다
4. **SPA 스토어**: imweb / Next 기반 공식몰은 curl 하면 빈 HTML 이 온다. 반드시 렌더링(`agent-browser`) 후 DOM 을 읽어야 한다

## 스크립트

| 파일 | 설명 |
|---|---|
| `scripts/fetch_all_brands.sh` | 무신사 랭킹 전체 페이지 긁기 (최상위 `link.next` 루프, `/sections/200`). Phase 1 필수 |
| `scripts/parse_brands.py` | 무신사 API JSON → 도메스틱 브랜드 TSV (글로벌 브랜드/아이돌 블록리스트 필터) |
| `scripts/scan.sh` | 브랜드 code → 공식몰 도메인 프로브 + 세일 키워드 카운트 |

## 사용법

```bash
# Phase 1: 무신사 실시간 랭キング 전체 긁기
./scripts/fetch_all_brands.sh pages/                    # → pages/p1..pN.json

# Phase 1 (후): JSON → domestic brand TSV
python3 scripts/parse_brands.py 'pages/p*.json' > brands.tsv   # code<TAB>brandName<TAB>freq

# Phase 2-3: 각 브랜드 공식몰 프로브 + 세일 키워드 카운트 (병렬)
awk -F'\t' '{print $1}' brands.tsv | xargs -P 20 -I{} bash scripts/scan.sh {} > scan.tsv
```

`scan.tsv` 형태:
```
matinkim   matinkim.com    200    up to 80%(3),시즌오프(1)
...
```

여기서 **구체 신호만** 거르면 진짜 세일 중인 브랜드가 나온다:

| Keep (구체) | Drop (스킨 노이즈) |
|---|---|
| `시즌오프`, `season off` | 단독 `sale` (장바구니/푸터) |
| `블랙프라이데이`, `black friday` | `coupon` / 쿠폰 (멤버 메뉴) |
| `final sale` | `clearance` (cafe24 기본) |
| `X%할인`, `X% OFF`, `up to X%` | 단독 `outlet` |

## 의존성

- `curl`, `python3`, `awk`, `xargs` (표준 Unix)
- **`agent-browser`** (선택이지만 거의 필수): Phase 1 에서 브랜드 목록 API 를 **발견** 하고, Phase 5 에서 **SPA 공식몰을 렌더링 검증**. API URL 을 이미 알면 Phase 1 은 curl 로 되지만, SPA 스토어 검증은 반드시 렌더링이 필요하다

## 다른 플랫폼에 적용하기

무신사 API URL 과 `parse_brands.py` 스키마(`data.modules[].items[].info`, `onClickBrandName.url=/brand/{slug}`)는 **무신사 전용** 이다. 29CM/W컨셉/에이블리에 적용하려면:

1. 그 플랫폼의 랭킹/브랜드 페이지에서 `agent-browser network requests` 로 브랜드 목록 API 를 새로 캡처
2. 응답 형태에 맞게 파서를 다시 짠다
3. **식별자 타입** 확인:
   - 영문 slug → Phase 2 프로브 가능
   - 숫자 ID / 한글명 (29CM `frontBrandNo`) → `scan.sh` 프로브 스킵, 검색 매핑(`"{브랜드명} 공식몰"`) 으로

## 레퍼런스 결과 (2026-07)

- 333 도메스틱 브랜드 → 234 스토어 히트 → 9 구체 신호 → 강한 세일 검증
  - 마뗑킴·마하그리드 (UP TO 80% OFF)
  - IDWS 아이돈워너셀 (블랙프라이데이 BF-26)
  - 올리브데올리브 (시즌오프 70%)
- 자동화 전체 런 ~10분. 수동 1페이지만 부르면 브랜드가 ~100개로 급감한다 (페이지네이션 함정)

## 한계

- 무신사 랭킹 API엔 **스타일 필터가 없다** (`categoryCode` 는 상의/아우터 같은 상품 타입). 스트릿/여성복/아메카지 같은 스타일 스코프는 **큐레이션된 slug 화이트리스트** 로 사후 필터해야 한다. 안 하면 SPA/여성복 브랜드(spao, 8seconds, mixxo, mindbridge) 가 묵묵히 섞여 들어온다
- `parse_brands.py` 의 글로벌 블록리스트는 best-effort. 상위 히트는 국적 스팟체크 권장 (mizuno=日 등)
- 7~8월엔 "블랙프라이데이" 른 기대하면 안 된다 — 인디 브랜드는 **시즌오프/아카이브세일**, 블프는 11월

## 라이선스

MIT — [LICENSE](LICENSE)
