# 루프 패킷 L1d — 합의 계산 구조 재설계 (입장 가드 폐기)

당신은 E2 프로그램의 계측기 수리 실행자다. L1c의 가드 방식 수리는 2차 사슬 검증단에 의해
기각됐다 — 우회 4종(display 제거·handle 재사용·GRID 위장·ratio-일치 위조), 가드 유발 신종
역전이(분모 청소: outlier 제거가 합의를 4/5→4/4로 올려 0.64→0.80 HIGH 돌파), 정당 입력
과차단(이중 치수 병기 장면의 HIGH 상실) 전부 라이브 실측. **먼저 읽어라 (READ-ONLY)**:
`D:\runs\e2_program\chainverify_L1c\SYNTHESIS.md` · `lens1_guard.md` · `seat4_sol.md`
(+ 프로브 하니스 `lens1_work\probe_guard.py`, `seat4_work\seat4_audit.py`).

## 수리 원칙 (계약 — 4원칙, SYNTHESIS의 직접 번역)

1. **입장 가드 폐기, 합의 계산 재설계**: 신규 `feyerabend_c1_v3.py` (원본·v2 모두 READ-ONLY).
   ① ratio mode 선택 **전에** z^mm 단위 정규화 (도시에 feyerabend_P2.md §2.3:205) — 1000MM≡1M
   이 같은 mode에 들게. ② n_independent = **고유 source handle 수** (도시에 §2.2.4) — 중복
   handle은 1로 접힘. ③ span 증거는 label-free 유지 (도시에 §2.4) — ratio 정합을 span 채택
   조건으로 결합 금지.
2. **단조성의 구조적 달성 — "의심 증거는 분모에만"**: 교차-공간 정합 실패 레코드(ratio-outlier
   등)는 모든 신뢰도 인자의 **분모(의심)에 남고 분자(지지)에 못 든다**. consensus 분수의 분모는
   전체 후보 레코드 집합에서 계산하며 어떤 경로로도 축소되지 않는다 — 레코드 제거·무시·위장이
   신뢰도를 올리는 경로 자체를 구조적으로 제거. REPORT에 이 단조성의 구조 논증(어느 인자가 왜
   비증가인지)을 수식으로 명시.
3. **검사기 무결 (이중 봉인 실물화)**: 실행 순서 = ① `prereg.json` 작성 ② `evidence_sealed.xlsx`
   (PREREG 시트) 작성 후 **불변 sidecar로 영구 보존**(이후 절대 재작성 금지 — 최종 증거는 별도
   `evidence.xlsx`) ③ 두 파일의 SHA-256을 실제 바이트에서 계산·기록 ④ 그 다음에야 추정기 코드
   작성. 검사기는 상수 반환 금지 — 모든 플래그는 관측값. L1c 검사기의 결함(SHA 불일치 시 시간
   검사 skip + True 상수)을 재현하지 말 것.
4. **속성 시험 문법 확장 + 함대 회귀 편입**: selftest에 ① 1차 함대 라이브 반례 ② lens1 B1~B4
   (probe_guard.py의 입력 재구성) ③ seat4 분모-청소 54-sweep ④ 혼합단위 정당 장면(O1)·stale
   라벨 장면(O2)의 **무손실 회귀**(원본 대비 status 하락 0) ⑤ 교란 문법에 display 제거·handle
   충돌·type 변경(GRID 위장) 추가한 고정시드 600종 속성 시험(전 필드 상승 0).

## 봉인 밴드 (도시에-유도 — prereg.json에 이대로)

- scale별 HIGH coverage ≥ 0.60 · HIGH 정확도 ≥ 0.95 (상대오차 ≤ 0.05) — 기존 유지.
- 교란 단조성 scope = **지정 mutation family 6종 + 함대 발견 class**(display-제거·handle-충돌·
  GRID-위장·분모-청소 sweep 전개·suffix/stale 변형) — 상승 허용 0.
- 과차단 무손실: 무교란 정당 장면(이중 치수 병기 포함)에서 원본 대비 status/coverage 하락 0.
- **B4(ratio-일치 완전 위조)는 게이트가 아니다** — 지지-계수 추정기의 정보이론적 한계로 문서화
  하고 그 효과를 측정·보고만 한다 (SYNTHESIS "자기 귀책 판정" 절 참조). "any perturbation"류
  문언 금지.

## 코호트 replay (eval-repair 거버넌스 — 개선 크레딧 없음)

v3로 ① L1b 200 ② C1 원본 200 전량 재평가 — v1·v2 대비 델타 표 전문. 정상 수치 변화는 숨기지
말고 전문 기록 (구조 재설계이므로 미세 변화 가능 — 변화 자체가 실격이 아니라 은폐가 실격).
26→0 유지 여부·함대 프로브 전 계열의 상승 0·무손실 회귀를 수치로.

## 산출물 (전부 `D:\runs\e2_program\cells\loop_l1d\` 에만 — repo 수정 금지)

`prereg.json` · `evidence_sealed.xlsx`(불변 sidecar) · `feyerabend_c1_v3.py` · `loop_l1d.py` ·
`c1v5_results.json` · `replay_delta.json` · `fleet_probe_results.json` · `evidence.xlsx` ·
`REPORT.md`(봉인 SHA 서두·구조 논증·selftest 전문·replay 델타 전문·B4 한계 측정·미해결,
마지막 줄 `LOOP_COMPLETE: L1d`)

수치만 — 게이트 판정 출력 금지. git 금지. 서브에이전트 금지. stdlib+numpy(+openpyxl). 원본 CAD·
test 접근 금지. 기존 산출물(c1/l1/l1b/l1c/chainverify) 수정 금지. 재현 주장은 "휘발 필드 제외
수치 전 필드 동일" 문구로만.
