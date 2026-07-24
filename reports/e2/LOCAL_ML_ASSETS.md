# LOCAL ML ASSETS — 실측 인벤토리 (2026-07-17)

Paul 지시 "모델 더 많아. 다 뒤져봐. 모델과 데이터셋 제대로 확보해"에 따른 전수 수색 결과.
수색 범위: `_ariadne\huggingface` · `_ariadne\alm\datasets` · HF hub 캐시(`~\.cache\huggingface\hub`) ·
ollama/lmstudio/torch 캐시(부재 확인) · D:\ 전역 + Desktop/Documents 가중치 파일 워커
(*.safetensors/.gguf/.onnx/.ckpt/.pth + 300MB↑ .pt/.bin, .git/node_modules 등 prune).

## 모델 (로컬 실보유)

| 모델 | 위치 | 크기 | 형태 · 용도 |
|---|---|---|---|
| **Qwen3.6-35B-A3B** UD-Q4_K_M | `D:\dev\99_tools\llama.cpp\models` | 20.61 GB | GGUF — llama.cpp 로컬 추론용 범용 LLM |
| **CAD-Coder** (gudo7208) | `_ariadne\huggingface\models\cad_coder\full` (=`alm\datasets\_models\CAD-Coder`) | 15.25 GB | safetensors — CAD 코드 생성 특화 |
| **C3D-v0** (numinousmuses) | `alm\datasets\_models\C3D-v0-gguf` | 6.80 GB | GGUF q8_0 (unsloth) — CAD 특화 |
| **qwen2.5-VL-3B floorplan-SFT** (mudasir13cs) | `_ariadne\huggingface\models\qwen25_vl_3b_floorplan_sft` | 1.08 GB | VLM 파인튜닝 (checkpoint-1000/-1234) — 도면 특화 선행 자산 |
| **qwen2.5-VL-3B floorplan-GRPO** (mudasir13cs) | 동 상 `..._grpo` | 0.62 GB | VLM **RL(GRPO)** 파인튜닝 (checkpoint-100 + ref) |
| faster-whisper large-v3 / small.en | HF hub 캐시 | 3.09 / 0.49 GB | 음성 (비-CAD 유틸) |
| multilingual-e5-small · MiniLM-L12-v2 | HF hub 캐시 | 0.49 / 0.48 GB | 임베딩 (비-CAD 유틸) |

## 데이터셋 (로컬 실보유)

| 데이터셋 | 위치 (정본) | 크기 | 형태 |
|---|---|---|---|
| **Zenodo10K** (Forceless) | `alm\datasets\Zenodo10K` (hf측 13.70GB 사본 병존) | 14.26 GB | 도면 코퍼스 |
| **Text2CAD** (SadilKhan) | `_ariadne\huggingface\datasets\text2cad` | 12.34 GB | 텍스트→CAD 페어 |
| **ArchCAD** (jackluoluo) | `alm\datasets\ArchCAD` (hf측 dir는 스텁) | 9.87 GB | 건축 CAD |
| **pseudo-floor-plan-12k** (zimhe) | 양쪽 동일본 | 3.92 GB | 합성 평면도 12k |
| **FloorPlanCAD** (Voxel51) | 양쪽 동일본 | 0.45 GB | **FiftyOne 래스터**: PNG 5,308 + per-object `wall` bbox/segmask (samples.json 60MB) |
| CubiCasa5K (Claudio9701) | (수색 시점 스텁 0GB) | — | **부재 → 2026-07-17 다운로드 착수** (`huggingface\datasets\cubicasa5k\full`) |

## 접근 경로 · 비고

- `D:\datasets` 정션이 Catalog 이사 이전 사멸 경로를 가리키고 있었음 → **2026-07-17 수리**: 이제
  `D:\datasets` → `D:\dev\_ariadne\alm\datasets` (FloorPlanCAD 접근 검증 PASS).
- HF hub 캐시의 CAD 계열 엔트리는 전부 0GB 포인터 스텁 — 실데이터는 `_ariadne` 트리가 정본.
- FloorPlanCAD **벡터(SVG 선단위 라벨) 변형은 로컬에 없음** — 래스터 트랙 실증 후 필요 시 별도 논의.
- E2 프로그램 접점: 래스터+마스크(FloorPlanCAD·pseudo-12k)=S6 세그·VLM 트랙 즉시 재료 /
  qwen SFT·GRPO=S6 사다리의 선행 기준선(RL 갈래 판별에 실물 비교대상) / CAD-Coder·C3D·Text2CAD=
  생성·코드 트랙 후보 / Zenodo10K·ArchCAD=대규모 도면 코퍼스.
