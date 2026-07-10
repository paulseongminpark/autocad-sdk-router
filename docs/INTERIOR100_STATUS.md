# interior-100 status

interior-100 프로그램의 현재 상태 도시에(dossier). 측정 사다리, 아크 이력, 잔차(residue) 구성, 다음 레버를 커밋 SHA와 run id 기준으로 정리한다.

## Measurement ladder

기준: interior diff0/a_total on `1.dwg`, census sha `14eb65eb...`.

- R4m/R4n = 26,818/27,130 = **0.9884998**
- R4p (phase repair, commit `d261e44`) = **26,831**
- R4q (predefined-origin carriage) = **26,834**
- R4r (LEX-0008 orphan-assoc quotient 재측정) = **26,893** = 0.991264 — prereg 26,900 대역 [26,890, 26,910] 내 적중 (`reports/interior100/R4r_remeasure_lex0008.json`)
- R4s (LEX-0009 angle-branch + LEX-0008 게이트 확장, 측정 전용 재측정) = **26,916** = **0.992112** — prereg 26,916 대역 [26,914, 26,918] **정중앙 적중**, 가드 4/4 (`reports/interior100/R4s_remeasure_angle_branch.json`, prereg는 `prereg_R4s_angle_branch.json`)

## Arc history

- **Phase arc (R4o–R4r)**: R4o 무효런(LEX-0006) → R4p 2-사이트 수리(D1a/D2) → R4q 위상 물리 왕복 실증(LEX-0007) → R4r orphan-assoc 몫 입법(LEX-0008). 종결.
- **Residue arc P1 (R4s, 2026-07-10)**: "loops 표기" 정찰 가설을 전수 해부로 **반증**(LEX-0010) — loops-only는 7쌍뿐, 전부 점군 실측 기하 차이. 진짜 조성 확정 후 angle principal-branch 몫 입법(LEX-0009: ellipse 16 + DASH row 2π 4) + LEX-0008 구현 갭 봉합(SOLID 3). 재측정 26,916 정중앙 적중. 도구: `tools/loops_residue_analysis.py`(페어 캡처·점군 검증·collision test), `tools/remeasure_interior.py`(prereg 판정 러너, 가드 4종 내장).

## Residue composition — R4s 이후 (214 = 27,130 − 26,916)

전수 실측 (`reports/interior100/loops_residue_analysis_R4s.json` + dissection):

- **H3 pattern-vintage clobber 154** — REAL 재생 결함. census의 H3는 4세대 혼재(X-그리드 45°/135° ×154, +-그리드 3표기 ×27)인데 `.pat`가 배치당 NAME당 1개(최초 조우 시드)로 합성되어 시드 세대가 전부를 덮어씀 (`patch_engine._synthesize_batch_pat_files`). X-해치가 +-해치로 렌더 변경 — 측정 입법 불가, 수리+재비행 대상.
- **lwpolyline z 소실 25** — REAL 재생 결함. census vertex z=0.4010621945564553이 0.0으로 평탄화 (blocks.py lwpolyline 브랜치가 elevation 미운반 + m08e lwpolyline 브랜치에 setElevation 부재).
- **loops 실기하 7** — 점군 max-NN ≥ 1e-3. 경계 재생 결함 후보, 별도 아크.
- **removed 28** — DIMDOT 3 + LWPOLYLINE 4 + LINE 21 (b측 부재). 사유 조사 = P2.

## Next levers (P2 — 재생 수리 + R4t 재비행)

1. `.pat` 세대별 분리: `_synthesize_batch_pat_files`를 (NAME, zero-phase 콘텐츠 해시)별 파일로 — leaf 이름은 `<NAME>.pat` 유지(cwd 해석), 디렉토리로 분리. 엔진 name-cache 리스크는 2-세대 프로브 잡으로 선판정 (m08e는 해치마다 CopyFileW 무조건 재복사라 구조상 가능).
2. lwpolyline elevation 운반: blocks.py(공통 vertex z → elevation) + m08e lwpolyline setElevation (C++ 리빌드 필요).
3. removed-28 사유 조사 (`runs/e2e_1dwg_R4r_assoc_20260710/deferred.json`).
4. R4t prereg → capstone 재비행 → `tools/remeasure_interior.py` 판정.

## E1 lane (동결 상태)

- E1 calibration 완료: ornith 383 + sonnet 20샤드 + wall_pairs 11,544 — 합치 0.549, 골든 리뷰 프로토콜 문서화 (`docs/E1_GOLDEN_REVIEW_PROTOCOL.md`, Paul 리뷰 대기).
