# interior-100 status

interior-100 프로그램의 현재 상태 도시에(dossier). 측정 사다리, 아크 이력, 잔차(residue) 구성, 다음 레버를 커밋 SHA와 run id 기준으로 정리한다.

## Measurement ladder

기준: interior diff0/a_total on `1.dwg`, census sha `14eb65eb...`.

- R4m/R4n = 26,818/27,130 = **0.9884998**
- R4p (phase repair, commit `d261e44`) = **26,831**
- R4q (predefined-origin carriage) = **26,834**
- R4r (LEX-0008 orphan-assoc quotient 재측정) = **26,893** = 0.991264 — prereg 26,900 대역 [26,890, 26,910] 내 적중 (`reports/interior100/R4r_remeasure_lex0008.json`)
- R4s (LEX-0009 angle-branch + LEX-0008 게이트 확장, 측정 전용 재측정) = **26,916** = **0.992112** — prereg 26,916 대역 [26,914, 26,918] **정중앙 적중**, 가드 4/4 (`reports/interior100/R4s_remeasure_angle_branch.json`, prereg는 `prereg_R4s_angle_branch.json`)
- R4t (P2 수리 3종 재비행) = **27,098** = 0.998820 — prereg 대역 [27,105, 27,123] **FAIL-by-7**: H3 vintage +154·orphan-def sweep +28 착지, lw-z 무효과 = **stale-deploy 함정**(patch_engine이 prebuilt/<최신>을 src/bin보다 우선, 리빌드가 prebuilt 미갱신 → 07-09 crx로 비행). 수리: prebuilt 갱신 + 빌드스크립트 자동배포 (`reports/interior100/R4t_remeasure_vintage.json`)
- R4u (lw-z 재비행, 신선 prebuilt 첫 비행) = **27,057** = 0.997309 — prereg 대역 [27,118, 27,123] **FAIL**, per-def 가드 FAIL: lw-z **+25 정확 착지**(gainers가 예측 def에 정확 일치), 그러나 **−66 unmask** — 신선 crx가 6d59fd5의 loop-local 추출을 처음 실어 census가 66 해치의 per-loop 소스 핸들을 처음 방출(전원 in-def 해석: lwpolyline 63+spline 14, 미해석 0) → orphan 주장 반증·철회, 재구축이 연관성을 복원하지 않는 **실 결함**이 드러남. R4t 27,098은 눈먼 계기 수치; **27,057이 정직한 현행 기록** (`reports/interior100/R4u_remeasure_lwz.json`, prereg `prereg_R4u_lwz_reflight.json`)

## Arc history

- **Phase arc (R4o–R4r)**: R4o 무효런(LEX-0006) → R4p 2-사이트 수리(D1a/D2) → R4q 위상 물리 왕복 실증(LEX-0007) → R4r orphan-assoc 몫 입법(LEX-0008). 종결.
- **Residue arc P1 (R4s, 2026-07-10)**: "loops 표기" 정찰 가설을 전수 해부로 **반증**(LEX-0010) — loops-only는 7쌍뿐, 전부 점군 실측 기하 차이. 진짜 조성 확정 후 angle principal-branch 몫 입법(LEX-0009: ellipse 16 + DASH row 2π 4) + LEX-0008 구현 갭 봉합(SOLID 3). 재측정 26,916 정중앙 적중. 도구: `tools/loops_residue_analysis.py`(페어 캡처·점군 검증·collision test), `tools/remeasure_interior.py`(prereg 판정 러너, 가드 4종 내장).
- **Residue arc P2 (R4t–R4u, 2026-07-10)**: 재생 수리 3종(H3 `.pat` 세대별 분리 + lwpolyline elevation + orphan-def sweep). R4t FAIL-by-7이 **stale-deploy 함정** 적발(수리: prebuilt 자동배포). R4u 재비행이 lw-z +25 착지를 실증하는 동시에 **계기 업그레이드의 unmask −66**: 신선 crx의 loop-local 추출(6d59fd5)이 66 해치의 실재 소스를 처음 드러내 "orphan" 전제를 반증(`docs/ASSOC_ORPHAN_FINDING.md` 철회) — 재구축의 연관성 미복원이 실 결함으로 확정. FAIL 2건 모두 개명 없이 조사로 종결, 산출은 정직 기록 27,057.

## Residue composition — R4u 이후 (73 = 27,130 − 27,057)

전수 실측 (`reports/interior100/R4u_remeasure_lwz.json` + `assoc_source_resolve_probe`):

- **assoc 미복원 66** — REAL 재생 결함 (R4u가 unmask). census 66 해치 `is_associative=true` + per-loop `assoc_source_handles` 실재(in-def 해석 77/77: lwpolyline 63 + spline 14), post는 258/258 비연관 — 재구축이 setAssocObjIdsAt를 수행하지 않음. 수리 = P3 relink 아크.
- **loops 실기하 7** — 점군 max-NN ≥ 1e-3. 경계 재생 결함 후보, 별도 아크 (P3 뒤).

## Next levers (P3 — assoc relink + R4v 재비행)

1. append op에 `source_handle` 원장 추가 (`ir_to_patch`) — census→post 핸들 대응을 op↔result(`new_handle`)로 명시화.
2. op 스트림 말미에 `write.block.relink_hatch_assoc` 방출 (census 핸들 payload) — 전 소스가 이미 생성된 뒤 실행됨 (Step C 순서 충족).
3. `patch_engine`: 배치 결과에서 원장 축적 → relink job 방출 시 census→post 치환, 미해석은 loud FAIL.
4. 네이티브 핸들러: 핸들→ObjectId, `setAssociative(true)` + per-loop **id-derived loop 교체**(`removeLoopAt`+`insertLoopAt(int, type, AcDbObjectIdArray)` — ObjectARX 2027엔 per-loop assoc setter가 없음, id-derived insert 오버로드가 유일한 쓰기 경로) + `evaluateHatch` + 소스에 persistent reactor. 미니 E2E 프로브로 선검증 후 풀비행.
5. 측정: LEX-0011(candidate) — canonical payload = per-loop cardinality; 정확 대응 검증은 post-flight assoc audit(양측 IR join + kind multiset)으로.
6. prereg_R4v: 27,057 + 66 = **27,123** 대역 [27,118, 27,123] (천장 27,130 − loops 7) — 발사 전 커밋.

## E1 lane (동결 상태)

- E1 calibration 완료: ornith 383 + sonnet 20샤드 + wall_pairs 11,544 — 합치 0.549, 골든 리뷰 프로토콜 문서화 (`docs/E1_GOLDEN_REVIEW_PROTOCOL.md`, Paul 리뷰 대기).
