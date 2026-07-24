# seat4 전면 감사 — L1c 루프 종결 주장

## 결론

**REFUTE.** 기록된 400장면 replay, `26→0`, L1b 정상 수치 불변, 소스 manifest, 고정 seed 300건은 독립 재현됐다. 그러나 결합 주장 전체는 성립하지 않는다.

1. 이중 봉인의 **내용**은 일치하지만, 전달된 `evidence.xlsx`가 수리 코드보다 먼저 봉인됐다는 절차 증거는 성립하지 않는다. prerepair workbook SHA는 실물이 없는 상수이고, 전달 workbook의 mtime·OOXML `modified`는 수리 코드보다 늦다. 더구나 검사 코드가 현재 workbook SHA가 prerepair SHA와 다르면 시간 검사를 건너뛰고 `created_before_estimator=True`를 반환한다.
2. C1v4 가드는 허용 가능한 `stale_override` 입력에서 새 `LOW→HIGH` 전이를 만든다. ratio outlier를 reference 모집단의 분모에서도 제거하여 reference confidence를 `0.64→0.80`으로 올리는 역전이다. 54개 계통 변형 중 15개에서 재현됐다.
3. 서로 물리적으로 같은 `1000 MM`과 `1 M` anchor를 v2가 ratio outlier로 오분류해 정당한 reference support를 제거하는 coverage 퇴행도 재현됐다.

계약의 “불확실하면 REFUTE”를 적용할 필요도 없이, 2번은 봉인된 `status` 상승 0 조건에 대한 직접 반례다.

## 감사 범위와 고정점

- 원본 추정기: `D:\dev\99_tools\autocad-sdk-router\tools\e2\cells\feyerabend_c1.py`, SHA-256 `633c5ee154eb3b869dba8361de2cbee9808627e0f192f8c2d29a4b05df2c4d51`.
- 실행 산출 원본 사본: `D:\runs\e2_program\cells\feyerabend_c1\feyerabend_c1.py`, 같은 SHA-256이며 byte-equal.
- 수리 추정기: `D:\runs\e2_program\cells\loop_l1c\feyerabend_c1_v2.py`, SHA-256 `5f6f2eee4810ad59863ce1c3e6b206d0a9d1818c0c0a32684194820b1aa73a0f` (`REPORT.md:126`).
- 독립 감사 harness: `seat4_work\seat4_audit.py`, SHA-256 `0ebc59dd049cc3e1da3c7f3e1caaccb87f5008ab126ddf1afd66eaf11f4b5005`.
- 독립 결과: `seat4_work\audit_results.json`, SHA-256 `586a2d04fb8dab141fb8208e778a1638c97f4fc9673c7a04f27dd0f3e83b6c87`.
- repo의 관련 세 파일은 `git status --short`와 `git diff --numstat`에 출력이 없었다. 감사 중 commit은 만들지 않았다.

## 1. 이중 사전봉인

### 1.1 내용과 밴드 — 통과

`prereg.json` 원문 SHA-256은 `30f6d0f7db9c5a9531183ec317936d4c5d3dda98139299d8ff43aeee68183fa8`, canonical SHA-256은 `a6c4a6d7a86b59b054df939c44e1744d958772381bc73d852f90c297d7a1989d`로 REPORT와 일치한다 (`REPORT.md:3-4`).

OOXML을 직접 해석한 결과:

- sheet는 visible `PREREG` 하나, dimension은 `A1:F47`, formula·external link·macro part는 0이다.
- `PREREG!B5`는 `prereg.json`의 UTF-8 sorted compact canonical JSON과 byte-for-byte 같다.
- rows 8–47의 JSON pointer 40개를 원 JSON leaf와 type-aware 대조했으며 mismatch 0, `Immutable != TRUE` 0이다 (`seat4_work\audit_results.json:1216-1679`).
- 최종 workbook SHA-256 `70f3001fc4a23948fd83aaa52809df04c468ea41d5c635ea0beaa0a50705fbfe`도 REPORT와 일치한다 (`REPORT.md:6`).

