# Issue #55 종결 초안

**대상**: #55 — [ir_builder] Hatch boundary 'ellipse_arc' edges silently dropped + wrong major_axis/ratio convention -> 20 hatches lose all boundaries
**조회 시점 상태**: OPEN

## (a) 처분 제안

**CLOSE 권고.** edge 타입명 불일치(`ellipse_arc` vs `ell_arc`) 인식 추가와 `major_axis`/`radius_ratio` 필드 규약 수정이 적용·검증됐다. 검증 모집단은 옥포 16개 도면(HDC가 아님) — `hatch_no_boundary` 20→0, rc53 회귀 없음, 옥포 전체 재검증 보존율 99.9893%.

## (b) 닫기 조건

- [ ] 수정 커밋이 main에 머지·push됨이 확인
- [ ] TODO 3건(IR 스키마에 edge type 문자열 규약 고정, 미인식 edge type 카운터 추가, major_axis 정규화 여부 명시)은 closure를 막지 않음 — 후속 이슈로 분리 권고

## (c) 게시용 코멘트 본문 (초안)

---

해치 경계의 `ellipse_arc` edge가 빌더 dispatch(`ell_arc`만 인식)에서 무시되고, 인식되더라도 `major_axis`(단위벡터)를 크기 벡터로 오인해 타원이 원으로 찌그러지던 문제를 수정했습니다. 검증은 옥포동주상복합 16개 도면 기준입니다 — `hatch_no_boundary` 20건이 전부 0으로, rc53 회귀 없이(d003·d014 로드 검증), 옥포 전체 재검증 보존율 99.9893%(605,647→605,582 엔티티, 잔여 손실은 전부 OLE·래스터·REGION 등 외부 파일 의존)로 확인됐습니다. 상세는 `reports/HDC_ROUNDTRIP_CAMPAIGN.md` §3.3·§4 참조.

수정 커밋이 main에 반영되면 닫습니다. 미인식 edge type을 조용히 무시하지 않고 카운터로 드러내는 TODO는 후속 이슈로 옮길 것을 제안합니다.

---
