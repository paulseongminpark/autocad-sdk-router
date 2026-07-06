#!/usr/bin/env python
"""command_template_engine.py -- Lane W5-TMPL governed command template engine.

Runs a small, human-curated set of built-in AutoCAD commands (AUDIT, -PURGE,
...) that have no safe path today because the only way to invoke a built-in
command is through the SAFETY_FORBIDDEN raw command-dispatch surface
(acedCommand / sendStringToExecute / acedMenuCmd -- see
docs/GOVERNED_COMMAND_TEMPLATES.md section 1 for the full threat model).

The registry (config/command_templates.json) fixes, per template, the EXACT
command-token sequence that will run. An agent never supplies a command
string: it supplies a template_id (from the closed registry) and values for
a small number of pre-declared, typed argument slots (enum / int_range /
float_range / name_token / staged_path). Every slot value passes a universal
hostile-character gate (control chars, quotes, semicolon, LISP parens) BEFORE
its type-specific validator runs, and `render_script()` builds the .scr line
list token-by-token from {"literal": ...} / {"slot": ...} steps -- there is
no string-interpolation step anywhere a slot value could smuggle an extra
script line.

Execution mirrors tools/autocad-router.ps1's Invoke-CadJobRoute/Invoke-AccoreScr
staged-copy discipline (staging/tmpl_<id>_<stamp>/input.dwg, accoreconsole.exe
/i <dwg> /s <script>, stdout/stderr captured to files, timeout+kill), reusing
tools/probe_routes.py's accoreconsole resolver -- no new resolver logic, and
autocad-router.ps1 itself is NOT touched (this lane's brief prefers building
on the existing script/job lane over adding a new router action).

write_original is impossible by construction: there is no code path here that
skips staging, and the registry loader rejects any template whose
write_mode.allowed contains anything other than "read"/"write_copy".

Standard library only (+ sibling tools/probe_routes.py for the accoreconsole
resolver). No CAD parsing beyond the tiny AutoLISP entity-count probe used for
postcondition enforcement.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parent
CONFIG_DIR = ROUTER_HOME / "config"
STAGING_DIR = ROUTER_HOME / "staging"
RUNS_DIR = ROUTER_HOME / "runs"
TEMPLATES_JSON = CONFIG_DIR / "command_templates.json"

if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import probe_routes  # noqa: E402  (sibling -- shared accoreconsole resolver)

SCHEMA_RESULT = "ariadne.autocad_sdk_result.v2"

# --------------------------------------------------------------------------- #
# Injection guard -- applies to EVERY slot value regardless of declared type,
# before that type's own validator runs. This is the literal implementation
# of "no free-text slot ever reaches the command line."
# --------------------------------------------------------------------------- #
_CONTROL_CHAR_RE = re.compile(r'[\x00-\x1f\x7f]')
_FORBIDDEN_CHARS = frozenset('\'"();')

_ALLOWED_WRITE_MODES = ("read", "write_copy")


class TemplateError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def _reject_if_hostile(value: str, slot_name: str) -> None:
    if _CONTROL_CHAR_RE.search(value):
        raise TemplateError(
            "INJECTION_REJECTED",
            f"slot {slot_name!r} contains a control character",
            {"slot": slot_name},
        )
    if any(ch in _FORBIDDEN_CHARS for ch in value):
        raise TemplateError(
            "INJECTION_REJECTED",
            f"slot {slot_name!r} contains a forbidden character (quote/semicolon/paren)",
            {"slot": slot_name},
        )


# --------------------------------------------------------------------------- #
# Registry load + validation
# --------------------------------------------------------------------------- #
# A registry document is `{"templates": [...]}` (the base file) or a bare
# `[...]` list (a fragment may use either shape). One drop-in file = one
# disjoint unit, so template additions never collide on the single base JSON.
FRAGMENT_DIRNAME_SUFFIX = ".d"  # command_templates.json -> command_templates.d/


def _templates_of(raw) -> list:
    return raw if isinstance(raw, list) else raw.get("templates", [])


def _ingest_templates(templates, by_id: dict, sources: dict, source: str) -> None:
    """Fold one document's templates into by_id. Fails LOUD on (a) a write_mode
    outside {read, write_copy} -- a template author cannot author a
    write_original-permitting entry without failing the whole load -- and (b) a
    template_id defined more than once (base vs fragment, or fragment vs
    fragment): a silent override would let a drop-in weaken a governed base
    template, so a collision is a hard error, never last-writer-wins."""
    for t in templates:
        tid = t["template_id"]
        allowed = t.get("write_mode", {}).get("allowed", [])
        bad = [m for m in allowed if m not in _ALLOWED_WRITE_MODES]
        if bad:
            raise TemplateError(
                "INVALID_TEMPLATE_REGISTRY",
                f"template {tid!r} declares disallowed write_mode(s) {bad!r} "
                f"(only {_ALLOWED_WRITE_MODES} permitted)",
                {"template_id": tid, "source": source},
            )
        if tid in by_id:
            raise TemplateError(
                "DUPLICATE_TEMPLATE_ID",
                f"template {tid!r} defined more than once "
                f"(collision between {sources[tid]!r} and {source!r})",
                {"template_id": tid, "source": source},
            )
        by_id[tid] = t
        sources[tid] = source


def load_templates(path: Path | str = TEMPLATES_JSON) -> dict:
    """Load + validate the governed command-template registry.

    Folded in a deterministic order (base first, then fragments sorted by
    filename):
      1. the base file `path` (config/command_templates.json), then
      2. every ``*.json`` under the sibling drop-in dir
         ``config/command_templates.d/`` (derived from the base filename).

    The drop-in dir lets a new template land as its OWN file -- a disjoint unit
    that never conflicts with the single base JSON at merge time. Every source
    is subject to the same guarantees (see _ingest_templates): a disallowed
    write_mode fails the whole load, and a duplicate template_id is a hard
    collision -- a fragment can never silently override a governed base
    template. Back-compatible: with no ``.d`` dir present, behavior is
    identical to the pre-drop-in single-file load."""
    base = Path(path)
    by_id: dict[str, dict] = {}
    sources: dict[str, str] = {}
    _ingest_templates(
        _templates_of(json.loads(base.read_text(encoding="utf-8-sig"))),
        by_id, sources, source=base.name,
    )
    frag_dir = base.parent / (base.stem + FRAGMENT_DIRNAME_SUFFIX)
    if frag_dir.is_dir():
        for frag in sorted(frag_dir.glob("*.json")):
            _ingest_templates(
                _templates_of(json.loads(frag.read_text(encoding="utf-8-sig"))),
                by_id, sources, source=f"{frag_dir.name}/{frag.name}",
            )
    return by_id


# --------------------------------------------------------------------------- #
# Slot validation + rendering
# --------------------------------------------------------------------------- #
def _validate_slot_value(slot_def: dict, slot_name: str, value) -> str:
    """Validate one slot value against its declared type; return the exact
    token string that will be written into the .scr file."""
    stype = slot_def["type"]

    if stype == "enum":
        sval = str(value)
        _reject_if_hostile(sval, slot_name)
        if sval not in slot_def["values"]:
            raise TemplateError(
                "VALIDATION_ERROR",
                f"slot {slot_name!r} value {value!r} not in {slot_def['values']!r}",
                {"slot": slot_name},
            )
        return sval

    if stype in ("int_range", "float_range"):
        try:
            num = int(value) if stype == "int_range" else float(value)
        except (TypeError, ValueError):
            raise TemplateError(
                "VALIDATION_ERROR",
                f"slot {slot_name!r} value {value!r} is not numeric ({stype})",
                {"slot": slot_name},
            )
        lo, hi = slot_def["min"], slot_def["max"]
        if not (lo <= num <= hi):
            raise TemplateError(
                "VALIDATION_ERROR",
                f"slot {slot_name!r} value {num} out of range [{lo}, {hi}]",
                {"slot": slot_name},
            )
        return str(num)

    if stype == "name_token":
        sval = str(value)
        _reject_if_hostile(sval, slot_name)
        if not re.fullmatch(r'[A-Za-z0-9_\-]{1,255}', sval):
            raise TemplateError(
                "VALIDATION_ERROR",
                f"slot {slot_name!r} value {value!r} is not a safe name token "
                r"(must match [A-Za-z0-9_-]{1,255})",
                {"slot": slot_name},
            )
        return sval

    if stype == "staged_path":
        sval = str(value)
        _reject_if_hostile(sval, slot_name)
        p = Path(sval).resolve()
        staging_root = STAGING_DIR.resolve()
        try:
            p.relative_to(staging_root)
        except ValueError:
            raise TemplateError(
                "VALIDATION_ERROR",
                f"slot {slot_name!r} path {value!r} escapes staging/ (must resolve inside {staging_root})",
                {"slot": slot_name},
            )
        return str(p).replace("\\", "/")

    raise TemplateError(
        "INVALID_TEMPLATE_REGISTRY",
        f"slot {slot_name!r} declares unknown type {stype!r}",
        {"slot": slot_name},
    )


def render_script(template: dict, args: dict) -> list[str]:
    """Render the fixed/slot command_sequence into a list of .scr tokens.

    Every token is either a template-fixed literal (author-controlled, never
    from agent input) or a validated slot value. `args` may only supply
    values for slots the template already declared in `command_sequence`;
    an extra key not backed by a declared slot is a hard UNKNOWN_ARG error
    (no smuggling extra script content through an unused arg)."""
    slots = template.get("slots", {})
    used_slots: set[str] = set()
    tokens: list[str] = []
    for step in template["command_sequence"]:
        if "literal" in step:
            tokens.append(step["literal"])
        elif "slot" in step:
            slot_name = step["slot"]
            slot_def = slots.get(slot_name)
            if slot_def is None:
                raise TemplateError(
                    "INVALID_TEMPLATE_REGISTRY",
                    f"command_sequence references undeclared slot {slot_name!r}",
                )
            used_slots.add(slot_name)
            if slot_name in args:
                value = args[slot_name]
            elif "default" in slot_def:
                value = slot_def["default"]
            else:
                raise TemplateError(
                    "MISSING_ARG",
                    f"required slot {slot_name!r} not supplied and has no default",
                    {"slot": slot_name},
                )
            tokens.append(_validate_slot_value(slot_def, slot_name, value))
        else:
            raise TemplateError(
                "INVALID_TEMPLATE_REGISTRY",
                f"command_sequence step {step!r} has neither 'literal' nor 'slot'",
            )
    extra = set(args) - used_slots
    if extra:
        raise TemplateError(
            "UNKNOWN_ARG",
            f"args contain slot(s) not referenced by this template's command_sequence: {sorted(extra)}",
            {"extra_args": sorted(extra)},
        )
    return tokens


# --------------------------------------------------------------------------- #
# accoreconsole resolution (delegates entirely to probe_routes.py)
# --------------------------------------------------------------------------- #
def resolve_engine() -> str | None:
    return probe_routes._cli(probe_routes.ACCORECONSOLE_CANDIDATES)


# --------------------------------------------------------------------------- #
# Staging + hashing
# --------------------------------------------------------------------------- #
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _read_accoreconsole_stdout(path: Path) -> str:
    """accoreconsole (UNICODE build) writes its console stream as UTF-16LE
    with no BOM -- measured live (Lane W5-TMPL): decoding as UTF-8 produces
    null-byte-interleaved mojibake. Falls back to utf-8 for any other tool's
    ASCII/UTF-8 captures if the byte stream doesn't look like UTF-16."""
    if not path.exists():
        return ""
    raw = path.read_bytes()
    if not raw:
        return ""
    # Heuristic: UTF-16LE ASCII-range text has a NUL every other byte.
    sample = raw[:200]
    nul_ratio = sample.count(b"\x00") / max(len(sample), 1)
    if nul_ratio > 0.3:
        try:
            return raw.decode("utf-16-le", errors="replace")
        except (UnicodeError, LookupError):
            pass
    return raw.decode("utf-8", errors="replace")


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stage_copy(input_path: Path, template_id: str) -> Path:
    """Copy input_path to staging/tmpl_<id>_<stamp>/input.dwg. Mirrors the
    router's staging/dwg_job_<stamp>/input.dwg naming family. The ORIGINAL
    is never opened directly by accoreconsole for a template run."""
    stage_root = STAGING_DIR / f"tmpl_{template_id.replace('.', '_')}_{_ts()}"
    stage_root.mkdir(parents=True, exist_ok=True)
    staged = stage_root / "input.dwg"
    shutil.copy2(input_path, staged)
    try:
        os.chmod(staged, 0o666)
    except OSError:
        pass
    return staged


