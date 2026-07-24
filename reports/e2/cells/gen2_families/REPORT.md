# gen2 family 다양화 셀 보고서

## 선행 이중 봉인

도면 생성과 충실도 계산 전에 셀 로컬 사전등록을 봉인했다.

| artifact | SHA-256 |
|---|---|
| prereg.json | 9fcf561fda3bc20f8aa68862fc013d3d8e1f91ba9511b2c13f82a2f0a9da7535 |
| PREREG.csv | 65c356d2c84cdccdec454e1fa48830894f43a52ce27af9621549a10857958b84 |

- `evidence.xlsx` 미생성 사유: 필수 `load_workspace_dependencies` capability가 이 executor에 노출되지 않았다. 패킷이 허용한 `PREREG.csv`를 사용했고 대체 스프레드시트 라이브러리는 사용하지 않았다.
- packet SHA-256: `b44be950a1237dfc4cb863021ac5a26bb6472c4fe82d718738ad86f7f00d5c06`
- amendment2 SHA-256: `6e29bbd5f8c502a1bc36277a535521c117408b2460e80511907d610321dd442a`
- read-only source hash 재검증: true

## 생성 팩

- family: 8
- family당 도면: 25
- 총 도면: 200
- tier 분포: S 67, F 67, M 66
- 진리 원장: 200; 모든 원장과 tier manifest entry에 `family_id` 기록
- 기존 `wall.v1`/`wall.v2.classes` 필드는 유지했고 family 필드는 additive extension으로만 추가했다.

| family | name | rooms | base walls | graph nodes | graph edges | cycle rank | oblique | opening walls | core signature |
|---|---|---|---|---|---|---|---|---|---|
| F01 | compact_five_room_spine | 5 | 8 | 12 | 16 | 5 | 0 | w05 | d3d5bd6df0ea46694fa465b3f92ed31e56f0918799450009ce442728f9529484 |
| F02 | six_room_offset_cross | 6 | 9 | 15 | 19 | 5 | 1 | w06, w03 | a57117153370565691d4389947b3319d34063db7924d3789044699b7d700b74c |
| F03 | seven_room_diagonal_branch | 7 | 10 | 17 | 21 | 5 | 2 | w05, w08 | 0ae8cdc0733fd9543f76af8cd0b5b8ea6cc94a660222d0f8764669c7d4ae5e9f |
| F04 | eight_room_longitudinal_bays | 8 | 11 | 18 | 25 | 8 | 0 | w07, w09, w02 | d65f4d91b58ac829d0f4d8e444174349f77548ce7b3e00738941b7d9cca26bf1 |
| F05 | nine_room_single_slant_court | 9 | 12 | 20 | 27 | 8 | 1 | w05, w10 | 4f1ea66293f5848b5cc849f7e6374d7955644550de08e0485903539eae0db77c |
| F06 | ten_room_double_slant_grid | 10 | 13 | 24 | 32 | 9 | 2 | w06, w11, w04 | db6e9a9a7c0472ad96e3723ecd4b36cae6c12fd3995c689a613ce45e40eedf4d |
| F07 | eleven_room_fan_branch | 11 | 14 | 27 | 35 | 9 | 3 | w05, w09, w12 | 3aa6a782098552d688cfa8e0c1f16e43b35ddfe44476b8e1d5d93792e701215b |
| F08 | twelve_room_mixed_angle_mesh | 12 | 15 | 27 | 36 | 10 | 4 | w06, w10, w13, w03 | 1312d6d761e04d5456c33470500742aafafafe15345dc4e1e09287e8f9a1b070 |

### family 설계 서술

