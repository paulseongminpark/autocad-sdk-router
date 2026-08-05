# ezdxf / 심볼테이블 함정 전수 감사 (fix/ezdxf-trap-audit)

- 대상: repo 자체 Python 코드 (`tools/**/*.py`) — `src/`(ObjectARX 네이티브)는 ezdxf를 쓰지 않으므로 모집단 밖.
- 함정 4종: T1(#49) add_wipeout layer 무시 · T2(#54) 심볼테이블 이름 대소문자 구분 비교 · T3(#58/#60) ezdxf 테이블 조회 무구분 특성/선생성 항목 충돌 · T4(#57) 정렬 TEXT bbox 비교 오탐.
- 방법: 아래 각 rg 명령의 매치 수를 모집단으로 잡고, 표는 그 매치를 전부 인용한다(파일별로 묶되 인용된 줄 번호 총합이 모집단 수와 일치). CHANGE_ONLY 밖 파일에서 나온 FIX는 **이 레인에서 수리하지 않는다** — 발견만 기록.

## T1 — `add_wipeout` layer 무시 (#49)

```
$ rg 'add_wipeout\(' -g '*.py'
tools\e2\gen2\gen2.py:491
```
모집단 = 1. 실측(이 세션, ezdxf 1.4.3 설치본):

```python
>>> w = msp.add_wipeout([...], dxfattribs={'layer':'PROFILE-FILL'})
>>> w.dxf.layer
'0'
```
근본 원인: `ezdxf.entities.image.Wipeout.set_masking_area()`가
`self.update_dxf_attribs(self.DEFAULT_ATTRIBS)`를 호출하는데 `DEFAULT_ATTRIBS = {"layer": "0", ...}`다.
`add_wipeout()`은 `new_entity(dxfattribs=dxfattribs)`로 엔티티를 올바른 layer로 먼저 만들지만,
바로 이어서 호출하는 `set_masking_area()`가 그 layer를 `"0"`으로 덮어쓴다 — dxfattribs로는 절대 우회 불가.

| 파일:줄 | 판정 | 근거 |
|---|---|---|
| tools/e2/gen2/gen2.py:491 | **FIX** | `_add_profile_entity`는 모든 필러 엔티티를 `layer="PROFILE-FILL"`에 배치하려는 의도(96행 `LAYER_COLORS["PROFILE-FILL"]`, 450행 `layer = "PROFILE-FILL"`)이지만 WIPEOUT만 위 근본원인으로 실제로는 layer `"0"`에 생성됨 — CHANGE_ONLY 안, 수리 대상. |

## T3 — ezdxf 테이블 조회(무구분 특성) / 선생성 항목 충돌 (#58 #60)

```
$ rg '\bdoc\.(layers|styles|linetypes|dimstyles)\b' tools -g '*.py'
tools\e2\gen2\gen2.py: 2 (134,135)
tools\e2\s2_fidelity.py: 2 (320,321)
tools\e2\s2_pack_cli.py: 2 (206,207)
tools\e2\meta\transforms_struct.py: 15 (150,183,192,194,195,199,202,204,205,208,209,283,284,285,286)
tools\e2\synth\noise.py: 2 (56,57)
tools\e2\synth\grammar.py: 2 (264,265)
tools\e2\synth\openings.py: 2 (429,430)
```
모집단 = 27 (7 파일). ezdxf 내부 실측: `Table.has_entry`/`__contains__`는 `validator.make_table_key = name.lower()`로 무구분 비교한다(이 세션에서 `inspect.getsource`로 확인).

| 파일 | 줄 | 판정 | 근거 |
|---|---|---|---|
| tools/e2/gen2/gen2.py | 134-135 | SAFE | `if name not in doc.layers: doc.layers.add(name,...)` — 검사와 생성이 같은 변수, 같은 ezdxf 무구분 의미론을 그대로 씀(idempotent create). 케이스 불일치 발생 여지 없음. CHANGE_ONLY 안. |
| tools/e2/s2_fidelity.py | 320-321 | SAFE | 동일 idempotent-create 패턴. CHANGE_ONLY 밖(참고용). |
| tools/e2/s2_pack_cli.py | 206-207 | SAFE | 동일 idempotent-create 패턴. CHANGE_ONLY 밖. |
| tools/e2/synth/noise.py | 56-57 | SAFE | 동일 패턴(`doc.layers.new`). CHANGE_ONLY 밖. |
| tools/e2/synth/grammar.py | 264-265 | SAFE | 동일 패턴. CHANGE_ONLY 밖. |
| tools/e2/synth/openings.py | 429-430 | SAFE | 동일 패턴. CHANGE_ONLY 밖. |
| tools/e2/meta/transforms_struct.py | 150,183,192,194,195,199,202,204,205,208,209,283-286 | **FIXED** | `_rename_layer_table`이 `doc.layers.has_entry()`(무구분)로 `changes` 목록을 거르지만, 그 `changes`는 대소문자만 다른 두 이름을 **서로 다른 실제 레이어**인 것처럼 담을 수 있는 `layer_map`(파이썬 dict, 대소문자 구분)에서 왔다 — 아래 T2 실측 참고. 같은 실제 레이어를 두 번 처리하려다 두 번째 `duplicate_entry`/`remove` 호출이 이미 지워진 항목을 찾다가 실패한다. B2 패킷(REPORT_B2.md)에서 수리: `_collect_layer_names`를 casefold 무구분 dedupe로, `_rename_layer_table`을 casefold 기준 changes dedupe로, `_remap_entity_layers`를 casefold lookup으로 교체 — red 재현(`ezdxf.DXFTableEntryError: wall`)과 green 둘 다 테스트로 고정. |

## T2 — 심볼테이블 이름의 대소문자 구분 비교 (#54)

```
$ rg '\.get\("name"\)\s*==\s*name' -g '*.py'
tools\op_roundtrip_probe.py: 8 (1544,1813,2043,2275,2493,2724,2957,3378)
```
모집단(1차) = 8, 전부 `op_roundtrip_probe.py` 한 파일. `_layer_by_name`/`_dimstyle_by_name`/`_linetype_by_name`/`_textstyle_by_name`/`_ucs_by_name`/`_view_by_name`/`_vport_by_name`(+1) 전부 동일 바디:
```python
if isinstance(rec, dict) and rec.get("name") == name:
```

| 파일:줄 | 판정 | 근거 |
|---|---|---|
| tools/op_roundtrip_probe.py:1544 (`_layer_by_name`) | **FIXED** | AutoCAD/DXF 레이어 이름은 대소문자 무구분 유일이다. `create_layer(name="wall")`이 기존 `"WALL"`을 upsert하면(네이티브 심볼테이블도 무구분) post_ir의 실제 레코드 이름은 그대로 `"WALL"`인데 `== "wall"` 비교가 실패해 "찾지 못함"(`STATUS_HOLLOW`)으로 오판 — 성공한 upsert를 실패로 보고하는 실참조 오판. B2 패킷에서 공용 헬퍼 `_find_by_name_casefold`로 수리(REPORT_B2.md). |
| tools/op_roundtrip_probe.py:1813 (`_dimstyle_by_name`) | **FIXED** | 위와 동일 패턴, DIMSTYLE 테이블 대상. `_find_by_name_casefold`로 수리. |
| tools/op_roundtrip_probe.py:2043 (`_ucs_by_name` — 정정: 이전 판정의 "TEXTSTYLE 계열 추정"은 오기, 코드 확인 결과 UCS 테이블) | **FIXED** | 위와 동일 패턴, UCS 테이블 대상. `_find_by_name_casefold`로 수리. |
| tools/op_roundtrip_probe.py:2275 (`_view_by_name`) | **FIXED** | 위와 동일 패턴, VIEW 테이블 대상. `_find_by_name_casefold`로 수리. |
| tools/op_roundtrip_probe.py:2493 (`_vport_by_name`) | **FIXED** | 위와 동일 패턴, VPORT 테이블 대상. `_find_by_name_casefold`로 수리. |
| tools/op_roundtrip_probe.py:2724 (`_linetype_by_name`) | **FIXED** | 위와 동일 패턴, LINETYPE 테이블 대상(코드 확인 완료 — docstring이 `_layer_by_name` 미러라고 명시). `_find_by_name_casefold`로 수리. |
| tools/op_roundtrip_probe.py:2957 (`_textstyle_by_name`) | **FIXED** | 위와 동일 패턴, TEXTSTYLE 테이블 대상. `_find_by_name_casefold`로 수리. |
| tools/op_roundtrip_probe.py:3378 (`_block_definition_by_name`) | **FIXED** | 위와 동일 패턴, BLOCK 테이블 대상. `_find_by_name_casefold`로 수리. |

`tools/op_roundtrip_probe.py` 8건 전부 B2 패킷에서 수리 완료(REPORT_B2.md) — red(`tests/unit/test_op_roundtrip_probe_casefold.py`, 수리 전 대소문자 조회 실패)와 green(수리 후) 둘 다 인용.

추가 수동 발견(같은 함정, 다른 코드 모양이라 위 rg 패턴에 안 걸림):

```
$ rg 'layer_map\[|layer_map\.get\(|names\.add\(|old != new' tools -g '*.py'
tools\blockdef_diff.py:771       matched_b_names.add(b_name)
tools\ir_to_patch.py:67          reserved_names.add(name)
tools\ir_to_patch.py:82          reserved_names.add(clone_name)
tools\e2\meta\transforms_struct.py:151   names.add(str(layer.dxf.name))
tools\e2\meta\transforms_struct.py:156   names.add(str(e.dxf.layer))
tools\e2\meta\transforms_struct.py:183   (T3 표에 이미 인용)
tools\e2\meta\transforms_struct.py:219   new = layer_map.get(old)
```
모집단(2차) = 6 (위 표의 183은 중복 계상하지 않음).

| 파일:줄 | 판정 | 근거 |
|---|---|---|
| tools/e2/meta/transforms_struct.py:151,156,219 | **FIXED (T3 표 항목과 동일 결함, 함께 수리)** | 실측(이 세션): 같은 파일을 저장 후 재로드하면 테이블 엔트리 이름(`'WALL'`)과 그 레이어를 참조하는 엔티티의 리터럴 문자열(`'wall'`)은 서로 다른 케이스로 **독립 보존**된다 (`ezdxf.readfile` 실측: `doc2.layers`엔 `'WALL'`, `e.dxf.layer`엔 `'wall'`). `_collect_layer_names`가 이 둘을 파이썬 `set`(대소문자 구분)에 같이 넣으므로 실제로는 하나뿐인 레이어가 `layer_map`에서 두 개의 다른 키로 등장할 수 있다 → `_rename_layer_table`이 같은 레코드를 두 번 처리(위 T3 항목). B2 패킷에서 수리: 151/156을 casefold dedupe로, 219(`_remap_entity_layers`)를 casefold lookup으로 교체(REPORT_B2.md). |
| tools/ir_to_patch.py:67,82 (`reserved_names`) | SAFE | 블록 테이블은 ezdxf가 아니라 네이티브 IR JSON에서 온 이름만 다루고, 새 이름은 `"ARIADNE_ANON_"` 전용 네임스페이스에 접미사를 붙여 생성한다 — 원본 도면이 이 네임스페이스와 대소문자만 다른 이름을 이미 갖고 있어야 충돌하는, 사실상 도달 불가능한 경로. CHANGE_ONLY 밖이기도 함. |
| tools/blockdef_diff.py:771 (`matched_b_names`) | SAFE | 두 IR(before/after) 모두 같은 네이티브 추출 파이프라인 산출물이라 소스가 섞이지 않음(ezdxf 무구분 테이블과 파이썬 구조체를 섞는 T2/T3의 전제 자체가 없음). CHANGE_ONLY 밖. |

## T4 — 정렬 TEXT를 insert(퇴화 bbox)로 비교해 오탐 (#57)

```
$ rg '"TEXT"|insert.*point.*text' tools/cad_diff.py -i
(matches: 0)
$ rg 'alignment_point' tools/cad_diff.py
(matches: 0)
```
`tools/cad_diff.py`에 TEXT 전용 비교 분기가 **아예 없다** — `classify_change`/`_geometry_fingerprint`/`_exact_fingerprint` 전부 `entity.get("geometry")` 딕셔너리 전체를 `_canonical()`로 구조 비교한다(455-492행, 768-809행). "insert만 보고 비교"하는 지름길이 없으므로, geometry 딕셔너리에 `alignment_point` 키가 들어있기만 하면 자동으로 비교 대상에 포함된다.

긍정 증거(SAFE 근거):
| 파일:줄 | 내용 |
|---|---|
| tools/ir_builder.py:907 | `alignment_point`이 TEXT/MTEXT류가 공유하는 포인트 필드 리프트 튜플에 포함(#42/#44/#38/#43, 커밋 94a3895에서 추가). |
| tools/cross_oracle.py:217 | `alignment_point`이 오라클이 값으로 단정하는(assert하는) 인식된 geometry 키 목록에 포함(#42/#43 주석). |
| tools/cad_diff.py:455-492, 768-809 | `geometry` 필드는 부분 필드가 아니라 **전체 딕셔너리**를 구조 비교 — `alignment_point`을 선택적으로 빠뜨릴 지름길이 없음. |

| 파일 | 판정 | 근거 |
|---|---|---|
| tools/cad_diff.py (전체) | **SAFE** | T4가 요구하는 "TEXT를 insert만으로 비교" 지름길이 존재하지 않음 — 전체 geometry 구조 비교 + `alignment_point`이 이미 그 구조에 실려 있음(ir_builder #42/#44/#38/#43 fix, NON_GOALS로 #43 자체는 범위 밖이나 그 결과물은 활용). CHANGE_ONLY 안, 수리 불필요. |

## 요약

| 함정 | 모집단(rg) | FIX | SAFE | UNKNOWN | CHANGE_ONLY 안 수리 |
|---|---|---|---|---|---|
| T1 | 1 | 1 | 0 | 0 | 1 |
| T3 | 27 | 15 (transforms_struct.py 한 결함, 15줄) | 12 | 0 | 0 |
| T2 | 8 + 6 = 14 | 8 (op_roundtrip_probe.py) + 3 (transforms_struct.py, T3와 동일 결함 중복 계상 아님) = 11 | 3 | 0 | 0 |
| T4 | 0 결함 지점(증거 3건) | 0 | 1 파일 + 3 증거 | 0 | 0 (이미 안전) |
| **합계** | **45 표 행** | **27** | **16** | **0** | **1** |

CHANGE_ONLY(`tools/e2/gen2/gen2.py`, `tools/patch_ops/`, `tools/cad_diff.py`) 안에서 확정된 FIX는 **T1 하나(gen2.py:491)** 뿐이다. `tools/patch_ops/tables.py`·`blocks.py`·`entities.py`는 ezdxf 테이블 객체를 전혀 건드리지 않고 네이티브(ObjectARX) job-args 딕셔너리만 조립하므로 T1/T2/T3 모집단에 아예 포함되지 않는다(rg 매치 0건, 표에서 SAFE-by-absence로 별도 행을 만들지 않음). 나머지 FIX 26건(T3의 transforms_struct.py 15줄 + T2의 op_roundtrip_probe.py 8줄 + transforms_struct.py 3줄)은 전부 `tools/e2/meta/` 또는 `tools/op_roundtrip_probe.py`로, CHANGE_ONLY 계약 밖이라 이 레인에서 수리하지 않는다 — REPORT.md에 별도 레인 필요 사항으로 인계한다.
