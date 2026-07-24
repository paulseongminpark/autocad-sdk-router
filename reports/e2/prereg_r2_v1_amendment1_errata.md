# prereg_r2_v1_amendment1.json — errata (2026-07-19)

- **결함**: `prereg_r2_v1_amendment1.json`은 JSON으로 파싱되지 않는다 — `gb10_caps_final_h` 객체가
  닫히지 않아 문서 말미 경계가 문법적으로 붕괴한다 (gnn_formal 셀 워커가 발견·보고).
- **처분**: 봉인 문서이므로 **원본은 수리하지 않는다** — 인용된 SHA-256
  (`30f752db803f7f589d1a8d1f1a2d8557364ae2d624f76a639533161f552b8283`, gnn_formal prereg
  `input_hashes.amendment1`)의 해시 사슬을 보존하기 위해서다.
- **해석 규약**: amendment1의 조문은 텍스트로 읽는다. 밴드·캡 수치(G5 RTX 132h, RAM 48GB,
  DGX_MEMORY_BOUND_ONLY 등)는 문법 결함과 무관하게 문언 그대로 유효하다.
- 향후 amendment는 봉인 전 `json.loads` 왕복 검증을 의무화한다 (amendment2부터 이미 준수).
