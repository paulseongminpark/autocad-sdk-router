from tools.ir_to_patch import build_patch_from_ir
from tools.patch_ops.xdata import (
    REGAPP_OP,
    REASON_DANGLING_1005,
    REASON_UNBALANCED_1002,
    XDATA_OP,
    build_xdata_ops,
)


def _line(handle):
    return {
        "handle": handle,
        "layer": "0",
        "geometry": {
            "kind": "line",
            "start": [0, 0, 0],
            "end": [1, 0, 0],
        },
    }


def test_xdata_1005_remaps_through_handle_map():
    ir = {
        "entities": [
            {
                **_line("A"),
                "xdata": [
                    {"app": "APP", "rows": [
                        {"code": 1000, "value": "kept"},
                        {"code": 1005, "value": "B"},
                    ]},
                ],
            }
        ],
    }

    ops, deferred = build_xdata_ops(ir, {"A": "NA", "B": "NB"})

    assert deferred == []
    assert ops[0] == {"operation": REGAPP_OP, "args": {"app": "APP"}}
    assert ops[1]["operation"] == XDATA_OP
    assert ops[1]["args"] == {
        "handle": "NA",
        "app_name": "APP",
        "values": [
            {"code": 1000, "value": "kept"},
            {"code": 1005, "value": "NB"},
        ],
    }


def test_dangling_1005_row_is_dropped_and_group_is_kept():
    ir = {
        "entities": [
            {
                **_line("A"),
                "xdata": [
                    {"app": "APP", "rows": [
                        {"code": 1000, "value": "kept"},
                        {"code": 1005, "value": "MISSING"},
                    ]},
                ],
            }
        ],
    }

    ops, deferred = build_xdata_ops(ir, {"A": "NA"})

    assert [op["operation"] for op in ops] == [REGAPP_OP, XDATA_OP]
    assert ops[1]["args"]["values"] == [{"code": 1000, "value": "kept"}]
    assert deferred[0]["reason"] == REASON_DANGLING_1005
    assert deferred[0]["value"] == "MISSING"


def test_unbalanced_1002_defers_whole_app_group():
    ir = {
        "entities": [
            {
                **_line("A"),
                "xdata": [
                    {"app": "APP", "rows": [
                        {"code": 1002, "value": "}"},
                        {"code": 1000, "value": "not emitted"},
                    ]},
                ],
            }
        ],
    }

    ops, deferred = build_xdata_ops(ir, {"A": "NA"})

    assert [op["operation"] for op in ops] == [REGAPP_OP]
    assert deferred == [{
        "index": 0,
        "handle": "A",
        "xdata_index": 0,
        "app": "APP",
        "reason": REASON_UNBALANCED_1002,
    }]


def test_include_xdata_appends_regapps_before_xdata_after_entity_ops():
    e0 = _line("A")
    e0["xdata"] = [
        {"app": "APP1", "rows": [{"code": 1000, "value": "a"}]},
        {"app": "APP2", "rows": [{"code": 1005, "value": "B"}]},
    ]
    e1 = _line("B")
    e1["xdata"] = [
        {"app": "APP1", "rows": [{"code": 1000, "value": "b"}]},
    ]

    patch, deferred = build_patch_from_ir(
        {"entities": [e0, e1]}, {"staged_path": "", "original_path": ""},
        "p4b", include_xdata=True)

    assert deferred == []
    names = [op["operation"] for op in patch["operations"]]
    assert names == [
        "create_line",
        "create_line",
        REGAPP_OP,
        REGAPP_OP,
        XDATA_OP,
        XDATA_OP,
        XDATA_OP,
    ]
    assert [op["args"]["app"] for op in patch["operations"][2:4]] == ["APP1", "APP2"]
    assert patch["operations"][5]["args"]["values"] == [{"code": 1005, "value": "e1"}]


def test_xdata_replay_is_default_off():
    e0 = _line("A")
    e0["xdata"] = [{"app": "APP", "rows": [{"code": 1000, "value": "a"}]}]

    patch, deferred = build_patch_from_ir(
        {"entities": [e0]}, {"staged_path": "", "original_path": ""},
        "default-off")

    assert deferred == []
    assert [op["operation"] for op in patch["operations"]] == ["create_line"]
