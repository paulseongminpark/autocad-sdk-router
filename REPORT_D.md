# REPORT_D — Issue #62: MULTILEADER downgraded to LEADER (text loss)

## STATUS: PASS

`tools/build_from_ir.py`의 leader 분기가 `#62`의 결함을 그대로 상속하고 있었음을
red 테스트로 재현한 뒤, 이슈에 첨부된 수리(ezdxf `add_multileader_mtext` 경로 +
기하 조정 3종)를 이식했다. 신규 회귀 테스트 4개 GREEN, 전체 `tests/unit` 2033개
통과·0 실패(베이스라인 대비 신규 실패 0).

## 1. 결함 상속 재현 (RED)

수리 전 `_h_leader` docstring(#59 당시 작성)에 이미 "MULTILEADER도 `kind ==
"leader"`로 들어와 LEADER로 강등된다 — 별도 추적 중인 결함"이라고 명시돼 있었다
(`tools/build_from_ir.py:706-708`, 수리 전). 코드에는 `dxf_name` 판별 분기가
전혀 없었으므로 이식된 빌더도 결함을 그대로 물려받았을 것으로 판단하고, 이를
`tests/unit/test_build_from_ir.py`에 `Issue62MultileaderTest` 클래스로 먼저
작성해 RED를 확보했다.

명령: `python -m pytest tests/unit/test_build_from_ir.py -k Issue62 -v --basetemp="$env:TEMP\pytest-d" -p no:cacheprovider`

수리 전 결과 — **4개 전부 FAIL**:
```
tests/unit/test_build_from_ir.py::Issue62MultileaderTest::test_multileader_is_not_downgraded_to_leader FAILED
  AssertionError: 0 != 1   # MULTILEADER 0개 (LEADER로 강등됨)
tests/unit/test_build_from_ir.py::Issue62MultileaderTest::test_multileader_text_survives_the_roundtrip FAILED
  IndexError: list index out of range   # MULTILEADER 자체가 없음 -> 텍스트도 없음
tests/unit/test_build_from_ir.py::Issue62MultileaderTest::test_multileader_vertex_count_is_not_inflated_by_a_synthesized_landing FAILED
  IndexError: list index out of range
tests/unit/test_build_from_ir.py::Issue62MultileaderTest::test_multileader_without_text_falls_back_to_leader_with_a_reason FAILED
  AssertionError: 0 != 1   # 폴백 사유 카운터가 아예 없었음
4 failed, 32 deselected, 17 warnings in 0.62s
```
결함 상속이 재현으로 확정됐다. (이슈가 보고한 "MULTILEADER → LEADER 강등 + 텍스트
소실"과 정확히 같은 실패 형태.)

## 2. IR의 MULTILEADER 판별 필드 확정

이슈 스니펫은 `e.get("dxf_name") == "MULTILEADER"`를 쓴다. `tools/ir_builder.py`
실코드로 확인한 결과 **이슈와 동일한 필드/값**임을 확정했다(추가 조정 불필요):

- `tools/ir_builder.py:818` — `_NATIVE_CLASS_TO_DXF_KIND` 매핑: `"AcDbMLeader": ("MULTILEADER", "leader")`.
  즉 AcDbMLeader 엔티티는 `dxf_name="MULTILEADER"`, `geometry.kind="leader"`로
  나란히 찍힌다 — 이슈가 지목한 "kind는 같은데 dxf_name만 다르다"는 근본 원인의
  1차 출처.
- `tools/ir_builder.py:1216-1217` — 엔티티 레코드 최상위에 `"dxf_name": dxf_name`이
  실제로 실린다(geometry 안이 아니라 entity 레벨). `_add_entity` 디스패처
  (`tools/build_from_ir.py:956-969`)가 핸들러를 `handler(ctx, space, ent, geom, attr)`
  형태로 호출하므로 `_h_leader`는 `ent`를 통해 `ent.get("dxf_name")`을 그대로
  읽을 수 있다 — 이식에 추가 배선 불필요.
- geometry 쪽 `text`/`height`는 `tools/ir_builder.py:950,987-988`의 범용
  숫자/문자열 리프트를 그대로 타므로 leader/multileader 모두 동일한 키
  (`g.get("text")`, `g.get("height")`)로 들어온다 — 기존 `_h_text`/`_h_mtext`
  핸들러와 동일한 관례.

## 3. 수리 이식

`tools/build_from_ir.py`에 `_add_multileader_mtext()` 헬퍼를 새로 추가하고,
`_h_leader()`의 `kind == "leader"` 분기 맨 앞에 `ent.get("dxf_name") ==
"MULTILEADER"` 판별을 추가했다. 이슈 스니펫과의 API 차이(ezdxf 1.4.3 실측,
`python -c` 프로브로 직접 확인):

- `mb.set_content(_txt, char_height=_h)` — 시그니처 일치, 그대로 이식.
- `mb.set_connection_properties(landing_gap=0.0, dogleg_length=0.0)` — 시그니처
  일치.
- `mb.add_leader_line(side, vertices)` — `ConnectionSide`는
  `ezdxf.render.mleader.ConnectionSide`에 있음(이슈의 `_CS`와 동일 enum,
  import 경로만 명시). `vertices`는 `Vec2` 이터러블 — 이슈의 `_V2`를
  `ezdxf.math.Vec2`로 확정.
- `mb.build(insert=...)` — 시그니처 일치. **`space[-1]`로 방금 만든
  MULTILEADER를 회수할 수 있음을 프로브로 확인**(이슈 스니펫의 `space[-1]`
  그대로 유효).
- `ml.dxf.has_landing = 0`, `leader.has_last_leader_line = 0` — 둘 다 존재하고
  쓰기 가능함을 프로브로 확인, save+reload 후에도 값 보존됨을 확인.

스니펫과의 차이는 문자 그대로의 함수/변수명 정리(`_txt`→`text`,
`_pts`→`points` 등)뿐, 동작은 이슈가 검증한 것과 동일하다. ezdxf API 자체는
스니펫과 어긋나지 않아 ESCAPE 조항(동등 동작으로 조정)은 발동하지 않았다.

폴백 규율:
- MULTILEADER 빌드가 예외를 던지면 `errors["multileader:<예외타입>:..."]`을
  올리고 `skipped["leader:multileader_build_failed"]`를 올린 뒤 기존
  LEADER 경로로 떨어진다(디스패처 레벨 try/except가 아니라 `_h_leader` 내부에서
  직접 잡아야 폴백이 가능 — 디스패처의 바깥쪽 try/except에 맡기면 엔티티가
  통째로 `errors`로만 잡히고 LEADER조차 안 만들어지므로).
- 텍스트가 없는 MULTILEADER(블록 콘텐츠형, `#62` TODO 항목)는
  `skipped["leader:multileader_no_text"]`를 올리고 LEADER로 폴백 —
  NON_GOAL(블록 콘텐츠형 완전 지원)을 침범하지 않으면서 엔티티가 조용히
  사라지지 않게 했다.

## 4. GREEN 확인

명령: `python -m pytest tests/unit/test_build_from_ir.py -k Issue62 -v --basetemp="$env:TEMP\pytest-d" -p no:cacheprovider`

```
tests/unit/test_build_from_ir.py::Issue62MultileaderTest::test_multileader_is_not_downgraded_to_leader PASSED
tests/unit/test_build_from_ir.py::Issue62MultileaderTest::test_multileader_text_survives_the_roundtrip PASSED
tests/unit/test_build_from_ir.py::Issue62MultileaderTest::test_multileader_vertex_count_is_not_inflated_by_a_synthesized_landing PASSED
tests/unit/test_build_from_ir.py::Issue62MultileaderTest::test_multileader_without_text_falls_back_to_leader_with_a_reason PASSED
4 passed, 32 deselected, 19 warnings in 0.64s
```

각 테스트가 단정하는 것:
- `test_multileader_is_not_downgraded_to_leader` — 재로드 후 MULTILEADER 1개,
  LEADER 0개.
- `test_multileader_text_survives_the_roundtrip` — `ml.context.mtext.default_content`가
  원본 텍스트와 정확히 일치(포맷 코드 포함 문자열 그대로).
  ezdxf 프로브로 write→read 왕복 후 텍스트가 바이트 그대로 보존됨을 별도 확인
  (`python -c` 프로브: `reload mtext: hello world`).
- `test_multileader_vertex_count_is_not_inflated_by_a_synthesized_landing` —
  `has_landing == 0`, leader line 1개·정점 2개(랜딩 정점 추가 없음), 각
  leader의 `has_last_leader_line == 0`. save+reload 후에도 값 유지됨을
  프로브로 확인(`reload has_landing: 0`, `reload has_last_leader_line: 0`).
  단, 이 단정은 **ezdxf 자체의 write/read 왕복**에 대한 것이며, 이슈가 말하는
  "AutoCAD가 재생성 때 정점을 하나 더 만든다"는 현상은 실물 AutoCAD 세션이
  필요해 이 테스트로는 검증하지 못한다(그 현상을 막는 플래그가 올바로
  설정·보존됨을 확인하는 것으로 대체) — 검증 범위를 여기 명시해 건너뛴 부분을
  숨기지 않는다.
- `test_multileader_without_text_falls_back_to_leader_with_a_reason` — 빈
  텍스트일 때 LEADER 1개로 폴백, `skipped["leader:multileader_no_text"] == 1`.

## 5. 전체 스위트

명령: `python -m pytest tests/unit -q --basetemp="$env:TEMP\pytest-d" -p no:cacheprovider`

```
2033 passed, 30 skipped, 63 warnings in 61.70s (0:01:01)
```
실패 0건. 베이스라인(수리 전 HEAD `2b19679`) 대비 신규 실패 없음 — 신규 테스트
4개가 더해져 전체 통과 수만 늘었다.

작업 중 `reports/autocad_router_status_latest.json`(PROTECTED_PATHS)이 다른
백그라운드 프로세스(자동 상태 리포트, 타임스탬프 기반)에 의해 재생성돼 워킹
트리에 나타났다 — 이 과업이 만든 변경이 아니므로 `git checkout --`로 원복하고
커밋에서 제외했다.

## 6. 변경 범위

- `tools/build_from_ir.py` — `_add_multileader_mtext()` 헬퍼 추가, `_h_leader()`에
  `dxf_name == "MULTILEADER"` 판별 분기 추가(+53/-3줄).
- `tests/unit/test_build_from_ir.py` — `Issue62MultileaderTest` 4개 테스트 추가.
- `REPORT_D.md` — 본 보고서(신규).

CHANGE_ONLY를 벗어난 파일 변경 없음. `ir_builder.py`(추출기) 미변경 — NON_GOAL
(추출기 보강, `kind` 스키마 분리)에 손대지 않았다. push/이슈 상태 변경 없음.

## 커밋

`ec3be9f` — "builder: native MULTILEADER instead of LEADER downgrade (#62)"
(부모: `2b19679`, 브랜치 `fix/hdc-builder-port`).
