"""CADOS_M08 — Reconcile config/operations.v2.json against the NATIVE family code.

The native ObjectARX dispatcher implements operations in
src/Ariadne.AcadNative/families/m08X_handlers.inc. Each family file carries a
`m08XHasOp(op)` gate function whose op-id set IS the authoritative list of what
the .crx/.arx actually dispatches. A teammate ticket may have wired handlers in
the .inc (CHANGE_ONLY = families/*.inc) WITHOUT touching the registry, leaving
those ops marked `catalogued` even though they are implemented in code. This
deterministic tool closes that gap honestly:

  1. Parse every families/m08*_handlers.inc -> the op-id set its HasOp admits
     (literals + resolved `kM08*` string constants).
  2. Cross-check each against the registry op-id set:
       - IN registry & status catalogued/stub -> FLIP to implemented (+evidence)
       - IN registry & already implemented     -> skip (informational overlap)
       - IN registry & blocked/deprecated      -> CONFLICT (report, never flip)
       - NOT in registry                       -> DRIFT (handler w/o registry op)
  3. For each flipped op: status=implemented, attach tests + evidence_refs +
     handler.dispatcher_symbol. Runtime ARIADNE_NATIVE_JOB smoke is honestly
     recorded as deferred-attended (build + unit are the closing evidence).

NO model, NO network: same .inc + same registry -> same reconciliation. The
registry is written back byte-format-identical to operation_coverage_matrix's
_dump_registry (utf-8-sig BOM, indent=2, NO trailing newline) so the diff is
exactly the status/evidence deltas.

CADOS F8 -- FOUR-surface vocab lockstep (extends the above): a registry
promotion is not the only place an op-id can drift. Two OTHER modules declare
their own patch-op -> registry-id vocab, independent of this tool's own
registry <-> .inc reconciliation:
  3. tools/patch_engine.OP_REGISTRY_MAP   -- declared patch-op -> registry id
     (the dry_run_plan/validate_patch_schema informational surface).
  4. tools/patch_ops.NATIVE_WRITE_OP_MAP  -- patch-op -> registry id WITH a
     live native write handler (the apply_staged real-execution surface).
check_vocab_lockstep() cross-checks every id those two surfaces reference
against THIS registry (surface 1) and the native dispatcher's full live gate
(surface 2 -- the m08X families' HasOp union PLUS the pre-M08
kAriadneNativeOperationTable ariadneNativeJob() itself also gates on; see
all_coded_ops()): the id must exist, be status=="implemented", be admitted by
that live gate (no dangling target), and carry a non-empty evidence_refs (a
promotion missing evidence_ref is not evidence). main() runs this check as an
informational preview in dry-run mode and as a hard gate in --apply mode (a
promotion that would leave the two external surfaces out of lockstep is
reported and the registry is NOT written).

Usage:
  python tools/reconcile_native_registry.py            # dry-run (default)
  python tools/reconcile_native_registry.py --apply    # write the registry
  python tools/reconcile_native_registry.py --families c,d,e   # restrict
"""
import json, os, sys, collections

if __package__:
    from .verification.operation_sources import (
        NON_M08_FAMILY_SPECS,
        check_vocab_lockstep as _check_vocab_lockstep,
        parse_hasop_operations as _parse_hasop_operations,
        parse_native_sources as _parse_native_sources,
        parse_patch_vocabularies as _parse_patch_vocabularies,
        patch_family_module_names as _patch_family_module_names,
    )
else:
    from verification.operation_sources import (
        NON_M08_FAMILY_SPECS,
        check_vocab_lockstep as _check_vocab_lockstep,
        parse_hasop_operations as _parse_hasop_operations,
        parse_native_sources as _parse_native_sources,
        parse_patch_vocabularies as _parse_patch_vocabularies,
        patch_family_module_names as _patch_family_module_names,
    )

