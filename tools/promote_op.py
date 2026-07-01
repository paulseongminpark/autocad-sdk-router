#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""promote_op.py -- CADOS WAVE-0 F2: the promotion harness.

PLAN.md PART 2 sec 2.0 legislates every write node against **three promotion
axes**, all satisfied atomically before a ``patch_op`` may be considered
agent-runnable:

  Axis A -- Registry policy (``config/operations.v2.json``
      ``operations[].policy.status_policy``): flip ``catalogued_not_runnable``
      -> ``implemented`` (+ merge an evidence_ref pointing at the F1 probe
      row). **Flip ONLY after F1 (``tools/probe_reachability.py`` /
      ``measure/reachable_matrix.jsonl``) marks ``native_op`` RUNNABLE --
      never RUNNABLE_BUT_DEGENERATE, never pending/unprobed.**
  Axis B -- Python wiring: the native write-op MAP entry (``patch_op ->
      native_op`` in the owning ``tools/patch_ops/<family>.py`` module's
      ``WRITE_OP_MAP``) and the matching ``build_job_args`` arg-branch
      (marshalling exactly ``arg_keys[]`` through to the native job). RT-FOLD
      H-R4 ("map key without arg branch then default entity") is exactly the
      failure this module refuses to ever produce: the map entry and its arg
      branch are generated together, in the SAME file write, or neither is.
  Axis C -- C++ reachability (``AriadneNativeJob.cpp`` dispatch). No file
      edit here: PLAN.md notes this gate is "already ON for the simple
      entity/annotation/solid create families", and F1's live RUNNABLE
      classification is itself proof the same C++ dispatch chain a promotion
      would rely on is already reachable -- Axis A's gate doubles as Axis C's
      confirmation (recorded in the diff for audit, never a file write).

A promotion is one row of ``config/promotion_manifest.json``::

    {"patch_op": ..., "native_op": ..., "arg_keys": [...], "ir_kind": ...,
     "persistence_class": "P|D|R|L", "risk": "low|medium|high"}

``ir_kind`` may be ``null`` for a record-level (non-entity) op with no
``ir_to_patch`` builder case yet -- PLAN.md's F2 node text names only the
map-entry + arg-branch as the atomic pair this tool generates; the
``ir_to_patch.py`` / ``patch_ops.ir_op_for`` builder-case wiring is a
different (already-forward-declared, see ``patch_ops.entities.ir_op_for``'s
"Tier 2/3" cases) surface this module does not edit. ``OP_REGISTRY_MAP`` /
``_OP_RISK`` (``tools/patch_engine.py``) are a THIRD, separate vocab surface
kept in lockstep by F8 (``tools/reconcile_native_registry.py``, extended),
not by F2.

No-fake-success (RT-FOLD R2-A9 / Rule 12): applying a promotion writes
``config/operations.v2.json`` **in-worktree as a throwaway for the local gate
only** -- the orchestrator's post-merge ``reconcile_native_registry.py`` is
the file's sole author across a real merge; every write this module makes is
captured byte-for-byte in ``PromotionResult.backups`` so ``revert_promotion``
can restore the pre-promotion bytes exactly.

Two entry points:
    compute_promotion(row, ...)  -- PURE, read-only. Runs the Axis-A gate and
        computes the exact 3-axis diff a promotion WOULD write, without
        touching any file. Safe to call any number of times.
    apply_promotion(row, ...)    -- calls compute_promotion; if (and only if)
        its status is PROMOTED, writes Axis A + Axis B together (reverting
        either write on any failure), then re-imports the touched family
        module fresh and asserts the map entry and arg branch actually
        cohere (the H-R4 "unknown-op guard").

Standard library only. Config/registry JSON on this box is BOM-prefixed --
read with encoding="utf-8-sig" (matches cadctl.py / reconcile_native_registry
convention); operations.v2.json is written back BOM-prefixed too (byte-format
matches reconcile_native_registry._dump_reg: indent=2, no trailing newline).

Usage:
    python tools/promote_op.py --list
    python tools/promote_op.py --patch-op create_line
    python tools/promote_op.py --patch-op write.block.simple_create --apply
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_THIS_FILE = os.path.abspath(__file__)
_THIS_DIR = os.path.dirname(_THIS_FILE)
ROUTER_HOME = os.path.dirname(_THIS_DIR)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import probe_reachability as f1  # noqa: E402  (RUNNABLE/RUNNABLE_BUT_DEGENERATE + matrix path)

