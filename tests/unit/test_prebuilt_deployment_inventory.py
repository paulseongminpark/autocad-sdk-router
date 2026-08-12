"""Keep the committed AutoCAD 2027 deployment surface singular."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOY_DIR = ROOT / "prebuilt" / "2027"
EXPECTED_FILES = {
    Path("Ariadne.AcadNative.arx"),
    Path("Ariadne.AcadNative.crx"),
    Path("Ariadne.AcadNativeDbx.dbx"),
    Path("native_deployment_manifest.json"),
}


def test_prebuilt_2027_contains_only_the_current_deployment_bundle() -> None:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "ls-files",
            "-z",
            "--",
            DEPLOY_DIR.relative_to(ROOT).as_posix(),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    files = {
        Path(path.decode("utf-8")).relative_to(DEPLOY_DIR.relative_to(ROOT))
        for path in result.stdout.split(b"\0")
        if path
    }

    assert files == EXPECTED_FILES
