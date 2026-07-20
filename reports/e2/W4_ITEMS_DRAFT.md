# W4 프리레그 항목 초안 (누적 — W3 착지가 만드는 W4 편성 재료)

작성 2026-07-20. W3 봉인 로스터 불변. 아래는 W3 셀들이 실측으로 발생시킨 W4 신규 봉인 후보.
봉인은 W4 프리레그 작성 시 (3석 확인 관문 재적용). 각 항목 = 발생 근거 + 사양 골격.

## W4-M2b — 노드 정밀도 RSI 표적 (Paul D7 길 2)
- 발생: M-2에서 S-node F1 0.870<0.92 FAIL (@3cda019). GNN 약점 = 정밀도 0.77(과잉표시)/
  재현율 0.99.
- 사양: RSI 내부 루프(C-3 하네스 재사용)의 **신규 봉인 목적함수 = S-node F1**(pooled AUPRC와
  별개 셀 — M-13 봉인 목적 불변 유지). 시작점 = GNN-A 동결. 탐색 공간 = M-13과 동일 + 정밀도
  타겟 정규화·임계 보정 규칙층. 공개/비공개 분할·가드·commit-then-evaluate = C-3 계약 승계.
  승자 = 노드-F1 비공개 개선 ∧ pooled AUPRC 비열화(회귀 방지 이중 게이트).
- 게이트: C-3 PASS(완료) ∧ M-14 라이브러리 봉인 ∧ proposer 설정 봉인.

## W4-M2c — 미정의 밴드 재입법 (Paul D7 길 1)
- 발생: M-2에서 S-pair F1·true style-OOD drop = BLOCKED_INPUT — 원 프리레그가 기준선(≥0.80,
  ≤0.10)만 봉인, 조작적 정의 미봉인. 워커 발명 거부(정직).
- 사양 (M-15 문법: 정의 선봉인 → 측정):
  - **S-pair**: 후보 쌍 우주(같은 도면 내 벽 노드 쌍? k-근접? 정의 필요) · 쌍 truth 규칙(양
    끝 모두 wall_handle?) · 채점기 · 결정 임계 · 풀링 단위 · 시드 집계. 정의 소스 발굴 우선
    (prereg_program_v1·FINAL_PROGRAM_PLAN), 없으면 신규 입법 명시.
  - **style-OOD**: 참 OOD 도면 집합 정의(스타일 축이 무엇인가 — 레이어 관행? 축척? 표기법?) ·
    IID 대비 하락 측정 규칙. E6 캘리브레이션 노트가 "참 OOD=차기 프리레그"로 미룬 항목 승계.
- 게이트: 정의 소스 발굴 → 선봉인 → 측정. FAIL이어도 완화 금지.

## W4-M12-split — ArchCAD 공식 분할 확보 (M-12 후속)
- 발생: M-12 TRACK_BLOCKED (@커밋대기) — 스키마 PASS(31클래스·wall=semantic:20)·어댑터 타당성
  PASS(설계)이나 **분할 격리 FAIL**(공식 project/drawing grouping 0건 — 무작위 split=누수
  위험)·좌표 INCONCLUSIVE(물리 단위 미확정).
- 사양: 원 배포자 제공 project/drawing grouping + 공식 split manifest 확보·해시 봉인 → 좌표
  물리 단위 machine-readable 근거 확보. 둘 다 확보 전 학습 투입 영구 금지(eligible_for_training
  =false 고정). 코드·학습보다 이 조달이 선행.
- 성격: 데이터 조달 조사(보유 인프라 우선 — 외부 조달 제안 아님, 로컬 복제본의 메타데이터
  재확인 우선).

## (누적 슬롯 — 후속 착지가 추가)
- W4-M11-* : M-11 청주 자격 결과 대기.
- W4-onto-* : M-14 온톨로지 실물 결과 대기.
- 고리 2/3 RSI (RSI_SYSTEM_DESIGN.md): gen3-RSI · 리뷰 좌석 파일럿 — P1 원장 + P3 배터리 후.
