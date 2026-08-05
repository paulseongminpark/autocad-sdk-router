# Issue #59 종결 초안

**대상**: #59 — [ir_builder] LEADER downgraded to POLYLINE (137->0 in d014) + LWPOLYLINE elevation/Z dropped entirely
**조회 시점 상태**: OPEN

## (a) 처분 제안

**CLOSE 권고.** LEADER를 `add_leader`로 네이티브 처리하는 수정과 LWPOLYLINE `elevation` 필드 복원 수정 둘 다 적용·검증됐다. 검증 모집단은 옥포 d014·d004(HDC가 아님). MULTILEADER(6건)는 이 이슈 범위에서 명시적으로 "별도 과제"로 남겨진 미지원 항목이다.

## (b) 닫기 조건

- [ ] 두 수정 커밋이 main에 머지·push됨이 확인
- [ ] TODO 2건(IR에 LWPOLYLINE elevation 명시적 필드 추가, LEADER의 dimstyle 참조를 IR에 포함)은 closure를 막지 않음 — 후속 이슈로 분리 권고
- [ ] MULTILEADER 네이티브 지원은 이 이슈 본문이 스스로 "별도 과제"로 분리한 항목 — 새 이슈로 전환 권고(#60의 구조적 한계표에도 "14건, 가능·별도 과제"로 교차 언급됨)

## (c) 게시용 코멘트 본문 (초안)

---

두 결함을 수정했습니다: ① 빌더가 `leader`를 `add_polyline3d`로 대체해 LEADER 개체성이 전량 소실되던 문제(d014에서 137→0) → ezdxf `add_leader`로 네이티브 처리, ② LWPOLYLINE의 Z가 정점이 아니라 `elevation`(DXF group 38)에 담기는데 빌더가 정점 X/Y만 읽어 Z가 전량 0이 되던 문제(d004에서 최대 200만 단위 차이) → elevation 필드 복원.

검증(옥포동주상복합 기준): d014에서 LEADER 137개 생성, 변환 rc=0(ENTCOUNT 71,174 동일, 회귀 없음), 옥포 L4 잔차 1,227→717(d014 단독 332→58); d004에서 elevation≠0인 LWPOLYLINE 107개 복원. 상세는 `reports/HDC_ROUNDTRIP_CAMPAIGN.md` §3.3·§4 참조.

두 커밋이 main에 반영되면 닫습니다. MULTILEADER(6건 미지원)는 이 이슈 본문이 스스로 별도 과제로 분리했으므로 새 이슈로 전환할 것을 제안합니다.

---
