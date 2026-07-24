# Seat 4 전면 감사 — L1e 교차 벤더 회의론 평결

## 결론

**REFUTE.** 봉인 사슬과 공개된 수치/manifest는 재구성 결과와 일치했지만, 종결에 필수인 자동 증인 판정기가 prereg의 `residual ratio outlier = explicit violation evidence` 규칙을 구현하지 못한다. 특히 `1τ < 거리 < 3.5τ`인 가시 ratio outlier를 잔존 의심으로 보고하지 않아, 그 outlier가 남은 상승을 `information_limit_record`로 오분류한다. 독립 적대 프로브 5건 모두 이 실패를 재현했고, 추가 1,494-case 수색에서 같은 유형 747건을 찾았다. 허용 violation 수는 0이므로 한 건만으로도 종결 주장은 성립하지 않는다.

감사는 원본 CAD 및 test를 실행하지 않았고, 서브에이전트를 사용하지 않았다. Git은 지정 repo의 `3a390e8` 봉인 검증에만 읽기 조회했다. 재계산 산출은 `seat4_work`에만 기록했으며, 원본 16개 입력의 전후 SHA-256 불일치 수는 0이다.

## ① 봉인 증인 사슬

이 항목의 내용 봉인은 확인했다.

- 지정 commit은 `3a390e83d05bb09a2d5589e7e206d9f86f6cf33d`이며 `main`이 이를 포함한다. author/commit 시각은 `2026-07-19T04:54:43+09:00`, parent는 `04f0e7dee3961b441602d13b1bf9959725dfc736`이다.
- 이 commit의 변경 경로는 아래 세 파일의 신규 추가뿐이다.
  - `reports/e2/cells/loop_l1e/prereg.json`
  - `reports/e2/cells/loop_l1e/PREREG_SEALED.csv`
  - `reports/e2/cells/loop_l1e/SEAL_MANIFEST.txt`
- commit tree에는 `tools/e2/cells/feyerabend_c1.py`, `_v2.py`, `_v3.py`는 있으나 `feyerabend_c1_v4.py`와 `loop_l1e.py`는 각각 0개다. 따라서 해당 tree 시점의 Phase B 추정기 부재는 확인된다.
- commit blob, repo working copy, run copy가 세 파일 모두 byte-identical이다.

| 파일 | commit blob | SHA-256 |
|---|---|---|
| `prereg.json` | `a91b72fc00dd05a1be36f834e528bd03c49e1a5b` | `EF1E98025EF3CF46CC829085F6F112E8E3CF2068756E0112043686215D743C86` |
| `PREREG_SEALED.csv` | `78a9a94c8a391f816dc359642420a11106aa5df1` | `4AA741C42F5828CC9484F8EBBA62C3CDBD1B9A5FE926C635514A5498BE48BB6B` |
| `SEAL_MANIFEST.txt` | `8674d80ed6e86a733da84dc99537c4f36b29edd2` | `73B83C3DC75206B37F460DB88096B032B1254120E75DFBD9997BAA2772E53693` |

- CSV는 정확히 2 record이며 canonical JSON record는 `prereg.json`과 동치다. manifest의 두 digest도 일치한다.
- run 파일 시각도 prereg `04:51:43`, CSV `04:52:20`, manifest `04:52:50`, commit `04:54:43`, runner `05:24:01`, v4 estimator `05:28:52`, results `05:30:29` 순이다.
- 단, commit signature 상태는 `N`(unsigned)이므로 Git metadata 자체가 외부 신뢰 시각기관의 증명은 아니다. 이 한계와 별개로, 계약에서 요구한 commit tree 내용 및 상대 순서는 확인했다.

## ② 641 property case, 5개 의무 stratum, 1,548 탐색 및 72,396 전이

독립 harness가 seeded mutator, fixture, Cartesian pool, 9-family variant 열거, canonical digest 및 모든 상승 필드를 별도로 재구성했다. v4 코드는 검증 대상 DUT로만 로드했다.

