#!/usr/bin/env python
"""certify_headless_safe.py -- staged, evidence-backed template certification gate.

Turns `headless_safe` from a registry bit into a live certification result:
the template must run through cadctl's governed command-template surface,
leave the ORIGINAL DWG byte-identical, and produce a real effect on the staged
copy before the registry may be flipped under `--apply`.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
import re

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parent
CONFIG_DIR = ROUTER_HOME / "config"
TEMPLATES_JSON = CONFIG_DIR / "command_templates.json"

if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import cadctl  # noqa: E402
import command_template_engine as cte  # noqa: E402
import template_live_sweep as tls  # noqa: E402

ENVELOPE_SCHEMA = "ariadne.headless_safe_certification.v1"
CERTIFIED = "CERTIFIED"
NOT_CERTIFIED = "NOT_CERTIFIED"

REASON_CERTIFIED = "CERTIFIED"
REASON_ORIGINAL_SHA_CHANGED = "ORIGINAL_SHA_CHANGED"
REASON_TIMEOUT = "TIMEOUT_ATTENDED_SUSPECT"
REASON_ATTENDED_MARKERS = "ATTENDED_MARKERS_PRESENT"
REASON_CRASH = "CRASH_OR_NONZERO_EXIT"
REASON_NO_STAGED_EFFECT = "NO_STAGED_EFFECT"
REASON_SAMPLE_ARGS = "SAMPLE_ARGS_REQUIRED"

# Interactive-prompt fingerprints in an accoreconsole tail. Deliberately broad: a
# false positive only errs toward NOT_CERTIFIED (conservative/honest), while a miss
# would certify an attended template. Covers the earlier under-inclusive set plus
# singular "Select object", "... to array/trim" variants, generic interactive verbs
# ending a prompt line with a colon, and any "<default>:" bracket prompt.
_ATTENDED_MARKER_PATTERNS = (
    ("Command:", re.compile(r"^\s*Command:\s*$", re.IGNORECASE | re.MULTILINE)),
    # "Select object:", "Select objects:", "Select object to trim:", "Select objects to array:"
    ("Select object(s)", re.compile(r"\bSelect\s+objects?\b.*:\s*$", re.IGNORECASE | re.MULTILINE)),
    ("Enter", re.compile(r"^\s*Enter\b.*:\s*$", re.IGNORECASE | re.MULTILINE)),
    ("Specify", re.compile(r"^\s*Specify\b.*:\s*$", re.IGNORECASE | re.MULTILINE)),
    # generic interactive verbs that end a prompt line with a colon
    ("interactive prompt", re.compile(
        r"^\s*(?:Pick|Remove|Delete|Replace|Overwrite|Erase|Continue|Save\s+changes)\b.*:\s*$",
        re.IGNORECASE | re.MULTILINE)),
    # default-bracket prompt anywhere on a line end: "Continue? <Y>:", "<Yes>:"
    ("default-bracket prompt", re.compile(r"<[^>\n]{1,40}>\s*:\s*$", re.MULTILINE)),
    ("dialog", re.compile(r"\bdialog\b", re.IGNORECASE)),
)


class CertificationSafetyError(RuntimeError):
    """Hard-stop safety violation (original bytes changed)."""

    def __init__(self, envelope: dict):
        self.envelope = envelope
        super().__init__(envelope.get("reason") or "certification safety violation")


def _safe_name(template_id: str) -> str:
    return template_id.replace(".", "_").replace(":", "_")


def envelope_path(out_dir: Path | str, template_id: str) -> Path:
    return Path(out_dir) / f"{_safe_name(template_id)}.certification.json"


def _load_json_doc(path: Path | str):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _templates_of(raw) -> list:
    return raw if isinstance(raw, list) else raw.get("templates", [])


def _iter_template_docs(templates_path: Path | str):
    base = Path(templates_path)
    yield base
    frag_dir = base.parent / (base.stem + cte.FRAGMENT_DIRNAME_SUFFIX)
    if frag_dir.is_dir():
        for frag in sorted(frag_dir.glob("*.json")):
            yield frag


def _find_template_entry(template_id: str, templates_path: Path | str):
    for doc_path in _iter_template_docs(templates_path):
        raw = _load_json_doc(doc_path)
        templates = _templates_of(raw)
        for idx, template in enumerate(templates):
            if template.get("template_id") == template_id:
                return doc_path, raw, templates, idx, template
    raise KeyError(template_id)


def _write_json_style(path: Path | str, doc) -> None:
    path = Path(path)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _repo_relative_ref(router_home: Path | str, target: Path | str) -> str:
    router_home = Path(router_home).resolve()
    target = Path(target).resolve()
    try:
        return target.relative_to(router_home).as_posix()
    except ValueError:
        return str(target)


def _derive_slots(template: dict, sample_args):
    if sample_args is not None:
        return dict(sample_args), None
    derived, note = tls.derive_sample_args(template)
    return derived, note


def _load_template_registry(router_home: Path | str = ROUTER_HOME) -> dict[str, dict]:
    return cte.load_templates(Path(router_home) / "config" / "command_templates.json")


def uncertified_template_ids(router_home: Path | str = ROUTER_HOME) -> list[str]:
    templates = _load_template_registry(router_home)
    return sorted(tid for tid, template in templates.items() if not template.get("headless_safe"))


def _clone_router_with_forced_template(router_home: Path | str, template_id: str) -> Path:
    router_home = Path(router_home)
    temp_root = Path(tempfile.mkdtemp(prefix="certify_headless_safe_"))
    config_dir = temp_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    base = router_home / "config" / "command_templates.json"
    shutil.copy2(base, config_dir / "command_templates.json")
    frag_dir = router_home / "config" / "command_templates.d"
    temp_frag_dir = config_dir / "command_templates.d"
    if frag_dir.is_dir():
        shutil.copytree(frag_dir, temp_frag_dir)

    temp_templates = config_dir / "command_templates.json"
    doc_path, raw, templates, idx, _template = _find_template_entry(template_id, temp_templates)
    templates[idx]["headless_safe"] = True
    _write_json_style(doc_path, raw)
    return temp_root


def _read_stdout_text(path: str | None) -> str:
    if not path:
        return ""
    return cte._read_accoreconsole_stdout(Path(path))


def _read_stderr_text(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    # accoreconsole emits UTF-16LE; reuse the stdout decoder (NUL-ratio heuristic with
    # UTF-8 fallback) so UTF-16 attended markers on stderr are not silently missed.
    return cte._read_accoreconsole_stdout(p)


def _tail_text(text: str, limit: int = 20) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-limit:])


def _find_attended_markers(stdout_path: str | None, stderr_path: str | None) -> list[str]:
    stdout_tail = _tail_text(_read_stdout_text(stdout_path))
    stderr_tail = _tail_text(_read_stderr_text(stderr_path))
    haystack = "\n".join(part for part in (stdout_tail, stderr_tail) if part)
    markers: list[str] = []
    for label, pattern in _ATTENDED_MARKER_PATTERNS:
        if pattern.search(haystack):
            markers.append(label)
    return markers


def _produce_ir(cad, dwg_path: str | Path, ir_dir: str | Path) -> tuple[str | None, str | None]:
    """Extract a native-full IR of dwg_path via cad.inspect (stages a COPY; original
    untouched). Returns (ir_file_path, error_note). include_rich routes the ObjectARX
    native inspect.database.graph op so surface/table/block entities are captured, not
    just geometry -- required so a surf*/array create registers as an added handle."""
    ir_dir = Path(ir_dir)
    ir_dir.mkdir(parents=True, exist_ok=True)
    env = cad.inspect(str(dwg_path), str(ir_dir), mode="graph", include_rich=True)
    status = env.get("status") if isinstance(env, dict) else None
    ir_file = ir_dir / "dwg_graph_ir.json"
    if status != "ok" or not ir_file.is_file():
        return None, f"inspect status={status!r}, ir_present={ir_file.is_file()}"
    return str(ir_file), None


def _as_count(value) -> int:
    """Fail-closed integer coercion for a diff-summary count: a non-numeric or
    negative value yields 0 (never inflates the change total into a false effect)."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    return n if n > 0 else 0


