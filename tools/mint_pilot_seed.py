#!/usr/bin/env python
"""mint_pilot_seed.py -- mint fixtures/pilot_cleared_seed.dwg [F4b, WAVE-0].

F4b is the "cleared-copy pilot seed": all pilot gates (M-B/M-C/M-D) must read
this ONE fixture, never an ad-hoc clear (RT-FOLD R2-A6, D:\\dev\\.build\\cados_plan\\
final\\PLAN.md:610). It is minted ONCE from a real production drawing
(``test.dws``, 375 modelspace entities / 140 block definitions -- measured
live, see PRE_CLEAR_REFERENCE below) via a PINNED clear procedure: delete every
modelspace entity, retain the symbol tables and all 140 block definitions.

Pinned procedure (PINNED_CLEAR_PROCEDURE below is the executable form of this):
  1. stage_copy               -- copy the source, original stays read-only.
  2. capture_pre_baseline     -- inspect.database.graph (rich) on the staged
                                 copy BEFORE clearing.
  3. erase_modelspace_entities-- delete every entity whose IR record has
                                 space=="model" (this is ALL entities in this
                                 source; see PRE_CLEAR_REFERENCE.entities_by_type).
  4. save_cleared_copy        -- write the cleared db to
                                 fixtures/pilot_cleared_seed.dwg.
  5. capture_post_baseline    -- inspect.database.graph (rich) on the written
                                 fixture; verify_cleared() checks retained vs
                                 cleared counts.
  6. compute_sha256           -- fixtures/pilot_cleared_seed.dwg.sha256.
  7. write_baseline_json      -- fixtures/pilot_cleared_seed.baseline.json,
                                 schema schemas/pilot_cleared_seed_baseline.v1.schema.json.

Honest capability gap (verified 2026-07-01, this session -- see report.md):
step 3 has NO implemented op anywhere in this codebase. config/operations.v2.json
has zero erase/delete-entity operations in ANY family (entities, write,
objectdbx_database, symbol_tables_dictionaries, blocks_xrefs_clone all checked);
patch_engine.NATIVE_WRITE_OP_MAP has exactly 4 entries, all create-only
(create_line, create_circle, set_layer, create_layer). ERASE_MODELSPACE_OP_ID
below is a PROPOSED name for the missing native handler -- it is NOT registered
in config/operations.v2.json (that file is out of scope for this node; RT-FOLD
R2-A9 excludes it from all worker diffs) and calling it via
cadctl.Cad.run_operation() today returns a truthful not_found refusal (never a
fake pass). Separately, step 4's op (transform.database.save_as) IS registered
as status=='implemented', but its own nested policy block says
status_policy=='catalogued_not_runnable' and its evidence_refs mark the native
job smoke test 'deferred_attended' (never proven outside attended/GUI AutoCAD)
-- so a green exit code there must not be trusted as PASS either, per that
op's own registry notes.

mint() therefore runs everything real today (stage -> pre-baseline, both
read-only against a staged copy) and stops at step 3 with a truthful
status='blocked' -- never fabricates the fixture. Re-run
render_deferred_command() once the erase op exists and is promoted.

Standard library only (matches tools/cadctl.py's own constraint). This module
never parses a DWG itself -- all CAD access goes through cadctl.Cad(), the
same surface the cadagent-mcp cad.* tools delegate to.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parent
FIXTURES_DIR = ROUTER_HOME / "fixtures"

if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

SCHEMA_ID = "ariadne.mint_pilot_seed.v1"
BASELINE_SCHEMA_ID = "ariadne.pilot_cleared_seed_baseline.v1"

# The literal F4b source, located under D:\dev\.build per the task ("locate one
# under the repo/build"): a real production drawing, NOT a repo-committed
# fixture. Override with --source for a different box/location.
DEFAULT_SOURCE_DWG = r"D:\dev\.build\test.dws"

FIXTURE_NAME = "pilot_cleared_seed.dwg"
FIXTURE_PATH = FIXTURES_DIR / FIXTURE_NAME
SHA_PATH = FIXTURES_DIR / (FIXTURE_NAME + ".sha256")
BASELINE_PATH = FIXTURES_DIR / "pilot_cleared_seed.baseline.json"

# Ground truth measured LIVE against D:\dev\.build\test.dws on 2026-07-01 (this
# session, via cadctl.Cad().inspect(include_rich=True) during research for this
# node -- see D:\dev\.build\cados_plan\measure\m4_inspect\dwg_graph_ir.json and
# D:\dev\.build\cados_plan\measure\M4_roundtrip_diff.md). NOT used to fabricate
# a baseline: mint() always re-derives counts from a fresh inspect at mint time.
# Kept here only as the pinned expectation the F4b acceptance criterion names
# ("retain symbol tables + 140 block defs") and as realistic fixture data for
# the unit tests in tests/unit/test_mint_pilot_seed.py.
PRE_CLEAR_REFERENCE = {
    "source_sha256": "1d6f35f03eff9c692ef9d59a5e2e494ce96fc549edefe5c175b796e10b79f344",
    "source_byte_size": 2337597,
    "modelspace_entity_count": 375,
    "entities_by_type": {
        "TEXT": 117, "DIMENSION": 113, "LWPOLYLINE": 73,
        "INSERT": 50, "LINE": 21, "CIRCLE": 1,
    },
    "block_definitions": 140,
    "block_references": 50,
    "symbol_tables": {
        "layers": 91, "linetypes": 18, "text_styles": 8, "dim_styles": 6,
        "viewports": 1, "app_ids": 25, "block_table_records": 410,
    },
    "xrefs": 0, "dictionaries": 1, "extension_dictionaries": 1,
    "xrecords": 2, "layouts": 3,
}

# symbol-table + database-level state: MUST be retained unchanged across the clear.
RETAINED_SYMBOL_TABLE_KEYS = (
    "layers", "linetypes", "text_styles", "dim_styles", "viewports",
    "app_ids", "block_table_records",
)
RETAINED_TOP_LEVEL_KEYS = (
    "block_definitions", "xrefs", "dictionaries", "extension_dictionaries",
    "xrecords", "layouts",
)
# modelspace graphical entities: MUST go to zero across the clear.
CLEARED_COUNT_KEYS = ("modelspace_entity_count", "block_references")

# PROPOSED op_id for the missing native handler (see module docstring). NOT
# present in config/operations.v2.json; run_operation() refuses it truthfully
# (registry status 'not_found') until a real ARX handler is built and promoted.
ERASE_MODELSPACE_OP_ID = "modify.entity.erase"

PINNED_CLEAR_PROCEDURE = [
    {
        "step": 1,
        "action": "stage_copy",
        "op_id": None,
        "method": "cadctl.Cad.inspect()/run_operation() internal staging "
                  "(staging/golden/<ts>/input.dwg)",
        "note": "Copy the source unchanged into a writable staging dir. "
                "Original stays read-only; sha256 verified unchanged after "
                "every call.",
    },
    {
        "step": 2,
        "action": "capture_pre_baseline",
        "op_id": "inspect.database.graph",
        "method": "cadctl.Cad().inspect(source, out_dir, mode='rich', "
                  "include_rich=True)",
        "note": "Native ObjectARX/ObjectDBX rich DWG Graph IR of the staged "
                "copy BEFORE clearing: modelspace entities + all symbol "
                "tables + block definitions.",
    },
    {
        "step": 3,
        "action": "erase_modelspace_entities",
        "op_id": ERASE_MODELSPACE_OP_ID,
        "method": "cadctl.Cad().run_operation(ERASE_MODELSPACE_OP_ID, "
                  "args={'space': 'model'}, write_mode='write_copy', "
                  "dwg_path=staged_source, out_dir=...)",
        "note": "NOT YET IMPLEMENTED (verified 2026-07-01): zero erase/"
                "delete-entity ops exist in config/operations.v2.json across "
                "families entities/write/objectdbx_database/"
                "symbol_tables_dictionaries/blocks_xrefs_clone; "
                "patch_engine.NATIVE_WRITE_OP_MAP has only create_line/"
                "create_circle/set_layer/create_layer. Needs a new native ARX "
                "handler: open the *MODEL_SPACE BTR (inspect.block.iterate "
                "gives the enumerator pattern), open each member for write, "
                "call AcDbEntity::erase(true); then promote the op to "
                "status='implemented' before this step is callable.",
    },
    {
        "step": 4,
        "action": "save_cleared_copy",
        "op_id": "transform.database.save_as",
        "method": "cadctl.Cad().run_operation('transform.database.save_as', "
                  "args={'file_name': str(FIXTURE_PATH)}, "
                  "write_mode='write_copy', dwg_path=staged_source, "
                  "out_dir=...)",
        "note": "CAUTION (verified 2026-07-01): top-level registry status is "
                "'implemented' (passes the run_operation allow-list) but the "
                "op's own nested policy block says "
                "status_policy=='catalogued_not_runnable' / "
                "runtime_behavior=='not_runnable_until_promoted_to_"
                "implemented_or_wired', and its evidence_refs mark "
                "runtime_native_job_smoke as 'deferred_attended' (never "
                "smoke-tested outside attended/GUI AutoCAD). Confirm a real "
                "successful run -- not just exit_code==0 -- before trusting "
                "the written .dwg.",
    },
    {
        "step": 5,
        "action": "capture_post_baseline",
        "op_id": "inspect.database.graph",
        "method": "cadctl.Cad().inspect(fixture_path, out_dir, mode='rich', "
                  "include_rich=True); verify_cleared(pre, post)",
        "note": "Re-inspect the written fixture and assert retained counts "
                "are unchanged and cleared counts are zero.",
    },
    {
        "step": 6,
        "action": "compute_sha256_and_write_sidecar",
        "op_id": None,
        "method": "hashlib.sha256 over the final fixture bytes -> "
                  "fixtures/pilot_cleared_seed.dwg.sha256",
        "note": None,
    },
    {
        "step": 7,
        "action": "write_baseline_json",
        "op_id": None,
        "method": "build_baseline_document(...) -> "
                  "fixtures/pilot_cleared_seed.baseline.json",
        "note": "Schema: schemas/pilot_cleared_seed_baseline.v1.schema.json.",
    },
]


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _sha256_file(path: "Path | str") -> str:
    """Full lowercase SHA-256 of a file's bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def already_minted(fixture_path: "Path | None" = None, sha_path: "Path | None" = None) -> bool:
    """Mint-ONCE guard: true once both the fixture and its sha sidecar exist.

    Defaults resolve FIXTURE_PATH/SHA_PATH at CALL time (not def time) so
    tests can monkeypatch the module-level paths and have mint() -- which
    calls this with no args -- see the patched location.
    """
    fixture_path = fixture_path if fixture_path is not None else FIXTURE_PATH
    sha_path = sha_path if sha_path is not None else SHA_PATH
    return Path(fixture_path).is_file() and Path(sha_path).is_file()


