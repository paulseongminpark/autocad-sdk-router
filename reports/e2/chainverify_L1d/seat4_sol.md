# Seat4 전면 감사 — L1d 교차 벤더 회의론 검증

## 판정 요약

좁은 재현 주장은 확인했다. 현재 L1d 산출물의 해시는 REPORT와 일치하고, 두 봉인 파일의 현재 내용은 서로 완전히 일치하며, 9-family 고정시드 600 case와 54-case denominator sweep은 독립 재구성에서도 상승 0이다. C1 원본 코호트 coverage/accuracy 1.0/1.0과 L1b의 0.8/1.0도 라이브 재실행으로 재현됐다.

그러나 결합 주장인 **“L1d로 루프가 종결됐다”**는 성립하지 않는다.

1. 실물 sidecar는 존재하지만, 로컬 filesystem 시각·OOXML 시각·ReadOnly bit만으로는 estimator보다 선행한 불변 봉인을 교차 벤더 관점에서 입증할 수 없다. 동일한 관측은 사후 생성·시간 역산·ReadOnly 후설정으로 만들 수 있다.
2. 더 결정적으로, 저장된 600 case가 한 번도 밟지 않은 strict-coherence 0 상태에서 같은 봉인 9-family 문법이 다수의 상승을 만든다. `suffix_removal`은 정보가 줄었는데도 5개 봉인 필드를 모두 올리는 직접 반례다.
3. 검사기의 literal `True` 성공 상수는 제거됐지만, `unique_handle_independence` selftest의 성공 술어는 후보 handle partition 수에 2를 더해 비교하는 항진식이다. 기능적으로 실패를 검출하지 못하는 성공 플래그다.

계약의 “불확실하면 REFUTE”에 의존할 필요 없이 2번이 직접 반례다.

## 1. 감사 경계와 재현물

