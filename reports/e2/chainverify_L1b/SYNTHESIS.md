# 오케스트레이터 종합 판정 — L1b 사슬 검증 (4석 함대)

판정자: Fable 5 (오케스트레이터). 함대: aclaude-d fable ×3 (lens1 데이터/누출 · lens2 통계/방법론 ·
lens3 코드/재현) + acodex gpt-5.6-sol ultra (seat4 전면 감사). 평결: CONFIRM 2 / REFUTE 2.

## 종합 평결: 주장 문안 RETRACTED — 수치 실질 CONFIRMED — 루프 미종결 (L1c 진입)

### 살아남은 것 (4석 전원 독립 재현)

봉인 밴드의 측정부 전체: HIGH coverage 0.80/scale · HIGH 정확도 160/160=1.0 (최대 상대오차
3.11e-15) · family 구조 witness 11/11 · KS 0.0403 / TV 0.000212 · truth integrity 0 ·
label blindness (bridge key = anchors 단독) · 이 모집단에서 교란 역전이 0 · 밴드 불이동 ·
루프 경로 정직 (L1 기각 이력 포함). 함대는 seat4의 stdlib 독립 재구현까지 포함해 이 수치들을
원 코드 경로 밖에서 재계산했다.

### 반증된 것 (수용 — 3건)

1. **⑥ "역방향 전이 티켓 수리 확인" = FALSE.** lens2가 라이브 반례로 증명: single-outlier 교란
   앵커는 ratio 공간 outlier이나 span 공간 inlier여서 reference 합의의 n·bins를 불리고, 점수 공식
   (feyerabend_c1.py:320-325)이 0.60→0.80으로 문턱 0.75를 넘어 보조 status가 상승한다 (:440).
   L1b의 0건은 수리가 아니라 **모집단이 그 입력 형태를 제거**한 결과다 (anchor-rich = 8 distinct
   span → reference 합의 미형성; single-span n=2<3). 결함은 봉인 추정기에 잠복 중.
2. **⑦ "재실행 바이트 동일" = 원리적 성립 불가.** seat4 이중 전량 재실행: 204 파일 중 201 동일,
   3 불일치 (REPORT.md / c1v3_results.json / evidence.xlsx — runtime 필드 + docProps 타임스탬프).
   수치 콘텐츠는 100% 동일. 정정 문구: "장면·c0v3 바이트 동일 + 수치 전 필드 동일 (휘발 필드 제외)".
3. **CRITICAL-2 — 이중 사전봉인 산출물 부재.** 도시에 feyerabend_P2.md:738-740이 요구하는
   prereg.json + evidence.xlsx PREREG 시트가 C0→L1b 전 사슬에 0개. 완화 사실 (문면 준수 주장
   아님): 밴드를 담은 도시에가 실행 전 git 커밋됨 (@e3bf728 — 시간적 선행 증거). 절차 자체는
   미충족이며 L1c부터 복원한다.

### MEDIUM (해석 범위 제한 — 기각 아님)

clean HIGH 정확도 1.0은 생성 규칙상 구성적 예정 (display=span). 합성 팩에서의 계측 자격이지
실도면 난이도 증거가 아니다 — 실전 시험은 DIM C4 실도면 접촉 시점.

## 집행

- L1c 패킷 발사: 추정기 교란 단조성 수리 (신규 v2, 원본 READ-ONLY) + lens2 반례 회귀 편입 +
  이중 봉인 선행 + L1b/C1 코호트 replay (eval-repair 거버넌스 — 개선 크레딧 없음).
- 저널 정정: ⑥·⑦ 원 문안 RETRACTED, 정정 진술로 교체.
- 거버넌스: 이중 봉인 의무를 prereg amendment2로 성문화 (전 향후 셀).
- C2 (다음 discrimination 셀 개방)는 L1c replay 통과까지 폐쇄 유지.

사슬 검증 독트린("검증은 처음부터 그 단계까지")의 첫 발사가 잠복 결함 1건 + 절차 공백 1건을
적중했다 — 제도가 설계 목적대로 작동했다.
