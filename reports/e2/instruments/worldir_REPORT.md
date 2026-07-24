# World-IR / INSERT transform oracle 빌드 보고서

## 판정

`worldir_oracle.py --selftest` 결과는 **PASS (26/26)** 다. 정상 transform case는 hand-authored world endpoint와 역변환 local endpoint를 모두 대조했고, malformed case는 빈 primary output과 명시적 failure code를 요구했다. 아래 PASS는 검사를 우회했다는 뜻이 아니라, 정상 입력은 정확히 전개되고 비정상 입력은 의도대로 fail-closed 됐다는 뜻이다.

## 구현 요약

- Python 3.12, stdlib + NumPy만 사용한다.
- 두 입력 형태를 받는다.
  - canonical definition graph: `root` + `definitions` + stable handles + primitive/INSERT entities
  - flat `seg.v1` 계열: `segments`를 이미 world-coordinate인 modelspace primitive로 감사
- column-vector 규약으로 `T_child_world = T_parent_world @ T_insert_local @ T_array_cell`을 적용한다.
- parser가 제공하는 `local_matrix`를 우선 사용한다. 없을 때 canonical JSON component fields를 `T(insert) @ R @ S @ T(-target_base)`로 합성한다.
- nested INSERT, 2D reflection, rotation, uniform/nonuniform scale, target base point, row/column array를 전개한다.
- endpoint는 float64 world 좌표에서 lexicographic canonicalization 한다.
- determinant와 singular value로 `mirrored`, `nonuniform_scaled`, `array_member` flags를 기록한다.
- cycle, missing target, non-finite/singular transform, unsupported extrusion/entity, degenerate/non-finite geometry, resource limit, silent drop은 모두 `status=FAIL`과 빈 primary `segments`를 낸다. 앞에서 만들어진 partial segment도 PASS 산출물로 노출하지 않는다.

## 보존 원장

`conservation_ledger`는 다음을 별도로 기록한다.

- 전체 definition의 input entity template 수와 primitive/INSERT 분해 수
- 실제 도달한 primitive entity instance 및 INSERT placement 수
- primitive별 독립 count contract가 요구한 segment 수
- 실제 normalizer와 transform 단계가 방출한 segment 수
- empty definition placement의 명시적 zero-output entry
- partial failure 시 폐기한 segment 수
- `expected_segment_instances - emitted_segment_instances`와 `conservation_ok`

배열, 반복 placement, polyline 분해 때문에 raw input entity template 수와 output segment 수는 일반적으로 같지 않다. 따라서 각 reachable primitive instance별 expected/emitted balance를 만들고 이를 전체 원장으로 합산한다. `_emitter` fault injection selftest는 LINE 1개를 0개로 방출하게 만들어 `SILENT_DROP`이 실제로 FAIL-CLOSED 되는지 검증한다.

## Lineage

식별자는 길이-prefix UTF-8 field의 SHA-256이다.

```text
root_uid   = H("MODELSPACE_ROOT", root_def_handle)
child_uid  = H(parent_uid, insert_handle, target_def_handle, row, column)
placed_uid = H(child_uid, source_entity_handle, subentity_ordinal)
```

각 segment에는 `placed_uid`, 동일값의 명시적 `lineage_id`, `root_def_handle`, `source_def_handle`, `source_entity_handle`, `placement_path_uid`, 전체 `lineage_path`, `subentity_ordinal`이 있다. block/layer name, label, entity order는 hash 입력이 아니다. rename 및 reorder parity를 selftest로 확인했다.

## CLI

```text
py -3.12 worldir_oracle.py --selftest
py -3.12 worldir_oracle.py input.json
py -3.12 worldir_oracle.py input.json --output expanded.json
```

정상 확장은 exit code 0, fail-closed 결과는 exit code 1, CLI/input I/O 오류는 exit code 2다.

## Selftest 결과 전문

실행 명령:

```text
py -3.12 -I D:\runs\e2_program\build\worldir\worldir_oracle.py --selftest
```

출력:

