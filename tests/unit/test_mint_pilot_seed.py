"""F4b -- tools/mint_pilot_seed.py unit tests (no accoreconsole needed).

These are the synthetic/mocked proof required because the live pinned-clear
procedure needs two things this headless suite cannot assume: a real CAD
runtime AND a native "erase modelspace entity" op that does not exist yet in
config/operations.v2.json (verified below, against the REAL registry). Every
test here exercises tools/mint_pilot_seed.py's actual logic (baseline
extraction, clear verification, mint-once idempotency, the never-fabricate
guard) against a `cad` test double built from the REAL field shapes
cadctl.Cad().inspect()/run_operation() return (see tools/cadctl.py). The
"actually erases + saves headless" proof is the separate CADOS_LIVE smoke this
module documents via render_deferred_command(), matching the convention in
tests/unit/test_run_operation_gates.py and tests/integration/
test_native_graph_router.py.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import mint_pilot_seed as mps  # noqa: E402

try:
    import jsonschema
except ImportError:  # optional, matches tests/unit/test_dwg_graph_ir_schema.py
    jsonschema = None

_REGISTRY = _ROOT / "config" / "operations.v2.json"
_BASELINE_SCHEMA = _ROOT / "schemas" / "pilot_cleared_seed_baseline.v1.schema.json"


# --------------------------------------------------------------------------- helpers

def _synthetic_ir(*, entity_count: int, block_definitions: int,
                  block_references: int, symbol_tables: dict,
                  xrefs=0, dictionaries=1, extension_dictionaries=1,
                  xrecords=2, layouts=3, entity_types=None) -> dict:
    """Build a small ariadne.dwg_graph_ir.v1 (rich)-shaped document at the
    EXACT counts requested, mirroring the real field names/shape captured live
    against D:\\dev\\.build\\test.dws (see mint_pilot_seed.PRE_CLEAR_REFERENCE)."""
    entity_types = entity_types or {"LINE": entity_count}
    entities = []
    for dxf_name, count in entity_types.items():
        for i in range(count):
            entities.append({"handle": f"{dxf_name}{i}", "dxf_name": dxf_name, "space": "model"})
    assert len(entities) == entity_count
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "coverage_level": "native_full",
        "source": {"path": "staged.dwg", "sha256": "deadbeef", "byte_size": 123},
        "symbol_tables": {k: [{"name": f"{k}{i}"} for i in range(n)] for k, n in symbol_tables.items()},
        "block_definitions": [{"name": f"BLK{i}"} for i in range(block_definitions)],
        "block_references": [{"handle": f"INS{i}"} for i in range(block_references)],
        "xrefs": [{}] * xrefs,
        "dictionaries": [{}] * dictionaries,
        "extension_dictionaries": [{}] * extension_dictionaries,
        "xrecords": [{}] * xrecords,
        "layouts": [{}] * layouts,
        "entities": entities,
    }


_PRE_IR = _synthetic_ir(
    entity_count=mps.PRE_CLEAR_REFERENCE["modelspace_entity_count"],
    block_definitions=mps.PRE_CLEAR_REFERENCE["block_definitions"],
    block_references=mps.PRE_CLEAR_REFERENCE["block_references"],
    symbol_tables=mps.PRE_CLEAR_REFERENCE["symbol_tables"],
    xrefs=mps.PRE_CLEAR_REFERENCE["xrefs"],
    dictionaries=mps.PRE_CLEAR_REFERENCE["dictionaries"],
    extension_dictionaries=mps.PRE_CLEAR_REFERENCE["extension_dictionaries"],
    xrecords=mps.PRE_CLEAR_REFERENCE["xrecords"],
    layouts=mps.PRE_CLEAR_REFERENCE["layouts"],
    entity_types=mps.PRE_CLEAR_REFERENCE["entities_by_type"],
)


def _post_ir_from(pre_ir: dict) -> dict:
    """A correctly-cleared IR: entities/block_references -> empty, everything
    else identical to pre_ir (the only truthful shape of a good F4b clear)."""
    post = copy.deepcopy(pre_ir)
    post["entities"] = []
    post["block_references"] = []
    return post


class FakeCad:
    """cadctl.Cad() test double. inspect()/run_operation() return dicts shaped
    exactly like the real methods (see tools/cadctl.py Cad.inspect /
    Cad.run_operation / Cad._run_op_refusal) so mint()'s parsing logic is
    genuinely exercised, not just trivially satisfied."""

    def __init__(self, *, pre_ir=None, post_ir=None, erase_executed=False,
                save_as_status="ok", write_fixture_bytes=b"FAKE-DWG-BYTES"):
        self.pre_ir = pre_ir if pre_ir is not None else _PRE_IR
        self.post_ir = post_ir if post_ir is not None else _post_ir_from(self.pre_ir)
        self.erase_executed = erase_executed
        self.save_as_status = save_as_status
        self.write_fixture_bytes = write_fixture_bytes
        self.calls: list[tuple[str, dict]] = []
        self._inspect_n = 0

    def inspect(self, dwg_path, out_dir, mode="graph", include_rich=False):
        self.calls.append(("inspect", {"dwg_path": dwg_path, "out_dir": out_dir,
                                       "mode": mode, "include_rich": include_rich}))
        self._inspect_n += 1
        ir = self.pre_ir if self._inspect_n == 1 else self.post_ir
        out_dir_p = Path(out_dir)
        out_dir_p.mkdir(parents=True, exist_ok=True)
        ir_path = out_dir_p / "dwg_graph_ir.json"
        ir_path.write_text(json.dumps(ir, ensure_ascii=False), encoding="utf-8")
        return {"schema": "ariadne.cadctl.inspect.v1", "status": "ok",
                "operation": "inspect.database.graph", "dwg_graph_ir": str(ir_path),
                "entity_count": len(ir.get("entities") or [])}

    def run_operation(self, op_id, args=None, write_mode=None, dwg_path=None, out_dir=None):
        self.calls.append(("run_operation", {"op_id": op_id, "args": args,
                                             "write_mode": write_mode, "dwg_path": dwg_path,
                                             "out_dir": out_dir}))
        if op_id == mps.ERASE_MODELSPACE_OP_ID:
            if not self.erase_executed:
                # Mirrors cadctl.Cad._run_op_refusal exactly (real shape: not_found).
                return {"schema": "ariadne.cadctl.run_operation.v1", "operation": op_id,
                        "status": "not_found", "executed": False,
                        "registry_operation_status": None,
                        "reason": f"operation '{op_id}' is not in the operation registry"}
            return {"schema": "ariadne.cadctl.run_operation.v1", "operation": op_id,
                    "status": "ok", "executed": True}
        if op_id == "transform.database.save_as":
            if self.save_as_status == "ok":
                dest = Path(args["file_name"])
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(self.write_fixture_bytes)
            return {"schema": "ariadne.cadctl.run_operation.v1", "operation": op_id,
                    "executed": True, "status": self.save_as_status,
                    "reason": None if self.save_as_status == "ok" else "simulated save_as failure"}
        raise AssertionError(f"unexpected op_id in FakeCad.run_operation: {op_id}")


@pytest.fixture(autouse=True)
def _isolated_fixture_paths(tmp_path, monkeypatch):
    """Every test gets its own fixtures/ dir -- never touches the real
    fixtures/pilot_cleared_seed.dwg (which does not exist yet, per this
    node's DONE_NEEDS_RUNTIME status)."""
    fixtures_dir = tmp_path / "fixtures"
    monkeypatch.setattr(mps, "FIXTURES_DIR", fixtures_dir)
    monkeypatch.setattr(mps, "FIXTURE_PATH", fixtures_dir / mps.FIXTURE_NAME)
    monkeypatch.setattr(mps, "SHA_PATH", fixtures_dir / (mps.FIXTURE_NAME + ".sha256"))
    monkeypatch.setattr(mps, "BASELINE_PATH", fixtures_dir / "pilot_cleared_seed.baseline.json")
    return fixtures_dir


def _make_source(tmp_path) -> Path:
    src = tmp_path / "source.dws"
    src.write_bytes(b"not a real dwg, just needs to exist for the is_file() check")
    return src


# --------------------------------------------------------------------------- baseline extraction

def test_extract_baseline_counts_matches_live_measured_reference():
    """extract_baseline_counts() must reproduce the exact F4b-pinned figures
    (140 block defs, 375 modelspace entities, 91 layers, ...) that were
    measured LIVE against the real D:\\dev\\.build\\test.dws source (see
    PRE_CLEAR_REFERENCE) -- not just whatever a hand-picked toy IR contains."""
    counts = mps.extract_baseline_counts(_PRE_IR)

    assert counts["modelspace_entity_count"] == 375
    assert counts["block_definitions"] == 140
    assert counts["block_references"] == 50
    assert counts["entities_by_type"] == {
        "TEXT": 117, "DIMENSION": 113, "LWPOLYLINE": 73, "INSERT": 50, "LINE": 21, "CIRCLE": 1,
    }
    assert counts["symbol_tables"] == {
        "layers": 91, "linetypes": 18, "text_styles": 8, "dim_styles": 6,
        "viewports": 1, "app_ids": 25, "block_table_records": 410,
    }
    assert counts["xrefs"] == 0
    assert counts["dictionaries"] == 1
    assert counts["extension_dictionaries"] == 1
    assert counts["xrecords"] == 2
    assert counts["layouts"] == 3


def test_extract_baseline_counts_handles_missing_sections_as_empty():
    """A minimal/degenerate IR (sections dropped) must count as zero, not crash --
    the extractor must never KeyError on a partial IR."""
    counts = mps.extract_baseline_counts({"entities": []})
    assert counts["modelspace_entity_count"] == 0
    assert counts["block_definitions"] == 0
    assert counts["symbol_tables"] == {k: 0 for k in mps.RETAINED_SYMBOL_TABLE_KEYS}


# --------------------------------------------------------------------------- verify_cleared

def test_verify_cleared_passes_on_a_correct_clear():
    pre = mps.extract_baseline_counts(_PRE_IR)
    post = mps.extract_baseline_counts(_post_ir_from(_PRE_IR))
    v = mps.verify_cleared(pre, post)
    assert v == {"ok": True, "errors": []}


@pytest.mark.parametrize("mutate_key,bad_value", [
    ("block_definitions", 139),   # dropped a block def
    ("xrefs", 1),                 # xrefs should stay 0
    ("layouts", 2),                # a layout got dropped
])
def test_verify_cleared_flags_retained_field_drift(mutate_key, bad_value):
    pre = mps.extract_baseline_counts(_PRE_IR)
    post = mps.extract_baseline_counts(_post_ir_from(_PRE_IR))
    post[mutate_key] = bad_value
    v = mps.verify_cleared(pre, post)
    assert v["ok"] is False
    assert any(mutate_key in e for e in v["errors"])


def test_verify_cleared_flags_leftover_modelspace_entities():
    pre = mps.extract_baseline_counts(_PRE_IR)
    bad_post_ir = _post_ir_from(_PRE_IR)
    bad_post_ir["entities"] = [{"handle": "LEFTOVER", "dxf_name": "LINE", "space": "model"}]
    post = mps.extract_baseline_counts(bad_post_ir)
    v = mps.verify_cleared(pre, post)
    assert v["ok"] is False
    assert any("modelspace_entity_count" in e for e in v["errors"])
    assert any("entities_by_type" in e for e in v["errors"])


def test_verify_cleared_flags_symbol_table_drift():
    pre = mps.extract_baseline_counts(_PRE_IR)
    bad_post_ir = _post_ir_from(_PRE_IR)
    bad_post_ir["symbol_tables"]["layers"] = bad_post_ir["symbol_tables"]["layers"][:-1]  # drop 1 layer
    post = mps.extract_baseline_counts(bad_post_ir)
    v = mps.verify_cleared(pre, post)
    assert v["ok"] is False
    assert any("symbol_tables.layers" in e for e in v["errors"])


def test_verify_cleared_flags_source_not_pinned_at_140():
    """If the SOURCE itself didn't have 140 block defs, the whole F4b pin is
    void -- verify_cleared must say so rather than silently accepting it."""
    pre_ir = _synthetic_ir(entity_count=1, block_definitions=99, block_references=0,
                           symbol_tables=mps.PRE_CLEAR_REFERENCE["symbol_tables"])
    pre = mps.extract_baseline_counts(pre_ir)
    post = mps.extract_baseline_counts(_post_ir_from(pre_ir))
    v = mps.verify_cleared(pre, post)
    assert v["ok"] is False
    assert any("140" in e for e in v["errors"])


# --------------------------------------------------------------------------- mint() orchestration

def test_mint_refuses_when_source_missing(tmp_path):
    res = mps.mint(str(tmp_path / "does_not_exist.dws"), cad=FakeCad())
    assert res["status"] == "blocked"
    assert "not found" in res["reason"]


def test_mint_is_idempotent_mint_once(tmp_path, _isolated_fixture_paths):
    fixtures_dir = _isolated_fixture_paths
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    (fixtures_dir / mps.FIXTURE_NAME).write_bytes(b"already here")
    (fixtures_dir / (mps.FIXTURE_NAME + ".sha256")).write_text("deadbeef\n", encoding="utf-8")

    src = _make_source(tmp_path)
    res = mps.mint(str(src), cad=FakeCad())

    assert res["status"] == "already_minted"
    assert "mint-ONCE" in res["reason"]


def test_mint_stops_truthfully_and_never_fabricates_when_erase_missing(tmp_path):
    """The real-world case today: erase is not implemented. mint() must report
    'blocked' and must NOT write the fixture, the sha sidecar, or the baseline."""
    src = _make_source(tmp_path)
    fake = FakeCad(erase_executed=False)

    res = mps.mint(str(src), out_dir=str(tmp_path / "run"), cad=fake)

    assert res["status"] == "blocked"
    assert "erase step refused" in res["reason"]
    assert res["pre_clear"]["block_definitions"] == 140  # pre-baseline WAS captured (real, useful work)
    assert not mps.FIXTURE_PATH.exists()
    assert not mps.SHA_PATH.exists()
    assert not mps.BASELINE_PATH.exists()
    # exactly the two calls that CAN run today: pre-inspect, then the erase
    # attempt. save_as/post-inspect must never be reached.
    assert [c[0] for c in fake.calls] == ["inspect", "run_operation"]


def test_mint_full_success_path_writes_fixture_sha_and_baseline(tmp_path):
    """Once erase + save_as both genuinely work (simulated here), mint() must
    complete: write the fixture, a matching sha256 sidecar, and a baseline
    document that VALIDATES against schemas/pilot_cleared_seed_baseline.v1.schema.json."""
    src = _make_source(tmp_path)
    fake = FakeCad(erase_executed=True, save_as_status="ok")

    res = mps.mint(str(src), out_dir=str(tmp_path / "run"), cad=fake)

    assert res["status"] == "ok", res
    assert mps.FIXTURE_PATH.is_file()
    assert mps.SHA_PATH.is_file()
    assert mps.BASELINE_PATH.is_file()

    # sha256 sidecar must match the actual bytes written.
    expected_sha = mps._sha256_file(mps.FIXTURE_PATH)
    assert expected_sha in mps.SHA_PATH.read_text(encoding="utf-8")
    assert res["fixture_sha256"] == expected_sha

    baseline = json.loads(mps.BASELINE_PATH.read_text(encoding="utf-8"))
    assert baseline["schema"] == mps.BASELINE_SCHEMA_ID
    assert baseline["post_clear"]["modelspace_entity_count"] == 0
    assert baseline["post_clear"]["block_definitions"] == 140
    assert baseline["verification"]["ok"] is True

    if jsonschema is not None:
        schema = json.loads(_BASELINE_SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(baseline, schema)

    # full call sequence: pre-inspect, erase, save_as, post-inspect.
    assert [c[0] for c in fake.calls] == ["inspect", "run_operation", "run_operation", "inspect"]


def test_mint_rejects_and_cleans_up_a_falsely_verified_fixture(tmp_path):
    """If save_as 'succeeds' but the written file is actually WRONG (here: the
    post-clear IR still shows leftover entities), mint() must refuse to certify
    it and must delete the fixture it just wrote -- never leave an unverified
    file sitting at the canonical F4b path."""
    src = _make_source(tmp_path)
    bad_post_ir = _post_ir_from(_PRE_IR)
    bad_post_ir["entities"] = [{"handle": "LEFTOVER", "dxf_name": "LINE", "space": "model"}]
    fake = FakeCad(erase_executed=True, save_as_status="ok", post_ir=bad_post_ir)

    res = mps.mint(str(src), out_dir=str(tmp_path / "run"), cad=fake)

    assert res["status"] == "blocked"
    assert "post-clear verification failed" in res["reason"]
    assert not mps.FIXTURE_PATH.exists(), "a failed-verification fixture must not be left behind"
    assert not mps.SHA_PATH.exists()
    assert not mps.BASELINE_PATH.exists()


def test_mint_force_remints_over_an_existing_fixture(tmp_path, _isolated_fixture_paths):
    fixtures_dir = _isolated_fixture_paths
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    (fixtures_dir / mps.FIXTURE_NAME).write_bytes(b"stale")
    (fixtures_dir / (mps.FIXTURE_NAME + ".sha256")).write_text("stale\n", encoding="utf-8")

    src = _make_source(tmp_path)
    fake = FakeCad(erase_executed=True, save_as_status="ok")
    res = mps.mint(str(src), out_dir=str(tmp_path / "run"), force=True, cad=fake)

    assert res["status"] == "ok"
    assert mps.FIXTURE_PATH.read_bytes() == fake.write_fixture_bytes


# --------------------------------------------------------------------------- plan / honesty pins

def test_pinned_clear_procedure_is_well_formed():
    steps = mps.PINNED_CLEAR_PROCEDURE
    assert [s["step"] for s in steps] == list(range(1, 8))
    for s in steps:
        assert {"step", "action", "op_id", "method", "note"} <= set(s.keys())

    erase_step = steps[2]
    assert erase_step["action"] == "erase_modelspace_entities"
    assert erase_step["op_id"] == mps.ERASE_MODELSPACE_OP_ID
    assert "NOT YET IMPLEMENTED" in erase_step["note"]

    save_step = steps[3]
    assert save_step["op_id"] == "transform.database.save_as"
    assert "catalogued_not_runnable" in save_step["note"]


def test_render_deferred_command_names_the_real_script_and_default_source():
    cmd = mps.render_deferred_command()
    assert "tools/mint_pilot_seed.py" in cmd
    assert mps.DEFAULT_SOURCE_DWG in cmd
    assert "--source" in cmd


def test_erase_op_truly_absent_and_save_as_truly_not_runnable_in_the_real_registry():
    """Ties the honesty claims in PINNED_CLEAR_PROCEDURE to the REAL registry
    shipped in this repo (config/operations.v2.json), not just to prose. If
    either op's status ever changes, THIS test must be the one that breaks --
    a signal to re-check whether F4b can now mint live."""
    ops = json.loads(_REGISTRY.read_text(encoding="utf-8-sig"))["operations"]
    ids = {o["id"] for o in ops}
    assert mps.ERASE_MODELSPACE_OP_ID not in ids, (
        f"{mps.ERASE_MODELSPACE_OP_ID} now exists in the registry -- F4b may be "
        "unblocked; update PINNED_CLEAR_PROCEDURE step 3 and re-check DONE_NEEDS_RUNTIME."
    )

    save_as = next(o for o in ops if o["id"] == "transform.database.save_as")
    assert save_as["status"] == "implemented"
    # policy.status_policy now mirrors top-level status by legislation
    # (tools/policy_hygiene.py, 2026-07-07), so it can no longer serve as the
    # not-yet-proven-headless tripwire. The durable signal is the evidence ref
    # marking the native job smoke as deferred/attended-only.
    evidence = "\n".join(save_as.get("evidence_refs") or [])
    assert "runtime_native_job_smoke:deferred_attended" in evidence, (
        "transform.database.save_as no longer carries the deferred_attended smoke "
        "marker -- it may now be genuinely runnable headless; re-check step 4's "
        "CAUTION note and F4b's blocked status."
    )
