#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dbx_capability_audit.py -- P2a: arx->dbx capability audit (static, evidence-based).

Scope (SDK certification ledger P2a): the `custom_objects_protocols` (63) and
`geometry_kernel` (25) families. For each op, decide whether its implementation
could be served by a pure ObjectDBX host (no AutoCAD editor/application), or
genuinely requires the ARX host -- and compare that verdict against the
registry's current `engine_tier` so P2c can apply corrections.

Method (two independent evidence sources per op, both recorded):
  1. DECLARED API: the registry handler.native_api string names the SDK calls
     the op uses (curated during M08 wiring).
  2. CODE SLICE: the op's dispatch block in src/ (AriadneNativeJob.cpp +
     src/Ariadne.AcadNative/families/*.inc), located by the op-id string
     compare, scanned for host-class tokens; plus ONE level of helper taint
     (helpers whose own bodies contain arx-only tokens).

Token model (ObjectARX 2027):
  ARX-ONLY  : aced* (editor services), AcAp*/acDocManager (application/document
              manager), AcEd* (editor reactors/jigs), AcPl* (plot), AcTc* (tool
              palettes), actrans/AcTransactionManager (editor transactions),
              AcGsView/AcGsManager-through-editor.
  DBX-SAFE  : AcDb*, AcGe*, AcCm*, AcRx*/acrx* (the Rx runtime ships in DBX
              hosts), acut* resbuf utilities, AcString, AcArray.
  ASM_BOUNDARY: AcDb3dSolid/AcDbBody/AcDbRegion boolean/modeling calls -- the
              ASM modeler boundary is a known dbx-write defer line (see
              reference_cados_objectdbx_write_feasibility); flagged for human
              review, never silently classified.

Honest-scope notes: helper taint is ONE level deep (recorded per op); a clean
static verdict is necessary-but-not-sufficient for a dbx port (link/runtime
proof happens at P2c via the dbx import audit + build).

Usage:
    python tools/dbx_capability_audit.py [--out-prefix reports/objectarx_sdk/P2A_DBX_CAPABILITY_AUDIT_<date>]
Exit 0 always (audit artifact is the deliverable); mismatches land in the report.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import io
import json
import os
import re
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REGISTRY = os.path.join(_REPO, "config", "operations.v2.json")
_FAMILIES = ("custom_objects_protocols", "geometry_kernel")

_ARX_TOKENS = re.compile(
    r"\b(aced[A-Z]\w*|AcAp[A-Z]\w*|acDocManager|AcEd[A-Z]\w*|AcPl[A-Z]\w*|"
    r"AcTc[A-Z]\w*|actrTransactionManager|AcTransactionManager|acedSSGet|"
    r"acutPrintf)\b")
_ASM_TOKENS = re.compile(
    r"\b(AcDb3dSolid|AcDbBody|AcDbRegion)\s*(::|\.|->)?\s*"
    r"(booleanOper|extrude|revolve|createSculptedSolid|imprintEntity|"
    r"sectionPlane|getSlice|createFrom)\w*")
_DBX_TOKENS = re.compile(r"\b(AcDb[A-Z]\w*|AcGe[A-Z]\w*|AcCm[A-Z]\w*|AcRx[A-Z]\w*|acrx\w+|acut\w+)\b")


def _load_sources():
    files = [os.path.join(_REPO, "src", "Ariadne.AcadNative", "AriadneNativeJob.cpp")]
    files += sorted(glob.glob(os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "*.inc")))
    return {f: io.open(f, encoding="utf-8", errors="replace").read() for f in files}


_CPP_KEYWORDS = frozenset((
    "if", "for", "while", "switch", "return", "sizeof", "catch", "throw",
    "do", "else", "case", "new", "delete", "static_cast", "dynamic_cast",
    "const_cast", "reinterpret_cast", "defined", "assert"))


def _match_brace_end(text: str, start: int) -> int:
    """Return index just past the '}' matching the '{' before `start`, walking
    literal-aware: braces inside "..."/'...' literals and //, /* */ comments do
    NOT count. (v1 counted the '{' in `j.find('{', p)` and swallowed 40k chars
    of neighboring functions -- the false-taint root cause.)"""
    depth, i, n = 1, start, len(text)
    while i < n and depth:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if c == "/" and nxt == "*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == '"' or c == "'":
            q, i = c, i + 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    return i


def _function_bodies(text: str):
    """Crude function splitter: '<ret> name(...) {' at column 0..8. Good enough
    for taint mapping (names + body text); not a C++ parser (documented).
    C++ keywords are rejected as 'function names' (an `if (...) {` statement
    would otherwise register a phantom helper named `if`)."""
    out = {}
    for m in re.finditer(r"^[ \t]{0,8}(?:static\s+)?[\w:<>&*\s]+?\b(\w+)\s*\([^;{)]*\)\s*\n?\s*\{",
                         text, re.M):
        name = m.group(1)
        if name in _CPP_KEYWORDS:
            continue
        start = m.end()
        out.setdefault(name, []).append(text[start:_match_brace_end(text, start)])
    return out


