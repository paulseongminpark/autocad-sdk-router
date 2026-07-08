#!/usr/bin/env python
"""template_live_sweep.py -- governed-template live-proof driver (Lane W5-TMPL).

WHY this exists:
  config/command_templates.d/ holds drop-in governed command templates (utf-8-sig
  JSON fragments). Most are catalogued but not yet live-measured. An orchestrator
  runs the live sweep on a machine with accoreconsole; this module is the
  offline-safe driver + plan emitter that mirrors cadctl.Cad.run_command_template
  validation exactly (closed registry, hostile-slot refusal, write_original
  impossible) without inventing a parallel schema.

Two modes:
  --plan (default): enumerate the full governed template surface cadctl can
      dispatch (base registry + command_templates.d/ drop-ins), validate each
      template against the same contract cadctl uses, and emit note rows for
      fragment files that intentionally declare zero templates. Zero AutoCAD
      interaction.
  --live --dwg <path> --out-dir <dir>: execute each template through
      cadctl.Cad().run_command_template (never shell out to accoreconsole
      directly) against a STAGED COPY of the supplied DWG; per-template envelope
      on disk; resumable (skip when envelope already exists); fail-loud summary
      exit 0=all ok / 1=any error / 2=any refusal.

Stdlib only (+ sibling cadctl / command_template_engine imports).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parent
CONFIG_DIR = ROUTER_HOME / "config"
FRAGMENT_DIR = CONFIG_DIR / "command_templates.d"
TEMPLATES_JSON = CONFIG_DIR / "command_templates.json"

if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import command_template_engine as cte  # noqa: E402
import cadctl  # noqa: E402

PLAN_SCHEMA = "ariadne.template_live_sweep.plan.v1"
ENVELOPE_SCHEMA = "ariadne.template_live_sweep.envelope.v1"
SUMMARY_SCHEMA = "ariadne.template_live_sweep.summary.v1"

_ALLOWED_WRITE_MODES = frozenset(cte._ALLOWED_WRITE_MODES)
_REFUSAL_STATUSES = frozenset({"blocked", "not_found", "not_implemented"})


class SweepError(Exception):
    """Driver-level abort (e.g. original DWG mutated)."""


def sha256_file(path: Path | str) -> str:
    """Return hex sha256 of a file (byte-exact original-unchanged assert)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_name(template_id: str) -> str:
    return template_id.replace(".", "_").replace(":", "_")


def _templates_of(raw) -> list:
    return raw if isinstance(raw, list) else raw.get("templates", [])


def enumerate_fragment_files(frag_dir: Path | str = FRAGMENT_DIR) -> list[Path]:
    """Sorted list of drop-in fragment JSON paths (deterministic sweep order)."""
    frag_dir = Path(frag_dir)
    if not frag_dir.is_dir():
        return []
    return sorted(frag_dir.glob("*.json"))


def _fragment_rel_path(frag_path: Path, router_home: Path) -> str:
    try:
        rel = frag_path.resolve().relative_to((router_home / "config").resolve())
        return rel.as_posix()
    except ValueError:
        return frag_path.name


def _load_json_doc(path: Path | str):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def derive_required_args(template: dict) -> list[str]:
    """Slots referenced by command_sequence that have no registry default."""
    slots = template.get("slots") or {}
    required: list[str] = []
    for step in template.get("command_sequence") or []:
        if "slot" not in step:
            continue
        slot_name = step["slot"]
        slot_def = slots.get(slot_name) or {}
        if "default" not in slot_def:
            required.append(slot_name)
    return required


def derive_sample_args(template: dict) -> tuple[dict | None, str | None]:
    """Build honest sample slot values from registry defaults/examples only.

    Returns (sample_args, note). note is set when some slots cannot be derived
    offline (staged_path) or when nothing is derivable for a slotted template.
    """
    slots = template.get("slots") or {}
    used: list[str] = []
    for step in template.get("command_sequence") or []:
        if "slot" in step:
            used.append(step["slot"])

    if not used:
        return {}, None

    sample: dict = {}
    notes: list[str] = []
    for slot_name in used:
        slot_def = slots.get(slot_name)
        if not slot_def:
            notes.append(f"{slot_name}: undeclared slot referenced by command_sequence")
            continue
        if "default" in slot_def:
            sample[slot_name] = slot_def["default"]
            continue
        stype = slot_def.get("type")
        if stype == "enum" and slot_def.get("values"):
            sample[slot_name] = slot_def["values"][0]
        elif stype == "int_range":
            sample[slot_name] = slot_def.get("min", 1)
        elif stype == "float_range":
            sample[slot_name] = slot_def.get("min", 0.0)
        elif stype == "name_token":
            sample[slot_name] = "SampleToken"
        elif stype == "point2":
            sample[slot_name] = "0,0"
        elif stype == "staged_path":
            # Engine-supplied: run_template auto-fills staged_path slots with its
            # own freshly-staged copy path (cert wave 2 wiring); nothing to derive
            # here and its absence from the sample must NOT block the template.
            continue
        else:
            notes.append(f"{slot_name}: no default/example derivable in registry")

    note = "; ".join(notes) if notes else None
    if not sample and notes:
        return None, note
    return sample, note


