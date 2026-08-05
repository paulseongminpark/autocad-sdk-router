# REPORT — HDC 캠페인 봉인 (docs/hdc-campaign-closure)

## STATUS

**PASS**

## 한 일

HDC(현대_더에이치클라스트) 267개 도면 왕복검증 캠페인(이슈 #52)의 지식을 GitHub 이슈 스레드에서 repo 문서로 승격 보존했다. 이슈 #49~#60(12건) 전문을 `gh issue view`로 읽어(전문 확보 방법: 처음 12건 일괄 조회에서 응답 크기 초과로 3건 누락되어, 부족분 5건(53·57·58·59·60)과 55는 개별 재조회로 보완 — 12건 전부 본문 원문 확보 완료), 캠페인 개요·결과 총괄·결함 분류(rc53급 전체거부/지배적 FAIL/데이터 소실/오탐/난제·외부의존)·이슈별 수리 기록·잔여 이연 목록 구조로 보고서를 작성했다. 이슈별 수리 기록에는 각 결함이 HDC 267 모집단에서 나온 것인지, 병행 진행된 옥포동주상복합(옥포) 16개 도면 모집단에서 나온 것인지를 구분 표기해, 옥포의 검증 수치(예: #58 "옥포 PASS 1→4")를 HDC 수치로 오인하지 않도록 했다. 이슈 본문 자체의 산술 불일치(#52 잔여 FAIL 표: 하위항목 합 71 vs 표제 70건)와 판단 불가 항목(HDC 텍스트 미세 위치이동 49건이 #57의 검증기 오탐과 같은 원인인지는 이슈 본문에 HDC 직접 재확인 언급 없음)은 임의로 재구성하지 않고 UNKNOWN으로 명기했다. 이어 12건 각각의 종결 코멘트 초안을 작성했다 — #50은 오픈 유지(이 워크트리는 실물 도면·네이티브 추출기 접근이 막혀 있어 재현 불가라는 이유 명시), #52·#57은 문서 승격+검증기 지식 반영을 닫기 조건으로, 나머지 9건은 각자의 "적용·검증 완료" 근거와 함께 CLOSE 권고로 작성했으며, 모든 닫기 조건은 "코드 이식 레인의 수정 커밋이 main에 머지·push됨을 오케스트레이터/Paul 게이트가 확인"을 공통 전제로 달아 실제 커밋 해시를 추측하지 않았다.

## 생성 파일 목록

- `reports/HDC_ROUNDTRIP_CAMPAIGN.md` (신규)
- `reports/issue_closures/issue_49_closure.md` (신규)
- `reports/issue_closures/issue_50_closure.md` (신규)
- `reports/issue_closures/issue_51_closure.md` (신규)
- `reports/issue_closures/issue_52_closure.md` (신규)
- `reports/issue_closures/issue_53_closure.md` (신규)
- `reports/issue_closures/issue_54_closure.md` (신규)
- `reports/issue_closures/issue_55_closure.md` (신규)
- `reports/issue_closures/issue_56_closure.md` (신규)
- `reports/issue_closures/issue_57_closure.md` (신규)
- `reports/issue_closures/issue_58_closure.md` (신규)
- `reports/issue_closures/issue_59_closure.md` (신규)
- `reports/issue_closures/issue_60_closure.md` (신규)
- `REPORT.md` (신규, 본 문서)

## 검증 (VALIDATION probe)

이슈 번호 49~60 각각이 보고서 본문에 등장하는지 `grep -c "#N\b"`로 카운트했다(전부 1회 이상, `#52`가 13회로 가장 많은 것은 그 자체가 마스터 리포트라 자연스럽다):

```
#49 : 4    #50 : 5    #51 : 3    #52 : 13   #53 : 5   #54 : 3
#55 : 3    #56 : 2    #57 : 3    #58 : 4    #59 : 4   #60 : 6
```

`reports/issue_closures/` 디렉토리에 `issue_49_closure.md`~`issue_60_closure.md` 12개 파일 전부 존재를 `test -f`로 확인했다(전부 OK, MISSING 없음).

## 커밋

- 해시: `5818f41`
- 메시지 1행: `docs: seal HDC 267-drawing round-trip campaign into repo (report + 12 closure drafts)`
- 변경: 13 files changed, 422 insertions(+)

## 건너뛴 것 / 미해결로 남긴 것

- **이슈 #43(OLE 임베드)**: 이번 청산 범위에서 제외(Paul 지시, ADN 답변 대기) — 종결 초안 미작성, 보고서 §5에 한 줄만 남김.
- **#52 표의 70/71건 산술 불일치**: 재조사 없이 미해소로 명기.
- **HDC "텍스트 미세 위치이동 49건"이 #57 오탐과 동일 원인인지**: 이슈 본문 근거 부족으로 UNKNOWN 처리, 추정 서술 금지 원칙에 따라 단정하지 않음.
- **실제 이슈 닫기(코멘트 게시·상태 변경)**: 이 레인의 범위 밖 — 코드 이식 레인 머지 후 오케스트레이터·Paul 게이트를 거쳐야 함. `gh` 명령은 view만 사용했고 comment/close/edit/push는 전혀 실행하지 않았다.
- **코드 파일**: 한 줄도 만지지 않았다(PROTECTED_PATHS 준수, tools/src/tests/prebuilt 접근 없음).

STATUS: PASS | REPORT: D:\runs\wt\autocad-sdk-router__hdc-docs\REPORT.md
