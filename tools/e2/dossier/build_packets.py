#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build 26 self-contained dossier packets for the E2 methodology deep-dive fleet.

Each packet inlines: the proposal's full seat-file section, the whole
PANEL_REPORT.md (cluster + dissent context), a measured-reality digest
(every number sourced from this session's tool outputs), the asset
inventory, and the dossier contract. Workers read ONE file and need
nothing else (delegation doctrine: deterministic data inlined, no
"as discussed" references).

Account assignment (Paul, 2026-07-18): aclaude(main opus max) 6 ·
aclaude-e(opus max) 6 · acodex(sol xhigh) 4 · acodex-b(sol xhigh) 4 ·
grok(4.5 xhigh) 6.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PANEL = os.path.join(ROOT, "reports", "e1", "panel_20260717")
RUN = r"D:\runs\e2_dossier_wave\20260718"

SEATS = {
    "platt": "platt_strong_inferencer.md",
    "doe": "doe_experimentalist.md",
    "calibration": "calibration_forecaster.md",
    "feyerabend": "feyerabendian_dissenter.md",
}

# seat_key, proposal_key, account
ASSIGN = [
    ("platt", "P0", "aclaude"), ("platt", "P2", "aclaude"), ("doe", "P1", "aclaude"),
    ("calibration", "P3", "aclaude"), ("feyerabend", "P1", "aclaude"), ("feyerabend", "P5", "aclaude"),
    ("platt", "P1", "aclaude-e"), ("platt", "P5", "aclaude-e"), ("doe", "P3", "aclaude-e"),
    ("calibration", "P4", "aclaude-e"), ("feyerabend", "P2", "aclaude-e"), ("feyerabend", "P6", "aclaude-e"),
    ("platt", "P3", "acodex"), ("doe", "P2", "acodex"), ("calibration", "P1", "acodex"),
    ("feyerabend", "P3", "acodex"),
    ("platt", "P4", "acodex-b"), ("doe", "P5", "acodex-b"), ("calibration", "P2", "acodex-b"),
    ("feyerabend", "P7", "acodex-b"),
    ("platt", "P6", "grok"), ("doe", "P4", "grok"), ("doe", "P6", "grok"),
    ("calibration", "P5", "grok"), ("calibration", "P6", "grok"), ("feyerabend", "P4", "grok"),
]

DIGEST = """## 실측 다이제스트 (2026-07-18 세션 도구 출력 — 이 수치만 인용 가능, 새 측정 주장 금지)

**프로그램**: E2 벽 의미 탐지기 — CAD 도면 선분에서 '벽' 의미를 인식. 사람 라벨은 초기 배제였으나
외부 제3자 라벨셋 사용이 GO됨. 방법론 사다리(결정론→고전ML→그래프→DL→RL→VLM)를 같은 시험지로 겨룬다.

**합성팩(S/F/M, 자체 생성기)**: B1 충실도 FAIL(KS 0.5792, TV 0.265 — 실도면은 SPLINE 3,973/ARC 2,198/
HATCH 264 혼재, 합성팩은 LINE/LWPOLYLINE/INSERT 3종뿐). B2 per-handle(임계 0.5): S 1.0/1.0(단, S팩
채점우주에 음성 0개 = 정밀도 공허), F P 0.9315, M P 0.8669(재현율 전부 1.0). B4 불변성: 강체(회전·이동·
반사)·단위 1.0 PASS, scale 팔 FAIL(0.7624), 센티널 조문상 strict FAIL 기록.

**실도면(1.dwg staged DXF, 도면정의 384개)**: B3 벽-제로 도면율 0.682(v0)→0.2135 PASS(밴드 ≤0.40).
B5 탐지기↔AI판정자(silver) Pearson 0.2911, name-blind 팔과 완전 동일(full-vs-nb 1.0 — 탐지기는 레이어명
신호 0) → 두 증거 축은 대체로 독립. 최대 도면정의 412,775 선분(연산 병목 실증). E1.5 silver 판정자
5기는 2어휘 가문(fable+sol vs opus+sonnet+grok)으로 갈림 — 5독립 아님, ~2가문으로 취급.

**외부셋 CubiCasa5k(핀란드 주거, 제3자 사람 라벨)**: 5,000도면 전량 SEG-IR 변환(실패 0). 분할
train 4,200(선분 386만)/val 400(35.4만)/test 400(37.5만), 벽 선분율 ~11.8%. 변환은 레이어 중립(라벨
누출 0), 진리=Wall 클래스 요소의 모서리. 좌표 px(도면별 축척 미상, 벽두께 px p50=22).
**기하 탐지기 v1 전이 성적: val F1 0.2358(P 0.134 ≈ 기저율 0.118, R 0.981)** — 축척 2~15mm/px 전
구간에서 성적 무감(물리 두께 prior 무력). FP 주범: Direction 화살표/BoundaryPolygon/Door/Window/
DimensionMark(전부 대역 내 평행 구조). 최소길이 필터 천장 F1 0.335(80px) — 아이콘 아닌 긴 평행
구조가 본질 교란. **학습 1단: HistGradientBoosting(6특징: parallel/thickness/junction/log길이/sin2θ/
cos2θ, 386만행) → val P 0.860/R 0.370/F1 0.517/AUC 0.9215** (탐지기 2.2배, 정밀도 0.13→0.86).
로지스틱 F1 0.053(선형 불충분). 셔플 대조군 AUC 0.375 PASS(누출 없음). test 분할은 무접촉(단발 원칙).

**탐지기 v1 구조**: 4증거 채널 가중합(parallel 0.35/thickness 0.25/junction 0.20/layer 0.20), 두께 대역
50~400mm, 각도 허용 2°, overlap 0.5, snap 6mm. NumPy 동치 고속 채점기(fast_score) 있음.

**자산**: FloorPlanCAD 래스터 5,308장+벽 bbox/segmask(벡터 SVG 없음) · qwen2.5-VL-3B floorplan
SFT/GRPO 파인튜닝 모델 로컬 실존 · RTX 5070 Ti 16GB · RAM 64GB · DGX Spark(Ornith-35B) 현재
unreachable(승인은 됨) · 프런티어 VLM API=유일 결재 게이트(미승인) · Zenodo10K/Text2CAD/ArchCAD/
pseudo-floor-plan-12k 로컬 보유.

**평가 원칙(고정)**: val=개발·튜닝 허용, test=방법당 단발, 합격선은 평가 전 봉인(프리레그), 셔플
대조군 의무, 증거 xlsx 의무, 실패도 사유와 함께 기록.
"""

STRUCTURE = """## 도시에 필수 구조 (8절 — 전부 채울 것, 깊이 우선·분량 무제한)

1. **이론적 근거·선행연구** — 이 제안이 기대는 방법론 계보. 구체 기법·논문·시스템 이름을 명시
   (일반 지식으로 서술하되, 확신 없는 인용은 '요검증' 표기).
2. **알고리즘 정확 스펙** — 의사코드/수식 수준. 입력·출력·손실·하이퍼파라미터 공간까지.
3. **벽 과업 적응 설계** — 위 다이제스트의 실제 하네스(CubiCasa SEG-IR 벡터축·FloorPlanCAD 래스터축·
   1.dwg 실도면축)에 어떻게 접속하는가. 전이 실패 0.236과 GBDT 0.517을 알고 있는 상태에서, 이 방법이
   무엇을 더 가져올 수 있는지 명시.
4. **데이터·컴퓨트 요구** — 우리 자산 기준 실행 가능성. GPU 16GB/RAM 64GB/DGX 불통을 전제로
   로컬 실행 계획과 DGX 계획을 분리.
5. **구현 계획** — 모듈·파일 골격, 기존 도구(evidence_grid/fast_score/cubicasa_ir/cubicasa_ml) 접속점,
   예상 개발 규모.
6. **실험 셀 정의** — 셀별 {가설, 지표, 제안 합격선, 킬 조건, 예산(시간·자원), 시드 계획}.
   val 개발/test 단발 원칙 준수. 셀 수는 방법이 요구하는 만큼(과소·과잉 둘 다 금지).
7. **red team 티켓 응답** — 아래 패널 보고서의 OPEN 티켓 중 이 제안에 걸린 것들을 지목하고 각각
   해소 방안 또는 수용(위험 인정) 입장을 명시.
8. **인접 제안과의 관계** — 병합 가능 지점, 차별점, 그리고 **이 제안이 죽어야 하는 조건**(정직하게).
"""

CONTRACT = """## 계약 (위반 = 도시에 무효)

- 산출물: 아래 지정된 절대경로에 UTF-8 markdown 파일 **하나만** 작성. 다른 파일 생성·수정 금지.
- git 명령 일체 금지. 서브에이전트/병렬 에이전트 생성 금지. 웹 검색은 가능하면 사용하지 않는다
  (일반 지식으로 충분; 사용했다면 출처를 명시).
- 수치 인용은 이 패킷의 다이제스트에서만. 그 외 수치는 문헌 일반 지식임을 명시.
- 파일 마지막 줄은 정확히: `DOSSIER_COMPLETE: <seat_id>`
- 한국어로 작성(기술 용어 영어 병기 허용).
"""


def extract_section(text: str, pkey: str) -> str:
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines)
              if re.match(rf"^#+\s*\**{pkey}\b", ln.strip()) or
              re.match(rf"^### {pkey}[ .—\-]", ln)]
    if not starts:
        raise SystemExit(f"section {pkey} not found")
    s = starts[0]
    e = len(lines)
    for j in range(s + 1, len(lines)):
        if re.match(r"^### ", lines[j]):
            e = j
            break
    return "\n".join(lines[s:e]).strip()


