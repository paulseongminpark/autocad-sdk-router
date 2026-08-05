#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAD OS Layer F3 TEST -- tools/e2/meta/transforms_struct.py's layer rename
must not double-process a single real layer under two different-case names
(AUDIT.md T2/T3, #54/#58/#60).

Intent (WHY):
  ezdxf's layer table is case-insensitive-unique (``Table.has_entry`` keys
  on ``name.lower()``), but ``_collect_layer_names`` gathered both the
  table entry's own name (``layer.dxf.name``) and every entity's literal
  layer-reference string (``e.dxf.layer``) into a case-SENSITIVE Python
  ``set``. When those two strings differ only in case (reproduced directly
  in-memory below -- no save/reload needed), the real single layer shows up
  as TWO entries in the resulting ``layer_map``. ``_rename_layer_table``
  then tries to ``duplicate_entry``/``remove`` the same real table entry
  twice; the second call fails on an already-removed entry
  (``ezdxf.DXFTableEntryError``, reproduced against this session's installed
  ezdxf before writing this test). Separately, even with a correct
  ``layer_map``, ``_remap_entity_layers`` looked its ``old`` key up with a
  case-sensitive ``dict.get`` -- an entity literal that differs in case from
  the layer_map's key would silently NOT get remapped.

Discoverable by pytest and ``python -m unittest discover -s tests``.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
for _p in (_REPO, os.path.join(_REPO, "tools", "e2", "meta")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ezdxf  # noqa: E402 -- router-development unit test, not real-drawing I/O
import transforms_struct as ts  # noqa: E402


def _doc_with_case_divergent_layer() -> "ezdxf.document.Drawing":
    """One real layer, but its table entry ("WALL") and the one entity that
    references it ("wall") differ only in case -- ezdxf permits this (no
    validation at attribute-assignment time); AUDIT.md's T3 section observed
    the same divergence surviving a save+reload round trip on real files."""
    doc = ezdxf.new("R2010")
    doc.layers.add("WALL")
    msp = doc.modelspace()
    msp.add_line((0.0, 0.0), (1.0, 1.0), dxfattribs={"layer": "wall"})
    return doc


class TestCollectLayerNamesCaseInsensitiveDedupe(unittest.TestCase):
    def test_table_entry_and_entity_literal_differing_only_in_case_collapse(self):
        doc = _doc_with_case_divergent_layer()
        names = ts._collect_layer_names(doc)
        wall_variants = [n for n in names if n.casefold() == "wall"]
        self.assertEqual(
            len(wall_variants), 1,
            f"'WALL' (table) and 'wall' (entity literal) are the SAME real "
            f"layer but _collect_layer_names returned them as separate "
            f"names: {names}",
        )


class TestRenameLayerTableCaseDuplicateKeys(unittest.TestCase):
    def test_case_duplicate_layer_map_keys_apply_once_without_exception(self):
        doc = ezdxf.new("R2010")
        doc.layers.add("WALL")
        # A layer_map carrying two keys that name the SAME real ezdxf table
        # entry under different case -- exactly what a case-sensitive
        # _collect_layer_names could hand to _build_layer_map.
        layer_map = {"WALL": "L001", "wall": "L002"}
        try:
            ts._rename_layer_table(doc, layer_map)
        except ezdxf.DXFTableEntryError as exc:  # pragma: no cover - the red failure
            self.fail(
                f"_rename_layer_table raised {exc!r} processing the second "
                "case-duplicate key against an already-removed table entry"
            )
        final_names = {layer.dxf.name for layer in doc.layers}
        self.assertFalse(
            "WALL" in final_names or "wall" in final_names,
            f"the real WALL layer should have been renamed exactly once: {final_names}",
        )
        applied = final_names & {"L001", "L002"}
        self.assertEqual(
            len(applied), 1,
            f"expected exactly ONE of L001/L002 applied (single real layer, "
            f"processed once), got {applied}",
        )


class TestRenameLayersEndToEnd(unittest.TestCase):
    def test_entity_literal_case_variant_still_remapped(self):
        """Even when the caller's layer_map key is cased like the TABLE
        entry ("WALL"), an entity whose literal layer string is cased
        differently ("wall") must still be remapped -- a case-sensitive
        dict.get on the entity's literal would silently skip it."""
        with tempfile.TemporaryDirectory(prefix="s5b_casefold_") as td:
            td_path = Path(td)
            src = td_path / "fixture.dxf"
            doc = _doc_with_case_divergent_layer()
            doc.saveas(str(src))

            dst = td_path / "renamed.dxf"
            layer_map = ts.rename_layers(src, dst, "anonymize", seed=1)

            doc_r = ezdxf.readfile(str(dst))
            lines = [e for e in doc_r.modelspace() if e.dxftype() == "LINE"]
            self.assertEqual(len(lines), 1)
            remapped_layer = str(lines[0].dxf.layer)
            self.assertNotEqual(
                remapped_layer.casefold(), "wall",
                f"entity's case-variant layer literal 'wall' was not "
                f"remapped by layer_map={layer_map} (still {remapped_layer!r})",
            )
            self.assertTrue(
                doc_r.layers.has_entry(remapped_layer),
                f"remapped entity layer {remapped_layer!r} has no matching "
                "table entry",
            )


if __name__ == "__main__":
    unittest.main()