_JSON_ENCODING = "utf-8-sig"

MANIFEST_PATH = os.path.join(ROUTER_HOME, "config", "promotion_manifest.json")
OPERATIONS_V2_PATH = os.path.join(ROUTER_HOME, "config", "operations.v2.json")
REACHABLE_MATRIX_PATH = str(f1.DEFAULT_OUT)
PATCH_OPS_DIR = os.path.join(ROUTER_HOME, "tools", "patch_ops")

FAMILY_FILES: Dict[str, str] = {
    "entities": os.path.join(PATCH_OPS_DIR, "entities.py"),
    "blocks": os.path.join(PATCH_OPS_DIR, "blocks.py"),
    "tables": os.path.join(PATCH_OPS_DIR, "tables.py"),
    "db": os.path.join(PATCH_OPS_DIR, "db.py"),
}

REQUIRED_ROW_FIELDS = ("patch_op", "native_op", "arg_keys", "ir_kind",
                        "persistence_class", "risk")
VALID_PERSISTENCE_CLASSES = ("P", "D", "R", "L")

# native_op prefix -> owning tools/patch_ops/<family>.py module (mirrors each
# family module's own docstring scope). A manifest row may override via its
# optional "family" key; unmatched prefixes fall to "db" (patch_ops.db's own
# docstring: the catch-all placeholder for the next family).
_FAMILY_PREFIXES = (
    ("write.entity.", "entities"),
    ("write.block.", "blocks"),
    ("write.layer.", "tables"),
    ("write.linetype.", "tables"),
    ("write.dimstyle.", "tables"),
    ("write.textstyle.", "tables"),
)

# PromotionResult.status vocabulary.
PROMOTED = "PROMOTED"
ALREADY_PROMOTED = "ALREADY_PROMOTED"
REJECTED = "REJECTED"
CONFLICT = "CONFLICT"


class PromotionError(RuntimeError):
    """Raised only for a hard, should-never-happen internal inconsistency
    (e.g. the H-R4 unknown-op guard tripping after a write) -- never for an
    ordinary gate refusal, which is a REJECTED result, not an exception."""


@dataclass
class _PendingWrite:
    """Precomputed Axis-A/Axis-B file contents for one PROMOTED result,
    carried from compute_promotion() to apply_promotion() without ever being
    written unless apply_promotion is actually called."""
    family_path: str
    new_family_text: str
    operations_v2_path: str
    new_operations_v2_doc: Dict[str, Any]


@dataclass
class PromotionResult:
    patch_op: str
    native_op: str
    status: str
    reason: str
    f1_class: Optional[str] = None
    family: Optional[str] = None
    diff: Dict[str, Any] = field(default_factory=dict)
    backups: Dict[str, bytes] = field(default_factory=dict)
    _pending: Optional[_PendingWrite] = field(default=None, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patch_op": self.patch_op, "native_op": self.native_op,
            "status": self.status, "reason": self.reason,
            "f1_class": self.f1_class, "family": self.family, "diff": self.diff,
        }


# --------------------------------------------------------------------------- #
# Manifest + F1 matrix loaders
# --------------------------------------------------------------------------- #
def load_manifest(path: str = MANIFEST_PATH) -> List[Dict[str, Any]]:
    """Load + validate config/promotion_manifest.json's rows[]. Every row MUST
    carry all of REQUIRED_ROW_FIELDS (ir_kind/family/etc may be null) -- a
    malformed row fails loud here, never silently at promotion time."""
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        doc = json.load(fh)
    rows = doc["rows"] if isinstance(doc, dict) else doc
    for row in rows:
        missing = [k for k in REQUIRED_ROW_FIELDS if k not in row]
        if missing:
            raise ValueError("promotion_manifest row missing required field(s) %s: %r"
                              % (missing, row))
        if row["persistence_class"] not in VALID_PERSISTENCE_CLASSES:
            raise ValueError("row %s: persistence_class %r not in %s"
                              % (row["patch_op"], row["persistence_class"], VALID_PERSISTENCE_CLASSES))
    return rows


