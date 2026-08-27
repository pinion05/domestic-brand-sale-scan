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
    "laka": "라카 — (주)라카코스메틱스 립밤/립세럼 뷰티 브랜드 (패션 의류 아님)",
    "shokz": "샥즈 — 골전도 헤드폰/오디오 기기 글로벌 브랜드 (패션 아님)",
    "allsaints": "올세인츠 — 영국 글로벌 패션 브랜드 한국 스토어 (국내 브랜드 아님)",
    "shioeip": "시오 이아이피 — 신규 회원 첫 구매 10% 할인 쿠폰 (회원 노이즈)",
    "dieuamour": "디유아모르 — 모이사나이트 목걸이 주얼리 (패션 의류 아님)",
    "scentlier": "센틀리에 — 퍼퓸룸앤패브릭스프레이 향수/홈프래그런스 브랜드 (패션 의류 아님)",
    "lussocloud": "루쏘 클라우드 — 미국 컴포트 슬리퍼 브랜드, USD 가격 (한국 패션 아님)",
    "sergiotacchini": "세르지오 타키니 — 이탈리아 테니스웨어 글로벌, USD 가격 (한국 브랜드 아님)",
    "rumtton": "럼튼 — 시계 전문 브랜드 (패션 의류 아님)",
    "prooted": "프루티드 — 샴푸/트리트먼트 헤어케어 브랜드 (패션 의류 아님)",
    "beanpoleacc": "빈폴 액세서리 — SSFShop 플랫폼 매장 (공식몰 아님) — 재제외",
    "rawrow": "로우로우 — 캐리어/트렁크 브랜드 (패션 의류 아님) — 재제외",
    "roundlab": "라운드랩 — 스킨케어/선케어 뷰티 브랜드 (패션 아님)",
    "tirtir": "티르티르 — 스킨케어 뷰티 브랜드 (패션 아님)",
    "bbia": "삐아 — 화장품/색조 뷰티 브랜드 (패션 아님) — 재제외",
    "sungbooneditor": "성분에디터 — 스킨케어 뷰티 브랜드 (패션 아님)",
    "dinto": "딘토 — 화장품/뷰티 브랜드 (패션 아님)",
    "lush": "러쉬 — 글로벌 뷰티/코스메틱 브랜드 (패션 아님)",
    "bose": "보스 — 음향기기/헤드폰 브랜드 (패션 아님)",
    "byc": "비와이씨 — 속옷/이너웨어 제조사 몰, 시즌 캠페인 아님",
    "uiq": "유이크 — 바이옴 레미디 선크림/쿨링패드 뷰티 (패션 아님)",
    "hyfve": "하이파이브 — LA 도매 여성복 쇼룸 (로스앤젤레스, 한국 공식몰 아님)",
    "cloop": "클룹 — 탄산음료/음료 브랜드 (패션 아님) — 재제외",
    "ilio": "에이던엠 — ilio.com 음악 소프트웨어/플러그인 판매 (패션 아님)",
    "charde": "샤르드 — 마스크팩/세럼 뷰티 브랜드 (패션 아님) — 재제외",
    "olivet": "올리베 — 테이블웨어/폰케이스 리빙 잡화 (패션 의류 아님)",
    "belier2": "벨리에 — belier.com 크로셋 의류 글로벌, EUR 가격 (한국 패션 아님)",
    "fully": "풀리 — fully.com = Herman Miller 가구 (Fall Sale 25% off, 패션 아님) — 재제외",
    # 2026-08-27 verdicts (verified in today's rendered artifacts):
    "vanwalk": "반워크 — vanwalk.com USD 가격 해외몰 (한국 공홈 아님) — 재제외",
    "outstanding": "아웃스탠딩 — outstanding.kr IT/투자 뉴스 미디어 (패션 아님) — 재제외",
    "doingwhat": "두잉왓 — 다크서클 매직 펜슬·스킨톤 로션 등 뷰티/화장품 브랜드 (패션 아님)",
    "positano": "포지타노 — 레몬 사탕·캔디 식품 브랜드 (패션 아님) — 재제외",
    "valik": "발릭 — 주얼리 제작 브랜드, B.B NEW DROP 10% (패션 의류 아님)",
    # 2026-08-28 verdicts (verified in today's rendered artifacts):
    "fitflop": "핏플랍 — ssfshop.com/fitflop 플랫폼 매장 (공식몰 아님)",
    "merzbschwanen": "메르츠 비 슈바넨 — 독일 글로벌몰 EUR 가격 + 뉴스레터 10% 쿠폰 (한국 패션 아님)",
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
    "limelightapparel": "라임라잇 어패럴 — 신규 회원 가입 시 10% 할인 쿠폰 (회원 노이즈)",
    "noice": "노이스 — 카카오톡 채널 추가 시 10% OFF 혜택 (채널 노이즈)",
    "kitschnkiss": "키치앤키스 — 신규 회원 30% off coupon (회원 노이즈)",
    "wwwkitschnkiss": "키치앤키스 — 신규 회원 30% off coupon (회원 노이즈)",
    "bemymood": "비마이무드 — 신규 회원 가입 시 10% 할인 쿠폰 (회원 노이즈)",
    "cellfusionc": "셀퓨전씨 — 뉴스레터 구독 GET 10% OFF (회원 노이즈)",
}
# remove placeholders and entries whose artifact evidence showed a real campaign
for _ph in [k for k, v in COUPON_REJECT.items() if v == "placeholder" or "유지 검토 결과 실제 캠페인" in v]:
    del COUPON_REJECT[_ph]
