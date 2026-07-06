#!/usr/bin/env python3
"""cross_engine_verify.py -- cross-check AutoCAD truth vs LibreDWG census.

Intent (WHY):
  * This op persists the ad-hoc LibreDWG cross-engine comparison done during
    1004 investigation into a governed, deterministic verification entry point.
  * It intentionally computes a read-only staged copy census and compares only
    the stable, high-signal invariants we care about cross-engine: entity_count
    and layer-name set.

No-LLM, no network, no fake success:
  * No third-party imports.
  * LibreDWG is invoked as a separate subprocess (sidecar only).
  * If LibreDWG is unavailable, the result is truthful truthfulness status:
    not_available.
  * Original DWG bytes are hashed before staging/cross-check and verified
    unchanged after.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

_THIS_DIR = Path(__file__).resolve().parent
ROUTER_HOME = _THIS_DIR.parent
STAGING_DIR = ROUTER_HOME / "staging" / "cross_engine_verify"


def _sha256(path: Path, n: int = 16) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:n].upper()


def _to_set(values: Iterable[Any]) -> Set[str]:
    out: Set[str] = set()
    for v in values:
        if isinstance(v, str):
            s = v.strip()
            if s:
                out.add(s)
        elif isinstance(v, dict):
            nm = v.get("name")
            if isinstance(nm, str):
                s = nm.strip()
                if s:
                    out.add(s)
    return out


def _autocad_summary(ir_path: str) -> Dict[str, Any]:
    with open(ir_path, "r", encoding="utf-8-sig") as fh:
        ir = json.load(fh)

    entities = ir.get("entities")
    entities_count = len([e for e in (entities or []) if isinstance(e, dict)]) if isinstance(entities, list) else 0

    layers: Set[str] = set()
    if isinstance(entities, list):
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            layer = ent.get("layer")
            if isinstance(layer, str) and layer:
                layers.add(layer)

    for table in (ir.get("symbol_tables") or {}).get("layers") or []:
        if isinstance(table, dict):
            nm = table.get("name")
            if isinstance(nm, str) and nm:
                layers.add(nm)

    return {
        "entities": entities_count,
        "layers": sorted(layers),
    }


def _resolve_dwgread_bin(libredwg_bin_dir: Optional[str] = None) -> Optional[str]:
    search: List[str] = []
    if libredwg_bin_dir:
        search.append(libredwg_bin_dir)
        if not search[0]:
            return None
        if search:
            for root in search:
                for name in ("dwgread.exe", "dwgread"):
                    candidate = Path(root) / name
                    if candidate.exists():
                        return str(candidate)
            return None

    env_bin = os.environ.get("ARIADNE_LIBREDWG_BIN_DIR")
    if env_bin:
        search.append(env_bin)

    for root in search:
        for name in ("dwgread.exe", "dwgread"):
            candidate = Path(root) / name
            if candidate.exists():
                return str(candidate)
    return None


def _parse_layer_from_entity_value(layer_ref: Any, by_handle: Dict[Tuple[int, ...], str]) -> Optional[str]:
    if isinstance(layer_ref, str):
        s = layer_ref.strip()
        return s or None
    if isinstance(layer_ref, tuple):
        layer_ref = list(layer_ref)
    if isinstance(layer_ref, list):
        key = tuple(int(v) for v in layer_ref if isinstance(v, int))
        if not key:
            return None
        if key in by_handle:
            return by_handle[key]
        # DWG layer handles sometimes appear with one extra trailing marker.
        if len(key) > 1 and (key[:-1] in by_handle):
            return by_handle[key[:-1]]
        # As a last resort, if layer handle list resolves to something numeric,
        # keep it as a stable textual token instead of dropping the signal.
        return str(key[-1])
    return None


def _libredwg_summary(libredwg_json: Dict[str, Any]) -> Dict[str, Any]:
    # Primary path: dwgread JSON object list.
    objects = libredwg_json.get("OBJECTS")
    if isinstance(objects, list):
        by_handle: Dict[Tuple[int, ...], str] = {}
        layers: Dict[str, str] = {}

        for obj in objects:
            if not isinstance(obj, dict):
                continue
            handle = obj.get("handle")
            if isinstance(handle, list) and handle and all(isinstance(v, int) for v in handle):
                by_handle[tuple(handle)] = str(obj.get("name") or "")

            if obj.get("object") == "LAYER":
                name = obj.get("name")
                if isinstance(name, str) and name:
                    layers[name] = name

        # Restrict to modelspace entities if this shape is available.
        model = None
        for obj in objects:
            if isinstance(obj, dict) and obj.get("object") == "BLOCK_HEADER" and obj.get("name") == "*Model_Space":
                model = obj
                break

        layer_set: Set[str] = set()
        entity_records = []
        if model is not None and isinstance(model.get("entities"), list):
            for ref in model.get("entities"):
                if isinstance(ref, list) and ref and all(isinstance(v, int) for v in ref):
                    ent = by_handle.get(tuple(ref))
                    if isinstance(ent, str):
                        entity_records.append(ent)
                        continue
        if not entity_records:
            # Fallback: every non-LAYER object with a stable object/class key.
            for obj in objects:
                if not isinstance(obj, dict):
                    continue
                if obj.get("object") == "LAYER":
                    continue
                if obj.get("object") or obj.get("entity") or obj.get("_subclass"):
                    entity_records.append(obj)

                layer = _parse_layer_from_entity_value(obj.get("layer"), by_handle)
                if layer:
                    layer_set.add(layer)

        else:
            for obj in objects:
                if not isinstance(obj, dict):
                    continue
                layer = _parse_layer_from_entity_value(obj.get("layer"), by_handle)
                if layer:
                    layer_set.add(layer)

        if layers:
            layer_set.update(layers.keys())

        return {
            "entities": len(entity_records),
            "layers": sorted(layer_set),
        }

    # Thin JSON-summary fallback (already-canned test payloads usually hit this).
    if isinstance(libredwg_json.get("entities"), list):
        return {
            "entities": len(libredwg_json["entities"]),
            "layers": sorted(_to_set(libredwg_json.get("layers") or [])),
        }

    if isinstance(libredwg_json.get("entity_count"), int):
        return {
            "entities": int(libredwg_json["entity_count"]),
            "layers": sorted(_to_set(libredwg_json.get("layers") or [])),
        }

    # If callers return a pre-canned object containing the final summary,
    # accept it too.
    summary = libredwg_json.get("summary")
    if isinstance(summary, dict) and isinstance(summary.get("entity_total"), int):
        return {
            "entities": int(summary["entity_total"]),
            "layers": sorted(_to_set(summary.get("layer_names") or summary.get("layers") or [])),
        }

    raise ValueError("unrecognized LibreDWG JSON shape")


def _run_libredwg(staged_dwg: str, bin_dir: Optional[str]) -> Tuple[int, str, str]:
    dwgread = _resolve_dwgread_bin(bin_dir)
    if not dwgread:
        return -1, "", ""

    tmp_root = tempfile.mkdtemp(prefix="cross_engine_verify_")
    json_out = os.path.join(tmp_root, "libredwg_extract.json")
    cmd = [dwgread, "-O", "JSON", "-o", json_out, staged_dwg]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    if getattr(result, "returncode", None) != 0:
        msg = (result.stderr or result.stdout or "dwgread returned non-zero").strip() or "dwgread failed"
        return getattr(result, "returncode", 1), msg, json_out

    if os.path.exists(json_out):
        with open(json_out, "r", encoding="utf-8") as fh:
            return 0, fh.read(), json_out

    return 0, (getattr(result, "stdout", "") or ""), json_out


def verify_cross_engine(
    dwg_path: str,
    autocad_ir_path: Optional[str] = None,
    libredwg_bin_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Run staged-dwg cross-check between AutoCAD IR truth and LibreDWG.

    Return keys:
      - ok
      - status
      - concordant
      - autocad (when autocad_ir_path is supplied)
      - libredwg
      - deltas (when both sides are available)
      - original_unchanged
    """

    src = Path(dwg_path)
    if not src.exists():
        return {
            "ok": False,
            "status": "blocked",
            "reason": "input DWG not found: %s" % dwg_path,
            "original_unchanged": True,
        }

    original_before = _sha256(src)

    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    stage_root = Path(tempfile.mkdtemp(prefix="cross_engine_verify_", dir=str(STAGING_DIR)))
    staged = stage_root / src.name
    shutil.copy2(src, staged)

    try:
        os.chmod(staged, 0o444)
    except OSError:
        pass

    rc, raw_output, _json_out = _run_libredwg(str(staged), libredwg_bin_dir)
    if rc < 0:
        autocad_summary = None
        if autocad_ir_path and Path(autocad_ir_path).is_file():
            try:
                autocad_summary = _autocad_summary(autocad_ir_path)
            except Exception:
                autocad_summary = None
        return {
            "ok": True,
            "status": "not_available",
            "reason": "libredwg dwgread binary not found in libredwg_bin_dir or ARIADNE_LIBREDWG_BIN_DIR",
            "libredwg": {
                "entities": 0,
                "layers": [],
            },
            "original_unchanged": _sha256(src) == original_before,
            "concordant": False,
            "autocad": autocad_summary,
            "deltas": {
                "entity_count": 0,
                "layers_only_autocad": [],
                "layers_only_libredwg": [],
            },
        }

    if rc != 0:
        return {
            "ok": False,
            "status": "blocked",
            "reason": raw_output or "dwgread failed",
            "original_unchanged": _sha256(src) == original_before,
        }

    if not raw_output.strip():
        return {
            "ok": False,
            "status": "blocked",
            "reason": "empty LibreDWG output",
            "original_unchanged": _sha256(src) == original_before,
        }

    try:
        parsed = json.loads(raw_output)
        libredwg = _libredwg_summary(parsed)
    except Exception as exc:  # pragma: no cover - structural fallback
        return {
            "ok": False,
            "status": "blocked",
            "reason": "failed to parse LibreDWG JSON: %s: %s" % (type(exc).__name__, exc),
            "original_unchanged": _sha256(src) == original_before,
        }

    out: Dict[str, Any] = {
        "ok": True,
        "status": "ok",
        "libredwg": libredwg,
        "original_unchanged": _sha256(src) == original_before,
    }

    if autocad_ir_path is None:
        out.update({
            "concordant": False,
            "autocad": None,
            "deltas": {
                "entity_count": 0,
                "layers_only_autocad": [],
                "layers_only_libredwg": [],
            },
        })
        return out

    irp = Path(autocad_ir_path)
    if not irp.exists():
        return {
            "ok": False,
            "status": "blocked",
            "reason": "AutoCAD IR not found: %s" % autocad_ir_path,
            "original_unchanged": _sha256(src) == original_before,
            "libredwg": libredwg,
        }

    try:
        autocad = _autocad_summary(str(irp))
    except Exception as exc:
        return {
            "ok": False,
            "status": "blocked",
            "reason": "failed to read AutoCAD IR: %s: %s" % (type(exc).__name__, exc),
            "original_unchanged": _sha256(src) == original_before,
            "libredwg": libredwg,
        }

    ac_layers = set(autocad["layers"])
    ld_layers = set(libredwg["layers"])
    only_ac = sorted(ac_layers - ld_layers)
    only_ld = sorted(ld_layers - ac_layers)
    entity_delta = libredwg["entities"] - autocad["entities"]
    concordant = (entity_delta == 0 and not only_ac and not only_ld)

    out.update({
        "concordant": concordant,
        "autocad": autocad,
        "deltas": {
            "entity_count": entity_delta,
            "layers_only_autocad": only_ac,
            "layers_only_libredwg": only_ld,
        },
    })
    return out


if __name__ == "__main__":
    raise SystemExit(0)
