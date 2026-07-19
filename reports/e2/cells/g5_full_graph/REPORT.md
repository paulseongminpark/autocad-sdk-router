# G5 full-graph 무샘플링 계측 REPORT

## 승계 봉인

- 승계 봉인 `prereg.json` SHA-256: `44a06ba6620d77bd2430bdc9cc0d52ababac1465dcf69c207c5381df037a1bf7`
- 승계 봉인 `PREREG.csv` SHA-256: `6dd37584767469dc36d294fdb295fc5904a42eb3768d4f731b307a7bd6239bd5`
- 재봉인·수정: `0`회
- claim_policy: `휘발 필드(runtime·타임스탬프) 제외 수치 전 필드 동일`
- 판정 정책: 수치 계측만 기록; 봉투/동등성 판정 미출력.

## 실행 범위

- 상태: `COMPLETE`
- 대상 def: `X-평면도(기본형)`
- 입력 선분 수: `412,775`
- sampling: `0`; retraining: `0`; accuracy claim: `0`.
- 입력은 기존 staged DXF, frozen graph builder, 3개 GNN-A checkpoint, 봉인 val-A SEG-IR 1개로 제한.

## DGX 점유 기록

- 최초 SSH 실호출 UTC: `2026-07-19T00:48:13Z`
- 최초 :8000 HTTP 상태: `PREEXISTING_UNREACHABLE`
- 최초 container 상태: `exited|exit=0|finished=2026-07-18T12:58:33.301940483Z`
- 실행 전 host available bytes: `120,454,250,496`
- vLLM stop 명령: `NOT_ISSUED_PREEXISTING_DOWN`
- vLLM restart 명령: `NOT_ISSUED_NO_CELL_STOP_ACTION`
- 실행 후 :8000 HTTP reachable: `False`
- DGX container launch: `docker run --rm --name g5_full_graph_20260719T004638Z --gpus all --ipc=host --network=host -v '/home/sunapse/g5_full_graph_20260719T004638Z:/workspace' -w /workspace nvcr.io/nvidia/pytorch:25.04-py3 timeout --signal=TERM --kill-after=60s 36h bash -lc 'python -m pip install --disable-pip-version-check --no-cache-dir -q ezdxf==1.4.3 && exec python /workspace/g5_full_graph.py dgx --builder /workspace/graph_builder.py --architecture /workspace/gnn_e2_v2.py --checkpoint-dir /workspace/ckpt --prereg /workspace/prereg.json --prereg-csv /workspace/PREREG.csv --dxf /workspace/1_export.dxf --reference /workspace/high_quality_architectural_6347.segir.json --output /workspace/_dgx_raw.json --vllm-probe-url http://127.0.0.1:8000/v1/models'`
- remote cleanup: `test exact target /home/sunapse/g5_full_graph_20260719T004638Z; verify no g5_full_graph_20260719T004638Z container; inventory; rm -rf -- /home/sunapse/g5_full_graph_20260719T004638Z; verify absent`

## full-graph 구축 수치

| metric | value |
|---|---:|
| node_count | 412,427 |
| directed_edge_count | 6,047,119 |
| build_wall_seconds | 574.270247 |
| dxf_read_wall_seconds | 1.4757748 |
| seg_ir_expand_wall_seconds | 2.19640175 |
| typed_graph_build_wall_seconds | 570.265579 |
| peak_host_rss_bytes | 3,873,734,656 |
| graph_hash | `1e8060f9b0fa640471a57b5317a749ddde9b6ce5cf311fecb49038f11e0ea6ed` |
| config_hash | `56911f4633979a3fe00fd56be2d0a39ac06757ed255ed49ed18ca20ba9d4ac49` |

## 무샘플링 inference 수치

| seed | forward_s | nodes/s | empirical_p95_s (n=1) | peak_cuda_alloc_B | peak_cuda_reserved_B | peak_host_rss_B | positive_ratio@0.5 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 1.54097026 | 267641.115 | 1.54097026 | 1,664,444,416 | 2,621,440,000 | 2,734,665,728 | 0.0985410751 |
| 29 | 0.379930202 | 1085533.6 | 0.379930202 | 1,664,444,416 | 2,621,440,000 | 2,743,046,144 | 0.110281335 |
| 43 | 0.379169083 | 1087712.63 | 0.379169083 | 1,664,444,416 | 2,621,440,000 | 2,747,998,208 | 0.0710307521 |

