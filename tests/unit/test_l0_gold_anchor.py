from __future__ import annotations

import math
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
E2_DIR = REPO_ROOT / "tools" / "e2"
if str(E2_DIR) not in sys.path:
    sys.path.insert(0, str(E2_DIR))

import l0_gold_anchor as anchor


W1, W2 = anchor.WALL_LAYERS


def _line(handle: str, layer: str, p0=(0.0, 0.0), p1=(1.0, 0.0), **extra):
    return {
        "handle": handle,
        "dxf_name": "LINE",
        "layer": layer,
        "class": "AcDbLine",
        "geometry": {"start": list(p0), "end": list(p1)},
        **extra,
    }


def _insert(handle: str, target: str, layer="0", point=(0.0, 0.0), **extra):
    return {
        "handle": handle,
        "dxf_name": "INSERT",
        "layer": layer,
        "class": "AcDbBlockReference",
        "block_record_handle": target,
        "geometry": {"position": list(point), "scale": [1.0, 1.0, 1.0], "rotation": 0.0},
        **extra,
    }


def _definition(handle: str, name: str, entities, origin=(0.0, 0.0)):
    return {
        "handle": handle,
        "name": name,
        "origin": list(origin),
        "entity_count": len(entities),
        "def_entities": entities,
    }


def _native(*, entities=None, definitions=None, btr_records=None, xrefs=None, layers=None, proxy_count=0):
    xref_values = list(xrefs or [])
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "coverage_level": "native_full",
        "source": {"sha256": "abc"},
        "entities": list(entities or []),
        "block_definitions": list(definitions or []),
        "xrefs": xref_values,
        "symbol_tables": {
            "layers": list(layers or [{"name": W1}, {"name": W2}]),
            "block_table_records": list(
                btr_records
                or [{"handle": "MS", "name": "*Model_Space", "origin": [0.0, 0.0]}]
            ),
        },
        "diagnostics": {
            "errors": [],
            "coverage": {
                "proxy_or_undecoded_count": proxy_count,
                "sections_present": ["xrefs"],
                "section_status": {"proxy_objects": "partial", "xrefs": "implemented"},
                "counts": {"xrefs": len(xref_values)},
            },
        },
    }


def test_nested_insert_transform_composition_is_applied_to_exact_wall_geometry():
    leaf = _definition("LEAF", "X-평면도(기본형)$0$leaf", [_line("L1", W1)])
    middle_insert = _insert("I1", "LEAF", point=(10.0, 0.0))
    middle_insert["geometry"]["scale"] = [2.0, 1.0, 1.0]
    middle_insert["geometry"]["rotation"] = math.pi / 2
    middle = _definition("MID", "middle", [middle_insert])
    native = _native(
        entities=[_insert("ROOT", "MID", point=(100.0, 0.0))],
        definitions=[leaf, middle],
        btr_records=[
            {"handle": "MS", "name": "*Model_Space", "origin": [0.0, 0.0]},
            {"handle": "LEAF", "name": "X-평면도(기본형)$0$leaf"},
            {"handle": "MID", "name": "middle"},
        ],
    )

    scoped, scope = anchor.scope_native_ir(native)
    projected, _ = anchor.wall_expansion_projection(scoped)
    adapted = anchor.graph_adapter.adapt(projected)
    no_clip, _ = anchor._drop_xclips(adapted)
    world = anchor.worldir_oracle.expand_world_ir(no_clip)

    assert scope["external_btr_handles"] == []
    assert world["status"] == "PASS"
    wall = [segment for segment in world["segments"] if segment["source_layer"] == W1]
    assert len(wall) == 1
    assert wall[0]["lineage_path"][-1]["insert_entity_handle"] == "I1"
    assert len(wall[0]["lineage_path"]) == 2
    assert wall[0]["p0_world"] == [110.0, 0.0]
    assert wall[0]["p1_world"] == [110.0, 2.0]
    assert anchor.world_layer_inventory(world)["recursive_insert_placements_total"] == 2