- 총 `521,443`개 검사, artifact mismatch `0`.
- property: randomized `630` + third-fleet regression `11` = `641`.
- 9 family는 각각 `70` case로 모두 비어 있지 않다.
- 5개 의무 stratum은 `zero_cliff_start=105`, `ratio_outlier=105`, `mixed_space=105`, `handle_collision=105`, `near_tau_spread=210`으로 모두 비어 있지 않다.
- property manifest digest 재계산값은 `82469917032f27c1d9b2eb6225b1b38353a4c38d8a6aac830b07a54a2efbf77e`로 공개값과 일치한다.
- search base는 6개 상태의 길이 2/3/4 Cartesian product이므로 `6^2 + 6^3 + 6^4 = 1,548`이다.
- 각 n-anchor base의 variant 수는 `12n+1`; 따라서 `6^2×25 + 6^3×37 + 6^4×49 = 72,396`이다.
- 1,548개 base row와 72,396개 transition row를 순서, case ID, variant, surface digest, 재실행 상승 필드까지 전건 대조했다.
- base manifest digest `d2b4efaa145aa0fa2f49765ce3686ce2f3c8c19be5287c4417a7c502e7c148ef`, transition manifest digest `7fadbe89300827e038f2be62ca8aa661d13bab21c7ff8a31a8a9658ea30db04c`가 각각 일치한다.
- 공개 탐색 범위에서는 수리 가능 6 family(`outlier_clone`, `handle_collision`, `display_removal`, `geometry_ratio_break`, `exact_duplicate`, `reference_support_drop`)의 상승이 모두 0인 것도 재현했다.
- 공개 잔존 상승은 `stale_override=36`, `suffix_removal=66`, `type_to_grid=210` transitions이고 각 transition이 5개 추적 필드를 올려 각각 180/330/1,050 field events를 만든다는 수치도 일치한다.

따라서 **공개된 유한 탐색의 회계는 맞다.** 아래 ④의 실패는 이 탐색 격자가 `1τ < d < 3.5τ` 구간과 자유 clean-handle 추가를 포함하지 않아 놓친 의미론 반례다.

## ③ 361 증인 record의 prereg 5종 증거 전건 감사

형식적 완전성은 통과했지만 독립 정당성은 통과하지 못했다.

| prereg 요구 증거 | 전건 형식 검사 | 실질 판정 |
|---|---:|---|
| witness 식별자 + complete input serialization | 361/361 존재 | 모든 식별자가 `HONEST::<post_sha256>`로 post에서 파생됨 |
| post-perturbation complete serialization | 361/361 존재 | canonical serialization 확인 |
| exact equality + 양쪽 digest | 361/361 유효 | 양 serialization이 361/361 byte-identical |
| city-semantic legitimacy rationale | 361/361 존재 | 361건 모두 동일한 1개 boilerplate rationale |
| automated classification | 361/361 존재 | 전부 `information_limit_record`, violation 0 |

추가 전건 결과:

- classification ID `W000000`~`W000360`은 유일하고 연속이다.
- 모든 ID를 실제 상승 transition에 역연결했으며 누락/고아 ID는 0이다.
- field event 합계는 `1,767`, manual suppression 0, unclassified 0이다.
- witness payload digest 재계산값 `9dbd08d03dd75cfcb7d33b6acebc3b31b7712165043bb0c4244e8817c0a888fd`가 일치한다.
- 그러나 unique post surface와 unique witness ID는 각각 65뿐이며, 별도 witness provenance/source field는 없다.

결정적 문제는 `loop_l1e.py:469-480`이다. 이 코드는 post surface를 직렬화한 뒤 JSON round-trip으로 그대로 복사해 witness surface를 만들고, 그 필연적 equality를 독립 증인으로 취급한다. 이는 prereg의 “independently specified honest scene, not justified by hidden perturbation history” 요구를 입증하지 않는다. 구조상 5개 필드가 채워졌다는 사실과 독립 정당성이 입증되었다는 사실은 동일하지 않다.

