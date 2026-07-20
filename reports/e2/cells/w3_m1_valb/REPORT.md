# M-1 val-B 단발 배치 — 개봉 보고 (W3 Phase 0C)

> **W3-BOUNDARY**: 본 보고의 탐지기 사다리·모든 val-A/val-B 수치의 유효 범위는 **CubiCasa
> SEG-IR 우주 한정**이다. **E1 실무 도면 전이는 미검증**이며, 본 보고는 이 경계 밖 일반화를
> 주장하지 않는다.

## 봉인 계보

| 항목 | 값 |
|---|---|
| wave_id | `e2.w3` |
| W3 프리레그 prose | `1348c40b2e95755478cd8a9f68df5f91fcc9290a5e51e2c68285d780bc16457a` (@079263e) |
| W3 로스터 JSON | `ad66606a239b56441ffbdead949e0b50e62f3105a931cad4421f36e3a963fde4` (@079263e) |
| amendment3 | `f4d06fc4b6ec049247c0fbfa17a633f6941cbc1b989557ac9c8d1855ce5b7800` (@e37acff) |
| 러너 | `e9edba8b20ed772633f1afa5ecbfc811b28167782795a7611398bf85646b12e9` |
| method manifest | `0070e290c1953b7268e60ebd8196e91178d7760297ab990518443667518d8d4a` |
| one-shot nonce SHA | `73d9f4f076c2bb9ddd4d3461b4a65b51754a52bafa195281f2dd0a2b4dbf50bb` (소모됨) |
| 실행 승인 | Paul D1 (PAUL_DECISIONS_20260720.md `1acf0e26…`) |
| preflight | 러너 자체 검증기 3종 PASS (TRUSTED_LAUNCH / METHOD_MANIFEST 1·3·3 / PRODUCTION_BINDING) |

## 결과 (val-B 봉인면, 팔별 pooled)

| 팔 | AUPRC | F1@0.5 | ECE-10 |
|---|---:|---:|---:|
| clean incumbent (3-seed 앙상블) | 0.8330226845762901 | 0.7036954337389751 | 0.008740825154958203 |
| 2-hop classical (3-seed) | 0.8700229464302716 | 0.7551630220905471 | 0.007864915006484598 |
| **GNN-A (3-seed)** | **0.9770778258449528** | **0.8694960306337228** | 0.029658771082815245 |

| 대조 | ΔAUPRC | ΔF1 | CI95 low | CI95 high | SE boot |
|---|---:|---:|---:|---:|---:|
| gnn − clean | 0.1440551412686627 | 0.1658005968947477 | **0.1370602535788751** | 0.1509698492158229 | 0.0035603169268295 |
| gnn − twohop | 0.1070548794146813 | 0.1143330085431757 | **0.1005933342590782** | 0.1134946748302635 | 0.0033152288495858 |
| twohop − clean | 0.0370002618539814 | 0.0514675883515720 | 0.0338944372305270 | 0.0402372444456344 | 0.0016096769889037 |

## 판정 (봉인 조문 그대로)

- **G1** (gnn−clean CI95 low > 0): 0.13706 > 0 → **PASS**
- **G2** (gnn−twohop CI95 low > 0): 0.10059 > 0 → **PASS**
- **G1 ∧ G2 → ADJ-PASS.**
- clean sentinel: `clean_sentinel_ok=true` (W2 회고 배치 기록치와 허용오차 1e-6 내 일치 — 계보
  드리프트 0).
- val-A DEV(0.9748) → val-B(0.9771): DEV 과적합 신호 없음 — 동일 우주 내 일반화 유지.
- ADJ-PASS의 효력 한계(봉인 조문): 최종 채택은 **M-2 AND-게이트 완결**(S-node/S-pair/true
  style-OOD) 충족 시에만. 본 판정 단독으로 RSI_ADOPT 금지.

## 무결성·회계

- integrity_flags 10종 전건 OK: AMENDMENT_FILE_PARENT_WAVE_BINDING_OK · ARTIFACT_SHA256_OK ·
  BOOTSTRAP_10000_SEED_43 · COMMON_ROW_UNIVERSE_OK · EXCLUSIVE_LEDGER_TRANSACTION ·
  EXTERNAL_PREDICTIONS_REJECTED · LABELS_READ_ONE_TRUSTED_TRANSACTION · ONE_SHOT_NONCE_OK ·
  OUTPUT_SCHEMA_EXACT · PREVIOUS_LEDGER_SHA256_OK
- canonical ledger: pre `955337d9ec48329e4f55a2ef949700fb5b8d868734d48227a368df25a324443a`
  (1행, 565B) → post `c4dba7013af894bf9020b113012220b89a1584e88252fcb20942f944faeab13b`
  (**통산 2행**, 5394B) — 봉인 회계 산술(정상=웨이브 1이벤트·본 배치=통산 2행)과 일치.
- 잔여 동결: 본 웨이브 val-B 추가 개봉 0 (팔 추가 금지 승계). 폐포 코드 동결 해제 → M-6 착수 가능.

## W3-TELEM

| 필드 | 값 |
|---|---|
| wall_seconds | 255.4142498 |
| peak_rss_bytes | RSS_RESOURCE_NOT_RECORDED (런처 미계측 — 자원 주장 인용 불가) |
| peak_vram_bytes | VRAM_RESOURCE_NOT_RECORDED |
| device | NVIDIA GeForce RTX 5070 Ti (GNN 추론) + CPU |
| budget_charge | M-1 캡 RTX 0.5h 내 (0.071h) · 질의 1/1 소진 |

- 산출 정본: `D:\runs\e2_program\cells\w2_09_valb\valb_batch_result_e2w3.json` (1221B) +
  본 디렉토리 `evidence.csv`.
- 실행: exit 0 · stderr 없음 · GOVERNANCE_STOP 미발동 · G-7 부검 불요.

REPORT_COMPLETE