def _structural_effect(cad, *, original_dwg: str | Path, staged_result: str | None,
                       out_dir: str | Path, baseline_ir: str | None = None,
                       tag: str = "adhoc") -> dict:
    """QSAVE-immune logical effect signal.

    Whole-file DWG sha is non-discriminating: command_template_engine.run_template
    unconditionally _QSAVEs, and QSAVE rewrites volatile header bytes (timestamp +
    next-handle seed) on EVERY save -- so a raw-sha delta is always True even for a
    logical no-op (finding 6). Instead, diff the ORIGINAL (== pristine staged input)
    against the post-template staged_result via the router's handle-based IR diff:
    existing entity handles are preserved across a save, so only genuinely
    added/removed/modified entities move the summary. Fail-closed -- any inspect/diff
    failure yields effect_took=False WITH an explanatory note, never a silent True.

    Per-template IR artifacts are written under out_dir/_ir/<tag>/{before,after} so the
    evidence trail survives a batch (a shared fixed path would let one template's IR be
    overwritten by the next, and a future inspect-cache could serve a stale file).
    """
    base = {"effect_took": False, "basis": "logical_ir_diff", "summary": None, "note": None}
    if not (isinstance(staged_result, str) and staged_result and Path(staged_result).is_file()):
        base["note"] = "no staged_result file to inspect"
        return base
    ir_root = Path(out_dir) / "_ir" / (tag or "adhoc")
    pre_ir = baseline_ir
    if pre_ir is None:
        pre_ir, err = _produce_ir(cad, original_dwg, ir_root / "before")
        if pre_ir is None:
            base["note"] = f"pre-IR unavailable: {err}"
            return base
    post_ir, err = _produce_ir(cad, staged_result, ir_root / "after")
    if post_ir is None:
        base["note"] = f"post-IR unavailable: {err}"
        return base
    diff = cad.diff_before_after(pre_ir, post_ir)
    if (not isinstance(diff, dict) or "summary" not in diff
            or diff.get("status") in ("blocked", "not_implemented", "error")):
        status = diff.get("status") if isinstance(diff, dict) else "n/a"
        base["note"] = f"diff unavailable: status={status!r}"
        return base
    summ = diff.get("summary") or {}
    changed = (_as_count(summ.get("added"))
               + _as_count(summ.get("removed"))
               + _as_count(summ.get("modified")))
    base["effect_took"] = changed > 0
    base["summary"] = {k: summ.get(k) for k in (
        "added", "removed", "modified", "entity_count_before", "entity_count_after")}
    if changed == 0:
        base["note"] = "logical IR diff empty (no added/removed/modified entities)"
    return base


