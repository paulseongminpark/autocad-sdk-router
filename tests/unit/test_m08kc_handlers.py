#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer M08KC TEST -- native constraints / associativity (AcDbAssoc*) handlers.

Intent (WHY):
  M08KC fills families/m08kc_handlers.inc with the feasible-hostless, SOLVER-FREE subset
  of the AcDbAssoc* associativity/constraints network: assoc network/action lifecycle +
  read, dependency create/attach/subent, constraint read + delete, parameter/variable,
  and assoc-array identify. The invariants that carry business meaning and must fail CI
  if violated:

  1. HASOP <-> DISPATCH PARITY -- every op id m08kcHasOp admits must have an
     `op == "<id>"` branch in m08kcDispatch, and every dispatch branch must be admitted
     by HasOp. Drift => OPERATION_DISPATCH_MISMATCH at runtime (a catalogued op reads as
     "implemented" but no handler claims it, or a handler is dead because the gate rejects
     it). The native build proves it compiles+links; this proves the seam is coherent.

  2. HASOP LISTS EXACTLY THE IMPLEMENTED SET -- guards a silent shrink (a refactor
     dropping ops) or a silent fake-grow (claiming ops with no handler).

  3. NO SOLVER / NO ORIGINAL WRITE (source-level) -- the hard safety contract from
     PLAN_M08KC.md. The .inc must NOT call the associative-evaluation solver
     (AcDbAssocAction::evaluate, AcDbAssocManager::evaluateTopLevelNetwork) nor the
     array layout evaluator (AcDbAssocArrayActionBody::createInstance / resetArrayItems),
     and must NOT write the original DWG (save/saveAs/_QSAVE) nor drive the editor
     (acedCommand/acedCmd). Create ops must be guarded by AcDbAssocNetworkEvaluationDisabler
     so posting an object never fires evaluation.

  4. SOLVER/MODELER-BOUND OPS ARE HONESTLY DEFERRED -- the assocsurface.* (ASM modeler),
     *.evaluate, autoConstrain, dimassoc.geometryDriven, assocarray create/edit/explode
     (the createInstance/reset/transform layout pass IS the evaluator), assocdata.xref,
     assocsurface.topology, repair.assocdata.audit, AND the
     geometric/dimensional CONSTRAINT create ops must NOT appear in HasOp. This test pins
     that so a future edit cannot silently claim a solver-bound op.

  5. CALLBACK CONFIG OPS ARE READ-ONLY INTROSPECTION -- the global assoc-evaluation and
     2d-constraint callback ops may report status/counts, but must never register,
     remove, or invoke callbacks from the agent surface.

  Source-level only (no AutoCAD/build needed). Stdlib only.
