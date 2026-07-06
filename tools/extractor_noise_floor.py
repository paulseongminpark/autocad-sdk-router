#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extractor_noise_floor.py -- CAD OS Layer Wave-0 blocker: extractor noise-floor
probe (F11, PLAN Appendix "F11 -- Extractor noise-floor probe", RT-FOLD R4-12).

Finding this closes (R4-12, MEDIUM/HIGH): ``cad_diff.DEFAULT_GEOMETRY_TOLERANCE``
is a fixed constant, and the D-half's "2*tol" perturbation is only a reliable
discriminator if it sits comfortably ABOVE the extractor's OWN run-to-run
numeric jitter. That jitter -- the "noise floor" -- was, before this module,
UNMEASURED.

Method (PLAN F11, verbatim): extract the SAME unchanged DWG twice, diff the two
IRs at tol=0; any non-zero leaf IS the noise floor. Assert
extract-twice-at-tol-0 == 0 (extractor deterministic); THEN assert
``2*tol > noise_floor``. If the first assert fails, the extractor is
non-deterministic and NO geometry-basis claim is falsifiable until fixed --
this is a WAVE-0 blocker, not a soft warning.

Why handle-join is correct here (not comparison_basis="geometry"): two extracts
of the identical, unmodified DWG file MUST realize the same handle set -- a DWG
handle is intrinsic to the file bytes; a plain read never re-issues one. This
module therefore joins the two IRs' entities by handle (reusing
``cad_diff.index_entities_by_handle``, the same join ``cad_diff.compute_diff``
uses by default) and then walks every leaf of ``layer`` / ``dxf_name`` /
``bbox`` / ``geometry`` at raw (tol=0) precision -- the exact field set
``cad_diff.classify_change`` compares, so this probe measures noise on exactly
the fields any geometry-basis diff claim relies on. ``source`` (extraction
provenance: staged path / sha256 / extracted_at timestamp) is deliberately OUT
of scope -- it legitimately differs between two runs of the SAME unchanged DWG
and is not part of any geometry-basis claim. A handle-set mismatch between the
two runs (an added/removed handle) is itself reported as evidence of
non-determinism, never silently dropped.

Hard rules (CAD OS Layer build invariants -- matches cad_diff.py / validator.py):
  * Standard library ONLY (Python 3.12). No third-party imports.
  * No-fake-success: a leaf that cannot be compared numerically (a structural
    mismatch: an added/removed handle, a changed string field, a type change, a
    list-length change) still counts as non-determinism -- ``noise_floor``
    stays the largest NUMERIC delta only, but ``assert_extractor_deterministic``
    / ``assert_tolerance_safe`` both fail whenever ANY non-numeric leaf differs,
    so a non-numeric drift can never hide behind a reported "noise_floor: 0.0".
  * Deterministic: no timestamps, no randomness in the report body; the same
    pair of IRs always yields the same report.
  * Read-only: this module never writes a DWG. The live path
    (``extract_twice``) stages COPIES via ``cadctl.Cad.inspect`` (same
    read-only contract as cadctl) and writes only the report/run artifacts
    under the caller-given ``out_dir``.
  * Truthful sibling degradation: ``cad_diff`` / ``cadctl`` / ``ir_builder`` are
    imported via ``_import_optional``; a missing sibling degrades a public
    function to a ``not_implemented`` result, never a crash, never a faked PASS.

Public API:
    NOISE_FLOOR_SCHEMA_ID
    DEFAULT_TOLERANCE                     # mirrors cad_diff.DEFAULT_GEOMETRY_TOLERANCE
    load_ir(path) -> dict                                        # BOM-tolerant
    write_report(report, path) -> str
    diff_leaves(ir_a: dict, ir_b: dict) -> list[dict]
    measure_noise_floor(ir_a: dict, ir_b: dict) -> dict
    assert_extractor_deterministic(measurement: dict) -> bool
    tolerance_exceeds_noise(noise_floor: float, tol: float) -> bool
    assert_tolerance_safe(measurement: dict, tol: float) -> bool
    run_probe(ir_a: dict, ir_b: dict, tol: float = DEFAULT_TOLERANCE) -> dict
    extract_twice(dwg_path, out_dir, cad=None) -> dict        # LIVE -- needs the accoreconsole runtime via cadctl.Cad
    run_live_probe(dwg_path, out_dir, tol=DEFAULT_TOLERANCE, cad=None) -> dict  # LIVE end-to-end