## 출력 분포 수치

| seed | min | p01 | p05 | p25 | p50 | p75 | p95 | p99 | max | mean | std_population |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 1.47113643e-09 | 6.24239503e-05 | 0.000512174756 | 0.00533160078 | 0.0188557785 | 0.0750916637 | 0.751241332 | 0.951772138 | 0.999827087 | 0.11997396 | 0.231553094 |
| 29 | 5.42983573e-13 | 2.38660349e-06 | 0.00116296572 | 0.0874848329 | 0.18269147 | 0.306540102 | 0.713077521 | 0.9215338 | 0.999895334 | 0.23255931 | 0.209164446 |
| 43 | 2.07081249e-12 | 2.20597257e-05 | 0.00188425169 | 0.0196774462 | 0.0504896156 | 0.13771566 | 0.623119456 | 0.90815533 | 0.999984622 | 0.128594403 | 0.195329085 |

## 시드 간 일치도 수치

- seed 17↔29 binary agreement: `0.903192565`
- seed 17↔43 binary agreement: `0.924345399`
- seed 29↔43 binary agreement: `0.907246616`
- three-seed unanimous ratio: `0.86739229`

## 장치 간 동등성 입력 수치 (판정 없음)

- reference drawing_id: `high_quality_architectural_6347`
- rule: `abs≤max(1e-4, 5×p99_within) ∧ rel≤max(1e-3, 5×p99_within)`

| metric | value |
|---|---:|
| local_within_max_abs | 5.36441803e-07 |
| local_within_p99_abs | 1.1920929e-07 |
| local_within_max_rel | 3.89860937e-06 |
| local_within_p99_rel | 2.08568871e-06 |
| dgx_within_max_abs | 6.07222319e-07 |
| dgx_within_p99_abs | 0 |
| dgx_within_max_rel | 0.000308835871 |
| dgx_within_p99_rel | 0 |
| cross_device_max_abs | 0.00864252448 |
| cross_device_p99_abs | 0.000961672068 |
| cross_device_max_rel | 0.0246235624 |
| cross_device_p99_rel | 0.0208271413 |
| sealed_absolute_limit | 0.0001 |
| sealed_relative_limit | 0.001 |

## selftest / 불변성

- same-input forward max_abs: `0`
- forbidden filesystem calls: `0`
- blocked-before-filesystem kinds: `original_CAD, test, val_A_truth, val_B`
- checkpoint SHA-256 before/after: 동일 문자열 기록.
- adopted seal SHA-256 before/after: 동일 문자열 기록.

## 증거 파일

- `evidence.csv` fallback reason: Required spreadsheet artifact dependency loader unavailable in this execution session; original packet CSV fallback applied and stricter adopted-seal xlsx requirement recorded unresolved.

## 미해결

- 원 패킷은 Ornith-35B vLLM(:8000)이 실행 중이라고 기술했으나, 착수 전 SSH/HTTP 실측에서 `vllm-qwen` container는 이미 exited(0), :8000은 unreachable이었다. 본 셀은 stop/restart 명령을 발행하지 않았다.
- 승계 봉인은 `val_A_truth`를 추가 금지한다. 원 패킷보다 엄격한 봉인 문언을 적용했고 truth 접근은 0이다.
- 봉인 output_policy는 `evidence.xlsx`를 요구하지만 필수 spreadsheet artifact dependency loader가 이 실행 세션에 없어 원 패킷이 허용한 CSV fallback을 사용했다. 이 충돌은 봉인 우선 규약상 unresolved로 유지한다.
- `single_sample_empirical_p95_seconds`는 봉인 필드명대로 seed당 단일 forward 표본의 empirical p95이며 표본 수는 1이다.

CELL_COMPLETE: g5_full_graph