def extract_symbol_table_counts(ir: dict) -> dict:
    st = ir.get("symbol_tables") or {}
    return {key: len(st.get(key) or []) for key in RETAINED_SYMBOL_TABLE_KEYS}


def extract_baseline_counts(ir: dict) -> dict:
    """Pull the F4b-pinned counts out of an ariadne.dwg_graph_ir.v1 (rich) document."""
    entities = ir.get("entities") or []
    by_type: dict = {}
    for ent in entities:
        name = ent.get("dxf_name", "UNKNOWN")
        by_type[name] = by_type.get(name, 0) + 1
    return {
        "modelspace_entity_count": len(entities),
        "entities_by_type": by_type,
        "block_definitions": len(ir.get("block_definitions") or []),
        "block_references": len(ir.get("block_references") or []),
        "symbol_tables": extract_symbol_table_counts(ir),
        "xrefs": len(ir.get("xrefs") or []),
        "dictionaries": len(ir.get("dictionaries") or []),
        "extension_dictionaries": len(ir.get("extension_dictionaries") or []),
        "xrecords": len(ir.get("xrecords") or []),
        "layouts": len(ir.get("layouts") or []),
    }


def verify_cleared(pre: dict, post: dict) -> dict:
    """Assert the clear did exactly what F4b pins: cleared counts -> 0, every
    retained (symbol-table + database-level) count unchanged. Returns
    {ok, errors}; never raises -- a bad clear is a reported error, not a crash.
    """
    errors: list[str] = []

    for key in CLEARED_COUNT_KEYS:
        actual = post.get(key)
        if actual != 0:
            errors.append(f"{key} not cleared: expected 0, found {actual!r}")
    if post.get("entities_by_type"):
        errors.append(f"entities_by_type not empty after clear: {post['entities_by_type']!r}")

    for key in RETAINED_TOP_LEVEL_KEYS:
        if pre.get(key) != post.get(key):
            errors.append(f"{key} drifted across clear: pre={pre.get(key)!r} post={post.get(key)!r}")

    pre_st = pre.get("symbol_tables") or {}
    post_st = post.get("symbol_tables") or {}
    for key in RETAINED_SYMBOL_TABLE_KEYS:
        if pre_st.get(key) != post_st.get(key):
            errors.append(
                f"symbol_tables.{key} drifted across clear: "
                f"pre={pre_st.get(key)!r} post={post_st.get(key)!r}"
            )

    if pre.get("block_definitions") != 140:
        errors.append(
            f"pre-clear block_definitions expected 140 (F4b pin), found "
            f"{pre.get('block_definitions')!r}"
        )

    return {"ok": not errors, "errors": errors}


