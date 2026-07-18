# Feyerabend C1 — Anchor scale estimation and confidence calibration

## 실행 계약과 설계

- 입력: `D:\runs\e2_program\cells\feyerabend_c0\scenes`의 C0 IR 200개, base seed 50개.
- estimator 경계: `anchor_artifact_from_scene`은 `anchors` 키 하나만 읽고, `fit_anchor_model`은 anchor sequence만 인자로 받는다. `truth_unit_scale`은 추정 뒤 오차 계산에만 사용했다.
- scale 추정: DIM/TEXT의 `display_value / geometric_span` log-ratio에서 `log(1.05)` 최대 가중 합의군을 고르고 Huber location(delta 1.5)을 계산했다.
- confidence: dossier의 consensus × exp(-logMAD/tau) × min(1,n/5) × min(1,spatial_bins/3), HIGH threshold 0.75를 그대로 사용했다. C1의 primary confidence bin은 `unit_status`다.
- corruption: 모든 200 IR에 duplicate, stale override(한 표시값 ×2), suffix removal(명시 suffix 전부 제거), single outlier(독립 표시값 ×10) 네 종류를 각각 적용했다. 별도로 `sha256(base_scene_id) mod 4` 배정도 기록했다.
- pair-label permutation은 `truth_pairs`의 label payload를 회전·재표기한 뒤 동일 anchor artifact를 다시 산출했다.
- 합격선 또는 셀/theory 판정은 산출하지 않았다.

## Selftest 전문

```text
SELFTEST exact_anchor_exact_scale: PASS | estimate=2.5 expected=2.5 unit_status=HIGH
SELFTEST exact_anchor_high_confidence: PASS | unit_status=HIGH confidence=1
SELFTEST no_anchor_honest_no_estimate: PASS | estimate=None unit_status=NONE status=NONE
SELFTEST corruption_reproducibility: PASS | duplicate=b7eafb24bff4 stale_override=4587fb707ef7 suffix_removal=d5721ef40250 single_outlier=802397c8b4a3
SELFTEST single_outlier_mode_or_downgrade: PASS | estimate=2.5 unit_status=HIGH
SELFTEST truth_key_access_guard: PASS | accessed_keys=['anchors']
SELFTEST SUMMARY: 6/6 passed
```

## 입력 및 실행 수치

| metric | value |
| --- | --- |
| scene_count | 200 |
| base_scene_count | 50 |
| seed_count | 50 |
| input_manifest_digest_before | be0e68b21fb0d201cdbeaf7b44f00da439b61393cc9cbb522486205fe7df67e1 |
| input_manifest_digest_after | be0e68b21fb0d201cdbeaf7b44f00da439b61393cc9cbb522486205fe7df67e1 |
| input_manifest_mismatch_count | 0 |
| elapsed_cpu_seconds | 0.953125 |
| elapsed_wall_seconds | 0.990569200003 |

## 전체 scale 추정 수치

| metric | value |
| --- | --- |
| estimate_count | 200 |
| estimate_coverage | 1 |
| accuracy_within_5pct | 1 |
| HIGH_scene_count | 0 |
| HIGH_coverage | 0 |
| HIGH_accuracy_within_5pct | null |
| e_s_min | 0 |
| e_s_median | 2.22044604925e-16 |
| e_s_p95 | 4.4408920985e-16 |
| e_s_max | 4.4408920985e-16 |
| relative_error_min | 0 |
| relative_error_median | 2.22044604925e-16 |
| relative_error_p95 | 4.4408920985e-16 |
| relative_error_max | 4.4408920985e-16 |

## Scale × confidence 전 행

| kappa | unit_status | n | fraction | n_est | accuracy_5pct | e_s_med | e_s_p95 | relerr_med | relerr_p95 | conf_med |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.001 | HIGH | 0 | 0 | 0 | null | null | null | null | null | null |
| 0.001 | LOW | 50 | 1 | 50 | 1 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 | 0.6 |
| 0.001 | NONE | 0 | 0 | 0 | null | null | null | null | null | null |
| 0.01 | HIGH | 0 | 0 | 0 | null | null | null | null | null | null |
| 0.01 | LOW | 50 | 1 | 50 | 1 | 4.4408920985e-16 | 4.4408920985e-16 | 4.4408920985e-16 | 4.4408920985e-16 | 0.6 |
| 0.01 | NONE | 0 | 0 | 0 | null | null | null | null | null | null |
| 1 | HIGH | 0 | 0 | 0 | null | null | null | null | null | null |
| 1 | LOW | 50 | 1 | 50 | 1 | 0 | 0 | 0 | 0 | 0.6 |
| 1 | NONE | 0 | 0 | 0 | null | null | null | null | null | null |
| 1000 | HIGH | 0 | 0 | 0 | null | null | null | null | null | null |
| 1000 | LOW | 50 | 1 | 50 | 1 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 | 2.22044604925e-16 | 0.6 |
| 1000 | NONE | 0 | 0 | 0 | null | null | null | null | null | null |

## Numeric confidence-score bin별 accuracy