```text
WORLDIR ORACLE SELFTEST
oracle=worldir.oracle.v1
python=3.12.10 numpy=1.26.4
coordinate_contract=column-vector T_parent @ T_insert_local @ T_array_cell
normal_tolerance=1e-9 * max(1, fixture_extent)
----------------------------------------------------------------------------------------
[PASS] identity_modelspace: n=1 max_error=0.000e+00 inverse_error=0.000e+00 tol=4.000e-09 conservation=1/1
[PASS] translation: n=1 max_error=0.000e+00 inverse_error=0.000e+00 tol=4.000e-09 conservation=1/1
[PASS] rotation_90: n=1 max_error=1.837e-16 inverse_error=1.837e-16 tol=2.000e-09 conservation=1/1
[PASS] uniform_scale: n=1 max_error=0.000e+00 inverse_error=0.000e+00 tol=4.000e-09 conservation=1/1
[PASS] rotation_nonuniform_scale: n=1 max_error=1.776e-15 inverse_error=8.882e-16 tol=1.200e-08 conservation=1/1 nonuniform_flag=true
[PASS] reflection: n=1 max_error=0.000e+00 inverse_error=0.000e+00 tol=2.000e-09 conservation=1/1 mirrored_flag=true
[PASS] nested_depth_2: n=1 max_error=0.000e+00 inverse_error=0.000e+00 tol=1.000e-09 conservation=1/1 path_depth=2
[PASS] nested_depth_3: n=1 max_error=0.000e+00 inverse_error=0.000e+00 tol=1.000e-09 conservation=1/1 path_depth=3
[PASS] array_2x3: n=6 max_error=0.000e+00 inverse_error=0.000e+00 tol=1.100e-08 conservation=6/6 array_flags=true
[PASS] target_base_point: n=1 max_error=0.000e+00 inverse_error=0.000e+00 tol=3.000e-09 conservation=1/1
[PASS] child_modelspace_combination: n=2 max_error=0.000e+00 inverse_error=0.000e+00 tol=5.000e-09 conservation=2/2
[PASS] parser_local_matrix: n=1 max_error=0.000e+00 inverse_error=0.000e+00 tol=6.000e-09 conservation=1/1
[PASS] arc_chord_normalization: n=1 max_error=2.220e-16 inverse_error=1.110e-16 tol=4.000e-09 conservation=1/1
[PASS] polyline_subentity_ordinals: n=3 max_error=0.000e+00 inverse_error=0.000e+00 tol=2.000e-09 conservation=3/3 ordinals=0,1,2
[PASS] repeated_placement_unique_lineage: n=2 max_error=0.000e+00 inverse_error=0.000e+00 tol=1.100e-08 conservation=2/2 lineage_ids_unique=2
[PASS] nested_array_composition: n=2 max_error=0.000e+00 inverse_error=0.000e+00 tol=8.000e-09 conservation=2/2
[PASS] flat_seg_ir_input: n=1 max_error=0.000e+00 inverse_error=0.000e+00 tol=4.000e-09 conservation=1/1 input_mode=flat_seg_ir
[PASS] transform_name_rename_parity: status_a=PASS status_b=PASS segment_parity=True
[PASS] entity_reorder_determinism: status_a=PASS status_b=PASS segment_parity=True
[PASS] degenerate_fail_closed: status=FAIL codes=['DEGENERATE_GEOMETRY'] output_segments=0 discarded=0
[PASS] empty_block_audited: status=PASS empty_placements=1 zero_entries=1
[PASS] cycle_reference_defense: status=FAIL codes=['GRAPH_CYCLE'] output_segments=0 discarded=0
[PASS] missing_target_fail_closed: status=FAIL codes=['MISSING_TARGET'] output_segments=0 discarded=0
[PASS] singular_transform_fail_closed: status=FAIL codes=['SINGULAR_TRANSFORM'] output_segments=0 discarded=0
[PASS] nonfinite_geometry_fail_closed: status=FAIL codes=['NONFINITE_GEOMETRY'] output_segments=0 discarded=0
[PASS] silent_drop_detector: status=FAIL codes=['SILENT_DROP'] output_segments=0 discarded=0
----------------------------------------------------------------------------------------
SUMMARY: 26/26 cases passed
SELFTEST_RESULT: PASS
```

## 추가 검증

- `py -3.12 -m py_compile worldir_oracle.py`: PASS
- isolated mode selftest 2회 exit code: `0`, `0`
- 첫 isolated run wall time: 236 ms
- 두 selftest 출력 byte sequence 동일: `True`
- selftest output SHA-256 (양쪽 동일): `10f37ac29959d50c46dad6b6122254de15f5a94e0bd03b58c27be2c9c0de176f`
- `worldir_oracle.py` SHA-256: `f49417843726413667ead2be2b1e249100ddbce961d67a4d6f3600de78550a18`
- import audit: `argparse, copy, dataclasses, hashlib, json, math, pathlib, platform, sys, typing, numpy`; third-party dependency는 NumPy 하나다.

## 스펙 원문과의 대응

- `feyerabend_P6.md` §2.3: handle/array-index 기반 length-prefixed SHA-256 lineage를 구현했다.
- §2.4: column-vector 누적 transform, reflection/nonuniform flags, array cell, path-local cycle 방어, max depth/instance fail-closed를 구현했다.
- §2.5: LINE, polyline edge, ARC chord endpoint 정규화, stable subentity ordinal, zero-length/non-finite 방어를 구현했다.
- §5.3 M1/M2와 §6.2 C0: graph integrity 및 hand-computed endpoint/inverse oracle을 고정 26 case로 실행했다. 패킷의 최소 8 case와 dossier의 고정 24 case 수를 모두 넘는다.
- `platt_P2.md` G1 자격 gate 중 transform parity, name-rename parity, deterministic build를 selftest에 넣었다.

## 차이와 미해결 항목

1. 이 산출물은 raw DXF를 직접 읽지 않는다. packet의 `stdlib+numpy` 제한 때문에 `ezdxf`를 의존하지 않으며, DXF parser 산출은 canonical definition-graph JSON과 parser-supplied `local_matrix`를 통해 받는다. non-default extrusion은 `local_matrix`가 없으면 fail-closed다.
2. flat SEG-IR은 이미 전개된 world geometry이므로 잃어버린 INSERT graph를 역구성하지 않는다. root lineage와 segment 보존만 감사한다.
3. primitive coverage는 LINE/SEGMENT, LWPOLYLINE/POLYLINE edge, ARC chord다. 기타 primitive는 조용히 버리지 않고 `UNSUPPORTED_ENTITY`로 fail-closed한다.
4. P2 G1의 exhaustive positive relation recall은 candidate adjacency builder의 gate다. 이 packet은 transform oracle만 만들기 때문에 relation graph를 생성하거나 recall ≥ 0.995를 주장하지 않는다.
5. `unit_mm`, world-pair predicate, downstream fast_score 및 실제 corpus probe는 이 계측기 범위 밖이다. 여기서의 PASS를 semantic wall-system PASS로 승격하지 않는다.

BUILD_COMPLETE: worldir
