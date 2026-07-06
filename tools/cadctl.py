#!/usr/bin/env python
"""cadctl.py -- the CAD OS Layer control surface (Lane B1).

`Cad` is a thin, truthful orchestrator over the existing AutoCAD SDK router. It
never parses a DWG itself: it stages a COPY of an input drawing under
staging/golden/<ts>/ and drives tools/autocad-router.ps1 (ObjectARX ->
ObjectDBX -> AutoLISP) to produce a dwg_geometry_extract.v1 JSON, then normalizes
that to the engine-neutral ariadne.dwg_graph_ir.v1 via tools/ir_builder.py.

Invariants honored here:
  * Original DWG files are READ-ONLY. inspect() always operates on a staged copy.
  * No-fake-success. If the router extraction is unavailable/fails, or a required
    sibling module (ir_builder / sqlite_ir_store / validator) is absent, the
    method returns a truthful status (not_implemented / unavailable / partial /
    blocked) -- never a faked ok.
  * status() READS the published router status JSON read-only; it never runs
    `-Action status`.
  * Every external command's stdout + stderr + exit code is captured into out_dir.

Standard library only (json, sqlite3 are stdlib). Config/status JSON on this box
is BOM-prefixed -> read with encoding="utf-8-sig".
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parent
CONFIG_DIR = ROUTER_HOME / "config"
REPORTS_DIR = ROUTER_HOME / "reports"
STAGING_GOLDEN_DIR = ROUTER_HOME / "staging" / "golden"

STATUS_JSON = REPORTS_DIR / "autocad_router_status_latest.json"
OPERATIONS_V2 = CONFIG_DIR / "operations.v2.json"

# Ensure sibling tools/*.py are importable when cadctl is imported by path.
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import run_job  # noqa: E402  (sibling helper, Lane B1)
import normalize_result  # noqa: E402  (sibling helper, Lane B1)
import route_select  # noqa: E402  (sibling helper, Lane B1)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _load_json_bom(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _sha256_head(path: Path, n: int = 16) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:n].upper()


def _import_optional(module_name: str):
    """Import a sibling module that another lane owns; return (mod, error_str|None)."""
    try:
        mod = __import__(module_name)
        return mod, None
    except Exception as exc:  # ImportError or downstream error in that module
        return None, f"{type(exc).__name__}: {exc}"


class Cad:
    """The cadctl control surface. All methods return plain dicts (stateless)."""

    def __init__(self, router_home: Path | str = ROUTER_HOME):
        self.router_home = Path(router_home)
        self.config_dir = self.router_home / "config"
        self.reports_dir = self.router_home / "reports"
        self.status_json = self.reports_dir / "autocad_router_status_latest.json"
        self.staging_golden = self.router_home / "staging" / "golden"

    # ------------------------------------------------------------------ status
    def status(self) -> dict:
        """Read the published router status JSON read-only and normalize it.

        DOES NOT run `-Action status`. If the published file is missing, report
        that truthfully (status='unavailable') rather than spawning a probe.
        """
        if not self.status_json.exists():
            return {
                "schema": "ariadne.cadctl.status.v1",
                "status": "unavailable",
                "reason": f"published router status JSON not found: {self.status_json}",
                "status_json_path": str(self.status_json),
                "route_count": 0,
                "available_count": 0,
                "native_available": False,
            }
        try:
            raw = _load_json_bom(self.status_json)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.status.v1",
                "status": "error",
                "reason": f"failed to parse status JSON: {type(exc).__name__}: {exc}",
                "status_json_path": str(self.status_json),
            }
        native_modules = raw.get("native_modules") or {}
        native_status = str(native_modules.get("status", "")).upper()
        routes = raw.get("routes") or []
        out = {
            "schema": "ariadne.cadctl.status.v1",
            "status": "ok",
            "router_status": raw.get("status"),
            "router_status_schema": raw.get("schema"),
            "status_json_path": str(self.status_json),
            "router_home": raw.get("router_home"),
            "timestamp": raw.get("timestamp"),
            "route_count": raw.get("route_count", len(routes)),
            "available_count": raw.get(
                "available_count",
                sum(1 for r in routes if r.get("available")),
            ),
            "unavailable": list(raw.get("unavailable", []) or []),
            "native_available": native_status == "PASS",
            "native_modules_status": native_modules.get("status"),
            "routes": [
                {"route": r.get("route"), "available": bool(r.get("available")),
                 "engine": r.get("engine")}
                for r in routes
            ],
            "note": "read-only snapshot of the router-published status; not a live probe.",
        }
        reg = self.registry_coverage()
        if reg.get("status") == "ok":
            by_status = reg.get("computed_by_status") or {}
            out["registry"] = {
                "schema": reg.get("registry_schema"),
                "version": reg.get("registry_version"),
                "operation_count": reg.get("operation_count"),
                "implemented": by_status.get("implemented", 0),
                "wired": by_status.get("wired", 0),
                "stub": by_status.get("stub", 0),
                "catalogued": by_status.get("catalogued", 0),
                "blocked": by_status.get("blocked", 0),
                "deprecated": by_status.get("deprecated", 0),
                "unknown": reg.get("unknown_count", 0),
                "consistent": reg.get("consistent"),
            }
        else:
            out["registry"] = {
                "status": reg.get("status"),
                "reason": reg.get("reason"),
                "unknown": None,
            }
        return out

    # ----------------------------------------------------------------- inspect
    def inspect(self, dwg_path: str, out_dir: str, mode: str = "graph",
                include_rich: bool = False) -> dict:
        """Stage a COPY of dwg_path, run the router DWG extraction on the copy,
        normalize to dwg_graph_ir.v1, and write the full artifact set into out_dir.

        include_rich=True routes the native inspect.database.graph op (ObjectARX
        .dbx/.crx) instead of the geometry-only extractor, producing a
        coverage_level="native_full" IR (symbol tables, blocks, layouts, xrefs,
        dictionaries, xrecords) via ir_builder.build_ir_from_database_graph.

        Artifacts written to out_dir:
          cad_job.json        -- the job descriptor we issued
          stdout.txt          -- router stdout (captured)
          stderr.txt          -- router stderr (captured)
          cad_result.json     -- ariadne.autocad_sdk_result.v2
          dwg_graph_ir.json   -- ariadne.dwg_graph_ir.v1 (when extraction succeeded)

        Truthful failure modes:
          - input missing                -> status 'blocked'
          - ir_builder (Lane B3) absent  -> status 'not_implemented'
          - router extraction failed     -> status 'partial' / 'unavailable'
        """
        out_dir_p = Path(out_dir)
        out_dir_p.mkdir(parents=True, exist_ok=True)
        cad_job_path = out_dir_p / "cad_job.json"
        cad_result_path = out_dir_p / "cad_result.json"
        ir_path = out_dir_p / "dwg_graph_ir.json"

        src = Path(dwg_path)
        operation = "inspect.geometry.extract"

        # --- precondition: input exists ---
        if not src.exists():
            cad_job = self._build_cad_job(operation, dwg_path, None, mode)
            cad_job_path.write_text(json.dumps(cad_job, ensure_ascii=False, indent=2), encoding="utf-8")
            result = normalize_result.blocked_result(
                operation, "PRECONDITION_FAILED",
                f"input DWG not found: {dwg_path}", input_path=str(dwg_path),
            )
            result["job_ref"] = str(cad_job_path)
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope("blocked", result, cad_job_path, cad_result_path,
                                          None, None, staged=None,
                                          reason="input DWG not found")

        # --- stage a COPY under staging/golden/<ts>/ (NEVER touch the original) ---
        stage_root = self.staging_golden / _ts()
        stage_root.mkdir(parents=True, exist_ok=True)
        staged = stage_root / "input.dwg"
        shutil.copy2(src, staged)
        try:
            os.chmod(staged, 0o666)  # ensure the staged copy is writable for the lane
        except OSError:
            pass
        staged_meta = {
            "staged_copy": str(staged),
            "original": str(src.resolve()),
            "byte_size": staged.stat().st_size,
            "sha256_16": _sha256_head(staged),
            "staged_at": _now_iso(),
        }

        cad_job = self._build_cad_job(operation, dwg_path, staged_meta, mode)
        cad_job_path.write_text(json.dumps(cad_job, ensure_ascii=False, indent=2), encoding="utf-8")

        # --- rich native_full path: native inspect.database.graph ---
        if include_rich:
            return self._inspect_rich_native(src, staged, staged_meta, out_dir_p,
                                             cad_job_path, cad_result_path, ir_path)

        # --- run the router extraction on the COPY (captures stdout/stderr/exit) ---
        run_res = run_job.run_router_extract(
            str(staged), str(out_dir_p), intent="dwg", extract_mode="geometry_native"
        )
        envelope = run_res.get("envelope")

        # Build the cad_result.v2 from whatever the router returned.
        if envelope is None:
            # Router produced no parseable JSON (missing entrypoint, spawn failure,
            # or timeout). That is unavailable/partial, never ok.
            reason = run_res.get("error") or "router produced no parseable JSON envelope"
            status_word = "unavailable" if run_res.get("error") else "partial"
            code = "HOST_UNAVAILABLE" if run_res.get("error") else "ROUTE_NONZERO_EXIT"
            result = normalize_result.blocked_result(
                operation, code, reason,
                exit_code=run_res.get("exit_code"),
                stdout_ref=run_res.get("stdout_path"),
                stderr_ref=run_res.get("stderr_path"),
            )
            # blocked_result chose status by code; force the intended word.
            result["status"] = status_word
            result["error"]["retryable"] = True
            result["job_ref"] = str(cad_job_path)
            result.setdefault("artifacts", []).append(
                {"kind": "dwg_staged", "ref": str(staged)}
            )
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope(status_word, result, cad_job_path, cad_result_path,
                                          run_res.get("stdout_path"), run_res.get("stderr_path"),
                                          staged=str(staged), reason=reason)

        result = normalize_result.normalize_router_run(
            envelope,
            operation=operation,
            job_ref=str(cad_job_path),
            write_mode="read",
            stdout_ref=run_res.get("stdout_path"),
            stderr_ref=run_res.get("stderr_path"),
        )

        # If the router did not succeed, write the result and stop (no IR).
        if result.get("status") != "ok":
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope(result.get("status", "error"), result,
                                          cad_job_path, cad_result_path,
                                          run_res.get("stdout_path"), run_res.get("stderr_path"),
                                          staged=str(staged),
                                          reason="router extraction did not return ok")

        # --- load the extract JSON the router wrote ---
        extract_ref = result.get("result_ref")
        extract = None
        extract_err = None
        if extract_ref and Path(extract_ref).exists():
            try:
                extract = _load_json_bom(Path(extract_ref))
            except Exception as exc:
                extract_err = f"failed to read extract JSON: {type(exc).__name__}: {exc}"
        else:
            extract_err = f"router reported ok but extract JSON missing: {extract_ref}"

        if extract is None:
            result["status"] = "partial"
            result["error"] = {
                "code": "VALIDATION_ERROR",
                "message": extract_err or "extract unavailable",
                "retryable": False,
            }
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope("partial", result, cad_job_path, cad_result_path,
                                          run_res.get("stdout_path"), run_res.get("stderr_path"),
                                          staged=str(staged), reason=extract_err)

        # --- normalize extract -> dwg_graph_ir.v1 via Lane B3's ir_builder ---
        ir_builder, imp_err = _import_optional("ir_builder")
        if ir_builder is None:
            # ir_builder is owned by Lane B3 and not present yet: report truthfully.
            result["status"] = "not_implemented"
            result["error"] = {
                "code": "OPERATION_NOT_IMPLEMENTED",
                "message": f"ir_builder (Lane B3) unavailable; cannot normalize extract to dwg_graph_ir.v1: {imp_err}",
                "retryable": True,
                "details": {"missing_module": "ir_builder", "extract_ref": extract_ref},
            }
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope("not_implemented", result, cad_job_path, cad_result_path,
                                          run_res.get("stdout_path"), run_res.get("stderr_path"),
                                          staged=str(staged),
                                          reason="ir_builder not available")

        source_meta = {
            "dwg_path": str(staged),
            "original_path": str(src.resolve()),
            "dwg_name": src.name,
            "format": "dwg",
            "byte_size": staged_meta["byte_size"],
            "sha256": _sha256_head(staged, 64).lower(),
            "extractor": (envelope.get("execution") or {}).get("engine_output", {}).get("winning_engine")
            or "objectarx",
            "engine_tier": "native_arx",
            "extracted_at": _now_iso(),
        }
        summary = extract.get("summary")
        try:
            ir = ir_builder.build_ir_from_extract(extract, summary, source_meta)
            ir_written = ir_builder.write_ir(ir, str(ir_path))
        except Exception as exc:
            result["status"] = "partial"
            result["error"] = {
                "code": "VALIDATION_ERROR",
                "message": f"ir_builder.build_ir_from_extract failed: {type(exc).__name__}: {exc}",
                "retryable": False,
                "details": {"extract_ref": extract_ref},
            }
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope("partial", result, cad_job_path, cad_result_path,
                                          run_res.get("stdout_path"), run_res.get("stderr_path"),
                                          staged=str(staged), reason="ir_builder failed")

        # --- success: attach IR ref + diagnostics, finalize cad_result.v2 ---
        ir_diag = (ir or {}).get("diagnostics", {})
        result["ir_ref"] = str(ir_path)
        result.setdefault("diagnostics", {})["entity_count"] = ir_diag.get("entity_count")
        result.setdefault("artifacts", []).append({"kind": "ir", "ref": str(ir_path)})
        cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        return self._inspect_envelope("ok", result, cad_job_path, cad_result_path,
                                      run_res.get("stdout_path"), run_res.get("stderr_path"),
                                      staged=str(staged), ir_path=str(ir_path),
                                      entity_count=ir_diag.get("entity_count"),
                                      reason=None)

    def _inspect_rich_native(self, src: Path, staged: Path, staged_meta: dict,
                             out_dir_p: Path, cad_job_path: Path,
                             cad_result_path: Path, ir_path: Path) -> dict:
        """Native inspect.database.graph -> coverage_level=native_full IR."""
        operation = "inspect.database.graph"
        # overwrite the cad_job with the rich operation for accuracy
        cad_job = self._build_cad_job(operation, str(src), staged_meta, "graph")
        cad_job_path.write_text(json.dumps(cad_job, ensure_ascii=False, indent=2), encoding="utf-8")

        run_res = run_job.run_router_cad_job(
            str(staged), str(out_dir_p), operation, write_mode="read")
        stdout_path = run_res.get("stdout_path")
        stderr_path = run_res.get("stderr_path")
        result_obj = run_res.get("result")

        if result_obj is None:
            reason = run_res.get("error") or "native graph job produced no result JSON"
            status_word = "unavailable" if run_res.get("error") else "partial"
            code = "HOST_UNAVAILABLE" if run_res.get("error") else "ROUTE_NONZERO_EXIT"
            result = normalize_result.blocked_result(
                operation, code, reason, exit_code=run_res.get("exit_code"),
                stdout_ref=stdout_path, stderr_ref=stderr_path)
            result["status"] = status_word
            result["job_ref"] = str(cad_job_path)
            result.setdefault("artifacts", []).append({"kind": "dwg_staged", "ref": str(staged)})
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope(status_word, result, cad_job_path, cad_result_path,
                                          stdout_path, stderr_path, staged=str(staged), reason=reason)

        ir_builder, imp_err = _import_optional("ir_builder")
        if ir_builder is None or not hasattr(ir_builder, "build_ir_from_database_graph"):
            result = normalize_result.blocked_result(
                operation, "OPERATION_NOT_IMPLEMENTED",
                f"ir_builder.build_ir_from_database_graph unavailable: {imp_err}",
                result_json=run_res.get("result_json"))
            result["status"] = "not_implemented"
            result["job_ref"] = str(cad_job_path)
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope("not_implemented", result, cad_job_path, cad_result_path,
                                          stdout_path, stderr_path, staged=str(staged),
                                          reason="ir_builder rich builder not available")

        source_meta = {
            "dwg_path": str(staged),
            "original_path": str(src.resolve()),
            "dwg_name": src.name,
            "format": "dwg",
            "byte_size": staged_meta["byte_size"],
            "sha256": _sha256_head(staged, 64).lower(),
            "extractor": "native_objectarx",
            "engine_tier": "native_arx",
            "route": "dwg_truth_autocad",
            "extracted_at": _now_iso(),
        }
        try:
            ir = ir_builder.build_ir_from_database_graph(result_obj, source_meta)
            ir_builder.write_ir(ir, str(ir_path))
        except Exception as exc:
            result = normalize_result.blocked_result(
                operation, "VALIDATION_ERROR",
                f"build_ir_from_database_graph failed: {type(exc).__name__}: {exc}",
                result_json=run_res.get("result_json"))
            result["status"] = "partial"
            result["job_ref"] = str(cad_job_path)
            cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._inspect_envelope("partial", result, cad_job_path, cad_result_path,
                                          stdout_path, stderr_path, staged=str(staged),
                                          reason="rich IR build failed")

        diag = ir.get("diagnostics", {})
        result = {
            "schema": "ariadne.autocad_sdk_result.v2",
            "operation": operation,
            "status": "ok",
            "write_mode": "read",
            "job_ref": str(cad_job_path),
            "result_ref": run_res.get("result_json"),
            "ir_ref": str(ir_path),
            "diagnostics": {
                "entity_count": diag.get("entity_count"),
                "coverage_level": ir.get("coverage_level"),
                "sections_present": (diag.get("coverage") or {}).get("sections_present"),
            },
            "artifacts": [
                {"kind": "ir", "ref": str(ir_path)},
                {"kind": "dwg_staged", "ref": str(staged)},
            ],
        }
        cad_result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return self._inspect_envelope("ok", result, cad_job_path, cad_result_path,
                                      stdout_path, stderr_path, staged=str(staged),
                                      ir_path=str(ir_path), entity_count=diag.get("entity_count"),
                                      reason=None)

    # ------------------------------------------------------------------- query
    def query(self, ir_path: str, sql: str) -> dict:
        """Run a read-only SQL query against an IR's sqlite store (Lane B2).

        Builds an ephemeral sqlite DB from the IR via sqlite_ir_store.build_store,
        then runs sqlite_ir_store.query(db, sql). Truthful failures: ir missing ->
        blocked; sqlite_ir_store (Lane B2) absent -> not_implemented.
        """
        irp = Path(ir_path)
        if not irp.exists():
            return {
                "schema": "ariadne.cadctl.query.v1",
                "status": "blocked",
                "reason": f"IR file not found: {ir_path}",
            }
        store, imp_err = _import_optional("sqlite_ir_store")
        if store is None:
            return {
                "schema": "ariadne.cadctl.query.v1",
                "status": "not_implemented",
                "reason": f"sqlite_ir_store (Lane B2) unavailable: {imp_err}",
            }
        try:
            ir = _load_json_bom(irp)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.query.v1",
                "status": "error",
                "reason": f"failed to read IR: {type(exc).__name__}: {exc}",
            }
        # Build the store next to the IR (deterministic, overwritable).
        db_path = str(irp.with_suffix(".sqlite"))
        try:
            build_info = store.build_store(ir, db_path)
            result = store.query(db_path, sql)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.query.v1",
                "status": "error",
                "reason": f"sqlite_ir_store failed: {type(exc).__name__}: {exc}",
                "db_path": db_path,
            }
        return {
            "schema": "ariadne.cadctl.query.v1",
            "status": "ok",
            "db_path": db_path,
            "store": build_info,
            "columns": result.get("columns", []),
            "rows": result.get("rows", []),
            "row_count": len(result.get("rows", [])),
        }

    def get_entity(self, ir_path: str, handle: str) -> dict:
        """Fetch one entity by handle using the same read-only SQL shell."""
        safe_handle = str(handle).replace("'", "''")
        q = self.query(ir_path, "SELECT * FROM entities WHERE handle = '%s'" % safe_handle)
        if q.get("status") != "ok":
            return {
                "schema": "ariadne.cadctl.get_entity.v1",
                "status": q.get("status", "error"),
                "handle": handle,
                "reason": q.get("reason") or q.get("error"),
                "delegate": "cadctl.query",
            }
        return {
            "schema": "ariadne.cadctl.get_entity.v1",
            "status": "ok",
            "handle": handle,
            "db_path": q.get("db_path"),
            "columns": q.get("columns", []),
            "rows": q.get("rows", []),
            "row_count": q.get("row_count", 0),
            "delegate": "cadctl.query",
        }

    # ---------------------------------------------------------------- validate
    def validate(self, ir_path: str) -> dict:
        """Validate an IR/run via the deterministic gates in validator (Lane E).

        Truthful failure: validator absent -> not_implemented (NOT a faked pass).
        """
        irp = Path(ir_path)
        if not irp.exists():
            return {
                "schema": "ariadne.cadctl.validate.v1",
                "status": "blocked",
                "reason": f"IR file not found: {ir_path}",
            }
        validator, imp_err = _import_optional("validator")
        if validator is None:
            return {
                "schema": "ariadne.cadctl.validate.v1",
                "status": "not_implemented",
                "reason": f"validator (Lane E) unavailable: {imp_err}",
            }
        try:
            report = validator.validate_target(ir_path=str(irp), run_dir=str(irp.parent))
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.validate.v1",
                "status": "error",
                "reason": f"validator.validate_target failed: {type(exc).__name__}: {exc}",
            }
        return {
            "schema": "ariadne.cadctl.validate.v1",
            "status": "ok",
            "report": report,
        }

    # --------------------------------------------------------------- registry
    def registry_list(self) -> dict:
        """List the v2 operation registry (config/operations.v2.json, utf-8-sig)."""
        if not OPERATIONS_V2.exists():
            return {
                "schema": "ariadne.cadctl.registry_list.v1",
                "status": "unavailable",
                "reason": f"operations.v2.json not found: {OPERATIONS_V2}",
            }
        reg = _load_json_bom(OPERATIONS_V2)
        ops = reg.get("operations", []) or []
        listed = [
            {
                "id": o.get("id"),
                "family": o.get("family"),
                "status": o.get("status"),
                "engine_tier": o.get("engine_tier"),
                "router_lane": (o.get("handler") or {}).get("router_lane"),
                "execution_host_class": (o.get("handler") or {}).get("execution_host_class"),
            }
            for o in ops
        ]
        return {
            "schema": "ariadne.cadctl.registry_list.v1",
            "status": "ok",
            "registry_schema": reg.get("schema"),
            "registry_version": reg.get("version"),
            "operation_count": len(listed),
            "wired_count": sum(1 for o in listed if o["status"] == "implemented"),
            "operations": listed,
        }

    def registry_coverage(self) -> dict:
        """Summarize operation coverage (totals + coverage block of operations.v2)."""
        if not OPERATIONS_V2.exists():
            return {
                "schema": "ariadne.cadctl.registry_coverage.v1",
                "status": "unavailable",
                "reason": f"operations.v2.json not found: {OPERATIONS_V2}",
            }
        reg = _load_json_bom(OPERATIONS_V2)
        ops = reg.get("operations", []) or []
        by_status: dict = {}
        by_family: dict = {}
        by_tier: dict = {}
        for o in ops:
            by_status[o.get("status")] = by_status.get(o.get("status"), 0) + 1
            by_family[o.get("family")] = by_family.get(o.get("family"), 0) + 1
            by_tier[o.get("engine_tier")] = by_tier.get(o.get("engine_tier"), 0) + 1
        wired = by_status.get("implemented", 0)
        unknown_count = sum(v for k, v in by_status.items() if k in (None, "", "unknown"))
        return {
            "schema": "ariadne.cadctl.registry_coverage.v1",
            "status": "ok",
            "registry_schema": reg.get("schema"),
            "registry_version": reg.get("version"),
            "operation_count": len(ops),
            "wired_count": wired,
            "totals": reg.get("totals"),
            "declared_coverage": reg.get("coverage"),
            "computed_by_status": by_status,
            "computed_by_family": by_family,
            "computed_by_engine_tier": by_tier,
            "unknown_count": unknown_count,
            "consistent": (
                reg.get("totals", {}).get("by_status", {}).get("implemented") == wired
            ),
        }

    def registry_explain(self, op_id: str) -> dict:
        """Return the full v2 registry record for one operation (drives `explain`)."""
        if not OPERATIONS_V2.exists():
            return {
                "schema": "ariadne.cadctl.registry_explain.v1",
                "status": "unavailable",
                "reason": f"operations.v2.json not found: {OPERATIONS_V2}",
            }
        reg = _load_json_bom(OPERATIONS_V2)
        ops = reg.get("operations", []) or []
        rec = next((o for o in ops if o.get("id") == op_id), None)
        if rec is None:
            return {
                "schema": "ariadne.cadctl.registry_explain.v1",
                "status": "not_found",
                "operation": op_id,
                "reason": f"operation '{op_id}' not found in registry",
                "known_count": len(ops),
            }
        return {
            "schema": "ariadne.cadctl.registry_explain.v1",
            "status": "ok",
            "operation": op_id,
            "registry_operation_status": rec.get("status"),
            "record": rec,
        }

    def _registry_operation_status(self, op_id: str | None) -> str | None:
        if not op_id:
            return None
        rec = self._registry_record(op_id)
        return rec.get("status") if rec else None

    def _registry_record(self, op_id: str | None) -> dict | None:
        """Return the full v2 registry record for op_id (by 'id' or 'operation'), or None."""
        if not op_id:
            return None
        try:
            reg = _load_json_bom(OPERATIONS_V2)
        except Exception:
            return None
        for rec in reg.get("operations", []) or []:
            if rec.get("id") == op_id or rec.get("operation") == op_id:
                return rec
        return None

    def _run_op_refusal(self, op_id, status_word, reason, out_dir,
                        registry_status=None, blocked_reason=None) -> dict:
        env = {
            "schema": "ariadne.cadctl.run_operation.v1",
            "operation": op_id,
            "status": status_word,
            "executed": False,
            "registry_operation_status": registry_status,
            "reason": reason,
            "out_dir": str(out_dir),
        }
        if blocked_reason:
            env["registry_blocked_reason"] = blocked_reason
        return env

    # ------------------------------------------------------------- run_operation
    def run_operation(self, op_id: str, args: dict | None = None,
                      write_mode: str | None = None, dwg_path: str | None = None,
                      out_dir: str | None = None) -> dict:
        """Drive ANY implemented registry operation through the native router job lane.

        The generic agent-control entry point: maps an arbitrary op_id onto the
        ObjectARX native-job lane (the same lane inspect.database.graph uses),
        behind a registry allow-list + write-mode governance gate.

        Safety gates (no-fake / original-safe):
          * op_id must be status=='implemented'. blocked / unknown / not-found ->
            truthful refusal (executed=False); the op is NEVER run.
          * write-mode governance: defaults to the op's registry default_write_mode;
            an explicit write_mode must be in allowed_write_modes; write_original is
            ALWAYS refused from this surface (the original DWG stays READ-ONLY).
          * a COPY is staged; the original DWG's sha is verified unchanged.

        Staged-copy snapshot (pre/post, for run-record-only verification):
          the router (autocad-router.ps1 -> Invoke-CadJobRoute) stages its OWN,
          second-level copy under staging/dwg_job_<stamp>/ and _QSAVEs THAT one
          for write ops; the copy staged here (`staged_copy`) is never touched
          again, so its sha256 taken right before the router runs is a true
          pre-write snapshot. The router's own post-run copy is reported back
          as run_res["staged_used"]; its path + sha256 are surfaced here as
          `staged_result` / `staged_result_sha256` so a caller can verify what a
          write op actually produced from this record alone, without re-deriving
          anything. read-mode ops never _QSAVE, so `staged_result_sha256` equals
          `staged_copy_sha256` in that case.
        """
        out_dir_p = Path(out_dir) if out_dir else (self.router_home / "runs" / "run_op" / _ts())
        out_dir_p.mkdir(parents=True, exist_ok=True)

        # --- registry allow-list gate ---
        rec = self._registry_record(op_id)
        if rec is None:
            return self._run_op_refusal(op_id, "not_found",
                f"operation '{op_id}' is not in the operation registry", out_dir_p)
        op_status = rec.get("status")
        if op_status != "implemented":
            return self._run_op_refusal(op_id, "blocked",
                f"operation '{op_id}' has registry status '{op_status}', not 'implemented'; refused",
                out_dir_p, registry_status=op_status, blocked_reason=rec.get("blocked_reason"))

        # --- write-mode governance ---
        wl = rec.get("write_level") or {}
        default_wm = wl.get("default_write_mode") or "read"
        allowed = set(wl.get("allowed_write_modes") or [default_wm])
        wm = write_mode or default_wm
        if wm in ("write_original", "original"):
            return self._run_op_refusal(op_id, "blocked",
                "write_mode 'write_original' is never permitted from the agent run surface; "
                "the original DWG is READ-ONLY (use a staged write_copy)",
                out_dir_p, registry_status=op_status)
        if wm not in allowed:
            return self._run_op_refusal(op_id, "blocked",
                f"write_mode '{wm}' is not in allowed_write_modes {sorted(allowed)} for '{op_id}'",
                out_dir_p, registry_status=op_status)

        # --- stage the input DWG (original READ-ONLY) ---
        if not dwg_path:
            return self._run_op_refusal(op_id, "blocked",
                "run_operation requires a dwg_path (a copy is staged); no-input generator ops "
                "are not yet wired through this surface",
                out_dir_p, registry_status=op_status)
        src = Path(dwg_path)
        if not src.exists():
            return self._run_op_refusal(op_id, "blocked",
                f"input DWG not found: {dwg_path}", out_dir_p, registry_status=op_status)
        sha_before = _sha256_head(src, 64)
        stage_root = self.staging_golden / _ts()
        stage_root.mkdir(parents=True, exist_ok=True)
        staged = stage_root / "input.dwg"
        shutil.copy2(src, staged)
        try:
            os.chmod(staged, 0o666)
        except OSError:
            pass
        # Pre-write snapshot: `staged` is never touched again after this point
        # (the router stages its OWN second-level copy -- see docstring), so its
        # sha256 taken now is a guaranteed pre-write value.
        staged_copy_sha256 = _sha256_head(staged, 64).lower()

        # --- optional args -> ARIADNE_NATIVE_JOB job file (-JobPath) ---
        job_path = None
        if args:
            job_path = str(out_dir_p / "job_args.json")
            payload = {"operation": op_id}
            payload.update(args)
            Path(job_path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        # --- drive the native job lane on the COPY ---
        run_res = run_job.run_router_cad_job(str(staged), str(out_dir_p), op_id,
                                             write_mode=wm, job_path=job_path)
        sha_after = _sha256_head(src, 64)
        original_unchanged = (sha_before == sha_after)

        # Post-run snapshot: the router's own staged copy, reported back as
        # staged_used (engine_output.input). For write ops this is the mutated
        # (post-_QSAVE) file; for read ops it is the router's unmutated read copy.
        staged_result = run_res.get("staged_used")
        staged_result_sha256 = None
        if isinstance(staged_result, str) and staged_result and Path(staged_result).is_file():
            staged_result_sha256 = _sha256_head(Path(staged_result), 64).lower()

        env = {
            "schema": "ariadne.cadctl.run_operation.v1",
            "operation": op_id,
            "executed": True,
            "registry_operation_status": op_status,
            "write_mode": wm,
            "out_dir": str(out_dir_p),
            "staged_copy": str(staged),
            "staged_copy_sha256": staged_copy_sha256,
            "staged_result": staged_result,
            "staged_result_sha256": staged_result_sha256,
            "original_unchanged": original_unchanged,
            "exit_code": run_res.get("exit_code"),
            "stdout": run_res.get("stdout_path"),
            "stderr": run_res.get("stderr_path"),
            "result_ref": run_res.get("result_json"),
        }
        if not original_unchanged:
            env["status"] = "error"
            env["reason"] = "SAFETY VIOLATION: original DWG sha changed during run_operation"
            return env
        if run_res.get("error"):
            env["status"] = "unavailable"
            env["reason"] = run_res.get("error")
            return env
        result_obj = run_res.get("result")
        if result_obj is None:
            env["status"] = "partial"
            env["reason"] = "native job produced no parseable result JSON"
            return env
        native_status = (result_obj.get("status") if isinstance(result_obj, dict) else None) or "ok"
        env["status"] = native_status if native_status in (
            "ok", "blocked", "not_implemented", "partial", "error", "unavailable") else "ok"
        env["result"] = result_obj
        return env

    # ------------------------------------------------------------- shell tools
    def patch_dry_run(self, patch: dict) -> dict:
        patch_engine, imp_err = _import_optional("patch_engine")
        if patch_engine is None or not hasattr(patch_engine, "dry_run_plan"):
            return {
                "schema": "ariadne.cadctl.patch_dry_run.v1",
                "status": "not_implemented",
                "reason": f"patch_engine.dry_run_plan unavailable: {imp_err}",
            }
        try:
            return patch_engine.dry_run_plan(patch)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.patch_dry_run.v1",
                "status": "error",
                "reason": f"patch_engine.dry_run_plan failed: {type(exc).__name__}: {exc}",
            }

    def patch_apply_staged(self, patch: dict, dwg_path: str, out_dir: str) -> dict:
        """Apply a cad_patch.v1 to a staged copy through patch_engine.

        This is the explicit M05 mutation surface. It delegates to
        patch_engine.apply_staged, which copies dwg_path to out_dir first and
        never writes the original DWG.
        """
        patch_engine, imp_err = _import_optional("patch_engine")
        if patch_engine is None or not hasattr(patch_engine, "apply_staged"):
            return {
                "schema": "ariadne.cad_patch.result.v1",
                "status": "not_implemented",
                "reason": f"patch_engine.apply_staged unavailable: {imp_err}",
            }
        try:
            return patch_engine.apply_staged(patch, dwg_path, out_dir)
        except Exception as exc:
            return {
                "schema": "ariadne.cad_patch.result.v1",
                "status": "error",
                "reason": f"patch_engine.apply_staged failed: {type(exc).__name__}: {exc}",
            }

    # ------------------------------------------------------------- semantic anchors (W5-ANCHOR)

    def anchor_set(self, dwg_path: str, handle: str, body: dict, out_dir: str, *,
                  author_agent: str, tags: list | None = None) -> dict:
        """Write (upsert) a semantic anchor onto ``handle`` on a STAGED copy of
        ``dwg_path``, via the existing set_entity_xdata_by_handle patch op
        (native modify.entity.xdata -- no new native op). See
        docs/SEMANTIC_ANCHOR_SPEC.md and tools/anchor_ops.py.
        """
        anchor_ops, imp_err = _import_optional("anchor_ops")
        if anchor_ops is None:
            return {
                "schema": "ariadne.cadctl.anchor_set.v1",
                "status": "not_implemented",
                "reason": f"anchor_ops (Lane W5-ANCHOR) unavailable: {imp_err}",
            }
        try:
            patch = anchor_ops.build_anchor_set_patch(
                handle, body, author_agent=author_agent, tags=tags)
        except anchor_ops.AnchorError as exc:
            return {
                "schema": "ariadne.cadctl.anchor_set.v1",
                "status": "blocked",
                "handle": handle,
                "reason": str(exc),
            }
        patch_engine, imp_err2 = _import_optional("patch_engine")
        if patch_engine is None or not hasattr(patch_engine, "apply_staged"):
            return {
                "schema": "ariadne.cadctl.anchor_set.v1",
                "status": "not_implemented",
                "reason": f"patch_engine.apply_staged unavailable: {imp_err2}",
            }
        try:
            patch_result = patch_engine.apply_staged(patch, dwg_path, out_dir)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.anchor_set.v1",
                "status": "error",
                "handle": handle,
                "reason": f"patch_engine.apply_staged failed: {type(exc).__name__}: {exc}",
            }
        return {
            "schema": "ariadne.cadctl.anchor_set.v1",
            "status": patch_result.get("status"),
            "handle": handle,
            "patch_result": patch_result,
        }

    def anchor_clear(self, dwg_path: str, handle: str, out_dir: str, *,
                     author_agent: str) -> dict:
        """Logically clear (tombstone) the semantic anchor on ``handle`` on a
        STAGED copy of ``dwg_path``. KNOWN LIMITATION: this cannot truly
        remove the RegApp xdata (the native handler rejects an empty
        'values' array) -- see anchor_ops.build_anchor_clear_patch and
        docs/SEMANTIC_ANCHOR_SPEC.md "Clear semantics".
        """
        anchor_ops, imp_err = _import_optional("anchor_ops")
        if anchor_ops is None:
            return {
                "schema": "ariadne.cadctl.anchor_clear.v1",
                "status": "not_implemented",
                "reason": f"anchor_ops (Lane W5-ANCHOR) unavailable: {imp_err}",
            }
        try:
            patch = anchor_ops.build_anchor_clear_patch(handle, author_agent=author_agent)
        except anchor_ops.AnchorError as exc:
            return {
                "schema": "ariadne.cadctl.anchor_clear.v1",
                "status": "blocked",
                "handle": handle,
                "reason": str(exc),
            }
        patch_engine, imp_err2 = _import_optional("patch_engine")
        if patch_engine is None or not hasattr(patch_engine, "apply_staged"):
            return {
                "schema": "ariadne.cadctl.anchor_clear.v1",
                "status": "not_implemented",
                "reason": f"patch_engine.apply_staged unavailable: {imp_err2}",
            }
        try:
            patch_result = patch_engine.apply_staged(patch, dwg_path, out_dir)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.anchor_clear.v1",
                "status": "error",
                "handle": handle,
                "reason": f"patch_engine.apply_staged failed: {type(exc).__name__}: {exc}",
            }
        return {
            "schema": "ariadne.cadctl.anchor_clear.v1",
            "status": patch_result.get("status"),
            "handle": handle,
            "patch_result": patch_result,
        }

    def anchor_get(self, ir_path: str, handle: str) -> dict:
        """Read a semantic anchor back from an already-extracted IR (same
        ir_path convention as query()/get_entity()). No native call: xdata is
        already carried through by the existing extraction pipeline.
        """
        irp = Path(ir_path)
        if not irp.exists():
            return {
                "schema": "ariadne.cadctl.anchor_get.v1",
                "status": "blocked",
                "reason": f"IR file not found: {ir_path}",
            }
        anchor_ops, imp_err = _import_optional("anchor_ops")
        if anchor_ops is None:
            return {
                "schema": "ariadne.cadctl.anchor_get.v1",
                "status": "not_implemented",
                "reason": f"anchor_ops (Lane W5-ANCHOR) unavailable: {imp_err}",
            }
        try:
            ir = _load_json_bom(irp)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.anchor_get.v1",
                "status": "error",
                "reason": f"failed to read IR: {type(exc).__name__}: {exc}",
            }
        result = dict(anchor_ops.get_anchor_from_ir(ir, handle))
        result["schema"] = "ariadne.cadctl.anchor_get.v1"
        return result

    def anchor_list(self, ir_path: str) -> dict:
        """List every live (non-tombstoned) semantic anchor in an
        already-extracted IR (same ir_path convention as query()/anchor_get()).
        """
        irp = Path(ir_path)
        if not irp.exists():
            return {
                "schema": "ariadne.cadctl.anchor_list.v1",
                "status": "blocked",
                "reason": f"IR file not found: {ir_path}",
            }
        anchor_ops, imp_err = _import_optional("anchor_ops")
        if anchor_ops is None:
            return {
                "schema": "ariadne.cadctl.anchor_list.v1",
                "status": "not_implemented",
                "reason": f"anchor_ops (Lane W5-ANCHOR) unavailable: {imp_err}",
            }
        try:
            ir = _load_json_bom(irp)
        except Exception as exc:
            return {
                "schema": "ariadne.cadctl.anchor_list.v1",
                "status": "error",
                "reason": f"failed to read IR: {type(exc).__name__}: {exc}",
            }
        result = dict(anchor_ops.list_anchors_from_ir(ir))
        result["schema"] = "ariadne.cadctl.anchor_list.v1"
        return result

    def diff_before_after(self, pre_ir_path: str, post_ir_path: str) -> dict:
        pre = Path(pre_ir_path)
        post = Path(post_ir_path)
        if not pre.exists() or not post.exists():
            return {
                "schema": "ariadne.cad_diff.v1",
                "status": "blocked",
                "reason": "pre_ir or post_ir file not found",
                "pre_ir": str(pre_ir_path),
                "post_ir": str(post_ir_path),
            }
        cad_diff, imp_err = _import_optional("cad_diff")
        if cad_diff is None or not hasattr(cad_diff, "compute_diff"):
            return {
                "schema": "ariadne.cad_diff.v1",
                "status": "not_implemented",
                "reason": f"cad_diff.compute_diff unavailable: {imp_err}",
            }
        try:
            pre_doc = _load_json_bom(pre)
            post_doc = _load_json_bom(post)
            return cad_diff.compute_diff(pre_doc, post_doc)
        except Exception as exc:
            return {
                "schema": "ariadne.cad_diff.v1",
                "status": "error",
                "reason": f"cad_diff.compute_diff failed: {type(exc).__name__}: {exc}",
            }

    def visual_report(self, source_ref: str, kind: str = "png",
                      artifact_id: str | None = None, out_dir: str | None = None,
                      route: str | None = None) -> dict:
        visual_report, imp_err = _import_optional("visual_report")
        if visual_report is None or not hasattr(visual_report, "build_visual_report"):
            return {
                "schema": "ariadne.visual_artifact.v1",
                "status": "not_implemented",
                "reason": f"visual_report.build_visual_report unavailable: {imp_err}",
            }
        try:
            result = visual_report.build_visual_report(
                source_ref, kind=kind, artifact_id=artifact_id,
                out_dir=out_dir, route=route)
            if result.get("status") == "error" and not Path(source_ref).exists():
                result = dict(result)
                result["status"] = "blocked"
                result["reason"] = "source_ref not found"
            return result
        except Exception as exc:
            return {
                "schema": "ariadne.visual_artifact.v1",
                "status": "error",
                "reason": f"visual_report.build_visual_report failed: {type(exc).__name__}: {exc}",
            }

    def live_status(self) -> dict:
        return {
            "schema": "ariadne.cadctl.live_status.v1",
            "status": "not_implemented",
            "live": False,
            "reason": "No persistent attended ObjectARX live pump is attached to cadctl. Use staged router operations; M07 owns deep live surface completion.",
        }

    # ----------------------------------------------------------------- helpers
    def _build_cad_job(self, operation: str, original: str,
                       staged_meta: dict | None, mode: str) -> dict:
        sel = route_select.operation_route(operation)
        if not sel.get("found"):
            sel = route_select.intent_route("dwg")
        job = {
            "schema": "ariadne.autocad_sdk_job.v1",
            "operation": operation,
            "write_mode": "read",
            "output_mode": "ir" if mode == "graph" else "extract",
            "issued_by": "cadctl",
            "issued_at": _now_iso(),
            "route": sel.get("route", "dwg_truth_autocad"),
            "extract_mode": "geometry_native",
            "input": {
                "original_path": str(Path(original).resolve()) if Path(original).exists() else str(original),
            },
        }
        if staged_meta:
            job["input"]["staged_copy"] = staged_meta.get("staged_copy")
            job["input"]["byte_size"] = staged_meta.get("byte_size")
            job["input"]["sha256_16"] = staged_meta.get("sha256_16")
        return job

    def _inspect_envelope(self, status_word: str, result: dict,
                          cad_job_path: Path, cad_result_path: Path,
                          stdout_path: str | None, stderr_path: str | None,
                          staged: str | None, ir_path: str | None = None,
                          entity_count=None, reason: str | None = None) -> dict:
        env = {
            "schema": "ariadne.cadctl.inspect.v1",
            "status": status_word,
            "operation": result.get("operation"),
            "registry_operation_status": (
                result.get("registry_operation_status")
                or self._registry_operation_status(result.get("operation"))
            ),
            "cad_job": str(cad_job_path),
            "cad_result": str(cad_result_path),
            "stdout": stdout_path,
            "stderr": stderr_path,
            "staged_copy": staged,
            "result_status": result.get("status"),
        }
        if ir_path:
            env["dwg_graph_ir"] = ir_path
        if entity_count is not None:
            env["entity_count"] = entity_count
        if reason:
            env["reason"] = reason
        return env


# Module-level convenience wrappers (so callers can `from cadctl import status`).
def status() -> dict:
    return Cad().status()


def inspect(dwg_path: str, out_dir: str, mode: str = "graph",
            include_rich: bool = False) -> dict:
    return Cad().inspect(dwg_path, out_dir, mode, include_rich)


def query(ir_path: str, sql: str) -> dict:
    return Cad().query(ir_path, sql)


def get_entity(ir_path: str, handle: str) -> dict:
    return Cad().get_entity(ir_path, handle)


def validate(ir_path: str) -> dict:
    return Cad().validate(ir_path)


def registry_list() -> dict:
    return Cad().registry_list()


def registry_coverage() -> dict:
    return Cad().registry_coverage()


def registry_explain(op_id: str) -> dict:
    return Cad().registry_explain(op_id)


def run_operation(op_id: str, args: dict | None = None, write_mode: str | None = None,
                  dwg_path: str | None = None, out_dir: str | None = None) -> dict:
    return Cad().run_operation(op_id, args, write_mode, dwg_path, out_dir)


def patch_dry_run(patch: dict) -> dict:
    return Cad().patch_dry_run(patch)


def patch_apply_staged(patch: dict, dwg_path: str, out_dir: str) -> dict:
    return Cad().patch_apply_staged(patch, dwg_path, out_dir)


def diff_before_after(pre_ir_path: str, post_ir_path: str) -> dict:
    return Cad().diff_before_after(pre_ir_path, post_ir_path)


def visual_report(source_ref: str, kind: str = "png",
                  artifact_id: str | None = None, out_dir: str | None = None,
                  route: str | None = None) -> dict:
    return Cad().visual_report(source_ref, kind, artifact_id, out_dir, route)


def live_status() -> dict:
    return Cad().live_status()