봉인 수치도 도시의 C1 제안 합격선과 맞는다.

- scale별 HIGH coverage minimum `0.60`: `prereg.json:15`; 도시 `feyerabend_P2.md:785-790`의 `0.60`.
- HIGH subset accuracy minimum `0.95`, relative error maximum `0.05`: `prereg.json:25-26`; 도시 `feyerabend_P2.md:785-790`의 95%/5%.
- scale `{0.001, 0.01, 1, 1000}` 및 seed `20260719`, 300 perturbations: `prereg.json:16-21,46-47`.
- `confidence_score/status/unit_status` upward 허용 수 `0`: `prereg.json:30-35`. 이는 packet의 “어떤 교란도 … 올릴 수 없음”을 그대로 더 엄격하게 봉인한 값이다 (`PACKET_loop_L1c_estimator_repair.md`, 수리 계약 1·5).
- 이중 봉인 자체의 선행 의무는 도시 `feyerabend_P2.md:738-740`에 명시돼 있다.

### 1.2 선행 시점 — 실패/입증 불가

시간축은 다음과 같다(UTC).

| 증거 | 시각 | 수리 코드보다 선행? |
|---|---:|---:|
| `prereg.json` filesystem mtime | 2026-07-18 17:49:11.162321Z | 예 |
| `evidence.xlsx` filesystem creation | 2026-07-18 17:49:48.241510Z | 예, 단 overwrite에도 보존되는 값 |
| `feyerabend_c1_v2.py` filesystem mtime | 2026-07-18 17:55:38.700987Z | 기준 |
| 전달 `evidence.xlsx` filesystem mtime | 2026-07-18 18:05:27.309449Z | **아니오** |
| 전달 workbook OOXML `modified` | 2026-07-18 18:05:27Z | **아니오** |
| 전달 workbook OOXML `created` | 2026-07-19 00:00:00Z | **아니오** |

추가로 OOXML `created`가 `modified`보다 뒤여서 내부 메타데이터 자체가 시간 순서 증거로 일관되지 않는다. ZIP 9개 entry의 timestamp도 모두 `2026-07-19T03:05:26`(timezone 없는 ZIP local time)로 최종 rewrite 시점에 맞춰져 있다. 원자료는 `seat4_work\audit_results.json:1216-1691`에 있다.

REPORT가 prerepair SHA로 적은 값은 `3013a276aa1c1dd0a4f8869cb4a83eff8ce31e980f49a7a7690cdda2b2f87041` (`REPORT.md:5`)이지만:

- 전달 `evidence.xlsx`의 SHA는 `70f300…`이라 prerepair 파일이 아니다.
- `loop_l1c` 산출 7개 파일 어디에도 `3013a…` SHA의 실물이 없다.
- `D:\runs\e2_program`의 텍스트 검색에서 `3013a…`는 REPORT, 결과 JSON, checker 상수에만 존재하고 prerepair workbook 사본/sidecar는 없다.

검사기 자체도 이 결함을 검출하지 못한다. `loop_l1c.py:115-148`에서:

```python
if (
    evidence_sha == EXPECTED_EVIDENCE_PREREPAIR_SHA256
    and EVIDENCE_PATH.stat().st_mtime_ns >= ESTIMATOR_PATH.stat().st_mtime_ns
):
    raise RuntimeError(...)
...
"created_before_estimator": True,
```

전달 workbook은 `evidence_sha != EXPECTED_EVIDENCE_PREREPAIR_SHA256`이므로 line 133의 첫 조건이 거짓이 되어 mtime 검사가 무조건 skip된다. 그 뒤 line 145는 관측 결과가 아니라 상수 `True`다. 실행 결과의 `evidence_xlsx_pre_repair_sha256`도 line 139의 상수를 복사할 뿐 prerepair bytes를 읽어 계산한 값이 아니다.

따라서 두 봉인의 현재 **내용 동일성**은 확인하지만, 두 번째 봉인이 수리 전에 존재했고 그 내용이 현재와 같았다는 핵심 절차는 확인할 수 없다. 이 항목 판정은 REFUTE다.

