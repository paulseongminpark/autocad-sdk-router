# C70 LEXICON-PROJECT-PROBE 측정 보고서

PREREG SHA-256: `bc5a463340cdbad858bf54104e377cc945894404dc4672e0acddbca9488f7f4d`  
PREREG schema amendment SHA-256: `7e2c0885456cc27790ae200b8f2fe37b3515edd6ac0994b1ad55e45833be9d1e`  
PREREG: `D:\runs\e2_program\cells\c70_pid_lexicon\PREREG_local.json`  
측정 완료 UTC: `2026-07-20T02:47:39.300801Z`  
실행 상태: **MEASUREMENT COMPLETE** (판정/채택은 오케스트레이터 권한)

## 계약과 판정 밴드

계획서 C70 행 원문:

> | C70 LEXICON-PROJECT-PROBE | VIABLE | GATED(F00,F01) | CPU-PAR | 승계 — lexicon freeze·PID 감사·convention-only cheapest probe (정확도 채택 셀 아님) | F00; F01 |

이 행에는 수치 PASS/FAIL, support/kill, 채택 임계값이 없다. 따라서 본 보고서는 측정값과 `RESOLVED`/`UNKNOWN`만 기록하며 정확도 채택, READY, 후속 셀 개방 판정을 만들지 않는다.

## 사전등록과 입력 무결성

- 원 PREREG 140건 입력을 측정 직전에 전건 SHA-256 재검증: **MATCH** (`140`건).
- F01의 known-state 열거형 `MEASURED`를 의미 상태 `RESOLVED`로 읽는 스키마 보정만 별도 봉인했다. lexicon, PID, score, AUC 산식은 바꾸지 않았다.
- staged DXF 사전/사후 SHA-256: `5a6035721630cddc6d753b1b97b898e7a4ce4d5988342ce85e2c465cdb81deff` / `5a6035721630cddc6d753b1b97b898e7a4ce4d5988342ce85e2c465cdb81deff` (**MATCH**).
- 모델/API 호출 0, test 접촉 0, 원본 CAD 쓰기 0, staged DXF 쓰기 0, Git 명령 0, 서브에이전트 0.

## LEX — lexicon freeze

- 상태: **RESOLVED**.
- 분석 정의: 384개; 관측 segment: 420개; frozen eligible token: 6개.
- label-free 규칙: `NFKC(casefold(def_norm))`의 Unicode letter/digit run 중 letters-only, 길이 ≥2, definition frequency ≥5.
- 제외 segment: 414개. 경로·judge/vendor·unit_id·handle·notes·source index는 lexicon 입력이 아니다.
- 대상 정의 coverage: `0.299479166667` = 115 / 384 (`115/384`).
- freeze artifact: `D:\runs\e2_program\cells\c70_pid_lexicon\lexicon_freeze.json`; 전건: `lexicon.csv`, `definition_features.csv`.

Frozen eligible tokens:

- `ba`
- `co`
- `dw`
- `wd`
- `기본형`
- `평면도`

## PID — project-identity 감사

- cross-project PID identifiability: **`UNKNOWN`**.
- 독립 project source: `1`개. authorized cohort에는 staged DXF 1개뿐이며 judge 5개, raw shard 100개, definition은 독립 project로 대치하지 않았다.
- 직접 식별 위험 필드 9개를 probe feature에서 제외; 실제 사용 0개. feature subset 검증: `True` (**RESOLVED**).
- 단일 project이므로 어떤 token이 project identity를 예측하는지 또는 project를 넘어 유지되는지는 측정할 수 없다. 그 항목은 `UNKNOWN`으로 보존한다.
- 전건 근거: `pid_audit.csv`, `pid_source_inventory.csv`.

## CP — convention-only cheapest probe

- 상태: **RESOLVED** (descriptive measurement only).
- eligible definition: 384개; positive/negative/UNKNOWN: 131/253/0.
- token-covered: 115개; coverage `0.299479166667` (`115/384`).
- leave-one-definition-out score unique: 6개; range `0.339425587467`–`0.801169590643`.
- pairwise AUC: `0.568475997948` (`18841/33143`); win/tie/loss=18841/0/14302 of 33143 positive-negative pairs.
- cross-project AUC: **`UNKNOWN`** — 독립 project가 1개뿐이다. C71의 cross-AUC 밴드는 적용하지 않았다.
- 이 값은 정확도 채택, support/kill, 일반화, transfer, silver 독립성 판정이 아니다.
- 전건 근거: `probe_predictions.csv`.

## UNKNOWN 보존

- project-identifying token의 경험적 판별: `UNKNOWN` (독립 project <2).
- cross-project AUC/transfer: `UNKNOWN` (독립 project <2).
- C70 프로그램 판정과 후속 gate 개방: 본 수치 worker 권한 밖이며 SoT 수치 밴드도 없음.

## evidence.xlsx fallback

`load_workspace_dependencies` / `@oai/artifact-tool` 런타임이 이 세션에 노출되지 않아 skill 계약상 다른 XLSX 라이브러리로 대치하지 않았다. 패킷 허용 fallback으로 `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\c70_pid_lexicon\evidence.csv`와 `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\c70_pid_lexicon\EVIDENCE_XLSX_UNAVAILABLE.txt`를 생성했다.

## 재현 명령과 파일 근거

```powershell
python D:\runs\e2_program\cells\c70_pid_lexicon\seal_prereg.py
python D:\runs\e2_program\cells\c70_pid_lexicon\seal_schema_amendment.py
python D:\runs\e2_program\cells\c70_pid_lexicon\measure_c70.py
python D:\runs\e2_program\cells\c70_pid_lexicon\verify_c70.py
```

주요 산출물:

- `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\c70_pid_lexicon\REPORT.md`
- `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\c70_pid_lexicon\evidence.csv`
- `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\c70_pid_lexicon\PREREG.csv`
- `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\c70_pid_lexicon\EVIDENCE_XLSX_UNAVAILABLE.txt`
- `D:\runs\e2_program\cells\c70_pid_lexicon\measurement.json`
- `D:\runs\e2_program\cells\c70_pid_lexicon\input_manifest_verified.csv`
- `D:\runs\e2_program\cells\c70_pid_lexicon\lexicon.csv`
- `D:\runs\e2_program\cells\c70_pid_lexicon\lexicon_freeze.json`
- `D:\runs\e2_program\cells\c70_pid_lexicon\definition_features.csv`
- `D:\runs\e2_program\cells\c70_pid_lexicon\pid_audit.csv`
- `D:\runs\e2_program\cells\c70_pid_lexicon\pid_source_inventory.csv`
- `D:\runs\e2_program\cells\c70_pid_lexicon\probe_predictions.csv`
- `D:\runs\e2_program\cells\c70_pid_lexicon\COMMANDS.md`

CELL_MEASUREMENT_COMPLETE