- **F01 — compact_five_room_spine**: compact_five_room_spine: grammar BSP 5 rooms, 8 base walls, 0 oblique partitions, outer/inner thickness hierarchy 260/120|160|200 mm, openings attached to w05. Topology signature `0c9402a1685b045a214667e3cb38fdc4c8c1072c18b91e4966eee1d08ec3ae62`.
- **F02 — six_room_offset_cross**: six_room_offset_cross: grammar BSP 6 rooms, 9 base walls, 1 oblique partitions, outer/inner thickness hierarchy 300/100|180|220 mm, openings attached to w06, w03. Topology signature `555065554683a6553cbb92ecd94c9e28690d61cd8fc6ba8d9990232bb8be2eb1`.
- **F03 — seven_room_diagonal_branch**: seven_room_diagonal_branch: grammar BSP 7 rooms, 10 base walls, 2 oblique partitions, outer/inner thickness hierarchy 280/110|170|240 mm, openings attached to w05, w08. Topology signature `1624e9f0f3d0da0ea9d30459c6e88460d312ccf73752bb8ae897a12a5a3d3d8f`.
- **F04 — eight_room_longitudinal_bays**: eight_room_longitudinal_bays: grammar BSP 8 rooms, 11 base walls, 0 oblique partitions, outer/inner thickness hierarchy 320/120|150|210|250 mm, openings attached to w07, w09, w02. Topology signature `dbf694f690931012705806819bc8540c205774563e5b70be46ecf787bf970b85`.
- **F05 — nine_room_single_slant_court**: nine_room_single_slant_court: grammar BSP 9 rooms, 12 base walls, 1 oblique partitions, outer/inner thickness hierarchy 340/100|140|190|230 mm, openings attached to w05, w10. Topology signature `919c6127c9c97aeaae90e7bee46b5ce78845e7c513aaa9e9283f6a01b23e12e7`.
- **F06 — ten_room_double_slant_grid**: ten_room_double_slant_grid: grammar BSP 10 rooms, 13 base walls, 2 oblique partitions, outer/inner thickness hierarchy 360/110|160|200|260 mm, openings attached to w06, w11, w04. Topology signature `bc41a15033c15afb88b0da2af71ca7262e189374fc5112436194febcad559ccf`.
- **F07 — eleven_room_fan_branch**: eleven_room_fan_branch: grammar BSP 11 rooms, 14 base walls, 3 oblique partitions, outer/inner thickness hierarchy 380/120|170|220|280 mm, openings attached to w05, w09, w12. Topology signature `1f6f7daa03cb8356c622742ad05c1570d18520bb006c5e3f175acc5f5017689d`.
- **F08 — twelve_room_mixed_angle_mesh**: twelve_room_mixed_angle_mesh: grammar BSP 12 rooms, 15 base walls, 4 oblique partitions, outer/inner thickness hierarchy 400/100|150|210|270|310 mm, openings attached to w06, w10, w13, w03. Topology signature `7b4db8c07578a88724b0547e29f5a07eb1a56149a017a64a642428e6e2a5b05a`.

## distinctness 감사

차단된 GNN screen과 동일하게 w01–w08의 `id`, `axis`, `geometry_kind`, `thickness`, `thickness_range`, `variant`를 canonical JSON SHA-256으로 계산했다. 같은 family의 25개 원장은 각각 core signature 1개로 불변이고, family 간 28쌍은 모두 상이하다. 아래 행렬에서 `1`은 상이, 대각선은 `—`이다.

| family | F01 | F02 | F03 | F04 | F05 | F06 | F07 | F08 |
|---|---|---|---|---|---|---|---|---|
| F01 | — | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F02 | 1 | — | 1 | 1 | 1 | 1 | 1 | 1 |
| F03 | 1 | 1 | — | 1 | 1 | 1 | 1 | 1 |
| F04 | 1 | 1 | 1 | — | 1 | 1 | 1 | 1 |
| F05 | 1 | 1 | 1 | 1 | — | 1 | 1 | 1 |
| F06 | 1 | 1 | 1 | 1 | 1 | — | 1 | 1 |
| F07 | 1 | 1 | 1 | 1 | 1 | 1 | — | 1 |
| F08 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | — |

- 설계 시도: 1/3
- family 내부 단일 core signature: true
- family 간 상이: 28/28
- 6/2 split: train F01, F02, F03, F04, F05, F06; development F07, F08; overlap 0; assignment SHA-256 `d51463fcfeb7dadf68f34ba69d0e4a56ef5d991a581b04017ceae933ec95acbb`

## 충실도 수치

`fidelity_stats.py`의 parallel-pair-offset histogram KS와 entity-type TV만 산출했다. 아래 값에 대한 band 판정이나 gate verdict는 이 셀에서 출력하지 않는다.

