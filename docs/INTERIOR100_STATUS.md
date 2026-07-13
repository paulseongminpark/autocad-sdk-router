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
- R4u (lw-z 재비행, 신선 prebuilt 첫 비행) = **27,057** = 0.997309 — prereg 대역 [27,118, 27,123] **FAIL**, per-def 가드 FAIL: lw-z **+25 정확 착지**(gainers가 예측 def에 정확 일치), 그러나 **−66 unmask** — 신선 crx가 6d59fd5의 loop-local 추출을 처음 실어 census가 66 해치의 per-loop 소스 핸들을 처음 방출(전원 in-def 해석: lwpolyline 63+spline 14, 미해석 0) → orphan 주장 반증·철회, 재구축이 연관성을 복원하지 않는 **실 결함**이 드러남. R4t 27,098은 눈먼 계기 수치; 27,057이 당시의 정직 기록 (`reports/interior100/R4u_remeasure_lwz.json`, prereg `prereg_R4u_lwz_reflight.json`)
- R4v (P3 assoc relink 비행, commit `37c6480`) = **27,116** = 0.999484 — prereg 대역 [27,118, 27,123] **FAIL-by-2**, 가드 4/4 OK(per-def 무회귀 포함): relink 기계 자체는 **66/66 성공**(op ok + `associative_after=true`), +59 순증. 미달 2+5는 수리가 unmask한 loop 표기 드리프트 — 해부로 3클래스 확정: **회전 5**(점군 0.0, LEX-0012로 입법) + **spline Bézier 재분해 2**(prereg 리스크 레지스터 항목 발화; 곡선 동일 9.2e-4, 수용 잔차) + 구 실기하 7. LEX-0011은 fold 증거(59/66, 오접힘 0)로 legislated — 런 판정은 FAIL 유지 (`reports/interior100/R4v_remeasure_assoc.json`, 해부 `loops_residue_analysis_R4v.json`)
- R4w (LEX-0012 측정 전용 재측정, prereg 커밋 `c51def8` 후 실행) = **27,121** = **0.999668** — prereg **점 대역 [27,121, 27,121] 정확 명중**, 가드 4/4 (`reports/interior100/R4w_remeasure_lex0012.json`, prereg `prereg_R4w_lex0012.json`).
- R4x (ccw flag-parse 수리 재비행, prereg 커밋 `263f0ff` 후 발사) = **27,128** = **0.999926** — prereg 27,128 대역 [27,126, 27,128] **정확 명중**, 가드 4/4 (`reports/interior100/R4x_remeasure_ccw.json`, prereg `prereg_R4x_ccw_flagparse.json`). **실기하 잔차 소멸**(재해부 geom_diff=0, `loops_residue_analysis_R4x.json`) — 잔차 2 = spline Bézier 재분해 쌍(1BDF/1BE6, 곡선 동일 9.2e-4)뿐. **forward fingerprint 천장 도달: 재구축 도면이 원본과 기하학적으로 완전 동치.**

## Idempotence 축 (내부 고정점, forward와 직교) — 2026-07-13

forward 충실도(census 1.dwg vs 재구축)와 별개로, **재구축을 재처리하면 변하는가**(gen1→gen2 고정점)를 측정. 설계 P6의 "무손실 증명".

- **GEN2c** (R4x 파이프라인 첫 고정점 측정) = `fixed_point=False`, interior **26,947/27,130 = 0.9933**, 13 hatch def drift. modelspace 엔티티는 완전 고정점(0/0/0)이나 블록 내부 hatch 패턴이 재생성마다 40×(=pattern_scale) 축소. (ultracode 워크플로 `wf_da1ab407` 3-suspect 근인 규명.)
- **근인 (empirical, gen0/gen1/gen2 + 실 .pat 대조)**: `.pat` 합성기(`patch_engine.py:_pattern_definition_line`)가 census offset을 pattern_scale로 나눔 — 이 baking 가정은 원본(kPreDefined type=1)에만 참, 재구축 hatch(setPattern kCustomDefined→type=2, census가 raw로 읽음)엔 이중적용. **DASH 대조군 drift 0으로 증명.** 수정: divide를 `pattern_type≤1`에만 게이트 (commit `b939f8d`).
- **GEN2d** (수정 재비행) = 26,947→**27,129**, 13→1 dirty def. 잔차 1 = ellipse hd1050/853의 full-ellipse 2π 브랜치 float knife-edge(gen1 end−start=2π+1.8e-15→~0 vs gen2 2π−2e-15→~2π; LEX-0009 `sweep==0.0` 가드가 한쪽 empty·한쪽 full로 접음).
- **최종** (robust full-ellipse fold, LEX-0009 확장, commit 후속) = 측정 전용 재-diff **27,130/27,130 = 1.0, fixed_point=TRUE, dirty def 0** (`reports/interior100/GEN2d_idempotence_remeasure.json`). forward R4x는 delta +0(27,128) 무회귀. **파이프라인이 진짜 내부 고정점 — 재구축 도면을 재처리해도 변하지 않음.**

## Arc history