def load_f1_matrix(path: str = REACHABLE_MATRIX_PATH) -> Dict[str, Dict[str, Any]]:
    """op_id -> latest F1 probe row (see probe_reachability.build_row). A
    missing matrix file or a native_op with no row at all is honestly 'never
    probed' (returns {} / no key) -- never fabricated as RUNNABLE."""
    rows: Dict[str, Dict[str, Any]] = {}
    if not os.path.isfile(path):
        return rows
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            oid = row.get("op_id")
            if oid:
                rows[oid] = row  # last row wins (freshest re-probe)
    return rows


def f1_gate(native_op: str, *, matrix: Optional[Dict[str, Dict[str, Any]]] = None,
            matrix_path: str = REACHABLE_MATRIX_PATH) -> Tuple[bool, str, Optional[str]]:
    """The Axis-A gate: (allowed, reason, f1_class). ``allowed`` is True iff
    F1's OWN classification of native_op is exactly RUNNABLE -- never
    RUNNABLE_BUT_DEGENERATE (RT-FOLD R1-1/R1-6: input-unvalidated fake
    success), never REACHABLE/CRASH/ATTENDED_ONLY/BLOCKED_BY_POLICY/
    OPERATION_NOT_IMPLEMENTED, never an unprobed (missing) row."""
    if matrix is None:
        matrix = load_f1_matrix(matrix_path)
    row = matrix.get(native_op)
    if row is None:
        return False, ("F1 has not probed %r (no measure/reachable_matrix.jsonl row) -- "
                        "promotion refused until a live F1 sweep classifies it" % native_op), None
    cls = row.get("class")
    if cls != f1.RUNNABLE:
        return False, ("F1 classifies %r as %r, not RUNNABLE (PLAN.md PART 2 sec 2.0 Axis-A gate; "
                        "RUNNABLE_BUT_DEGENERATE is an input-unvalidated fake success, never promotable)"
                        % (native_op, cls)), cls
    return True, "", cls


def infer_family(native_op: str) -> str:
    """native_op -> owning tools/patch_ops/<family>.py module, by prefix.
    Unmatched (e.g. write.layout.*, write.xdata.*, write.xrecord.*) falls to
    "db" -- patch_ops.db.py's own docstring is the designated catch-all."""
    for prefix, fam in _FAMILY_PREFIXES:
        if native_op.startswith(prefix):
            return fam
    return "db"


def _family_for_row(row: Dict[str, Any], family_files: Dict[str, str]) -> str:
    fam = row.get("family") or infer_family(row["native_op"])
    if fam not in family_files:
        raise ValueError("row %s: unknown family %r (valid: %s)"
                          % (row["patch_op"], fam, sorted(family_files)))
    return fam


# --------------------------------------------------------------------------- #
# Axis B -- family module text surgery (WRITE_OP_MAP entry + build_job_args
# arg-branch), generated together or not at all (RT-FOLD H-R4).
# --------------------------------------------------------------------------- #
_MAP_RE = re.compile(r"(WRITE_OP_MAP: Dict\[str, str\] = )\{(.*?)\}", re.DOTALL)
_MAP_ENTRY_RE = re.compile(r'"([^"]+)"\s*:\s*"([^"]+)"')
_BUILD_JOB_ARGS_DEF_RE = re.compile(
    r"^def build_job_args\(native_op: str, args: Dict\[str, Any\]\) -> Optional\[Dict\[str, Any\]\]:$",
    re.MULTILINE)
_TOP_LEVEL_DEF_RE = re.compile(r"^def ", re.MULTILINE)
_RETURN_NONE_RE = re.compile(r"^    return None\s*$", re.MULTILINE)
_IF_NATIVE_OP_RE = re.compile(r'if native_op == "([^"]+)":')


def _existing_map_entries(text: str) -> Dict[str, str]:
    m = _MAP_RE.search(text)
    if not m:
        raise PromotionError("WRITE_OP_MAP literal not found in family module text")
    return dict(_MAP_ENTRY_RE.findall(m.group(2)))


def _map_entry_lookup(text: str, patch_op: str) -> Optional[str]:
    return _existing_map_entries(text).get(patch_op)


