# APS Design Automation (AutoCAD) 타당성 평가 — v0 (2026-07-24)

> 질문: 대량 DWG regen/추출을 APS(Autodesk Platform Services) Design Automation
> API(클라우드에서 AutoCAD 엔진 실행)로 스케일아웃할 가치가 있는가?

## 무엇을 주는가

- 클라우드 AutoCAD 엔진에 커스텀 add-in/스크립트/AutoLISP을 올려 DWG 배치 처리
  (수천 파일 병렬) — 로컬 accoreconsole 1대 병목 제거.
- Activity(작업 정의) + WorkItem(실행) 모델, 파일은 클라우드 스토리지 경유.

## 우리 스택 적합성 판정 (현재 증거 기준)

| 축 | 판정 | 근거 |
|---|---|---|
| 기술 적합 | **가능** | 우리 .dbx/.crx(ObjectARX)는 DA의 custom AppBundle 모델과 동형. ASCII .scr 방식 그대로 이식 가능성 높음 |
| 필요성 (현재) | **낮음** | PR #40 배치 레인이 1.9M ops를 ~8–10h로 이미 낮춤(추정). 로컬 처리량이 당장의 병목 아님 |
| 보안/데이터 | **주의** | 회사 원본 도면을 클라우드 업로드 — 내부 데이터 반출 정책 검토 선행 필요 (VecFormer SPEC의 "외부 노출 금지" 원칙과 충돌 여지) |
| 비용 | 미정 | 토큰(클라우드 크레딧) 과금. ADN 멤버십 포함 크레딧 여부 = 포털 확인 항목(C1) |

## 결론 (v0)

**지금은 도입 안 함.** 트리거 조건 둘 중 하나가 오면 재평가:
1. 배치 레인으로도 wall-clock이 부족한 규모의 regen 캠페인 (예: 수만 도면 전수 재생성)
2. RealDWG 협상 불발 + 로컬 accoreconsole 병렬 한계 도달

재평가 시 선행 과제: 원본 도면 클라우드 반출 정책 결재(ballot), 크레딧 단가 실측(파일럿 10도면).

## 출처

- https://aps.autodesk.com/developer/overview/automation-api
- https://aps.autodesk.com/en/docs/design-automation/v3/developers_guide/overview
