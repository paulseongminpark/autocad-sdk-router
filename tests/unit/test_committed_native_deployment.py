"""Verify the exact native bundle committed under prebuilt/2027.

Synthetic manifest fixtures prove the verifier logic in other tests. This file
is deliberately different: it binds CI to the source, build recipe, marker,
and three PE images that would actually be consumed from this checkout.
"""
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cadctl  # noqa: E402
from verification.native_integrity import verify_committed_deployment  # noqa: E402


DEPLOY_DIR = ROOT / "prebuilt" / "2027"


def test_committed_native_deployment_matches_this_checkout() -> None:
    receipt = verify_committed_deployment(ROOT, DEPLOY_DIR)

    assert receipt["valid"] is True, receipt["errors"]
    assert receipt["errors"] == []
    assert len(receipt["artifact_paths"]) == 3


def test_native_source_identity_ignores_checkout_line_endings(tmp_path: Path) -> None:
    native = tmp_path / "src" / "Ariadne.AcadNative"
    dbx = tmp_path / "src" / "Ariadne.AcadNativeDbx"
    native.mkdir(parents=True)
    dbx.mkdir(parents=True)
    native_file = native / "native.cpp"
    dbx_file = dbx / "dbx.cpp"
    native_file.write_bytes(b"// native\n")
    dbx_file.write_bytes(b"// dbx\n")

    lf_inputs = cadctl._native_source_inputs(tmp_path)
    native_file.write_bytes(b"// native\r\n")
    dbx_file.write_bytes(b"// dbx\r\n")
    crlf_inputs = cadctl._native_source_inputs(tmp_path)

    assert lf_inputs == crlf_inputs
    assert cadctl._source_tree_digest(lf_inputs) == cadctl._source_tree_digest(
        crlf_inputs
    )


def test_build_recipe_identity_ignores_checkout_line_endings(tmp_path: Path) -> None:
    recipe = tmp_path / "tools" / "build_native_acad.ps1"
    recipe.parent.mkdir(parents=True)
    recipe.write_bytes(b"# recipe\n")
    lf_state = cadctl._build_recipe_state(tmp_path)

    recipe.write_bytes(b"# recipe\r\n")
    crlf_state = cadctl._build_recipe_state(tmp_path)

    assert lf_state == crlf_state
