# Issue #53 종결 초안

**대상**: #53 — [ir_builder] Periodic (closed) spline knots (ncp+1, ObjectARX convention) silently dropped -> rc53
**조회 시점 상태**: OPEN

## (a) 처분 제안

**CLOSE 권고.** 스플라인 분기 3단 재구성(표준 knot / periodic → ezdxf `set_closed` / 기타 → 합성 knot)이 적용·검증됐다. 검증 모집단은 옥포 16개 도면(HDC가 아님) — d012 재빌드로 rc=0·63,196개 전량 확인, 동일 원인 5개 도면(d001·d002·d007·d009·d010) 전부 ERROR→FAIL 전환.

## (b) 닫기 조건

- [ ] 스플라인 분기 재구성 커밋이 main에 머지·push됨이 확인
- [ ] TODO 2건(IR 스키마에 periodic/closed 플래그·knot 표현 규약 명시, rational(weights) periodic 케이스 점검)은 closure를 막지 않음 — 후속 이슈로 분리 권고

## (c) 게시용 코멘트 본문 (초안)

---

periodic(닫힌) 스플라인의 knot이 조용히 버려져 rc53으로 파일 전체가 거부되던 문제는 빌더 스플라인 분기를 3단(표준/periodic `set_closed`/합성 폴백)으로 재구성해 해결했습니다. 검증은 옥포동주상복합 16개 도면 기준입니다 — d012 재빌드로 완전 로드(rc=0, 63,196개 전량), 동일 원인이던 5개 도면 전부 ERROR→FAIL(파이프라인 완주)로 전환됐습니다. 상세는 `reports/HDC_ROUNDTRIP_CAMPAIGN.md` §3.1·§4 참조.

수정 커밋이 main에 반영되면 닫습니다. IR 스키마에 periodic 플래그를 명시하는 TODO는 후속 이슈로 옮길 것을 제안합니다.

---