## ④ v4 신규 이상 경로 전면 수색

### 근본 원인

- consensus outlier 경계는 `τ`다.
- `feyerabend_c1_v4.py:291-296`은 오직 `distance >= 3.5τ` 또는 structural case만 `hard_suspicious_handles`에 넣는다.
- `feyerabend_c1_v4.py:816-825`의 `suspicion_analysis`는 이 hard 집합만 ratio suspicion으로 공개하며, `(τ, 3.5τ)`의 가시 non-inlier를 누락한다.
- `loop_l1e.py:478-480`은 `residual_suspicion_count == 0`이면 legitimate로 정하고, 앞서 복제한 equality와 결합해 `information_limit_record`를 낸다.

즉, estimator 내부에서 consensus support 밖에 남아 있는 명시적 ratio record가 있어도 그 거리가 3.5τ 미만이면 자동 증인 판정기가 이를 보지 못한다. prereg는 residual ratio outlier를 명시적 violation evidence로 규정하므로 이 누락은 직접 계약 위반이다.

### 독립 targeted 반례

아래 모든 post surface에는 `τ`보다 먼 eligible ratio record가 실제로 남아 있고, 별도 consensus 재계산에서 non-inlier로 확인됐다. 그럼에도 공개 classifier 조건은 모두 `residual_suspicion_count=0`이고 `information_limit_record`를 낸다.

| probe/family | 잔존 outlier | confidence 전→후 | reference 전→후 | 기타 상승 |
|---|---:|---:|---:|---|
| clean-handle dilution + spatial mask (자유 변형) | `OUT=2.0τ` | `0.5625→0.8` | `0.75→0.8` | `unit_status LOW→HIGH` |
| suffix merge (`suffix_removal`) | `SOUT=2.0τ` | `0→0.5625` | `0→0.75` | `status NONE→HIGH`, `unit NONE→LOW`, `reference NONE→HIGH` |
| mixed-severity retype (`type_to_grid`) | `MODERATE=2.0τ` | `0→0.5625` | `0→0.6` | 세 status 모두 `NONE→LOW` |
| partial stale correction (`stale_override`) | `STALE=2.4τ` | `0.01575→0.5625` | `0.021→0.75` | `status/reference LOW→HIGH` |
| partial geometry correction (`geometry_ratio_break`) | `GEOM=2.4τ` | `0.01575→0.5625` | `0.021→0.421875` | numeric 2필드 상승 |

첫 반례를 확장해 outlier 거리 `1.01τ`~`3.49τ`의 249 값과 clean handle 위치 6개를 교차한 `1,494` case를 탐색했다. 그중 `747` case가 residual outlier를 유지한 채 추적 필드를 올렸고, `747/747` 모두 classifier의 residual count가 0이었다. 이는 단일 경계 우연이 아니라 누락된 전체 구간이다.

## 평결 근거 요약

- PASS: commit tree의 Phase A 내용, 추정기 부재, 세 봉인 파일 불변성.
- PASS: 공개된 641/1,548/72,396 회계, manifest/digest, 공개 격자 내 family 통계.
- PASS(형식만): 361 record의 필드/serialization/digest/cross-link 완전성.
- FAIL: independently specified honest witness의 실질 증거가 없고 post 복제만 존재.
- FAIL: prereg가 violation으로 정한 residual ratio outlier 상승을 자동 판정기가 `information_limit_record`로 받는다.
- FAIL: 신규 targeted violation 5건 및 확장 탐색 747건. 허용 violation 0.

재현 파일:

- `D:\runs\e2_program\chainverify_L1e\seat4_work\audit_reconstruct.py` — SHA-256 `452983AC6C4860CEC4E853748D29C12651DA5D164D1720CEE2BEDF14FE18B278`
- `D:\runs\e2_program\chainverify_L1e\seat4_work\audit_results.json` — SHA-256 `E8A0831141B0E87748F0FDDE79C3574F06AAE1B2754B7BE56041E0CF1B960D6A`

VERDICT: REFUTE
