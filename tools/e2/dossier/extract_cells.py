#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract the experiment-cell sections (packet §6) from all 26 dossiers into
one synthesis index: reports/e2/dossiers/CELLS_INDEX.md (+ per-dossier TOC).

Heuristic: a dossier's cell section starts at a header whose text matches
the §6 vocabulary (실험 셀 | 셀 정의 | experiment cell | 실험 계획) and runs
to the next same-or-higher-level header. Falls back to flagging NOT_FOUND so
missing extractions are visible, never silently empty.
"""
from __future__ import annotations

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DOSS = os.path.join(ROOT, "reports", "e2", "dossiers")
PAT = re.compile(r"(실험\s*셀|셀\s*정의|experiment\s*cell|실험\s*계획|실험\s*설계)", re.I)


def extract(path: str):
    lines = open(path, encoding="utf-8").read().splitlines()
    headers = [(i, len(m.group(1)), lines[i]) for i, m in
               ((i, re.match(r"^(#+)\s", ln)) for i, ln in enumerate(lines)) if m]
    for idx, (i, lvl, text) in enumerate(headers):
        if PAT.search(text):
            end = len(lines)
            for j, jlvl, _ in headers[idx + 1:]:
                if jlvl <= lvl:
                    end = j
                    break
            return "\n".join(lines[i:end]).strip(), text.strip()
    return None, None


def main() -> int:
    out = ["# CELLS_INDEX — 26 도시에의 실험 셀 섹션 원문 모음 (종합용)\n"]
    toc = []
    missing = []
    for f in sorted(glob.glob(os.path.join(DOSS, "*.md"))):
        base = os.path.basename(f)
        if base in ("manifest.json", "CELLS_INDEX.md", "TOC.md"):
            continue
        sid = base[:-3]
        if sid in ("CELLS_INDEX", "TOC"):
            continue
        block, header = extract(f)
        if block is None:
            missing.append(sid)
            out.append(f"\n---\n\n## [{sid}] — **NOT_FOUND** (셀 섹션 헤더 미검출, 원문 직접 확인 필요)\n")
        else:
            n_lines = block.count("\n") + 1
            toc.append((sid, header, n_lines))
            out.append(f"\n---\n\n## [{sid}] — {header} ({n_lines} lines)\n\n{block}\n")
    path = os.path.join(DOSS, "CELLS_INDEX.md")
    open(path, "w", encoding="utf-8").write("\n".join(out))
    for sid, header, n in toc:
        print(f"{sid}: {n} lines  ({header[:60]})")
    if missing:
        print("NOT_FOUND:", ", ".join(missing))
    print(f"-> {path}  ({os.path.getsize(path)} bytes, {len(toc)}/26 extracted)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
