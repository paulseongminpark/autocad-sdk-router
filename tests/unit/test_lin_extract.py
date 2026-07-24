from pathlib import Path

from tools.lin_synthesis import synthesize_lin_file


ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "src" / "Ariadne.AcadNative" / "AriadneNativeJob.cpp"


def test_synthesis_accepts_extractor_dash_schema(tmp_path):
    out_path = tmp_path / "batch.lin"
    rows = [
        {
            "name": "CENTER",
            "description": "Center ____ _ ____ _ ____",
            "pattern_length": 2.0,
            "is_scaled_to_fit": False,
            "dashes": [
                {"length": 1.25},
                {"length": -0.25},
                {"length": 0.0},
            ],
        }
    ]

    result = synthesize_lin_file(rows, out_path)

    assert result == {"written": ["CENTER"], "deferred": []}
    assert out_path.read_text(encoding="utf-8") == (
        "*CENTER,Center ____ _ ____ _ ____\n"
        "A,1.25,-0.25,0\n"
    )


def test_synthesis_defers_extractor_shape_marker(tmp_path):
    out_path = tmp_path / "batch.lin"
    rows = [
        {
            "name": "SHAPED",
            "description": "Shape segment",
            "pattern_length": 0.5,
            "is_scaled_to_fit": True,
            "dashes": [
                {
                    "length": 0.25,
                    "shape": True,
                    "shape_number": 42,
                    "shape_style_handle": "2A",
                    "shape_scale": 1.0,
                    "shape_rotation": 0.0,
                    "shape_is_ucs_oriented": False,
                }
            ],
        }
    ]

    result = synthesize_lin_file(rows, out_path)

    assert result == {
        "written": [],
        "deferred": [
            {
                "name": "SHAPED",
                "reason": "shape segments are not supported in lin_synthesis v1",
            }
        ],
    }
    assert out_path.read_text(encoding="utf-8") == ""


def test_native_linetype_extractor_emits_p5b_schema():
    source = NATIVE.read_text(encoding="utf-8")

    for token in (
        '\\"pattern_length\\"',
        "patternLength()",
        '\\"is_scaled_to_fit\\"',
        "isScaledToFit()",
        '\\"dashes\\"',
        '\\"length\\"',
        "dashLengthAt(di)",
        "textAt(di, textRaw) == Acad::eOk",
        '\\"text\\"',
        "shapeStyleAt(di)",
        '\\"shape\\"',
        '\\"shape_number\\"',
        "shapeNumberAt(di)",
        '\\"shape_style_handle\\"',
        "handleOfId(shapeStyleId)",
        '\\"shape_scale\\"',
        "shapeScaleAt(di)",
        '\\"shape_rotation\\"',
        "shapeRotationAt(di)",
        '\\"shape_is_ucs_oriented\\"',
        "shapeIsUcsOrientedAt(di)",
    ):
        assert token in source

    assert "if (numDashes > 0)" in source