def _extract_result_dict(cad_env: dict) -> dict:
    result = cad_env.get("result")
    return result if isinstance(result, dict) else {}


def _extract_details(cad_env: dict) -> dict:
    details = _extract_result_dict(cad_env).get("details")
    return details if isinstance(details, dict) else {}


def _extract_error(cad_env: dict) -> dict:
    err = _extract_result_dict(cad_env).get("error")
    return err if isinstance(err, dict) else {}


def _extract_exit_code(cad_env: dict):
    diagnostics = _extract_result_dict(cad_env).get("diagnostics")
    if isinstance(diagnostics, dict):
        return diagnostics.get("exit_code")
    return None


def _looks_like_timeout(cad_env: dict) -> bool:
    texts = [
        str(cad_env.get("reason") or ""),
        str(_extract_error(cad_env).get("code") or ""),
        str(_extract_error(cad_env).get("message") or ""),
    ]
    combined = " ".join(texts).lower()
    return (
        "accoreconsole_timeout" in combined
        or "timed out" in combined
        or "timeout" in combined
        or "did not exit within" in combined
    )


def _build_evidence_paths(envelope_file: Path, cad_env: dict, staged_result: str | None) -> dict:
    evidence = {"envelope": str(envelope_file.resolve())}
    for key in ("stdout", "stderr", "staged_copy"):
        val = cad_env.get(key)
        if val:
            evidence[key] = str(val)
    if staged_result:
        evidence["staged_result"] = staged_result
    return evidence


