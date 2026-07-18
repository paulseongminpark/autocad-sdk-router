# seat4 — L1f Phase B 독립 계측 재검증 평결

## 최종 판정

**REFUTE.** 봉인 선행 사슬과 실행 보고의 주요 수치 회계는 재현되었지만, 봉인 계약의 두 필수 조건이 충족되지 않는다.

1. **새로운 결함 유형 — 동결 표면 필드형 심판 누락.** `text_height`, `region`, `anchor_factory_revision`, `display_value`, `display_unit`의 비계약형 값이 동결 표면에 그대로 남아도 `declared_field_type_and_presence`는 0건을 기록한다. 동일 비정상 필드형을 유지한 채 다른 Tier-B 신호를 완화·제거하면 점수가 `0→0.7784468207540134` 또는 `0→1.0`으로 상승하고 세 상태가 모두 `HIGH`가 되며, 증인 생성기까지 표면을 수용한다. 이는 봉인 계약의 전 필드 원형·타입·값 심판 및 closed-world 규칙 위반이다. 이 유형은 지정된 알려진 결함 목록의 `선언↔기하 불일치 비검출`보다 넓은 **비기하 선언 필드형 미심판**이므로 새로운 결함 유형으로 판정한다.
2. **알려진 결함 유형의 회귀 — 증인 논거 항진.** 90개 상승 분류의 증인 사양은 매번 post 표면에서 `raw_span`만 제외한 전 필드를 그대로 생성기 파라미터로 복사하고, 같은 post `p0/p1`에서 `raw_span`을 재계산한다. 증인 직렬화는 post 직렬화와 90/90 동일하고 식별자는 그 사양 digest에서 파생된다. 실행 하니스는 `exact equality ∧ Tier-B count=0`만으로 도시 의미 정당성을 참으로 둔다. 따라서 독립 장면은 제시되지 않았고, 이 실패는 알려진 `증인 논거 항진`의 회귀다.

새로운 결함 유형이 한 건 이상 실증되었으므로, 패킷이 규정한 다음 단계 분기상 설계 재검토 상신 조건이 성립한다.

전체 산출 명령: `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --run`

## 실행 경계

