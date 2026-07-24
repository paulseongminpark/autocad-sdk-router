#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W2 — freeze the WSD-EVAL-v1 evaluation pack (G2 gate).

Hashes every evaluation input so all S6+ experiments score against an
immutable, named pack. Outputs reports/e2/WSD_EVAL_v1.manifest.json.

Inputs frozen:
  - synthetic packs S/F/M (dxf + truth + pack manifests)
  - staged real DXF of 1.dwg (CAD-OS derived copy; provenance recorded)
  - E1.5 silver raw judge shards (5 judges)
  - E1 frozen projections pointer (bench/e1_shards, commit-pinned in prereg_e15)
  - metamorphic transform module sources (code identity)
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def freeze_glob(pattern: str) -> dict:
    files = sorted(glob.glob(os.path.join(ROOT, pattern), recursive=True))
    return {os.path.relpath(p, ROOT).replace("\\", "/"): sha256(p)
            for p in files if os.path.isfile(p)}


def main() -> int:
    git_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()

    sections = {
        "synth_packs": freeze_glob(r"reports/e2/s2/packs/**/*"),
        "real_staged_dxf": freeze_glob(r"runs/e2_b3_dxfout_20260717/1_export.dxf"),
        "silver_raw": freeze_glob(r"reports/e1/annot_v1/raw/**/*.json"),
        "transform_code": freeze_glob(r"tools/e2/meta/*.py"),
        "detector_code": freeze_glob(r"tools/e2/detect/*.py"),
    }
    counts = {k: len(v) for k, v in sections.items()}
    manifest = {
        "schema": "ariadne.wsd_eval.v1",
        "frozen_at_commit": git_head,
        "prereg": "e2.wave1.v1 (bands) + e2 PROGRAM_PLAN_v1 G2 (freeze discipline)",
        "provenance": {
            "real_staged_dxf": {
                "source_original": "D:/dev/.build/1.dwg (READ-ONLY)",
                "original_sha256": "14eb65eb292d8a07f38ab5662dcafe9761c6185bc5ff0c8a9a008be15b598961",
                "derivation": "cad_run_operation transform.database.dxf_out (write_copy)",
            },
            "e1_projections": "bench/e1_shards shard_01..20.jsonl @ commit 6772935 (prereg_e15)",
            "silver_top_tier": ["opus48_max", "fable5_high", "sol56_xhigh"],
        },
        "counts": counts,
        "files": sections,
        "rule": "S6+ experiments MUST score against these hashes; any drift = new pack version.",
    }
    out = os.path.join(ROOT, "reports", "e2", "WSD_EVAL_v1.manifest.json")
    json.dump(manifest, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(counts, indent=1))
    print("frozen at commit:", git_head)
    print("->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