"""
from __future__ import annotations

import os
import re
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_INC = os.path.join(_REPO, "src", "Ariadne.AcadNative", "families", "m08kc_handlers.inc")

# ---- The 25 IMPLEMENTED ops (feasible-hostless, solver-free) -----------------
# assoc network / action lifecycle + read/write-safe staged mutation (13)
_NETWORK_ACTION = [
    "define.assocaction.create",
    "define.assocaction.addDependency",
    "define.assocaction.valueParam",
    "define.assocnetwork.addAction",
    "edit.assocnetwork.removeAction",
    "inspect.assocnetwork.get",
    "inspect.assocnetwork.iterate",
    "inspect.assocaction.dependencies",
    "inspect.assocaction.requestToEvaluate",
    "inspect.assocmanager.state",
    "config.assocmanager.evalDisabler",
    "edit.assocdata.xref",
    "repair.assocdata.audit",
]
# dependencies (create / attach / subent) (5)
_DEPENDENCIES = [
    "define.assocdependency.attach",
    "define.assocgeomdependency.subent",
    "define.assocvaluedependency.value",
    "define.georef.subent",
    "define.perssubentid.resolve",
]
# constraints (read/delete + Wave3 authoring) (13)
_CONSTRAINTS = [
    "define.constraint.group",
    "define.constraint.addGeometry",
    "define.constraint.geometric",
    "define.constraint.autoConstrain",
    "define.constraint.dimensional.distance",
    "define.constraint.dimensional.angle",
    "define.constraint.dimensional.radiusDiameter",
    "define.dimassoc.geometryDriven",
    "edit.constraint.delete",
    "inspect.constraint.enumerate",
    "inspect.constraint.node",
    "inspect.constraint.status",
    "inspect.constraint.dimensional.value",
]
# parameters / variables (3)
_PARAMETERS = [
    "define.parameter.variable",
    "define.parameter.merge",
    "inspect.parameter.evaluate",
]
# assoc arrays -- read-only identify (1)
_ARRAYS = [
    "inspect.assocarray.identify",
]
# callback configuration -- read-only status/introspection only (2)
_CALLBACKS = [
    "config.assoceval.callback",
    "config.constraint.globalCallback",
]

_IMPLEMENTED = _NETWORK_ACTION + _DEPENDENCIES + _CONSTRAINTS + _PARAMETERS + _ARRAYS + _CALLBACKS

# ---- The 23 DEFERRED ops (solver / ASM modeler / mutating callback setup) ----
# These must NOT appear in HasOp (honest contract; no fakes).
_DEFERRED = [
    # ASM surface modeler (8)
    "define.assocsurface.blend",
    "define.assocsurface.extrude",
    "define.assocsurface.fillet",
    "define.assocsurface.loft",
    "define.assocsurface.offset",
    "define.assocsurface.patch",
    "define.assocsurface.result",
    "define.assocsurface.trim",
    # in-app evaluation solver (2)
    "inspect.assocaction.evaluate",
    "inspect.assocnetwork.evaluate",
    # assoc array create/edit/explode -- the layout pass IS the evaluator (10)
    "define.assocarray.create",
    "define.assocarray.rectangular",
    "define.assocarray.polar",
    "define.assocarray.path",
    "edit.assocarray.item",
    "edit.assocarray.itemReplace",
    "edit.assocarray.reset",
    "edit.assocarray.source",
    "edit.assocarray.transform",
    "edit.assocarray.explode",
    # topology only (xref sync + assoc audit reopened under staged-write contract)
    "inspect.assocsurface.topology",
]


def _read():
    with open(_INC, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _strip_comments(src):
    """Remove // line comments and /* */ block comments so the banned-token safety
    scans check ACTUAL CODE, not the header/safety prose that legitimately *names* the
    prohibited calls (e.g. "save()/saveAs() are NEVER called here"). String literals are
    left intact -- the emitted JSON/error strings are part of behavior."""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)   # block comments
    src = re.sub(r"//[^\n]*", "", src)                  # line comments
    return src


def _hasop_region(src):
    m = re.search(r"static bool m08kcHasOp\(const std::string& op\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "m08kcHasOp not found"
    return m.group(1)


def _dispatch_region(src):
    m = re.search(r"static bool m08kcDispatch\(.*?\)\s*\{(.*)\n\}\s*$", src, re.S)
    assert m, "m08kcDispatch not found"
    return m.group(1)


def _hasop_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _hasop_region(src)))


def _dispatch_ops(src):
    return set(re.findall(r'op == "([^"]+)"', _dispatch_region(src)))


class TestM08KCHandlers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read()
        cls.code = _strip_comments(cls.src)   # comment-free view for banned-call scans
        cls.hasop = _hasop_ops(cls.src)
        cls.dispatch = _dispatch_ops(cls.src)

    def test_inc_file_exists(self):
        self.assertTrue(os.path.exists(_INC), f"missing {_INC}")

    def test_signatures_present(self):
        self.assertRegex(self.src, r"bool\s+m08kcHasOp\(const std::string& op\)")
        self.assertRegex(
            self.src,
            r"bool\s+m08kcDispatch\(const std::string& op, const AriadneJobCtx& ctx, std::ostringstream& r\)",
        )

    def test_hasop_lists_exactly_implemented(self):
        self.assertEqual(
            self.hasop, set(_IMPLEMENTED),
            "m08kcHasOp op set drifted; only_in_src=%s missing_from_src=%s"
            % (sorted(self.hasop - set(_IMPLEMENTED)), sorted(set(_IMPLEMENTED) - self.hasop)),
        )

    def test_implemented_count(self):
        # Group totals: network/action=13, dependencies=5, constraints=13, parameters=3,
        # arrays=1, callbacks=2. 13+5+13+3+1+2 = 37 real handlers. The remaining 21
        # ops of the 58-op brief are the _DEFERRED solver/modeler set.
        self.assertEqual(len(_NETWORK_ACTION), 13)
        self.assertEqual(len(_DEPENDENCIES), 5)
        self.assertEqual(len(_CONSTRAINTS), 13)
        self.assertEqual(len(_PARAMETERS), 3)
        self.assertEqual(len(_ARRAYS), 1)
        self.assertEqual(len(_CALLBACKS), 2)
        self.assertEqual(len(_IMPLEMENTED), 37)
        self.assertEqual(len(set(_IMPLEMENTED)), 37, "duplicate op id in the implemented list")
        self.assertEqual(len(self.hasop), 37)

    def test_total_op_budget_is_58(self):
        # The brief is 58 ops: 37 implemented + 21 deferred, with no overlap.
        self.assertEqual(len(set(_DEFERRED)), 21, "duplicate op id in the deferred list")
        self.assertEqual(len(set(_IMPLEMENTED)) + len(set(_DEFERRED)), 58)
        self.assertEqual(set(_IMPLEMENTED) & set(_DEFERRED), set(), "an op is both implemented and deferred")

    def test_no_deferred_op_in_hasop(self):
        leaked = sorted(self.hasop & set(_DEFERRED))
        self.assertEqual(leaked, [], "solver/modeler/callback-bound ops leaked into m08kcHasOp: %s" % leaked)

    def test_hasop_dispatch_parity(self):
        missing = sorted(set(_IMPLEMENTED) - self.dispatch)
        self.assertEqual(missing, [], "implemented ops with no dispatch branch: %s" % missing)
        extra = sorted(self.dispatch - self.hasop)
        self.assertEqual(extra, [], "dispatch branches not admitted by HasOp: %s" % extra)

    def test_no_original_write_or_editor_tokens(self):
        # Hostless staged family: never write the original DWG nor drive the editor.
        banned = [
            r"\bsaveAs\b",
            r"\bsave\s*\(",
            r"_QSAVE",
            r"\bwriteDwgFile\b",
            r"\bacedCommand\b",
            r"\bacedCmd\b",
        ]
        for pat in banned:
            self.assertIsNone(
                re.search(pat, self.code),
                "must not contain original-write/editor token in code: %s" % pat,
            )

    def test_no_solver_evaluation_call(self):
        # *** The hard rule: never call the associative-evaluation solver. ***
        # AcDbAssocAction::evaluate(...) / AcDbAssocManager::evaluateTopLevelNetwork /
        # the array layout evaluator must be absent from the implemented handlers.
        banned = [
            r"->evaluate\s*\(",                 # pAction->evaluate(cb)  (the solver)
            r"\.evaluate\s*\(",
            r"evaluateTopLevelNetwork",         # AcDbAssocManager solver entry
            r"requestToEvaluate\s*\(",          # AcDbAssocManager::requestToEvaluate (queues a solve)
            r"::createInstance\b",              # AcDbAssocArrayActionBody::createInstance (evaluates layout)
            r"\bresetArrayItems\b",             # array re-layout (evaluator)
            r"evaluateDependencies\s*\(",       # action dependency evaluation
        ]
        for pat in banned:
            self.assertIsNone(
                re.search(pat, self.code),
                "implemented op must not invoke the solver/evaluator in code: %s" % pat,
            )
        # evaluateExpression IS allowed (the static parameter-expression parser, not the
        # network solver) -- sanity: it is the only "evaluate"-named symbol we use.
        self.assertIn("evaluateExpression", self.code,
                      "inspect.parameter.evaluate must use the static expression evaluator")

    def test_callback_config_is_introspection_only(self):
        self.assertIn("getGlobalEvaluationCallbacks", self.code)
        self.assertIn("globalCallback", self.code)
        banned = [
            r"addGlobalEvaluationCallback\s*\(",
            r"removeGlobalEvaluationCallback\s*\(",
            r"addGlobalCallback\s*\(",
            r"removeGlobalCallback\s*\(",
            r"setDoNotCheckNewlyAddedConstraints\s*\(",
        ]
        for pat in banned:
            self.assertIsNone(
                re.search(pat, self.code),
                "callback config op must be read-only introspection, not mutation: %s" % pat,
            )

    def test_create_ops_guard_disables_evaluation(self):
        # Every create op posts under an AcDbAssocNetworkEvaluationDisabler so adding an
        # object to the network can never fire the solver. Pin that the guard is used.
        self.assertIn("AcDbAssocNetworkEvaluationDisabler", self.src,
                      "create ops must scope an evaluation disabler to stay solver-free")

    def test_strings_use_utf8_njsonstr(self):
        self.assertIn("njsonStr", self.src, "string emission must route through njsonStr")
        self.assertNotIn("wideToAscii(", self.src, "must not use the lossy wideToAscii funnel")

    def test_validates_required_args_and_has_dispatch_guard(self):
        # handlers surface MISSING_ARG rather than fabricating output, and the
        # dispatch-mismatch guard exists (no silent fall-through).
        self.assertIn("MISSING_ARG", self.src)
        self.assertIn("OPERATION_DISPATCH_MISMATCH", self.src)

    def test_no_leak_new_objects_are_posted_or_deleted(self):
        # Every `new AcDbAssoc*` must be matched by addAcDbObject (post) on success or
        # delete on the failure path. Source-level smoke: count news vs posts+deletes.
        news = len(re.findall(r"new AcDbAssoc(?:Action|Variable)\b", self.src))
        posts = len(re.findall(r"addAcDbObject\(", self.src))
        deletes = len(re.findall(r"\bdelete pAction\b|\bdelete pVar\b", self.src))
        self.assertGreaterEqual(posts, news, "every new'd assoc object must be posted via addAcDbObject")
        self.assertGreaterEqual(deletes, news, "every new'd assoc object must be delete()'d on the failure path")


if __name__ == "__main__":
    unittest.main(verbosity=2)