def commands_or_action_summary(template: dict) -> str:
    """Human-readable action summary for plan rows."""
    summary = template.get("summary")
    if summary:
        return str(summary)
    parts: list[str] = []
    for step in template.get("command_sequence") or []:
        if "literal" in step:
            lit = step["literal"]
            parts.append(f'"{lit}"' if lit else '""')
        elif "slot" in step:
            parts.append(f"<{step['slot']}>")
    if parts:
        return " ".join(parts)
    if template.get("command"):
        return str(template["command"])
    return template.get("template_id", "(unknown template)")


def expected_assertions(template: dict) -> list[dict]:
    """Declared postconditions as plan-time expected assertions (no execution)."""
    out: list[dict] = []
    for pc in template.get("postconditions") or []:
        entry = {"kind": pc.get("kind")}
        if pc.get("description"):
            entry["description"] = pc["description"]
        if pc.get("required") is not None:
            entry["required"] = pc["required"]
        if pc.get("expect_unchanged") is not None:
            entry["expect_unchanged"] = pc["expect_unchanged"]
        if pc.get("expect_increase") is not None:
            entry["expect_increase"] = pc["expect_increase"]
        if "expect_baseline" in pc:
            entry["expect_baseline"] = pc["expect_baseline"]
        if pc.get("pattern"):
            entry["pattern"] = pc["pattern"]
        if pc.get("bind"):
            entry["bind"] = pc["bind"]
        out.append(entry)
    return out


def _validate_write_mode(template: dict) -> str | None:
    """Mirror command_template_engine._ingest_templates write_mode guard."""
    tid = template.get("template_id", "<unknown>")
    allowed = (template.get("write_mode") or {}).get("allowed") or []
    bad = [m for m in allowed if m not in _ALLOWED_WRITE_MODES]
    if bad:
        return (
            f"template {tid!r} declares disallowed write_mode(s) {bad!r} "
            f"(only {sorted(_ALLOWED_WRITE_MODES)} permitted)"
        )
    default = (template.get("write_mode") or {}).get("default") or "read"
    if default not in allowed:
        return f"template {tid!r} write_mode default {default!r} not in allowed {allowed!r}"
    return None


def _validate_command_sequence(template: dict) -> str | None:
    """Structural checks before render_script (registry shape)."""
    tid = template.get("template_id", "<unknown>")
    seq = template.get("command_sequence")
    if not seq:
        return f"template {tid!r} missing command_sequence"
    slots = template.get("slots") or {}
    for step in seq:
        if "literal" in step or "slot" in step:
            if "slot" in step:
                slot_name = step["slot"]
                if slot_name not in slots:
                    return (
                        f"template {tid!r} command_sequence references "
                        f"undeclared slot {slot_name!r}"
                    )
            continue
        return f"template {tid!r} command_sequence step {step!r} has neither literal nor slot"
    return None


def validate_template_contract(
    template: dict,
    merged_registry: dict[str, dict],
    *,
    require_merged: bool = True,
) -> tuple[str, str | None]:
    """Validate one template against the cadctl / command_template_engine contract.

    Returns (validation_status, validation_reason) where validation_status is
    'ok' or 'refused'. Mirrors the refusal surfaces cadctl.run_command_template
    depends on: closed registry membership, write_mode safety, slot rendering.
    """
    tid = template.get("template_id")
    if not tid:
        return "refused", "missing template_id"

    wm_err = _validate_write_mode(template)
    if wm_err:
        return "refused", wm_err

    seq_err = _validate_command_sequence(template)
    if seq_err:
        return "refused", seq_err

    if require_merged and tid not in merged_registry:
        return "refused", f"template {tid!r} is not in command_templates.json merged registry"

    merged = merged_registry.get(tid, template)

    sample_args, _note = derive_sample_args(merged)
    if sample_args is not None:
        try:
            cte.render_script(merged, sample_args)
        except cte.TemplateError as exc:
            return "refused", f"{exc.code}: {exc.message}"

    return "ok", None


