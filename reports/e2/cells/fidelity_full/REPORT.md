# fidelity_full 셀 실행 보고서

## 범위와 실행 설계

gen2 v2의 기본 전체-다양성 비율로 S/F/M 각 50장, 총 150장을 새로 생성했다. 각 tier는 50개 고정 seed를 가지며, `seed_manifest.json`과 tier manifest의 DXF/truth SHA-256으로 재생 recipe를 고정했다. 원본 CAD와 외부 test split은 열지 않았고, source repo의 세 Python 파일은 read-only import했다.

- base seed: `20260719`
- entity target: 1400 / drawing
- reference parallel pairs: 600 / drawing
- 생성기 SHA-256: `a8c2468b696b9271610e38bd87cec1402e9153bc464a5d9cf1429595f26dab55`
- source hash unchanged: `True`
- pack files: DXF 150, truth ledger 150, tier manifest 3, root manifest 1
- artifact integrity errors: 0

충실도 수치에는 prereg band 비교나 PASS/FAIL 판정을 붙이지 않았고, 검증기 수치에도 자격 판정을 붙이지 않았다.

## 소표본 처리율 선실측과 전량 예상

전량 전에 동일 config의 S/F/M 각 1장(3장)을 생성·통계·검증했다. 임시 샘플 팩은 측정 뒤 제거했다.

| 단계 | 소표본 초 | 초/도면 | 150장 예상 초 |
|---|---|---|---|
| 팩 생성 | 0.292239 | 0.097413 | 14.612 |
| fidelity_stats 방식 | 4.092453 | 1.364151 | 204.623 |
| SEG-IR+검증기 | 37.255263 | 12.418421 | 1862.763 |

전량 실제 시간은 생성 13.948s, fidelity 207.891s, SEG-IR+검증 2246.529s, pack hash 검증 0.221s였다.

## 팩 달성 분포와 진리 원장

- drawings: 150
- observed entity types: 13 — `3DFACE, ARC, CIRCLE, ELLIPSE, HATCH, INSERT, LINE, LWPOLYLINE, MTEXT, POINT, SPLINE, TEXT, WIPEOUT`
- wall handles / explicitly labeled handles: 2700 / 7800
- aggregate wall_frac: 0.346153846

### 엔티티 수와 달성 비율

| entity | count | ratio |
|---|---|---|
| 3DFACE | 450 | 0.001050298 |
| ARC | 33450 | 0.078072120 |
| CIRCLE | 2100 | 0.004901389 |
| ELLIPSE | 3000 | 0.007001984 |
| HATCH | 4050 | 0.009452678 |
| INSERT | 17700 | 0.041311705 |
| LINE | 184550 | 0.430738709 |
| LWPOLYLINE | 112800 | 0.263274594 |
| MTEXT | 1650 | 0.003851091 |
| POINT | 5250 | 0.012253472 |
| SPLINE | 60600 | 0.141440075 |
| TEXT | 2400 | 0.005601587 |
| WIPEOUT | 450 | 0.001050298 |

### 명시적 음성 클래스 수 (요구 8개 미끼 포함)

| class | count |
|---|---|
| dimension_helper | 450 |
| dimension_text | 300 |
| direction_arrow | 150 |
| direction_symbol | 150 |
| door_frame | 600 |
| door_hardware | 100 |
| door_swing | 150 |
| furniture_bed | 450 |
| furniture_curve | 150 |
| furniture_desk | 450 |
| furniture_storage | 450 |
| messy_fragment | 50 |
| room_boundary | 300 |
| stair_tread | 1350 |

## 충실도 수치

`fidelity_stats.py`의 동일 계산으로 reference aggregate JSON의 parallel-offset histogram KS와 entity-mix TV를 산출했다.

| scope | thickness KS | entity TV | drawings | pair offsets | read errors |
|---|---|---|---|---|---|
| aggregate | 0.062659021712 | 0.000833248782 | 150 | 110450 | 0 |
| S | 0.062532316731 | 0.000822052800 | 50 | 36800 | 0 |
| F | 0.062532316731 | 0.000822052800 | 50 | 36800 | 0 |
| M | 0.062912087836 | 0.000855632910 | 50 | 36850 | 0 |

