# Issue #54 종결 초안

**대상**: #54 — [ir_builder] Case-sensitive 'Standard' prune deletes referenced dimstyle 'STANDARD' -> rc53
**조회 시점 상태**: OPEN

## (a) 처분 제안

**CLOSE 권고.** 대소문자 구분 비교로 실제 참조 중인 dimstyle을 오삭제하던 문제가 수정·검증됐다. 검증 모집단은 옥포 d014·d016(HDC가 아님) — 재빌드 후 `prune_dimstyle_std` 미발동, 변환 rc=0·71,174개 전량, 두 도면 모두 ERROR→FAIL 전환.

## (b) 닫기 조건

- [ ] 수정 커밋이 main에 머지·push됨이 확인
- [ ] TODO 2건(심볼테이블 이름 비교 전반의 무구분 일괄 감사, DXFIN 오류 출력 상시 로깅)은 closure를 막지 않음 — #58과 함께 후속 이슈로 통합 분리 권고(동일 대소문자 함정 계열)

## (c) 게시용 코멘트 본문 (초안)

---

`Standard`/`STANDARD` 대소문자 구분 비교로 빌더가 실제 참조 중인 dimstyle을 purge 대상으로 오판·삭제해 rc53으로 파일 전체가 거부되던 문제를 수정했습니다. 검증은 옥포동주상복합 d014·d016 기준입니다 — 재빌드 후 오삭제 미발동, 변환 rc=0(71,174개 전량), 두 도면 모두 ERROR→FAIL(파이프라인 완주) 전환됐습니다. 상세는 `reports/HDC_ROUNDTRIP_CAMPAIGN.md` §3.1·§4 참조.

이 이슈는 #58(대소문자 **무구분** 조회로 인한 반대 방향 오염)과 동일한 "심볼테이블 이름 대소문자 취급 불일치" 계열입니다. 심볼테이블 이름 비교 전반의 무구분 일괄 감사 TODO는 #58과 묶어 별도 후속 이슈로 옮길 것을 제안합니다. 수정 커밋이 main에 반영되면 닫습니다.

---