def load_merged_registry(templates_json: Path | str) -> dict[str, dict]:
    """Load the full governed registry (base + .d/ fragments)."""
    return cte.load_templates(templates_json)


def _build_note_row(
    source_path: Path,
    router_home: Path,
    *,
    provenance: str,
    validation_status: str,
    validation_reason: str,
) -> dict:
    return {
        "schema": PLAN_SCHEMA,
        "template_id": None,
        "file": _fragment_rel_path(source_path, router_home),
        "provenance": provenance,
        "validation_status": validation_status,
        "validation_reason": validation_reason,
        "commands_or_action_summary": None,
        "required_args": [],
        "sample_args": None,
        "sample_args_note": None,
        "expected_assertions": [],
    }


def build_plan_row(
    template: dict,
    source_path: Path,
    router_home: Path,
    merged_registry: dict[str, dict],
    *,
    provenance: str = "fragment_declared",
    validation_status: str | None = None,
    validation_reason: str | None = None,
) -> dict:
    """One JSONL plan row for a single governed template."""
    tid = template["template_id"]
    merged = merged_registry.get(tid, template)
    if validation_status is None:
        validation_status, validation_reason = validate_template_contract(
            template, merged_registry,
        )
    sample_args, sample_args_note = derive_sample_args(merged)
    return {
        "schema": PLAN_SCHEMA,
        "template_id": tid,
        "file": _fragment_rel_path(source_path, router_home),
        "provenance": provenance,
        "validation_status": validation_status,
        "validation_reason": validation_reason,
        "commands_or_action_summary": commands_or_action_summary(merged),
        "required_args": derive_required_args(merged),
        "sample_args": sample_args,
        "sample_args_note": sample_args_note,
        "expected_assertions": expected_assertions(merged),
    }


def run_plan(
    *,
    router_home: Path | str = ROUTER_HOME,
    frag_dir: Path | str | None = None,
    templates_json: Path | str | None = None,
) -> list[dict]:
    """Enumerate the full governed template surface and emit plan rows."""
    router_home = Path(router_home)
    frag_dir = Path(frag_dir) if frag_dir else router_home / "config" / "command_templates.d"
    templates_json = Path(templates_json) if templates_json else router_home / "config" / "command_templates.json"

    merged_registry: dict[str, dict] = {}
    registry_error: str | None = None
    try:
        merged_registry = load_merged_registry(templates_json)
    except cte.TemplateError as exc:
        registry_error = f"{exc.code}: {exc.message}"

    rows: list[dict] = []
    fragment_declared_ids: set[str] = set()
    for frag_path in enumerate_fragment_files(frag_dir):
        try:
            raw = _load_json_doc(frag_path)
        except (OSError, json.JSONDecodeError) as exc:
            rows.append(_build_note_row(
                frag_path,
                router_home,
                provenance="fragment_parse_error",
                validation_status="refused",
                validation_reason=f"fragment parse error: {type(exc).__name__}: {exc}",
            ))
            continue

        templates = _templates_of(raw)
        if not templates:
            notice = raw.get("notice") if isinstance(raw, dict) else None
            rows.append(_build_note_row(
                frag_path,
                router_home,
                provenance="fragment_duplicate_guard",
                validation_status="skipped_with_reason",
                validation_reason=(
                    str(notice)
                    if notice
                    else "fragment declares zero templates; likely a duplicate-guard stub"
                ),
            ))
            continue

        for template in templates:
            if not template.get("template_id"):
                rows.append(_build_note_row(
                    frag_path,
                    router_home,
                    provenance="fragment_invalid_entry",
                    validation_status="refused",
                    validation_reason="template entry missing template_id",
                ))
                continue
            tid = template["template_id"]
            fragment_declared_ids.add(tid)
            validation_status, validation_reason = validate_template_contract(
                template,
                merged_registry,
                require_merged=registry_error is None,
            )
            if validation_status == "ok" and registry_error:
                validation_status = "refused"
                validation_reason = f"registry load refused: {registry_error}"
            rows.append(build_plan_row(
                template,
                frag_path,
                router_home,
                merged_registry,
                provenance="fragment_declared",
                validation_status=validation_status,
                validation_reason=validation_reason,
            ))

    if registry_error is None:
        for template in _templates_of(_load_json_doc(templates_json)):
            tid = template.get("template_id")
            if not tid or tid in fragment_declared_ids or tid not in merged_registry:
                continue
            rows.append(build_plan_row(
                template,
                templates_json,
                router_home,
                merged_registry,
                provenance="base_registry",
            ))
    return rows