- **Phase arc (R4o–R4r)**: R4o 무효런(LEX-0006) → R4p 2-사이트 수리(D1a/D2) → R4q 위상 물리 왕복 실증(LEX-0007) → R4r orphan-assoc 몫 입법(LEX-0008). 종결.
- **Residue arc P1 (R4s, 2026-07-10)**: "loops 표기" 정찰 가설을 전수 해부로 **반증**(LEX-0010) — loops-only는 7쌍뿐, 전부 점군 실측 기하 차이. 진짜 조성 확정 후 angle principal-branch 몫 입법(LEX-0009: ellipse 16 + DASH row 2π 4) + LEX-0008 구현 갭 봉합(SOLID 3). 재측정 26,916 정중앙 적중. 도구: `tools/loops_residue_analysis.py`(페어 캡처·점군 검증·collision test), `tools/remeasure_interior.py`(prereg 판정 러너, 가드 4종 내장).
- **Residue arc P2 (R4t–R4u, 2026-07-10)**: 재생 수리 3종(H3 `.pat` 세대별 분리 + lwpolyline elevation + orphan-def sweep). R4t FAIL-by-7이 **stale-deploy 함정** 적발(수리: prebuilt 자동배포). R4u 재비행이 lw-z +25 착지를 실증하는 동시에 **계기 업그레이드의 unmask −66**: 신선 crx의 loop-local 추출(6d59fd5)이 66 해치의 실재 소스를 처음 드러내 "orphan" 전제를 반증(`docs/ASSOC_ORPHAN_FINDING.md` 철회) — 재구축의 연관성 미복원이 실 결함으로 확정. FAIL 2건 모두 개명 없이 조사로 종결, 산출은 정직 기록 27,057.
- **Residue arc P3 (R4v–R4w, 2026-07-11, commits `37c6480`→`c51def8`)**: assoc relink 전 사슬 구현(append `source` 원장 → 엔진 census→rebuilt 치환, 미해석 loud FAIL → 배치 플래너 relink 배리어 → 네이티브 id-derived loop 교체 `removeLoopAt`+`insertLoopAt(int, type, ids)`+`evaluateHatch`+persistent reactor). R4v 비행: relink **66/66 기계 성공**, +59, FAIL-by-2 — 수리가 unmask한 표기 드리프트를 쌍 단위 전수 해부(분석기의 dict-vertex 파싱 갭 수리가 선행 — 5쌍은 "측정 안 됨"이었지 "기하 차이"가 아니었음): 회전 5(점군 0.0) + spline 재분해 2(곡선 동일) + 구 실기하 7. **LEX-0012 입법**(closed cycle의 직렬화 시작점 = 표기; dup-drop + rotation-minimal + 6dp 방출, LEX-0010의 재개 조건 발화) 후 R4w 측정 전용 재측정이 점 대역 정확 명중. FAIL은 개명 없이 조사로 종결.

## Residue composition — R4x 이후 (2 = 27,130 − 27,128, 전원 판별 완료)

전수 실측 (`reports/interior100/loops_residue_analysis_R4x.json`): loops_only=2, **geom_diff=0**.

- **spline Bézier 재분해 2** (1BDF/1BE6, dA로고) — census 다중스팬 spline 3/1 엣지 vs post 스팬별 Bézier 9/3 엣지: `evaluateHatch`가 재파생하며 분해. 곡선 동일(control-net 점군 프록시 9.2e-4, 도면 스케일 수천 단위). Bézier 추출 정규화는 2쌍 대비 블라인드 리스크 과대 — fingerprint 밖 수용 잔차로 문서화(대체검증 담당).

## Arc P4 종결 (R4x, 2026-07-11, commit `263f0ff`)

구 loops-7 "실기하" 잔차의 근인 = **m08eFindFlag boolean 파싱 결함**: `jsonFindNumber`가 non-numeric을 거부하지 못해(`strtod("true")`→0.0+found) boolean 분기가 죽은 코드 — 네이티브 job의 모든 JSON boolean 플래그가 false로 읽힘. 1.dwg 실피해는 hatch arc 엣지 `ccw` 단일(census ccw=true 11 arc = 정확히 7쌍, 전수 회계 완결; census ccw=false 3 arc는 무사 왕복). entity `closed`는 Python의 0/1 숫자 직렬화로 우연 회피(539/539), rational 110/110 false, is_solid_fill은 SOLID fallback 수렴으로 무피해. 부수 정정: R4u의 assoc "job true→saved false" 관찰 = 이 파싱 버그(원장 LEX-0008 메커니즘 각주). 수리 = boolean-literal-first 재배열(`m08eReadFlagArray`의 기존 올바른 이디엄), 미니 E2E 프로브(ccw 왕복+create-시 assoc 실적용) PASS 후 재비행 정확 명중.

## Next (Paul 결재 대상)

1. **잔여 결정 1건**: spline Bézier 재분해 2쌍 — 수용 잔차 유지(현 상태, 대체검증 문서화 완료) vs Bézier 추출 정규화 입법(블라인드 리스크 평가 필요). 현행 판단: 유지.
2. E1 골든 리뷰 (`docs/E1_GOLDEN_REVIEW_PROTOCOL.md`, Paul 리뷰 대기).

## E1 lane (동결 상태)

- E1 calibration 완료: ornith 383 + sonnet 20샤드 + wall_pairs 11,544 — 합치 0.549, 골든 리뷰 프로토콜 문서화 (`docs/E1_GOLDEN_REVIEW_PROTOCOL.md`, Paul 리뷰 대기).