def main() -> int:
    panel_report = open(os.path.join(PANEL, "PANEL_REPORT.md"), encoding="utf-8").read()
    seat_texts = {k: open(os.path.join(PANEL, "seats", v), encoding="utf-8").read()
                  for k, v in SEATS.items()}
    os.makedirs(os.path.join(RUN, "prompts"), exist_ok=True)
    os.makedirs(os.path.join(RUN, "dossiers"), exist_ok=True)
    os.makedirs(os.path.join(RUN, "logs"), exist_ok=True)

    manifest = []
    for seat, pkey, account in ASSIGN:
        sid = f"{seat}_{pkey}"
        section = extract_section(seat_texts[seat], pkey)
        out_md = os.path.join(RUN, "dossiers", f"{sid}.md")
        packet = f"""# E2 방법론 심층 도시에 패킷 — {sid}

당신은 E2 벽 의미 탐지기 프로그램의 방법론 심층조사 연구자다. 아래 제안 1건을 **끝까지 파서**
실행 가능한 실험 계획으로 만든다. 이 패킷은 자기완결이다 — 여기 없는 맥락은 가정하지 말 것.

## 당신이 맡은 제안 ({seat} 좌석 · {pkey})

{section}

---

{DIGEST}

---

## 패널 보고서 전문 (클러스터·반대의견·티켓 맥락)

{panel_report}

---

{STRUCTURE}

---

{CONTRACT}

**산출 경로**: `{out_md}`
**seat_id**: `{sid}`
"""
        ppath = os.path.join(RUN, "prompts", f"{sid}.md")
        open(ppath, "w", encoding="utf-8").write(packet)
        manifest.append({"seat_id": sid, "account": account,
                         "prompt": ppath, "output": out_md,
                         "chars": len(packet)})
    mpath = os.path.join(RUN, "manifest.json")
    json.dump(manifest, open(mpath, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    by_acct = {}
    for m in manifest:
        by_acct.setdefault(m["account"], []).append(m["seat_id"])
    print(json.dumps({k: v for k, v in by_acct.items()}, indent=1, ensure_ascii=False))
    print("packet chars min/max:", min(m["chars"] for m in manifest),
          max(m["chars"] for m in manifest))
    print("->", mpath)
    return 0


if __name__ == "__main__":
    sys.exit(main())