def _insert_map_entry(text: str, patch_op: str, native_op: str) -> str:
    """Add {patch_op: native_op} to WRITE_OP_MAP, re-emitting the dict in
    canonical multi-line form (stable regardless of whether the dict started
    empty single-line ``{}`` or already multi-line)."""
    m = _MAP_RE.search(text)
    if not m:
        raise PromotionError("WRITE_OP_MAP literal not found in family module text")
    entries = _existing_map_entries(text)
    entries[patch_op] = native_op
    body = "".join('    "%s": "%s",\n' % (k, v) for k, v in entries.items())
    new_literal = "%s{\n%s}" % (m.group(1), body)
    return text[:m.start()] + new_literal + text[m.end():]


def _build_job_args_span(text: str) -> Tuple[int, int]:
    m = _BUILD_JOB_ARGS_DEF_RE.search(text)
    if not m:
        raise PromotionError("def build_job_args(...) not found in family module text")
    tail = _TOP_LEVEL_DEF_RE.search(text, m.end())
    end = tail.start() if tail else len(text)
    return m.start(), end


def _has_arg_branch(text: str, native_op: str) -> bool:
    start, end = _build_job_args_span(text)
    return native_op in set(_IF_NATIVE_OP_RE.findall(text[start:end]))


def _arg_keys_tuple_literal(arg_keys: List[str]) -> str:
    items = ", ".join(repr(k) for k in arg_keys)
    if len(arg_keys) == 1:
        items += ","
    return "(%s)" % items


def _insert_arg_branch(text: str, native_op: str, arg_keys: List[str]) -> str:
    """Insert a new ``if native_op == "<native_op>":`` branch into
    build_job_args, immediately before the function's final fallback
    ``return None`` -- so an unrecognized native_op still falls through to
    None (never silently defaults to some OTHER entity's args, RT-FOLD
    H-R4's "unknown-op guard")."""
    start, end = _build_job_args_span(text)
    func_slice = text[start:end]
    matches = list(_RETURN_NONE_RE.finditer(func_slice))
    if not matches:
        raise PromotionError("build_job_args has no fallback 'return None' to insert before")
    last = matches[-1]
    branch = (
        '    if native_op == "%s":\n'
        '        out: Dict[str, Any] = {}\n'
        '        for k in %s:\n'
        '            if k in args:\n'
        '                out[k] = args[k]\n'
        '        return out\n'
    ) % (native_op, _arg_keys_tuple_literal(arg_keys))
    new_func_slice = func_slice[:last.start()] + branch + func_slice[last.start():]
    return text[:start] + new_func_slice + text[end:]


# --------------------------------------------------------------------------- #
# Axis A -- config/operations.v2.json policy.status_policy flip (throwaway).
# --------------------------------------------------------------------------- #
def _merge_list(existing: Optional[List[str]], addition: str) -> List[str]:
    out = list(existing or [])
    if addition not in out:
        out.append(addition)
    return out


def _flip_axis_a(op_record: Dict[str, Any], native_op: str) -> Dict[str, Any]:
    """Return a NEW op record (deep copy) with policy.status_policy flipped
    to "implemented" and an evidence_ref merged in. If status_policy is
    already "implemented" this is a no-op copy (Axis A already satisfied --
    true for some Tier-1 candidates whose registry flip predates F2; the
    promotion still requires the F1 RUNNABLE gate independently)."""
    new_op = copy.deepcopy(op_record)
    policy = new_op.setdefault("policy", {})
    policy["status_policy"] = "implemented"
    policy.pop("runtime_behavior", None)  # stale once promoted
    new_op["evidence_refs"] = _merge_list(
        new_op.get("evidence_refs"), "measure/reachable_matrix.jsonl#%s" % native_op)
    return new_op


def _load_operations_v2(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _dump_operations_v2(doc: Dict[str, Any], path: str) -> None:
    # Byte-format matches reconcile_native_registry._dump_reg exactly (BOM,
    # indent=2, NO trailing newline) so any real diff is status/evidence only.
    with open(path, "w", encoding=_JSON_ENCODING, newline="\n") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)


def _find_op(doc: Dict[str, Any], op_id: str) -> Dict[str, Any]:
    for op in doc["operations"]:
        if op.get("id") == op_id:
            return op
    raise PromotionError("native_op %r not found in operations.v2.json" % op_id)


