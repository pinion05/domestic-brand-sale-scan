#!/usr/bin/env python3
"""Analyze today's rendered/summary.tsv -> analysis.json (exact/page + excluded groups).

Decision rules applied on top of rendered visible signals:
  - stale-year / render-failed / no-concrete-visible-signal -> rejected as-is
  - identity: global / beauty / non-fashion domain -> rejected
  - membership/coupon-only context (sign-up, kakao channel, birthday, monthly coupon,
    "always-on" shop discount) -> rejected as noise
  - real campaign (season-off menu/banner, dated promo, product % OFF) -> kept
  - tier: max% visible -> exact, else season-off/bf/fs page only -> page

Also recovers registry brands that share a rendered URL with another brand row
(code-collision dedupe drops, e.g. 쥬시쥬디 == tbhshop.co.kr).
"""
import json
import re
from pathlib import Path

IDENTITY_REJECT = {
    "fragrancedubois": "프래그런스 두 부아 — 향수 브랜드, USD 가격 (한국 패션 아님)",
    "marieclaire": "마리끌레르 — 패션/뷰티 매거진 (의류 브랜드 아님)",
    "grove": "그로브 — Grove Collaborative 홈/클리닝 제품 글로벌 (한국 패션 아님)",
    "xero": "제로 — xero.com 회계 SaaS 글로벌 (한국 패션 아님)",
    "branden": "브랜든 — GoDaddy 파킹 도메인 (공식몰 아님)",
    "moo": "엠오오 — MOO 글로벌 명함/스티커 인쇄 브랜드 (패션 아님)",
    "tansanmagnesium": "탄산마그네슘 — 의류 상품 미확인 — 재제외",
    "subdued": "섭듀드 — 이탈리아 글로벌 의류, 첫 구매 쿠폰만 (한국 패션 아님)",
    "wwwssfshop": "빈폴 액세서리 — SSFShop 플랫폼 매장 (공식몰 아님) — 재제외",
    "breezfy": "브리즈피 — 핸드폰 케이스/액세서리, USD 가격 (한국 패션 아님)",
    "tillidie": "틸아이다이 — 미국 익스트림스포츠 의류 글로벌, USD — 재제외",
    "ravrac": "라브라크 — 여행용 캐리어/러기지 (패션 의류 아님)",
    "lannue": "랑느 — 코스메틱 브랜드 (패션 의류 아님)",
    "gramicci": "그라미치 — 미국 글로벌 사이츠 (USD 가격)",
    "kkonglash": "꽁래쉬 — 속눈썹/뷰티 브랜드 (EUR 가격)",
    "rense": "렌세 — 음모론/대안뉴스 사이트 (패션 아님)",
    "banila": "바닐라코 — 화장품/뷰티 브랜드",
    "bearpaw": "베어파우 — 미국 신발 브랜드 (USD)",
    "blayer": "블레이어 — 음반/CD 판매",
    "innisfree": "이니스프리 — 화장품/뷰티 브랜드",
    "podl": "포들 — 스킨케어 브랜드",
    "olaplex": "올라플렉스 — 헤어케어/뷰티 글로벌",
    "mediheal": "메디힐 — 마스크팩/스킨케어 (USD)",
    "thebodyshop": "더바디샵 — 뷰티/코스메틱 글로벌",
    "yvesrocher": "이브로쉐 — 뷰티/코스메틱 글로벌",
    "gillette": "질레트 — 면도기/생활용품 글로벌 (패션 아님)",
    "banilaco": "바닐라코 — 화장품/뷰티 브랜드 (banilaco.com)",
    "indosole": "인도솔 — 인도네시아 샌들 브랜드, USD (한국 패션 아님)",
    "museum02": "뮤지엄02 — 뷰티 리테일 (패션 의류 아님)",
    "chi": "취 — chi.com = CHI 헤어스타일링 기기 (미국, 패션 아님)",
    "yurt": "유르트 — yurts.com = Pacific Yurts 미국 주거 제조 (패션 아님)",
    "belier": "벨리에 — belier.com 크로셋 의류 글로벌, EUR 가격 (한국 패션 아님)",
    "age20s": "에이지투웨니스 — 화장품/뷰티 브랜드, 가입 5% 쿠폰 (한국 패션 아님)",
    "anillo": "아닐로 — 헤어&바디 세트 뷰티 브랜드 (패션 의류 아님)",
    "arocell": "아로셀 — 화장품(마스크팩) 브랜드, 회원가입 쿠폰 (패션 아님)",
    "lilybyred": "릴리바이레드 — 뷰티(틴트) 브랜드, 회원 전용 할인 (패션 아님)",
    "paparecipe": "파파레서피 — 화장품 브랜드, 신규회원 50% (패션 아님)",
    "not4u": "낫포유 — 바디케어 브랜드, 회원가입 혜택 (패션 아님)",
    "klattermusen": "클라터뮤젠 — klattermusen.kr이 en-eu 글로벌샵으로 리다이렉트 (한국 공식몰 아님)",
    "laboh": "라보에이치 — 두피 스킨케어 브랜드 (패션 아님)",
    "ssfshop": "빈폴 액세서리 — SSFShop 플랫폼 매장 (공식몰 아님) — 재제외",
    "celimax": "셀리맥스 — 스킨케어 뷰티 브랜드 (패션 아님)",
    "drunkelephant": "드렁크엘리펀트 — 스킨케어 뷰티 글로벌, USD (한국 패션 아님)",
    "kuoca": "쿠오카 — 향수/프래그런스 브랜드 (패션 의류 아님)",
    "triconix": "트리코닉스 — 두피케어/탈모 케어 브랜드 (패션 아님)",
    "timex": "타이맥스 — 미국 시계 브랜드 글로벌, USD (한국 패션 아님)",
    "parity": "패리티 — 캐리어/수트케이스·트래블 용품 (패션 의류 아님)",
    "romand": "롬앤 — 립틴트/글로스 색조 뷰티 브랜드 (패션 의류 아님)",
    "lloyd": "로이드 — lloyd.com 독일 신발/패션 글로벌, EUR/영어 페이지 (한국 패션 아님)",
}