CLI:
    python tools/extractor_noise_floor.py
        -- inline self-test (two independent copies of ir_builder's fixture IR;
           no DWG / runtime needed)
    python tools/extractor_noise_floor.py --dwg <p> --out <dir> [--tol T]
        -- LIVE: extract <p> twice via cadctl.Cad.inspect, then measure
    python tools/extractor_noise_floor.py --ir-a <a.json> --ir-b <b.json> [--tol T] [--out <dir>]
        -- OFFLINE: measure against two already-extracted dwg_graph_ir.json files

Exit codes: 0=PASS, 1=FAIL (an assert was violated), 2=bad usage,
3=unavailable/not_implemented (no runtime / sibling module missing -- no fake pass).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROUTER_HOME = os.path.dirname(_THIS_DIR)

NOISE_FLOOR_SCHEMA_ID = "ariadne.extractor_noise_floor.v1"
IR_SCHEMA_ID = "ariadne.dwg_graph_ir.v1"

# On this box the catalog/config/IR JSON may carry a UTF-8 BOM; json.load on the
# cp949 locale needs utf-8-sig to decode it. Writes are plain UTF-8.
_JSON_ENCODING = "utf-8-sig"

# Default production geometry tolerance this probe safety-checks the noise
# floor against. Mirrors cad_diff.DEFAULT_GEOMETRY_TOLERANCE (the AutoCAD
# COMPARETOLERANCE analog) as a literal -- kept independent of a module-level
# cad_diff import so this module never depends on a sibling at import time.
DEFAULT_TOLERANCE = 1e-6

# Entity fields walked for noise -- identical scope to cad_diff.classify_change,
# so this probe measures noise on exactly the fields a geometry-basis diff claim
# relies on. `source` (extraction provenance) is deliberately excluded.
_ENTITY_SCALAR_FIELDS = ("layer", "dxf_name")
_ENTITY_NESTED_FIELDS = ("bbox", "geometry")


def _import_optional(module_name: str):
    """Import a sibling-lane module if present, else return None (no crash).

    Mirrors the truthful-degradation pattern used across the CAD OS Layer: a
    sibling module that is not on disk / not importable degrades the dependent
    feature to ``not_implemented`` instead of raising at import time.
    """
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    try:
        return __import__(module_name)
    except Exception:  # pragma: no cover - defensive; sibling truly absent
        return None


# --------------------------------------------------------------------------- #
# IO (BOM-tolerant, mirrors cad_diff.load_ir / write_diff)
# --------------------------------------------------------------------------- #

