#!/usr/bin/env python
"""mint_blank_seed.py -- mint fixtures/blank_seed.dwg ONCE [F4, WAVE-0].

Mints the CADOS blank-seed fixture from the Korean AutoCAD template
(``acad.dwt``, locale ``kor``) via the native ``transform.database.save_as``
op (m08c, family handler ``families/m08c_handlers.inc``), then captures the
template's default symbol-table content (layers/linetypes/text-styles/
dim-styles/viewports/app-ids/block-table-records/block-definitions/layouts/
xrefs/dictionaries) via ``inspect.database.graph`` so a later diff stage (F5,
``config/diff_scope.json`` ``full_database`` scope) can subtract these
template defaults from a real drawing's symbol tables instead of reporting
them as "added" content.

This script never parses a DWG itself: like ``cadctl.py``/``run_job.py`` it
shells out to the canonical router entrypoint (``tools/autocad-router.ps1``),
which drives the native ObjectARX/ObjectDBX job lane on a STAGED copy. The
Korean template (the true original) is never opened directly by accoreconsole
-- the router always copies it into its own ``staging/`` dir first; this
script also never overwrites an existing ``blank_seed.dwg`` unless ``--force``
is passed (the fixture is meant to be minted ONCE and then committed frozen).

Exit codes:
  0  truthful outcome: DONE, DONE_NEEDS_RUNTIME, or ALREADY_MINTED.
     A missing CAD runtime/template is reported honestly, never faked.
  1  BLOCKED -- a genuine script-side failure (e.g. the router itself errored
     while the runtime was supposedly available).

Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parent
FIXTURES_DIR = ROUTER_HOME / "fixtures"
DEFAULT_OUTPUT = FIXTURES_DIR / "blank_seed.dwg"

if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import run_job  # noqa: E402  (sibling helper, Lane B1 -- shells out to the router)

# The op that mints the fixture (staged write-copy only; families/m08c_handlers.inc
# refuses if output_path == input_path -- ORIGINAL_WRITE_FORBIDDEN).
MINT_OPERATION = "transform.database.save_as"
# The op that captures the "default symbol-table records" baseline (base op in
# AriadneNativeJob.cpp -- collectDatabaseGraph -- NOT m08c-specific; pure read).
BASELINE_OPERATION = "inspect.database.graph"

# acad.dwt (kor locale) install layout: <profile-root>/Autodesk/AutoCAD <ver>/R<rel>/kor/Template/acad.dwt.
# Version-agnostic: glob every installed AutoCAD version/release under the current
# user's profile and pick the highest, so an AutoCAD upgrade needs no code edit
# (mirrors Resolve-AcadEnginePath's version-agnostic resolution in autocad-router.ps1).
_TEMPLATE_GLOB = "AutoCAD */R*/kor/Template/acad.dwt"
_TEMPLATE_ENV_VAR = "ARIADNE_ACAD_KOR_TEMPLATE_PATH"


def _candidate_template_paths() -> list[Path]:
    home = Path.home()
    candidates: list[Path] = []
    for base in (home / "AppData" / "Local" / "Autodesk", home / "AppData" / "Roaming" / "Autodesk"):
        if not base.is_dir():
            continue
        candidates.extend(sorted(base.glob(_TEMPLATE_GLOB), reverse=True))
    return candidates


def find_template(explicit: str | None) -> Path | None:
    """Locate the Korean acad.dwt. Honest None if it cannot be found anywhere."""
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    env = os.environ.get(_TEMPLATE_ENV_VAR)
    if env:
        p = Path(env)
        if p.is_file():
            return p
    for cand in _candidate_template_paths():
        if cand.is_file():
            return cand
    return None


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_sha256_sidecar(dwg_path: Path) -> Path:
    digest = _sha256_file(dwg_path)
    sidecar = dwg_path.with_suffix(dwg_path.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {dwg_path.name}\n", encoding="ascii")
    return sidecar


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deferred_mint_command(template_hint: str, output: Path) -> str:
    return (
        '$env:PYTHONUTF8=1; python tools/mint_blank_seed.py '
        f'--template "{template_hint}" --output "{output}"'
    )


def _run_native_op(*, staged_input: str, operation: str, run_dir: Path,
                   write_mode: str, extra_job_fields: dict | None = None,
                   timeout: int = 180) -> dict:
    """One native-job round trip through the router; returns run_job's raw dict."""
    run_dir.mkdir(parents=True, exist_ok=True)
    job = {"schema": "ariadne.autocad_sdk_job.v1", "operation": operation, "write_mode": write_mode}
    if extra_job_fields:
        job.update(extra_job_fields)
    job_path = run_dir / f"job_{operation.replace('.', '_')}.json"
    job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_job.run_router_cad_job(
        staged_input, str(run_dir), operation,
        write_mode=write_mode, job_path=str(job_path), timeout=timeout,
    )


