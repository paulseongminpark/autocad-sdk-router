# F03 P6 C4 실코퍼스 raw-DXF 재구성 프로브

PREREG_SHA256: `d9b2004ebd057cffa8e70ac5a36eaf46268e0a602b2df60d1088b08a4bfc725b`

## 종결 판정

`BLOCKED_INPUT: 봉인된 판정식으로 구성·독립 검증된 cross-scope pair는 0개이며 패킷 최소치는 3개다 (확보 가능 쌍 수=0).`

- F03 실도면 밴드 결과: **BELOW_BAND — 0/10 (0.0%)**.
- 정본 밴드 `적격 def 중 ≥30%, 최소 3/10`을 충족하지 못했다.
- 따라서 이 코퍼스에서 **world-assembly 이득을 주장할 수 없다**.
- 이 판정은 World-IR 인프라 판정과 분리한다. 집중 재구성 자체는 `status=PASS`, 보존 원장은 `1280/1280`, 독립 endpoint parity는 `1280/1280 PASS`였다.

패킷은 허용 입력에서 최소 3개 쌍을 구성하지 못하면 `BLOCKED_INPUT`을 기록하도록 요구한다. 따라서 수치 밴드는 `BELOW_BAND`로 관측됐지만 패킷 종결 상태는 `BLOCKED_INPUT`이다. 0건을 PASS로 승격하지 않았다.

## 선봉인 프로토콜

수치 산출 전에 `PREREG_local.json`을 봉인했다. 선정·판정 규칙은 다음과 같다.

1. 허용된 5개 annotation source에서 같은 `(unit_id, def, handle)`을 지목한 source가 3개 이상인 handle만 consensus wall handle로 인정했다.
2. consensus handle이 raw DXF의 같은 block definition 안에서 실제 지원 primitive로 해석되는 def를 적격으로 삼았다.
3. `(unit_id UTF-8 bytes, def UTF-8 bytes)` 순으로 정렬하고 앞 10개를 결과 비열람 상태에서 고정했다.
4. 서로 다른 source definition의 placed segment만 cross-scope 후보로 삼았다. local 좌표끼리의 관계는 `UNKNOWN_SCOPE_INCOMPARABLE`로 보존하고 비교하지 않았다.
5. 공통 world frame에서 기존 `evidence_grid.py` 기본 계약을 그대로 적용했다: angle difference `≤2°`, longitudinal overlap ratio `≥0.5`, lateral offset `50–400 mm` (DXF `$INSUNITS=4`, 즉 `1 drawing unit=1 mm`).
6. World-IR 결과와 별도로 `insert_expand.py + normalize.py`가 동일 raw DXF에서 만든 `(source handle, INSERT path)` endpoint를 대조했다. 두 endpoint 모두 `1e-9 × max(1, absolute coordinate extent)` 이내이고 보존 원장이 PASS인 쌍만 성공으로 셌다.
7. threshold, 표본 순서, annotator fallback, pair fallback은 결과 확인 후 변경하지 않았다.

## 입력 무결성

| 입력 | SHA-256 / 상태 |
|---|---|
| `1_export.dxf` | `5a6035721630cddc6d753b1b97b898e7a4ce4d5988342ce85e2c465cdb81deff` |
| raw annotation 100-file manifest | `82be103a69fd55b89f5a8672f1c00f81be8474b29cdc9bf1ae5343cb73c5020d` |
| `worldir_oracle.py` | `f49417843726413667ead2be2b1e249100ddbce961d67a4d6f3600de78550a18` |
| `insert_expand.py` | `5e450d29026d9dcb78a702cb6859a6beed3a3ec07b984ec741c96be6e897e732` |
| `normalize.py` | `fbc4c86e88aca06e6be465ba131bbe839de1570b20582941a6162ff08549c1be` |
| `evidence_grid.py` | `918c6754c0b3d5608613c189240629dc419d94a42e167ef6ce0d298a08660b6a` |
| 전체 선봉인 입력 재검증 | mismatch `0` |

원본 DXF는 실행 전후 SHA-256, byte size `15,305,576`, `mtime_ns=1784295285215350300`이 모두 같았다. 원본 CAD/DXF 쓰기는 없었다.

## 수치 결과와 전건 근거

- annotation record key: `384`; wall handle가 하나 이상 있는 key: `95`; 3/5 consensus 적격 def: `49`.
- 결정론적으로 선택된 trial: `10`; modelspace 도달: `10/10`; 판정 가능: `10/10`.
- 집중 canonical graph: input template `406` (`206` primitive + `200` INSERT), 도달 INSERT placement `545`.
- World-IR: expected segment instance `1280`, emitted `1280`, delta `0`, discarded partial `0`, `conservation_ok=true`.
- 독립 raw-DXF 경로: 전체 nested segment `413,136` 중 consensus focus `1,280`; World-IR과 endpoint parity `1,280/1,280 PASS`; 최대 endpoint error `0.0`.
- array INSERT: `0`; array reference UNKNOWN 없음.
- 봉인된 world-pair predicate를 만족한 geometric candidate: `0`; 독립 검증 성공 pair: `0`.

