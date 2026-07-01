#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""op_dag_generate.py -- CADOS WAVE-0 F0.5 (plan v2-A3, CRITICAL).

Intent (WHY):
  v2-A3: "The full op DAG is not an enumerated artifact." PART 2 SS2.4 of the
  build plan gives op FAMILIES + generated-node rules + a partial edge list
  (e.g. ``T3a.2 -> T2.1``), not all 517 op_ids with concrete
  predecessors/arg-keys/target-files/tests. This tool closes that gap: for
  EVERY catalogued op_id in ``config/operations.v2.json`` it emits one DAG row
  -- ``{op_id, predecessors[], arg_keys[], target_files[], acceptance_test_id,
  persistence_class}`` -- to ``config/op_dag.json``. SS2.4's edge list becomes a
  *generated projection* of this artifact, not the source of truth.

  The one property every downstream T1+ work item depends on: the emitted
  node set MUST equal the catalogue set EXACTLY (a missing or invented op_id
  fails the audit -- see ``audit`` block below and
  ``tests/unit/test_op_dag_generate.py``).

Catalogue source (discovery, not invention):
  ``config/operations.v2.json`` operations[].id is the SAME id set
  ``tools/operation_coverage_matrix.py`` (``build_row``) and
  ``tools/reconcile_native_registry.py`` (``by_id``) already key off. This tool
  reads no other catalogue source, so all three tools necessarily agree.

