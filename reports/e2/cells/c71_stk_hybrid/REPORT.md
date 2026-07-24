# C71 STK-HYBRID / CONVENTION-ONLY-H3 측정 보고서

PREREG SHA-256: `25433c6a1d179c38a2356e8423121bee5567a4de2b3a886fab5595de319477c3`  
PREREG: `D:\runs\e2_program\cells\c71_stk_hybrid\PREREG_local.json`  
측정 완료 UTC: `2026-07-20T03:04:45.425585Z`  
실행 상태: **MEASUREMENT COMPLETE — 합법 축 측정, BLOCKED_INPUT 축 보존** (프로그램 채택/후속 gate 개방은 오케스트레이터 권한)

## 계약과 판정 밴드

계획서 C71 행 원문:

> | C71 CONVENTION-ONLY-H3 | VIABLE | GATED(C70) | CPU-PAR | 승계 — 측정기 (기하 의도 배제): cross AUC `≥0.75` 지지 / `≤0.55` kill; E1 corr `≥0.70`이면 silver 독립성 강등 | C70; F00; M30(STK) |

이 보고서는 위 행을 그대로 적용한다. cross-project AUC는 독립 프로젝트 자산이 1개뿐이므로 계산·대치·밴드 적용을 하지 않는다. 단일 프로젝트 안에서 행 문언상 측정 가능한 E1 correlation만 primary 수치로 집행했고, TAU/SHUF는 사전등록된 기술 통계·음성 대조로만 기록했다.

## 사전등록과 입력 무결성

- 원 PREREG 입력 `672`건을 수치 계산 직전에 전건 SHA-256 재검증: **MATCH**.
- staged DXF 사전/사후 SHA-256: `5a6035721630cddc6d753b1b97b898e7a4ce4d5988342ce85e2c465cdb81deff` / `5a6035721630cddc6d753b1b97b898e7a4ce4d5988342ce85e2c465cdb81deff` (**MATCH**).
- C70 frozen lexicon `6`개만 사용; 재유도 0건. C70 score는 leave-one-definition-out 동결값을 그대로 사용했다.
- 모델/API 호출 0, test 접촉 0, 원본 CAD 쓰기 0, staged DXF 쓰기 0, Git 명령 0, 서브에이전트 0.
- feature는 C70 lexicon-derived score 1개뿐이다. geometry intent, handle/path/vendor/judge/source index/notes/unit ID, s1/s4 detector 출력은 feature로 사용하지 않았다.

## XP — cross-project AUC

- 상태: **`BLOCKED_INPUT`**.
- 사유: **`BLOCKED_INPUT: 독립 프로젝트 자산 <2`**.
- 독립 project asset: `1`개. judge, raw shard, definition을 project로 대치하지 않았다.
- cross-project AUC: **`UNKNOWN`**.
- `≥0.75` support / `≤0.55` kill 밴드 적용: **둘 다 False**. 단일-project AUC에 이 밴드를 소급 적용하지 않았다.

## E1C — frozen convention score와 E1 silver 상관

- 상태: **`RESOLVED`**.
- 정의 join: `384/384`; missing from E1 `0`, missing from C70 `0`.
- x: `C70 probe_predictions.score`; y: `real_defs_v3.rows[].silver_mean_wall_likelihood`.
- Pearson r: **`0.253443069177`**.
- 산식 전건: `Σ[(x−x̄)(y−ȳ)] / sqrt(Σ(x−x̄)^2 · Σ(y−ȳ)^2)`.
- x̄ `0.452196266840`; ȳ `0.169825781250`; 교차편차합 `3.587726501580`; 분모 `14.155946395499`.
- 판정: **`DOWNGRADE_TRIGGER_NOT_MET`**. `r < 0.70`이면 강등 trigger 미충족일 뿐 silver 독립성의 증명으로 해석하지 않는다.
- score unique `6`개; frozen token-covered definition `115/384`.
- 전건 근거: `D:\runs\e2_program\cells\c71_stk_hybrid\correlation_rows.csv`.