- 원본 CAD와 test surface는 접근하지 않았다.
- 모든 재계산 산출은 `D:\runs\e2_program\chainverify_L1d\seat4_work\`에만 기록했다.
- 원본·scene·estimator의 전후 해시는 불변이다. git 명령·commit·subagent를 사용하지 않았다.
- 독립 증거:
  - `seat4_work\seal_audit.json`
  - `seat4_work\property_rebuild.json`
  - `seat4_work\boundary_audit.json`
  - `seat4_work\cohort_check.json`

Spreadsheet artifact runtime의 dependency loader가 이 세션에 없어 workbook 시각 렌더는 수행하지 못했다. 대신 ZIP CRC, workbook/sheet relationship, raw cell types·values, formula·external relationship·macro/custom part를 OOXML에서 직접 검사했다. 이 제한 때문에 외관을 봉인 증명으로 과대해석하지 않았으며, 아래 반례 계산에는 영향이 없다.

## 2. 이중 봉인

### 2.1 현재 내용과 실물은 확인

독립 SHA-256:

- `prereg.json`: `474cf61bb8d8856d62e161444b091bd0f501e8fda30d116612608974db6524c1`
- `evidence_sealed.xlsx`: `0d1f30762546ece2a2b0233f46410f78edb8f69c99b6512d251cc519ba2d4cf4`

둘 다 REPORT 서두, `loop_l1d.py`의 expected hash, 결과 JSON에 기록된 값과 일치한다. sealed workbook은 실제 ZIP/OOXML 실물이며:

- visible `PREREG` sheet 하나, dimension `A1:F105`;
- `PREREG!B5`가 prereg JSON의 UTF-8 sorted compact canonical JSON과 byte-for-byte 동일;
- JSON leaf 98개 대 98개, 값·type mismatch 0;
- formula 0, external relationship 0, defined-name 우회 0, macro/external/custom/OLE part 0;
- ZIP CRC 이상 0;
- 두 파일 모두 현재 Windows ReadOnly attribute가 설정됨;
- filesystem creation/mtime와 workbook core `created/modified`가 estimator 시각보다 이른 값으로 정렬됨.

따라서 **현재 두 실물의 내용 동일성**은 CONFIRM이다.

### 2.2 선행·불변성은 입증되지 않음

위 관측은 tamper-evident timestamp가 아니다. `seat4_work\backdate_demo.txt`를 이번 감사 중 작성한 뒤 표준 로컬 API만으로 creation/mtime을 2001-01-01로 역산하고 ReadOnly bit를 후설정했다. 관측 결과는 estimator보다 오래되고 read-only인 파일로 보였다. 이는 실제 봉인이 위조됐다는 증거가 아니라, 제시된 관측만으로 위조 가능성을 배제할 수 없다는 실증이다.

명명된 증거에는 외부 timestamp authority, 서명된 digest, append-only 원격 witness, deny-write ACL 이력 어느 것도 없다. OOXML core time도 workbook 내부의 수정 가능한 문자열이다. 또한:

- `loop_l1d.py:87`은 estimator module을 먼저 import하고, seal 검사는 `execute_full`의 `:1149`에서 실행한다.
- expected hash 상수는 estimator보다 나중에 만들어진 `loop_l1d.py:62-63`에 있다.
- `verify_seals()`는 기존 REPORT가 expected hash를 포함하는지도 검사한다(`:179-197`). 이후 같은 실행이 REPORT를 다시 작성하므로 최초 봉인 증명이라기보다 이미 완성된 산출물의 자기일관성 검사다.

따라서 filesystem 시각이 서로 일관된다는 사실은 확인하지만, **사전봉인 절차가 역산 불가능하게 입증됐다**는 주장은 REFUTE다.

### 2.3 검사기 상수 성공 부재

L1c의 literal `True` 반환 결함은 현재 `verify_seals()`에서 제거됐다. 각 seal observation은 실제 비교식이다. 그러나 `feyerabend_c1_v3.py:1214-1227`의 `unique_handle_independence` selftest는 다음 형태다.

`n_candidate_handles < len(ratio_inlier_handles) + len(ratio_outlier_handles) + 2`

inlier/outlier handle이 candidate handle partition이므로 정상 provenance에서는 우변이 항상 `n_candidate_handles + 2`다. 즉 테스트 이름과 달리 `n_independent < n_candidate_handles`나 기대값 `2/3`을 assert하지 않으며 논리적으로 항상 통과한다. 실제 detail `n_candidate_handles=3`, `n_independent=2`는 맞지만 성공 술어가 그 사실을 검증하지 않는다. “관측값만 사용하고 상수 성공 플래그가 없다”는 검사기 무결 주장은 이 항진식 때문에 CONFIRM할 수 없다.

## 3. 9-family 600 case 독립 재구성

vendor의 `monotonicity_property_test`, `randomized_corruption`, `_snapshot`, `_increases`, digest helper를 사용하지 않고 문법·RNG 소비 순서·scene selection·mutation·5-field 비교·canonical digest를 별도 구현했다.

결과:

- seed: `20260719`
- case: 600
- family count: `{66,67}` 분배가 원 기록과 정확히 일치
- cases digest: `f03048a56f3f289e0660461e77ffa03e8da6eef5bb69f7c5af79538eb3b6a207`
- 5개 field upward count: 전부 0
- 독립 summary = vendor live summary = `fleet_probe_results.json` = `c1v5_results.json` = REPORT
- source manifest 전후 동일
- replacement sampling의 실제 unique scene: 317/400 (`c1_original` 162, `l1b` 155)

따라서 **그 고정 표본에서 상승 0**은 CONFIRM이다. REPORT 379행도 결과를 두 200-scene pool로 제한한다고 정직하게 적었다.

다만 시험 강도에는 중요한 공백이 있다.

- 600/600 모두 before ratio confidence가 0보다 컸다. strict-coherence 0-collapse 시작 상태는 한 건도 없었다.
- `exact_duplicate` 67/67은 raw input은 변했지만 canonical preparation 뒤 변화 0, model snapshot 변화 0이었다.
- `suffix_removal` 67/67은 full model의 unit metadata는 바뀌었지만 봉인 5-field snapshot 변화는 0이었다.

즉 600이라는 수는 실재하고 재현되지만, v3의 신규 절벽 상태를 포괄하는 600개의 독립 구조를 뜻하지 않는다.

## 4. v3 신규 이상 경로

v3의 핵심은 `feyerabend_c1_v3.py:380-390`의 `all_candidates_coherent` binary factor다. selected mode가 candidate 전체와 정확히 같지 않으면 다른 연속 factor와 무관하게 confidence가 즉시 0이 된다. 저장된 600 case는 이 0 상태에서 출발하지 않았기 때문에, 교란이 일부 불일치를 제거해 0에서 1로 복귀하는 경로를 보지 못했다.

### 4.1 최소 직접 반례

| mutation | before | after | 상승 field |
|---|---|---|---|
| `suffix_removal` | ratio conf `0`, ref conf `2/3`, LOW/LOW/LOW | ratio/ref conf `1`, HIGH/HIGH/HIGH | 5개 전부 |
| `type_to_grid` | ratio conf `0`, ref conf `2/3`, status/ref LOW, unit LOW | ratio/ref conf `1`, status/ref HIGH, unit LOW | conf·ref_conf·status·ref_status |
| `stale_override ×1.25` | ratio conf `0`, ref conf `2/3`, LOW/LOW/LOW | ratio/ref conf `1`, HIGH/HIGH/HIGH | 5개 전부 |
| `geometry_ratio_break ×0.2` | ratio/ref conf `0`, LOW/LOW/LOW | ratio/ref conf `1`, HIGH/HIGH/HIGH | 5개 전부 |

가장 강한 반례는 `suffix_removal`이다. 세 anchor의 실제 숫자 ratio는 모두 2.5이고, 두 개는 `MM`, 한 개는 `UNKNOWN`이다. v3는 동일 숫자를 `z_mm`과 `z_raw`의 별도 mode로 나눠 strict factor를 0으로 만든다. 그 뒤 두 명시 suffix를 제거하는 **정보 손실**이 세 anchor를 모두 `z_raw`로 합쳐 5개 봉인 field를 올린다. 이는 “의심 증거는 분모에만 남아 교란이 confidence/status를 올리지 못한다”는 구조 논증에 대한 동일 grammar 직접 반례다.

### 4.2 체계적 작은 상태 탐색

ratio `{2.0, 2.5, 3.125}` × unit `{MM, UNKNOWN}` × anchor count `{2,3,4}`의 ordered scene 1,548개를 전수 구성했다. 1,530개가 strict ratio score 0에서 시작했다. 봉인 9-family와 동일한 변형을 적용한 결과:

- `suffix_removal`: 786 / 1,548 transition에서 상승
- `type_to_grid`: 3,870 / 5,904 transition에서 상승
- `stale_override`: 948 / 17,712 transition에서 상승

상승은 모두 ratio score 0 시작 상태에서 나왔다. 다른 여섯 family는 이 제한된 문법에서는 상승 0이었다. 별도 exact targeted scene에서는 봉인 geometry factor `0.2`도 5-field 상승을 만들었다.

따라서 “저장된 600 case가 0이었다”는 사실과 “9-family 구조가 단조적이다”는 명제는 다르다. 전자는 CONFIRM, 후자는 REFUTE다. task가 요구한 신규 이상 경로 수색에서 후자가 실제로 깨졌으므로 루프 종결 주장은 무너진다.

### 4.3 절벽과 0.75 경계

- 세 coherent anchor 중 하나를 tolerance `log(1.05)`의 아래/위로 ratio factor 약 `2.1e-10`만 이동시키자 ratio confidence가 `1→0`, reference confidence가 `1→2/3`, 세 status가 `HIGH→LOW`로 불연속 전환했다. 역방향의 같은 미세 이동은 이 필드들을 복구한다.
- reference handle이 4개이고 ratio-trusted handle이 3개이면 reference confidence는 정확히 `0.75`이며 `>=` 비교 때문에 `HIGH`다. untrusted handle 하나를 더 넣어 3/5가 되면 `0.6/LOW`다.

이는 구현된 경계와 REPORT 수치에는 일치하지만, v3가 smooth한 보수적 confidence가 아니라 binary coherence 절벽과 정수 handle 경계를 갖는다는 뜻이다.

## 5. B4 정보 한계의 정직성

B4는 이 감사에서 재현됐다.

- coherent unique handle 수 1·2에서도 v3 numeric confidence는 이미 `1.0`이고 status만 `MIN_INDEPENDENT=3` 때문에 LOW다.
- 세 번째 구별 불가능 handle을 넣으면 confidence는 `1→1`로 포화된 채 `unit_status`, `reference_status`, `status` 세 필드가 LOW→HIGH가 된다.
- 독립 재구성은 저장된 `B4_information_limit_two_to_three`와 정확히 일치한다.
- prereg의 B4 gate는 `false`이고 REPORT 146-154·375-379행은 이 3-field 상승과 식별 한계를 숨기지 않는다.

따라서 **주어진 estimator 관측 모델 안에서 B4 한계를 공개한 정직성**은 CONFIRM이다. 다만 “unique handle”은 인증된 독립 주체가 아니라 입력 문자열이므로 새 handle 위조를 막지 않는다. 이 probe에는 외부 truth/authentication이 없어 accuracy 공격을 측정한 것이 아니라 support/status spoofability를 측정한 것이다. B4가 gate 밖이라는 봉인 선택을 존중하므로 이 한계만으로 판정을 내리지는 않았다.

## 6. 나머지 수치 교차 확인

- live vendor fleet core(P0, B1-B4, O1-O3, 54 sweep)는 저장 JSON과 완전 일치했다.
- 54 denominator-cleanup case를 별도 구성해 5-field 상승 0을 재현했다.
- O1/O2 status downgrade는 0이다.
- C1 원본 200 scene: 모든 scale에서 HIGH coverage `1.0`, HIGH accuracy `1.0`; 전체 relative-error max `4.44e-16`.
- L1b 200 scene: 모든 scale에서 HIGH coverage `0.8`, HIGH accuracy `1.0`; 전체 relative-error max `3.11e-15`.
- L1b의 input count, scale/truth/estimate/error, status/unit/reference status, physical unit은 v1→v3와 v2→v3 모두 scene change 0이었다.
- REPORT가 열거한 8개 L1d artifact SHA는 현재 파일과 전부 일치한다.

이 수치들은 CONFIRM이다. 그러나 수치 표본의 정확성이 사전봉인 입증 실패와 동일 family의 live counterexample을 상쇄하지 않는다.

## 최종 판정

현재 sidecar 내용, 고정시드 600 case, 54 sweep, O1/O2, cohort headline 수치는 재현된다. 반면 사전봉인 chronology는 로컬 시각만으로 독립 입증되지 않고, checker에는 항진식 selftest가 있으며, 가장 중요하게는 strict-coherence 0 상태에서 봉인 grammar 자체가 다수의 upward transition을 만든다. 따라서 Feyerabend C1 루프가 L1d로 종결됐다는 결합 주장을 확인할 수 없다.

VERDICT: REFUTE
