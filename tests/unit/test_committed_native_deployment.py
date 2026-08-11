"""Verify the exact native bundle committed under prebuilt/2027.

Synthetic manifest fixtures prove the verifier logic in other tests. This file
is deliberately different: it binds CI to the source, build recipe, marker,
and three PE images that would actually be consumed from this checkout.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cadctl  # noqa: E402


DEPLOY_DIR = ROOT / "prebuilt" / "2027"
MARKER = DEPLOY_DIR / "native_deployment_manifest.json"


def test_committed_native_deployment_matches_this_checkout() -> None:
    assert MARKER.is_file()
    assert cadctl._path_reparse_error(DEPLOY_DIR) is None
    assert cadctl._path_reparse_error(MARKER) is None
    manifest = json.loads(MARKER.read_text(encoding="utf-8-sig"))

    assert manifest["schema"] == "ariadne.cad_os.native_deployment_manifest.v1"
    assert manifest["schema_version"] == 1
    assert manifest["claim_scope"] == "release_build_integrity_bundle"
    assert manifest["deployment_state"] == "committed"
    assert manifest["committed"] is True
    assert manifest["build_target"] == "Rebuild"
    assert manifest["configuration"] == "Release"
    assert manifest["platform"] == "x64"

    recipe = cadctl._build_recipe_state(ROOT)
    assert recipe["available"] is True
    assert manifest["build_recipe"] == {
        "path": recipe["path"],
        "sha256": recipe["sha256"],
    }

    source_inputs = cadctl._native_source_inputs(ROOT)
    assert manifest["source_tree_digest"] == cadctl._source_tree_digest(source_inputs)

    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    expected_leaves = set(cadctl.DISPLAY_MEMBERSHIP_REQUIRED_ARTIFACTS)
    assert {item["leaf"] for item in artifacts} == expected_leaves
    assert len(artifacts) == len(expected_leaves)

    for item in artifacts:
        path = DEPLOY_DIR / item["leaf"]
        assert item["current"] is True
        assert item["exists"] is True
        assert path.is_file()
        assert cadctl._path_reparse_error(path) is None
        assert item["bytes"] == path.stat().st_size
        assert item["sha256"] == cadctl._sha256_file(path)

        observed = cadctl._pe64_image_state(path)
        recorded = item["pe_verification"]
        assert observed["verified"] is True
        for key in (
            "verified",
            "format",
            "machine",
            "minimum_bytes",
            "pe_header_offset",
            "section_count",
            "optional_header_bytes",
        ):
            assert recorded[key] == observed[key]


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