# --------------------------------------------------------------------------- #
# The two public entry points
# --------------------------------------------------------------------------- #
def compute_promotion(row: Dict[str, Any], *,
                       matrix: Optional[Dict[str, Dict[str, Any]]] = None,
                       operations_v2_path: str = OPERATIONS_V2_PATH,
                       family_files: Optional[Dict[str, str]] = None) -> PromotionResult:
    """PURE, read-only: run the Axis-A gate and compute the exact 3-axis diff
    a promotion WOULD write, touching no file. Safe to call any number of
    times; never mutates ``row``. ``operations_v2_path``/``family_files``
    default to the real repo paths but tests point them at a tmp_path
    fixture tree so no tracked file is ever touched by a test."""
    patch_op = row["patch_op"]
    native_op = row["native_op"]
    arg_keys = list(row["arg_keys"])
    fam_files = family_files if family_files is not None else FAMILY_FILES

    allowed, reason, f1_class = f1_gate(native_op, matrix=matrix)
    if not allowed:
        return PromotionResult(patch_op, native_op, REJECTED, reason, f1_class)

    family = _family_for_row(row, fam_files)
    family_path = fam_files[family]
    fam_text = open(family_path, "r", encoding="utf-8").read()
    ops_doc = _load_operations_v2(operations_v2_path)
    op_record = _find_op(ops_doc, native_op)

    existing_native = _map_entry_lookup(fam_text, patch_op)
    if existing_native is not None and existing_native != native_op:
        return PromotionResult(
            patch_op, native_op, CONFLICT,
            "patch_op %r already mapped to %r in %s, not %r"
            % (patch_op, existing_native, family_path, native_op),
            f1_class, family)

    has_branch = _has_arg_branch(fam_text, native_op)
    axis_a_satisfied = op_record.get("policy", {}).get("status_policy") == "implemented"
    if existing_native == native_op and has_branch and axis_a_satisfied:
        no_change = {"changed": False}
        return PromotionResult(
            patch_op, native_op, ALREADY_PROMOTED,
            "map-entry + arg-branch + Axis-A already in place; no-op", f1_class, family,
            diff={"axis_a": dict(no_change, file=operations_v2_path),
                  "axis_b_map": dict(no_change, file=family_path),
                  "axis_b_args": dict(no_change, file=family_path)})

    new_fam_text = fam_text
    map_changed = existing_native != native_op
    if map_changed:
        new_fam_text = _insert_map_entry(new_fam_text, patch_op, native_op)
    args_changed = not has_branch
    if args_changed:
        new_fam_text = _insert_arg_branch(new_fam_text, native_op, arg_keys)

    new_op_record = _flip_axis_a(op_record, native_op)
    axis_a_changed = new_op_record != op_record
    new_ops_doc = copy.deepcopy(ops_doc)
    for i, op in enumerate(new_ops_doc["operations"]):
        if op.get("id") == native_op:
            new_ops_doc["operations"][i] = new_op_record
            break

    diff = {
        "axis_a": {"file": operations_v2_path, "op_id": native_op, "changed": axis_a_changed,
                   "before": {"status_policy": op_record.get("policy", {}).get("status_policy")},
                   "after": {"status_policy": new_op_record.get("policy", {}).get("status_policy")}},
        "axis_b_map": {"file": family_path, "changed": map_changed, "entry": {patch_op: native_op}},
        "axis_b_args": {"file": family_path, "changed": args_changed, "arg_keys": arg_keys},
        "axis_c": {"changed": False,
                   "note": ("no C++ edit -- F1's live RUNNABLE probe of %r already exercised the same "
                            "AriadneNativeJob.cpp dispatch chain this promotion relies on "
                            "(PLAN.md PART 2 sec 2.0 Axis-C note)") % native_op},
    }
    pending = _PendingWrite(family_path=family_path, new_family_text=new_fam_text,
                            operations_v2_path=operations_v2_path, new_operations_v2_doc=new_ops_doc)
    return PromotionResult(patch_op, native_op, PROMOTED, "", f1_class, family, diff=diff,
                            _pending=pending)