def load_ir(path) -> Dict[str, Any]:
    """Load an IR JSON document (BOM-tolerant)."""
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def write_report(report: Dict[str, Any], path) -> str:
    """Write a noise-floor report (UTF-8, pretty). Returns the path written."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(report, ensure_ascii=False, indent=2))
        fh.write("\n")
    return str(path)


# --------------------------------------------------------------------------- #
# Leaf-level (tol=0) comparison
# --------------------------------------------------------------------------- #

def _leaf_path(parts: List[str]) -> str:
    return ".".join(parts) if parts else "$"


def _walk_leaves(pre: Any, post: Any, parts: List[str], out: List[Dict[str, Any]]) -> None:
    """Recursively compare two JSON-like values at raw (tol=0) precision.

    Appends one record per DIFFERING terminal onto ``out``:
      * ``kind="numeric"``    -- two comparable numbers that differ (carries
        ``delta`` = abs(pre - post)); int vs float of equal VALUE is NOT a
        diff (JSON int/float formatting must never register as noise).
      * ``kind="structural"`` -- a key/length/type mismatch (a leaf present on
        only one side, a list-length change, or two differing non-scalars).
      * ``kind="scalar"``     -- two differing same-typed non-numeric scalars
        (e.g. a changed ``block_name`` string).

    ``bool`` is excluded from the numeric branch (an int subclass but never a
    coordinate) -- same guard as ``cad_diff._quantize``.
    """
    if isinstance(pre, bool) or isinstance(post, bool):
        if pre != post:
            out.append({"path": _leaf_path(parts), "kind": "scalar",
                       "before": pre, "after": post})
        return
    if isinstance(pre, (int, float)) and isinstance(post, (int, float)):
        if pre != post:
            out.append({"path": _leaf_path(parts), "kind": "numeric",
                       "before": pre, "after": post, "delta": abs(pre - post)})
        return
    if isinstance(pre, dict) and isinstance(post, dict):
        for k in sorted(set(pre) | set(post), key=str):
            if k not in pre or k not in post:
                out.append({"path": _leaf_path(parts + [str(k)]), "kind": "structural",
                           "before": pre.get(k, "<absent>"), "after": post.get(k, "<absent>")})
                continue
            _walk_leaves(pre[k], post[k], parts + [str(k)], out)
        return
    if isinstance(pre, (list, tuple)) and isinstance(post, (list, tuple)):
        if len(pre) != len(post):
            out.append({"path": _leaf_path(parts), "kind": "structural",
                       "before": "len=%d" % len(pre), "after": "len=%d" % len(post)})
            return
        for i, (a, b) in enumerate(zip(pre, post)):
            _walk_leaves(a, b, parts + [str(i)], out)
        return
    if pre != post:
        kind = "scalar" if type(pre) is type(post) else "structural"
        out.append({"path": _leaf_path(parts), "kind": kind, "before": pre, "after": post})


# --------------------------------------------------------------------------- #
# Entity-level diff (handle join, reusing cad_diff's index)
# --------------------------------------------------------------------------- #

def diff_leaves(ir_a: Dict[str, Any], ir_b: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Diff every entity leaf between two IRs of the SAME (unchanged) DWG at tol=0.

    Entities are paired by handle -- a plain read of an unmodified DWG can never
    re-issue a handle, so a handle-set mismatch is itself reported as evidence
    of non-determinism (or a caller mistake: the two IRs are not of the same
    drawing), never silently ignored.

    Returns the flat list of differing-leaf records; an empty list means the
    two IRs are IDENTICAL on every compared field.

    Raises RuntimeError if ``cad_diff`` (the sibling that owns the handle join)
    is not importable -- callers that must degrade truthfully instead of
    raising should catch this (``run_probe`` does not call this directly with
    an absent cad_diff in the supported flows; the CLI/self-test check for
    ``ir_builder`` availability up front for the same reason).
    """
    cad_diff = _import_optional("cad_diff")
    if cad_diff is None or not hasattr(cad_diff, "index_entities_by_handle"):
        raise RuntimeError("cad_diff.index_entities_by_handle unavailable (sibling module missing)")

    by_handle_a, problems_a = cad_diff.index_entities_by_handle(ir_a or {})
    by_handle_b, problems_b = cad_diff.index_entities_by_handle(ir_b or {})
    handles_a = set(by_handle_a)
    handles_b = set(by_handle_b)

    leaves: List[Dict[str, Any]] = []

    for h in sorted(handles_a - handles_b):
        leaves.append({"handle": h, "path": "$entity", "kind": "structural",
                       "before": "present", "after": "<absent>"})
    for h in sorted(handles_b - handles_a):
        leaves.append({"handle": h, "path": "$entity", "kind": "structural",
                       "before": "<absent>", "after": "present"})

    for h in sorted(handles_a & handles_b):
        ea, eb = by_handle_a[h], by_handle_b[h]
        for field in _ENTITY_SCALAR_FIELDS:
            va, vb = ea.get(field), eb.get(field)
            if va != vb:
                leaves.append({"handle": h, "path": field, "kind": "scalar",
                               "before": va, "after": vb})
        for field in _ENTITY_NESTED_FIELDS:
            sub: List[Dict[str, Any]] = []
            _walk_leaves(ea.get(field), eb.get(field), [field], sub)
            for rec in sub:
                rec["handle"] = h
                leaves.append(rec)

    for label, problems in (("ir_a", problems_a), ("ir_b", problems_b)):
        for p in problems:
            leaves.append({"handle": None, "path": "$join", "kind": "join_problem",
                          "before": None, "after": None, "detail": "%s: %s" % (label, p)})

    return leaves


