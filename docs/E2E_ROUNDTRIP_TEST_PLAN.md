# E2E_ROUNDTRIP_TEST_PLAN — CADOS 전체-도면 라운드트립 시험 프로그램

## 1. 목적과 한 줄 정의

**E2E 라운드트립 = `dwg_graph_ir.v1`의 복원-충분성(rebuild-sufficiency) 인증 게이트.**

도면을 IR(JSON)로 추출하고, 그 IR만으로 새 도면을 재생성하고, 원본과 재생성본을 비교한다.
비교가 통과하면 그 IR 스키마와 그 IR을 소비하는 patch-op 세트가 "이 도면을 다시 만들기에
충분한 정보를 담고 있다"는 것을 뜻한다. 통과하지 못하면 IR 어딘가에 정보 손실이 있거나
patch-op 변환에 결함이 있다는 뜻이다.

이것은 ALM(Ariadne Learning Method) 1단계 — "라운드트립 검증(roundtrip verification)" —
을 DWG 레인에 그대로 적용한 것이다. 새 방법론이 아니라 기존 ALM 원칙을 이 도메인의 기존
CADOS 하네스 위에 얹은 것이다.

**합격선은 `diff == 0`이 아니라 `유해 패턴(harmful pattern) 수 == 0`이다.** 재생성본이 원본과
byte-identical 하거나 entity-count-identical 할 필요는 없다. 예를 들어 POLYLINE이 LWPOLYLINE으로
재생성되는 것은 kind 드리프트이지만 기하가 보존되면 무해하다. 무해 diff는 기록(record)하고
허용(allow)한다 — 감추지 않는다. 유해 diff(기하 손실, 좌표 오류, 속성 누락 등)만 FAIL 사유가 된다.

## 2. 기존 자산 인벤토리 (새로 짓지 않은 이유)

이 시험 프로그램은 CADOS 하네스에 이미 존재하는 도구를 조합한 것이다. 아래 표의 모든 경로는
`tools/full_roundtrip_capstone.py` 기준 상대경로다.

