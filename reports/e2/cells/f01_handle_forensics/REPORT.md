# F01 E1-HANDLE-FORENSICS 측정 보고서

PREREG SHA-256: `9ae565948e03787216f8744d7d5ba3e938a1c7302c0cadcf0bb73440724e02b2`  
PREREG: `D:\runs\e2_program\cells\f01_handle_forensics\PREREG_local.json`  
측정 완료 UTC: `2026-07-20T02:25:14.819167Z`  
실행 상태: **MEASUREMENT COMPLETE** (판정/채택은 오케스트레이터 권한)

## 계약과 판정 밴드

계획서 F01 행 원문:

> | F01 E1-HANDLE-FORENSICS | TOP | GATED(F00) | CPU-PAR | 승계 — O-A/O-B/r_pair/unit factor 결정 lattice, CPU `<1h` | F00 |

이 행은 수치 PASS/FAIL 임계값을 두지 않는다. 따라서 아래에는 측정값과 `RESOLVED`/`UNKNOWN`만 기록하며 프로그램 채택 판정을 만들지 않는다. O-A/O-B의 별도 대수 정의서는 authorized input에 없었으므로, 결과를 보기 전에 PREREG에 봉인한 operational definition을 적용했다.

## 입력·금지사항 준수

- PREREG 입력 110건의 SHA-256을 측정 직전에 전건 재검증: **MATCH**.
- staged DXF 사전/사후 SHA-256: `5a6035721630cddc6d753b1b97b898e7a4ce4d5988342ce85e2c465cdb81deff` / `5a6035721630cddc6d753b1b97b898e7a4ce4d5988342ce85e2c465cdb81deff` (**MATCH**).
- 모델/API 호출 0, test 접촉 0, 원본 CAD 쓰기 0, staged DXF 쓰기 0, Git 쓰기 0.
- raw panel 판정의 handle cap 상태: `{"fable5_high": "NOT_CENSORED", "grok45_xhigh": "MIXED", "opus48_max": "NOT_CENSORED", "ornith_v0": "CAP_CENSORED", "sol56_xhigh": "MIXED", "sonnet5_xhigh": "NOT_CENSORED"}`. 이 검열 상태는 보존했으며 누락 handle을 보충하지 않았다.

## C0 — 선정 계보 재현

- `a_original`, `b_absdiff`, `c_wrankdiff`, `d_bootstrap` top-20 순서 재현: **MATCH** (4개 selector 모두 exact order=True).
- `a_original` 원시 panel 매핑 완결: `True`.
- `a_original` definition graph root-reachable: 19/20.
- graph 전체: root 3개, block 410개, INSERT edge 825개, root-reachable block 293개.
- 전건 근거: `selector_reproduction.csv`, `selection_lineage.csv`, `definition_graph.json`, `definition_graph_edges.csv`.

## C1 — O-A (annotation-side)

- raw panel judge: 5개; raw record: 1920건; 정의: 384개.
- O-A known/positive/negative/UNKNOWN: 384/20/364/0.
- panel handle union: 502개; staged DXF에 실재: 502개; C3 직선 primitive 적격: 454개.
- 정의/주석 전건 근거: `annotations_all.csv`, `oa_per_def.csv`, `oa_handle_citations.csv`.

## C2 — O-B (staged-DXF geometric pair)

봉인 조건: 동일 정의 내부, 직선 LINE 또는 2-vertex straight LWPOLYLINE, 각도차 ≤1°, 수직거리 50–500, 짧은 선 대비 종방향 겹침 ≥0.50, 길이비 ≥0.50.

- O-B measured/positive/negative/UNKNOWN 정의: 384/131/253/0.
- 적격 직선 primitive 12176개; 평가 unordered pair 2912289건; 양성 pair 12173건; 참여 handle 6359개.
- 전건 양성 pair와 정의별 탈락 단계 계수: `geometric_pairs.csv`, `ob_per_def.csv`.

## C3 — r_pair

- handle 수준: `0.748898678414` = 340 / 454.
- 정의 수준 analogue: `0.837209302326` = 72 / 86.
- 분모 0 대치는 하지 않았고, 본 실행에서는 `RESOLVED`.

## C4 — unit factor

- `unit_factor`: **`1`** (RESOLVED).
- anchor match 113건 중 frozen 후보 지지 70건; 우승 지지 70건, share `1`.
- 물리 단위 이름: **`UNKNOWN`**.

| 후보 factor | 지지 건수 | 후보지지 내 share |
|---:|---:|---:|
| 1 | 70 | 1 |
| 10 | 0 | 0 |
| 25.4 | 0 | 0 |
| 304.8 | 0 | 0 |
| 1000 | 0 | 0 |