# --------------------------------------------------------------------------- #
# Entity-count probe (postcondition support) -- engine-authored LISP, never
# built from agent input, so the injection guard above does not apply to it.
# --------------------------------------------------------------------------- #
def _entity_count_lisp_lines(out_path_fwd: str, marker: str) -> list[str]:
    fn = f"ariadneTmplCount{marker}"
    return [
        f'(defun c:{fn} ()',
        '  (setq _f (open "%s" "w"))' % out_path_fwd,
        '  (write-line (itoa (sslength (ssget "_X" (list (cons 410 "Model"))))) _f)',
        '  (close _f)',
        '  (princ))',
        fn,
    ]


def _read_int_file(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="ascii", errors="strict").strip())
    except (ValueError, OSError):
        return None


def evaluate_postconditions(postconditions: list[dict], stdout_text: str,
                             before_count: int | None, after_count: int | None
                             ) -> tuple[bool, list[dict]]:
    """Pure function: apply a template's declared postconditions against
    already-captured evidence (accoreconsole stdout text + the before/after
    entity-count probe results, if any). Returns (all_required_ok, results).

    Split out of run_template() so postcondition logic is unit-testable
    without accoreconsole (feed it synthetic stdout_text/counts)."""
    results = []
    ok = True
    for pc in postconditions:
        kind = pc.get("kind")
        if kind == "regex_capture":
            m = re.search(pc["pattern"], stdout_text)
            if m:
                binds = {name: m.group(i + 1) for i, name in enumerate(pc.get("bind", []))}
                results.append({"kind": kind, "matched": True, "values": binds})
            else:
                results.append({"kind": kind, "matched": False, "pattern": pc["pattern"]})
                if pc.get("required"):
                    ok = False
        elif kind == "entity_count_probe":
            entry = {"kind": kind, "before": before_count, "after": after_count}
            if pc.get("expect_unchanged"):
                entry["unchanged"] = (before_count is not None and before_count == after_count)
                if not entry["unchanged"]:
                    ok = False
            if pc.get("expect_increase"):
                entry["increased"] = (before_count is not None and after_count is not None
                                       and after_count > before_count)
                if not entry["increased"]:
                    ok = False
            if "expect_baseline" in pc:
                tolerance = pc.get("tolerance", 0)
                baseline = pc["expect_baseline"]
                entry["baseline"] = baseline
                entry["within_tolerance"] = (
                    after_count is not None and abs(after_count - baseline) <= tolerance
                )
                if not entry["within_tolerance"]:
                    ok = False
            results.append(entry)
        else:
            results.append({"kind": kind, "checked": False, "note": "unknown postcondition kind"})
            ok = False
    return ok, results