# Real campaigns found in today's artifacts (keep despite coupon menu presence):
#   surfea (FINAL SEASON OFF), prodeshirt (SEASON OFF menu)
#   bibyseob (26 SUMMER 10% off banner), hieta 15% OFF product prices
#   prospecs 여름 ~30% OFF, illigo BRAND WEEK UP TO 40%, alavague BAG TO SCHOOL UP TO 50%
#   andar / xexymix: real 26SS 시즌오프 campaigns visible -> keep
#   codescombineinnerwear: SUMMER PICKS ~51% dated 08.10-08.24 real campaign -> keep
for _keep in ["hieta", "prospecs", "illigo", "alavague"]:
    COUPON_REJECT.pop(_keep, None)

# 2026-08-27 verdicts (today's rendered-artifact evidence):
#   RESTORED as real campaigns (removed from COUPON_REJECT — campaign visible today):
#     muarmus/wwwmuarmus: TIME SALE 20~30% countdown on products -> KEEP sale
#     doffjason/doffjason2: SEASON OFF menu visible -> KEEP page
#     leire(르아르): 블랙프라이데이 ~88% + 세일 카테고리 — 전일 exact 유지
#     ronron/atcorner/lmood/ept/taildern: SEASON OFF menu visible -> KEEP page
#     boovoom(시즌 오프 ~84%), heute(SEASON OFF UP TO 70%), nain(TIME SALE ~80%),
#     letedepauline(26' Clearance 8.25-9.10 UP TO 60%) -> KEEP exact
#   NEW rejects (membership/coupon/new-open noise, no season campaign):
for _restore in ["muarmus", "wwwmuarmus", "doffjason", "doffjason2", "leire", "rosie"]:
    COUPON_REJECT.pop(_restore, None)