| 자산 | 역할 |
|---|---|
| `tools/full_roundtrip_capstone.py` | E2E 드라이버. `extract → regen(인증된 kind만) → re-extract → handle-독립 diff` 순으로 실행. CLI: `--dwg --seed --out-dir --kinds --per-kind-limit --census-only --with-records --cross-verify --visual-gate` |
| `tools/ir_to_patch.py` + `tools/patch_ops/*` | IR → `cad_patch.v1` op 변환. modelspace 엔티티가 참조하는 블록 정의는 IR의 `block_definitions`에서 합성한다(#129b). 이 변환이 지원하지 않는 kind는 조용히 건너뛰지 않고 `deferred[]`에 정직하게 보고한다. |
| `tools/cad_diff.py` | `compute_diff(comparison_basis="geometry")`. `(dxf_name, layer, geometry)` 를 tolerance 안에서 join — 핸들에 의존하지 않는다. 재생성본은 원본과 다른 핸들 체계를 갖기 때문에 이 basis가 필요하다(기본값인 `comparison_basis="handle"`은 패치-전후 비교용이지 재생성-비교용이 아니다). |
| `tools/ir_identity.py` | `stable_id`(콘텐츠 해시) + ordinal 기반 lineage. matched/moved/added/removed 를 핸들과 무관하게 계산한다. |
| `tools/mint_blank_seed.py` + `tests/fixtures/blank_seed.dwg` | 재생성 대상이 되는 빈 seed 도면과 그 생성기. |
| `tools/roundtrip_report.py` (신규, 이번 세션) | diff를 패턴 클러스터로 묶고 유해/무해를 판정, PASS/FAIL/VACUOUS를 산출, naive-foil 대조를 병기하는 리포터. |
| `tests/test_roundtrip_fault_injection.py` (신규, 이번 세션) | 검증기 자체를 결함주입으로 검증하는 R0 게이트. |

새 파이프라인을 짓지 않은 이유: 위 6개 기존 자산(추출·변환·diff·identity·seed)이 이미 각자의
책임을 충실히 지고 있고, 서로 handle-독립 join과 IR 스키마로 이미 맞물려 있다. 부족했던 것은
"이 조각들을 라운드트립 관점에서 판정하고 보고하는 층"과 "그 판정기 자체를 믿을 수 있는지
확인하는 층" 뿐이었다 — 그래서 이번 세션에 추가한 것은 `roundtrip_report.py`와
`test_roundtrip_fault_injection.py` 두 개뿐이다.

## 3. ALM 설계노트 → 이 하네스 매핑

| ALM 원리 | 이 하네스에서의 구현 위치 |
|---|---|
| Probe 정찰(타입 인벤토리 · 속성 채움률) | `full_roundtrip_capstone.py`의 census 단계(`census_report`) + `--census-only` 런 |
| 복원은 원본을 안 본다(커닝 금지) | `ir_to_patch.py`는 IR만 소비한다 — 원본 DWG를 다시 열지 않는다 |
| diff를 패턴으로 묶고 유해/무해 판정 | `roundtrip_report.classify_patterns` + `HARMLESS_RULES` |
| tolerance는 타입별로 다르게(좌표/각도/텍스트) | `cad_diff.py`의 `tolerance_profile` (v2-A5) |
| identity 3단 매칭(added/moved/removed) | geometry-basis join(핸들 무관) + `ir_identity.stable_id` lineage |
| 검증기를 먼저 검증한다(합성 시나리오 + 결함주입) | `test_roundtrip_fault_injection.py` (R0) — 4가지 합성 시나리오에 결함을 주입해 리포터가 실제로 FAIL을 내는지 확인 |
| naive-foil 대조 | `roundtrip_report.naive_count_verdict` — 개수만 세는 소박한 비교기를 나란히 돌려 대조 |
| vacuous ≠ PASS (H6) | `kind_buckets`의 VACUOUS 버킷 — 인증된 kind라도 이 도면에서 실제로 시험되지 않았으면 PASS로 세지 않는다 |
| 규칙은 코드가 아니라 데이터다(profile 분리) | `harmless_rules` JSON 오버라이드 — 유해/무해 판정 규칙을 코드 재배포 없이 갱신 가능 |
| 발견 도면 ≠ 검증 도면 | R4 코퍼스 스윕(166 DWG) — 첫 실험 대상 하나로 튜닝한 규칙을 다른 모집단에서 재확인 |

## 4. 첫 실험 대상: `D:\dev\.build\1.dwg`

census 실측일: 2026-07-08.

- 원본 sha256 = `14eb65eb292d8a07f38ab5662dcafe9761c6185bc5ff0c8a9a008be15b598961` (2,368,524 bytes)
  — **READ-ONLY**. 모든 작업은 스테이징 사본에서만 수행한다.
- modelspace 엔티티 375개:

  | dxf_name | count | 비고 |
  |---|---|---|
  | TEXT | 117 | |
  | DIMENSION | 113 | `AcDbRotatedDimension` |
  | LWPOLYLINE | 73 | |
  | INSERT | 50 | |
  | LINE | 21 | |
  | CIRCLE | 1 | |

  전 종류가 `CERTIFIED_KINDS` 안에 있다. DIMENSION이 포함되어 있어, 이 도면이 라이브
  dimension 재생성을 검증하는 첫 사례가 된다.

- 블록 정의 140개, def 엔티티 합계 20,851개:

  | dxf_name | count |
  |---|---|
  | LINE | 11,482 |
  | SPLINE | 3,973 |
  | ARC | 2,198 |
  | LWPOLYLINE | 1,447 |
  | (nested) INSERT / block_reference | 944 |
  | HATCH | 265 |
  | ELLIPSE | 201 |
  | TEXT | 154 |
  | CIRCLE | 143 |
  | 3DFACE | 34 |
  | WIPEOUT | 7 |
  | POINT | 2 |
  | POLYLINE | 1 |

- INSERT 50개의 블록 폐쇄(closure):

  | 블록 그룹 | INSERT 수 | def 규모 |
  |---|---|---|
  | C | 18 | 각 1~2 엔티티 |
  | LV | 14 | 각 1~2 엔티티 |
  | SC | 12 | 각 1~2 엔티티 |
  | LV2 | 4 | 각 1~2 엔티티 |
  | X-FORM_청주 | 1 | 3개 def, 232 엔티티 |
  | X-평면도(기본형) | 1 | 128개 def, 20,567 엔티티 — **도면 전체가 사실상 이 한 블록** |

- DIMENSION 113개는 각자 익명 `*D` 블록을 참조하는데, 이 익명 블록은 `block_definitions`에
  존재하지 않는다. 즉 dimension create-op가 자체적으로 치수 기하를 생성해야 한다 — 이번 런의
  실측 대상 중 하나다.
- 레이어 분포(상위): `DIM` 110 · `4L` 63 · `AA-AXIS-DIM7` 53 · `LEVEL` 46 · `A-DOOR-IDEN` 36,
  그 외 한국어 레이어명(예: `설비OPEN`) 포함.
- **cp949 함정**: 이 도면은 한국어 레이어명을 포함하므로 모든 read는 `encoding='utf-8-sig'`로
  고정한다. mojibake로 보이는 표시는 데이터 손상이 아니라 인코딩 문제일 수 있다 — 코드포인트로
  판정한다(FM6).

## 5. 비용 모델과 스코프 사다리

실측: 2026-07-06 `native_sample` capstone 런에서 op 14개에 181초 소요 — **per-op ≈ 12.9초**
(op 하나당 accoreconsole 프로세스 1회 기동이 지배 비용).

이 비용 모델 위에서 스코프를 단계적으로 넓힌다. 각 단계는 이전 단계가 통과해야 다음으로 간다.

| 단계 | 범위 | 예상 소요 | 목적 |
|---|---|---|---|
| R0 | 결함주입 셀프테스트 (CAD 실행 없음) | < 5초 | 검증기 자체가 결함을 실제로 잡아내는지 확인 |
| R1a | 스모크: 5종(line, circle, text, dimension, lwpolyline), `--per-kind-limit 2` | 수 분 | 각 kind별 최소 표본으로 배선 확인 |
| R1b | R1a + INSERT 포함 + def-entity 예산(거대 블록은 정직 유예) | R1a보다 큼 | 블록 폐쇄 경로 확인, 단 20,567-엔티티 블록은 계산에서 뺀다 |
| R2 | 본실행: modelspace 375개 전량 + 소형 블록 def 전량 ≈ 620 ops | ≈ 2.2시간 | 이 도면에 대한 완전한 1차 판정 |
| R4 (후속) | 166-DWG 코퍼스 스윕 | R2의 배수 | 발견 도면 ≠ 검증 도면 원칙 — 규칙을 다른 모집단에서 재확인 |

`X-평면도(기본형)` 블록의 def 엔티티 20,567개는 per-op 비용 그대로 곱하면 ≈ 74시간이 든다.
**이번 런에서는 이 블록을 정직하게 유예(deferred)한다** — 스킵 사실을 리포트 천장(ceiling)에
명시하고, PASS 판정에 포함시키지 않는다. 후속 과제는 patch 배칭(하나의 native 잡에 다수 op를
묶어 프로세스 기동 비용을 상각)이다.

## 6. 판정 의미론

| 상태 | 조건 |
|---|---|
| PASS | `attempted > 0` 이고 `diff0 == attempted` (시도한 것 전부가 유해 diff 0) |
| FAIL | 유해 패턴이 하나 이상 존재 |
| VACUOUS | 인증된 kind이지만 이 도면에서는 실제로 시험되지 않음 — PASS로 세지 않는다(H6) |

**유해 vs 무해**: 무해 후보의 예 — POLYLINE → LWPOLYLINE kind 드리프트. 2026-07-06 런 실측에서
`POLYLINE removed 2` + `LWPOLYLINE added 2`가 함께 나타났고, 기하는 보존되었다. 이런 패턴은
사람이 비준(ratify)하기 전까지 "candidate harmless"로만 표시하고, 비준 후에 `harmless_rules`에
데이터로 편입한다. 임의로 유해 목록에서 빼지 않는다.

**naive-foil 대조**: 개수 보존만 확인하는 소박한(naive) 비교기를 스마트 비교기와 나란히 돌린다.
naive가 PASS를 내는데 스마트 비교기가 FAIL을 내는 경우(foil PASS & smart FAIL)가 나와야, 스마트
비교기가 실제로 무언가를 검출하고 있다는 게이트-생존 증명이 된다. 둘 다 항상 같은 판정만
낸다면 스마트 비교기가 나이브 비교기보다 나은 게 없다는 뜻이다.

**모든 수치 주장에는 그 수치를 낳은 run 디렉토리 경로를 병기한다** (FM9 — 출처 없는 수치 금지).
이 문서의 수치도 예외가 아니다: 섹션 4·5의 수치는 census 실측(2026-07-08)과 2026-07-06
`native_sample` capstone 런에서 나온 것이며, 재확인이 필요하면 해당 run 산출물을 다시 연다.

## 7. 실행 방법

```powershell
# R0 — 결함주입 셀프테스트 (CAD 없이, 수 초)
python -m pytest tests/test_roundtrip_fault_injection.py -v

# census-only — 도면을 열지 않고(추출만) 타입 인벤토리 확인
python tools/full_roundtrip_capstone.py `
  --dwg "D:\dev\.build\1.dwg" `
  --out-dir "runs\1dwg_census_<stamp>" `
  --census-only

# R1a 스모크 — 5종, kind당 2개
python tools/full_roundtrip_capstone.py `
  --dwg "D:\dev\.build\1.dwg" `
  --seed "tests\fixtures\blank_seed.dwg" `
  --out-dir "runs\1dwg_r1a_<stamp>" `
  --kinds line,circle,text,dimension,lwpolyline `
  --per-kind-limit 2 `
  --with-records `
  --cross-verify

# R2 본실행 — modelspace 전량 + 소형 블록 def
python tools/full_roundtrip_capstone.py `
  --dwg "D:\dev\.build\1.dwg" `
  --seed "tests\fixtures\blank_seed.dwg" `
  --out-dir "runs\1dwg_r2_<stamp>" `
  --with-records `
  --cross-verify `
  --visual-gate

# 위 런 산출물을 패턴 리포트로 정리
python tools/roundtrip_report.py `
  --run-dir "runs\1dwg_r2_<stamp>" `
  --harmless-rules "config\roundtrip_harmless_rules.json"
```

각 명령의 플래그는 섹션 2의 CLI 인벤토리에서 조합한 것이다. `<stamp>`는 실행 시각 기반
디렉토리명(run마다 고유)이며, 실제 run 디렉토리 경로는 실행 로그에서 확인한다.

## 8. 안전 불변식

- 원본 CAD 파일은 항상 READ-ONLY. 모든 작업은 스테이징 사본에서 수행한다.
- `write_original`류 동작 금지 — 원본을 절대 SAVE하지 않는다.
- 실행 전후 원본 sha256을 검증해 원본이 손대지 않았음을 확인한다.
- No-fake-PASS: deferred(유예)와 vacuous(무시험)는 PASS와 분리해서 보고한다. 스킵한 것을
  PASS에 슬쩍 포함시키지 않는다.
- 증거 없는 완료 선언 금지 — PASS/FAIL 주장에는 항상 그 근거가 된 run 디렉토리와 리포트
  경로를 병기한다.
