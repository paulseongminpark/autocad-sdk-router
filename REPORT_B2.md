# REPORT_B2 — AUDIT.md CHANGE_ONLY 밖 FIX 11지점 수리 (fix/ezdxf-trap-audit)

## STATUS: PASS

AUDIT.md가 확정한 FIX(out of CHANGE_ONLY scope) 11개 지점 — `tools/op_roundtrip_probe.py` 8곳(T2, #54) + `tools/e2/meta/transforms_struct.py` 3줄(T2/T3 결함 실체 동일, #54/#58/#60) — 전부 red-first 테스트와 함께 수리·커밋했다. 전체 unit 스위트는 베이스라인(1990 passed, 30 skipped) 대비 신규 실패 0(1997 passed = 1990 + 신규 테스트 7개, 30 skipped 그대로).

## 무엇을 했나

1. **op_roundtrip_probe.py 8곳 — 공용 casefold 헬퍼로 수렴.** `_layer_by_name`/`_dimstyle_by_name`/`_ucs_by_name`/`_view_by_name`/`_vport_by_name`/`_linetype_by_name`/`_textstyle_by_name`/`_block_definition_by_name` 8개 함수가 전부 동일 바디(`rec.get("name") == name`, 대소문자 구분)였다. `_find_by_name_casefold(records, name)` 공용 헬퍼를 `_load_ir_maybe` 바로 뒤에 신설하고, 8개 함수가 전부 이 헬퍼로 위임하도록 교체했다 — 반환 레코드는 실제 레코드 그대로(이름 재작성 없음), 각 함수의 기존 시그니처·반환 계약(`Optional[Dict[str, Any]]`)은 보존.
2. **transforms_struct.py 3줄 — layer_map 파이프라인 3개 이음매를 casefold로 정규화.**
   - `_collect_layer_names`(150-151행 인근): 테이블 엔트리 이름과 엔티티 리터럴 레이어 문자열을 casefold 키의 dict로 dedupe(테이블 엔트리 casing이 canonical) — 대소문자만 다른 두 문자열이 `layer_map`에서 별개 키로 등장하는 근본 원인 제거.
   - `_rename_layer_table`(177-209행 인근): `changes` 목록을 casefold 기준으로 한 번 더 dedupe(첫 등장 casing 우선) — 방어적 이중화. `_collect_layer_names`를 거치지 않고 케이스 중복 키를 가진 `layer_map`을 직접 넘기는 호출에도 안전.
   - `_remap_entity_layers`(212-224행 인근): `layer_map.get(old)`(대소문자 구분)를 casefold 키 lookup으로 교체 — 엔티티 리터럴이 `layer_map`의 키와 케이스만 다를 때 리매핑이 누락되는 결함 제거.
3. **red-first 테스트.**
   - `tests/unit/test_op_roundtrip_probe_casefold.py` 신설(4 테스트: 8개 헬퍼 전부 대소문자 무구분 조회/정확매치 회귀 없음/무관 이름 오매치 없음/중복 시 첫 매치).
   - `tests/unit/test_transforms_struct_layer_casefold.py` 신설(3 테스트: `_collect_layer_names` dedupe, `_rename_layer_table` 케이스 중복 키, `rename_layers` end-to-end 엔티티 리터럴 리매핑).
   - 수리 전 실행 결과와 수리 후 실행 결과를 아래 §"지점별 표"에 인용.
4. **전체 스위트 회귀.** `python -m pytest tests/unit -q` → 수리 후 `1997 passed, 30 skipped`(베이스라인 1990 + 신규 테스트 7개, 그 외 전부 동일) — 신규 실패 0건.
5. **AUDIT.md 판정 갱신.** T2 표의 op_roundtrip_probe.py 8행, T3 표/T2 추가발견 표의 transforms_struct.py 관련 행의 `**FIX (out of CHANGE_ONLY scope)**` 라벨을 `**FIXED**`로 교체하고 각 근거에 이 보고서 참조를 덧붙였다(라벨 교체만 — 요약 집계표 숫자는 건드리지 않음, 계약 범위 준수). 부수적으로, 이전 감사가 2043행을 "TEXTSTYLE 계열 추정"이라 적었던 오기를 코드 확인 결과(`_ucs_by_name`, UCS 테이블)로 정정했다.

## 지점별 표 (수리 위치 · red 증거 · green 증거)

| 파일:줄 | 수리 위치 | red 증거 (수리 전) | green 증거 (수리 후) |
|---|---|---|---|
| tools/op_roundtrip_probe.py:1544 (`_layer_by_name`) | `_find_by_name_casefold`로 위임 | `test_op_roundtrip_probe_casefold.py::test_all_eight_helpers_find_a_differently_cased_query` → `AssertionError: unexpectedly None : _layer_by_name: stored name 'WALL' not found by query 'wall' ...` | 동일 테스트 재실행 → `4 passed`(subTest 전부 포함) |
| tools/op_roundtrip_probe.py:1813 (`_dimstyle_by_name`) | 〃 | 위와 동일 스위트, `helper=_dimstyle_by_name` subTest | 〃 |
| tools/op_roundtrip_probe.py:2043 (`_ucs_by_name`) | 〃 | 〃, `helper=_ucs_by_name` subTest | 〃 |
| tools/op_roundtrip_probe.py:2275 (`_view_by_name`) | 〃 | 〃, `helper=_view_by_name` subTest | 〃 |
| tools/op_roundtrip_probe.py:2493 (`_vport_by_name`) | 〃 | 〃, `helper=_vport_by_name` subTest | 〃 |
| tools/op_roundtrip_probe.py:2724 (`_linetype_by_name`) | 〃 | 〃, `helper=_linetype_by_name` subTest | 〃 |
| tools/op_roundtrip_probe.py:2957 (`_textstyle_by_name`) | 〃 | 〃, `helper=_textstyle_by_name` subTest | 〃 |
| tools/op_roundtrip_probe.py:3378 (`_block_definition_by_name`) | 〃 | 〃, `helper=_block_definition_by_name` subTest | 〃 |
| tools/e2/meta/transforms_struct.py:151 (`_collect_layer_names`) | casefold dedupe(canonical dict) | `test_transforms_struct_layer_casefold.py::test_table_entry_and_entity_literal_differing_only_in_case_collapse` → `AssertionError: 2 != 1 : 'WALL' (table) and 'wall' (entity literal) ... : ['0', 'Defpoints', 'WALL', 'wall']` | 동일 테스트 재실행 → `3 passed` |
| tools/e2/meta/transforms_struct.py:183(수리 전) → `_rename_layer_table`(수리 후 187행부터) | casefold 기준 `changes` dedupe | `test_case_duplicate_layer_map_keys_apply_once_without_exception` → `ezdxf.lldxf.const.DXFTableEntryError: wall`(`doc.layers.duplicate_entry(old, tmp)`에서 발생, 이 세션에서 직접 재현 확인) | 〃 |
| tools/e2/meta/transforms_struct.py:219(수리 전) → `_remap_entity_layers`(수리 후 232행부터) | casefold lookup dict | `test_entity_literal_case_variant_still_remapped` → 동일 `DXFTableEntryError`(엔드투엔드 `rename_layers` 경로에서 재현, `_rename_layer_table` 호출 스택) | 〃 |

부가 확인: 수리 후 `tools/e2/meta/transforms_struct.py`의 기존 `run_selftest()`(explode/anonymize/shuffle) 재실행 → `S5-B transforms_struct selftest ALL PASS`(회귀 없음).

## 전체 스위트 결과

```
$ python -m pytest tests/unit -q --basetemp="$env:TEMP\pytest-b2" -p no:cacheprovider
1997 passed, 30 skipped, 7 warnings in 45.02s
```

베이스라인(오케스트레이터 확인) `1990 passed, 30 skipped` 대비 `+7`(신규 테스트 파일 2개, 4+3 테스트) — 신규 실패 0건. 7개 경고는 ezdxf 자체의 `pyparsing` deprecation 경고로 이 패킷과 무관(수리 전에도 동일하게 발생).

## 커밋

`<PENDING — 이 커밋 직후 기록>`

## 검증 (VALIDATION 항목별)

- PowerShell pytest 결과: 위 §"전체 스위트 결과" 인용.
- `git log --oneline -5`: 아래 §"커밋" 갱신 커밋에서 확인.

## 건너뛴 것 / 확장하지 않은 것

- AUDIT.md 요약(집계) 표의 숫자(FIX/SAFE/UNKNOWN 카운트)는 계약이 허용한 범위("FIX(out of scope) 라벨 교체만")를 지키기 위해 갱신하지 않았다 — 개별 판정 행의 라벨만 FIXED로 바꿨다. 집계표 재계산이 필요하면 별도 승인 후 진행한다.
- `_rename_layer_table`의 casefold dedupe는 `_collect_layer_names`가 이미 정규화한 정상 경로에서는 사실상 no-op이지만, 외부 호출자가 직접 케이스 중복 `layer_map`을 넘기는 경로까지 방어하도록 의도적으로 이중 배치했다 — 과설계가 아니라 red 테스트가 요구한 계약(§BUNDLE 항목 2)이다.