# Membership/coupon-only noise (no real season campaign)
COUPON_REJECT = {
    "they": "데이 — 신규회원 10% 쿠폰 (회원 노이즈)",
    "nupip": "누핍 — 신규가입 10% 할인 쿠폰 (회원 노이즈)",
    "denmade": "덴메이드 — 카카오톡 플러스친구 15% 쿠폰 (회원 노이즈)",
    "wwwmuarmus": "무아르무스 — 카카오톡 채널 10% 쿠폰 (회원 노이즈)",
    "muarmus": "무아르무스 — 카카오톡 채널 10% 쿠폰 (회원 노이즈)",
    "vinaj": "비나제이 — 카톡 플친 10% 쿠폰 (회원 노이즈)",
    "cesti": "세스띠 — 회원가입 5% 쿠폰 (회원 노이즈)",
    "alavague": "아라바그 — Back to School + EXTRA 10% COUPON (쿠폰 노이즈)",
    "axistudio": "악시 스튜디오 — 첫 구매 10% 쿠폰 (회원 노이즈)",
    "mmic": "엠엠아이씨 — 첫 구매 10% 쿠폰 (회원 노이즈)",
    "mmlg": "엠엠엘지 — 신규 회원 10% 쿠폰 (회원 노이즈)",
    "wioe": "위오이 — 신규 가입시 10% 할인 (회원 노이즈)",
    "universegarment": "유니버스 가먼트 — 회원가입 10% 쿠폰 (회원 노이즈)",
    "ufcsport": "유에프씨 스포츠 — 신규회원 10% 쿠폰 (회원 노이즈)",
    "heeari": "히어리 — 신규회원 10% 쿠폰 (회원 노이즈)",
    "bibyseob2": "placeholder",
    "graynoise": "그레이노이즈 — 회원가입 10% 쿠폰 (회원 노이즈)",
    "nocle": "노클 — 카카오톡 플러스친구 10% 할인 (회원 노이즈)",
    "atez": "아테즈 — 회원가입 후 구매 시 5% (회원 노이즈)",
    "deheve": "드헤베 — KAKAO PLUS 10% OFF (채널 쿠폰 노이즈)",
    "wwwyegg": "예그 — Bundle & Save 묶음 할인 (세일 캠페인 아님)",
    "prospecs-coupon": "placeholder",
    "illigo-coupon": "placeholder",
    "kookeesee": "쿠키시 — 매월 1일 회원 자동 20% 쿠폰 (월간 쿠폰 노이즈)",
    "wvproject": "더블유브이프로젝트 — 회원등급별 최대 20% (멤버십 등급 노이즈)",
    "108pound": "108파운드 — Join us and Get 10% off (회원가입 노이즈)",
    "dogmaehks": "도그마 엑스 — SIGN UP 10% OFF COUPON (회원 노이즈)",
    "lebar": "르바 — 신규가입 쿠폰 (회원 노이즈)",
    "leire": "르아르 — 블랙프라이데이 ~88% 상설 메뉴명 (현재 캠페인 아님) — 메뉴 노이즈",
    "magoodgan": "맥우드건 — 신규가입 10% 쿠폰 (회원 노이즈)",
    "moodinside2": "placeholder",
    "musemuseum": "뮤즈뮤지엄 — Always 10% Off (상시 할인, 시즌 캠페인 아님)",
    "baeredancerp": "배러댄서프 — 신규 가입 15% 쿠폰 (멤버십 노이즈)",
    "benhiss": "벤힛 — 회원가입 후 구매 시 신상품 5% (회원 노이즈)",
    "auber": "오베르 — 첫 주문 10% OFF / 가입 쿠폰 (회원 노이즈)",
    "zzerosongzio2": "placeholder",
    "onnhans": "온한스 — 가입 시 10% 생일쿠폰 (회원 노이즈)",
    "venhit": "벤힛 — 회원가입 후 구매 시 신상품 5% (회원 노이즈)",
    "anillo2": "placeholder",
    "doffjason": "도프제이슨 — BLACK FRIDAY 메뉴(%없음) + 첫구매 10% 쿠폰 — 메뉴 노이즈",
    "dalinbra": "달링브라 — 상품별 할인가 표기만 (캠페인 문구 없음)",
    "coolsis": "쿨시스 — 단일 SEASON OFF (약한 신호) — 재제외",
    "martincoks": "마틴콕스 — 첫 주문 20% 쿠폰 (카카오 채널 노이즈)",
    "pleasenofollow": "플리즈노팔로우 — OPEN SALE (신상품 런칭, 세일 아님)",
    "surfea": "써피 — FINAL SEASON OFF 진행 (유지 검토 결과 실제 캠페인)",
    "moodinside3": "placeholder",
    "kantr": "캔터 — 회원가입 전상품 추가 10% 쿠폰 (회원 노이즈)",
    "cargobros": "카고브로스 — 카카오플친 5% 쿠폰 (회원 노이즈)",
    "prospecs": "프로-스펙스 — 신규 가입시 10%OFF 쿠폰 (회원 노이즈)",
    "hieta": "히에타 — 신규 가입 10% 쿠폰 (회원 노이즈)",
    "doffjason2": "placeholder",
    "illigo": "일리고 — KAKAO CHANNEL 10% OFF COUPON (채널 쿠폰 노이즈)",
    "alavague2": "placeholder",
    "kookeesee2": "placeholder",
    "surfea2": "placeholder",
    "deara": "디어에이 — 회원가입 시 5% 할인쿠폰 (회원 노이즈)",
    "majournee": "마조네 — 카카오 채널 5% 할인 쿠폰 (회원 노이즈)",
    "pentaon": "펜타온 — 신규회원 10% 쿠폰 + 상품별 할인가 표기만 (캠페인 문구 없음)",
    "boxraw": "복스로 — 포인트 적립 '최대 100%까지 사용' 안내 (포인트 노이즈)",
    "meenderi": "민더리 — 카카오톡 플러스친구 10% OFF 쿠폰 (회원 노이즈)",
    "chancesnoi": "챈세스노이 — always-on 상시 이벤트 30% + 신규가입 쿠폰 (상시 노이즈)",
    "1507": "일오공칠 — 신규 회원가입시 30% 할인 쿠폰 증정 (회원 노이즈)",
    "ndod": "엔디오디 — 신규 회원 10% 쿠폰 + 적립금 (회원 노이즈)",
    "thematee": "더마티 — 카카오채널 친구추가 10% 할인쿠폰 (채널 노이즈)",
    "sealot": "실롯 — 10% Off Coupon만 노출 (쿠폰 노이즈)",
    "not4nerd": "낫포너드 — 회원 등급별 최대 10% 추가 할인 (멤버십 등급 노이즈)",
    "tarvert": "타버트 — 신규 가입시 최대 20% 할인 쿠폰 (회원 노이즈)",
}
# remove placeholders and entries whose artifact evidence showed a real campaign
for _ph in [k for k, v in COUPON_REJECT.items() if v == "placeholder" or "유지 검토 결과 실제 캠페인" in v]:
    del COUPON_REJECT[_ph]
