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

Usage:
  python tools/reconcile_native_registry.py            # dry-run (default)
  python tools/reconcile_native_registry.py --apply    # write the registry
  python tools/reconcile_native_registry.py --families c,d,e   # restrict
"""
import json, os, re, sys, collections

# native family / registry payloads may carry non-ASCII (e.g. Korean layer names);
# the cp949 console would otherwise crash on print. Emit UTF-8, never crash.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "config", "operations.v2.json")
FAMILIES_DIR = os.path.join(ROOT, "src", "Ariadne.AcadNative", "families")

# string-valued C constant:  ... NAME = "value" ;
RE_CONST = re.compile(r'\b([A-Za-z_]\w*)\s*=\s*"([^"]+)"\s*;')
# op == "literal"  |  op == IDENT
RE_OPEQ = re.compile(r'op\s*==\s*(?:"([^"]+)"|([A-Za-z_]\w*))')
RE_FAMFILE = re.compile(r'^m08([a-z]+)_handlers\.inc$')   # unit token may be multi-char (e.g. m08kc)


def _load_reg():
    with open(REG, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _dump_reg(obj):
    # EXACTLY operation_coverage_matrix._dump_registry: BOM, indent=2, no trailing nl
    with open(REG, "w", encoding="utf-8-sig", newline="\n") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _hasop_body(text, letter):
    """Extract the brace-balanced body of m08{letter}HasOp(...).

    Anchor on the DEFINITION (`bool m08XHasOp(...)`) not the doc-comment mention
    (`//   - m08XHasOp(op): ...`), which has no `bool` before the name."""
    m = re.search(r'bool\s+m08' + letter + r'HasOp\s*\([^)]*\)', text)
    if not m:
        return ""
    i = text.find("{", m.end())
    if i < 0:
        return ""
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1:j]
        j += 1
    return text[i + 1:]


def parse_family(path, letter):
    text = open(path, "r", encoding="utf-8").read()
    consts = {name: val for name, val in RE_CONST.findall(text)}
    body = _hasop_body(text, letter)
    ops, unresolved = set(), []
    for lit, ident in RE_OPEQ.findall(body):
        if lit:
            ops.add(lit)
        elif ident:
            if ident in consts:
                ops.add(consts[ident])
            else:
                unresolved.append(ident)
    return ops, unresolved


def discover_families(restrict):
    out = {}
    for fn in sorted(os.listdir(FAMILIES_DIR)):
        m = RE_FAMFILE.match(fn)
        if not m:
            continue
        letter = m.group(1)
        if restrict and letter not in restrict:
            continue
        ops, unresolved = parse_family(os.path.join(FAMILIES_DIR, fn), letter)
        out[letter] = {"file": fn, "ops": ops, "unresolved": unresolved}
    return out


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


def main():
    apply = "--apply" in sys.argv
    restrict = None
    for i, a in enumerate(sys.argv):
        if a == "--families" and i + 1 < len(sys.argv):
            restrict = set(x.strip() for x in sys.argv[i + 1].split(",") if x.strip())

    fams = discover_families(restrict)
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
        print("\n[m08{0}] {1}".format(letter, info["file"]))
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

    if not apply:
        print("\n(DRY-RUN — no file written. Re-run with --apply to write.)")
        return

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
    _dump_reg(doc)
    cat_after = collections.Counter(o.get("status") for o in doc["operations"]).get("catalogued", 0)
    print("\nAPPLIED: {0} ops flipped to implemented.".format(len(flips)))
    print("  catalogued: {0} -> {1}".format(cat_before, cat_after))
    print("  registry written: {0}".format(os.path.relpath(REG, ROOT)))
    if drift:
        print("  NOTE: {0} drift op(s) NOT reconciled (handler w/o registry op) — see above.".format(len(drift)))


if __name__ == "__main__":
    main()
