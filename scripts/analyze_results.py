#!/usr/bin/env python3
"""Analyze render summary → final sale list with tier/max/condition.

Input: rendered/summary.tsv
Output: sales list JSON-ready + excluded groups

Rules:
  - Keep visible-candidate only
  - Reject global/non-fashion identity (hardcoded reject set)
  - Reject stale-year unless current campaign visible
  - De-noise: drop coupon/clearance/outlet-only skin noise
  - tier: exact (% present), page (season off / final sale / black friday only)
  - max: highest extracted %, else null
"""
import re
import sys
import json

# Reject codes — global/non-fashion/identity mismatch
REJECT = {
    "fully": "Herman Miller 의자 (fully.com 리다이렉트)",
    "moo": "글로벌 명함 인쇄 (moo.com)",
    "belier": "유럽 크로셰 의류, EUR 가격 (belier.com/en-ad)",
    "cornell": "간호사 호출 시스템 (cornell.com)",
    "positano": "이탈리아 과자/사탕 (positano.co.kr)",
    "kuoca": "향수/홈프래그런스 브랜드 (kuoca.com)",
    "anillo": "헤어 에센스/바디케어 (anillo.co.kr)",
    "blayer": "음반/CD 판매 (blayer.co.kr)",
    "bbia": "화장품 브랜드 (bbia.co.kr)",
    "boxraw": "복싱 용품 (kr.boxraw.com)",
    "rawrow": "캐리어/트렁크 브랜드 (rawrow.com)",
    "xexymix": "스포츠/요가웨어 (xexymix.com)",
    "timex": "시계 브랜드 (timex.kr)",
    "klairs": "스킨케어 브랜드 (klairs.co.kr)",
    "malbongolf": "골프웨어 → malbon.com (글로벌 골프)",
    "horlisun": "세렉트샵/편집숍 (horlisun.com)",
    "venhit": "공식몰 오픈 이벤트 5% — 신상품 멤버십 혜택",
    "heavenlyjelly": "신규회원 10% 쿠폰 + 신발 5% — 멤버십 혜택",
    "murless": "신규 10% OFF + 카카오 5% — 멤버십 혜택",
    "chasecult": "5% 쿠폰 — 멤버십 혜택",
    "anillo_dup": "duplicate",
    "beanpoleacc": "빈폴 액세서리 — SSFShop 플랫폼 (공식몰 아님)",
}

# noise-only signals: if ALL signals are coupon/clearance/outlet, drop
NOISE_SIGNALS = {"쿠폰", "coupon", "clearance", "outlet", "아웃렛", "할인"}

PERCENT_RE = re.compile(r"(\d{1,3})\s*%")
SEASON_OFF_RE = re.compile(r"season[\s_-]*off|시즌\s*오프", re.IGNORECASE)
FINAL_SALE_RE = re.compile(r"final[\s_-]*sale|end[\s_-]*of[\s_-]*season", re.IGNORECASE)
BF_RE = re.compile(r"black[\s_-]*friday|블랙[\s_-]*프라이데이", re.IGNORECASE)


def extract_max_percent(signals_field):
    """Find highest % in signals string."""
    return max((int(m) for m in PERCENT_RE.findall(signals_field)), default=None)


def has_concrete_offline(signals_field):
    """True if any non-noise concrete signal present."""
    return bool(
        SEASON_OFF_RE.search(signals_field)
        or FINAL_SALE_RE.search(signals_field)
        or BF_RE.search(signals_field)
        or PERCENT_RE.search(signals_field)
    )


def classify_tier(signals_field, max_pct):
    if max_pct is not None:
        return "exact"
    if SEASON_OFF_RE.search(signals_field) or FINAL_SALE_RE.search(signals_field) or BF_RE.search(signals_field):
        return "page"
    return "page"  # fallback


def make_offer(signals_field, brand):
    """Human-readable offer string from signals."""
    # Parse signal phrases
    parts = []
    for tok in signals_field.split(","):
        tok = tok.strip()
        if tok and tok != "-":
            parts.append(tok)
    return " · ".join(parts[:6]) if parts else "세일 진행 중"


def make_condition(signals_field, max_pct, tier):
    if SEASON_OFF_RE.search(signals_field):
        if max_pct is not None:
            return "시즌오프"
        return "할인율·종료일 미표기"
    if FINAL_SALE_RE.search(signals_field):
        if max_pct is not None:
            return "파이널 세일"
        return "할인율·종료일 미표기"
    if max_pct is not None:
        return "선택 상품"
    return "할인율·종료일 미표기"


def main():
    lines = open("rendered/summary.tsv", encoding="utf-8").read().splitlines()
    header = lines[0].split("\t")
    sales = []
    rejected_global = []
    rejected_noise = []
    rejected_stale = []
    rejected_novisual = []
    
    for line in lines[1:]:
        f = line.split("\t")
        if len(f) < 7:
            continue
        code, brand, input_url, final_url, status, signals, artifact = f[:7]
        
        if status == "stale-year":
            rejected_stale.append(f"{brand} ({status})")
            continue
        if status != "visible-candidate":
            rejected_novisual.append(brand)
            continue
        
        if code in REJECT:
            rejected_global.append(f"{brand} → {REJECT[code]}")
            continue
        
        if not has_concrete_offline(signals):
            rejected_noise.append(brand)
            continue
        
        max_pct = extract_max_percent(signals)
        tier = classify_tier(signals, max_pct)
        offer = make_offer(signals, brand)
        condition = make_condition(signals, max_pct, tier)
        
        url = final_url if final_url else input_url
        
        sales.append({
            "code": code,
            "brand": brand,
            "url": url,
            "offer": offer,
            "max": max_pct,
            "tier": tier,
            "condition": condition,
            "_signals": signals,
        })
    
    # Sort exact by max desc, page by brand name
    exact = sorted([s for s in sales if s["tier"] == "exact"], key=lambda x: (-(x["max"] or 0), x["brand"]))
    page = sorted([s for s in sales if s["tier"] == "page"], key=lambda x: x["brand"])
    
    result = {
        "exact": exact,
        "page": page,
        "rejected_global": rejected_global,
        "rejected_noise": rejected_noise,
        "rejected_stale": rejected_stale,
        "rejected_novisual": rejected_novisual,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
