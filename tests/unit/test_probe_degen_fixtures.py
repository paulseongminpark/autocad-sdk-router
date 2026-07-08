"""WHY: the 2026-07-07 live sweep exposed no-CAD regressions that should stay
pinned in unit tests.

First, 24 RUNNABLE_BUT_DEGENERATE rows were pure fixture-authoring misses: the
native handler already reads real caller args, but FIXTURES had no entry, so
the empty-arg control call's created:true fake success stood as the final
class. 23 of those 24 were legitimately promoted with an authored valid-arg
fixture. The 24th, write.entity.solid3d.loft, was promoted in the first pass
too but reverted by a 2026-07-08 adversarial review (reports/
crash_triage_20260707.md): its only candidate fixture (width/depth/top_width/
top_depth/height) just rescales the SAME synthetic same-profile rectangle the
{} empty-arg call's own defaults already produce via createLoftedSolid() -- it
does not demonstrate a materially different code path, so promoting it would
be gaming the RUNNABLE classifier rather than proving non-degeneracy. Its
solid3d siblings, revolve (a 270 deg OPEN solid vs. the handler's 360 deg
CLOSED default) and sweep (a distinct swept path vs. the handler's default
straight extrusion), DO exercise materially different topology/code paths and
stay promoted. These tests assert the 23 promotable ops now have fixtures,
that write.entity.solid3d.loft plus six architecturally-blocked ops stay
fixtureless (7 total excluded), and that each fixture's top-level arg keys
appear verbatim WITHIN the op's own dispatch branch of the owning native
source file -- not merely anywhere in that (up to ~7700-line) file.

The original version of this test searched the WHOLE mapped C++ file for each
key (`f'"{arg_name}"' in source_text`). That only proves the key exists
SOMEWHERE in the file -- a key mistakenly authored under the wrong op's
fixture (e.g. "circle_sides", real only in write.vport.create's branch,
accidentally placed on write.dimstyle.create's fixture) would still have
passed, because both ops share AriadneNativeJob.cpp. The branch-scoped
rewrite below locates each op's own `if (op == "<op_id>")` /
`else if (op == "<op_id>")` dispatch site and bounds the search to that
handler's own text, up to the NEXT dispatch site in the file (or end of file
if it is the last branch) -- so a key placed on the wrong op's fixture now
fails on that op specifically, instead of silently matching some other op's
branch. If an op's dispatch site cannot be located at all, the test FAILS for
that op (never silently skips it) -- a silent skip would reintroduce exactly
the weak whole-file guard this rewrite exists to close.

Second, the isolated harness used to share one timeout budget across both probe
legs. The fix is per-leg budgeting. A stubbed leg runner here proves both legs
receive the full timeout and that a second-leg timeout reports which leg
exceeded budget and how long the completed first leg took.

This file is stdlib-only, pytest-discoverable, and never touches AutoCAD.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
import probe_reachability as pr  # noqa: E402


PROMOTABLE_FIXTURE_SOURCES = {
    "write.dimstyle.create": _ROOT / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp",
    "write.entity.attribdef": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.entity.face": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.entity.nurbsurface": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.entity.point": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.entity.ray": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.entity.shape": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.entity.solid2d": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.entity.solid3d.extrude": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.entity.solid3d.primitive": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.entity.solid3d.revolve": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.entity.solid3d.sweep": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.entity.subdmesh": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.entity.surface": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.entity.table": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08h_handlers.inc",
    "write.entity.tolerance": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.entity.trace": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.entity.xline": _ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08g_handlers.inc",
    "write.linetype.create": _ROOT / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp",
    "write.textstyle.create": _ROOT / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp",
    "write.ucs.create": _ROOT / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp",
    "write.view.create": _ROOT / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp",
    "write.vport.create": _ROOT / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp",
}

NON_PROMOTABLE_OPS = (
    "write.entity.body",
    "define.assocaction.create",
    "define.constraint.group",
    "editor.react.events",
    "live.overrule.enable",
    "live.reactor.enable",
    "write.entity.solid3d.loft",
)


def _ok_env(created: bool) -> dict:
    return {
        "schema": "ariadne.cadctl.run_operation.v1",
        "operation": "x",
        "executed": True,
        "registry_operation_status": "implemented",
        "write_mode": "write_copy",
        "original_unchanged": True,
        "status": "ok",
        "result": {
            "created": created,
            "class": "AcDbLine",
            "handle": "8F8D",
            "layer": "ARIADNE_F1_PROBE",
            "modelspace_entities_after": 1,
        },
    }


# --------------------------------------------------------------------------- #
# Branch-scoping: find an op's OWN dispatch region instead of trusting a
# whole-file substring search. C++ dispatch in this codebase is a flat
# `if (op == "<id>") { ... return true; }` / `else if (op == "<id>") { ... }`
# chain per file (verified against AriadneNativeJob.cpp and both
# m08g_handlers.inc / m08h_handlers.inc) -- NOT the multi-condition
# `op == "<id>" || op == "<id2>" || ...` shape used only by each family's
# separate HasOp() admission-gate function, which this anchor pattern
# deliberately does NOT match (it requires `if (` / `else if (` immediately
# before `op ==`, which HasOp()'s `return ... || op == "..."` lines lack).
# --------------------------------------------------------------------------- #
_DISPATCH_ANCHOR_FMT = r'(?:else\s+)?if\s*\(\s*op\s*==\s*"{}"\s*\)'
_DISPATCH_ANY_RE = re.compile(r'(?:else\s+)?if\s*\(\s*op\s*==\s*"')

# "layer" is the one arg key that is NOT read inside every op's own branch:
# m08g_handlers.inc reads it exactly ONCE, in a shared preamble immediately
# before its per-op dispatch chain begins (m08g_handlers.inc:499-500,
# `std::string layer; jsonFindString(job, "layer", layer);`, executed for
# EVERY op that family admits, regardless of which `if (op == ...)` branch
# ends up matching) -- so it can never appear inside any individual op's own
# bounded region there by construction. (m08h_handlers.inc, in contrast,
# re-reads "layer" locally inside EACH op's own branch -- confirmed at
# write.entity.table's branch itself -- so it needs no exception there.)
# Rather than silently exempting this key from the per-op check everywhere
# (which would reopen exactly the wrong-branch hole this rewrite closes), the
# fallback below only accepts a shared-preamble match for keys named here,
# and only once the strict per-branch check has already failed.
_SHARED_PREAMBLE_KEYS = {"layer"}


def _find_own_handler_region(source_text: str, op_id: str) -> str | None:
    """Bound op_id's OWN handler text: from its dispatch site to the NEXT
    dispatch literal (any op) in the file, or end-of-file if it is the last
    branch in the chain. Returns None if the dispatch site itself cannot be
    located -- callers MUST fail loud on None, never silently skip (a silent
    skip reintroduces the whole-file weak guard this rewrite closes)."""
    anchor = re.search(_DISPATCH_ANCHOR_FMT.format(re.escape(op_id)), source_text)
    if anchor is None:
        return None
    nxt = _DISPATCH_ANY_RE.search(source_text, anchor.end())
    end = nxt.start() if nxt is not None else len(source_text)
    return source_text[anchor.start():end]


def _shared_preamble(source_text: str) -> str:
    """Text preceding the FIRST `if (op == "...")` / `else if (op == "...")`
    dispatch branch in the file -- shared setup code (if any) that runs
    before any op-specific branch is even reached, e.g. m08g_handlers.inc's
    single shared `layer` read. Empty string if no dispatch branch exists."""
    first = _DISPATCH_ANY_RE.search(source_text)
    return source_text[:first.start()] if first is not None else ""


def _key_is_present(source_text: str, region: str, arg_name: str) -> bool:
    needle = f'"{arg_name}"'
    if needle in region:
        return True
    return arg_name in _SHARED_PREAMBLE_KEYS and needle in _shared_preamble(source_text)


class ProbeDegenerateFixtureTests(unittest.TestCase):
    def test_promotable_ops_have_fixtures_with_real_handler_keys(self) -> None:
        for op_id, source_path in PROMOTABLE_FIXTURE_SOURCES.items():
            with self.subTest(op_id=op_id):
                self.assertIn(op_id, pr.FIXTURES)
                args = pr.FIXTURES[op_id]["args"]
                self.assertTrue(args)
                source_text = source_path.read_text(encoding="utf-8")
                region = _find_own_handler_region(source_text, op_id)
                self.assertIsNotNone(
                    region,
                    f'{op_id}: no `if (op == "{op_id}")` / `else if (op == "{op_id}")` '
                    f"dispatch site found in {source_path.name} -- cannot branch-scope "
                    f"the key check for this op (FAIL, not skip)",
                )
                for arg_name in args:
                    self.assertTrue(
                        _key_is_present(source_text, region, arg_name),
                        f"{op_id}: handler key {arg_name!r} not found WITHIN its own "
                        f"dispatch branch of {source_path.name} (a whole-file search "
                        f"would have missed a key placed under the wrong op's fixture), "
                        f"nor in the file's shared pre-dispatch preamble "
                        f"({sorted(_SHARED_PREAMBLE_KEYS)!r} only)",
                    )

    def test_promotable_and_excluded_op_counts(self) -> None:
        """Net promoted rows from the 2026-07-07 sweep: 23 (was 24 before the
        2026-07-08 adversarial review reverted write.entity.solid3d.loft --
        gaming the classifier, see reports/crash_triage_20260707.md). The
        deferred/no-fixture set is 7."""
        self.assertEqual(len(PROMOTABLE_FIXTURE_SOURCES), 23)
        self.assertEqual(len(NON_PROMOTABLE_OPS), 7)
        self.assertIn("write.entity.solid3d.loft", NON_PROMOTABLE_OPS)
        self.assertNotIn("write.entity.solid3d.loft", PROMOTABLE_FIXTURE_SOURCES)

    def test_non_promotable_ops_stay_fixtureless(self) -> None:
        for op_id in NON_PROMOTABLE_OPS:
            with self.subTest(op_id=op_id):
                self.assertNotIn(op_id, pr.FIXTURES)

    def test_per_leg_timeout_uses_full_budget_and_names_timed_out_leg(self) -> None:
        calls: list[tuple[str, float]] = []

        def fake_run_probe_leg(op_id, dwg_path, out_dir, *, fixture, timeout_sec):
            calls.append((Path(out_dir).name, timeout_sec))
            if Path(out_dir).name == "empty":
                return _ok_env(True), 47.2
            return {"_probe_timeout": True}, 60.0

        with mock.patch.object(pr, "_run_probe_leg", side_effect=fake_run_probe_leg):
            payload = pr._run_isolated(
                "write.entity.point",
                _ROOT / "tests" / "fixtures" / "native_sample.dwg",
                _ROOT / "runs" / "unit_probe_timeout",
                {"position": {"x": 3.5, "y": 4.5, "z": 0.0}},
                60.0,
            )

        self.assertEqual(calls, [("empty", 60.0), ("valid", 60.0)])
        agg = pr.classify_op_result(payload)
        self.assertEqual(agg["class"], pr.ATTENDED_ONLY)
        self.assertEqual(
            agg["valid_arg_probe"]["reason"],
            "valid-arg leg exceeded 60.0s (empty-arg leg completed in 47.2s)",
        )


if __name__ == "__main__":
    unittest.main()
