# Issue #51 종결 초안

**대상**: #51 — [ir_builder] Always-inline of block-internal dimensions orphans *D -> purge cascade deletes INSERTs
**조회 시점 상태**: OPEN

## (a) 처분 제안

**CLOSE 권고.** 2단 폴백 설계(기본 인라인 OFF + rc53 실패 시만 자동 인라인 재빌드)가 채택·적용됐고, 워너청담(100%보존 31→41, ERROR 0 유지)과 HDC 267(PASS 182·평균보존 99.9854%) 양쪽 전체 재검증으로 효과가 확인됐다.

## (b) 닫기 조건

- [ ] 이 폴백 설계를 담은 커밋이 main에 머지·push됨이 확인
- [ ] TODO 2건(rc53 폴백 발동 이력 로깅, 인라인 재빌드 경로의 purge 연쇄 방지 가드)은 closure를 막지 않음 — 후속 이슈로 분리 권고

## (c) 게시용 코멘트 본문 (초안)

---

상시 인라인이 INSERT를 연쇄 소실시키는 문제는 "기본 OFF + rc53 실패 시만 자동 인라인 재빌드" 2단 폴백으로 확정·적용됐습니다. 워너청담(100%보존 도면 31→41, ERROR 0 유지)과 HDC 267개(PASS 182·평균보존 99.9854%) 양쪽 전체 재검증으로 효과를 확인했습니다. 상세는 `reports/HDC_ROUNDTRIP_CAMPAIGN.md` §4 참조.

수정 커밋이 main에 반영되면 닫습니다. 남은 TODO(rc53 폴백 이력 로깅, purge 가드)는 후속 이슈로 옮길 것을 제안합니다.

---