def _native_op_ok(run_result: dict) -> bool:
    envelope = run_result.get("envelope") or {}
    result = run_result.get("result") or {}
    if run_result.get("exit_code") != 0 or envelope.get("status") != "PASS":
        return False
    if not isinstance(result, dict) or not result:
        return False
    return "written" in result or "modelspace_entities" in result


def mint_blank_seed(*, template: str | None, output: Path, run_dir: Path,
                    baseline: Path | None = None, force: bool = False,
                    timeout: int = 180) -> dict:
    """Mint fixtures/blank_seed.dwg once; return a truthful structured result."""
    schema = "ariadne.mint_blank_seed.v1"
    baseline_target = baseline if baseline is not None else output.parent / f"{output.stem}.symbol_table_baseline.json"

    if output.exists() and not force:
        return {
            "schema": schema,
            "status": "ALREADY_MINTED",
            "detail": f"{output} already exists; pass --force to re-mint (the fixture is meant to be frozen).",
            "dwg_path": str(output),
            "sha256": _sha256_file(output),
        }

    template_path = find_template(template)
    if template_path is None:
        hint = template or f"$env:{_TEMPLATE_ENV_VAR} or {_TEMPLATE_GLOB} under %LOCALAPPDATA%/%APPDATA%\\Autodesk"
        return {
            "schema": schema,
            "status": "DONE_NEEDS_RUNTIME",
            "detail": "Korean acad.dwt template not found on this machine.",
            "deferred_command": _deferred_mint_command(hint, output),
            "template_glob": _TEMPLATE_GLOB,
        }

    mint_run_dir = run_dir / "mint"
    mint_result = _run_native_op(
        staged_input=str(template_path),
        operation=MINT_OPERATION,
        run_dir=mint_run_dir,
        write_mode="write_copy",
        extra_job_fields={"input_path": str(template_path).replace("\\", "/"),
                          "output_path": str(output).replace("\\", "/")},
        timeout=timeout,
    )
    if mint_result.get("error") or not _native_op_ok(mint_result) or not (mint_result.get("result") or {}).get("written"):
        return {
            "schema": schema,
            "status": "DONE_NEEDS_RUNTIME",
            "detail": "Live mint via the router did not complete (accoreconsole/DBX/CRX unavailable or errored).",
            "deferred_command": _deferred_mint_command(str(template_path), output),
            "router_error": mint_result.get("error"),
            "router_result": mint_result.get("result"),
            "stdout_path": mint_result.get("stdout_path"),
            "stderr_path": mint_result.get("stderr_path"),
        }

    if not output.exists():
        return {
            "schema": schema,
            "status": "BLOCKED",
            "detail": "Router reported written:true but output_path does not exist on disk.",
            "expected_path": str(output),
            "router_result": mint_result.get("result"),
        }

    # write_copy makes the router append _QSAVE after the native job (see
    # Invoke-CadJobRoute in autocad-router.ps1); saveAs() re-points the ACTIVE
    # document at output_path, so that trailing _QSAVE re-saves the SAME path a
    # second time in-session. AcDbDatabase::saveAs's bBakAndRename=true then
    # renames the first save to a stray "<stem>.bak" before the second save
    # lands as the final output_path bytes. Both saves are the identical 0-
    # entity template content (proven byte-identical at the decoded-graph level
    # in the F4 verification runs); the .bak is a discarded superseded copy,
    # never a second deliverable -- remove it so fixtures/ stays exactly the
    # declared fileset.
    stray_bak = output.with_suffix(".bak")
    cleaned_bak = False
    if stray_bak.exists():
        stray_bak.unlink()
        cleaned_bak = True

    sha256_path = _write_sha256_sidecar(output)

    baseline_run_dir = run_dir / "baseline"
    baseline_result = _run_native_op(
        staged_input=str(output),
        operation=BASELINE_OPERATION,
        run_dir=baseline_run_dir,
        write_mode="read",
        timeout=timeout,
    )
    baseline_ok = not baseline_result.get("error") and _native_op_ok(baseline_result)
    baseline_payload = baseline_result.get("result") if baseline_ok else None

    concern = None
    baseline_path = None
    if baseline_ok and baseline_payload is not None:
        modelspace_entities = baseline_payload.get("modelspace_entities")
        if modelspace_entities != 0:
            concern = f"blank_seed.dwg has {modelspace_entities} modelspace entities (expected 0)"
        try:
            source_dwg = str(output.relative_to(ROUTER_HOME)).replace("\\", "/")
        except ValueError:
            source_dwg = str(output)
        baseline_doc = {
            "schema": "ariadne.blank_seed_symbol_table_baseline.v1",
            "generated_at": _now_iso(),
            "source_dwg": source_dwg,
            "source_dwg_sha256": _sha256_file(output),
            "minted_from_template": str(template_path),
            "captured_via_operation": BASELINE_OPERATION,
            "note": (
                "Default symbol-table/graph content of a fresh drawing minted from the "
                "kor acad.dwt template. F5 (config/diff_scope.json, full_database scope) "
                "subtracts these {handle,name} records from a real drawing's symbol "
                "tables so template defaults are never reported as added content. "
                "modelspace_entities is expected to be 0."
            ),
            "baseline": baseline_payload,
        }
        baseline_target.parent.mkdir(parents=True, exist_ok=True)
        baseline_target.write_text(
            json.dumps(baseline_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        baseline_path = baseline_target
    else:
        concern = "baseline capture (inspect.database.graph) failed after a successful mint"

    return {
        "schema": schema,
        "status": "DONE",
        "detail": "Minted fixtures/blank_seed.dwg from the kor acad.dwt template via transform.database.save_as.",
        "dwg_path": str(output),
        "sha256_path": str(sha256_path),
        "sha256": _sha256_file(output),
        "baseline_path": str(baseline_path) if baseline_path else None,
        "modelspace_entities": (baseline_payload or {}).get("modelspace_entities"),
        "cleaned_bak_sidecar": cleaned_bak,
        "concern": concern,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--template", help="explicit path to the Korean acad.dwt (else auto-discovered)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="output .dwg path (default: fixtures/blank_seed.dwg)")
    parser.add_argument("--baseline", default=None,
                        help="output baseline JSON path (default: <output-stem>.symbol_table_baseline.json next to --output)")
    parser.add_argument("--run-dir", default=None, help="evidence directory for router stdout/stderr/job JSON")
    parser.add_argument("--force", action="store_true", help="re-mint even if the output already exists")
    parser.add_argument("--timeout", type=int, default=180, help="per-router-call timeout in seconds")
    args = parser.parse_args(argv)

    output = Path(args.output)
    baseline = Path(args.baseline) if args.baseline else None
    run_dir = Path(args.run_dir) if args.run_dir else ROUTER_HOME / "runs" / "mint_blank_seed"

    try:
        result = mint_blank_seed(
            template=args.template, output=output, run_dir=run_dir,
            baseline=baseline, force=args.force, timeout=args.timeout,
        )
    except Exception as exc:  # genuine script-side failure
        result = {
            "schema": "ariadne.mint_blank_seed.v1",
            "status": "BLOCKED",
            "detail": f"{type(exc).__name__}: {exc}",
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"DONE", "DONE_NEEDS_RUNTIME", "ALREADY_MINTED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