Per-field derivation (every rule below is deterministic and sourced from REAL
registry/repo data -- no field is guessed or fabricated; see the emitted
``derivation_rules`` block for the same text, kept alongside the data it
describes):

  persistence_class in {P, D, R, L, NON_GOAL} -- SS2.6 of the plan buckets
    write-capable ops into P (geometry-diff=0) or D (record-diff=0), the rest
    into R (read/compute) or L (live), with the 60 hard-blocked ops NON-GOAL.
    Derived purely from (status, family, write_level.default_write_mode):
      status == "blocked"                                -> NON_GOAL
      family == "live" or default_write_mode == "live_edit" -> L
      default_write_mode == "read"                       -> R
      default_write_mode in (write_copy, write_original):
        family in {entities, brep_solids, geometry_kernel}  -> P
        else                                                -> D
    (Empirically: NON_GOAL count == status=="blocked" count == 60, matching
    the plan's own "60 hard-blocked ... NON-GOAL" accounting exactly.)

  predecessors[] -- the union of two REAL, sourced signals, never an invented
    pairing:
      1. handler.composed_of -- 28 ops carry an authored "this op's own
         implementation composes these other op_ids" list. Every target is
         validated to be a catalogued op_id (a dangling target raises --
         that would be a registry bug, not something to silently drop).
      2. A coarse, family-level read-before-write barrier: the per-op_id
         projection of SS2.4's tier edges (e.g. ``T3a.2 -> T2.1`` = "the read
         extraction for a kind gates that kind's write wiring"). The registry
         only carries `family` (not per-"kind"), so the honest projection is:
         every P/D (write-capable) op depends on every R (read) op in the
         SAME family. This is coarse by construction and is documented as such
         -- it is NOT a claim of item-level 1:1 correspondence.
    Provably acyclic by construction: rule 2 edges only ever run P|D -> R, and
    R (the tier minimum) never gets a rule-2 outgoing edge, so rule 2 alone
    cannot cycle. Empirically no composed_of edge runs {R} -> {P,D} within the
    same family either (checked below), so the two signals cannot jointly
    close a cycle. `topo_check` re-verifies this at generation time regardless
    and FAILS LOUD rather than silently emitting a cyclic graph.

  arg_keys[] -- 15 of 517 op_ids carry a real per-op args schema
    (``schemas/cad_job.v2.schema.json`` allOf if/then blocks) -- the only
    ground-truth arg-key source in this tree today (F2's promotion manifest,
    which would carry arg_keys for every promoted op, does not exist yet).
    Those 15 use their exact ``args.properties`` key set; every other op_id
    gets ``[]`` -- honestly empty, not a guessed field name.

  target_files[] -- path-like tokens parsed out of the op's own
    citation / evidence_refs / tests registry fields, KEPT ONLY if the token
    is NOT under a gitignored, worktree-local evidence root (``runs/``,
    ``staging/``, ``ErrorReports/`` -- ``.gitignore``'s own "regenerable run +
    staging evidence" section) AND ``os.path.isfile`` resolves it on THIS
    worktree at generation time (no invented paths survive). The root
    exclusion is required, not cosmetic: those roots are never committed, so
    a path under them can exist on whichever worktree originally ran a
    probe/build and be absent on every other worktree -- letting one through
    would make target_files (and therefore ``config/op_dag.json``) a function
    of local, worktree-variable disk state instead of a pure function of the
    tracked registry. Additionally, the 3 native op_ids that
    ``tools/patch_engine.NATIVE_WRITE_OP_MAP`` (imported live, never
    hardcoded here) already wires today get ``tools/patch_engine.py`` added,
    since that file demonstrably touches those exact op_ids right now.

  acceptance_test_id -- the registry's own ``tests[0]`` (every implemented op
    already carries a non-empty ``tests[]`` -- enforced independently by
    ``operation_coverage_matrix``'s ``zero_untested_implemented`` gate). This
    is TODAY's best-evidence test reference (dispatch/contract-level), not yet
    the future F3 per-op W+D roundtrip gate (``tools/op_roundtrip_probe.py`` /
    ``tools/cad_op_gate.py`` do not exist in this tree yet) -- when F3 lands it
    should key its per-op test ids 1:1 to op_id so this field becomes exact.

Hard rules (matching the rest of this tool suite): standard library ONLY; no
model, no network -- same registry on disk always yields the same
``config/op_dag.json`` byte-for-byte (no wall-clock timestamp is embedded);
no-fake-success -- an audit failure (node-set mismatch or a cycle) prints the
failure and refuses to write ``config/op_dag.json``, rather than emitting a
dishonest artifact.

Usage:
  python tools/op_dag_generate.py             # build + audit-gate + write
  python tools/op_dag_generate.py --check      # build + audit-gate, no write
"""
from __future__ import annotations

import collections
import json
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPERATIONS_V2 = os.path.join(ROOT, "config", "operations.v2.json")
CAD_JOB_SCHEMA = os.path.join(ROOT, "schemas", "cad_job.v2.schema.json")
OUT_PATH = os.path.join(ROOT, "config", "op_dag.json")
_JSON_ENCODING = "utf-8-sig"

# write_copy/write_original ops in these families create/modify persisted
# geometry directly (roundtrip target = geometry-diff=0); every other
# write-capable family persists a non-geometry record (roundtrip target =
# record-diff=0). See derive_persistence_class.
GEOMETRY_FAMILIES = {"entities", "brep_solids", "geometry_kernel"}

# repo-relative-looking path tokens ending in one of these extensions, pulled
# out of free-text registry fields (citation / evidence_refs / tests).
_PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_./\\-]+\.(?:py|ps1|cs|inc|h|cpp|json|md)\b")

# .gitignore's "Large, regenerable run + staging evidence" roots: never
# committed, so their on-disk presence varies per worktree. A citation /
# evidence_refs / tests token under one of these must never survive into
# target_files even if os.path.isfile happens to resolve True on THIS
# worktree -- see derive_target_files docstring.
_WORKTREE_VARIABLE_ROOTS = ("runs/", "staging/", "ErrorReports/")


def _load(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding=_JSON_ENCODING) as f:
        return json.load(f)


def _dump(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_catalogue() -> Dict[str, Dict[str, Any]]:
    """The catalogued op_id set: config/operations.v2.json operations[].id.

    The SAME field operation_coverage_matrix.build_row (`op.get("id")`) and
    reconcile_native_registry.main (`by_id = {o.get("id"): o ...}`) key off,
    so this tool's catalogue never disagrees with either sibling tool.
    """
    doc = _load(OPERATIONS_V2)
    by_id: Dict[str, Dict[str, Any]] = {}
    for op in doc["operations"]:
        oid = op.get("id")
        if not oid:
            raise ValueError("registry op with no id: %r" % (op,))
        if oid in by_id:
            raise ValueError("duplicate op_id in registry: %s" % oid)
        by_id[oid] = op
    return by_id


def load_arg_key_schema() -> Dict[str, List[str]]:
    """{op_id: sorted[arg_key,...]} for the 15 op_ids with a real per-op args
    schema in schemas/cad_job.v2.schema.json's allOf if/then blocks -- the
    only ground-truth arg-key source that exists today."""
    doc = _load(CAD_JOB_SCHEMA)
    out: Dict[str, List[str]] = {}
    for block in doc.get("allOf") or []:
        try:
            op_id = block["if"]["properties"]["operation"]["const"]
            props = block["then"]["properties"]["args"].get("properties") or {}
        except (KeyError, TypeError):
            continue
        out[op_id] = sorted(props.keys())
    return out


def load_python_wired_op_ids() -> Set[str]:
    """Native op_ids tools/patch_engine.py ALREADY wires today
    (NATIVE_WRITE_OP_MAP, imported live so this generator can never go stale
    relative to the actual wiring)."""
    tools_dir = os.path.join(ROOT, "tools")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import patch_engine  # sibling tool, stdlib-only; safe to import (see module docstring)
    return set(patch_engine.NATIVE_WRITE_OP_MAP.values())


def derive_persistence_class(op: Dict[str, Any]) -> str:
    """P (geometry-diff=0) | D (record-diff=0) | R (read/compute) |
    L (live/interactive) | NON_GOAL (hard-blocked). See module docstring for
    the full rule; deterministic function of (status, family,
    write_level.default_write_mode) only."""
    if op.get("status") == "blocked":
        return "NON_GOAL"
    wl = (op.get("write_level") or {}).get("default_write_mode")
    fam = op.get("family")
    if fam == "live" or wl == "live_edit":
        return "L"
    if wl == "read":
        return "R"
    if wl in ("write_copy", "write_original"):
        return "P" if fam in GEOMETRY_FAMILIES else "D"
    return "R"


def _extract_existing_files(*texts: Optional[str]) -> List[str]:
    found: List[str] = []
    for text in texts:
        if not text:
            continue
        for tok in _PATH_TOKEN_RE.findall(text):
            cand = tok.strip(".").replace("\\", "/")
            if cand.startswith(_WORKTREE_VARIABLE_ROOTS):
                continue
            if cand not in found and os.path.isfile(os.path.join(ROOT, cand)):
                found.append(cand)
    return found


def derive_target_files(op: Dict[str, Any], python_wired_ids: Set[str]) -> List[str]:
    """Files this op_id is anchored to TODAY, restricted to paths verified to
    exist on disk at generation time (Rule 12: no invented paths)."""
    texts: List[str] = []
    if op.get("citation"):
        texts.append(op["citation"])
    for e in (op.get("evidence_refs") or []):
        texts.append(e.split("#", 1)[0].split("::", 1)[0])
    for t in (op.get("tests") or []):
        texts.append(t.split("::", 1)[0])
    files = set(_extract_existing_files(*texts))
    if op.get("id") in python_wired_ids:
        files.add("tools/patch_engine.py")
    return sorted(files)


def derive_acceptance_test_id(op: Dict[str, Any]) -> Optional[str]:
    """The registry's own tests[0] -- see module docstring for why this (and
    not a fabricated id) is the correct field today."""
    tests = op.get("tests") or []
    return tests[0] if tests else None


def derive_predecessors(by_id: Dict[str, Dict[str, Any]],
                         pclass: Dict[str, str]) -> Dict[str, List[str]]:
    """{op_id: sorted[predecessor_op_id,...]}. See module docstring for the
    two source signals (composed_of + coarse same-family P|D -> R gate)."""
    preds: Dict[str, Set[str]] = collections.defaultdict(set)

    for oid, op in by_id.items():
        for c in (op.get("handler") or {}).get("composed_of") or []:
            if c not in by_id:
                raise ValueError(
                    "handler.composed_of dangling target: %s -> %s (not in catalogue)" % (oid, c))
            preds[oid].add(c)

    read_by_family: Dict[str, List[str]] = collections.defaultdict(list)
    for oid, op in by_id.items():
        if pclass[oid] == "R":
            read_by_family[op.get("family")].append(oid)

    for oid, op in by_id.items():
        if pclass[oid] in ("P", "D"):
            for r in read_by_family.get(op.get("family"), ()):
                if r != oid:
                    preds[oid].add(r)

    return {oid: sorted(preds.get(oid, ())) for oid in by_id}


def topo_check(node_ids: Iterable[str],
               predecessors: Dict[str, List[str]]) -> Tuple[bool, Optional[List[str]]]:
    """DFS white/gray/black cycle check. Edge u -> v (v in predecessors[u])
    means "v must be resolvable before u". Returns (acyclic, cycle_path).
    Stdlib only (no networkx / third-party graph lib)."""
    ids = list(node_ids)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {oid: WHITE for oid in ids}
    path: List[str] = []

    sys.setrecursionlimit(max(10000, len(ids) * 4))

    def visit(u: str) -> Optional[List[str]]:
        color[u] = GRAY
        path.append(u)
        for v in predecessors.get(u, ()):
            if color.get(v) == GRAY:
                i = path.index(v)
                return path[i:] + [v]
            if color.get(v) == WHITE:
                cyc = visit(v)
                if cyc:
                    return cyc
        path.pop()
        color[u] = BLACK
        return None

    for oid in sorted(ids):
        if color[oid] == WHITE:
            cyc = visit(oid)
            if cyc:
                return False, cyc
    return True, None


_DERIVATION_RULES = {
    "catalogue": "config/operations.v2.json operations[].id -- the same id set "
                 "operation_coverage_matrix.py / reconcile_native_registry.py key off",
    "persistence_class": "status=='blocked' -> NON_GOAL; family=='live' or "
                          "write_level.default_write_mode=='live_edit' -> L; "
                          "default_write_mode=='read' -> R; default_write_mode in "
                          "(write_copy, write_original): family in {entities, brep_solids, "
                          "geometry_kernel} -> P else D",
    "predecessors": "handler.composed_of (authored, validated against the catalogue) UNION "
                    "coarse same-family P|D -> R read-before-write gate (SS2.4 tier-barrier "
                    "projection); acyclic by construction + defensively re-checked "
                    "(tests/unit/test_op_dag_generate.py)",
    "arg_keys": "schemas/cad_job.v2.schema.json allOf if/then args.properties keys for the 15 "
                "op_ids that carry one; [] elsewhere (no per-op arg schema authored yet -- "
                "honest, not guessed)",
    "target_files": "citation / evidence_refs / tests path-like tokens, kept ONLY if NOT "
                     "under a gitignored worktree-local evidence root (runs/, staging/, "
                     "ErrorReports/) and os.path.isfile resolves on this worktree at "
                     "generation time, plus tools/patch_engine.py for op_ids "
                     "NATIVE_WRITE_OP_MAP already wires (no invented paths, no "
                     "worktree-variable paths)",
    "acceptance_test_id": "registry tests[0] (current best-evidence test ref; F3's future "
                          "per-op W+D roundtrip gate is not built in this tree yet)",
}


def build_dag() -> Dict[str, Any]:
    by_id = load_catalogue()
    catalogue_set = set(by_id)
    arg_schema = load_arg_key_schema()
    python_wired_ids = load_python_wired_op_ids()
    pclass = {oid: derive_persistence_class(op) for oid, op in by_id.items()}
    predecessors = derive_predecessors(by_id, pclass)
    acyclic, cycle = topo_check(by_id.keys(), predecessors)

    nodes = []
    for oid in sorted(by_id):
        op = by_id[oid]
        nodes.append({
            "op_id": oid,
            "predecessors": predecessors[oid],
            "arg_keys": arg_schema.get(oid, []),
            "target_files": derive_target_files(op, python_wired_ids),
            "acceptance_test_id": derive_acceptance_test_id(op),
            "persistence_class": pclass[oid],
        })

    node_set = {n["op_id"] for n in nodes}
    missing = sorted(catalogue_set - node_set)
    invented = sorted(node_set - catalogue_set)
    by_pclass = collections.Counter(n["persistence_class"] for n in nodes)
    edge_count = sum(len(n["predecessors"]) for n in nodes)

    return {
        "schema": "ariadne.cad_os.op_dag.v1",
        "packet": "CADOS_WAVE0_F05",
        "generated_from": "config/operations.v2.json",
        "generated_by": "tools/op_dag_generate.py",
        "derivation_rules": _DERIVATION_RULES,
        "totals": {
            "catalogue_count": len(catalogue_set),
            "node_count": len(nodes),
            "edge_count": edge_count,
            "by_persistence_class": dict(sorted(by_pclass.items())),
        },
        "audit": {
            "node_set_equals_catalogue_set": (not missing and not invented),
            "missing_from_dag": missing,
            "invented_op_ids": invented,
            "acyclic": acyclic,
            "cycle_example": cycle,
        },
        "nodes": nodes,
    }


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    check_only = "--check" in argv

    dag = build_dag()
    audit = dag["audit"]
    t = dag["totals"]

    print("op_dag_generate: catalogue=%d node_count=%d edge_count=%d"
          % (t["catalogue_count"], t["node_count"], t["edge_count"]))
    print("  by_persistence_class:", t["by_persistence_class"])

    if not audit["node_set_equals_catalogue_set"]:
        print("AUDIT FAIL: node set != catalogue set")
        print("  missing_from_dag:", audit["missing_from_dag"][:20])
        print("  invented_op_ids:", audit["invented_op_ids"][:20])
        return 1
    if not audit["acyclic"]:
        print("AUDIT FAIL: cycle detected:", audit["cycle_example"])
        return 1

    print("  audit: node_set_equals_catalogue_set=True acyclic=True")

    if check_only:
        print("  (--check: not written)")
        return 0

    _dump(OUT_PATH, dag)
    print("  written:", os.path.relpath(OUT_PATH, ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