- 원본 CAD 접근: 0
- test 표면 접근: 0
- 서브에이전트 사용: 0
- Git 명령: `show`, `cat-file`, `log`만 사용
- 쓰기 범위: `D:\runs\e2_program\chainverify_L1f\seat4_work\` 및 이 평결 파일
- 읽기 전후 원본 21개 SHA-256 불일치: 0

산출 명령: `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section source_integrity`

## 1. 봉인 선행 증인

커밋 `c896068fe678d91c14be2b8d25a80d959b878813`의 author/commit 시각은 `2026-07-19T06:59:14+09:00`이다. 변경 경로는 아래 세 파일의 신규 추가뿐이었다. 세 commit blob은 repo 작업 복사본 및 실행 복사본과 각각 byte-identical이다.

| 파일 | SHA-256 | commit=repo=run |
|---|---|---:|
| `prereg.json` | `76AC2A58D74C644A3BF7897325818F1E12151596DC3316BA7CA488BDEB207861` | 참 |
| `PREREG_SEALED.csv` | `94356AF8F4D219AF65A96825E3A08B29245454EDA1B29B2C3AE83F4B19A8F266` | 참 |
| `SEAL_MANIFEST.txt` | `2C16BA1E66A2CA491364DD533A914F94592E3EC1558ED35A8A1D02E077F92501` | 참 |

동일 tree에서 `tools/e2/cells/feyerabend_c1_v5.py`와 `tools/e2/cells/loop_l1f.py`는 모두 부재했다. 두 파일의 최초 기록 커밋은 `8675b9073d631ff494f5a06d68010fbacfaabddf`, 시각은 `2026-07-19T07:53:25+09:00`이므로 봉인 커밋보다 54분 11초 뒤다. CSV는 2 record이고 canonical prereg record는 JSON과 동치이며 manifest의 두 digest도 일치한다. 커밋 signature 상태는 `N`이므로 Git metadata 자체는 외부 신뢰 시각기관의 증명은 아니다.

산출 명령: `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section git_witness` 및 `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section seal`

## 2. 계약↔구현 축조 대조

| 봉인 조문 | 독립 결과 | 계측 근거 |
|---|---|---|
| 2계층 경계 및 Tier-B 경로별 exact `0/NONE` | PASS | 열거 Tier-B 경로 9종×N 5점에서 hard-block 위반 0 |
| Tier-A per-signal 감쇠 하한, 후보 수 비희석 | PASS | 11 fixed-S 사례, 55 sweep row, 재분류 0, 하한 붕괴 0 |
| span 측 closed-world/max 봉투 | PASS | 중간·severe span 잔존을 reference 경로에서 전건 exact block |
| ratio-absent GRID 중립(P4) | PASS | reference confidence 손실 0, status downgrade 0 |
| O1/O2 정직 사례 무손실 | PASS | 2사례 status downgrade 0, coverage loss 0 |
| 641 property 및 11 third-fleet 회귀 | PASS | surface/suspicion/v5 snapshot mismatch 각각 0; manifest digest 일치 |
| 이전 체인 명명 회귀 | PASS(수치) | W000002/B5/T_A/T_C/T_S/T_B 6개 상승 0; sweep 15행 mismatch 0 |
| seat4 5개+747창 | PASS(수치) | 아래 3절 수치 재현 |
| 동결 표면 전 필드 타입·값 심판 | **FAIL** | 현재 최소 필드 5종의 비계약형이 rule count 0인 채 상승·증인 수용 |
| 장면별 독립 증인 및 info-limit 금지 | **FAIL** | 90/90 post 파생 사양, 독립 증인 0; 44 잔존 상승 전건 violation |
| replay 공개·coverage·accuracy | PASS | 400장면 전건 v5 rerun 및 field-path 완전성 일치 |
| 술어 반례 무항진성 | PASS(형식), FAIL(실제 의미 심판) | 15/15 반례는 false이나 실제 증인 성공식은 18-rule 길이·18-key·비어 있지 않은 문자열만 검사 |

계약 근거는 `prereg.json`의 closed-world 규칙, 전 필드 `presence/type/value/multiplicity/order` 심판, future field 자동 포함, normalized-away 결과=`violation`, post round-trip 비독립 규칙이다. 구현은 `feyerabend_c1_v5.py`에서 제한된 여섯 종류의 invalid reason만 만들고, `text_height` 변환 실패를 `None`처럼 처리하며, `uncovered_declared_field_count`를 0으로 고정한다. 증인 경로는 post record를 파라미터로 복사한 뒤 동일성을 다시 검사한다.

산출 명령: `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section contract_review`, `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section non_dilution_and_grid`, `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section other_named_regressions`

## 3. 이전 seat4 프로브 독립 재실행

이전 4차 프로브 정의를 독립 구성해 v4와 v5에 다시 실행했다.

| 집합 | parent | v4 상승 | v5 상승 |
|---|---:|---:|---:|
| 표적 5케이스 | 5 | 5 | 0 |
| `1.01τ..3.49τ`×6위치 | 1,494 | 747 | 0 |

1,494개 전건에서 재구성 input digest와 공개 input digest 불일치 0, 상승 map 불일치 0, 747개 known-positive ID 순서 불일치 0이었다.

산출 명령: `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section seat4_regressions`

## 4. 결정적 교란 탐색

seed `2026071904`로 총 4,096사례를 실행했다.

| 탐색 층 | 사례 | 상승 | 계약 위반 |
|---|---:|---:|---:|
| 일반 8종 base×9종 교란 | 2,048 | 60 | 검출된 Tier-B 잔존 상승 0 |
| 비계약 선언 필드형 고정 + 다른 차단 신호 완화/제거 | 1,024 | 1,024 | 1,024 |
| fixed-S 비희석 무작위 N∈[1,60] | 1,024 | 해당 없음 | 하한/하드블록 위반 0 |
| 합계 | 4,096 | — | 1,024 |

전체 case manifest digest는 `157d47ece04072df571705cca813b825e122963110c6b2e1add973c865366af1`이다. 1,024개 비계약 필드형 사례 모두 post Tier-B count 0, declared-field type finding 0, 증인 생성기 수용으로 끝났다.

산출 명령: `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section independent_search`

### 최소 재현 반례

| 사례 | 고정된 비계약형 | score 전→후 | post statuses | type finding | post Tier-B | witness accepted |
|---|---|---:|---|---:|---:|---:|
| `invalid_text_height_mapping_persists` | `text_height={invalid: non_numeric}` | `0→0.7784468207540134` | `HIGH/HIGH/HIGH` | 0 | 0 | 1 |
| `invalid_region_mapping_persists` | `region={invalid: non_string}` | `0→0.7784468207540134` | `HIGH/HIGH/HIGH` | 0 | 0 | 1 |
| `invalid_anchor_factory_revision_mapping_persists` | revision object | `0→0.7784468207540134` | `HIGH/HIGH/HIGH` | 0 | 0 | 1 |
| `invalid_display_value_string_persists` | numeric string | `0→1.0` | `HIGH/HIGH/HIGH` | 0 | 0 | 1 |
| `invalid_display_unit_integer_persists` | integer unit | `0→1.0` | `HIGH/HIGH/HIGH` | 0 | 0 | 1 |
| `invalid_region_list_persists` | list region | `0→1.0` | `HIGH/HIGH/HIGH` | 0 | 0 | 1 |

첫 세 사례는 3.6τ 신호를 2.0τ로 이동하면서 비계약형을 byte-identical하게 유지한다. 뒤 세 사례는 명시적 geometry block만 제거하고 비계약형을 유지한다. 봉인 계약상 해당 타입 신호는 measured honest envelope에 등록되지 않았으므로 closed-world Tier B이며, 영향 경로는 exact `0/NONE`이어야 한다.

산출 명령: `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section full_field_counterexamples`

## 5. 공개 P5 2,000사례 및 44건 전건 판별

공개 2,000사례를 저장 surface에서 v4/v5로 전건 재실행했다. case digest, surface digest, full snapshot, suspicion transcript 불일치가 모두 0이었다.

| 측정량 | 값 |
|---|---:|
| v4 상승 | 265 |
| v4 violation | 50 |
| v5가 차단한 v4 violation | 50 |
| v5 상승 | 44 |
| 공개 `information_limit_record` | 44 |
| 독립 증인 미성립 | 44 |
| 봉인 계약상 violation | 44 |

44건 중 수치 표면만 보면 34건은 residual 0, 10건은 `O2_class_moderate_display_stale`로 표기된 Tier-A 잔존이다. Tier-A 10건의 거리 범위는 `0.558501156205694τ..2.05457604055991τ`, per-signal floor 범위는 `0.0633778688057731..0.231043617196592`로 수치 한계 이내다. 그러나 봉인 분류는 **수치 조건과 독립 증인 조건의 논리곱**이다. 44건 모두 유일한 증인이 post 표면의 결정적 투영이므로 독립 증인이 성립하지 않고, `missing/ambiguous witness = violation` 조문에 따라 전건 (b) 계약 위반이다.

산출 명령: `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section P5_publication_and_residual_44` 및 `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section residual_44`

### Tier-A 잔존 10건

| case | 교란 | 거리 τ | floor | 판정 |
|---|---|---:|---:|---|
| `P5_0047_severe_toward_consensus` | toward_consensus | 1.77687381797499 | 0.185410379674545 | violation |
| `P5_0064_midband_toward_consensus` | toward_consensus | 0.985075310239319 | 0.091617659034391 | violation |
| `P5_0082_midband_toward_consensus` | toward_consensus | 0.918459294443116 | 0.0861791705847332 | violation |
| `P5_0190_midband_toward_consensus` | toward_consensus | 0.558501156205694 | 0.0633778688057731 | violation |
| `P5_0463_ratio_collision_collide` | collide | 1.71341618533083 | 0.175911242502027 | violation |
| `P5_0623_severe_toward_consensus` | toward_consensus | 2.05457604055991 | 0.231043617196592 | violation |
| `P5_0685_midband_toward_consensus` | toward_consensus | 0.803364492787612 | 0.077679869940486 | violation |
| `P5_1235_severe_toward_consensus` | toward_consensus | 2.03598714714723 | 0.227782432299189 | violation |
| `P5_1585_midband_toward_consensus` | toward_consensus | 0.850380678163241 | 0.0810145544998994 | violation |
| `P5_1729_midband_toward_consensus` | toward_consensus | 0.862444227358257 | 0.0819007445067326 | violation |

### residual 0인 34건

아래 각 사례도 target 증인이 post 투영이므로 violation이다.

- `remove_one` 25건: `P5_0208_midband_remove_one`, `P5_0209_severe_remove_one`, `P5_0235_midband_remove_one`, `P5_0379_midband_remove_one`, `P5_0437_missing_remove_one`, `P5_0658_midband_remove_one`, `P5_0866_severe_remove_one`, `P5_0991_midband_remove_one`, `P5_1010_severe_remove_one`, `P5_1040_missing_remove_one`, `P5_1050_mixed_remove_one`, `P5_1172_severe_remove_one`, `P5_1177_span_outlier_remove_one`, `P5_1246_ratio_collision_remove_one`, `P5_1442_severe_remove_one`, `P5_1501_span_outlier_remove_one`, `P5_1553_missing_remove_one`, `P5_1604_severe_remove_one`, `P5_1675_midband_remove_one`, `P5_1720_midband_remove_one`, `P5_1748_severe_remove_one`, `P5_1823_missing_remove_one`, `P5_1932_mixed_remove_one`, `P5_1967_missing_remove_one`, `P5_1973_severe_remove_one`.
- `unit_flip` 7건: `P5_0627_mixed_unit_flip`, `P5_0978_mixed_unit_flip`, `P5_1068_mixed_unit_flip`, `P5_1221_mixed_unit_flip`, `P5_1590_mixed_unit_flip`, `P5_1752_mixed_unit_flip`, `P5_1968_mixed_unit_flip`.
- `retype_grid` 2건: `P5_1184_missing_retype_grid`, `P5_1733_missing_retype_grid`.

각 사례의 전후 5개 추적 필드, surface digest, signal 측정, 목표 분류, 독립 판정 근거는 `seat4_work\residual_44_adjudication.json`에 전건 기록했다.

## 6. 증인·술어 구조

| 측정량 | 값 |
|---|---:|
| 상승 classification | 90 |
| upward field events | 395 |
| 18-rule transcript 완비 | 90 |
| manual suppression | 0 |
| unclassified fields | 0 |
| witness serialization = post serialization | 90 |
| post-derived parameter projection | 90 |
| digest-derived witness ID | 90 |
| 독립 지정 증인 | 0 |

`build_honest_witness`는 post의 모든 필드를 `raw_span`만 제외하고 `typed_declared_parameters`로 복사하고, 같은 `p0/p1`로 `raw_span`을 재생성한다. 하니스의 `city_semantic_legitimacy`는 `exact and tier_B_count == 0`이다. 서술 문자열은 90건 모두 동일한 기계적 문형에 case ID, digest, 개수, Tier-A JSON만 삽입한다. 따라서 구조 필드가 채워졌다는 측정과 독립 의미 증인이 성립했다는 판정은 동일하지 않다.

15개 술어의 주석 반례는 15/15 false로 실행됐다. 다만 실제 `scene_specific_witness_substantiation` 성공식은 rule list 길이 18, count-map 길이 18, `bool(nonempty narrative)`만 검사하므로 독립성·생성 서사의 의미 내용을 관측하지 않는다.

산출 명령: `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section witness_audit` 및 `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section predicate_audit`

## 7. 정직 봉투·property·replay 수치

- 정직 봉투: 400장면, 2,008앵커, 최대 ratio 편차 `1.4563237239633405e-13τ`, raw-span↔기하 mismatch 0.
- property: randomized 630 + third-fleet 11 = 641. 9 family 각각 70; strata는 105/105/105/105/210. case/surface/suspicion/v5 output mismatch 0.
- 비희석: 11사례×5 N = 55행; 재분류 0, Tier-A floor violation 0, Tier-B hard-block violation 0.
- replay: 400장면, 218,469 field row, all-version zero-delta 32,538행. union path 누락·중복 scene 0, v5 full-row rerun mismatch 0.
- v5 HIGH: 360, 그중 5% 이내 360, 정확도 비율 1.0, 최소 cohort-scale HIGH coverage 0.8.

산출 명령: `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section honest_envelope`, `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section property_audit`, `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section non_dilution_and_grid`, `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --section replay`

## 8. 디스크 산출물

| 산출물 | SHA-256 |
|---|---|
| `seat4_work\verify_l1f.py` | `4F146F78C3D3102C24307BA85C0C28C70D654F1134E7417E61B7F5F4635097D3` |
| `seat4_work\audit_results.json` | `A25FCD4D78260BE30E580793BBD5D5E9E146C2890206595318101A1DB946C644` |
| `seat4_work\independent_search_cases.json` | `DEA7C7E1A1110732412B38A6A241472B33EC05A7BC476A3DBFB20B9EB28A2DD1` |
| `seat4_work\residual_44_adjudication.json` | `C89588D31EEC49D0C5F5F4ACB69BBA4BB035E92FBF747C9490E7D446395C72B0` |
| `seat4_work\reproduction_commands.md` | `8BA942CA9A5E1AF8A5DDD07701A516BFBBA26E23D2729F9693A66A8B161512E9` |

해시 산출 명령: `Get-FileHash -Algorithm SHA256 -LiteralPath D:\runs\e2_program\chainverify_L1f\seat4_work\*`

최종 원본 무결성 재검사 명령: `python "D:\runs\e2_program\chainverify_L1f\seat4_work\verify_l1f.py" --verify-integrity`

**VERDICT: REFUTE**
