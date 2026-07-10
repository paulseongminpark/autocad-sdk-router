# interior-100 status

interior-100 프로그램의 현재 상태 도시에(dossier). 측정 사다리, 위상(phase) 아크, 잔차(residue) 구성, 다음 레버를 커밋 SHA와 run id 기준으로 정리한다.

## Measurement ladder

기준: interior diff0/a_total on `1.dwg`, census sha `14eb65eb...`.

- R4m/R4n = 26,818/27,130 = **0.9884998**
- R4p (phase repair, commit `d261e44`) = **26,831**
- R4q (predefined-origin carriage) = **26,834**
- R4r IN FLIGHT — prereg point **26,900**, band **[26,890, 26,910]** (assoc-flag replay, commit `6d59fd5`)

## Phase arc (R4o-R4r)

- **R4o** — INVALID run. `--dwg` 없이 launch되어 `native_sample.dwg`(= input0616)를 대상으로 실행됨. population forensics + `identity.json`으로 포착, `LEX-0006`으로 기록.
- **R4p** (commit `d261e44`) — 두 지점(two-site) 결함 발견:
  - D1a: predefined-name 패턴(`DASH` x66)이 origin fold가 serialized entity에서 행(row)을 읽는 과정에서 위상(phase)을 잃음.
  - D2: canonical divisor가 `pattern_type`을 그대로 신뢰함.
- **R4q** (predefined-origin carriage) — 위상이 물리적으로 round-trip됨을 증명. 생존한 DASH 쌍의 canonical geometry diff == `is_associative`만 남음 (`LEX-0007`).
- **R4r** — IN FLIGHT, assoc-flag replay 기반 adjudication 대기 (commit `6d59fd5`).

### Orphan-assoc finding (2026-07-10)

`is_associative`인 66개 hatch가 어디에도 boundary source ref를 가지고 있지 않음:
- ObjectARX `getAssocObjIds`와 `getAssocObjIdsAt` 모두 0/66으로 읽힘.
- LibreDWG DXF projection에서도 group 97/330 ref가 나타나지 않음.

faithful replay = flag만 복사 (`setAssociative`), commit `6d59fd5`에 구현됨.

## Residue composition

R4q 이후 (residue_tail_report 기준):

- assoc class **66** (59 phase-overlap + 4 + 3)
- loops **7**
- phase-only **3**
- removed **28**
- 별도로, non-hatch modified tail이 forensic decomposition 진행 중 (`tools/modified_composition.py`, report pending)

## Next levers

- R4r adjudication (prereg 26,900, band [26,890, 26,910] 검증)
- modified-composition forensics 완료
- E1 calibration: ornith 383 + sonnet second pass + wall_pairs 11,544 deterministic claims over 407 defs