def test_bound_name_is_in_scope_but_explicit_external_xref_branch_is_excluded():
    bound = _definition("BND", "X-평면도(기본형)$0$bound", [_line("BOUND_LINE", W1)])
    external = _definition("EXT", "remote.dwg", [_line("EXT_LINE", W1)])
    native = _native(
        entities=[_insert("BOUND_REF", "BND"), _insert("EXT_REF", "EXT")],
        definitions=[bound, external],
        btr_records=[
            {"handle": "MS", "name": "*Model_Space", "origin": [0.0, 0.0]},
            {"handle": "BND", "name": "X-평면도(기본형)$0$bound", "is_xref": False},
            {"handle": "EXT", "name": "remote.dwg", "is_xref": True},
        ],
        xrefs=[{"handle": "EXT", "name": "remote.dwg", "status": "resolved"}],
    )

    scoped, scope = anchor.scope_native_ir(native)
    inventory = anchor.layer_inventory(scoped)
    projected, _ = anchor.wall_expansion_projection(scoped)
    adapted = anchor.graph_adapter.adapt(projected)
    no_clip, _ = anchor._drop_xclips(adapted)
    world = anchor.worldir_oracle.expand_world_ir(no_clip)

    assert scope["name_based_inference_used"] is False
    assert scope["external_block_definitions_excluded"] == 1
    assert scope["external_insert_edges_excluded"] == 1
    assert [definition["handle"] for definition in scoped["block_definitions"]] == ["BND"]
    assert inventory["layers"][0]["internal_block_template_count"] == 1
    assert len([segment for segment in world["segments"] if segment["source_layer"] == W1]) == 1


def test_wall_layer_matching_is_exact_for_korean_and_dollar_names():
    native = _native(
        definitions=[
            _definition(
                "B1",
                "internal",
                [
                    _line("W1_EXACT", W1),
                    _line("W1_NEAR", W1 + "-suffix"),
                    _line("W2_EXACT", W2),
                ],
            )
        ],
        btr_records=[
            {"handle": "MS", "name": "*Model_Space", "origin": [0.0, 0.0]},
            {"handle": "B1", "name": "internal"},
        ],
        layers=[{"name": W1}, {"name": W2}, {"name": W1 + "-suffix"}],
    )

    inventory = anchor.layer_inventory(native)

    assert inventory["matching"] == "exact_utf8_string"
    assert inventory["both_layers_present_exactly_once"] is True
    assert inventory["layers"][0]["internal_block_template_count"] == 1
    assert inventory["layers"][1]["internal_block_template_count"] == 1
    assert inventory["layers"][0]["internal_block_templates_by_dxf_name"] == {"LINE": 1}


def test_proxy_custom_and_unresolved_xref_accounting_is_explicit():
    native = _native(
        entities=[
            {
                "handle": "P1",
                "dxf_name": "PROXYENTITY",
                "layer": "0",
                "class": "AcDbProxyEntity",
                "geometry": {},
            },
            {
                "handle": "C1",
                "dxf_name": "CUSTOM",
                "layer": "0",
                "class": "VendorWallObject",
                "geometry": {},
            },
        ],
        xrefs=[{"name": "missing-handle.dwg", "status": "unresolved"}],
        proxy_count=2,
    )
    _, scope = anchor.scope_native_ir(native)
    accounting = anchor.incomplete_object_accounting(
        native,
        {"status": "PARTIAL", "adapter_ledger": {"explicitly_excluded_entity_templates": 2}},
        scope,
    )

    assert scope["scope_identity_resolved"] is False
    assert len(scope["unresolved_scope_identity_records"]) == 1
    assert accounting["native_proxy_or_undecoded_count"] == 2
    assert accounting["proxy_like_entity_templates"] == {"PROXYENTITY|AcDbProxyEntity": 1}
    assert accounting["non_acdb_custom_entity_class_counts"] == {"VendorWallObject": 1}
    assert accounting["full_native_templates_outside_adapter_surface"] == {
        "CUSTOM": 1,
        "PROXYENTITY": 1,
    }
    assert accounting["adapter_explicitly_excluded_entity_templates"] == 2


def test_xref_scope_requires_an_observed_present_implemented_empty_section():
    _, scope = anchor.scope_native_ir(_native(xrefs=[]))

    observation = scope["xref_section_observation"]
    assert scope["scope_identity_resolved"] is True
    assert observation["key_present"] is True
    assert observation["json_type"] == "list"
    assert observation["coverage_section_status"] == "implemented"
    assert observation["coverage_count"] == 0
    assert observation["observed_present_empty"] is True
    assert observation["resolution_reasons"] == []