# native family / registry payloads may carry non-ASCII (e.g. Korean layer names);
# the cp949 console would otherwise crash on print. Emit UTF-8, never crash.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "config", "operations.v2.json")
FAMILIES_DIR = os.path.join(ROOT, "src", "Ariadne.AcadNative", "families")
_NATIVE_JOB_CPP = os.path.join(ROOT, "src", "Ariadne.AcadNative", "AriadneNativeJob.cpp")

# Compatibility view for existing callers/tests; the canonical specifications
# live beside the pure parser that consumes them.
_NON_M08_FAMILIES = NON_M08_FAMILY_SPECS

def _load_reg():
    with open(REG, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _dump_reg(obj):
    # EXACTLY operation_coverage_matrix._dump_registry: BOM, indent=2, no trailing nl
    with open(REG, "w", encoding="utf-8-sig", newline="\n") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def parse_family(path, hasop_fn):
    with open(path, "rb") as source_file:
        operations, unresolved = _parse_hasop_operations(
            source_file.read(), hasop_fn, os.fspath(path)
        )
    return set(operations), list(unresolved)


def _native_facts(router_home=None):
    root = os.fspath(ROOT if router_home is None else router_home)
    native_path = os.path.join(
        root, "src", "Ariadne.AcadNative", "AriadneNativeJob.cpp"
    )
    families_dir = os.path.join(root, "src", "Ariadne.AcadNative", "families")
    with open(native_path, "rb") as native_file:
        native_source = native_file.read()
    family_sources = {}
    for file_name in sorted(os.listdir(families_dir)):
        if not file_name.endswith(".inc"):
            continue
        with open(os.path.join(families_dir, file_name), "rb") as family_file:
            family_sources[file_name] = family_file.read()
    return _parse_native_sources(native_source, family_sources)


def discover_families(restrict, router_home=None):
    facts = _native_facts(router_home=router_home)
    out = {}
    for key, family in sorted(facts.families.items()):
        if restrict and key not in restrict:
            continue
        out[key] = {
            "file": family.file_name,
            "ops": set(family.operations),
            "unresolved": list(family.unresolved),
            "label": family.label,
            "hasop_fn": family.hasop_fn,
        }
    return out


def native_family_gate_functions(router_home=None):
    """Return the HasOp functions admitted by native ``familyHasOp()``.

    Missing source or an unparsable definition is an error, not an empty gate
    universe: callers use this as a verification input.
    """
    return set(_native_facts(router_home=router_home).runtime_family_gates)


def discovered_family_gate_functions(router_home=None):
    """Return the HasOp functions scanned by ``discover_families``."""
    return set(_native_facts(router_home=router_home).discovered_family_gates)


def evidence_for(letter):
    test = "tests/unit/test_m08{0}_handlers.py".format(letter)
    return {
        "tests": [test],
        "evidence_refs": [
            "src/Ariadne.AcadNative/families/m08{0}_handlers.inc:m08{0}Dispatch".format(letter),
            "reports/merge/MERGE-M08-READ.json",
            "build:native_acad exit 0 (.crx/.arx, VS2026 MSBuild x64)",
            "runtime_native_job_smoke:deferred_attended(MERGE-M08-READ)",
        ],
        "dispatcher_symbol": "m08{0}Dispatch".format(letter),
    }


def _merge_list(existing, additions):
    out = list(existing or [])
    for a in additions:
        if a not in out:
            out.append(a)
    return out


def _sync_totals(doc):
    """Re-derive the registry's self-declared status counts from the actual
    records so the declared blocks never drift (tests assert totals.by_status ==
    per-record counts, and cadctl consistency == totals.implemented == counted).
    Only status-dependent fields are touched; by_family / by_engine_tier /
    catalog_* are status-invariant and left as-is."""
    cnt = collections.Counter(o.get("status") for o in doc["operations"])
    msgs = []
    tot = doc.get("totals")
    if isinstance(tot, dict):
        new_bs = {k: cnt[k] for k in cnt}
        if tot.get("by_status") != new_bs:
            msgs.append("totals.by_status {0} -> {1}".format(tot.get("by_status"), new_bs))
        tot["by_status"] = new_bs
    cov = doc.get("coverage")
    if isinstance(cov, dict):
        unknown = sum(v for k, v in cnt.items() if k in (None, "", "unknown"))
        for key in ("implemented", "wired", "stub", "catalogued", "blocked", "deprecated"):
            if key in cov and cov[key] != cnt.get(key, 0):
                msgs.append("coverage.{0} {1} -> {2}".format(key, cov[key], cnt.get(key, 0)))
                cov[key] = cnt.get(key, 0)
        if "unknown" in cov and cov["unknown"] != unknown:
            cov["unknown"] = unknown
    return msgs


# --------------------------------------------------------------------------- #
# CADOS F8 -- FOUR-surface vocab lockstep (registry + native HasOp gates +
# patch_engine.OP_REGISTRY_MAP + patch_ops.NATIVE_WRITE_OP_MAP)
# --------------------------------------------------------------------------- #

def _load_external_vocab(router_home=None):
    """Load the two vocab surfaces this tool does not itself own:
    tools/patch_engine.OP_REGISTRY_MAP (declared patch-op -> registry op id,
    the dry_run_plan/validate_patch_schema surface) and the patch_ops family
    aggregate NATIVE_WRITE_OP_MAP (patch-op -> registry op id with a LIVE
    native write handler, the apply_staged real-execution surface).

    Returns {surface_label: {patch_op: registry_op_id}}. Sources are parsed as
    inert bytes; checkout Python is never imported or executed."""
    root = os.fspath(ROOT if router_home is None else router_home)
    patch_engine_path = os.path.join(root, "tools", "patch_engine.py")
    patch_ops_dir = os.path.join(root, "tools", "patch_ops")
    patch_ops_init_path = os.path.join(patch_ops_dir, "__init__.py")
    with open(patch_engine_path, "rb") as patch_engine_file:
        patch_engine_source = patch_engine_file.read()
    with open(patch_ops_init_path, "rb") as patch_ops_init_file:
        patch_ops_init = patch_ops_init_file.read()
    family_sources = {}
    for module_name in _patch_family_module_names(patch_ops_init):
        with open(os.path.join(patch_ops_dir, module_name + ".py"), "rb") as family_file:
            family_sources[module_name] = family_file.read()
    return _parse_patch_vocabularies(
        patch_engine_source, patch_ops_init, family_sources
    )


def native_operation_table_ops(router_home=None):
    """The op-id set ``kAriadneNativeOperationTable`` registers directly in
    AriadneNativeJob.cpp -- the pre-M08 dispatcher's OWN gate for the ops it
    implements without going through any m08X family (write.entity.line,
    write.entity.circle, write.layer.create, inspect.database.*, ...).
    ariadneNativeJob() gates on ``findAriadneNativeOp(op) OR familyHasOp(op)``
    (see AriadneNativeJob.cpp), so this table UNION the family HasOp sets IS
    the native dispatcher's full live-admission gate -- see all_coded_ops().

    Missing or unparsable source raises: an empty native gate must not be
    mistaken for a valid reconciliation input."""
    return set(_native_facts(router_home=router_home).native_table_operations)


def all_coded_ops(restrict=None, router_home=None):
    """Union of every family's live HasOp-admitted op-id set PLUS the pre-M08
    kAriadneNativeOperationTable (surface 2's full live-admission universe),
    by default over EVERY family regardless of a --families restriction (a
    restricted reconcile run must not make check_vocab_lockstep falsely report
    "no_live_hasop" for an id owned by a family this run didn't scan)."""
    facts = _native_facts(router_home=router_home)
    coded = set(facts.native_table_operations)
    for key, family in facts.families.items():
        if restrict and key not in restrict:
            continue
        coded.update(family.operations)
    return coded


def check_vocab_lockstep(doc, coded_ops, external_vocab=None):
    """Cross-check the FOUR op-id vocab surfaces stay in lockstep:

      1. config/operations.v2.json          (``doc`` -- this tool's own registry input)
      2. the native dispatcher's live gate  (``coded_ops`` -- families/*.inc HasOp
                                              union PLUS kAriadneNativeOperationTable;
                                              see all_coded_ops)
      3. tools/patch_engine.OP_REGISTRY_MAP  (declared patch-op -> registry id)
      4. tools/patch_ops.NATIVE_WRITE_OP_MAP (patch-op -> registry id w/ a LIVE
                                              native write handler)

    Every registry-id that surface 3 or 4 points at must:
      (a) exist in the registry                             -- problem="dangling_target"
      (b) be admitted by the live gate (2)                   -- problem="no_live_hasop"
      (c) carry status=="implemented"                        -- problem="not_implemented"
      (d) carry a non-empty evidence_refs list                -- problem="missing_evidence_ref"
    (a promotion missing evidence_ref is not evidence -- CADOS F8 acceptance).

    ``external_vocab`` lets a caller (a unit test) inject a synthetic
    {surface: {patch_op: id}} mapping instead of importing patch_engine/
    patch_ops live; defaults to `_load_external_vocab()`.

    Returns a list of violation dicts (empty == the four surfaces agree);
    never raises.
    """
    vocab = _load_external_vocab() if external_vocab is None else external_vocab
    return _check_vocab_lockstep(doc, set(coded_ops), vocab)


def _print_vocab_violations(violations):
    for v in violations:
        print("    [{0}] {1}.{2} -> {3}: {4}".format(
            v["problem"], v["surface"], v["patch_op"], v["target"], v["detail"]))


def main():
    apply = "--apply" in sys.argv
    restrict = None
    for i, a in enumerate(sys.argv):
        if a == "--families" and i + 1 < len(sys.argv):
            restrict = set(x.strip() for x in sys.argv[i + 1].split(",") if x.strip())

    fams = discover_families(restrict)
    # coded_ops (surface 2, for check_vocab_lockstep below) always spans EVERY
    # family, independent of --families -- see all_coded_ops's docstring.
    coded_ops = all_coded_ops()
    doc = _load_reg()
    by_id = {o.get("id"): o for o in doc["operations"]}
    reg_ids = set(by_id)

    print("=" * 72)
    print("RECONCILE native registry  (mode: {})".format("APPLY" if apply else "DRY-RUN"))
    print("  registry: {} ops".format(len(reg_ids)))
    print("=" * 72)

    flips = []           # (op_id, letter)
    overlaps = []        # already implemented, also coded
    conflicts = []       # coded + registry blocked/deprecated
    drift = []           # coded op not in registry
    code_total = 0

    for letter in sorted(fams):
        info = fams[letter]
        coded = info["ops"]
        code_total += len(coded)
        f_in, f_overlap, f_conflict, f_drift = [], [], [], []
        for oid in sorted(coded):
            if oid not in reg_ids:
                f_drift.append(oid); drift.append((oid, letter)); continue
            st = by_id[oid].get("status")
            if st in ("catalogued", "stub"):
                f_in.append(oid); flips.append((oid, letter))
            elif st == "implemented":
                f_overlap.append(oid); overlaps.append(oid)
            else:  # blocked / deprecated / other
                f_conflict.append(oid); conflicts.append((oid, st))
        print("\n[{0}] {1}".format(info["label"], info["file"]))
        print("  coded HasOp ops : {0}".format(len(coded)))
        print("  -> flip (catalogued/stub -> implemented): {0}".format(len(f_in)))
        print("  -> already implemented (skip)           : {0}".format(len(f_overlap)))
        print("  -> conflict (blocked/deprecated)        : {0}".format(len(f_conflict)))
        print("  -> DRIFT (not in registry)              : {0}".format(len(f_drift)))
        if info["unresolved"]:
            print("  !! UNRESOLVED HasOp idents: {0}".format(info["unresolved"]))
        if f_drift:
            for d in f_drift:
                print("       DRIFT: {0}".format(d))
        if f_conflict:
            for c in f_conflict:
                print("       CONFLICT: {0} (status={1})".format(c, by_id[c].get("status")))

    print("\n" + "-" * 72)
    print("TOTALS: coded={0}  flips={1}  overlaps={2}  conflicts={3}  drift={4}".format(
        code_total, len(flips), len(overlaps), len(conflicts), len(drift)))
    cat_before = collections.Counter(o.get("status") for o in doc["operations"]).get("catalogued", 0)
    print("  catalogued before: {0}  ->  projected after: {1}".format(
        cat_before, cat_before - len(flips)))

    # sample records for shape verification (one flip target, one already-impl)
    if flips:
        sid = flips[0][0]
        print("\nSAMPLE flip-target record [{0}]:".format(sid))
        print(json.dumps(by_id[sid], ensure_ascii=False, indent=2)[:900])

    # CADOS F8: FOUR-surface vocab lockstep preview (registry as of right now,
    # before any promotion below is folded in -- see module docstring).
    preview_violations = check_vocab_lockstep(doc, coded_ops)
    print("\n" + "-" * 72)
    print("VOCAB LOCKSTEP  (patch_engine.OP_REGISTRY_MAP + patch_ops.NATIVE_WRITE_OP_MAP"
          " vs. this registry + every family's live HasOp gate)")
    if preview_violations:
        print("  {0} violation(s):".format(len(preview_violations)))
        _print_vocab_violations(preview_violations)
    else:
        print("  OK -- every op-id patch_engine/patch_ops points at resolves live, "
              "is implemented, and is evidenced.")

    if not apply:
        print("\n(DRY-RUN — no file written. Re-run with --apply to write.)")
        return 1 if preview_violations else 0

    # ---- APPLY ----
    for oid, letter in flips:
        op = by_id[oid]
        ev = evidence_for(letter)
        op["status"] = "implemented"
        op["tests"] = _merge_list(op.get("tests"), ev["tests"])
        op["evidence_refs"] = _merge_list(op.get("evidence_refs"), ev["evidence_refs"])
        h = op.get("handler")
        if not isinstance(h, dict):
            h = {} if h is None else {"native_api": h}
        h["dispatcher_symbol"] = ev["dispatcher_symbol"]
        op["handler"] = h

    # Re-run matrix field assignment to keep strategy/evidence deterministic & synchronized
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import operation_coverage_matrix as ocm
    ocm.reopen_registry(doc)

    sync_msgs = _sync_totals(doc)
    for m in sync_msgs:
        print("  SYNC: {0}".format(m))

    # CADOS F8: re-check AFTER this run's promotions are folded into `doc` --
    # keep the FOUR vocab surfaces in lockstep on every promotion. A promotion
    # that leaves patch_engine.OP_REGISTRY_MAP / patch_ops.NATIVE_WRITE_OP_MAP
    # pointing at a dangling/un-evidenced id is reported and the registry is
    # NOT written (no silent write, no fake pass).
    post_violations = check_vocab_lockstep(doc, coded_ops)
    if post_violations:
        print("\n" + "-" * 72)
        print("VOCAB LOCKSTEP FAILED after this promotion -- registry NOT written.")
        _print_vocab_violations(post_violations)
        return 2

    _dump_reg(doc)
    cat_after = collections.Counter(o.get("status") for o in doc["operations"]).get("catalogued", 0)
    print("\nAPPLIED: {0} ops flipped to implemented.".format(len(flips)))
    print("  catalogued: {0} -> {1}".format(cat_before, cat_after))
    print("  registry written: {0}".format(os.path.relpath(REG, ROOT)))
    if drift:
        print("  NOTE: {0} drift op(s) NOT reconciled (handler w/o registry op) — see above.".format(len(drift)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