소비자 표기는 같은 관측 수치를 서로 다른 prereg 정의에 연결할 뿐 판정을 내리지 않는다. Calibration 소비자에는 thickness-offset KS와 entity-type TV를 기록했다. Face 소비자에는 같은 reference-based entity TV와 함께 normalized primitive length, expected-pair axis degree, endpoint-gap의 tier간 KS/TV를 `fidelity_numbers.json`에 기록했다. 허용된 real aggregate에는 후자 세 분포의 원표본이 없으므로 real-vs-synthetic 값을 만들지 않았다.

## SEG-IR 곡선 근사 정책

- ARC: 균일 각도 chord, 최대 7.5° step.
- CIRCLE: 32개 균일 chord.
- SPLINE: ezdxf `BSpline.approximate`의 equal-parameter 4개 chord.
- 포함: LINE/LWPOLYLINE/POLYLINE/ARC/CIRCLE/SPLINE.
- 비선분 타입 3DFACE/ELLIPSE/HATCH/INSERT/MTEXT/POINT/TEXT/WIPEOUT은 pack에는 남아 있고 verifier SEG-IR에서는 생략했다.

## 검증기 전체-다양성 FAR/FRR 수치

150개 고유 도면마다 4개 perturbation ordinal을 사용했다. 참 complete-set claim은 도면당 동일하므로 총 600회지만 독립 topology 600개로 해석하지 않는다. 각 교란은 ordinal에 따라 제거/교체 handle이 달라지며 종별 600회다.

- full-metadata true claims: n=600, accept=600, reject=0, FRR=0.000000000
- full-metadata false claims: n=3600, accept=0, reject=3600, FAR=0.000000000
- name-blind true claims: n=600, accept=0, reject=600, FRR=1.000000000
- name-blind FRR delta: 1.000000000

### 교란 종별

| perturbation | n | accept | reject | FAR |
|---|---|---|---|---|
| wall_remove_single | 600 | 0 | 600 | 0.000000000 |
| wall_remove_pair | 600 | 0 | 600 | 0.000000000 |
| lure_add | 600 | 0 | 600 | 0.000000000 |
| neighbor_swap | 600 | 0 | 600 | 0.000000000 |
| pair_swap | 600 | 0 | 600 | 0.000000000 |
| orphan_add | 600 | 0 | 600 | 0.000000000 |

### 티어별

| tier | true n | FRR | false n | FAR | name-blind FRR |
|---|---|---|---|---|---|
| S | 200 | 0.000000000 | 1200 | 0.000000000 | 1.000000000 |
| F | 200 | 0.000000000 | 1200 | 0.000000000 | 1.000000000 |
| M | 200 | 0.000000000 | 1200 | 0.000000000 | 1.000000000 |

## 미해결과 해석 제한

- 600회 true/종별 false 계측은 150개 고유 도면에서 네 ordinal을 반복한 correlated claim 수다. gen2의 tier별 벽 topology도 seed마다 새 grammar가 아니라 고정 구조에 가깝다.
- name-blind arm은 layer metadata를 완전히 제거한다. verifier의 현재 `layer_metadata`와 candidate reconstruction 계약 때문에 변화 원인이 분리 가능하지만, 이 수치를 다른 name-blind 정의와 혼합하지 않는다.
- face 소비자의 real-corpus normalized-length/face-degree/endpoint-gap 원분포는 허용된 aggregate JSON에 없다. tier간 수치는 측정했지만 real-vs-synthetic face KS/TV는 만들지 않았다.
- HATCH 포셰, ELLIPSE, INSERT 내부 geometry 등은 full pack에는 존재하지만 이번 verifier SEG-IR adapter의 claim universe에는 들어가지 않는다.
- sample anomaly records: 0. 상세는 `verifier_far_frr_full.json`에 있다.
- 수치만 제공하며 fidelity band 또는 verifier 자격 결론은 이 셀에서 출력하지 않는다.

CELL_COMPLETE: fidelity_full
