# ADN 라이센스 — 우리가 쓸 수 있는 것 (2026-07-24 조사)

> 배경: Autodesk가 ADN(Autodesk Developer Network) 라이센스를 부여함 (Paul 보고, 2026-07-24).
> 이 문서는 ADN이 autocad-sdk-router 스택에 열어주는 능력의 조사 기록이다.
> ⚠️ 정확한 entitlement는 티어별로 다름 — **ADN 포털에서 실제 포함 목록 확인이 선행 작업** (C1).

## 1. 개발용 소프트웨어 라이센스 (거의 전 제품)

ADN 멤버는 개발·지원·시연 목적으로 Autodesk 데스크톱 제품 대부분을 받는다.
- 현재 파이프라인의 AutoCAD/accoreconsole 2027 개발 사용이 라이센스로 정당화됨.
- 팀원 개발 머신 배포 가능.

## 2. 무제한 1:1 API 기술지원 (즉시 활용 가능)

전담 소프트웨어 엔지니어 팀의 무제한 온라인 지원. 현재 앓고 있는 문제를 직접 문의할 수 있다:
- accoreconsole **QUIT 행** — PR #40이 타임아웃 킬로 우회 중인 그 버그 (→ 지원 케이스 C3-1)
- **ErrorStatus=53** — ELLIPSE major_axis 직교성 검증 규칙의 공식 스펙 (#46) (→ 지원 케이스 C3-2)
- ACAD_SORTENTS·헤더 시스템 변수의 공식 API 접근법 (#38, #44)

## 3. RealDWG SDK — 잠재적 게임체인저 (별도 상용 계약)

AutoCAD **없이** 단독 프로세스에서 DWG/DXF를 네이티브로 읽고 쓰는 C++/.NET 라이브러리.
ObjectARX의 부분집합이며, Revit·Inventor가 내부적으로 쓰는 그 엔진 (R14 이후 전 버전 호환).

우리 구조에의 함의:
- "쓰기 1 op = accoreconsole 프로세스 1개" 병목과 그 우회(배치 레인 PR #40)를 **구조적으로 제거** 가능
- ezdxf 우회 경로 특유의 문제(#46 타원 평면성, #41 해치 호 OCS, #38 SORTENTS)가 원본 DB 직접 조작으로 소멸
- Plan C(`write.database.from_ir`, docs/PLAN_BULK_FROM_IR.md)의 이상적 호스트
- **주의**: 라이센스는 ADN에 포함되지 않음. Tech Soft 3D 경유 별도 상용 계약 (평가판 신청 가능).
  ADN은 RealDWG 기술지원 채널만 제공.

## 4. APS Design Automation API (AutoCAD)

클라우드에서 AutoCAD 엔진 실행 — 수천 DWG 배치 처리(스크립트·AutoLISP·커스텀 add-in).
- 대량 regen의 스케일아웃 경로 (배치 레인의 클라우드 버전)
- APS는 토큰 과금 — ADN 멤버십 포함 크레딧 여부는 포털 확인 필요

## 5. 조기 액세스·베타 + 앱스토어

차기 AutoCAD/SDK 베타 접근, Autodesk App Store 배포 자격.

## 이슈 매핑

| 능력 | 관련 이슈/작업 |
|---|---|
| API 지원 | #38 #44 #46, accoreconsole QUIT hang |
| RealDWG | Plan C (#39 후속), #46 #41 #38의 근본 해소, host_required op 축소 |
| Design Automation | 대량 regen 스케일아웃 (PR #40 배치 레인의 후속) |

## 출처 (2026-07-24 조회)

- https://aps.autodesk.com/developer/overview/autodesk-developer-network-membership
- https://app.upskill-dev.autodesk.com/developer-network/membership-options
- https://aps.autodesk.com/developer/overview/realdwg-api
- https://www.techsoft3d.com/oem/realdwg/ (라이센스·평가판)
- https://aps.autodesk.com/developer/overview/objectarx-autocad-sdk
- https://aps.autodesk.com/developer/overview/automation-api
- https://blog.autodesk.io/understanding-objectdbx-and-realdwg/
- https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Joining-Autodesk-Developer-Network-ADN.html