## 2. 소스 무수정과 manifest — 통과

`c1v4_results.json -> source_readonly_manifest`에 기록된 8개 파일과 2개 scene directory를 독립적으로 다시 해시하고, 동일한 canonical directory-record 알고리즘으로 digest를 재계산했다.

- recorded before: `65a16f6f0881810e6f2e1586d099d241418e11ea94ae16a8cebeb88d9563346c`.
- recorded after: 같은 값.
- 현재 독립 재계산: 같은 값.
- file mismatch 0/8, directory mismatch 0/2.
- `loop_l1b\scenes_v3` 200개 digest `95593c0e6a482fecc8c051a3026e711cd28d072cc08f4e562d318afda10603db`.
- `feyerabend_c0\scenes` 200개 digest `a1ac0601d321be6111bd2ef60175a794267aa167f3d8ee92daaba7b09900ee12`.
- task가 가리킨 repo `reports\e2\chainverify_L1b\lens2_stats.md`와 manifest가 사용한 runs 사본은 모두 SHA `6cb7a87434c8752b753035cedd55717762cc7af143b19b163adb3062bedb92c6`.
- REPORT의 L1c 산출물 SHA 6개도 현재 bytes와 모두 일치했다.

근거 전문은 `seat4_work\audit_results.json:977-1097`; REPORT 요약은 `REPORT.md:121-131`이다. 이 범위에서 기존 산출물·원본 소스 변경은 확인되지 않았다.

## 3. 300종 속성 시험 — 기록된 표본은 통과, 보편 단조성은 실패

공식 generator를 호출해 결과를 복사하지 않고, `feyerabend_c1_v2.py:542-667`의 RNG 소비 순서와 여섯 mutation을 별도로 구현해 seed부터 재구성했다. 결과는 저장값과 exact match다.

- seed: `20260719`.
- case count: 300.
- family counts: `exact_duplicate=48`, `geometry_ratio_break=42`, `outlier_clone=57`, `reference_support_drop=46`, `stale_override=50`, `suffix_removal=57`.
- upward counts: `confidence_score=0`, `reference_status=0`, `status=0`, `unit_status=0`.
- cases digest: `5dabc8d8bb4ae60c265ec1c5a29f34675f45dcc31c6cbd2ac1dd386add7e29bf`.
- 공식 `feyerabend_c1_v2.py --selftest`는 8/8, `loop_l1c.py --selftest`는 19/19 PASS로 재실행됐다.

각 family는 두 cohort 모두에 들어갔다.

| family | C1-v1 | L1b |
|---|---:|---:|
| exact_duplicate | 22 | 26 |
| geometry_ratio_break | 17 | 25 |
| outlier_clone | 33 | 24 |
| reference_support_drop | 26 | 20 |
| stale_override | 26 | 24 |
| suffix_removal | 26 | 31 |

다만 400장면에서 replacement sampling한 것이어서 unique scene은 222개(각 cohort 111개)다. 봉인 상태 snapshot 기준 `exact_duplicate` 48건과 `suffix_removal` 57건, 합계 105/300은 before/after가 같았다. 따라서 300은 실제 deterministic 시험이지만, 단조성 경계 형태를 300개 독립 구조로 폭넓게 탐색한 것은 아니다. 원자료는 `seat4_work\audit_results.json:1098-1215`, REPORT 값은 `REPORT.md:46-49`다.

아래 5절의 반례 때문에 “이 고정 표본에서 상승 0”만 CONFIRM이고, prereg의 `scope: any perturbation`은 REFUTE다.

## 4. 400장면 replay와 26→0 — 통과

두 cohort 400장면을 원본과 v2로 전량 다시 평가해 저장 row와 canonical 비교했다.