## TAU — tie-corrected 순위 기술 통계

- Kendall tau-b: **`0.124797191506`** (별도 SoT 밴드 없음; descriptive only).
- concordant / discordant / x-only tie / y-only tie / both tie: `25933` / `18835` / `25396` / `1337` / `2035`.
- 전체 unordered pair: `73536`. 전건은 correlation row에서 결정적으로 재산출 가능하다.

## SHUF — deterministic negative control

- seed `710071`, permutation `10000`회.
- two-sided empirical p: **`0.000199980002`** = `(1 + |r_perm| ≥ |r_obs| 건수 1) / (B+1)`.
- null mean / population SD: `-0.000763135732` / `0.050995594418`.
- null q2.5% / median / q97.5%: `-0.098117118051` / `-0.002063569419` / `0.101426024952`.
- 별도 SoT 밴드가 없으므로 판정에 승격하지 않았다. 원시 `D:\runs\e2_program\cells\c71_stk_hybrid\shuffle_distribution.csv` 전건 공개.

## STK-HYBRID

- 상태: **`BLOCKED_INPUT`**.
- C71 의존열은 `M30(STK)`를 명시하지만 packet-authorized input 목록에는 frozen M30(STK) prediction artifact가 없다.
- stacker 발명, 현 결과를 본 재적합, s1/s4 detector score 대치, geometry-intent 혼입을 모두 하지 않았다. 그러므로 STK hybrid 수치는 **`UNKNOWN`**이다.

## upstream single-project AUC 무결성 재검산

- C70 score 대 O-B target pairwise AUC: `0.568475997948` = `18841/33143`; win/tie/loss `18841/0/14302` of `33143`.
- C70 봉인값과 **MATCH**. 이 값은 single-project descriptive measurement이고 C71 cross-project support/kill 판정이 아니다.

## UNKNOWN 보존과 판정 경계

- cross-project AUC, support/kill, transfer/generalization: `UNKNOWN` / `BLOCKED_INPUT`.
- frozen M30(STK) 없는 hybrid score: `UNKNOWN` / `BLOCKED_INPUT`.
- E1 corr가 0.70 미만인 경우: downgrade trigger 미충족; silver 독립성 PASS로 대치하지 않음.
- 프로그램 채택, C71 전체 PASS/FAIL, 후속 gate 개방: 수치 worker 권한 밖.

## evidence.xlsx fallback

`load_workspace_dependencies` / `@oai/artifact-tool` 런타임이 이 세션에 노출되지 않아 Spreadsheets skill 계약상 다른 XLSX 라이브러리로 대치하지 않았다. 패킷 허용 fallback으로 `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\c71_stk_hybrid\evidence.csv`와 `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\c71_stk_hybrid\EVIDENCE_XLSX_UNAVAILABLE.txt`를 생성했다.

## 재현 명령과 파일 근거

```powershell
python D:\runs\e2_program\cells\c71_stk_hybrid\seal_prereg.py
python D:\runs\e2_program\cells\c71_stk_hybrid\measure_c71.py
python D:\runs\e2_program\cells\c71_stk_hybrid\verify_c71.py
```

주요 산출물:

- `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\c71_stk_hybrid\REPORT.md`
- `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\c71_stk_hybrid\evidence.csv`
- `D:\dev\99_tools\autocad-sdk-router\reports\e2\cells\c71_stk_hybrid\EVIDENCE_XLSX_UNAVAILABLE.txt`
- `D:\runs\e2_program\cells\c71_stk_hybrid\measurement.json`
- `D:\runs\e2_program\cells\c71_stk_hybrid\input_manifest_verified.csv`
- `D:\runs\e2_program\cells\c71_stk_hybrid\correlation_rows.csv`
- `D:\runs\e2_program\cells\c71_stk_hybrid\shuffle_distribution.csv`
- `D:\runs\e2_program\cells\c71_stk_hybrid\COMMANDS.md`

CELL_MEASUREMENT_COMPLETE
