# E2E 라운드트립 R0/R1 중간 리포트

- **일자**: 2026-07-08
- **대상 도면**: `D:\dev\.build\1.dwg`
  - size: 2,368,524 bytes
  - sha256: `14eb65eb292d8a07f38ab5662dcafe9761c6185bc5ff0c8a9a008be15b598961`
  - 원본 상태: READ-ONLY — 전 런(R0/R1a/R1b) 전후 byte 불변 확인됨
- **프로그램 문서**: `docs/E2E_ROUNDTRIP_TEST_PLAN.md`
- **커밋**: `3bf9894`

---

## 1. 센서스 (Stage 0)

modelspace 총 375 엔티티, 전량 CERTIFIED_KINDS 내:

| kind | count | 비고 |
|---|---|---|
| TEXT | 117 | |
| DIMENSION | 113 | AcDbRotatedDimension |
| LWPOLYLINE | 73 | |
| INSERT | 50 | |
| LINE | 21 | |
| CIRCLE | 1 | |
| **합계** | **375** | |

블록 정의 140개, def 엔티티 합계 20,851개. INSERT 폐쇄(block name × 참조 count(참조당 엔티티)):

| block | refs | entities/ref | 폐쇄 규모 |
|---|---|---|---|
| C | 18 | 2 | 36 |
| LV | 14 | 1 | 14 |
| SC | 12 | 2 | 24 |
| LV2 | 4 | 2 | 8 |
| X-FORM_쳍주 | 1 | 232 | 232 |
| X-평면도(기본형) | 1 | 20,567 (128 defs) | 20,567 |

DIMENSION 113개는 익명 `*D` 블록을 참조하나 해당 정의가 `block_definitions`에 부재 → `create_dimension`이 자체 생성해야 하는 구조이며, 이는 R1에서 실증됨(§3).

---

## 2. R0 — 검증기 자기검증 (CAD 엔진 없음)

`tests/test_roundtrip_fault_injection.py` — 8 tests **PASS**:

| 케이스 | 기대 | 결과 |
|---|---|---|
| 동일 IR(핸들 전이) | 전량 diff0 | PASS |
| 이동 주입 | 검출 | PASS |
| 삭제 주입 | 검출 | PASS |
| 추가 주입 | 검출 | PASS |
| 레이어 변경 주입 | 검출 | PASS |
| 텍스트 변경 주입 | 검출 | PASS |
| 1e-9 미세 오차 | tolerance 내 통과 | PASS |
| naive foil(개수만 비교) | 이동/레이어/텍스트 변경에 맹목 PASS, smart 게이트는 검출 | PASS |

핵심 결론: 개수만 보는 naive foil은 이동·레이어·텍스트 변경 주입에도 PASS해버려 눈이 멀어 있음을 확인 — smart 게이트(핸들 매칭 + 필드 diff)만이 이를 검출. **"실패할 수 없는 게이트는 게이트가 아니다"**를 R0에서 실측으로 입증.

---

## 3. R1a — 5종 스모크

- **런 디렉토리**: `runs/e2e_1dwg_R1a_20260708`
- **kinds**: line, circle, text, dimension, lwpolyline (per-kind-limit 2)
- **ops**: 9
- **소요**: 129.4s (14.4 s/op)

| kind | ops | verdict |
|---|---|---|
| LINE | 2 | diff0 |
| LWPOLYLINE | 2 | diff0 |
| TEXT | 2 | diff0 |
| DIMENSION | 2 | diff0 |
| CIRCLE | 1 | diff0 |
| **합계** | **9** | **9/9 diff0** |

- 첫 라이브 DIMENSION 재생성 성공 (익명 `*D` 블록을 `create_dimension`이 자체 생성 — §1에서 예견된 구조가 실제로 동작 확인됨).
- visual gate: **PASS** (ssim 1.0)
- cross-verify: **mismatch** — LibreDWG는 `DIMENSION_LINEAR`를 정직하게 보고(unmapped에 기록)하지만, 우리 쪽 `LIBREDWG_KIND_MAP`에 dimension 계열 라벨이 통째로 누락되어 있던 매핑 갭 발견.
  - **수리**: `tools/cross_verify.py`에 dimension 7종 추가 (커밋 `3bf9894`).

---

## 4. R1b — INSERT + 예산 유예

- **런 디렉토리**: `runs/e2e_1dwg_R1b2_20260708`
- **설정**: per-kind-limit 3, `--max-def-entities-per-block 100`
- **ops**: 17 (엔티티 13 + `create_block` 'C' ×1 + `append` ×2 + `create_blockref` ×1)

### 4.1 예산 드랍 (`summary.def_entity_budget`)

| block | def 엔티티 수 | 사유 |
|---|---|---|
| X-평면도(기본형) | 4,723 (direct) | > 100 한도 → 드랍 |
| X-FORM_쳍주 | 196 | > 100 한도 → 드랍 |

목록과 사유는 `summary.def_entity_budget`에 명시적으로 기록됨.

### 4.2 verdict

| kind | 결과 |
|---|---|
| CIRCLE | 1/1 diff0 |
| DIMENSION | 3/3 diff0 |
| LINE | 3/3 diff0 |
| LWPOLYLINE | 3/3 diff0 |
| TEXT | 3/3 diff0 |
| INSERT | att 3 / diff0 1 (블록 'C' 포함 완벽 재현) / removed 2 |

INSERT의 removed 2건은 예산 드랍된 대형 블록(X-평면도(기본형), X-FORM_쳍주) 참조 — `deferred.json`에 `'no block_definitions entry'` 사유로 정직하게 유예 기록됨.

### 4.3 cross-verify

이번엔 **ok** — dimension 3=3, deltas `[]`, unmapped `[]` (§3에서의 수리가 라이브로 검증됨).

### 4.4 visual gate — "정직한 blocked"

유예된 거대 INSERT 2개가 pre 렌더에만 존재:

| 항목 | pre | post |
|---|---|---|
| deleted entities | 2 (유예분) | — |
| viewbox | [-261784, -116140, 322973 × 159432] | [42717, 20189, 12591 × 17222] |

예산 유예의 시각적 대가가 viewbox 불일치·deleted:2로 그대로 기록됨 — 감춰지지 않고 정직하게 blocked 처리. 개선 패킷(union-viewbox + 사유 명시)은 별도 진행 중.

---

## 5. 판정 · 다음

- **판정**: 파이프라인 전 구간(census → 검증기 자기검증 → 5종 스모크 → INSERT/예산 유예) 라이브 검증 완료.
- **다음**: R2 본실행 — 전량 modelspace + budget 300 + records, 약 630 ops 예상 → `roundtrip_report`로 유해/무해 최종 판정.
- **잔여 정직 천장**: 거대 블록(X-평면도(기본형) 등)은 per-op 비용(~13 s/op 기준) 상 현재 유예 처리 — 해소는 패치 배칭 설계 브리프에서 별도 진행.

---

*모든 수치는 각 절에 명시된 산출 run 디렉토리(`runs/e2e_1dwg_R1a_20260708`, `runs/e2e_1dwg_R1b2_20260708`) 및 `tests/test_roundtrip_fault_injection.py` 실행 결과에서 인용됨.*