# --------------------------------------------------------------------------- #
# Envelope helpers (ariadne.autocad_sdk_result.v2 shape)
# --------------------------------------------------------------------------- #
def _base_envelope(operation: str, write_mode: str) -> dict:
    return {"schema": SCHEMA_RESULT, "operation": operation, "write_mode": write_mode}


def _error_envelope(env: dict, code: str, message: str, *, retryable: bool,
                     details: dict | None = None, status: str = "error") -> dict:
    env = dict(env)
    env["status"] = status
    env["error"] = {"code": code, "message": message, "retryable": retryable,
                     "details": details or {}}
    return env


# --------------------------------------------------------------------------- #
# Core entrypoint
# --------------------------------------------------------------------------- #
def run_template(template_id: str, args: dict, dwg_path: str, *,
                  write_mode: str = "read", run_dir: str | None = None,
                  timeout_sec: float = 120.0,
                  templates_path: Path | str = TEMPLATES_JSON,
                  _force_unverified: bool = False) -> dict:
    """Run one governed command template against dwg_path (a READ-ONLY
    original; this function stages its own copy and never opens the original
    with accoreconsole). Returns an ariadne.autocad_sdk_result.v2-shaped dict.

    Never raises for an ordinary validation/execution failure -- those become
    a truthful status != ok. Only programmer errors (e.g. a malformed
    registry file) propagate as TemplateError to the caller.

    `_force_unverified=True` bypasses the headless_safe gate. It exists ONLY
    for this lane's own live-measurement runs (proving a template out BEFORE
    its registry entry is flipped to headless_safe=true) and must never be
    set by an agent-facing caller -- the CLI below exposes it as
    --force-unverified specifically so that usage is visible in any command
    history / run log."""
    env = _base_envelope(template_id, write_mode)

    try:
        templates = load_templates(templates_path)
    except (OSError, ValueError, KeyError) as exc:
        return _error_envelope(env, "INVALID_TEMPLATE_REGISTRY", str(exc), retryable=False)

    template = templates.get(template_id)
    if template is None:
        return _error_envelope(env, "TEMPLATE_NOT_FOUND",
                                f"no such template: {template_id!r}", retryable=False,
                                status="blocked")

    if not template.get("headless_safe") and not _force_unverified:
        return _error_envelope(
            env, "ATTENDED_ONLY_TEMPLATE",
            f"template {template_id!r} is not certified headless-safe "
            "(headless_safe=false in the registry)",
            retryable=False, status="blocked",
        )

    allowed = template.get("write_mode", {}).get("allowed", [])
    if write_mode not in allowed:
        return _error_envelope(
            env, "WRITE_MODE_NOT_ALLOWED",
            f"write_mode {write_mode!r} not in this template's allowed set {allowed!r}",
            retryable=False, status="blocked",
        )

    src = Path(dwg_path)
    if not src.exists():
        return _error_envelope(env, "PRECONDITION_FAILED",
                                f"input DWG not found: {dwg_path}", retryable=False,
                                status="blocked")

    try:
        tokens = render_script(template, args or {})
    except TemplateError as exc:
        return _error_envelope(env, exc.code, exc.message, retryable=False,
                                details=exc.details, status="blocked")

    engine = resolve_engine()
    if not engine:
        return _error_envelope(env, "HOST_UNAVAILABLE",
                                "accoreconsole.exe not found on this machine",
                                retryable=True, status="unavailable")

    stamp = _ts()
    run_dir_p = (Path(run_dir) if run_dir else
                 RUNS_DIR / f"command_template_{template_id.replace('.', '_')}_{stamp}")
    run_dir_p = run_dir_p.resolve()
    run_dir_p.mkdir(parents=True, exist_ok=True)

    original_sha_before = sha256_file(src)
    staged = stage_copy(src, template_id)

    # ---- assemble the .scr: sysvars, optional before-probe, template
    # tokens, optional after-probe, optional QSAVE, QUIT ----
    postconds = template.get("postconditions", [])
    has_entity_probe = any(p.get("kind") == "entity_count_probe" for p in postconds)
    before_count_path = run_dir_p / "entity_count_before.txt"
    after_count_path = run_dir_p / "entity_count_after.txt"

    scr_lines = ["FILEDIA", "0", "CMDECHO", "1"]
    if has_entity_probe:
        scr_lines += _entity_count_lisp_lines(str(before_count_path).replace("\\", "/"), "Before")
    scr_lines += tokens
    if has_entity_probe:
        scr_lines += _entity_count_lisp_lines(str(after_count_path).replace("\\", "/"), "After")
    # Always QSAVE the STAGED (disposable) copy before QUIT, regardless of the
    # caller's write_mode. Live-measured (Lane W5-TMPL): accoreconsole hangs on
    # QUIT whenever the in-memory database has any unsaved modification
    # relative to its last save point -- reproduced with a bare LINE command,
    # AUDIT with fix_answer="N", and ARRAYRECT, all fixed by this QSAVE. This
    # does NOT change the write_mode CONTRACT: "read" still means the ORIGINAL
    # is never touched and no persistence is guaranteed/reported to the
    # caller -- only the throwaway staged copy (already gitignored, already
    # discarded after the run) gets flushed to disk so accoreconsole's exit
    # path has nothing pending to hang on. See docs/GOVERNED_COMMAND_TEMPLATES.md
    # section 5 for the root-cause narrative.
    scr_lines.append("_QSAVE")
    scr_lines += ["QUIT", ""]

    scr_path = run_dir_p / f"{template_id.replace('.', '_')}.scr"
    scr_path.write_text("\n".join(scr_lines), encoding="ascii", errors="strict")

    stdout_path = run_dir_p / "accoreconsole_stdout.txt"
    stderr_path = run_dir_p / "accoreconsole_stderr.txt"
    cmd = [engine, "/i", str(staged), "/s", str(scr_path)]
    timed_out = False
    exit_code = None
    with open(stdout_path, "wb") as out_fh, open(stderr_path, "wb") as err_fh:
        try:
            proc = subprocess.run(cmd, cwd=str(staged.parent), stdout=out_fh,
                                   stderr=err_fh, timeout=timeout_sec)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
        except OSError as exc:
            return _error_envelope(env, "HOST_UNAVAILABLE",
                                    f"failed to launch accoreconsole: {exc}",
                                    retryable=True, status="unavailable")

    stdout_text = _read_accoreconsole_stdout(stdout_path)
    original_sha_after = sha256_file(src)
    original_unchanged = (original_sha_before == original_sha_after)

    diagnostics = {
        "exit_code": exit_code,
        "stdout_ref": str(stdout_path),
        "stderr_ref": str(stderr_path),
        "warnings": [],
    }
    details = {
        "template_id": template_id,
        "staged_input": str(staged),
        "original_input": str(src),
        "original_sha256_before": original_sha_before,
        "original_sha256_after": original_sha_after,
        "original_unchanged": original_unchanged,
        "command": cmd,
        "scr_path": str(scr_path),
    }

    if not original_unchanged:
        # H-R8-class safety violation: never mask this behind any other status.
        return _error_envelope(
            env, "ORIGINAL_MUTATED",
            "original DWG sha256 changed during a template run -- this must never happen",
            retryable=False, status="error", details=details,
        )

    if timed_out:
        env["status"] = "error"
        env["diagnostics"] = diagnostics
        env["error"] = {"code": "ACCORECONSOLE_TIMEOUT",
                         "message": f"accoreconsole did not exit within {timeout_sec}s",
                         "retryable": True, "details": details}
        return env

    # ---- postcondition enforcement ----
    before_count = _read_int_file(before_count_path) if has_entity_probe else None
    after_count = _read_int_file(after_count_path) if has_entity_probe else None
    pc_ok, pc_results = evaluate_postconditions(postconds, stdout_text, before_count, after_count)

    exit_clean = (exit_code == 0)
    env["status"] = "ok" if (exit_clean and pc_ok) else "partial"
    env["host"] = {"execution_host_class": "coreconsole",
                    "template_lane": "GOVERNED_COMMAND_TEMPLATE"}
    env["diagnostics"] = diagnostics
    env["result"] = {
        "template_id": template_id,
        "args": args or {},
        "postconditions": pc_results,
        "stdout_tail": "\n".join(
            [ln for ln in stdout_text.splitlines() if ln.strip()][-20:]
        ),
    }
    env["details"] = details
    if env["status"] != "ok":
        env["error"] = {
            "code": "POSTCONDITION_FAILED" if exit_clean else "ROUTE_NONZERO_EXIT",
            "message": "one or more required postconditions did not confirm" if exit_clean
                       else f"accoreconsole exited {exit_code}",
            "retryable": False,
            "details": {"postconditions": pc_results},
        }
    return env


# --------------------------------------------------------------------------- #
# CLI (manual/live testing)
# --------------------------------------------------------------------------- #
def _build_arg_parser():
    import argparse
    ap = argparse.ArgumentParser(description="Run one governed command template.")
    ap.add_argument("template_id")
    ap.add_argument("--dwg", required=True, help="path to the ORIGINAL dwg (never mutated)")
    ap.add_argument("--write-mode", default="read", choices=list(_ALLOWED_WRITE_MODES))
    ap.add_argument("--args-json", default="{}", help="JSON object of slot args")
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--force-unverified", action="store_true",
                     help="bypass the headless_safe gate for live-measurement runs "
                          "(NOT for agent-facing use)")
    return ap


def main(argv=None) -> int:
    ap = _build_arg_parser()
    ns = ap.parse_args(argv)
    args = json.loads(ns.args_json)
    result = run_template(ns.template_id, args, ns.dwg, write_mode=ns.write_mode,
                           run_dir=ns.run_dir, timeout_sec=ns.timeout,
                           _force_unverified=ns.force_unverified)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
