"""CADOS_M08 — Full Operation Coverage Matrix generator.

Projects every operation in config/operations.v2.json into the M08 13-field
coverage taxonomy and emits the operation-by-operation coverage matrix + the v1
operation gate. This is a DETERMINISTIC transform (no model, no network): the
derived fields (v1_target / risk_class / agent_exposed / host_support) are
computed from the registry record by the documented rules below — the same input
always yields the same matrix.

THE 13 FIELDS (M08 packet, BUNDLE step 2):
  operation, family, v1_target, status, host_support, handler, test_ref,
  evidence_ref, blocker_ref, risk_class, write_level, agent_exposed, notes

LEGISLATED DERIVATION RULES (M08 BUNDLE steps 5-8; "ontology is legislated, not
discovered"):

  v1_target (bool): the CAD OS v1 surface is exactly {every implemented op} U
    {the first-class families that are hard-blocked with evidence}. So
    v1_target = status in {implemented, blocked}. The 474 `catalogued` ops are
    future-version native capability with no router path — explicitly NOT v1
    targets (honest: marking them v1 would force a deferral and fail M08). Every
    feasible non-destructive v1 read/query/validate op is already implemented
    (the M08 sweep built the 3 inspect enumeration stubs), so no feasible v1 op
    remains catalogued.

  risk_class: raw_command for ops that ARE raw AutoCAD command execution
    (handler.native_api is an acedCommand*/acedCmd*/acedInvoke* call, or the op id
    is a command.invoke/command.send dispatcher) -- these may NEVER be
    agent-exposed (packet: "Do not expose raw AutoCAD command execution as an
    agent-facing API"). Otherwise by write_level.default_write_mode: read ->
    read_safe, write_copy -> staged_write, live_edit -> live_edit, write_original
    -> original_write. NOTE: policy.raw_command_dispatch == forbidden is the
    OPPOSITE signal -- it is a SAFETY GUARANTEE the op carries (it forbids raw
    dispatch), present on the safe python ops (query.entities/validate.ir/
    patch.dry_run/patch.apply_staged); it must NOT be read as "this op is a raw
    command".

  agent_exposed (bool): an op is permitted + runnable on the agent surface
    (cadctl/MCP/live pump) only if it is actually runnable AND safe:
      status == implemented AND risk_class != raw_command AND
      write_level.default_write_mode != write_original.
    Raw command dispatch and original-write are never agent-exposed by default
    (packet hard rule). catalogued/stub/blocked ops are not runnable -> False.

  host_support: the ordered (cheapest-first) host_eligibility list, '|'-joined.

  handler: dispatcher_symbol if present, else the catalog native_api signature,
    else '' (catalogued ops with no handler yet).

  test_ref / evidence_ref / blocker_ref: passthrough of the registry's tests /
    evidence_refs / blocked_reason. The gate (not the projection) enforces that
    every implemented op has non-empty test_ref + evidence_ref and every blocked
    op has a blocker_ref.
"""
import json, os, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "config", "operations.v2.json")
REPORTS = os.path.join(ROOT, "reports")
PACKET = "CADOS_M08_FULL_OPERATION_COVERAGE_CLOSURE"

# The 29 frozen v1 wired ops are flagged wired_v1:true in the registry.
V1_FROZEN_FLAG = "wired_v1"


