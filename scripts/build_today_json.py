#!/usr/bin/env python3
"""Build today's docs/sales-YYYY-MM-DD.json from merged-summary.tsv with manual verdicts."""
import json
import re
import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent

# verdicts: url -> (include?, brand_override|None, condition|None, note|None)
EXCLUDE = {
    # membership/coupon noise
    "https://graynoise.co.kr/": "회원가입 시 10% 할인 쿠폰 발급 — 신규 기각",
    "https://www.montbell.co.kr/": "회원가입하고 5% 할인 쿠통 받기 — 신규 기각",
    "https://vern.kr/": "쇼룸 멤버십 최대 10% + 가입 5% 쿠폰 — 신규 기각",
    "https://heeari.com/": "신규회원 10% 할인 쿠폰 발급 — 신규 기각",
    "https://venhit.co.kr/": "회원가입 후 구매 시 신상품 5% 할인 — 재제외",
    "https://atez.co.kr/": "회원가입 후 구매 시 신상품 5% 할인 — 재제외",
    "https://majournee.co.kr": "쿠폰성 5% 할인(플친) — 신규 기각",
    "https://cargobros.com/": "카카오플친 5% 할인쿠폰 — 재제외",
    "https://wioe.co.kr/": "신규 가입시 10% 할인 — 재제외",
    "https://illigo.co.kr/": "ILLIGO KAKAO CHANNEL 10% OFF COUPON — 재제외",
    "https://alavague.com/": "멤버십 매월 10% 할인 쿠폰 — 재제외",
    "https://onnhans.com/": "생일쿠폰 10%할인 등 회원 혜택 — 신규 기각",
    "https://projectwave.kr/": "신규 회원가입 10% 할인 쿠폰 — 신규 기각",
    "https://pinkzone.co.kr/": "신규회원 5% OFF 쿠폰(+상품 최대 30~37%는 자사몰 세일가이나 저관측) — 재제외",
    "https://oggitt.com/": "첫구매 전용 상품+Last Piece 잔여 처분 — 재제외",
    "https://horlisun.com/": "09.10~13 4일 한시 프로모션 종료 — 재제외",
    # global / non-fashion / wrong-domain
    "https://grove.com/": "미국 USD 스마트홈(Club 멤버십) — 신규 기각",
    "https://tillidie.com/": "미국 USD 서프/스케이트 애파렬 — 재기각",
    "https://mediheal.com/": "글로벌 뷰티(번들 세이브) — 신규 기각",
    "https://outstanding.kr/": "IT/미디어 콘텐츠(세일 아님) — 재제외",
    "https://breezfy.com/": "폰케이스 BOGO 50% — 재제외",
    "https://nuebetter.com": "다이어트 식품(비패션) — 재제외",
    "https://obge.co.kr/": "남성 그루밍 스킨케어(랜덤쿠폰 결합) — 재제외",
    "https://charde.co.kr": "뷰티 세트 할인(비패션) — 신규 기각",
    # stale campaign
    "https://thevinylhouse.co.kr/": "3월 4주년 40% OFF(과거 캠페인 잔재) — 신규 기각",
    # multi-brand mall signal
    "https://tbhshop.co.kr/": "TBH SHOP 멀티브랜드 공용몰(마인드브릿지·쥬시쥬디·베이직하우스 동반) — 마인드브릿지 항목으로만 보고",
}
# keep-only: pleasenofollow = OPEN SALE? weak "sale alone" → per de-noise, drop
EXCLUDE["https://pleasenofollow.kr/"] = "26FW OPEN SALE(단독 sale 문구=스킨 노이즈) — 신규 기각"

# renames / condition overrides for included brands
CONDITION = {
    "https://urago.kr/": "26FW 신상 15%",
    "https://kashiko.kr/": "신상품 15% (~09.18)",
    "https://kikozy.kr/": "26 F/W 신상 (~09.24)",
    "https://gardenexpress.kr/": "LONG SLEEVE WEEK (~09.18)",
    "https://tarvert.kr/": "기간 프로모션(~09.14)",
    "https://rebrush.co.kr/": "최대 65% 할인 혜택",
    "https://blayer.co.kr/": "최대 70% 할인",
    "https://damio.kr/": "LAST PIECES UP TO 40%",
    "https://findkapoor.co.kr/": "SEPTEMBER BEST 10% OFF(+멤버십 10%)",
    "https://suade.co.kr/": "상품 10% off",
    "https://eiom.co.kr/": "UP TO 50% (수동 렌더)",
    "https://ufcsport.co.kr/": "10% 할인 (수동 렌더)",
    "https://www.stco.co.kr/": "추석 시즌오프 (수동 렌더)",
    "https://blackyak.com/": "추석맞이 쇼핑지원금 최대 15%",
    "https://nokjok.co.kr/": "베스트 셀러 최대 63%",
    "https://well247.co.kr/": "추석 맞춤 선물전",
    "https://dthirtyone.com/": "시즌오프 UP TO 50%",
    "https://mur.kr/": "25% OFF 세일",
    "https://lazybee.co.kr/": " 최대 20%",
    "https://prooted.kr/": "선택 상품",
}

PCT = re.compile(r"(\d+)\s*%?\s*(?:할인|OFF|off|Off)|up to\s*(\d+)%|UP TO\s*(\d+)%|~\s*(\d+)%|최대\s*(\d+)%|최대(\d+)%|(\d+)%", re.I)