COUPON_REJECT.update({
    # 2026-08-28 verdicts (today's rendered-artifact evidence):
    "muarmus": "무아르무스 — 카카오톡 채널 추가 시 10% 할인 쿠폰만 가시 (TIME SALE 소멸) — 재제외",
    "wwwmuarmus": "무아르무스 — 카카오톡 채널 10% 쿠폰만 가시 — 재제외",
    "blueing": "블루잉 — 첫 회원가입시 20% 할인 쿠폰 즉시 지급 (회원 노이즈)",
    "urago": "유라고 — 26FW 1st collection 신상 15% 할인 (신상 오픈 노이즈)",
    "painorpleasure": "페인오어플레져 — 26FW MIDNIGHT TIDE 1st Drop 15% (신상 오픈 노이즈)",
    "fingersuit": "핑거수트 — 26 TONE-UP STRENGTHENER 론칭 혜택 ~15% (신상 오픈 노이즈)",
    "epingler": "에핑글러 — PRE-ORDER 25% OFF FW26 1ST DROP (신상 예약판매 노이즈)",
    # legacy (2026-08-27 and earlier) follows:
    "notyourrose": "낫 유어 로즈 — 26Autumn Collection 신상 10% + 회원가입 5,000P (신상·회원 노이즈)",
    "rosie": "로지 — 신상 5% 할인 + 회원가입 쿠폰발급 (회원·신상 노이즈)",
    "miuki": "미유키 — 7.15 발매 기념 최대 20% (신상 오픈 혜택)",
    "friver07": "프리버07 — New Item 15% OFF 26 FALL 1st DROP (신상 오픈 노이즈)",
    "ayasnsey": "아야즈앤세이 — 첫 FW 컬렉션 발매 기념 30% (무신사 발매 기념 — 신상·타플랫폼 혜택)",
    "bibyseob": "바이바이섭 — 여름 신상 자사몰 10% 할인 (신상 오픈 혜택)",
    "rubymerlot": "루비멀로 — Sign up 이메일 가입 10% (회원 노이즈)",
    "tuomio": "뚜오미오 — 카카오 채널추가 20% 쿠폰 (채널 노이즈) — 재제외",
    "louisquatorze": "루이까또즈 — Sign up 15% off first order (회원 노이즈) — 재제외",
    "maxza": "마쟈 — 신규회원 최대 20% 쿠폰 (회원 노이즈) — 재제외",
    "wwwmontbell": "몽벨 — 회원가입 5% 쿠폰 (회원 노이즈) — 재제외",
    "mucuandebony": "무쿠앤에보니 — 이달의 신규회원 20% OFF (회원 노이즈) — 재제외",
    "ikalook": "이카룩 — 첫 쇼핑 회원가입 20% 쿠폰 (회원 노이즈) — 재제외",
    "eprlayer": "이피알 레이어 — 신규 회원 10% Welcome 쿠폰 (회원 노이즈) — 재제외",
    "toulnbrick": "툴룬즈브릭 — JOIN NOW & SAVE 10% 신규회원 쿠폰 (회원 노이즈) — 재제외",
    "formlich": "폼리쉬 — 신규 가입 3% 쿠폰 (회원 노이즈) — 재제외",
    "hervino": "에르비노 — 신규 회원가입 20% 쿠폰 + 적립금 (회원 노이즈) — 재제외",
    "vacantarchive": "베이컨트 아카이브 — KAKAOTALK FRIENDS 10% 쿠폰 (채널 노이즈) — 재제외",
    "surfea": "써피 — 신규회원 10% 할인 쿠폰만 남음 (FINAL SEASON OFF 소멸) — 재제외",
    "hieta": "히에타 — 신규 가입 10% 할인쿠폰 + 적립금만 가시 (제품 할인가 소멸) — 재제외",
    "prospecs": "프로-스펙스 — 신규 가입시 10%OFF 쿠폰만 가시 — 재제외",
    "codescombineinnerwear": "코데즈컴바인 이너웨어 — 첫구매 베스트 20% 혜택만 남음 (SUMMER PICKS ~51%는 08.24 종료) — 재제외",
    "gemgemparadis": "젬젬파라디 — 신규 회원가입 10% 쿠폰 (회원 노이즈)",
    "desporte": "데스포르치 — 신규 가입 3,000원 쿠폰 + 등급별 최대 5% 적립 (회원·적립 노이즈)",
    "horlisun": "홀리선 — 08.26 5일 한정 10% + 카카오채널 5% 쿠폰 (기한·채널 노이즈)",
    "snoya": "스노야 — 공식몰 오픈 기념 30%/26FW 런칭 10% (오픈·신상 노이즈)",
    "firenzeatelier": "피렌체 아뜨리에 — 회원등급별 최대 20% 추가할인 + 카톡채널 5% 쿠폰 (멤버십 노이즈) — 재제외",
    "outdoorvoices": "아웃도어 보이스 — 26 가을/겨울 컬렉션 발매 10% + 회원가 (신상·멤버십) — 재제외",
    "thevinylhouse": "더바이닐하우스 — 4주년 40% OFF가 3월 15–18일 과거 프로모션 (현재 캠페인 없음) — 재제외",
})