def write_jsonl(rows: list[dict], out_path: Path | str) -> None:
    """Atomic UTF-8 JSONL write (flush+fsync, crash-safe)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False))
            fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(out_path)


def emit_jsonl(rows: list[dict], out_stream) -> None:
    """Write plan rows to a text stream (stdout default)."""
    for row in rows:
        out_stream.write(json.dumps(row, ensure_ascii=False))
        out_stream.write("\n")


def envelope_path(out_dir: Path | str, template_id: str) -> Path:
    return Path(out_dir) / f"{_safe_name(template_id)}.envelope.json"


def status_to_exit_code(status: str, *, original_unchanged: bool = True) -> int:
    """Map cadctl status to per-template exit_code (0 ok / 1 error / 2 refusal)."""
    if not original_unchanged:
        return 1
    if status == "ok":
        return 0
    if status in _REFUSAL_STATUSES:
        return 2
    return 1


def summarize_exit_codes(envelopes: list[dict]) -> int:
    """Fail-loud sweep exit: 2 if any refusal, elif 1 if any error, else 0."""
    codes = [int(e.get("exit_code", 1)) for e in envelopes]
    if any(c == 2 for c in codes):
        return 2
    if any(c == 1 for c in codes):
        return 1
    return 0


def _collect_live_templates(
    frag_dir: Path,
    router_home: Path,
    templates_json: Path,
    merged_registry: dict[str, dict],
) -> list[tuple[str, dict | None, str | None]]:
    """(template_id, sample_args, sample_args_note) in deterministic order."""
    items: list[tuple[str, dict | None, str | None]] = []
    seen: set[str] = set()
    for frag_path in enumerate_fragment_files(frag_dir):
        try:
            raw = _load_json_doc(frag_path)
        except (OSError, json.JSONDecodeError):
            continue
        for template in _templates_of(raw):
            tid = template.get("template_id")
            if not tid or tid in seen or tid not in merged_registry:
                continue
            merged = merged_registry[tid]
            validation_status, _reason = validate_template_contract(
                template, merged_registry,
            )
            if validation_status != "ok":
                continue
            sample_args, note = derive_sample_args(merged)
            items.append((tid, sample_args, note))
            seen.add(tid)
    for template in _templates_of(_load_json_doc(templates_json)):
        tid = template.get("template_id")
        if not tid or tid in seen or tid not in merged_registry:
            continue
        merged = merged_registry[tid]
        validation_status, _reason = validate_template_contract(
            template, merged_registry,
        )
        if validation_status != "ok":
            continue
        sample_args, note = derive_sample_args(merged)
        items.append((tid, sample_args, note))
        seen.add(tid)
    return items


def build_plan_summary(
    rows: list[dict],
    *,
    templates_json: Path | str = TEMPLATES_JSON,
) -> dict:
    total_governed = None
    try:
        total_governed = len(load_merged_registry(templates_json))
    except Exception:  # pragma: no cover - keep summary honest, never crash main()
        total_governed = None

    refused = sum(1 for r in rows if r.get("validation_status") == "refused")
    ok = sum(1 for r in rows if r.get("validation_status") == "ok")
    planned = sum(1 for r in rows if r.get("template_id") is not None)
    skipped_with_reason = sum(
        1 for r in rows if r.get("validation_status") == "skipped_with_reason"
    )
    return {
        "schema": SUMMARY_SCHEMA,
        "mode": "plan",
        "total_rows": len(rows),
        "total_governed": total_governed,
        "planned": planned,
        "skipped_with_reason": skipped_with_reason,
        "refused": refused,
        "ok": ok,
    }


def run_live(
    dwg_path: Path | str,
    out_dir: Path | str,
    *,
    router_home: Path | str = ROUTER_HOME,
    frag_dir: Path | str | None = None,
    templates_json: Path | str | None = None,
    cad_factory=None,
) -> tuple[list[dict], int]:
    """Execute templates via cadctl; resumable per-template envelopes on disk."""
    router_home = Path(router_home)
    dwg_path = Path(dwg_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frag_dir = Path(frag_dir) if frag_dir else router_home / "config" / "command_templates.d"
    templates_json = Path(templates_json) if templates_json else router_home / "config" / "command_templates.json"

    if not dwg_path.is_file():
        raise SweepError(f"--live requires an existing DWG: {dwg_path}")

    try:
        merged_registry = load_merged_registry(templates_json)
    except cte.TemplateError as exc:
        raise SweepError(f"registry load refused: {exc.code}: {exc.message}") from exc

    cad = cad_factory(router_home) if cad_factory else cadctl.Cad(router_home)
    original_sha = sha256_file(dwg_path)
    envelopes: list[dict] = []

    for template_id, sample_args, sample_args_note in _collect_live_templates(
        frag_dir, router_home, templates_json, merged_registry,
    ):
        env_path = envelope_path(out_dir, template_id)
        if env_path.is_file():
            existing = json.loads(env_path.read_text(encoding="utf-8-sig"))
            existing["resumed"] = True
            envelopes.append(existing)
            continue

        slots = sample_args if sample_args is not None else {}
        cad_env = cad.run_command_template(template_id, slots, dwg=str(dwg_path))

        post_sha = sha256_file(dwg_path)
        original_unchanged = (post_sha == original_sha)
        if not original_unchanged:
            raise SweepError(
                f"original DWG sha256 changed after {template_id!r} "
                f"(write_original contract violated)"
            )

        status = cad_env.get("status", "error")
        exit_code = status_to_exit_code(status, original_unchanged=original_unchanged)

        evidence_paths: dict[str, str] = {"envelope": str(env_path.resolve())}
        for key in ("stdout", "stderr", "staged_copy"):
            val = cad_env.get(key)
            if val:
                evidence_paths[key] = str(val)

        envelope = {
            "schema": ENVELOPE_SCHEMA,
            "template_id": template_id,
            "status": status,
            "exit_code": exit_code,
            "original_unchanged": original_unchanged,
            "original_sha256": original_sha,
            "sample_args": slots,
            "sample_args_note": sample_args_note,
            "evidence_paths": evidence_paths,
            "resumed": False,
        }
        if cad_env.get("reason"):
            envelope["reason"] = cad_env["reason"]
        if cad_env.get("error"):
            envelope["error"] = cad_env["error"]

        env_path.write_text(
            json.dumps(envelope, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        envelopes.append(envelope)

    return envelopes, summarize_exit_codes(envelopes)


def _build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--live", action="store_true",
                    help="run templates via cadctl against a staged DWG copy "
                         "(default mode is --plan)")
    ap.add_argument("--dwg", default=None, help="original DWG path (--live required)")
    ap.add_argument("--out-dir", default=None, help="per-template envelope directory (--live)")
    ap.add_argument("--out", default=None, help="plan JSONL output path (default: stdout)")
    ap.add_argument("--router-home", default=str(ROUTER_HOME),
                    help="autocad-sdk-router root (config/command_templates.json)")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    router_home = Path(args.router_home)

    if args.live:
        if not args.dwg or not args.out_dir:
            print("ABORTED: --live requires --dwg and --out-dir", file=sys.stderr)
            return 2
        try:
            envelopes, exit_code = run_live(args.dwg, args.out_dir, router_home=router_home)
        except SweepError as exc:
            print(f"ABORTED: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2

        summary = {
            "schema": SUMMARY_SCHEMA,
            "mode": "live",
            "total": len(envelopes),
            "by_exit_code": {},
            "out_dir": str(Path(args.out_dir).resolve()),
        }
        for env in envelopes:
            code = str(env.get("exit_code", 1))
            summary["by_exit_code"][code] = summary["by_exit_code"].get(code, 0) + 1
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return exit_code

    try:
        rows = run_plan(router_home=router_home)
    except SweepError as exc:
        print(f"ABORTED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.out:
        write_jsonl(rows, args.out)
    else:
        emit_jsonl(rows, sys.stdout)

    summary = build_plan_summary(
        rows,
        templates_json=router_home / "config" / "command_templates.json",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), file=sys.stderr)
    return 2 if summary["refused"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