# Real campaigns found in today's artifacts (keep despite coupon menu presence):
#   surfea (FINAL SEASON OFF), prodeshirt (SEASON OFF menu)
#   vanwalk (LIMITED TIME OFFER 10% promo code), bibyseob (26 SUMMER 10% off banner)
#   hieta 15% OFF product prices = real product discount -> KEEP
#   prospecs 여름 ~30% OFF = real campaign -> KEEP
#   illigo BRAND WEEK UP TO 40% = real campaign (coupon additive) -> KEEP
#   alavague BAG TO SCHOOL UP TO 50% OFF = real campaign -> KEEP
#   andar / xexymix: real 26SS 시즌오프 campaigns visible today -> keep
#   codescombineinnerwear: SUMMER PICKS ~51% dated 08.10-08.24 real campaign -> keep
for _keep in ["hieta", "prospecs", "illigo", "alavague"]:
    COUPON_REJECT.pop(_keep, None)

def parse_summary(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines()[1:]:
        f = line.split("\t")
        if len(f) >= 6:
            rows.append({"code": f[0], "brand": f[1], "url": f[2], "final_url": f[3], "status": f[4], "signals": f[5]})
    return rows


def extract_max_pct(signals):
    pcts = []
    for m in re.finditer(r"(?:up\s*to|최대|~\s*)\s*(\d{1,3})\s*%", signals, re.IGNORECASE):
        pcts.append(int(m.group(1)))
    for m in re.finditer(r"(\d{1,3})\s*%\s*(?:할인|off|오프)", signals, re.IGNORECASE):
        pcts.append(int(m.group(1)))
    return max(pcts) if pcts else None


def main():
    rows = parse_summary("rendered/summary.tsv")
    final, ex_identity, ex_coupon, ex_stale, ex_novisual, ex_failed = [], [], [], [], [], []
    for r in rows:
        code, status = r["code"], r["status"]
        if status.startswith("stale-year"):
            ex_stale.append(f"{r['brand']} ({status})")
            continue
        if status == "render-failed":
            ex_failed.append(f"{r['brand']} (render-failed)")
            continue
        if status != "visible-candidate":
            ex_novisual.append(r["brand"])
            continue
        if code in IDENTITY_REJECT:
            ex_identity.append(IDENTITY_REJECT[code])
            continue
        if code in COUPON_REJECT:
            ex_coupon.append(COUPON_REJECT[code])
            continue
        max_pct = extract_max_pct(r["signals"])
        season = bool(re.search(r"(시즌\s*오프|season[\s_-]*off)", r["signals"], re.IGNORECASE)) or \
            bool(re.search(r"end[\s_-]*of[\s_-]*season[\s_-]*sale", r["signals"], re.IGNORECASE))
        bf = bool(re.search(r"(블랙\s*프라이디|black[\s_-]*friday)", r["signals"], re.IGNORECASE))
        fs = bool(re.search(r"final[\s_-]*sale", r["signals"], re.IGNORECASE))
        tier = "exact" if max_pct is not None else "page"
        if season:
            condition = "시즌오프"
        elif bf:
            condition = "블랙프라이데이"
        elif fs:
            condition = "파이널세일"
        else:
            condition = "선택 상품"
        url = r["final_url"] if r["final_url"].startswith("http") else r["url"]
        final.append({
            "brand": r["brand"], "url": url, "offer": r["signals"].replace(",", " · "),
            "max": max_pct, "tier": tier, "condition": condition, "code": code,
            "_signals": r["signals"],
        })
    exact = sorted([x for x in final if x["tier"] == "exact"], key=lambda x: (-(x["max"] or 0), x["brand"]))
    page = sorted([x for x in final if x["tier"] == "page"], key=lambda x: x["brand"])

    # Recover registry brands dropped by code-collision dedupe: their registry URL
    # was rendered under a different brand's code today (e.g. 쥬시쥬디 == tbhshop.co.kr).
    # The rendered row for that URL is the evidence surface for them too.
    # Brands rejected today via identity/coupon maps keep their rejection.
    reg = json.loads(Path("data/brand-urls.json").read_text(encoding="utf-8"))
    kept = {x["brand"] for x in exact} | {x["brand"] for x in page}
    code_brand = {r["code"]: r["brand"] for r in rows}
    rejected_brands = {code_brand[c] for c in IDENTITY_REJECT if c in code_brand} | \
                      {code_brand[c] for c in COUPON_REJECT if c in code_brand}
    by_final_host = {}
    from urllib.parse import urlparse
    for r in rows:
        if r["status"] == "visible-candidate":
            u = r["final_url"] if r["final_url"].startswith("http") else r["url"]
            by_final_host[urlparse(u).netloc] = r
    today_codes = {}
    for line in Path("brands.tsv").read_text(encoding="utf-8").splitlines():
        f = line.split("\t")
        if len(f) >= 2:
            today_codes[f[1]] = f[0]
    rendered_codes = {r["code"] for r in rows}
    recovered = []
    for brand, url in reg.items():
        if brand in kept or brand in rejected_brands:
            continue
        host = urlparse(url).netloc
        r = by_final_host.get(host)
        if not r:
            continue
        code_today = today_codes.get(brand)
        if code_today and code_today in rendered_codes:
            continue  # brand had its own render row; its rejection stands
        # this URL's render is the brand's evidence -> clone the row
        max_pct = extract_max_pct(r["signals"])
        season = bool(re.search(r"(시즌\s*오프|season[\s_-]*off)", r["signals"], re.IGNORECASE)) or \
            bool(re.search(r"end[\s_-]*of[\s_-]*season[\s_-]*sale", r["signals"], re.IGNORECASE))
        bf = bool(re.search(r"(블랙\s*프라이디|black[\s_-]*friday)", r["signals"], re.IGNORECASE))
        fs = bool(re.search(r"final[\s_-]*sale", r["signals"], re.IGNORECASE))
        entry = {
            "brand": brand, "url": url, "offer": r["signals"].replace(",", " · "),
            "max": max_pct, "tier": "exact" if max_pct is not None else "page",
            "condition": "시즌오프" if season else ("블랙프라이데이" if bf else ("파이널세일" if fs else "선택 상품")),
            "code": r["code"], "_signals": r["signals"], "_recovered": True,
        }
        recovered.append(entry)
    exact = sorted(exact + [x for x in recovered if x["tier"] == "exact"], key=lambda x: (-(x["max"] or 0), x["brand"]))
    page = sorted(page + [x for x in recovered if x["tier"] == "page"], key=lambda x: x["brand"])
    if recovered:
        print("recovered (same-URL registry brands):", [x["brand"] for x in recovered])
    ex_stale_all = ex_stale + ex_failed
    doc = {
        "exact": exact, "page": page,
        "excluded_noconcrete": ex_novisual,
        "excluded_identity": ex_identity,
        "excluded_membership": ex_coupon,
        "excluded_stale": ex_stale,
    }
    Path("analysis.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"EXACT={len(exact)} PAGE={len(page)} TOTAL={len(exact)+len(page)}")
    print(f"EXCL noconcrete={len(ex_novisual)} identity={len(ex_identity)} membership={len(ex_coupon)} stale={len(ex_stale)} failed={len(ex_failed)}")


if __name__ == "__main__":
    main()
