from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
HANDLER = ROOT / "src" / "Ariadne.AcadNative" / "families" / "m08e_handlers.inc"


def handler_text() -> str:
    return HANDLER.read_text(encoding="utf-8")


def test_wipeout_loads_acismobj26_with_guard():
    text = handler_text()

    assert "acismobj26.dbx" in text
    assert "acrxDynamicLinker->loadModule" in text
    assert re.search(r"static bool \w*attempted\w* = false;", text)
    assert re.search(r"if \(!\w*attempted\w*\)", text)


def test_wipeout_has_distinct_fail_loud_errors():
    text = handler_text()

    assert '"WIPEOUT_MODULE_UNAVAILABLE"' in text
    assert '"WIPEOUT_BTR_APPEND_UNPROVEN"' in text
    assert text.index('"WIPEOUT_MODULE_UNAVAILABLE"') != text.index('"WIPEOUT_BTR_APPEND_UNPROVEN"')


def test_unsupported_kind_allow_list_includes_wipeout():
    text = handler_text()

    assert re.search(
        r"supports entity\.kind in \{[^}]*wipeout[^}]*\}",
        text,
    )


def test_wipeout_clip_boundary_is_closed_from_first_last_points():
    text = handler_text()

    assert "firstClipPoint = clipBoundary[0]" in text
    assert "lastClipPoint = clipBoundary[clipBoundary.length() - 1]" in text
    assert "clipBoundary.append(firstClipPoint)" in text