| scope | thickness KS | entity TV | drawings | pair offsets | read errors |
|---|---|---|---|---|---|
| pooled-new vs real | 0.077563829623 | 0.000487365196 | 200 | 155554 | 0 |
| F01 vs real | 0.067507697308 | 0.000662172002 | 25 | 18733 | 0 |
| F02 vs real | 0.069329973820 | 0.000662172002 | 25 | 18858 | 0 |
| F03 vs real | 0.070483606293 | 0.000649195936 | 25 | 18938 | 0 |
| F04 vs real | 0.083398258411 | 0.000579708373 | 25 | 19708 | 0 |
| F05 vs real | 0.082935412069 | 0.000579708373 | 25 | 19733 | 0 |
| F06 vs real | 0.086228593733 | 0.000571292807 | 25 | 19877 | 0 |
| F07 vs real | 0.080776514438 | 0.000579708373 | 25 | 19683 | 0 |
| F08 vs real | 0.088419957155 | 0.000579708373 | 25 | 20024 | 0 |
| existing-single-family vs real | 0.062659021712 | 0.000833248782 | 150 | 110450 | 0 |

### pooled tier별 수치

| tier | thickness KS | entity TV | drawings | pair offsets | read errors |
|---|---|---|---|---|---|
| S | 0.077265702074 | 0.000567275848 | 67 | 52052 | 0 |
| F | 0.077362454594 | 0.000567275848 | 67 | 52071 | 0 |
| M | 0.078069437804 | 0.000626895770 | 66 | 51431 | 0 |

### 새 팩과 기존 단일-family 팩의 직접 분포 비교

- thickness histogram KS: `0.032474863001`
- entity-type TV: `0.000606556947`
- 새/기존 도면 수: 200/150
- 새/기존 parallel-pair offsets: 155554/110450

## selftest

- 결정성: 200/200 nonvolatile truth ledgers identical after same-seed regeneration. 주장 문안은 "All numeric and other nonvolatile truth-ledger fields are identical after same-seed regeneration; volatile runtime and timestamp fields are excluded."이다.
- `family_id` 무결: true (200장 전수)
- frozen graph config: `56911f4633979a3fe00fd56be2d0a39ac06757ed255ed49ed18ca20ba9d4ac49`

| family | tier | drawing | status | nodes | directed edges | missing wall handles | unresolved refs |
|---|---|---|---|---|---|---|---|
| F01 | S | f01_000 | ok | 2361 | 28340 | 0 | 0 |
| F02 | F | f02_000 | ok | 2361 | 28347 | 0 | 0 |
| F03 | M | f03_000 | ok | 2363 | 28370 | 0 | 0 |
| F04 | S | f04_000 | ok | 2372 | 28528 | 0 | 0 |
| F05 | F | f05_000 | ok | 2372 | 28536 | 0 | 0 |
| F06 | M | f06_000 | ok | 2374 | 28535 | 0 | 0 |
| F07 | S | f07_000 | ok | 2372 | 28482 | 0 | 0 |
| F08 | F | f08_000 | ok | 2372 | 28478 | 0 | 0 |

## 자원 및 접촉 기록

- process CPU: 0.251345 h / cap 8 h
- executor wall: 0.252241 h
- peak RSS: 0.091114 GiB / cap 48 GiB
- GPU 사용: 0
- 원본 CAD 접촉: 0
- CubiCasa val/test 접촉: 0/0
- repository 수정: 0
- Git operation: 0

## 미해결 및 해석 경계

- 이 셀은 fidelity 수치만 제공하며 band 판정 권한은 오케스트레이터에 남긴다.
- 기존 차단 기록의 `gnn_e2.py`는 historical 150-drawing root와 tier당 50장 guard를 고정한다. 새 팩은 기존 manifest/truth schema를 유지하고 graph builder는 무수정으로 8/8 표본을 읽었지만, 후속 GNN 재스크린 실행자는 새 root와 67/67/66 tier cardinality를 실행 입력으로 지정해야 한다.
- `NEXT`는 사용자 조치가 아니라 미래 executor 권고다: 이 8-family pack으로 seed 17 family-disjoint GNN screen을 별도 packet에서 재실행한다.

## Closeout

- STATUS: COMPLETE (cell artifact completion only; no fidelity gate verdict)
- FILES_CHANGED: `D:\runs\e2_program\cells\gen2_families\` 아래 신규 산출물만 생성
- STATE_DELTA: one-family blocker를 해소할 8개 family, 200장, 6/2 split 증거를 생성
- PROTECTED_PATHS: repo, 원본 CAD, CubiCasa val/test, 기존 셀 산출물 모두 hash-stable/read-only
- BLOCKERS: 없음; evidence workbook은 packet-authorized CSV fallback으로 기록
- NEXT: future executor가 새 pack으로 family-disjoint GNN screen을 실행
- HANDOFF_PATH: `D:\runs\e2_program\cells\gen2_families\handoff\gen2_families_handoff.zip`

CELL_COMPLETE: gen2_families