# --------------------------------------------------------------------------- #
# Noise-floor measurement + WAVE-0 asserts
# --------------------------------------------------------------------------- #

def measure_noise_floor(ir_a: Dict[str, Any], ir_b: Dict[str, Any]) -> Dict[str, Any]:
    """Measure the extractor noise floor between two IRs of the SAME unchanged DWG.

    ``noise_floor`` is the LARGEST absolute numeric delta among differing
    leaves that ARE numerically comparable -- ``0.0`` when none differ. A leaf
    that differs but carries no numeric magnitude (a structural mismatch, a
    scalar/string change, an added/removed entity, an unjoinable handle) is
    counted separately in ``non_numeric_leaf_count`` and is NOT folded into
    ``noise_floor`` -- callers MUST check ``non_numeric_leaf_count`` (both
    ``assert_extractor_deterministic`` and ``assert_tolerance_safe`` do) rather
    than reading ``noise_floor`` in isolation, so a non-numeric drift can never
    hide behind a reported "noise_floor: 0.0".
    """
    leaves = diff_leaves(ir_a, ir_b)
    numeric = [l for l in leaves if l["kind"] == "numeric"]
    non_numeric = [l for l in leaves if l["kind"] != "numeric"]

    noise_floor = max((l["delta"] for l in numeric), default=0.0)
    worst = sorted(numeric, key=lambda l: -l["delta"])[:10]

    return {
        "noise_floor": noise_floor,
        "leaf_count": len(leaves),
        "numeric_leaf_count": len(numeric),
        "non_numeric_leaf_count": len(non_numeric),
        "entity_count_a": len((ir_a or {}).get("entities") or []),
        "entity_count_b": len((ir_b or {}).get("entities") or []),
        "worst_leaves": worst,
        "non_numeric_leaves": non_numeric[:10],
    }


def assert_extractor_deterministic(measurement: Dict[str, Any]) -> bool:
    """extract-twice-at-tol-0 == 0: the two IRs must be IDENTICAL on every
    compared leaf (numeric AND non-numeric) -- any difference at all is noise.
    """
    return measurement["leaf_count"] == 0


def tolerance_exceeds_noise(noise_floor: float, tol: float) -> bool:
    """The literal WAVE-0 assert: ``2*tol > noise_floor`` (strict)."""
    return (2.0 * tol) > noise_floor


def assert_tolerance_safe(measurement: Dict[str, Any], tol: float) -> bool:
    """``2*tol > noise_floor`` -- AND no non-numeric noise (a structural/scalar
    change has no magnitude for a numeric tolerance to safely bound, so it is
    treated as unsafe by construction rather than silently ignored).
    """
    if measurement["non_numeric_leaf_count"] > 0:
        return False
    return tolerance_exceeds_noise(measurement["noise_floor"], tol)