def _op_slice(sources: dict, op_id: str):
    """Find the DISPATCH block for the op and slice a bounded window after it
    (up to the next op-compare or 6000 chars). Preference order (an op-id can
    appear in comments/tables far from its handler, which mis-sliced v1):
      1. an exact dispatch compare  op == "<id>"  anywhere in the TU set;
      2. fallback: the first bare "<id>" string occurrence."""
    compare = re.compile(r'op\w*\s*==\s*"%s"' % re.escape(op_id))
    candidates = []
    for path, text in sources.items():
        m = compare.search(text)
        if m:
            candidates.append((0, path, text, m.start()))
    if not candidates:
        needle = '"%s"' % op_id
        for path, text in sources.items():
            idx = text.find(needle)
            if idx >= 0:
                candidates.append((1, path, text, idx))
    if not candidates:
        return None, None, ""
    candidates.sort(key=lambda c: c[0])
    _, path, text, idx = candidates[0]
    window = text[idx: idx + 6000]
    nxt = re.search(r'op\w*\s*==\s*"(?!%s")' % re.escape(op_id), window[80:])
    if nxt:
        window = window[: 80 + nxt.start()]
    line = text.count("\n", 0, idx) + 1
    return os.path.relpath(path, _REPO), line, window


def _classify(evidence_text: str):
    arx = sorted(set(_ARX_TOKENS.findall(evidence_text)))
    asm = sorted(set(m[0] for m in _ASM_TOKENS.findall(evidence_text)))
    return arx, asm


def main() -> int:
    ap = argparse.ArgumentParser()
    default_prefix = os.path.join(
        _REPO, "reports", "objectarx_sdk",
        "P2A_DBX_CAPABILITY_AUDIT_" + _dt.date.today().strftime("%Y%m%d"))
    ap.add_argument("--out-prefix", default=default_prefix)
    args = ap.parse_args()

    reg = json.load(io.open(_REGISTRY, encoding="utf-8-sig"))
    ops = reg["operations"]
    lst = ops if isinstance(ops, list) else list(ops.values())
    targets = [o for o in lst if o.get("family") in _FAMILIES]

    sources = _load_sources()
    taint = {}
    for text in sources.values():
        for name, bodies in _function_bodies(text).items():
            toks = sorted(set(t for b in bodies for t in _ARX_TOKENS.findall(b)))
            if toks:
                taint[name] = toks

    rows = []
    for o in sorted(targets, key=lambda x: x["id"]):
        op_id = o["id"]
        handler = o.get("handler") or {}
        declared = str(handler.get("native_api") or "")
        src_file, src_line, sl = _op_slice(sources, op_id)
        d_arx, d_asm = _classify(declared)
        c_arx, c_asm = _classify(sl)
        called = set(re.findall(r"\b(\w+)\s*\(", sl)) - _CPP_KEYWORDS
        tainted = sorted((h, taint[h]) for h in called if h in taint)
        arx_evidence = sorted(set(d_arx) | set(c_arx))
        asm_evidence = sorted(set(d_asm) | set(c_asm))
        if arx_evidence or tainted:
            verdict = "arx_required"
            reason = {"tokens": arx_evidence, "tainted_helpers": [h for h, _ in tainted]}
        elif asm_evidence:
            verdict = "asm_boundary_review"
            reason = {"asm_tokens": asm_evidence}
        elif not sl and not declared:
            verdict = "no_evidence"
            reason = {"note": "no code slice found and no declared native_api"}
        else:
            verdict = "dbx_capable"
            reason = {}
        cur_tier = o.get("engine_tier")
        cur_host = (handler.get("execution_host_class") or "")
        mismatch = (
            (verdict == "dbx_capable" and cur_tier == "native_arx_only") or
            (verdict == "arx_required" and cur_tier == "objectdbx_capable"))
        rows.append({
            "op_id": op_id, "family": o.get("family"), "status": o.get("status"),
            "engine_tier": cur_tier, "execution_host_class": cur_host,
            "verdict": verdict, "reason": reason,
            "declared_api_excerpt": declared[:160],
            "code_slice": {"file": src_file, "line": src_line, "chars": len(sl)},
            "mismatch_vs_engine_tier": mismatch,
        })

    from collections import Counter
    vc = Counter(r["verdict"] for r in rows)
    mism = [r for r in rows if r["mismatch_vs_engine_tier"]]
    out = {
        "schema": "ariadne.p2a_dbx_capability_audit.v1",
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "method": "declared native_api tokens + op dispatch code slice + 1-level helper taint (see module docstring)",
        "families": list(_FAMILIES),
        "totals": {"audited": len(rows), **{k: vc[k] for k in sorted(vc)}},
        "mismatches_vs_engine_tier": [r["op_id"] for r in mism],
        "ops": rows,
    }
    jpath = args.out_prefix + ".json"
    io.open(jpath, "w", encoding="utf-8", newline="\n").write(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n")

    lines = ["# P2A -- arx->dbx capability audit (static)", "",
             f"Generated: {out['generated']}  |  audited: {len(rows)} ops "
             f"({_FAMILIES[0]} + {_FAMILIES[1]})", "",
             "| verdict | count |", "|---|---|"]
    lines += [f"| {k} | {vc[k]} |" for k in sorted(vc)]
    lines += ["", f"**Mismatches vs current engine_tier: {len(mism)}**", ""]
    if mism:
        lines += ["| op | engine_tier (current) | audit verdict | evidence |", "|---|---|---|---|"]
        for r in mism:
            ev = ", ".join(r["reason"].get("tokens", []) + r["reason"].get("tainted_helpers", [])) or "-"
            lines += [f"| {r['op_id']} | {r['engine_tier']} | {r['verdict']} | {ev} |"]
    lines += ["", "Honest scope: static necessary-not-sufficient; helper taint 1 level; "
              "link/runtime proof = P2C dbx import audit + build.", ""]
    mpath = args.out_prefix + ".md"
    io.open(mpath, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print(f"[p2a] audited={len(rows)} verdicts={dict(vc)} mismatches={len(mism)}")
    print(f"[p2a] wrote {os.path.relpath(jpath, _REPO)} + .md")
    for r in mism:
        print(f"  MISMATCH {r['op_id']}: tier={r['engine_tier']} vs audit={r['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