| cohort | original rows digest | patched rows digest | 저장 row mismatch |
|---|---|---|---:|
| L1b 200 | `632fdeb6aa0835479dcc88f201d11108c50b275a52c15d821d98d3414bac5fb8` | `e1b81c370d12f74e1c875e64d6dfea7ad78967df2271132a12c65ef6163379b3` | original 0, patched 0 |
| C1-v1 200 | `1c0898e48254f8e5a657080cb56e3570d4161adfc1e354b33614822f1ef214bf` | `c40628edad398fdc91b7c48de3a921e04ec1b6490baa0e165c38cfe197b7cc82` | original 0, patched 0 |

- C1-v1 `single_outlier`: 원본 `status` 상승 26, `reference_status` 상승 26; v2는 각각 0. 정확한 26 scene id 목록도 독립 결과에 저장했다 (`seat4_work\audit_results.json:794-915`; REPORT `:106-113`).
- L1b의 네 corruption은 원본/v2 모두 해당 두 상태 상승 0.
- unperturbed common scalar/categorical model field는 두 cohort 모두 changed scene 0이고, unperturbed guard rejection도 0 (`seat4_work\audit_results.json:1719-1742`).
- L1b scale별 HIGH coverage `0.8`, HIGH accuracy `1.0`, 오차 분포 불변이라는 REPORT 표도 저장 row 재계산과 일치한다 (`REPORT.md:52-84`).

즉 기존 두 cohort에서의 국소 수리 효과와 정상 수치 불변은 사실이다.

## 5. v2 신규 퇴행·이상 경로 — 실패

### 5.1 결정적 신규 역전: stale override가 reference 분모를 청소해 LOW→HIGH를 만든다

유효 DIM anchor만으로 다음 입력을 만들었다.

- `GOOD_0..3`: geometry span `100`, display `100`, ratio `1`, 서로 다른 4 spatial bins.
- `REF_OUTLIER`: geometry span `1000`, display `1000`, ratio `1`, unique handle.
- perturbation은 `REF_OUTLIER.display_value`만 `1000→2000`으로 바꾼 stale override다. geometry, span, handle, type, weight는 그대로다.

전이 결과:

| estimator | phase | ratio confidence / unit | reference confidence / status | overall status | guard rejects |
|---|---|---|---|---|---:|
| original | before | `1.00 / HIGH` | `0.64 / LOW` | LOW | 0 |
| original | after | `0.64 / LOW` | `0.64 / LOW` | LOW | 0 |
| C1v4 | before | `1.00 / HIGH` | `0.64 / LOW` | LOW | 0 |
| C1v4 | after | `0.64 / LOW` | **`0.80 / HIGH`** | **HIGH** | 1 |

수학적으로 before reference mode는 4/5 consensus이므로 `0.8 × min(1,4/5) × 1 = 0.64`다. mutation 뒤 v2는 ratio outlier인 다섯 번째 anchor를 reference records에서 완전히 제거한다 (`feyerabend_c1_v2.py:164-198`). 남은 4개 안에서 consensus가 1.0이 되어 `1.0 × 4/5 × 1 = 0.80`, HIGH threshold `0.75`를 넘는다. `status = reference_status` (`feyerabend_c1_v2.py:200-224`)라서 봉인 필드 `status`가 LOW→HIGH로 상승한다.

이는 원 결함과 다른 **가드 유발 분모 역전**이다. 원본은 stale anchor를 reference outlier로 분모에 남겨 LOW를 유지한다. 동일 구조를 `good_count=3..8`, reference outlier count `1..3`, override factor `{1.25,2,25}`로 전개한 54개 sweep에서 15개가 status/reference LOW→HIGH였다 (`seat4_work\audit_results.json:207-282,324-793`).

고정 seed 300건의 stale_override 50개가 이 입력 구조를 뽑지 않았을 뿐이다. prereg의 `allowed_upward_transition_count=0`, `scope=any perturbation`, fields에 `status` 포함이라는 계약을 직접 위반한다.

### 5.2 ratio guard handle-collision 우회

`prepare_anchors`는 handle uniqueness를 검사하지 않는다. canonical 중복은 geometry/display/unit key로만 줄인다 (`feyerabend_c1.py:170-252`). v2는 anchor identity 대신 `str(handle)` 집합으로 ratio inlier membership을 판정한다 (`feyerabend_c1_v2.py:168-198`).

