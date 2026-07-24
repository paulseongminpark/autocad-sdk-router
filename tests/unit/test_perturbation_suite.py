#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for the N1 IR perturbation suite (tools/semantic_gates/perturbation.py)."""

from __future__ import annotations

import copy
import os
import sys

import pytest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.semantic_gates import perturbation  # noqa: E402
from tools import blockdef_diff  # noqa: E402


def _entity(handle, kind, *, layer="0", **geometry):
    payload = {"kind": kind}
    payload.update(geometry)
    return {"handle": handle, "layer": layer, "geometry": payload}


def _block(name, *entities):
    return {"name": name, "handle": "H_%s" % name, "def_entities": list(entities)}


def _make_ir():
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "block_definitions": [
            _block(
                "HINGE",
                _entity("H1", "line", start=[0.0, 0.0, 0.0], end=[1.0, 1.0, 0.0]),
            ),
            _block(
                "DOOR",
                _entity("D1", "line", start=[0.0, 0.0, 0.0], end=[10.0, 0.0, 0.0]),
                _entity("D2", "circle", center=[5.0, 5.0, 0.0], radius=2.0),
                _entity("D3", "block_reference", block_name="HINGE", position=[1.0, 1.0, 0.0]),
            ),
        ],
    }


def test_catalog_lists_all_five_kinds():
    assert perturbation.catalog() == [
        "entity_shift",
        "entity_delete",
        "entity_duplicate",
        "def_rename",
        "layer_swap",
    ]


@pytest.mark.parametrize("kind", perturbation.PERTURBATION_KINDS)
def test_each_kind_produces_a_different_doc(kind):
    ir = _make_ir()
    perturbed = perturbation.perturb(ir, kind)

    assert perturbed != ir


def test_perturb_does_not_modify_the_original_doc():
    ir = _make_ir()
    baseline = copy.deepcopy(ir)

    perturbation.perturb(ir, "entity_shift")

    assert ir == baseline


def test_perturb_rejects_unknown_kind():
    ir = _make_ir()

    with pytest.raises(ValueError):
        perturbation.perturb(ir, "not_a_real_kind")


@pytest.mark.parametrize(
    "kind", ["entity_shift", "entity_delete", "entity_duplicate", "layer_swap"]
)
def test_blockdef_diff_reacts_to_damage_kinds(kind):
    ir = _make_ir()

    results = {row["kind"]: row for row in perturbation.run_suite(ir)}

    assert results[kind]["blockdef_diff_reacts"] is True
    assert results[kind]["fraction_delta"] is not None


@pytest.mark.parametrize("kind", ["entity_shift", "entity_delete", "layer_swap"])
def test_blockdef_diff_fraction_drops_when_an_existing_entity_is_damaged(kind):
    # entity_duplicate reacts via an *added* extra (see test above) without
    # shrinking interior_diff0_fraction, since that fraction only measures
    # whether A's population survived in B -- it is not penalized by B
    # gaining unmatched extras. These three kinds all damage an EXISTING
    # entity, so A's population provably shrinks.
    ir = _make_ir()

    results = {row["kind"]: row for row in perturbation.run_suite(ir)}

    assert results[kind]["fraction_delta"] > 0.0


def test_def_rename_preserves_interior_fraction_under_name_map():
    ir = _make_ir()
    old_name = ir["block_definitions"][0]["name"]

    perturbed = perturbation.perturb(ir, "def_rename")
    new_name = perturbed["block_definitions"][0]["name"]

    assert new_name != old_name

    report = blockdef_diff.diff_block_definitions(
        ir, perturbed, name_map={old_name: new_name}
    )

    assert report["totals"]["interior_diff0_fraction"] == 1.0
    assert report["totals"]["diff0_total"] == report["totals"]["a_entity_total"]
