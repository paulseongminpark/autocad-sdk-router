# Issue #56 종결 초안

**대상**: #56 — [ir_builder] 3DFACE (AcDbFace) has no dispatch branch -> all 136 lost in d008
**조회 시점 상태**: OPEN

## (a) 처분 제안

**CLOSE 권고.** `add_entity` dispatch에 `face3d` 분기를 추가해 3DFACE 전량 손실을 해결, 단위테스트+실측으로 검증됐다. 검증 모집단은 옥포 d008(HDC가 아님) — 생성 개수 136→136, edge_visibility 비트 패턴 완전 일치, d008 보존율 99.84%→99.99%.

## (b) 닫기 조건

- [ ] 수정 커밋이 main에 머지·push됨이 확인
- [ ] TODO 1건(다른 미지원 엔티티 종류가 `skipped` 카운터에만 남고 조용히 사라지는지 점검)은 closure를 막지 않음 — 후속 이슈로 분리 권고(단, REGION 5건은 ACIS 구조적 불가로 이미 확인됨 — 출처 #56 TODO, #60 구조적 한계표)

## (c) 게시용 코멘트 본문 (초안)

---

`build_from_ir.py`의 `add_entity` dispatch에 `solid`(AcDbSolid) 분기는 있었지만 `face3d`(AcDbFace) 분기가 없어 3DFACE가 전량 `skipped`로 사라지던 문제를 수정했습니다. 검증은 옥포동주상복합 d008 기준입니다 — 생성 개수 136(원본)→136(복원) 완전 일치, invisible_edges 비트 패턴(2|8=10) 및 Z좌표까지 왕복 보존 확인, d008 도면 보존율 99.84%→99.99%(L4 콘텐츠 불일치 232→96). 상세는 `reports/HDC_ROUNDTRIP_CAMPAIGN.md` §3.3·§4 참조.

수정 커밋이 main에 반영되면 닫습니다. 다른 미지원 엔티티 종류가 조용히 skip되는지 점검하는 TODO는 후속 이슈로 옮길 것을 제안합니다(REGION 5건은 ACIS 구조적 불가로 이미 확인됨).

---
