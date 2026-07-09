from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NATIVE_SOURCE = ROOT / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"


def _native_source() -> str:
    return NATIVE_SOURCE.read_text(encoding="utf-8")


def _function_block(name: str) -> str:
    source = _native_source()
    start = source.index(f"static std::string {name}(")
    end = source.index("static std::string xrecordJson(", start)
    return source[start:end]


def test_xdata_contract_shape_for_synthetic_rows() -> None:
    entity = {
        "handle": "ABCD",
        "xdata": [
            {
                "app": "ARIADNE_APP",
                "rows": [
                    {"code": 1000, "value": "text"},
                    {"code": 1005, "value": "FF"},
                    {"code": 1040, "value": 1.25},
                    {"code": 1070, "value": 7},
                    {"code": 1010, "value": [1.0, 2.0, 3.0]},
                ],
            }
        ],
    }

    groups = entity["xdata"]
    assert groups
    for group in groups:
        assert set(group) == {"app", "rows"}
        assert isinstance(group["app"], str)
        assert group["rows"]
        for row in group["rows"]:
            assert set(row) == {"code", "value"}
            assert isinstance(row["code"], int)

    rows = groups[0]["rows"]
    assert isinstance(rows[1]["value"], str)
    assert isinstance(rows[2]["value"], float)
    assert isinstance(rows[3]["value"], int)
    assert rows[4]["value"] == [1.0, 2.0, 3.0]


def test_native_entity_xdata_emits_rows_not_legacy_items() -> None:
    block = _function_block("xdataBlocksJson")
    assert r'\"rows\"' in block
    assert r'\"items\"' not in block


def test_native_entity_xdata_is_pointer_gated_and_1005_stays_string() -> None:
    source = _native_source()
    assert "resbuf* xdata = pEnt->xData(nullptr);" in source
    assert "if (xdata != nullptr)" in source
    assert "arr << \",\\\"xdata\\\":\" << blocksJson;" in source
    assert "(code >= 1000 && code <= 1005)" in source
