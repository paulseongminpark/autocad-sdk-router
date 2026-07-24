# 벽-주장 검증기 빌드 보고서

## 구현 요약

`verifier.py`는 SEG-IR의 기하와 policy-visible CAD 메타데이터만으로 완전한 벽 핸들 집합 주장을 판정한다. `label` 필드는 파싱·분석·판정 어느 경로에서도 읽지 않는다. 평행짝(각도·종방향 겹침), 도면 단위로 환산한 50–400 mm 두께, 짝 중심축의 정션 토폴로지, 고아 핸들, 벽 레이어 메타데이터, 후보 집합 완전성, 빈/전체 주장 센티널을 각각 분리해 출력한다.

판정은 보수적이다. 기하+레이어로 재구성한 후보 전체와 주장이 정확히 같고, 모든 주장 핸들이 두께 대역의 평행짝을 가지며, 후보 정션 토폴로지가 보존되고, 입력/센티널/고아 검사가 모두 성립할 때만 `accept`한다. 진리 원장은 이 함수에 전달되지 않는다.

CLI:

```text
python verifier.py --seg-ir <seg-ir.json> --claim <claim.json-or-json-list>
python verifier.py --selftest
python verifier.py --build --n 504 --seed 20260718
```

## Selftest 전문

```text
=== verifier selftest ===
[OK] obvious_true: verdict=accept
[OK] obvious_false: verdict=reject reasons=['junction_closure', 'layer_metadata', 'set_completeness']
[OK] degenerate_empty: verdict=reject reasons=['sentinels', 'parallel_pairs', 'thickness_consistency', 'junction_closure', 'set_completeness']
[OK] degenerate_whole_universe: verdict=reject reasons=['sentinels', 'parallel_pairs', 'orphan_segments', 'layer_metadata', 'set_completeness']
[OK] label_independence: original=accept poisoned=accept
[OK] perturbation_wall_remove_single: verdict=reject reasons=['parallel_pairs', 'junction_closure', 'orphan_segments', 'set_completeness']
[OK] perturbation_wall_remove_pair: verdict=reject reasons=['junction_closure', 'set_completeness']
[OK] perturbation_lure_add: verdict=reject reasons=['parallel_pairs', 'orphan_segments', 'layer_metadata', 'set_completeness']
[OK] perturbation_neighbor_swap: verdict=reject reasons=['parallel_pairs', 'junction_closure', 'orphan_segments', 'layer_metadata', 'set_completeness']
[OK] perturbation_pair_swap: verdict=reject reasons=['junction_closure', 'layer_metadata', 'set_completeness']
[OK] perturbation_orphan_add: verdict=reject reasons=['parallel_pairs', 'orphan_segments', 'layer_metadata', 'set_completeness']
SELFTEST_RESULT: PASS
```

## FAR/FRR 실측

- generator: `D:\dev\99_tools\autocad-sdk-router\tools\e2\gen2\gen2.py`
- generator SHA-256: `a8c2468b696b9271610e38bd87cec1402e9153bc464a5d9cf1429595f26dab55`
- 고정 base seed: `20260718`
- 생성 도면: 504건; 평가 도면: 504건 ({'F': 168, 'M': 168, 'S': 168})
- 참 주장: n=504, accept=504, reject=0, FRR=0.000000000
- 거짓 주장: n=3024, accept=0, reject=3024, FAR=0.000000000
- runtime_seconds: 15.688654

수치는 고정 시드 audit의 관측값만 기록한다. 자격 판정은 이 빌드 산출물에서 내리지 않는다.

### 교란 종별 FAR

| 절차 교란 | n | accept | reject | FAR |
|---|---:|---:|---:|---:|
| `wall_remove_single` | 504 | 0 | 504 | 0.000000000 |
| `wall_remove_pair` | 504 | 0 | 504 | 0.000000000 |
| `lure_add` | 504 | 0 | 504 | 0.000000000 |
| `neighbor_swap` | 504 | 0 | 504 | 0.000000000 |
| `pair_swap` | 504 | 0 | 504 | 0.000000000 |
| `orphan_add` | 504 | 0 | 504 | 0.000000000 |

교란은 (1) 벽 한쪽 제거, (2) 벽 pair 전체 제거, (3) 벽처럼 보이는 미끼 추가, (4) 공간상 가장 가까운 음성 핸들과 이웃 스왑, (5) 참 pair를 음성 평행 pair로 교체, (6) 평행 지지가 없는 고아 추가다. 각 교란은 모든 평가 도면에 한 번씩 적용했다.

## 감사 경계

- gen2는 `sys.dont_write_bytecode=True` 상태에서 read-only import했고 원본 repo에 쓰지 않았다.
- ezdxf는 audit 중 gen2가 만든 임시 팩을 SEG-IR로 재생하는 경로에서만 lazy import한다. 핵심 verifier는 stdlib만 사용한다.
- 임시 팩은 이 산출 디렉토리 안에서 만들고 측정 종료 시 제거했다.
- `far_frr_numbers.json`에는 수치와 provenance만 있으며 자격 verdict/threshold 비교는 넣지 않았다.

## 미해결·해석 제한

- gen2 v2의 벽 토폴로지는 tier별로 고정되고 seed는 주로 calibration context를 바꾼다. 따라서 n은 서로 다른 재생 seed/팩의 주장 수이지만, 완전히 독립적인 n개 벽 토폴로지 family로 해석하면 안 된다.
- 벽 레이어 메타데이터가 제거·오염된 name-blind SEG-IR에서는 이 보수적 verifier가 거부할 수 있다. 이는 라벨 누출을 피하면서 현재 팩의 hard-negative 평행 구조를 분리하기 위한 명시적 범위다.
- ARC는 audit adapter에서 7.5도 이하 chord로 근사한다. 원본 SEG-IR이 다른 chord 정책을 쓰면 동일 파라미터로 재계측해야 한다.

### 실측 중 이상 표본

없음.

BUILD_COMPLETE: verifier