def _classify_verdict(cad_env: dict, *, effect_took: bool,
                      attended_markers: list[str]) -> tuple[str, str]:
    status = cad_env.get("status")
    exit_code = _extract_exit_code(cad_env)
    if _looks_like_timeout(cad_env):
        return NOT_CERTIFIED, REASON_TIMEOUT
    if attended_markers:
        return NOT_CERTIFIED, REASON_ATTENDED_MARKERS
    if status != "ok" or exit_code != 0:
        return NOT_CERTIFIED, REASON_CRASH
    if not effect_took:
        return NOT_CERTIFIED, REASON_NO_STAGED_EFFECT
    return CERTIFIED, REASON_CERTIFIED


def _build_sample_args_envelope(template_id: str, out_dir: Path, *, note: str,
                                timeout_sec: float) -> dict:
    env_path = envelope_path(out_dir, template_id)
    envelope = {
        "schema": ENVELOPE_SCHEMA,
        "template_id": template_id,
        "verdict": NOT_CERTIFIED,
        "reason": f"{REASON_SAMPLE_ARGS}: {note}",
        "exit_code": None,
        "original_sha256_before": None,
        "original_sha256_after": None,
        "original_unchanged": True,
        "staged_input_sha256": None,
        "staged_result_sha256": None,
        "staged_whole_file_sha_changed": False,
        "effect_took": False,
        "effect_basis": "logical_ir_diff",
        "effect_diff_summary": None,
        "effect_note": "not run: sample args unavailable",
        "attended_markers": [],
        "elapsed_sec": 0.0,
        "timeout_sec": timeout_sec,
        "evidence_paths": {"envelope": str(env_path.resolve())},
    }
    _write_json_style(env_path, envelope)
    return envelope


