# RealDWG 평가판 신청 초안 (Tech Soft 3D)

> 신청 창구: https://www.techsoft3d.com/products/realdwg/ ("Start an evaluation")
> 신청자: Paul (Sunapse) — ADN 멤버 자격 병기. 작성 2026-07-24.

## 신청 폼 초안 (영문)

- **Company**: Sunapse Inc. (Seoul, South Korea)
- **ADN status**: Autodesk Developer Network member (2026)
- **Product**: RealDWG SDK — evaluation license
- **Use case** (제출용):
  > We build an internal CAD data pipeline that extracts a faithful JSON
  > intermediate representation (IR) from production DWG drawings
  > (300k+ entities per drawing) and regenerates DWG output from that IR.
  > Today we host all DWG database access inside AutoCAD Core Console via
  > ObjectARX (one process per write operation; a batched lane was added
  > recently). We want to evaluate RealDWG to host the same AcDb-level
  > read/write code in a standalone service process — removing the
  > AutoCAD-host requirement for headless extraction/regeneration and
  > enabling a single-pass bulk `write.database.from_ir` lane.
- **Environment**: C++ (ObjectARX 2027-compatible codebase), Windows 11, .NET interop not required initially
- **Distribution**: internal tooling only (no redistribution) — 라이센스 협상 시 핵심 포인트

## 평가 스파이크 계획 (라이센스 수령 후)

1. `AriadneNativeJob.cpp`의 추출 경로(AcDbDatabase 순회)를 RealDWG 호스트로 컴파일 — API 표면 차이 목록화 (AcDb 계열은 대부분 동일, AcEd*/AcAp* 의존이 이식 장벽)
2. 안양 종합운동장 도면(300,429 엔티티 IR 기준) 추출 왕복 — accoreconsole 결과와 IR diff=0 검증
3. 처리율 실측: per-op accoreconsole vs RealDWG in-process (배치 레인 #40의 ~8-10h 추정 대비)
4. `write.database.from_ir`(Plan C, docs/PLAN_BULK_FROM_IR.md) 드래프트를 RealDWG 위에서 구현 타당성 판정

## 판단 기준 (GO/NO-GO)

- GO: AcDb 이식 장벽이 국소적(AcEd 의존 제거 가능) + 왕복 IR 무손실 + 라이센스 비용이 내부용 협상 가능 범위
- NO-GO 시 대안: 배치 레인(#40) + Design Automation API 클라우드 스케일아웃 유지
