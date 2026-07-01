#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""adversarial_fixtures.py -- F3-self: 5 hand-built adversarial IR pairs.

This is the META-GUARD for ``tools/cad_op_gate.py``: five deliberately-broken
``(pre_ir, post_ir)`` pairs, each modelling a DIFFERENT way a P/D-gate
perturbation could be lying about what it proves, hand-crafted (never built
via ``cad_op_gate.perturb_field_replace``, since several of these are
violations that function itself refuses to construct). Every case's
``run()`` returns the gate result ``check_mutation_pair`` (or, for case B,
``check_fingerprint_discriminability``) produces; the expected exit code is
pinned alongside it in ``CASES`` below.

    (a) field_absent            -- the field targeted for perturbation was
                                    never populated on the pre-entity at all.
    (b) bucket_collapse          -- two DISTINCT entities of the same kind
                                    collapse onto the SAME geometry
                                    fingerprint ("degenerate dim").
    (c) key_injected              -- the post-entity carries a brand-new key
                                    the pre-entity never had (an injected
                                    field, not a replaced value).
    (d) coarse_quantized_invisible -- a simulated coarse extractor stores the
                                    IDENTICAL (rounded) value on both sides
                                    even though a real edit occurred --
                                    zero modified entities detected.
    (e) wrong_entity_modified    -- the diff reports exactly one modified
                                    entity, but it is NOT the entity that was
                                    supposedly perturbed (identity check must
                                    reject this -- the ONE case that is NOT
                                    exit 4; see module docstring "mostly exit
                                    4" in cad_op_gate.py).

Dual-runnable: discoverable by both pytest and
``python -m unittest discover -s tests``. Stdlib only.
"""
from __future__ import annotations

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cad_op_gate  # noqa: E402

IR_SCHEMA_ID = cad_op_gate.IR_SCHEMA_ID


def _entity(handle, dxf_name="LINE", layer="0", geometry=None, extra=None):
    e = {"handle": handle, "dxf_name": dxf_name, "layer": layer,
        "geometry": geometry if geometry is not None else {"kind": "line", "start": [0.0, 0.0, 0.0],
                                                            "end": [10.0, 0.0, 0.0]}}
    if extra:
        e.update(extra)
    return e


def _ir(*entities):
    return {"schema": IR_SCHEMA_ID, "entities": [dict(e) for e in entities]}


# --------------------------------------------------------------------------- #
# (a) field-absent -- perturbation target was never populated
# --------------------------------------------------------------------------- #

def case_a_field_absent():
    """pre-entity has no ``xdata`` at all; a legitimate D-gate probe of that
    field must refuse (fail-closed), not fabricate a value."""
    pre = _ir(_entity("A1", layer="WALLS"))
    post = _ir(_entity("A1", layer="WALLS"))  # no field present on either side
    return cad_op_gate.check_mutation_pair(pre, post, "A1", "xdata")


# --------------------------------------------------------------------------- #
# (b) single-bucket-collapsed kind -- degenerate dim
# --------------------------------------------------------------------------- #

def case_b_bucket_collapse():
    """Two DISTINCT CIRCLE entities (different handles) whose geometry, once
    quantized, collapses onto the identical fingerprint bucket -- a
    "degenerate dim" (an extractor that zeroed out the true distinguishing
    coordinate). A geometry-basis roundtrip built on top of this population
    could silently pair a real defect against the wrong twin."""
    degenerate_geom = {"kind": "circle", "center": [0.0, 0.0, 0.0], "radius": 0.0}
    entities = [
        _entity("B1", dxf_name="CIRCLE", layer="0", geometry=degenerate_geom),
        _entity("B2", dxf_name="CIRCLE", layer="0", geometry=degenerate_geom),
    ]
    return cad_op_gate.check_fingerprint_discriminability(entities)


# --------------------------------------------------------------------------- #
# (c) key-injected perturbation -- replace-not-inject violation
# --------------------------------------------------------------------------- #

def case_c_key_injected():
    """post-entity introduces a brand-new top-level key (``xdata``) the
    pre-entity never had, instead of replacing an existing field's value --
    ``validate_replace_not_inject`` must reject this outright."""
    pre = _ir(_entity("C1", layer="0"))
    post_entity = _entity("C1", layer="0")
    post_entity["xdata"] = [{"app": "INJECTED", "value": "not a real replace"}]
    post = _ir(post_entity)
    return cad_op_gate.check_mutation_pair(pre, post, "C1", "layer")


# --------------------------------------------------------------------------- #
# (d) coarse-quantized extractor sim -- invisible data (zero modified found)
# --------------------------------------------------------------------------- #

def case_d_coarse_quantized_invisible():
    """A real edit occurred (the TRUE end-x moved from 10.03 to 10.43) but a
    simulated coarse extractor rounds BOTH reads to the nearest whole unit,
    so pre_entity and post_entity end up with the IDENTICAL stored value
    (10.0) -- the diff detects ZERO modified entities even though a genuine
    field-level change happened. This is exactly the failure a Rung-A sweep
    exists to catch: invisible data from a lossy/coarse extraction path."""
    coarse_geom = {"kind": "line", "start": [0.0, 0.0, 0.0], "end": [10.0, 0.0, 0.0]}
    pre = _ir(_entity("D1", geometry=coarse_geom))
    post = _ir(_entity("D1", geometry=dict(coarse_geom)))  # identical after coarse rounding
    return cad_op_gate.check_mutation_pair(pre, post, "D1", "geometry.end")


# --------------------------------------------------------------------------- #
# (e) wrong-entity-modified -- identity check must reject
# --------------------------------------------------------------------------- #

def case_e_wrong_entity_modified():
    """Two entities present on both sides; the perturbation was claimed
    against handle E1, but the diff's one 'modified' record actually names
    E2 (a defect in whatever built this pair silently attributed the change
    to the wrong entity). The identity check ("the single 'modified' MUST be
    the perturbed entity") must reject this -- exit 8, not exit 4: SOMETHING
    real was detected, it just cannot be reconstructed back to E1."""
    pre = _ir(
        _entity("E1", layer="0"),
        _entity("E2", layer="WALLS", geometry={"kind": "line", "start": [0.0, 0.0, 0.0], "end": [5.0, 0.0, 0.0]}),
    )
    post = _ir(
        _entity("E1", layer="0"),  # E1 (the claimed target) is UNCHANGED
        _entity("E2", layer="MOVED",  # E2 is the one that actually changed
               geometry={"kind": "line", "start": [0.0, 0.0, 0.0], "end": [5.0, 0.0, 0.0]}),
    )
    return cad_op_gate.check_mutation_pair(pre, post, "E1", "layer")


# --------------------------------------------------------------------------- #
# Manifest: (name, runner, expected_exit_code, expected_status)
# --------------------------------------------------------------------------- #

CASES = (
    ("field_absent", case_a_field_absent, cad_op_gate.EXIT_HOLLOW, cad_op_gate.STATUS_HOLLOW),
    ("bucket_collapse", case_b_bucket_collapse, cad_op_gate.EXIT_HOLLOW, cad_op_gate.STATUS_HOLLOW),
    ("key_injected", case_c_key_injected, cad_op_gate.EXIT_HOLLOW, cad_op_gate.STATUS_HOLLOW),
    ("coarse_quantized_invisible", case_d_coarse_quantized_invisible,
     cad_op_gate.EXIT_HOLLOW, cad_op_gate.STATUS_HOLLOW),
    ("wrong_entity_modified", case_e_wrong_entity_modified,
     cad_op_gate.EXIT_IRRECONSTRUCTIBLE, cad_op_gate.STATUS_IRRECONSTRUCTIBLE),
)


def run_all():
    """Return {name: result_dict} for every case (used by both the standalone
    self-test below and tests/unit's bridging test)."""
    return {name: runner() for name, runner, _exit, _status in CASES}


def _selftest() -> int:
    print("== F3-self: 5 hand-built adversarial gate fixtures ==")
    all_ok = True
    for name, runner, expected_exit, expected_status in CASES:
        result = runner()
        ok = (result.get("exit_code") == expected_exit and result.get("status") == expected_status)
        all_ok = all_ok and ok
        print("%-28s: status=%-16s exit=%s (expect %s/%d) %s"
             % (name, result.get("status"), result.get("exit_code"),
                expected_status, expected_exit, "OK" if ok else "MISMATCH"))
    print("RESULT                      : %s" % ("PASS" if all_ok else "FAIL"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(_selftest())