def build_baseline_document(
    *,
    source_path: str,
    source_sha256: str | None,
    source_byte_size: int | None,
    fixture_sha256: str,
    fixture_byte_size: int,
    pre: dict,
    post: dict,
    verification: dict,
    minted_at: str | None = None,
) -> dict:
    """The F4b baseline document Rung-A/Rung-C compare against (RT-FOLD R2-A6).
    Shape: schemas/pilot_cleared_seed_baseline.v1.schema.json.
    """
    return {
        "schema": BASELINE_SCHEMA_ID,
        "fixture": "fixtures/" + FIXTURE_NAME,
        "minted_at": minted_at or datetime.now(timezone.utc).isoformat(),
        "clear_scope": "modelspace_entities_only",
        "source": {
            "path": str(source_path),
            "sha256": source_sha256,
            "byte_size": source_byte_size,
        },
        "fixture_sha256": fixture_sha256,
        "fixture_byte_size": fixture_byte_size,
        "pre_clear": pre,
        "post_clear": post,
        "verification": verification,
    }


def render_deferred_command(source: str = DEFAULT_SOURCE_DWG) -> str:
    """The exact command to run once the erase op (step 3) exists and is
    promoted to status='implemented'."""
    return (
        '$env:PYTHONUTF8=1; python tools/mint_pilot_seed.py '
        f'--source "{source}"'
    )


