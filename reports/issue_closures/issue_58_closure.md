# Issue #58 종결 초안

**대상**: #58 — [ir_builder] SHAPE-file STYLE records dropped by name filter; named shape record 'STANDARD' corrupts text style 'Standard' font to SYMBOL
**조회 시점 상태**: OPEN

## (a) 처분 제안

**CLOSE 권고.** 이름 없는 SHAPE 레코드가 전량 소실되던 문제와, 이름 있는 shape 레코드 `STANDARD`가 대소문자 무구분 조회로 텍스트스타일 `Standard`의 폰트를 오염시키던 문제 둘 다 수정·검증됐다. 검증 모집단은 옥포(7개 도면, 24건 오염 / 16개 도면 전체 PASS 집계, HDC가 아님).

## (b) 닫기 조건

- [ ] 수정 커밋(빌더의 `is_shape_file` 분기 + 검증기의 shape 레코드 고유 폰트 집합 정규화) 둘 다 main에 머지·push됨이 확인
- [ ] TODO 2건(심볼테이블 이름 비교 전반 무구분 일괄 감사 — #54와 함께, 추출기의 shape 레코드 `name` 필드가 왜 `STANDARD`로 나오는지 확인)은 closure를 막지 않음 — 후속 이슈로 분리 권고

## (c) 게시용 코멘트 본문 (초안)

---

두 겹의 결함을 수정했습니다: ① 이름 없는 SHAPE 파일 STYLE 레코드가 `if not nm: continue`로 전량 소실되던 문제, ② 이름이 `STANDARD`인 shape 레코드가 ezdxf의 대소문자 무구분 심볼테이블 조회로 기존 텍스트스타일 `Standard`와 동일시되어 font가 `SYMBOL`로 덮어써지던 오염(옥포 7개 도면 24건 확인). `is_shape_file`이면 이름과 무관하게 `add_shx` 경로로 분리 처리하도록 고쳤고, 검증기도 shape 레코드를 고유 폰트 집합 기준으로 비교하도록 정규화했습니다.

검증(옥포동주상복합 기준): d012에서 `Standard` 폰트 arial.ttf 정상 복구, L1·L4·L5 전부 PASS. 검증기 정규화 이후 옥포 16개 도면 PASS 1→4, L2 실패 도면 14→0. 상세는 `reports/HDC_ROUNDTRIP_CAMPAIGN.md` §3.3·§4 참조.

이 이슈는 #54(대소문자 **구분** 비교로 인한 반대 방향 결함)와 동일 계열이며, #60이 세 번째 발현입니다. 두 커밋이 main에 반영되면 닫습니다. 심볼테이블 이름 비교 전반의 무구분 일괄 감사 TODO는 #54와 묶어 후속 이슈로 옮길 것을 제안합니다.

---