def certify(template_id: str, dwg_path: str | Path, out_dir: str | Path,
            timeout_sec: float, sample_args=None, *,
            router_home: Path | str = ROUTER_HOME,
            cad_factory=None, baseline_ir: str | None = None) -> dict:
    """Run one live certification and persist its envelope."""
    router_home = Path(router_home)
    dwg_path = Path(dwg_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    templates = _load_template_registry(router_home)
    template = templates[template_id]
    slots, sample_note = _derive_slots(template, sample_args)
    if slots is None:
        return _build_sample_args_envelope(
            template_id, out_dir, note=sample_note or "sample args unavailable",
            timeout_sec=timeout_sec,
        )

    original_sha_before = tls.sha256_file(dwg_path)
    temp_router_home = None
    try:
        # minor 9: clone happens INSIDE the try so a clone failure cannot leak the temp dir.
        cad_router_home = router_home
        if not template.get("headless_safe"):
            temp_router_home = _clone_router_with_forced_template(router_home, template_id)
            cad_router_home = temp_router_home

        started = time.monotonic()
        cad = cad_factory(cad_router_home) if cad_factory else cadctl.Cad(cad_router_home)
        # finding 5: forward the wall-clock budget to the engine's accoreconsole timeout.
        cad_env = cad.run_command_template(
            template_id, slots, dwg=str(dwg_path), timeout_sec=timeout_sec)
        elapsed_sec = time.monotonic() - started

        original_sha_after = tls.sha256_file(dwg_path)
        original_unchanged = (
            original_sha_before == original_sha_after
            and cad_env.get("original_unchanged") is not False
        )

        details = _extract_details(cad_env)
        staged_result = cad_env.get("staged_copy") or details.get("staged_input")
        # Whole-file staged shas are recorded as EVIDENCE ONLY (non-authoritative: QSAVE
        # churns header bytes on every save -> a raw delta is meaningless, finding 6).
        staged_result_sha256 = None
        if isinstance(staged_result, str) and staged_result and Path(staged_result).is_file():
            staged_result_sha256 = tls.sha256_file(staged_result)
        staged_input_sha256 = original_sha_before if staged_result else None
        staged_whole_file_sha_changed = bool(
            staged_input_sha256 and staged_result_sha256
            and staged_input_sha256 != staged_result_sha256
        )
        # finding 6: the AUTHORITATIVE effect signal is the router's handle-based logical
        # IR diff of original vs staged_result (QSAVE-immune). Fail-closed. Skip the probe
        # entirely once an original mutation is detected -- that is an overriding safety
        # stop, and no further CAD work should be spent on the fixture.
        if original_unchanged:
            effect = _structural_effect(
                cad, original_dwg=dwg_path, staged_result=staged_result,
                out_dir=out_dir, baseline_ir=baseline_ir, tag=_safe_name(template_id),
            )
        else:
            effect = {"effect_took": False, "basis": "logical_ir_diff", "summary": None,
                      "note": "skipped: original mutated (safety stop)"}
        effect_took = effect["effect_took"]
        attended_markers = _find_attended_markers(
            cad_env.get("stdout"),
            cad_env.get("stderr"),
        )
        verdict, reason = _classify_verdict(
            cad_env,
            effect_took=effect_took,
            attended_markers=attended_markers,
        )
        if not original_unchanged:
            verdict = NOT_CERTIFIED
            reason = REASON_ORIGINAL_SHA_CHANGED

        env_path = envelope_path(out_dir, template_id)
        envelope = {
            "schema": ENVELOPE_SCHEMA,
            "template_id": template_id,
            "verdict": verdict,
            "reason": reason,
            "exit_code": _extract_exit_code(cad_env),
            "original_sha256_before": original_sha_before,
            "original_sha256_after": original_sha_after,
            "original_unchanged": original_unchanged,
            "staged_input_sha256": staged_input_sha256,
            "staged_result_sha256": staged_result_sha256,
            "staged_whole_file_sha_changed": staged_whole_file_sha_changed,
            "effect_took": effect_took,
            "effect_basis": effect["basis"],
            "effect_diff_summary": effect["summary"],
            "effect_note": effect["note"],
            "attended_markers": attended_markers,
            "elapsed_sec": round(elapsed_sec, 6),
            "timeout_sec": timeout_sec,
            "evidence_paths": _build_evidence_paths(env_path, cad_env, staged_result),
        }
        _write_json_style(env_path, envelope)
        if not original_unchanged:
            raise CertificationSafetyError(envelope)
        return envelope
    finally:
        if temp_router_home is not None:
            shutil.rmtree(temp_router_home, ignore_errors=True)


def _flip_headless_safe_text(text: str) -> tuple[str, bool]:
    """Flip the single `"headless_safe": false` -> true in place (single-template
    doc). Returns (text, ok); ok is False unless exactly one occurrence was flipped."""
    new, n = re.subn(r'("headless_safe"\s*:\s*)false\b', r"\1true", text, count=1)
    return new, (n == 1)


def _append_evidence_ref_text(text: str, new_ref: str) -> tuple[str, bool, str | None]:
    """Append new_ref to an EXISTING evidence_refs array in place, preserving the
    array's hand-authored single/multi-line style and the file's newline. Returns
    (text, changed, reason); reason is set (changed False) when the array is
    absent/unparseable/already-present."""
    m = re.search(r'("evidence_refs"\s*:\s*)(\[.*?\])', text, re.DOTALL)
    if not m:
        return text, False, "no_array"
    arr_text = m.group(2)
    try:
        arr = json.loads(arr_text)
    except Exception:
        return text, False, "unparseable"
    if not isinstance(arr, list):
        return text, False, "not_a_list"
    if new_ref in arr:
        return text, False, "duplicate"
    items = arr + [new_ref]
    if "\n" in arr_text:
        nl = "\r\n" if "\r\n" in arr_text else "\n"
        entry_m = re.search(r"[\r\n]([ \t]+)\"", arr_text)
        indent = entry_m.group(1) if entry_m else "        "
        close_m = re.search(r"[\r\n]([ \t]*)\]\s*$", arr_text)
        close_indent = close_m.group(1) if close_m else "      "
        body = (","+ nl).join(indent + json.dumps(i, ensure_ascii=False) for i in items)
        new_arr = "[" + nl + body + nl + close_indent + "]"
    else:
        new_arr = "[" + ", ".join(json.dumps(i, ensure_ascii=False) for i in items) + "]"
    new_text = text[:m.start(2)] + new_arr + text[m.end(2):]
    return new_text, True, None


def apply_certification(template_id: str, envelope: dict, *,
                        router_home: Path | str = ROUTER_HOME) -> bool:
    """Flip headless_safe=true (+ append the certification evidence_ref) only for a
    CERTIFIED envelope.

    The registry document is edited IN PLACE as text so a fragment's hand-authored
    compact-array formatting is preserved -- a whole-doc re-dump would reflow every
    array on each --apply (collateral diff; the arrays are compact-single-line for
    some keys and multi-line for others, which no mechanical serializer reproduces).
    Falls back to a structure-level re-dump ONLY when the surgical edit is not safely
    applicable (a multi-template doc, or a template with no evidence_refs array), and
    says so on stderr -- never a silent reformat."""
    if envelope.get("verdict") != CERTIFIED:
        return False

    router_home = Path(router_home)
    templates_path = router_home / "config" / "command_templates.json"
    doc_path, raw, templates, idx, template = _find_template_entry(template_id, templates_path)

    evidence_ref = _repo_relative_ref(router_home, envelope["evidence_paths"]["envelope"])
    already_safe = bool(template.get("headless_safe"))
    existing_refs = template.get("evidence_refs")
    has_refs_array = isinstance(existing_refs, list)
    already_ref = has_refs_array and evidence_ref in existing_refs
    if already_safe and already_ref:
        return False

    # Surgical, style-preserving path: single-template doc with an existing
    # evidence_refs array (the certification-fragment shape).
    if len(templates) == 1 and has_refs_array:
        with open(doc_path, "r", encoding="utf-8-sig", newline="") as fh:
            text = fh.read()
        ok = True
        if not already_safe:
            text, ok = _flip_headless_safe_text(text)
        if ok and not already_ref:
            text, ok, _reason = _append_evidence_ref_text(text, evidence_ref)
        if ok:
            with open(doc_path, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
            return True
        # fall through to the structural re-dump if the surgical edit did not apply

    print(
        f"[apply_certification] NOTE: structural re-dump of {doc_path} "
        f"(style-preserving edit not applicable: templates={len(templates)}, "
        f"has_evidence_refs={has_refs_array}); array formatting may reflow.",
        file=sys.stderr,
    )
    changed = False
    if not already_safe:
        templates[idx]["headless_safe"] = True
        changed = True
    if not has_refs_array:
        existing_refs = []
        templates[idx]["evidence_refs"] = existing_refs
        changed = True
    if evidence_ref not in existing_refs:
        existing_refs.append(evidence_ref)
        changed = True
    if changed:
        _write_json_style(doc_path, raw)
    return changed


def _is_safety_envelope(envelope: dict) -> bool:
    return (
        envelope.get("reason") == REASON_ORIGINAL_SHA_CHANGED
        or envelope.get("original_unchanged") is False
    )


def _apply_trust_check(envelope: dict, template_id: str,
                       dwg_path: str | Path) -> tuple[bool, str | None]:
    """Guard the registry flip against an untrusted / stale / wrong-fixture envelope.

    run_batch resumes a CERTIFIED envelope from disk WITHOUT re-running CAD (by design),
    and --apply would otherwise flip headless_safe=true on nothing but that file's verdict
    string -- so `--dwg <anything> --out-dir <dir-with-a-CERTIFIED-envelope> --apply` could
    flip the registry with zero CAD in the invocation. Before honoring a CERTIFIED envelope
    for apply, require that its identity + the fixture it was certified against match THIS
    invocation: schema, template_id, and original_sha256_before == sha256 of the current
    --dwg. Any mismatch refuses the flip."""
    if envelope.get("schema") != ENVELOPE_SCHEMA:
        return False, f"schema mismatch ({envelope.get('schema')!r})"
    if envelope.get("template_id") != template_id:
        return False, f"template_id mismatch ({envelope.get('template_id')!r} != {template_id!r})"
    recorded = envelope.get("original_sha256_before")
    try:
        actual = tls.sha256_file(dwg_path)
    except OSError as exc:
        return False, f"cannot read --dwg to verify sha ({exc})"
    if not recorded or recorded != actual:
        return False, (f"fixture sha mismatch (envelope {str(recorded)[:16]}... "
                       f"!= --dwg {actual[:16]}...)")
    return True, None


def run_batch(template_ids: list[str], *, dwg_path: str | Path, out_dir: str | Path,
              timeout_sec: float, apply: bool = False, force: bool = False,
              router_home: Path | str = ROUTER_HOME, cad_factory=None) -> tuple[list[dict], int]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # angle-4 defense: the fixture must not drift mid-batch. A corruption during
    # template A's run must not be silently adopted as template B's "pristine" baseline
    # (certify recomputes original_sha_before per call, so a loud stop has to live here).
    try:
        batch_baseline_sha = tls.sha256_file(dwg_path)
    except OSError:
        batch_baseline_sha = None

    # Compute the ORIGINAL fixture's baseline IR once for the whole batch (same fixture,
    # immutable) so per-template certify only inspects its own staged_result + diffs.
    # Only pay for it if at least one template will actually run live (a full resume
    # from existing envelopes needs no CAD at all). Best-effort: a failure leaves
    # baseline_ir=None and each certify re-derives its own pre-IR.
    needs_run = force or any(
        not envelope_path(out_dir, tid).is_file() for tid in template_ids)
    baseline_ir = None
    if needs_run:
        try:
            _cad = cad_factory(router_home) if cad_factory else cadctl.Cad(router_home)
            baseline_ir, _base_err = _produce_ir(_cad, Path(dwg_path), out_dir / "_ir_baseline")
        except Exception:
            baseline_ir = None

    envelopes: list[dict] = []
    overall_exit = 0

    for template_id in template_ids:
        if batch_baseline_sha is not None:
            try:
                now_sha = tls.sha256_file(dwg_path)
            except OSError:
                now_sha = None
            if now_sha is not None and now_sha != batch_baseline_sha:
                print(f"[run_batch] HARD STOP: fixture {dwg_path} changed mid-batch "
                      f"({batch_baseline_sha[:16]}... -> {now_sha[:16]}...); refusing further work",
                      file=sys.stderr)
                overall_exit = 2
                break
        env_path = envelope_path(out_dir, template_id)
        if env_path.is_file() and not force:
            envelope = _load_json_doc(env_path)
        else:
            try:
                envelope = certify(
                    template_id, dwg_path, out_dir, timeout_sec,
                    router_home=router_home, cad_factory=cad_factory,
                    baseline_ir=baseline_ir,
                )
            except CertificationSafetyError as exc:
                envelope = exc.envelope
            except Exception as exc:  # minor 10: one certify blowup must not abort the batch
                envelope = {
                    "schema": ENVELOPE_SCHEMA,
                    "template_id": template_id,
                    "verdict": NOT_CERTIFIED,
                    "reason": f"CERTIFY_ERROR: {type(exc).__name__}: {exc}",
                    "evidence_paths": {},
                }
                _write_json_style(env_path, envelope)

        if apply and envelope.get("verdict") == CERTIFIED:
            trust_ok, trust_reason = _apply_trust_check(envelope, template_id, dwg_path)
            if trust_ok:
                apply_certification(template_id, envelope, router_home=router_home)
            else:
                envelope["apply_refused_reason"] = trust_reason
                print(f"[run_batch] REFUSED --apply of {template_id}: {trust_reason}",
                      file=sys.stderr)
                if overall_exit < 1:
                    overall_exit = 1

        envelopes.append(envelope)

        if _is_safety_envelope(envelope):
            overall_exit = 2
            break
        if envelope.get("verdict") != CERTIFIED and overall_exit < 1:
            overall_exit = 1

    return envelopes, overall_exit


def _parse_templates_arg(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--templates", help="comma-separated template ids")
    group.add_argument("--all-uncertified", action="store_true",
                       help="certify every template whose headless_safe is false")
    ap.add_argument("--dwg", required=True, help="original DWG path (never mutated)")
    ap.add_argument("--out-dir", required=True, help="envelope output directory")
    ap.add_argument("--timeout-sec", type=float, required=True, help="per-template timeout")
    ap.add_argument("--apply", action="store_true",
                    help="flip headless_safe=true only when verdict==CERTIFIED")
    ap.add_argument("--force", action="store_true",
                    help="re-run even when an envelope already exists")
    return ap


def main(argv: list[str] | None = None) -> int:
    ns = _build_arg_parser().parse_args(argv)
    if ns.all_uncertified:
        template_ids = uncertified_template_ids()
    else:
        template_ids = _parse_templates_arg(ns.templates)

    envelopes, exit_code = run_batch(
        template_ids,
        dwg_path=ns.dwg,
        out_dir=ns.out_dir,
        timeout_sec=ns.timeout_sec,
        apply=ns.apply,
        force=ns.force,
    )
    for envelope in envelopes:
        print(json.dumps(envelope, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