| # | unit_id | def | consensus handles | placed segments | geometric pairs | verified pairs | trial status |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | `defannot-u132-143` | `*U132` | 2 | 8 | 0 | 0 | `FAIL_NO_CROSS_SCOPE_PAIR` |
| 2 | `defannot-u139-150` | `*U139` | 2 | 38 | 0 | 0 | `FAIL_NO_CROSS_SCOPE_PAIR` |
| 3 | `defannot-u140-151` | `*U140` | 2 | 8 | 0 | 0 | `FAIL_NO_CROSS_SCOPE_PAIR` |
| 4 | `defannot-u197-201` | `*U197` | 2 | 8 | 0 | 0 | `FAIL_NO_CROSS_SCOPE_PAIR` |
| 5 | `defannot-x-0-101co1-274` | `X-평면도(기본형)$0$101co1` | 9 | 27 | 0 | 0 | `FAIL_NO_CROSS_SCOPE_PAIR` |
| 6 | `defannot-x-0-101co1-rf-275` | `X-평면도(기본형)$0$101co1-RF` | 11 | 11 | 0 | 0 | `FAIL_NO_CROSS_SCOPE_PAIR` |
| 7 | `defannot-x-0-101co1-rf2-276` | `X-평면도(기본형)$0$101co1-RF2` | 11 | 11 | 0 | 0 | `FAIL_NO_CROSS_SCOPE_PAIR` |
| 8 | `defannot-x-0-101co2-278` | `X-평면도(기본형)$0$101co2` | 10 | 50 | 0 | 0 | `FAIL_NO_CROSS_SCOPE_PAIR` |
| 9 | `defannot-x-0-103co1-279` | `X-평면도(기본형)$0$103co1` | 12 | 12 | 0 | 0 | `FAIL_NO_CROSS_SCOPE_PAIR` |
| 10 | `defannot-x-0-104co1-280` | `X-평면도(기본형)$0$104co1` | 8 | 16 | 0 | 0 | `FAIL_NO_CROSS_SCOPE_PAIR` |

각 행의 원시 근거는 `D:\runs\e2_program\cells\f03_real_probe\trial_results.json`에 있고, 모든 1,280 endpoint 대조는 `segment_parity.json`, 빈 pair 전수 결과는 `pair_candidates.json`, 보존 원장은 `worldir_output.json`에 있다.

## UNKNOWN 보존

- 서로 다른 definition의 local 좌표는 공통 frame이 아니므로 사전 관계를 false로 두지 않고 전부 `UNKNOWN_SCOPE_INCOMPARABLE`로 유지했다.
- 선택된 10 trial은 모두 world frame에 도달했고 모든 focused segment에 독립 reference가 하나씩 존재했으므로, 선택 trial의 endpoint parity UNKNOWN은 `0`이었다.
- unsupported primitive, array ambiguity, missing reference를 PASS로 변환하지 않았다. 이 실행에서는 해당 UNKNOWN이 실제로 발생하지 않았다.

## Evidence 형식

요구된 `evidence.xlsx` 대신 `evidence.csv`를 산출했다. 이 세션에는 spreadsheet skill이 강제하는 `@oai/artifact-tool` dependency loader (`load_workspace_dependencies`)가 제공되지 않았다. 해당 skill은 dependency 경로 추측이나 `openpyxl`/`xlsxwriter` 대체 사용을 금지하며, 패킷은 XLSX 불가 시 CSV+사유를 명시적으로 허용한다.

- CSV: `reports/e2/cells/f03_real_probe/evidence.csv`
- CSV SHA-256: `ede32364d5d92aa23be71156b89896fd606d59dd7ba02b9ad2e2ee5dfb52c670`
- 행 수: `10` (trial당 1행)
- 사유 문서: `reports/e2/cells/f03_real_probe/EVIDENCE_FORMAT_REASON.md`

## 원시 산출물

모든 재구성 산출물은 요구된 staging 위치 `D:\runs\e2_program\cells\f03_real_probe\`에만 기록했다.

- `PREREG_local.json`
- `input_manifest.json`
- `annotation_consensus.json`
- `canonical_focus_input.json`
- `worldir_output.json`
- `reference_focus_segments.json`
- `segment_parity.json`
- `pair_candidates.json`
- `trial_results.json`
- `run_summary.json`
- `run_log.txt`
- `evidence.csv`

모델 API 호출, test-set 접근, git 명령, subagent 사용은 없었다.

AXIS_MEASUREMENT_COMPLETE
