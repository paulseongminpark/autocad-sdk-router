# 계측기 3 — 합성 도면 생성기 v2 빌드 보고서

## 산출 결과

- 구현: `gen2.py`
- 수치 전용 충실도 계산기: `fidelity_stats.py`
- S/F/M 샘플 팩: `packs_sample/`
- 충실도 실측: `fidelity_stats.json`
- 저장소 수정, Git 실행, 원본 CAD 접근, 서브에이전트 사용: 없음

## 설계

생성 순서는 `의미 벽/음성 클래스 → 기하 → DXF 표현 → 실제 handle 원장`이다. 기존 하네스가 읽는 `s2pack.v1`, `wall.v1`, per-wall `handles`, `wall_handles_flat`을 그대로 유지했고, `class_of_handle`을 additive extension으로 넣었다. `class_of_handle`은 벽과 명시적 hard-negative scoring universe를 기록한다. 프로파일 보정용 배경 entity는 legacy evaluator에서 자연스럽게 non-wall이지만 명시적 hard-negative class count에는 섞지 않는다.

hard negative는 모두 벽 두께 대역의 평행 구조를 실제 기하로 포함한다.

- `dimension_helper`: 평행 치수 보조선, tick, TEXT/MTEXT
- `door_frame`: 이중 jamb 선
- `furniture_bed`, `furniture_desk`, `furniture_storage`: 100–140 mm 간격의 이중 외곽과 SPLINE
- `stair_tread`: 250 mm 간격 디딤판
- `direction_arrow`: 이중 shaft를 가진 닫힌 LWPOLYLINE
- `room_boundary`: 160 mm 간격 이중 room polyline

벽 표현은 straight/partial/open-plan, 시작·끝 두께가 다른 tapered LWPOLYLINE, ARC 쌍 곡면벽, M-tier 비평행 messy fragment를 포함한다. HATCH는 벽 채움과 floor pattern을 모두 만든다. entity mix는 CLI의 `--entity-ratios` JSON으로 바꿀 수 있으며 기본값은 기존 fidelity JSON에 기록된 집계 분포다. 기본 profile은 LINE, LWPOLYLINE, SPLINE, ARC, INSERT 외에 HATCH, TEXT, MTEXT, CIRCLE, ELLIPSE, POINT, 3DFACE, WIPEOUT을 생성한다.

같은 seed의 byte SHA 재현을 위해 ezdxf의 시간/GUID metadata를 고정하고 CLASSES 등록 순서를 정렬했다. 각 tier manifest에는 seed 목록과 각 DXF/truth SHA-256이 들어 있다.

## 샘플 팩 실측

| tier | seed | modelspace entities | wall handles | explicit negative handles | wall_frac | wall variants |
|---|---:|---:|---:|---:|---:|---|
| S | 20260718 | 2,856 | 16 | 32 | 0.333333 | open_plan, partial, thickness_change |
| F | 20360718 | 2,856 | 18 | 34 | 0.346154 | curved, open_plan, partial, thickness_change |
| M | 20460718 | 2,857 | 20 | 36 | 0.357143 | curved, messy_nonparallel, open_plan, partial, thickness_change |

세 tier 모두 legacy `validate_manifest()`와 `validate_truth()` 오류가 0이었다. 기존 detect→eval CLI로 M 샘플을 그대로 읽는 smoke test도 종료코드 0이었다: 2,358 segments, truth 20 handles, threshold 0.5에서 TP=18/FP=406/FN=2, P=0.042453/R=0.900/F1=0.081081. 이는 호환성 실측이며 generator 품질 PASS/FAIL 판정으로 사용하지 않는다. 다수의 의도적 평행 음성과 reference-shaped drafting context 때문에 기존 detector의 낮은 precision은 예상되는 노출 결과다.

## `--selftest` 전문

실행 명령:

```text
python D:\runs\e2_program\build\gen2\gen2.py --selftest
```

출력:

```text
=== gen2 selftest ===
python=3.12.10 ezdxf=1.4.3
[OK] pack_created: C:\Users\PAUL\AppData\Local\Temp\e2_gen2_selftest_74fwh6xy\first
[OK] S_manifest: schema=s2pack.v1 n=1
[OK] S_ezdxf_parse: version=AC1032 entities=701
[OK] S_ledger_handles: labeled=48 missing=0
[OK] S_wall_class: walls=16
[OK] S_negative_present: wall=16 negative=32
[OK] S_wall_frac: wall_frac=0.333333
[OK] F_manifest: schema=s2pack.v1 n=1
[OK] F_ezdxf_parse: version=AC1032 entities=701
[OK] F_ledger_handles: labeled=52 missing=0
[OK] F_wall_class: walls=18
[OK] F_negative_present: wall=18 negative=34
[OK] F_wall_frac: wall_frac=0.346154
[OK] M_manifest: schema=s2pack.v1 n=1
[OK] M_ezdxf_parse: version=AC1032 entities=701
[OK] M_ledger_handles: labeled=56 missing=0
[OK] M_wall_class: walls=20
[OK] M_negative_present: wall=20 negative=36
[OK] M_wall_frac: wall_frac=0.357143
[OK] hard_negative_classes: required=8 missing=[]
[OK] entity_diversity: observed=['3DFACE', 'ARC', 'CIRCLE', 'ELLIPSE', 'HATCH', 'INSERT', 'LINE', 'LWPOLYLINE', 'MTEXT', 'POINT', 'SPLINE', 'TEXT', 'WIPEOUT'] missing=[]
[OK] seed_reproducibility: files=10 differing=[]
temp_cleaned=C:\Users\PAUL\AppData\Local\Temp\e2_gen2_selftest_74fwh6xy
SELFTEST_RESULT: PASS
```

검사는 S/F/M 팩 1벌 생성, ledger handle 실재성, 벽/음성 클래스 수 실측, 각 tier `wall_frac∈[0.15,0.60]`, 요구 hard-negative class, 요구 entity type, ezdxf 재파싱, 같은 seed의 전 파일 SHA-256 동일성을 포함한다.

## 충실도 통계 실측

계산기는 기존 `s2_fidelity.py`와 같은 방법을 독립 구현했다. modelspace entity type의 categorical TV와, LINE/LWPOLYLINE/POLYLINE의 겹치는 평행 segment offset histogram KS를 계산한다. 참조는 기존 fidelity JSON의 집계 통계만 사용했다.

- thickness histogram: `fidelity_M_v2.json`, SHA-256 `afec84ebf141d8bc29ef6b0ee8fe615c7e6c2bf19b1e4df10c64d11951691ae3`
- entity mix: `fidelity_M_v1_tv.json`, SHA-256 `cc95a55852932cc41eb5dfdc5fc9df560f6ada94625969e9284c581e809608ea`
- 원본 CAD 파일: 접근하지 않음

집계 수치:

- `thickness_ks = 0.06265902171230281`
- `entity_mix_tv = 0.0008332487822938152`
- `n_drawings = 3`
- `n_entities = 8569`
- `n_parallel_pair_offsets = 2209`
- `read_errors = 0`

tier별 수치:

| tier | thickness_ks | entity_mix_tv | pair offsets | read errors |
|---|---:|---:|---:|---:|
| S | 0.0625323167307058 | 0.000822052799641249 | 736 | 0 |
| F | 0.0625323167307058 | 0.000822052799641249 | 736 | 0 |
| M | 0.06291208783565533 | 0.0008556329100193184 | 737 | 0 |

`fidelity_stats.json`과 계산기 stdout에는 threshold, band, PASS/FAIL, verdict가 없다. 위 값에도 소비자별 판정을 붙이지 않는다.

## 미해결 및 경계

- 샘플은 tier당 1장이라 seed population의 분산을 추정하지 않는다.
- 참조 분포는 기존 집계 JSON에 한정되어 project/definition별 조건부 분포를 재현하지 않는다.
- 곡면벽의 ARC handle 2개는 ledger의 wall truth에 포함된다. 현재 legacy detector smoke에서는 전체 20개 중 18개를 threshold 0.5에서 회수했지만, generator는 이를 숨기거나 LINE으로 가장하지 않는다.
- HATCH wall fill은 `wall_handles_flat`에 넣지 않았다. 이 필드는 기존 line/curve wall-member 하네스 호환 handle universe이고, HATCH는 entity-diversity와 poché 표현으로 남긴다.
- reference-shaped drafting context는 기존 aggregate histogram을 재현하기 위한 명시적 non-wall 배경이며, semantic hard-negative class count와 분리되어 있다.

BUILD_COMPLETE: gen2