def apply_promotion(row: Dict[str, Any], *,
                     matrix: Optional[Dict[str, Dict[str, Any]]] = None,
                     operations_v2_path: str = OPERATIONS_V2_PATH,
                     family_files: Optional[Dict[str, str]] = None,
                     dry_run: bool = False) -> PromotionResult:
    """compute_promotion(); if (and only if) PROMOTED, write Axis A + Axis B
    TOGETHER (reverting either write on any failure -- an all-or-nothing
    promotion never leaves a map entry without its arg branch, RT-FOLD
    H-R4), then re-import the family module fresh and assert the new
    native_op really resolves through build_job_args (the H-R4 "unknown-op
    guard": a map entry with no matching arg-branch must be structurally
    impossible, never just improbable)."""
    result = compute_promotion(row, matrix=matrix, operations_v2_path=operations_v2_path,
                                family_files=family_files)
    pending = result._pending
    if result.status != PROMOTED or dry_run or pending is None:
        return result

    # Byte-exact backups (never a decode/re-encode round trip -- utf-8-sig's
    # ENCODE side always prepends a BOM even to BOM-less text, so a text-mode
    # backup/restore would silently inject a BOM revert_promotion never had).
    with open(pending.family_path, "rb") as fh:
        original_fam_bytes = fh.read()
    with open(pending.operations_v2_path, "rb") as fh:
        original_ops_bytes = fh.read()
    result.backups = {pending.family_path: original_fam_bytes,
                       pending.operations_v2_path: original_ops_bytes}

    try:
        with open(pending.family_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(pending.new_family_text)
        _dump_operations_v2(pending.new_operations_v2_doc, pending.operations_v2_path)
        _verify_axis_b(pending.family_path, result.native_op, row["arg_keys"])
    except Exception:
        revert_promotion(result)
        raise

    return result


def _verify_axis_b(family_path: str, native_op: str, arg_keys: List[str]) -> None:
    """H-R4 unknown-op guard: reload the just-written family module fresh
    (never trust the in-memory pre-edit module) and assert build_job_args
    actually recognizes native_op with a non-None, arg_keys-shaped result --
    proof the map entry and its arg branch are not just textually present but
    behaviorally coherent."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_promote_op_verify_family", family_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    got = mod.build_job_args(native_op, {k: object() for k in arg_keys})
    if got is None:
        raise PromotionError(
            "H-R4 unknown-op guard tripped: build_job_args(%r, ...) returned None "
            "immediately after promotion -- map entry without a coherent arg branch" % native_op)
    if set(got) != set(arg_keys):
        raise PromotionError(
            "H-R4 unknown-op guard tripped: build_job_args(%r, ...) returned keys %s, expected %s"
            % (native_op, sorted(got), sorted(arg_keys)))


def revert_promotion(result: PromotionResult) -> None:
    """Undo apply_promotion via the exact backup bytes it captured -- the
    promotion's reversibility guarantee (PLAN.md F2 accept: "...is
    reversible"). Byte-exact (no decode/re-encode) so a BOM-less file is
    never left with a spuriously-added BOM, and vice versa."""
    for path, original_bytes in result.backups.items():
        with open(path, "wb") as fh:
            fh.write(original_bytes)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--manifest", default=MANIFEST_PATH)
    p.add_argument("--patch-op", help="promote exactly this manifest row's patch_op")
    p.add_argument("--apply", action="store_true", help="write the promotion (default: dry-run check)")
    p.add_argument("--list", action="store_true", help="list every manifest row's gate status, no writes")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    rows = load_manifest(args.manifest)
    matrix = load_f1_matrix()

    if args.list:
        for row in rows:
            allowed, reason, cls = f1_gate(row["native_op"], matrix=matrix)
            print("%-20s -> %-28s f1_class=%-24s %s" % (
                row["patch_op"], row["native_op"], cls, "GATE-OPEN" if allowed else "GATE-CLOSED: " + reason))
        return 0

    if not args.patch_op:
        print("error: --patch-op is required (or use --list)", file=sys.stderr)
        return 2

    matching = [r for r in rows if r["patch_op"] == args.patch_op]
    if not matching:
        print("error: no manifest row for patch_op %r" % args.patch_op, file=sys.stderr)
        return 2
    row = matching[0]

    fn = apply_promotion if args.apply else compute_promotion
    result = fn(row, matrix=matrix)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0 if result.status in (PROMOTED, ALREADY_PROMOTED) else 1


if __name__ == "__main__":
    raise SystemExit(main())