def run_probe(ir_a: Dict[str, Any], ir_b: Dict[str, Any],
              tol: float = DEFAULT_TOLERANCE) -> Dict[str, Any]:
    """Run the full F11 probe: measure, then both WAVE-0 asserts in sequence.

    Never raises for a normal measurement; the report's ``status`` is the
    truth (``PASS`` only when BOTH asserts hold).
    """
    measurement = measure_noise_floor(ir_a, ir_b)
    deterministic = assert_extractor_deterministic(measurement)
    tol_safe = assert_tolerance_safe(measurement, tol)
    passed = deterministic and tol_safe

    note: Optional[str] = None
    if not deterministic:
        if measurement["non_numeric_leaf_count"] > 0:
            note = ("extractor is NON-DETERMINISTIC: %d non-numeric leaf(ves) differ "
                    "(structural/scalar/added-removed/join) between the two extracts "
                    "of the SAME unchanged DWG -- no geometry-basis claim is "
                    "falsifiable until fixed (WAVE-0 blocker, PLAN F11 / R4-12)."
                    % measurement["non_numeric_leaf_count"])
        else:
            note = ("extractor is NON-DETERMINISTIC: noise_floor=%r (!= 0) across %d "
                    "numeric leaf(ves) -- no geometry-basis claim is falsifiable "
                    "until fixed (WAVE-0 blocker, PLAN F11 / R4-12)."
                    % (measurement["noise_floor"], measurement["numeric_leaf_count"]))
    elif not tol_safe:
        note = ("2*tol (%r) <= noise_floor (%r): the configured geometry tolerance has "
                "no safety margin over the measured extractor noise floor (R4-12)."
                % (2.0 * tol, measurement["noise_floor"]))

    return {
        "schema": NOISE_FLOOR_SCHEMA_ID,
        "status": "PASS" if passed else "FAIL",
        "tol": tol,
        "noise_floor": measurement["noise_floor"],
        "extractor_deterministic": deterministic,
        "tolerance_safe_2x": tol_safe,
        "wave0_blocker": not passed,
        "note": note,
        "measurement": measurement,
    }


# --------------------------------------------------------------------------- #
# LIVE double-extract (needs the accoreconsole runtime via cadctl.Cad)
# --------------------------------------------------------------------------- #

def extract_twice(dwg_path: str, out_dir: str, cad=None) -> Dict[str, Any]:
    """Run the LIVE cadctl inspect() extraction twice against the SAME unchanged
    DWG (``dwg_path`` is never modified -- ``cadctl.Cad.inspect`` stages its own
    read-only copy each call). Writes run A to ``<out_dir>/run_a`` and run B to
    ``<out_dir>/run_b``.

    Truthful degradation: if ``cadctl`` is missing, or the router/accoreconsole
    is unavailable, returns ``status="not_implemented"``/``"unavailable"``
    (never raises, never fakes an IR) -- the caller (``run_live_probe`` / CLI)
    surfaces that as DONE_NEEDS_RUNTIME, not a silent pass.
    """
    cadctl = _import_optional("cadctl")
    if cadctl is None or not hasattr(cadctl, "Cad"):
        return {"status": "not_implemented",
               "reason": "cadctl.Cad unavailable (sibling module missing)"}

    cad = cad or cadctl.Cad()
    out_dir_p = os.path.abspath(out_dir)
    run_a_dir = os.path.join(out_dir_p, "run_a")
    run_b_dir = os.path.join(out_dir_p, "run_b")

    env_a = cad.inspect(str(dwg_path), run_a_dir)
    env_b = cad.inspect(str(dwg_path), run_b_dir)

    ir_path_a = env_a.get("dwg_graph_ir")
    ir_path_b = env_b.get("dwg_graph_ir")
    ok = bool(env_a.get("status") == "ok" and env_b.get("status") == "ok"
              and ir_path_a and ir_path_b)

    return {
        "status": "ok" if ok else "unavailable",
        "reason": None if ok else "one or both live extractions did not return status=ok",
        "run_a": env_a,
        "run_b": env_b,
        "ir_path_a": ir_path_a,
        "ir_path_b": ir_path_b,
    }


def run_live_probe(dwg_path: str, out_dir: str, tol: float = DEFAULT_TOLERANCE,
                   cad=None) -> Dict[str, Any]:
    """LIVE end-to-end F11 probe: extract the SAME unchanged DWG twice, then
    ``run_probe`` over the two resulting IRs.

    Needs the accoreconsole runtime (via ``cadctl.Cad.inspect``); returns a
    truthful ``not_implemented``/``unavailable`` envelope (never a fake PASS)
    when that runtime is not reachable from this process -- this IS the
    DONE_NEEDS_RUNTIME path.
    """
    extraction = extract_twice(dwg_path, out_dir, cad=cad)
    if extraction["status"] != "ok":
        return {
            "schema": NOISE_FLOOR_SCHEMA_ID,
            "status": extraction["status"],
            "reason": extraction.get("reason"),
            "extraction": extraction,
        }
    ir_a = load_ir(extraction["ir_path_a"])
    ir_b = load_ir(extraction["ir_path_b"])
    report = run_probe(ir_a, ir_b, tol=tol)
    report["extraction"] = extraction
    return report


