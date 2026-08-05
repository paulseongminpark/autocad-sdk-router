#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T1 (#49) regression: ezdxf's add_wipeout() silently resets dxf.layer to
"0" -- Wipeout.set_masking_area() calls update_dxf_attribs(DEFAULT_ATTRIBS),
where DEFAULT_ATTRIBS["layer"] == "0", AFTER new_entity() already applied the
caller's dxfattribs. gen2.py's DrawingBuilder._add_profile_entity intends
every filler entity (including WIPEOUT) to land on "PROFILE-FILL"
(see LAYER_COLORS / the "layer = 'PROFILE-FILL'" assignment)."""
from __future__ import annotations

import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_GEN2_DIR = os.path.join(_REPO, "tools", "e2", "gen2")
for _p in (_GEN2_DIR,):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gen2  # noqa: E402


def test_wipeout_filler_entity_lands_on_profile_fill_layer():
    builder = gen2.DrawingBuilder(
        tier="S", seed=1, entity_ratios={"WIPEOUT": 1.0},
        entity_count=1, calibration_pairs=0,
    )
    builder._add_profile_entity("WIPEOUT", 0)

    wipeouts = [e for e in builder.msp if e.dxftype() == "WIPEOUT"]
    assert len(wipeouts) == 1, "expected exactly one WIPEOUT entity"
    assert wipeouts[0].dxf.layer == "PROFILE-FILL", (
        "WIPEOUT landed on layer %r instead of PROFILE-FILL -- ezdxf's "
        "add_wipeout()/set_masking_area() resets dxf.layer to '0' after "
        "creation; gen2.py must set .dxf.layer AFTER the add_wipeout() call"
        % (wipeouts[0].dxf.layer,)
    )