전건 근거: `unit_anchors.csv`, `unit_candidate_summary.csv`.

## C5 — token association

- 공통 측정 정의: 384개; O-B 미매칭 제외: 0개.
- 2×2 (numeric token yes/pair yes, yes/no, no/yes, no/no): `{"token_no_pair_no": 176, "token_no_pair_yes": 95, "token_yes_pair_no": 77, "token_yes_pair_yes": 36}`.
- P(pair | numeric token): `0.318584070796`.
- P(pair | no numeric token): `0.350553505535`.
- risk ratio: `0.908802980904`; odds ratio: `0.866165413534` (0-cell이면 `UNKNOWN`, continuity correction 금지).

| 이름 token | support | P(O-A+|token) | P(O-B+|token) |
|---|---:|---:|---:|
| `x` | 118 | 0.169491525424 | 0.694915254237 |
| `0` | 116 | 0.163793103448 | 0.689655172414 |
| `기본형` | 115 | 0.173913043478 | 0.704347826087 |
| `평면도` | 115 | 0.173913043478 | 0.704347826087 |
| `a` | 30 | 0 | 0.633333333333 |

전건 근거: `token_contingency.csv`, `token_association.csv`.

## C6 — n_h_ornith

- `n_h_ornith`: **`2045`** (CONSISTENT).
- 교차검증: n_cited=2045, n_cited_distinct=2045, n_nonexistent=0.
- 개별 handle 재구성은 `UNKNOWN`; panel handle로 대치하지 않았다.

## UNKNOWN·제약 보존

- 물리 단위 이름: `UNKNOWN` — 1:1 표시비는 측정되지만 authorized input은 mm/m 등 단위명을 직접 증명하지 않는다.
- ornith_v0 개별 handle 목록 재구성: `UNKNOWN` — authorized raw 디렉터리에 ornith_v0 원시 주석이 없다. `n_h_ornith`만 handle_audit의 봉인된 행에서 교차검증했다.
- 독립 `evidence.xlsx`: 생성 불가 — Spreadsheets skill이 요구하는 `load_workspace_dependencies`/`@oai/artifact-tool` 런타임이 이 세션에 노출되지 않았다. 패킷 허용 fallback으로 `evidence.csv` + 상세 CSV 묶음을 생성했다.

## 재현 명령과 파일 근거

```powershell
python D:\runs\e2_program\cells\f01_handle_forensics\seal_prereg.py
python D:\runs\e2_program\cells\f01_handle_forensics\measure_f01.py
python D:\runs\e2_program\cells\f01_handle_forensics\verify_f01.py
```

산출물:

- `D:\runs\e2_program\cells\f01_handle_forensics\PREREG_local.json`
- `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\f01_handle_forensics\evidence.csv`
- `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\f01_handle_forensics\PREREG.csv`
- `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\f01_handle_forensics\EVIDENCE_XLSX_UNAVAILABLE.txt`
- `D:\runs\e2_program\cells\f01_handle_forensics\measurement.json`
- `D:\runs\e2_program\cells\f01_handle_forensics\input_manifest_verified.csv`
- `D:\runs\e2_program\cells\f01_handle_forensics\selector_reproduction.csv`
- `D:\runs\e2_program\cells\f01_handle_forensics\selection_lineage.csv`
- `D:\runs\e2_program\cells\f01_handle_forensics\annotations_all.csv`
- `D:\runs\e2_program\cells\f01_handle_forensics\oa_per_def.csv`
- `D:\runs\e2_program\cells\f01_handle_forensics\oa_handle_citations.csv`
- `D:\runs\e2_program\cells\f01_handle_forensics\ob_per_def.csv`
- `D:\runs\e2_program\cells\f01_handle_forensics\geometric_pairs.csv`
- `D:\runs\e2_program\cells\f01_handle_forensics\unit_anchors.csv`
- `D:\runs\e2_program\cells\f01_handle_forensics\unit_candidate_summary.csv`
- `D:\runs\e2_program\cells\f01_handle_forensics\token_contingency.csv`
- `D:\runs\e2_program\cells\f01_handle_forensics\token_association.csv`
- `D:\runs\e2_program\cells\f01_handle_forensics\definition_graph.json`
- `D:\runs\e2_program\cells\f01_handle_forensics\definition_graph_edges.csv`
- `D:\runs\e2_program\cells\f01_handle_forensics\COMMANDS.md`

`CELL_MEASUREMENT_COMPLETE`