def extract_max(offer: str):
    vals = []
    for part in offer.split(","):
        m = PCT.search(part)
        if m:
            g = [x for x in m.groups() if x]
            if g:
                vals.append(int(g[0]))
    return max(vals) if vals else None


def season_off_only(offer: str) -> bool:
    parts = [p for p in offer.split(",")]
    concrete = [p for p in parts if PCT.search(p)]
    seasonish = [p for p in parts if re.search(r"시즌오프|SEASON[ -]?OFF|Season [Oo]ff|SEASONOFF", p, re.I)]
    return bool(seasonish) and not concrete


def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    today = now.strftime("%Y-%m-%d")
    sales = []
    excluded_coupon, excluded_domain, excluded_stale = [], [], []
    rendered_urls = set()

    for line in open(ROOT / "merged-summary.tsv"):
        p = line.rstrip("\n").split("\t")
        if len(p) < 6 or p[3] == "status":
            continue
        code, brand, url, status, offer = p[0], p[1], p[2], p[3], p[4]
        rendered_urls.add(url)
        if status != "visible-candidate":
            continue
        if url in EXCLUDE:
            note = EXCLUDE[url]
            if any(k in note for k in ("쿠폰", "멤버십", "회원", "첫구매", "플친", "생일", "BOGO", "OPEN SALE", "종료")):
                excluded_coupon.append(f"{brand} — {url} — {note}")
            elif any(k in note for k in ("USD", "글로벌", "비패션", "미디어", "폰케이스", "식품", "그루밍", "뷰티", "스마트홈", "서프", "멀티브랜드", "공용몰")):
                excluded_domain.append(f"{brand} — {url} — {note}")
            else:
                excluded_stale.append(f"{brand} — {url} — {note}")
            continue
        # 브랜드 정규화: 오늘 랭킹 한글명 우선, registry 이름 유지
        # 카시코 ~100%: CSS max-width 노이즈 → 15%만 남김. 브라운브레스 BLACK FRIDAY: 과거 캠페인 메뉴 → SEASON OFF(26 S/S)만 page 근거
        if url == "https://kashiko.kr/":
            offer = ",".join(p for p in offer.split(",") if "100%" not in p)
        if url == "https://brownbreath.com/":
            offer = ",".join(p for p in offer.split(",") if "BLACK FRIDAY" not in p)
        max_v = extract_max(offer)
        if max_v is not None:
            tier = "exact"
        elif season_off_only(offer):
            tier = "page"
        else:
            tier = "page"
        cond = CONDITION.get(url, "시즌오프" if tier == "page" else "선택 상품")
        if url == "https://tbhshop.co.kr/":
            continue  # handled below
        sales.append({"brand": brand, "url": url, "offer": offer, "max": max_v, "tier": tier, "condition": cond})

    # tbhshop → 마인드브릿지 (멀티브랜드몰, 어제 관례 유지)
    for line in open(ROOT / "merged-summary.tsv"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 6 and p[2] == "https://tbhshop.co.kr/" and p[3] == "visible-candidate":
            offer = p[4]
            sales.append({"brand": "마인드브릿지", "url": "https://tbhshop.co.kr/", "offer": offer,
                          "max": extract_max(offer), "tier": "exact", "condition": "TBH SHOP FALL BRAND WEEK(멀티브랜드몰)"})
            break

    exact = sorted([s for s in sales if s["tier"] == "exact"], key=lambda s: (-(s["max"] or 0), s["brand"]))
    page = sorted([s for s in sales if s["tier"] == "page"], key=lambda s: s["brand"])
    out = {
        "verifiedAt": now.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "verifiedLabel": now.strftime("%Y-%m-%d %H:%M") + " KST",
        "source": {
            "rankingPages": 10,
            "brandCandidates": 367,
            "renderedUrls": len(rendered_urls),
            "finalBrands": len(exact) + len(page),
            "exactOffers": len(exact),
            "openSalePages": len(page),
        },
        "sales": exact + page,
        "excluded": [
            {"label": "멤버십/쿠폰 노이즈", "items": sorted(set(excluded_coupon))},
            {"label": "도메인 불일치·글로벌·비패션", "items": sorted(set(excluded_domain))},
            {"label": "과거 캠페인·렌더 실패", "items": sorted(set(excluded_stale)) + [
                "아르메데스 — armedes.co.kr — '할인가' 상품 라벨뿐, 콘크리트 세일 문구 없음 — 재제외",
                "슈마커 — shoemarker.co.kr — 반복 타임아웃 — 렌더 실패",
                "엘칸토 — elcanto.co.kr — 스크립트만 렌더(본문 없음) — 렌더 실패",
                "프로스펙스 — prospecs.com — 반복 타임아웃 — 렌더 실패",
                "글런든 — grunden.co.kr — SUMMER SALE 메뉴 잔재(여름 과거 캠페인) — 재제외",
                "브렌슨 — brenson.co.kr — stale-year:2019 — 재제외",
            ]},
        ],
    }
    path = ROOT / f"docs/sales-{today}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"final={out['source']['finalBrands']} exact={out['source']['exactOffers']} page={out['source']['openSalePages']} rendered={out['source']['renderedUrls']}")
    print(f"-> {path}")


if __name__ == "__main__":
    main()
