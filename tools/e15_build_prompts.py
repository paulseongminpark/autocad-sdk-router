#!/usr/bin/env python3
"""Build E1.5 (annot v1) oneshot prompts from the frozen E1 shards.

Reads bench/e1_shards/shard_NN.jsonl (the sha-pinned E1 projections, commit 6772935)
and emits one self-contained oneshot prompt per shard under
reports/e1/annot_v1/prompts/shard_NN.txt plus a prompts_manifest.json with
per-file sha256 + unit ids. The projections are byte-identical to v0 — only the
instruction block changes (adds the mandatory rationale fields). Judges answer a
strict JSON array so results parse without repair.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARDS_DIR = ROOT / "bench" / "e1_shards"
OUT_DIR = ROOT / "reports" / "e1" / "annot_v1" / "prompts"
_SPLIT = "\nInstructions / 지시사항:"

HEADER = """DWG block definition annotation task v1 / DWG 블록 정의 주석 작업 v1
The model has no filesystem access. Use only the inline projections below.
You will annotate {n} block definitions. Definitions are independent; judge each on its own.

For EACH definition output one JSON object with ALL of these fields:
- "unit_id": copied exactly from the definition header
- "def": definition name exactly as given
- "role": exactly one of "평면 부분도" | "심볼" | "치수캐시" | "가구" | "기타"
- "wall_likelihood": number 0..1
- "wall_line_handles": up to 10 [{{"handle":"...","reason":"one phrase"}}] entities that look like wall lines; [] if none
- "notes": one-line summary
- "rationale": {{
    "evidence": which concrete entities/layers/patterns drove the judgment (2-4 sentences),
    "rule": the general principle applied, stated so it would transfer to other drawings (1-2 sentences),
    "counterfactual": what, if present or absent in this projection, would flip the judgment (1-2 sentences),
    "uncertainty": what cannot be determined from this projection alone and why (1-2 sentences)
  }}

Answer STRICTLY as one JSON array of {n} objects, in the same order as the definitions below.
No surrounding prose, no markdown fence, no trailing commentary.

"""


def build() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    for shard_path in sorted(SHARDS_DIR.glob("shard_*.jsonl")):
        units = []
        with open(shard_path, "r", encoding="utf-8-sig") as handle:
            for line in handle:
                if line.strip():
                    units.append(json.loads(line))
        blocks = []
        unit_ids = []
        for i, unit in enumerate(units, 1):
            projection = unit["prompt"].split(_SPLIT)[0]
            # drop the v0 per-unit header lines; keep from "Definition name:" on
            idx = projection.find("Definition name:")
            projection = projection[idx:] if idx >= 0 else projection
            unit_ids.append(unit["unit_id"])
            blocks.append(
                f"=== DEFINITION {i}/{len(units)} (unit_id: {unit['unit_id']}) ===\n{projection.strip()}\n"
            )
        text = HEADER.format(n=len(units)) + "\n".join(blocks)
        out_path = OUT_DIR / (shard_path.stem + ".txt")
        out_path.write_text(text, encoding="utf-8", newline="\n")
        manifest[shard_path.stem] = {
            "units": len(units),
            "unit_ids": unit_ids,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }
    manifest_path = OUT_DIR / "prompts_manifest.json"
    manifest_path.write_text(
        json.dumps({"schema": "ariadne.e15_prompts.v1", "shards": manifest}, ensure_ascii=False, indent=1),
        encoding="utf-8",
        newline="\n",
    )
    total = sum(m["units"] for m in manifest.values())
    print(f"built {len(manifest)} prompts, {total} units -> {OUT_DIR}")


if __name__ == "__main__":
    build()