3개 정상 anchor의 handle 중 `H0`를 재사용한 ratio-outlier anchor를 네 번째 spatial bin에 넣으면:

- `ratio_inlier_handles = [H0,H1,H2]`, `ratio_outlier_handles = [H0]`.
- outlier의 handle도 inlier set에 있으므로 guard rejection 0.
- reference inliers `[H0,H0,H1,H2]`, reference confidence `0.60→0.80`, status `LOW→HIGH`.

즉 code-admissible duplicate-handle 입력에서 원 live 결함이 그대로 우회된다 (`seat4_work\audit_results.json:3-82`). CAD 정상 handle의 유일성을 기대하더라도, estimator 입력 계약과 canonicalizer가 이를 강제하지 않으므로 corruption/anomaly 방어로는 불완전하다.

### 5.3 정당한 mixed-unit anchor 과차단

도시는 suffix anchor를 unit-normalized `z^mm` 합의로 보라고 명시한다 (`feyerabend_P2.md:194-218`, 특히 line 205). 그러나 v2는 unit 변환 전에 `log(display_value/raw_span)`으로 ratio mode를 고른다 (`feyerabend_c1_v2.py:113-145`); `UNIT_TO_MM`은 mode가 정해진 뒤 `mm_per_raw` 출력에만 쓰인다 (`:147-162`).

같은 raw span `1000`을 나타내는 anchor 4개를 다음처럼 넣었다.

- 세 개: display `1000`, unit `MM`.
- 한 개: display `1`, unit `M`.

물리적으로 모두 `1000 mm`인데 v2는 `M_3`을 ratio outlier로 격리한다. 원본은 reference support 4개, score `0.80`, `reference_status/status=HIGH`; v2는 support 3개, score `0.60`, `reference_status/status=LOW`가 됐다 (`seat4_work\audit_results.json:283-323`). 이는 새 가드가 만든 정당 anchor coverage 퇴행이며 도시의 `z^mm` 규칙과도 어긋난다.

### 5.4 남은 ratio-less/GRID 상승 경로

3개 span-inlier DIM anchor의 reference score가 `0.60/LOW`인 입력에 네 번째 spatial-bin support를 넣으면 다음 두 경우 모두 v2가 `0.80/HIGH`로 상승했다.

- `display_value=None`인 DIM/TEXT reference-only anchor.
- GRID reference-only anchor.

두 경로는 v2 주석과 REPORT 미해결 절에서 의도적으로 보존했다고 인정한다 (`feyerabend_c1_v2.py:164-167`; `REPORT.md:133-136`). GRID-only reference가 유효할 수 있다는 도시 설계 (`feyerabend_P2.md:218`) 때문에 이것만으로 모두 버그라고 단정하지는 않는다. 그러나 prereg 문언은 `scope=any perturbation`이고 입력 한 건만으로 진짜 GRID/reference와 교란을 식별할 수 없다는 미해결이 남아 있으므로, “루프 종결”의 보편 단조성 해석은 성립하지 않는다.

## 6. 종합 판정

확인된 사실:

- prereg JSON과 현재 PREREG sheet 내용은 완전 일치한다.
- 밴드 수치는 도시/packet과 일치한다.
- source manifest와 현재 원본 SHA는 완전 일치한다.
- 기록된 300 fixed-seed cases는 정확히 재현되고 그 표본 안에서는 상승 0이다.
- C1 원본 cohort의 표준 `single_outlier` 상승 26건은 v2에서 0건이다.
- L1b 정상 cohort의 공통 수치 필드는 불변이다.

그러나 검증 대상은 이 사실들의 일부가 아니라 “이중 선행 봉인까지 절차대로 수행됐고, 수리가 결함을 닫아 L1c로 루프가 종결됐다”는 결합 주장이다. 전달 증거로 선행 workbook seal을 입증할 수 없고, 더 결정적으로 C1v4 자체가 유효 stale override에서 새로운 `status LOW→HIGH`를 만든다. 따라서 CONFIRM할 수 없다.

VERDICT: REFUTE