def _read_ir(inspect_envelope: dict) -> "dict | None":
    ir_path = inspect_envelope.get("dwg_graph_ir")
    if not ir_path or not Path(ir_path).is_file():
        return None
    with open(ir_path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def mint(
    source_path: str = DEFAULT_SOURCE_DWG,
    *,
    force: bool = False,
    out_dir: "str | None" = None,
    cad: Any = None,
) -> dict:
    """Run the F4b pinned clear procedure end to end.

    Mint-ONCE: refuses (status='already_minted') if the fixture + sha already
    exist, unless force=True. Never fabricates the fixture: if a step cannot
    truthfully complete (missing source, missing runtime, missing op, a failed
    write, or a post-clear verification mismatch) mint() returns a truthful
    non-'ok' status and stops -- it does not write fixtures/pilot_cleared_seed.dwg
    unless every step (including verify_cleared) actually passed.
    """
    result: dict = {
        "schema": SCHEMA_ID,
        "node": "F4b",
        "source": str(source_path),
        "fixture": str(FIXTURE_PATH),
        "status": None,
        "reason": None,
        "plan": PINNED_CLEAR_PROCEDURE,
    }

    if not force and already_minted():
        result["status"] = "already_minted"
        result["reason"] = (
            f"{FIXTURE_PATH} and {SHA_PATH} already exist; F4b is mint-ONCE. "
            "Pass force=True / --force to deliberately re-pin."
        )
        return result

    src = Path(source_path)
    if not src.is_file():
        result["status"] = "blocked"
        result["reason"] = f"source DWG not found: {source_path}"
        return result

    if cad is None:
        try:
            import cadctl
        except Exception as exc:  # pragma: no cover - environment-dependent
            result["status"] = "unavailable"
            result["reason"] = f"cadctl unavailable: {type(exc).__name__}: {exc}"
            return result
        cad = cadctl.Cad()

    out_root = Path(out_dir) if out_dir else (ROUTER_HOME / "runs" / "mint_pilot_seed" / _ts())
    out_root.mkdir(parents=True, exist_ok=True)

    # --- step 1+2: stage + pre-clear baseline (read-only rich inspect) ---
    pre_env = cad.inspect(str(src), str(out_root / "pre"), mode="rich", include_rich=True)
    result["pre_inspect"] = pre_env
    if pre_env.get("status") != "ok":
        result["status"] = pre_env.get("status") or "unavailable"
        result["reason"] = f"pre-clear inspect did not succeed: {pre_env.get('reason')}"
        return result
    pre_ir = _read_ir(pre_env)
    if pre_ir is None:
        result["status"] = "unavailable"
        result["reason"] = "pre-clear inspect reported ok but wrote no dwg_graph_ir.json"
        return result
    pre = extract_baseline_counts(pre_ir)
    result["pre_clear"] = pre

    # --- step 3: erase (the real gap -- expect a truthful refusal today) ---
    erase_env = cad.run_operation(
        ERASE_MODELSPACE_OP_ID, args={"space": "model"},
        write_mode="write_copy", dwg_path=str(src), out_dir=str(out_root / "erase"),
    )
    result["erase"] = erase_env
    if not erase_env.get("executed"):
        result["status"] = "blocked"
        result["reason"] = (
            "erase step refused -- no erase op is implemented yet (see "
            f"PINNED_CLEAR_PROCEDURE step 3): {erase_env.get('reason')}"
        )
        return result

    # --- step 4: save the cleared copy out to the fixture path ---
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    save_env = cad.run_operation(
        "transform.database.save_as", args={"file_name": str(FIXTURE_PATH)},
        write_mode="write_copy", dwg_path=str(src), out_dir=str(out_root / "save_as"),
    )
    result["save_as"] = save_env
    if save_env.get("status") != "ok" or not FIXTURE_PATH.is_file():
        result["status"] = save_env.get("status") or "unavailable"
        result["reason"] = f"save_as of cleared copy did not succeed: {save_env.get('reason')}"
        return result

    # --- step 5: post-clear baseline + verification ---
    post_env = cad.inspect(str(FIXTURE_PATH), str(out_root / "post"), mode="rich", include_rich=True)
    result["post_inspect"] = post_env
    if post_env.get("status") != "ok":
        result["status"] = post_env.get("status") or "unavailable"
        result["reason"] = f"post-clear inspect did not succeed: {post_env.get('reason')}"
        return result
    post_ir = _read_ir(post_env)
    if post_ir is None:
        result["status"] = "unavailable"
        result["reason"] = "post-clear inspect reported ok but wrote no dwg_graph_ir.json"
        return result
    post = extract_baseline_counts(post_ir)
    result["post_clear"] = post

    verification = verify_cleared(pre, post)
    result["verification"] = verification
    if not verification["ok"]:
        result["status"] = "blocked"
        result["reason"] = f"post-clear verification failed: {verification['errors']}"
        # Do NOT leave a half-verified fixture behind as if it were canonical.
        try:
            FIXTURE_PATH.unlink()
        except OSError:
            pass
        return result

    # --- step 6+7: sha256 sidecar + baseline JSON (only now, everything verified) ---
    fixture_sha256 = _sha256_file(FIXTURE_PATH)
    SHA_PATH.write_text(fixture_sha256 + "  " + FIXTURE_NAME + "\n", encoding="utf-8")

    source_ir_source = pre_ir.get("source") or {}
    baseline = build_baseline_document(
        source_path=str(src),
        source_sha256=source_ir_source.get("sha256"),
        source_byte_size=source_ir_source.get("byte_size"),
        fixture_sha256=fixture_sha256,
        fixture_byte_size=FIXTURE_PATH.stat().st_size,
        pre=pre,
        post=post,
        verification=verification,
    )
    BASELINE_PATH.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["baseline"] = str(BASELINE_PATH)
    result["fixture_sha256"] = fixture_sha256
    result["status"] = "ok"
    return result


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("--source", default=DEFAULT_SOURCE_DWG, help="source DWG/DWS to clear (default: %(default)s)")
    ap.add_argument("--force", action="store_true", help="re-mint even if the fixture already exists")
    ap.add_argument("--out-dir", default=None, help="run directory for intermediate artifacts")
    args = ap.parse_args(argv)

    res = mint(args.source, force=args.force, out_dir=args.out_dir)
    printable = {k: v for k, v in res.items() if k != "plan"}
    print(json.dumps(printable, ensure_ascii=False, indent=2))

    return {
        "ok": 0, "already_minted": 0,
        "blocked": 3, "not_implemented": 3,
        "unavailable": 1, "partial": 1, "error": 1,
    }.get(res.get("status"), 1)


if __name__ == "__main__":
    raise SystemExit(main())