| scale | score_bin | n | n_est | accuracy_5pct | relerr_med | relerr_p95 |
| --- | --- | --- | --- | --- | --- | --- |
| ALL | [0.00,0.25) | 0 | 0 | null | null | null |
| ALL | [0.25,0.50) | 0 | 0 | null | null | null |
| ALL | [0.50,0.75) | 200 | 200 | 1 | 2.22044604925e-16 | 4.4408920985e-16 |
| ALL | [0.75,1.00] | 0 | 0 | null | null | null |
| 0.001 | [0.00,0.25) | 0 | 0 | null | null | null |
| 0.001 | [0.25,0.50) | 0 | 0 | null | null | null |
| 0.001 | [0.50,0.75) | 50 | 50 | 1 | 2.22044604925e-16 | 2.22044604925e-16 |
| 0.001 | [0.75,1.00] | 0 | 0 | null | null | null |
| 0.01 | [0.00,0.25) | 0 | 0 | null | null | null |
| 0.01 | [0.25,0.50) | 0 | 0 | null | null | null |
| 0.01 | [0.50,0.75) | 50 | 50 | 1 | 4.4408920985e-16 | 4.4408920985e-16 |
| 0.01 | [0.75,1.00] | 0 | 0 | null | null | null |
| 1 | [0.00,0.25) | 0 | 0 | null | null | null |
| 1 | [0.25,0.50) | 0 | 0 | null | null | null |
| 1 | [0.50,0.75) | 50 | 50 | 1 | 0 | 0 |
| 1 | [0.75,1.00] | 0 | 0 | null | null | null |
| 1000 | [0.00,0.25) | 0 | 0 | null | null | null |
| 1000 | [0.25,0.50) | 0 | 0 | null | null | null |
| 1000 | [0.50,0.75) | 50 | 50 | 1 | 2.22044604925e-16 | 2.22044604925e-16 |
| 1000 | [0.75,1.00] | 0 | 0 | null | null | null |

## Corruption 전후 수치

| corruption | n | unit_transition | overall_transition | scale_same | scale_changed | relerr_med | relerr_p95 | conf_after_med |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| duplicate | 200 | {"LOW->LOW": 200} | {"LOW->LOW": 200} | 200 | 0 | 2.22044604925e-16 | 4.4408920985e-16 | 0.6 |
| stale_override | 200 | {"LOW->LOW": 200} | {"LOW->LOW": 200} | 200 | 0 | 2.22044604925e-16 | 4.4408920985e-16 | 0.177777777778 |
| suffix_removal | 200 | {"LOW->LOW": 200} | {"LOW->LOW": 200} | 200 | 0 | 2.22044604925e-16 | 4.4408920985e-16 | 0.6 |
| single_outlier | 200 | {"LOW->LOW": 200} | {"LOW->HIGH": 26, "LOW->LOW": 174} | 200 | 0 | 2.22044604925e-16 | 4.4408920985e-16 | 0.45 |

### Hash-assigned corruption 분포

| corruption | scene_count | base_scene_count | unit_transitions |
| --- | --- | --- | --- |
| duplicate | 44 | 11 | {"LOW->LOW": 44} |
| stale_override | 56 | 14 | {"LOW->LOW": 56} |
| suffix_removal | 52 | 13 | {"LOW->LOW": 52} |
| single_outlier | 48 | 12 | {"LOW->LOW": 48} |

## Pair-label permutation digest 수치

| metric | value |
| --- | --- |
| scene_count | 200 |
| pair_label_changed_scene_count | 196 |
| matching_anchor_artifact_scene_count | 200 |
| mismatching_anchor_artifact_scene_count | 0 |
| anchor_artifact_match_rate | 1 |
| global_anchor_artifact_digest_before | f601bf1bbb7179c622eab3173f72593e9d8c2fa9f64cc014b1a8d11e3f324b49 |
| global_anchor_artifact_digest_after | f601bf1bbb7179c622eab3173f72593e9d8c2fa9f64cc014b1a8d11e3f324b49 |

## 산출물 검증 수치

| artifact | status | bytes | sha256 |
| --- | --- | --- | --- |
| results.json | GENERATED | 1314502 | 6d792e4a722859cc12df300c7bc804ee257e0f8b2caa8c2518a95f491f9b4186 |
| evidence.xlsx | GENERATED | 11609 | e7e631369dab1c7c2dcc840c68376cce551afca09f87f1990e835fb6fc4649a4 |

## 미해결

- dossier confidence 식의 `min(1,n/5)` 항 때문에 C0의 독립 DIM ratio anchor 3개는 완전 합의·zero MAD에서도 confidence 0.60이며 HIGH threshold 0.75에 닿지 않는다. HIGH subset 수치가 비어 있으면 null로 보존했다.
- C0 IR은 parser 이전의 정규화된 anchor schema다. stale override와 suffix 제거 diagnostic은 각각 `display_value` 및 `display_unit` 정규화 필드에서 deterministic mutation으로 구현했다.
- single-outlier diagnostic에서 scale estimate는 200/200 동일했고 unit_status도 200/200 LOW 유지였지만, 추가 anchor의 geometry span이 reference 독립성 수를 늘려 reference/overall status가 26/200에서 LOW→HIGH로 변했다. 이 transition은 수치 그대로 보존했다.
- 첫 full-process 시도는 200-scene 계산 뒤 nested distribution을 Excel cell로 직렬화하는 단계에서 중단됐다. estimator/config/metric은 바꾸지 않고 workbook 행만 평탄화한 뒤 동일 deterministic 평가를 재실행했다.
- 첫 successful export의 독립 검증에서 `results.json` 안의 self-hash가 final rewrite 전 값을 가리키는 순환 manifest 문제가 발견됐다. 수치 계산은 바꾸지 않고 finalized results를 REPORT가 단방향으로 hash하도록 export finalization만 수정했다.
- packet을 처음 읽기 위한 병렬 진단에 read-only `git status`가 잘못 포함되었고, target cell이 아닌 기본 `D:\dev`에서 `not a git repository`로 종료했다. Git 상태와 파일은 바뀌지 않았으며 packet 확인 뒤 Git 명령을 다시 실행하지 않았다.
- 이 셀은 수치와 진단만 산출하며 제안 합격선, C2 개방 여부, reigning/counter theory 판정을 출력하지 않는다.

CELL_COMPLETE: feyerabend_c1
