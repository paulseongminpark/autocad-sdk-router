# Issue #60 종결 초안

**대상**: #60 — [ir_builder] ezdxf pre-created 'Defpoints' layer casing wins over original 'DEFPOINTS' -> every entity on that layer mismatches (POINT 7,326 in HDC 267)
**조회 시점 상태**: OPEN

## (a) 처분 제안

**CLOSE 권고.** 사전 생성 레이어와 케이스만 다르면 버리고 원본 케이싱으로 재생성하는 가드가 적용·검증됐다(d031). 이 이슈는 **HDC 267 재검증**에서 직접 나온 것이므로(옥포가 아님) HDC 수치로 인용 가능한 몇 안 되는 §3.3 항목 중 하나다. 부가로 실은 HDC L1 실패 68건의 원인 분포(OLE 47·MULTILEADER 14·REGION 5·기타 2) — HDC의 엄격 PASS 상한이 구조적으로 정해져 있다는 근거 — 도 이 이슈에서 나왔으며, 이는 이미 `reports/HDC_ROUNDTRIP_CAMPAIGN.md` §5(잔여·이연 목록)에 반영했다.

## (b) 닫기 조건

- [ ] 레이어 재생성 가드 커밋이 main에 머지·push됨이 확인
- [ ] TODO 2건(같은 함정을 선생성 항목 전반 — 선종류 `ByLayer`/`ByBlock`/`Continuous`, 텍스트/치수 스타일 `Standard` — 에 일괄 적용, MULTILEADER 네이티브 지원)은 closure를 막지 않음 — 후속 이슈로 분리 권고(MULTILEADER는 #59에서도 별도 과제로 교차 언급됨)

## (c) 게시용 코멘트 본문 (초안)

---

ezdxf가 문서 생성 시 미리 만드는 `Defpoints` 레이어의 케이싱이 원본 `DEFPOINTS`를 이겨, 그 레이어의 모든 엔티티가 레이어명 불일치로 미매칭되던 문제(HDC 재검증 L4 잔차 최대 항목, POINT 7,326건)를 수정했습니다. 사전 생성 레이어와 케이스만 다르면 버리고 원본 케이싱으로 재생성하는 가드를 추가했고, d031에서 레이어 테이블 `DEFPOINTS` 복구·POINT 895개 정상 배치를 확인했습니다. 이 이슈는 #54(대소문자 과잉 구분)·#58(대소문자 과잉 무구분)과 같은 함정의 세 번째 발현입니다.

부가로, 같은 재검증에서 HDC L1 실패 68건의 원인 분포를 확인했습니다: AcDbOle2Frame(OLE, #43 관련) 47건은 구조적으로 복원 불가, MULTILEADER→LEADER 다운그레이드 14건은 가능하나 별도 과제, REGION(ACIS) 5건은 구조적 불가, 기타(XLINE/IMAGE 등) 2건. **HDC는 OLE 객체가 든 도면이 47개라 엄격 판정 PASS율에 구조적 상한이 있습니다** — 이 사실은 `reports/HDC_ROUNDTRIP_CAMPAIGN.md` §5에 반영했습니다.

수정 커밋이 main에 반영되면 닫습니다. 선생성 항목 전반에 대한 일괄 적용과 MULTILEADER 네이티브 지원은 후속 이슈로 옮길 것을 제안합니다.

---