def test_xref_scope_fails_closed_when_section_is_absent():
    native = _native(xrefs=[])
    del native["xrefs"]

    _, scope = anchor.scope_native_ir(native)

    assert scope["scope_identity_resolved"] is False
    assert "XREF_SECTION_ABSENT" in scope["scope_identity_resolution_reasons"]
    assert "XREF_SECTION_COVERAGE_UNOBSERVED" not in scope["scope_identity_resolution_reasons"]


def test_xref_scope_fails_closed_when_section_is_null_or_wrong_type():
    for invalid_value in (None, {"handle": "EXT"}):
        native = _native(xrefs=[])
        native["xrefs"] = invalid_value

        _, scope = anchor.scope_native_ir(native)

        assert scope["scope_identity_resolved"] is False
        assert "XREF_SECTION_NOT_LIST" in scope["scope_identity_resolution_reasons"]
        assert scope["xref_section_observation"]["observed_present_empty"] is False


def test_xref_scope_fails_closed_when_coverage_is_unobserved():
    native = _native(xrefs=[])
    coverage = native["diagnostics"]["coverage"]
    coverage.pop("sections_present")
    coverage["section_status"].pop("xrefs")
    coverage["counts"].pop("xrefs")

    _, scope = anchor.scope_native_ir(native)

    assert scope["scope_identity_resolved"] is False
    assert set(scope["scope_identity_resolution_reasons"]) >= {
        "XREF_SECTION_COVERAGE_UNOBSERVED",
        "XREF_SECTION_COVERAGE_NOT_IMPLEMENTED",
        "XREF_SECTION_COUNT_UNOBSERVED",
    }


def test_structural_wall_insert_terminal_accounting_conserves_every_omission():
    leaf = _definition("LEAF", "leaf", [_line("WALL", W1)])
    path = _definition(
        "PATH",
        "path",
        [
            _insert("PATH_TO_LEAF", "LEAF"),
            _insert("W1_KEEP", "LEAF", layer=W1),
        ],
    )
    omitted_w1 = _definition("OMIT_W1", "omitted-w1", [_insert("W1_OMIT", "OTHER", layer=W1)])
    omitted_w2 = _definition("OMIT_W2", "omitted-w2", [_insert("W2_OMIT", "OTHER", layer=W2)])
    other = _definition("OTHER", "other", [_line("OTHER_LINE", "0")])
    native = _native(
        entities=[_insert("ROOT", "PATH")],
        definitions=[leaf, path, omitted_w1, omitted_w2, other],
        btr_records=[
            {"handle": "MS", "name": "*Model_Space", "origin": [0.0, 0.0]},
            {"handle": "LEAF", "name": "leaf"},
            {"handle": "PATH", "name": "path"},
            {"handle": "OMIT_W1", "name": "omitted-w1"},
            {"handle": "OMIT_W2", "name": "omitted-w2"},
            {"handle": "OTHER", "name": "other"},
        ],
    )

    scoped, _ = anchor.scope_native_ir(native)
    _, receipt = anchor.wall_expansion_projection(scoped)

    assert receipt["raw_structural_wall_insert_templates_by_layer"] == {W1: 2, W2: 1}
    assert receipt["retained_structural_wall_insert_templates_by_layer"] == {W1: 1}
    assert receipt["omitted_structural_wall_inserts_by_layer"] == {W1: 1, W2: 1}
    assert receipt["omitted_structural_wall_inserts_no_label_inheritance"] == 2
    assert receipt["structural_wall_insert_terminal_accounting"] == {
        "raw_template_count": 3,
        "retained_template_count": 1,
        "omitted_template_count": 2,
        "terminal_disposition_count": 2,
        "conservation_ok": True,
    }
    dispositions = receipt["omitted_structural_wall_insert_terminal_dispositions"]
    assert {(item["layer"], item["handle"]) for item in dispositions} == {(W1, "W1_OMIT"), (W2, "W2_OMIT")}
    assert all(item["reason"] == "NO_LABEL_INHERITANCE" for item in dispositions)
    assert all(item["owner_definition_handle"] in {"OMIT_W1", "OMIT_W2"} for item in dispositions)
    assert all(item["target_block_record_handle"] == "OTHER" for item in dispositions)
    assert all(item["target_reachable_for_label_scope"] is False for item in dispositions)
