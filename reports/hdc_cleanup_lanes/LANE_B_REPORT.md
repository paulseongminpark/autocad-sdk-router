# REPORT — ezdxf/심볼테이블 함정 전수 감사 (fix/ezdxf-trap-audit)

## STATUS: PARTIAL_PASS

범위: 감사(전수) 자체는 repo 전체 `tools/**/*.py`에 대해 완료. **수리는 계약(CHANGE_ONLY)이 허용한 범위로 축소** — `tools/e2/gen2/gen2.py`·`tools/patch_ops/`·`tools/cad_diff.py` 안에서 확정된 FIX는 1건뿐이었고 그 1건은 수리·테스트·커밋까지 완료. 그 밖에서 발견한 확정 FIX 11개 지점(26줄)은 CHANGE_ONLY 밖(`tools/e2/meta/transforms_struct.py`, `tools/op_roundtrip_probe.py`)이라 이 레인에서 수리하지 않고 AUDIT.md에 기록만 했다 — 그래서 PASS가 아니라 PARTIAL_PASS.

## 무엇을 했나

1. **모집단 확정** — `tools/**/*.py`에서 4종 함정 각각의 rg 검색을 돌려 전수 나열했다(AUDIT.md 참고). `add_wipeout(` 1건, ezdxf 테이블 접근(`doc.layers/styles/linetypes/dimstyles`) 27건(7 파일), 심볼테이블 이름 `==` 비교 8+6건(2차 수동 발견 포함), TEXT 비교 키 감사는 "지름길이 없다"는 부재 증명 3건 — 표 행 수 45.
2. **각 지점 판정** — FIX 27줄 / SAFE 16개 지점(파일 단위) / UNKNOWN 0. 임의 수리 없이 판정만 먼저 끝냈다.
3. **CHANGE_ONLY 안 FIX 1건 수리** — `tools/e2/gen2/gen2.py:491`의 `add_wipeout` 호출이 `dxfattribs={"layer": "PROFILE-FILL"}`을 줘도 ezdxf 1.4.3의 `Wipeout.set_masking_area()`가 `update_dxf_attribs(DEFAULT_ATTRIBS)`(`DEFAULT_ATTRIBS["layer"]=="0"`)로 되돌리는 것을 이 세션에서 실측 확인(`inspect.getsource` + 실제 문서 생성 테스트) 후, `add_wipeout()` 반환값에 `.dxf.layer = layer`를 사후 설정하도록 고쳤다.
4. **red-first 테스트** — `tests/unit/test_gen2_wipeout_layer.py` 신설. 수리 전 실행: `AssertionError: WIPEOUT landed on layer '0' instead of PROFILE-FILL`(적색). 수리 후 재실행: `1 passed`(녹색).
5. **베이스라인/최종 회귀** — 착수 직후 `python -m pytest tests/unit -q` → `1989 passed, 30 skipped in 59.81s`. 수리 후 전체 재실행 → `1990 passed, 30 skipped`(신규 테스트 1개 추가분, 그 외 전부 동일) — 신규 실패 0건.

## FIX/SAFE/UNKNOWN 집계 (AUDIT.md 표 기준)