# 2026-08-23 verdicts (verified in today's rendered artifacts):
#   cornell/캔버스: cornell.com = Cornell Communications 미국 널스콜/비상벨 장비 (패션 아님) -> identity reject
#   anytimeloreak/애니타임로릭: ~30~85% 는 할인 카테고리 메뉴명. 카테고리/상품 페이지 모두 정가
#     표기 — 실제 할인가 없음 -> menu-noise reject
#   avvinapelle/아비나펠르: Refurb Sale (60% off) 카테고리 12개 전품목 SOLD OUT — 구매 가능한
#     할인 제품 없음 -> reject
#   ouat/오우앗: 2/25-3/16 기간의 '회원가입시 30% 쿠폰' 팝업 — 과거+회원 노이즈 -> reject
#   tolance/토런스: SUMMER FINAL WEEK UP TO 64% + 제품 할인가 — 실제 캠페인 -> keep
#   511vision/511비전: HOT SUMMER SEASON OFF SALE ~8/23 마감 — 실제 시즌오프 -> keep
NAME_REJECT = {
    "캔버스": "캔버스 — cornell.com = Cornell Communications 미국 널스콜/비상벨 장비 (패션 아님)",
    "애니타임로릭": "애니타임로릭 — ~30~85% 카테고리 메뉴명, 제품 정가 표기 (할인가 없음) — 메뉴 노이즈",
    "아비나펠르": "아비나펠르 — Refurb Sale(60% off) 전품목 SOLD OUT (구매 가능 할인 제품 없음)",
    "오우앗": "오우앗 — 2/25~3/16 회원가입 30% 쿠폰 팝업 (과거+회원 노이즈)",
}

# 2026-08-22 new-brand render evidence:
#   nastyfancyclub: SEASON-OFF SALE UP TO 65% (2026 S/S) — real campaign -> keep
#   skullpig: 쿨링세일 최대~90% — real campaign -> keep
#   romantinuer: BEST ITEMS UP TO 20% OFF 카테고리 한정 할인 — real campaign -> keep
#   vacantarchive: 시즌오프 메뉴 활성. 노출 %는 08.24 신상 예약가(10%)와 카카오친구
#     10% 쿠폰뿐 → % 신호는 노이즈, 시즌오프 페이지만 인정 (page/null).
VACANT_PAGE_ONLY = {"vacantarchive"}
# 2026-08-28: visible % is membership-signup coupon only; SEASON OFF menu remains
# (이피티 EPT 회원가입 10%, 찰스앤키스 뉴스레터/회원가입 10%, 테일던·프로드셔츠 회원가입 10% 쿠폰)
PAGE_ONLY = {"ept", "charleskeith", "taildern", "prodeshirt"}

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
    # brand-name-keyed maps (values are "브랜드명 — 사유") work regardless of code scheme,
    # so registry renders keyed by hostname still get yesterday's verified rejections.
    id_by_name = {v.split(" — ")[0]: v for v in IDENTITY_REJECT.values()}
    cp_by_name = {v.split(" — ")[0]: v for v in COUPON_REJECT.values()}
    rejected_name_set = set()  # names rejected below; recovery must not resurrect them
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
            rejected_name_set.add(r["brand"])
            continue
        if code in COUPON_REJECT:
            ex_coupon.append(COUPON_REJECT[code])
            rejected_name_set.add(r["brand"])
            continue
        if r["brand"] in NAME_REJECT:
            reason = NAME_REJECT[r["brand"]]
            (ex_identity if "패션 아님" in reason else ex_coupon).append(reason)
            rejected_name_set.add(r["brand"])
            continue
        if r["brand"] in id_by_name:
            ex_identity.append(id_by_name[r["brand"]])
            rejected_name_set.add(r["brand"])
            continue
        if r["brand"] in cp_by_name:
            ex_coupon.append(cp_by_name[r["brand"]])
            rejected_name_set.add(r["brand"])
            continue
        max_pct = extract_max_pct(r["signals"])
        if code in VACANT_PAGE_ONLY:
            max_pct = None
        if code in PAGE_ONLY:
            max_pct = None
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
                      {code_brand[c] for c in COUPON_REJECT if c in code_brand} | \
                      rejected_name_set
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
        if r["code"] in VACANT_PAGE_ONLY or r["code"] in PAGE_ONLY:
            max_pct = None
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
