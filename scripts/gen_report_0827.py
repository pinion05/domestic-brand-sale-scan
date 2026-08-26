#!/usr/bin/env python3
"""Generate reports/2026-08-27.md from docs/sales-2026-08-27.json (tables stay consistent)."""
import json
from pathlib import Path

d = json.loads(Path('docs/sales-2026-08-27.json').read_text(encoding='utf-8'))
yd = json.loads(Path('docs/sales-2026-08-26.json').read_text(encoding='utf-8'))
src = d['source']
sales = [s for s in d['sales'] if s['tier'] == 'exact']
pages = [s for s in d['sales'] if s['tier'] == 'page']
y_in = {s['brand'] for s in yd['sales']}
t_in = {s['brand'] for s in d['sales']}
new = sorted(t_in - y_in)
gone = sorted(y_in - t_in)

L = []
L.append('# 2026-08-27 국내 패션 브랜드 공식몰 세일 리포트')
L.append('')
L.append(f"**검증 시각**: {d['verifiedLabel']}")
L.append('')
L.append('## 조사 범위')
L.append('')
L.append(f"- 무신사 랭킹 API {src['rankingPages']}페이지 순회 → 브랜드 후보 {src['brandCandidates']}개")
L.append(f"- 누적 레지스트리 320개(known) 전체 + 신규 후보 중 콘크리트 세일 신호 51개 → 렌더링 {src['renderedUrls']}개 URL")
L.append(f"- agent-browser 렌더링 기준 visible-candidate 243개 → 신원·멤버십·신상·글로벌 필터 → **최종 {src['finalBrands']}개 브랜드** (할인율 확인 {src['exactOffers']} + 세일 페이지 {src['openSalePages']})")
L.append('')
L.append(f"## 세일 브랜드 (할인율 확인 — exact {len(sales)}곳)")
L.append('')
L.append('| 브랜드 | 최대 할인 | 공식몰 | 확인 문구 |')
L.append('|---|---|---|---|')
for s in sales:
    offer = s['offer'] if len(s['offer']) <= 70 else s['offer'][:67] + '…'
    L.append(f"| {s['brand']} | {s['max']}% | {s['url']} | {offer} |")
L.append('')
L.append(f"## 세일 페이지 오픈 (시즌오프 등 — page {len(pages)}곳)")
L.append('')
L.append('| 브랜드 | 공식몰 | 확인 문구 |')
L.append('|---|---|---|')
for s in pages:
    L.append(f"| {s['brand']} | {s['url']} | {s['condition']} |")
L.append('')
L.append('## 전일 대비 변동')
L.append('')
new_note = {
    '레떼드폴린': "26' Clearance Sale 8.25–9.10 UP TO 60%",
    '부붐': '시즌 오프 ~84%',
    '호이테': 'SEASON OFF SALE UP TO 70%',
    '아틀리에 나인': '단 48H TIME SALE ~80%',
    '론론': 'SUMMER SEASON OFF 페이지',
    '앳코너': 'SEASON OFF 페이지',
    '엘무드': 'SEASON OFF 페이지',
    '이피티': 'SEASON OFF 페이지',
    '테일던': 'SEASON OFF 페이지',
}
gone_note = {
    '디유아모르': '모이사나이트 주얼리 — 비패션 제외',
    '샤르드': '도메인이 마스크팩/세럼 뷰티몰 — 비패션 제외',
    '시도': '세일 문구 소멸',
    '시오': 'sio.kr 404 — UP TO 70% 페이지 비활성',
    '애즈온': '재렌더(대기 4초)에도 세일 문구 미가시',
    '에핑글러': 'PRE-ORDER FW26 1st DROP — 신상 오픈 전환',
    '유에프씨 스포츠': '회원가입 쿠폰만 노출, 가시 할인율 없음',
    '프루티드': '헤어케어 뷰티 — 비패션 제외',
    '플리즈노팔로우': "26HS 'Tropical Haze' OPEN SALE — 신상 오픈 노이즈",
}
L.append(f"- 신규 진입 {len(new)}: " + ', '.join(f"{b}({new_note.get(b, '')})" for b in new))
L.append(f"- 이탈 {len(gone)}: " + ', '.join(f"{b}({gone_note.get(b, '')})" for b in gone))
y_tot = yd['source']['finalBrands']
L.append(f"- 전일 {y_tot}개 → 오늘 {src['finalBrands']}개 ({src['finalBrands'] - y_tot:+d}, exact {yd['source']['exactOffers']}→{src['exactOffers']} · page {yd['source']['openSalePages']}→{src['openSalePages']})")
L.append('')
L.append('## 제외 로그')
L.append('')
for e in d['excluded']:
    L.append(f"### {e['label']} ({len(e['items'])})")
    L.append('')
    for it in e['items']:
        L.append(f"- {it}")
    L.append('')
L.append('## 주의')
L.append('')
L.append('- 렌더링은 최종 증거. SPA(29CM·아임웹·카페24)는 curl 판단 불가 대상.')
L.append('- 회원가입/카톡채널 쿠폰, 신상 오픈 기념 할인은 세일에서 제외 (스킨 노이즈).')
L.append('- 사업자등록번호/저작권 연도는 stale 판정에서 제외, 캠페인 연도만 판단.')
L.append('- `max`는 화면에 가시 표기된 최대 할인율 정수. 조건(회원가 등)은 문구 참조.')
L.append('- 리그·마인드브릿지·쥬시쥬디는 tbhshop.co.kr 공용 도메인 렌더 결과를 공유.')
L.append('- 무아르무스의 max=30%는 TIME SALE 제품 할인가 기준(카톡채널 10% 쿠폰 제외).')
Path('reports/2026-08-27.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
print(f"report: {len(sales)} exact + {len(pages)} page, new={len(new)}, gone={len(gone)}")