| 함정 | 모집단(rg) | FIX | SAFE | UNKNOWN | 이 레인에서 수리 |
|---|---|---|---|---|---|
| T1 (#49 add_wipeout) | 1 | 1 | 0 | 0 | 1 |
| T3 (#58/#60 테이블 무구분) | 27 | 15줄(1개 결함) | 12 | 0 | 0 |
| T2 (#54 이름 대소문자) | 14 | 11줄(2개 결함: op_roundtrip_probe.py 8줄 + transforms_struct.py 3줄, T3과 결함 실체 동일) | 3 | 0 | 0 |
| T4 (#57 정렬 TEXT bbox) | 0 결함 지점 (증거 3건) | 0 | 1 파일+3증거 | 0 | 0 (이미 안전) |
| **합계** | **45 표 행** | **27줄** | **16 지점** | **0** | **1** |

## CHANGE_ONLY 밖이라 수리하지 않은 확정 FIX (다음 레인 인계)

- **`tools/e2/meta/transforms_struct.py`** — `_collect_layer_names`가 ezdxf 테이블 항목 이름(`layer.dxf.name`)과 엔티티가 들고 있는 리터럴 레이어 문자열(`e.dxf.layer`)을 대소문자 구분 파이썬 `set`에 같이 담는다. 실측(이 세션): 같은 도면을 저장 후 재로드하면 테이블 엔트리는 `'WALL'`인데 엔티티의 리터럴 문자열은 `'wall'`로, 서로 다른 케이스가 **독립 보존**된다. 그 결과 `_rename_layer_table`이 실제로는 하나뿐인 레이어를 `layer_map`에서 두 개의 키로 만나 두 번 처리하려다, 두 번째 `duplicate_entry`/`remove` 호출이 이미 지워진 항목을 찾지 못해 실패할 수 있다.
- **`tools/op_roundtrip_probe.py`** — `_layer_by_name`/`_dimstyle_by_name`/`_linetype_by_name` 등 8개 헬퍼가 전부 `rec.get("name") == name`(대소문자 구분)으로 심볼테이블 레코드를 찾는다. AutoCAD 심볼테이블 이름은 대소문자 무구분 유일이므로, `create_layer(name="wall")`이 기존 `"WALL"`을 upsert했을 때(성공) `_layer_by_name(post_ir, "wall")`은 못 찾고 `STATUS_HOLLOW`(실패)로 오판한다 — 성공한 쓰기를 실패로 보고하는 실제 오탐.

두 항목 모두 AUDIT.md에 파일:줄·근거·재현 실측이 남아 있다. 이 레인의 CHANGE_ONLY(`tools/e2/gen2/gen2.py`·`tools/patch_ops/`·`tools/cad_diff.py`·`tests/unit/` 신규·`AUDIT.md`/`REPORT.md`)로는 손댈 수 없어 그대로 인계한다.

## 검증 (VALIDATION 항목별)

- PowerShell pytest 결과: 베이스라인 `1989 passed, 30 skipped`, 최종 `1990 passed, 30 skipped` — 신규 실패 0건 (위 인용).
- AUDIT.md 표 행수(45) == rg 모집단 수(1+27+14+3 증거행): AUDIT.md 요약 표에 명시.
- FIX건(gen2.py:491) red/green 출력: 위 §"red-first 테스트" 인용.
- `git log --oneline -10`: 아래 커밋 해시 참고.

## 커밋

`cb5186c` — "gen2: fix add_wipeout layer-reset trap (#49); audit T1-T4 repo-wide (#54 #57 #58 #60)" (브랜치 `fix/ezdxf-trap-audit`, 4 files changed: `AUDIT.md`, `REPORT.md`, `tests/unit/test_gen2_wipeout_layer.py`, `tools/e2/gen2/gen2.py`).

## 건너뛴 것 / 검증 못 한 것

- CHANGE_ONLY 밖 FIX 11개 지점(26줄)은 판정까지만 하고 수리는 건너뛰었다 — 계약(CHANGE_ONLY)이 이유이지 시간/능력 문제가 아니다.
- `src/`(ObjectARX 네이티브 C++)는 READ_ALLOW 안이지만 ezdxf를 쓰지 않으므로(파이썬 전용 라이브러리) 모집단에서 원천 제외했다 — grep으로 `import ezdxf`/`from ezdxf`가 `tools/` 밖에서 전혀 나오지 않음을 확인.
- `tools/ir_to_patch.py:67,82`(블록 이름 예약 집합)와 `tools/blockdef_diff.py:771`은 T2 패턴과 겉모양이 비슷해 검토했지만, 두 곳 다 소스가 네이티브 추출 하나로 일관돼 있어(ezdxf 무구분 테이블과 파이썬 케이스 구분 구조를 섞는 T2/T3의 전제 자체가 없음) SAFE로 판정 — 다만 실제 라이브 파이프라인으로 재현 테스트는 하지 않았다(코드 판독 근거만).