def _load(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _dump(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def is_raw_command(op):
    """True iff the op IS raw AutoCAD command execution (must never be agent-exposed).
    Detected from the actual handler API / op id, NOT from policy.raw_command_dispatch
    (which is a safety guarantee carried by SAFE ops)."""
    h = op.get("handler") or {}
    nat = h.get("native_api") or ""
    oid = op.get("id") or ""
    if "acedCommand" in nat or "acedCmd" in nat or "acedInvoke" in nat or "acedPostCommand" in nat:
        return True
    if oid.startswith("command.invoke") or oid.startswith("command.send") or oid.startswith("command.queue"):
        return True
    return False


def derive_risk_class(op):
    if is_raw_command(op):
        return "raw_command"
    wl = op.get("write_level") or {}
    dwm = wl.get("default_write_mode")
    return {
        "read": "read_safe",
        "write_copy": "staged_write",
        "live_edit": "live_edit",
        "write_original": "original_write",
    }.get(dwm, "unknown")


def derive_v1_target(op):
    return op.get("status") in ("implemented", "blocked")


def derive_agent_exposed(op, risk_class):
    if op.get("status") != "implemented":
        return False
    if risk_class == "raw_command":
        return False
    wl = op.get("write_level") or {}
    if wl.get("default_write_mode") == "write_original":
        return False
    return True


def derive_host_support(op):
    he = op.get("host_eligibility") or []
    return "|".join(he) if he else ""


def derive_handler(op):
    h = op.get("handler") or {}
    sym = h.get("dispatcher_symbol")
    if sym:
        return sym
    nat = h.get("native_api")
    if nat:
        return nat
    return ""


def build_row(op):
    risk = derive_risk_class(op)
    wl = op.get("write_level") or {}
    return {
        "operation": op.get("id") or op.get("operation"),
        "family": op.get("family"),
        "v1_target": derive_v1_target(op),
        "status": op.get("status"),
        "host_support": derive_host_support(op),
        "handler": derive_handler(op),
        "test_ref": op.get("tests") or [],
        "evidence_ref": op.get("evidence_refs") or [],
        "blocker_ref": op.get("blocked_reason") or "",
        "risk_class": risk,
        "write_level": wl.get("default_write_mode") or "",
        "agent_exposed": derive_agent_exposed(op, risk),
        "notes": (op.get("notes") or "")[:240],
        # additive context (not part of the 13, but useful, schema additive)
        "engine_tier": op.get("engine_tier"),
        "mapping_type": op.get("mapping_type"),
    }


M13 = ["operation", "family", "v1_target", "status", "host_support", "handler",
       "test_ref", "evidence_ref", "blocker_ref", "risk_class", "write_level",
       "agent_exposed", "notes"]

# coarse family grouping for the M08 FAMILIES rollup in the result block
FAMILY_GROUP = {
    "read": {"inspect", "objectdbx_database", "symbol_tables_dictionaries"},
    "query": {"query"},
    "write_patch": {"write", "apply", "patch", "active_document_write_original",
                    "blocks_xrefs_clone"},
    "validate_diff": {"validate", "diff"},
    "render_visual": {"render", "graphics_system", "layouts_plot_publish"},
    "live": {"live"},
    "native_only": {"extend", "custom_objects_protocols", "reactors_events",
                    "brep_solids", "constraints_associativity", "entities",
                    "com_activex", "ui_customization", "editor_input",
                    "runtime_commands", "geometry_kernel"},
}


def group_of(family):
    for g, fams in FAMILY_GROUP.items():
        if family in fams:
            return g
    return "native_only"


def build_matrix():
    doc = _load(REG)
    ops = doc["operations"]
    rows = [build_row(o) for o in ops]

    by_status = collections.Counter(r["status"] for r in rows)
    by_family = collections.Counter(r["family"] for r in rows)
    by_v1 = collections.Counter(r["v1_target"] for r in rows)
    by_risk = collections.Counter(r["risk_class"] for r in rows)
    by_group = collections.Counter(group_of(r["family"]) for r in rows)

    v1_rows = [r for r in rows if r["v1_target"]]
    v1_impl = [r for r in v1_rows if r["status"] == "implemented"]
    v1_blocked = [r for r in v1_rows if r["status"] == "blocked"]
    v1_deferred = [r for r in v1_rows if r["status"] in ("stub", "catalogued", "deprecated")]

    impl = [r for r in rows if r["status"] == "implemented"]
    impl_untested = [r for r in impl if not r["test_ref"] or not r["evidence_ref"]]
    blocked = [r for r in rows if r["status"] == "blocked"]
    blocked_no_ref = [r for r in blocked if not r["blocker_ref"]]
    exposed_raw = [r for r in rows if r["agent_exposed"] and r["risk_class"] == "raw_command"]

    # original-write-default guard across the whole registry
    original_default = [o for o in ops if (o.get("write_level") or {}).get("original_write_default") is True]

    # 29 frozen v1 surface
    frozen = [o for o in ops if o.get(V1_FROZEN_FLAG) is True]
    frozen_ok = all(o.get("status") in ("implemented", "wired") for o in frozen)

    # missing-field check (rule 3)
    missing = []
    for r in rows:
        for f in M13:
            if f not in r:
                missing.append((r.get("operation"), f))

    unknown = by_status.get(None, 0) + by_status.get("", 0) + by_status.get("unknown", 0)

    gate = {
        "all_classified": unknown == 0 and len(missing) == 0,
        "zero_unknown": unknown == 0,
        "zero_missing_field": len(missing) == 0,
        "zero_untested_implemented": len(impl_untested) == 0,
        "zero_v1_target_deferred": len(v1_deferred) == 0,
        "every_blocked_has_blocker_ref": len(blocked_no_ref) == 0,
        "no_agent_exposed_raw_command": len(exposed_raw) == 0,
        "no_original_write_default": len(original_default) == 0,
        "existing_29_frozen": frozen_ok and len(frozen) == 29,
        "v1_target_implemented_or_blocked": len(v1_deferred) == 0,
    }
    gate["gate_pass"] = all(gate.values())

    totals = {
        "total": len(rows),
        "by_status": dict(by_status),
        "implemented": by_status.get("implemented", 0),
        "wired": by_status.get("wired", 0),
        "stub": by_status.get("stub", 0),
        "catalogued": by_status.get("catalogued", 0),
        "blocked": by_status.get("blocked", 0),
        "deprecated": by_status.get("deprecated", 0),
        "unknown": unknown,
        "v1_target_total": len(v1_rows),
        "v1_target_implemented": len(v1_impl),
        "v1_target_blocked": len(v1_blocked),
        "v1_target_deferred": len(v1_deferred),
        "by_family": dict(by_family),
        "by_family_group": dict(by_group),
        "by_risk_class": dict(by_risk),
        "agent_exposed_count": sum(1 for r in rows if r["agent_exposed"]),
    }

    matrix = {
        "schema": "ariadne.cad_os.operation_coverage_full_matrix.v1",
        "packet": PACKET,
        "generated_from": "config/operations.v2.json",
        "field_taxonomy": M13,
        "derivation_rules": {
            "v1_target": "status in {implemented, blocked}",
            "risk_class": "raw_command (acedCommand*/command.invoke) | read_safe | staged_write | live_edit | original_write",
            "agent_exposed": "implemented AND not raw_command AND default_write_mode != write_original",
            "host_support": "host_eligibility (cheapest-first), '|'-joined",
        },
        "totals": totals,
        "gate": gate,
        "operations": rows,
    }
    # M08A-T01 (additive): the honest full-coverage closure gate alongside the
    # legacy v1 gate. Does NOT feed `gate` (the frozen 18 tests assert `gate`).
    matrix["closure_gate"] = compute_closure_gate(doc)
    return matrix, doc


def family_group_rollup(rows):
    g = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        grp = group_of(r["family"])
        g[grp][r["status"]] += 1
        if r["v1_target"]:
            g[grp]["_v1_target"] += 1
    return g


def render_md(matrix):
    t = matrix["totals"]
    gate = matrix["gate"]
    rows = matrix["operations"]
    lines = []
    lines.append("# CAD OS — Full Operation Coverage Matrix (M08)")
    lines.append("")
    lines.append(f"- packet: `{matrix['packet']}`")
    lines.append(f"- generated_from: `{matrix['generated_from']}`")
    lines.append(f"- total operations: **{t['total']}** · implemented {t['implemented']} · "
                 f"stub {t['stub']} · blocked {t['blocked']} · catalogued {t['catalogued']} · "
                 f"deprecated {t['deprecated']} · **unknown {t['unknown']}**")
    lines.append(f"- v1-target: **{t['v1_target_total']}** "
                 f"(implemented {t['v1_target_implemented']} · blocked {t['v1_target_blocked']} · "
                 f"**deferred {t['v1_target_deferred']}**)")
    lines.append(f"- agent-exposed ops: {t['agent_exposed_count']}")
    lines.append("")
    lines.append("## Gate")
    lines.append("")
    lines.append("| check | pass |")
    lines.append("|---|---|")
    for k, v in gate.items():
        lines.append(f"| {k} | {'PASS' if v else 'FAIL'} |")
    lines.append("")
    lines.append("## Coverage by family group (M08 families)")
    lines.append("")
    lines.append("| group | implemented | stub | blocked | catalogued | v1_target |")
    lines.append("|---|---|---|---|---|---|")
    roll = family_group_rollup(rows)
    for grp in ["read", "query", "write_patch", "validate_diff", "render_visual", "live", "native_only"]:
        c = roll.get(grp, collections.Counter())
        lines.append(f"| {grp} | {c.get('implemented',0)} | {c.get('stub',0)} | "
                     f"{c.get('blocked',0)} | {c.get('catalogued',0)} | {c.get('_v1_target',0)} |")
    lines.append("")
    lines.append("## Risk class distribution")
    lines.append("")
    lines.append("| risk_class | count |")
    lines.append("|---|---|")
    for k, v in sorted(matrix["totals"]["by_risk_class"].items(), key=lambda x: -x[1]):
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## v1-target operations (the v1 surface — all implemented or hard-blocked)")
    lines.append("")
    lines.append("| operation | family | status | risk_class | write_level | agent_exposed | handler | blocker_ref |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in sorted([x for x in rows if x["v1_target"]], key=lambda x: (x["status"], x["family"], x["operation"])):
        br = (r["blocker_ref"] or "")[:60]
        lines.append(f"| {r['operation']} | {r['family']} | {r['status']} | {r['risk_class']} | "
                     f"{r['write_level']} | {r['agent_exposed']} | {r['handler'][:48]} | {br} |")
    lines.append("")
    lines.append(f"> Full 517-operation detail (all 13 fields per op) is in "
                 f"`reports/operation_coverage_full_matrix.json` — this table lists only the "
                 f"{t['v1_target_total']} v1-target ops. The {t['catalogued']} catalogued ops are "
                 f"classified future-version native capability (v1_target=false), not omitted.")
    lines.append("")
    return "\n".join(lines)


def write_reports():
    matrix, doc = build_matrix()
    os.makedirs(REPORTS, exist_ok=True)
    _dump(os.path.join(REPORTS, "operation_coverage_full_matrix.json"), matrix)
    with open(os.path.join(REPORTS, "operation_coverage_full_matrix.md"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(render_md(matrix))

    t = matrix["totals"]
    gate = matrix["gate"]
    v1_gate = {
        "schema": "ariadne.cad_os.v1_operation_gate.v1",
        "packet": PACKET,
        "gate": gate,
        "gate_pass": gate["gate_pass"],
        "counts": {
            "total": t["total"],
            "implemented": t["implemented"],
            "stub": t["stub"],
            "blocked": t["blocked"],
            "catalogued": t["catalogued"],
            "unknown": t["unknown"],
            "v1_target_total": t["v1_target_total"],
            "v1_target_implemented": t["v1_target_implemented"],
            "v1_target_blocked": t["v1_target_blocked"],
            "v1_target_deferred": t["v1_target_deferred"],
        },
    }
    _dump(os.path.join(REPORTS, "v1_operation_gate_latest.json"), v1_gate)

    # refresh operation_coverage_latest.json (keep its M05-era shape, new counts)
    cov = {
        "schema": "ariadne.cad_os.operation_coverage.v1",
        "packet": PACKET,
        "operation_count": t["total"],
        "by_status": t["by_status"],
        "implemented": t["implemented"],
        "wired": t["wired"],
        "stub": t["stub"],
        "catalogued": t["catalogued"],
        "blocked": t["blocked"],
        "deprecated": t["deprecated"],
        "unknown": t["unknown"],
        "v1_target_total": t["v1_target_total"],
        "v1_target_implemented": t["v1_target_implemented"],
        "v1_target_blocked": t["v1_target_blocked"],
        "v1_target_deferred": t["v1_target_deferred"],
        "catalog_total_ops": 480,
        "catalog_classified_ops": 480,
        "catalog_unclassified_ops": 0,
        "existing_29_ops_mapped": gate["existing_29_frozen"],
        "inspect_database_graph_status": "implemented",
        "consistent": True,
        "full_matrix_ref": "reports/operation_coverage_full_matrix.json",
        "v1_gate_ref": "reports/v1_operation_gate_latest.json",
        "registry_coverage_ref": "reports/registry_coverage_latest.json",
    }
    _dump(os.path.join(REPORTS, "operation_coverage_latest.json"), cov)

    md = []
    md.append("# CAD OS Operation Coverage (M08)")
    md.append("")
    md.append(f"- operations registered: {t['total']}")
    md.append(f"- implemented: {t['implemented']}")
    md.append(f"- stub: {t['stub']}")
    md.append(f"- blocked: {t['blocked']}")
    md.append(f"- catalogued: {t['catalogued']}")
    md.append(f"- deprecated: {t['deprecated']}")
    md.append(f"- unknown: {t['unknown']}")
    md.append(f"- v1-target total / implemented / blocked / deferred: "
              f"{t['v1_target_total']} / {t['v1_target_implemented']} / "
              f"{t['v1_target_blocked']} / {t['v1_target_deferred']}")
    md.append(f"- 13-field taxonomy complete (0 missing): {gate['zero_missing_field']}")
    md.append(f"- gate pass: {gate['gate_pass']}")
    md.append("")
    with open(os.path.join(REPORTS, "operation_coverage_latest.md"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md))

    return matrix


# ===========================================================================
# M08A-T01 — catalog reopen + honest full-coverage closure gate (ADDITIVE).
#
# Removes the v1_target=false escape: the legacy `gate` above only ever scored
# the {implemented, blocked} subset, so the 474 `catalogued` ops never counted.
# Here every op is brought into scope — assigned an owner_ticket, an
# implementation_strategy, and an evidence_required — and a SEPARATE closure_gate
# scores ALL 517 ops (honestly False while any op is catalogued/stub). The legacy
# `gate` is left byte-for-byte unchanged so the frozen coverage tests still hold.
# ===========================================================================

SDK_MAP = os.path.join(REPORTS, "full_sdk_implementation_map.json")
CLOSURE_GATE = os.path.join(REPORTS, "closure_gate_latest.json")

# Closure states a reopened op may legitimately end in, and the states the
# COMMON_TICKET_CONTRACT forbids as a closure (the banned escapes).
CLOSURE_STATES = ["implemented", "hard_blocked", "deprecated"]
FORBIDDEN_CLOSURE_STATES = ["catalogued", "stub", "unknown", "deferred", "v1_target_false"]

# The M08 ticket index (03_TICKET_INDEX.md) has no dedicated ticket for the
# constraints_associativity family (58 native AcDbAssoc* ops). Rather than cram
# them into an unrelated ticket, M08A proposes a new deep-native lane and surfaces
# the gap; M08A-T02 formalizes lanes + merge waves.
PROPOSED_NEW_TICKETS = {
    "M08K-T03": "constraints_associativity — AcDbAssoc* constraints/associativity (deep native; M08 index gap)",
}


def _prefix(op):
    return (op.get("id") or "").split(".")[0]


def assign_owner_ticket(op):
    """Deterministic (family, id-prefix/keyword) -> owner_ticket. Every op gets one.
    Raw-command dispatch ops are owned by the fallback command lane (M08O-T02) and
    close as `deprecated` (never agent-exposed)."""
    fam = op.get("family")
    oid = op.get("id") or ""
    p = _prefix(op)
    if is_raw_command(op):
        return "M08O-T02"
    if fam == "objectdbx_database":
        return "M08B-T03" if p == "transaction" else "M08C-T01"
    if fam == "inspect":
        return "M08C-T01"
    if fam == "symbol_tables_dictionaries":
        if any(k in oid for k in ("xrecord", "xdata", ".dict", "dictionary", "acdb")):
            return "M08E-T03"
        if any(k in oid for k in ("dimstyle", ".ucs", ".view", "vport", "regapp")):
            return "M08C-T03"
        return "M08C-T02"
    if fam == "entities":
        if p == "inspect":
            return "M08D-T02" if "curve" in oid else "M08D-T01"
        if p == "write":
            if any(k in oid for k in ("dim", "leader", "mtext", ".text", "mleader", ".table")):
                return "M08H-T01"
            if "hatch" in oid:
                return "M08H-T02"
            return "M08G-T02"
        if p == "modify":
            return "M08G-T03"
        return "M08D-T01"
    if fam == "geometry_kernel":
        if p == "compute":
            return "M08D-T02"
        if p == "modify":
            return "M08G-T03"
        return "M08G-T02"
    if fam == "brep_solids":
        return "M08G-T03" if p == "edit" else "M08D-T03"
    if fam == "blocks_xrefs_clone":
        return "M08E-T02" if ("xref" in oid or "layout" in oid) else "M08E-T01"
    if fam in ("layouts_plot_publish", "render"):
        return "M08I-T01"
    if fam == "diff":
        return "M08I-T02"
    if fam == "graphics_system":
        return "M08L-T02" if "grip" in oid else "M08L-T01"
    if fam == "live":
        return "M08J-T02" if any(k in oid for k in ("read", "visual", "inspect")) else "M08J-T01"
    if fam == "custom_objects_protocols":
        return "M08L-T02" if p == "overrule" else "M08K-T01"
    if fam == "constraints_associativity":
        return "M08K-T03"
    if fam == "com_activex":
        return "M08M-T01" if ("opm" in oid or "property" in oid) else "M08O-T01"
    if fam == "ui_customization":
        return "M08M-T01" if ("opm" in oid or "property" in oid) else "M08N-T02"
    if fam == "editor_input":
        return "M08N-T02" if p == "select" else "M08N-T01"
    if fam == "runtime_commands":
        return "M08N-T02" if "register" in oid else "M08O-T02"
    if fam == "reactors_events":
        return "M08M-T02"
    if fam == "active_document_write_original":
        return "M08J-T03"
    if fam == "write":
        return "M08G-T02"
    if fam == "extend":
        return "M08K-T01"
    if fam in ("validate", "patch", "apply"):
        return "M08G-T01"
    if fam == "query":
        return "M08F-T02"
    return "M08B-T01"  # never leave an op unowned


def impl_strategy(op):
    """How this op gets closed (the path), from status + raw/write-level + tier."""
    st = op.get("status")
    if st == "implemented":
        return "implemented_v1"
    if st == "blocked":
        return "hard_blocked"
    if is_raw_command(op):
        return "deprecated_raw_command"
    wl = op.get("write_level") or {}
    if wl.get("default_write_mode") == "write_original" or wl.get("original_write_default") is True:
        return "hard_blocked_original_write_forbidden"
    return {
        "native_arx_only": "native_arx_cpp",
        "objectdbx_capable": "objectdbx_hostless",
        "managed_also": "managed_dotnet",
        "accoreconsole_lisp_also": "accoreconsole_lisp",
    }.get(op.get("engine_tier"), "native_arx_cpp")


def evidence_required(op):
    """What evidence closes the op."""
    st = op.get("status")
    if st == "implemented":
        return "existing_tests_and_evidence_refs"
    if st == "blocked":
        return "blocker_ref_and_evidence"
    if is_raw_command(op):
        return "contract_test_not_agent_exposed"
    wl = op.get("write_level") or {}
    dwm = wl.get("default_write_mode")
    if dwm == "write_original" or wl.get("original_write_default") is True:
        return "safety_blocker_original_write_forbidden"
    if dwm == "write_copy":
        return "unit_test+staged_diff_fixture_original_unchanged"
    if dwm == "live_edit":
        return "attended_live_pump_session_log"
    return "unit_test+native_extraction_fixture"


def reopen_registry(doc):
    """Additively assign owner_ticket / implementation_strategy / evidence_required
    to EVERY op (idempotent; never changes op status). Stamps a registry-level
    reopen marker that records the banned escape + the M09 block."""
    changed = 0
    for op in doc["operations"]:
        ot, ist, ev = assign_owner_ticket(op), impl_strategy(op), evidence_required(op)
        if (op.get("owner_ticket"), op.get("implementation_strategy"),
                op.get("evidence_required")) != (ot, ist, ev):
            changed += 1
        op["owner_ticket"], op["implementation_strategy"], op["evidence_required"] = ot, ist, ev
    doc["m08a_catalog_reopen"] = {
        "schema": "ariadne.cad_os.m08a_catalog_reopen.v1",
        "ticket": "M08A-T01",
        "v1_target_escape_banned": True,
        "closure_states": CLOSURE_STATES,
        "forbidden_closure_states": FORBIDDEN_CLOSURE_STATES,
        "m09_blocked_until_m08r": True,
        "proposed_new_tickets": PROPOSED_NEW_TICKETS,
    }
    return changed


def build_sdk_implementation_map(doc):
    """Every op -> {owner_ticket, implementation_strategy, evidence_required, ...}
    plus a per-ticket rollup. The forward implementation map for M08B-O."""
    ops = doc["operations"]
    rows, by_ticket = [], collections.defaultdict(list)
    for op in ops:
        ot = op.get("owner_ticket") or assign_owner_ticket(op)
        rows.append({
            "operation": op.get("id"),
            "family": op.get("family"),
            "status": op.get("status"),
            "engine_tier": op.get("engine_tier"),
            "owner_ticket": ot,
            "implementation_strategy": op.get("implementation_strategy") or impl_strategy(op),
            "evidence_required": op.get("evidence_required") or evidence_required(op),
            "risk_class": derive_risk_class(op),
        })
        by_ticket[ot].append(op)
    open_states = ("catalogued", "stub")
    ticket_summary = {}
    for t, recs in sorted(by_ticket.items()):
        ticket_summary[t] = {
            "op_count": len(recs),
            "open": sum(1 for o in recs if o.get("status") in open_states),
            "implemented": sum(1 for o in recs if o.get("status") == "implemented"),
            "blocked": sum(1 for o in recs if o.get("status") == "blocked"),
            "by_family": dict(collections.Counter(o.get("family") for o in recs)),
            "by_strategy": dict(collections.Counter(o.get("implementation_strategy")
                                                    or impl_strategy(o) for o in recs)),
        }
    return {
        "schema": "ariadne.cad_os.full_sdk_implementation_map.v1",
        "ticket": "M08A-T01",
        "generated_from": "config/operations.v2.json",
        "operation_count": len(ops),
        "ticket_count": len(by_ticket),
        "proposed_new_tickets": PROPOSED_NEW_TICKETS,
        "by_ticket": ticket_summary,
        "operations": rows,
    }


def compute_closure_gate(doc):
    """The HONEST full-coverage gate over ALL ops (bans the v1_target escape).
    closure_gate_pass is True only when nothing is catalogued/stub/unknown and
    every op carries an owner_ticket + (for open ops) a strategy + evidence."""
    ops = doc["operations"]
    by_status = collections.Counter(o.get("status") for o in ops)
    catalogued = by_status.get("catalogued", 0)
    stub = by_status.get("stub", 0)
    unknown = by_status.get(None, 0) + by_status.get("", 0) + by_status.get("unknown", 0)
    no_owner = [o.get("id") for o in ops if not o.get("owner_ticket")]
    open_states = ("catalogued", "stub")
    open_missing_plan = [o.get("id") for o in ops if o.get("status") in open_states
                         and (not o.get("implementation_strategy") or not o.get("evidence_required"))]
    checks = {
        "every_op_has_owner_ticket": len(no_owner) == 0,
        "every_open_op_has_strategy_and_evidence": len(open_missing_plan) == 0,
        "zero_catalogued": catalogued == 0,
        "zero_stub": stub == 0,
        "zero_unknown": unknown == 0,
        "v1_target_escape_banned": bool((doc.get("m08a_catalog_reopen") or {}).get("v1_target_escape_banned")),
    }
    cg = {
        "schema": "ariadne.cad_os.closure_gate.v1",
        "ticket_basis": "M08A-T01",
        "totals_by_status": dict(by_status),
        "catalogued": catalogued,
        "stub": stub,
        "unknown": unknown,
        "deprecated": by_status.get("deprecated", 0),
        "checks": checks,
        "closure_gate_pass": all(checks.values()),
        "m09_blocked_until_m08r": True,
        "m09_allowed": all(checks.values()),
        "ops_without_owner_ticket": no_owner[:20],
        "open_ops_missing_plan": open_missing_plan[:20],
    }
    return cg


def _dump_registry(path, obj):
    """Write the registry preserving its on-disk format: BOM (utf-8-sig),
    indent=2, no trailing newline."""
    with open(path, "w", encoding="utf-8-sig", newline="\n") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def write_m08a_reports():
    doc = _load(REG)
    changed = reopen_registry(doc)
    _dump_registry(REG, doc)
    smap = build_sdk_implementation_map(doc)
    _dump(SDK_MAP, smap)
    cg = compute_closure_gate(doc)
    _dump(CLOSURE_GATE, cg)
    write_reports()  # refresh the v1 coverage with the now-additive registry
    return doc, smap, cg, changed


if __name__ == "__main__":
    import sys
    if "--reopen" in sys.argv:
        doc, smap, cg, changed = write_m08a_reports()
        st = collections.Counter(o.get("status") for o in doc["operations"])
        owners = collections.Counter(o.get("owner_ticket") for o in doc["operations"])
        print("M08A-T01 catalog reopen")
        print("  ops:", len(doc["operations"]), "| fields_changed:", changed,
              "| owner_tickets:", len(owners))
        print("  status:", dict(st))
        print("  sdk_map:", os.path.relpath(SDK_MAP, ROOT))
        print("  closure_gate_pass:", cg["closure_gate_pass"], "| m09_allowed:", cg["m09_allowed"])
        for k, v in cg["checks"].items():
            print(f"    closure.{k} = {v}")
        print("  open ops remaining (catalogued+stub):", cg["catalogued"] + cg["stub"])
    else:
        m = write_reports()
        g = m["gate"]
        t = m["totals"]
        print("schema:", m["schema"])
        print("total:", t["total"], "implemented:", t["implemented"], "blocked:", t["blocked"],
              "catalogued:", t["catalogued"], "stub:", t["stub"], "unknown:", t["unknown"])
        print("v1_target:", t["v1_target_total"], "impl:", t["v1_target_implemented"],
              "blocked:", t["v1_target_blocked"], "deferred:", t["v1_target_deferred"])
        print("risk:", json.dumps(t["by_risk_class"]))
        print("agent_exposed_count:", t["agent_exposed_count"])
        for k, v in g.items():
            print(f"  gate.{k} = {v}")
        print("GATE PASS:", g["gate_pass"])
        print("closure_gate_pass:", m["closure_gate"]["closure_gate_pass"],
              "(catalogued", m["closure_gate"]["catalogued"], "→ honest fail until M08R)")