# --------------------------------------------------------------------------- #
# Self-demo (__main__ bare invocation): two independent copies of a fixture IR
# --------------------------------------------------------------------------- #

def _selftest() -> int:
    """Bare-invocation self-demo (no args): two INDEPENDENT copies of the SAME
    fixture IR simulate an identical re-extraction -- proves the tol-0
    determinism logic without needing a DWG or a live runtime.
    """
    ir_builder = _import_optional("ir_builder")
    if ir_builder is None or not hasattr(ir_builder, "make_fixture_ir"):
        print("== extractor_noise_floor self-demo (F11) ==")
        print("ir_builder.make_fixture_ir unavailable -> NOT_IMPLEMENTED (no fake PASS)")
        return 3

    ir_a = ir_builder.make_fixture_ir()
    ir_b = json.loads(json.dumps(ir_a))  # independent deep copy (stdlib)

    report = run_probe(ir_a, ir_b)

    print("== extractor_noise_floor self-demo (F11) ==")
    print("schema                  : %s" % report["schema"])
    print("entities (a/b)          : %d/%d" % (report["measurement"]["entity_count_a"],
                                               report["measurement"]["entity_count_b"]))
    print("noise_floor             : %r" % report["noise_floor"])
    print("extractor_deterministic : %s" % report["extractor_deterministic"])
    print("tolerance_safe_2x (tol=%r) : %s" % (report["tol"], report["tolerance_safe_2x"]))
    print("RESULT                  : %s" % report["status"])

    return 0 if report["status"] == "PASS" else 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="extractor_noise_floor.py",
        description="F11 WAVE-0 blocker: measure the extractor's run-to-run "
                    "noise floor and assert it against the geometry tolerance "
                    "(emits ariadne.extractor_noise_floor.v1).")
    ap.add_argument("--dwg", default=None,
                    help="LIVE mode: DWG path, extracted twice via cadctl.Cad.inspect")
    ap.add_argument("--out", default=None,
                    help="LIVE mode: required run directory for the two extractions "
                         "and the report; OFFLINE mode: optional report-only dir")
    ap.add_argument("--ir-a", dest="ir_a", default=None,
                    help="OFFLINE mode: first already-extracted dwg_graph_ir.json")
    ap.add_argument("--ir-b", dest="ir_b", default=None,
                    help="OFFLINE mode: second already-extracted dwg_graph_ir.json")
    ap.add_argument("--tol", type=float, default=DEFAULT_TOLERANCE,
                    help="production geometry tolerance to safety-check against "
                         "(default: %r, mirrors cad_diff.DEFAULT_GEOMETRY_TOLERANCE)"
                         % DEFAULT_TOLERANCE)
    args = ap.parse_args(argv)

    if args.dwg is None and args.ir_a is None and args.ir_b is None:
        return _selftest()

    if args.dwg:
        if not args.out:
            ap.error("--dwg (LIVE mode) requires --out <run dir>")
            return 2  # pragma: no cover - ap.error exits already
        report = run_live_probe(args.dwg, args.out, tol=args.tol)
    elif args.ir_a and args.ir_b:
        report = run_probe(load_ir(args.ir_a), load_ir(args.ir_b), tol=args.tol)
    else:
        ap.error("offline mode requires BOTH --ir-a and --ir-b")
        return 2  # pragma: no cover - ap.error exits already

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        write_report(report, os.path.join(args.out, "noise_floor_report.json"))
    print(text)

    status = report.get("status")
    if status == "PASS":
        return 0
    if status in ("not_implemented", "unavailable"):
        return 3
    return 1


if __name__ == "__main__":
    sys.exit(main())
