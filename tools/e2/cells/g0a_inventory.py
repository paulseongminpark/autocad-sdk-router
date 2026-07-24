#!/usr/bin/env python3
"""G0-A metadata-only inventory for the E2 W2 two-stage seal.

This collector deliberately does not import or execute project code, does not parse
CubiCasa SEG-IR or gen2 truth payloads, and does not calculate model metrics.  It
uses file names, sizes, hashes, narrowly extracted pre-existing ledger fields, and
environment reachability probes only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import mmap
import os
import platform
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


CELL_DIR = Path(__file__).resolve().parent
INVENTORY_PATH = CELL_DIR / "inventory.json"
REPORT_PATH = CELL_DIR / "REPORT.md"

PROGRAM_ROOT = Path(r"D:\runs\e2_program")
CELLS_ROOT = PROGRAM_ROOT / "cells"
PACKET_PATH = PROGRAM_ROOT / "build" / "PACKET_g0a_inventory.md"

REPO_ROOT = Path(r"D:\dev\99_tools\autocad-sdk-router")
TOOLS_E2_ROOT = REPO_ROOT / "tools" / "e2"
CUBICASA_IR_ROOT = REPO_ROOT / "runs" / "e2_ext_cubicasa" / "ir"
GEN2_PACK_ROOT = CELLS_ROOT / "fidelity_full" / "packs"

BASELINE_RESULTS_PATH = CELLS_ROOT / "baseline_freeze" / "results.json"
BSTAR_MANIFEST_PATH = CELLS_ROOT / "bstar_repair" / "bstar_manifest_v2.json"
C0_SCENES_ROOT = CELLS_ROOT / "feyerabend_c0" / "scenes"
L1_SCENES_ROOT = CELLS_ROOT / "loop_l1" / "scenes_v2"

AUTHORITY_PATHS = (
    REPO_ROOT / "reports" / "e2" / "duo" / "WAVE2_JOINT_DESIGN.md",
    REPO_ROOT / "reports" / "e2" / "duo" / "REVISED_sol.md",
)

CORPUS_CANDIDATES: dict[str, tuple[Path, ...]] = {
    "ArchCAD": (
        Path(r"D:\datasets\ArchCAD"),
        Path(r"C:\datasets\ArchCAD"),
    ),
    "FloorPlanCAD": (
        Path(r"D:\datasets\FloorPlanCAD"),
        Path(r"C:\datasets\FloorPlanCAD"),
    ),
    "Zenodo10K": (
        Path(r"D:\datasets\Zenodo10K"),
        Path(r"D:\datasets\Zenodo-10K"),
        Path(r"C:\datasets\Zenodo10K"),
    ),
    "pseudo-12k": (
        Path(r"D:\datasets\pseudo-floor-plan-12k"),
        Path(r"D:\datasets\pseudo-12k"),
        Path(r"C:\datasets\pseudo-floor-plan-12k"),
    ),
}

TRAINER_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "gnn_trainer": (
        re.compile(r"(?:^|/)(?:gnn|graph_neural)[^/]*(?:train|trainer)[^/]*$"),
        re.compile(r"(?:^|/)(?:train|trainer)[^/]*(?:gnn|graph_neural)[^/]*$"),
    ),
    "qwen_trainer": (
        re.compile(r"(?:^|/)qwen[^/]*(?:train|trainer)[^/]*$"),
        re.compile(r"(?:^|/)(?:train|trainer)[^/]*qwen[^/]*$"),
    ),
    "raster_trainer": (
        re.compile(r"(?:^|/)(?:raster|segmentation)[^/]*(?:train|trainer)[^/]*$"),
        re.compile(r"(?:^|/)(?:train|trainer)[^/]*(?:raster|segmentation)[^/]*$"),
    ),
    "rl_harness": (
        re.compile(r"(?:^|/)(?:rl|rlvr|reinforcement)[^/]*(?:harness|train|trainer)[^/]*$"),
        re.compile(r"(?:^|/)(?:harness|train|trainer)[^/]*(?:rl|rlvr|reinforcement)[^/]*$"),
    ),
}

STATUS_MARKER_RE = re.compile(
    r"^\s*(CELL_(?:COMPLETE|BLOCKED|INVALID|FAIL|PASS|KILL)|BUILD_COMPLETE)"
    r"\s*:\s*([A-Za-z0-9_.-]+)\s*$",
    re.IGNORECASE,
)
ELAPSED_RE = re.compile(
    r"\b(elapsed[a-z0-9_-]*)\b[^0-9\r\n]{0,24}([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE,
)
COMPLETION_FILE_NAMES = {
    ".complete",
    "cell_complete",
    "complete",
    "complete.marker",
    "done",
}


def _path_text(path: Path) -> str:
    return str(path.resolve()) if path.exists() else str(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    resolved_parent = path.resolve().parent
    if resolved_parent != CELL_DIR:
        raise RuntimeError(f"output escaped cell directory: {path}")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def _walk_files(root: Path) -> tuple[list[Path], list[dict[str, str]]]:
    """Walk regular files without following links/junctions."""
    files: list[Path] = []
    errors: list[dict[str, str]] = []
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda item: item.name.casefold())
        except OSError as exc:
            errors.append({"path": str(directory), "error": f"{type(exc).__name__}: {exc}"})
            continue
        child_directories: list[Path] = []
        for entry in entries:
            child = Path(entry.path)
            try:
                if entry.is_symlink():
                    continue
                if entry.is_file(follow_symlinks=False):
                    files.append(child)
                elif entry.is_dir(follow_symlinks=False):
                    child_directories.append(child)
            except OSError as exc:
                errors.append({"path": str(child), "error": f"{type(exc).__name__}: {exc}"})
        stack.extend(reversed(child_directories))
    files.sort(key=lambda path: path.relative_to(root).as_posix().casefold())
    errors.sort(key=lambda row: row["path"].casefold())
    return files, errors


def _metadata_listing(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    files, errors = _walk_files(root)
    rows: list[dict[str, Any]] = []
    for path in files:
        try:
            rows.append(
                {
                    "bytes": path.stat().st_size,
                    "relative_path": path.relative_to(root).as_posix(),
                }
            )
        except OSError as exc:
            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
    rows.sort(key=lambda row: row["relative_path"].casefold())
    errors.sort(key=lambda row: row["path"].casefold())
    return rows, errors


def _extract_named_json_value(path: Path, key: str) -> Any:
    """Parse only one named JSON value, never the surrounding score-bearing object."""
    needle = json.dumps(key, ensure_ascii=True).encode("ascii")
    with path.open("rb") as handle:
        with mmap.mmap(handle.fileno(), length=0, access=mmap.ACCESS_READ) as mapped:
            key_at = mapped.find(needle)
            if key_at < 0:
                raise KeyError(f"{key!r} not found in {path}")
            cursor = key_at + len(needle)
            while cursor < len(mapped) and mapped[cursor] in b" \t\r\n":
                cursor += 1
            if cursor >= len(mapped) or mapped[cursor] != ord(":"):
                raise ValueError(f"malformed JSON member {key!r} in {path}")
            cursor += 1
            while cursor < len(mapped) and mapped[cursor] in b" \t\r\n":
                cursor += 1
            start = cursor
            if start >= len(mapped):
                raise ValueError(f"missing JSON value for {key!r} in {path}")

            first = mapped[start]
            if first in (ord("{"), ord("[")):
                opening = first
                closing = ord("}") if opening == ord("{") else ord("]")
                depth = 0
                in_string = False
                escaped = False
                end = None
                for cursor in range(start, len(mapped)):
                    byte = mapped[cursor]
                    if in_string:
                        if escaped:
                            escaped = False
                        elif byte == ord("\\"):
                            escaped = True
                        elif byte == ord('"'):
                            in_string = False
                        continue
                    if byte == ord('"'):
                        in_string = True
                    elif byte == opening:
                        depth += 1
                    elif byte == closing:
                        depth -= 1
                        if depth == 0:
                            end = cursor + 1
                            break
                if end is None:
                    raise ValueError(f"unterminated JSON value for {key!r} in {path}")
            elif first == ord('"'):
                escaped = False
                end = None
                for cursor in range(start + 1, len(mapped)):
                    byte = mapped[cursor]
                    if escaped:
                        escaped = False
                    elif byte == ord("\\"):
                        escaped = True
                    elif byte == ord('"'):
                        end = cursor + 1
                        break
                if end is None:
                    raise ValueError(f"unterminated JSON string for {key!r} in {path}")
            else:
                end = start
                while end < len(mapped) and mapped[end] not in b",}\r\n\t ":
                    end += 1
            raw_value = mapped[start:end]
    return json.loads(raw_value.decode("utf-8"))


def _inventory_cubicasa() -> dict[str, Any]:
    split_rows: dict[str, Any] = {}
    for split in ("test", "train", "val"):
        directory = CUBICASA_IR_ROOT / split
        if not directory.is_dir():
            split_rows[split] = {
                "path": str(directory),
                "status": "NOT_FOUND",
            }
            continue
        files = sorted(
            (
                path
                for path in directory.iterdir()
                if path.is_file() and path.name.lower().endswith(".segir.json")
            ),
            key=lambda path: path.name.casefold(),
        )
        drawing_ids = [path.name[: -len(".segir.json")] for path in files]
        split_rows[split] = {
            "content_parsed": False,
            "drawing_id_derivation": "filename with terminal .segir.json removed",
            "drawing_id_list_hash_encoding": "canonical JSON UTF-8, sorted filenames",
            "drawing_id_list_sha256": _canonical_hash(drawing_ids),
            "file_count": len(files),
            "filename_pattern": "*.segir.json",
            "path": _path_text(directory),
            "status": "FOUND",
            "total_bytes": sum(path.stat().st_size for path in files),
        }
    return {
        "root": _path_text(CUBICASA_IR_ROOT),
        "splits": split_rows,
    }


def _inventory_gen2() -> dict[str, Any]:
    root_manifest_path = GEN2_PACK_ROOT / "manifest.json"
    if not root_manifest_path.is_file():
        return {
            "path": str(GEN2_PACK_ROOT),
            "status": "NOT_FOUND",
        }
    root_manifest = json.loads(root_manifest_path.read_text(encoding="utf-8"))
    tier_rows: list[dict[str, Any]] = []
    drawing_ids: list[str] = []
    declared_checks = 0
    mismatches: list[dict[str, str]] = []
    manifest_hash_rows = [
        {
            "relative_path": "manifest.json",
            "sha256": _sha256_file(root_manifest_path),
        }
    ]
    tiers = root_manifest.get("tiers", {})
    for tier in sorted(tiers):
        root_record = tiers[tier]
        relative_manifest = str(root_record.get("manifest", f"{tier}/manifest.json"))
        tier_manifest_path = GEN2_PACK_ROOT / Path(relative_manifest)
        if not tier_manifest_path.is_file():
            mismatches.append(
                {"kind": "missing_tier_manifest", "relative_path": relative_manifest}
            )
            continue
        tier_manifest_sha = _sha256_file(tier_manifest_path)
        manifest_hash_rows.append(
            {"relative_path": Path(relative_manifest).as_posix(), "sha256": tier_manifest_sha}
        )
        tier_manifest = json.loads(tier_manifest_path.read_text(encoding="utf-8"))
        entries = tier_manifest.get("files", [])
        for entry in entries:
            drawing_id = str(entry.get("drawing_id", ""))
            drawing_ids.append(f"{tier}/{drawing_id}")
            for kind, path_key, hash_key in (
                ("dxf", "dxf", "dxf_sha256"),
                ("truth", "truth", "truth_sha256"),
            ):
                declared_checks += 1
                relative_artifact = Path(tier) / str(entry.get(path_key, ""))
                artifact_path = GEN2_PACK_ROOT / relative_artifact
                if not artifact_path.is_file():
                    mismatches.append(
                        {"kind": f"missing_{kind}", "relative_path": relative_artifact.as_posix()}
                    )
                    continue
                actual = _sha256_file(artifact_path)
                declared = str(entry.get(hash_key, "")).lower()
                if actual != declared:
                    mismatches.append(
                        {"kind": f"{kind}_sha256_mismatch", "relative_path": relative_artifact.as_posix()}
                    )
        tier_rows.append(
            {
                "declared_n_in_root": root_record.get("n"),
                "entry_count": len(entries),
                "manifest_path": _path_text(tier_manifest_path),
                "manifest_sha256": tier_manifest_sha,
                "tier": tier,
            }
        )
    drawing_ids.sort(key=str.casefold)
    mismatches.sort(key=lambda row: (row["relative_path"].casefold(), row["kind"]))
    manifest_hash_rows.sort(key=lambda row: row["relative_path"].casefold())
    return {
        "artifact_content_parsed": False,
        "declared_artifact_hashes_checked": declared_checks,
        "drawing_count": len(drawing_ids),
        "drawing_id_list_sha256": _canonical_hash(drawing_ids),
        "expected_150_match": len(drawing_ids) == 150,
        "manifest_bundle_sha256": _canonical_hash(manifest_hash_rows),
        "manifest_hashes": manifest_hash_rows,
        "manifest_or_artifact_mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "path": _path_text(GEN2_PACK_ROOT),
        "root_manifest_sha256": _sha256_file(root_manifest_path),
        "status": "FOUND",
        "tiers": sorted(tier_rows, key=lambda row: row["tier"]),
    }


def _inventory_scenes() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for name, root in (("C0", C0_SCENES_ROOT), ("L1", L1_SCENES_ROOT)):
        if not root.is_dir():
            rows[name] = {"path": str(root), "status": "NOT_FOUND"}
            continue
        files = sorted(root.glob("scene_*.json"), key=lambda path: path.name.casefold())
        rows[name] = {
            "content_parsed": False,
            "file_count": len(files),
            "filename_pattern": "scene_*.json",
            "path": _path_text(root),
            "status": "FOUND",
            "total_bytes": sum(path.stat().st_size for path in files),
        }
    return rows


def _inventory_family_ledgers() -> dict[str, Any]:
    result: dict[str, Any] = {}
    if BASELINE_RESULTS_PATH.is_file():
        family_audit = _extract_named_json_value(BASELINE_RESULTS_PATH, "family_audit")
        if not isinstance(family_audit, dict):
            raise TypeError("baseline family_audit is not an object")
        result["baseline_freeze"] = {
            "extraction": "only the named family_audit JSON value was decoded",
            "family_audit": family_audit,
            "source_path": _path_text(BASELINE_RESULTS_PATH),
            "source_sha256": _sha256_file(BASELINE_RESULTS_PATH),
            "status": "FOUND",
        }
    else:
        result["baseline_freeze"] = {
            "source_path": str(BASELINE_RESULTS_PATH),
            "status": "NOT_FOUND",
        }
    if BSTAR_MANIFEST_PATH.is_file():
        repaired_split_hash = _extract_named_json_value(
            BSTAR_MANIFEST_PATH, "repaired_split_hash"
        )
        if not isinstance(repaired_split_hash, str) or not re.fullmatch(
            r"[0-9a-fA-F]{64}", repaired_split_hash
        ):
            raise ValueError("bstar repaired_split_hash is not a SHA-256 hex string")
        result["bstar_repair"] = {
            "extraction": "only the named repaired_split_hash JSON value was decoded",
            "repaired_split_hash": repaired_split_hash.lower(),
            "source_path": _path_text(BSTAR_MANIFEST_PATH),
            "source_sha256": _sha256_file(BSTAR_MANIFEST_PATH),
            "status": "FOUND",
        }
    else:
        result["bstar_repair"] = {
            "source_path": str(BSTAR_MANIFEST_PATH),
            "status": "NOT_FOUND",
        }
    return result


def _inventory_code_landing() -> dict[str, Any]:
    if not TOOLS_E2_ROOT.is_dir():
        return {"path": str(TOOLS_E2_ROOT), "status": "NOT_FOUND"}
    paths, walk_errors = _walk_files(TOOLS_E2_ROOT)
    files: list[dict[str, Any]] = []
    relative_paths: list[str] = []
    for path in paths:
        relative = path.relative_to(TOOLS_E2_ROOT).as_posix()
        relative_paths.append(relative)
        files.append(
            {
                "bytes": path.stat().st_size,
                "relative_path": relative,
                "sha256": _sha256_file(path),
            }
        )
    trainer_status: dict[str, Any] = {}
    for category in sorted(TRAINER_PATTERNS):
        matches = sorted(
            (
                relative
                for relative in relative_paths
                if any(
                    pattern.search(relative.casefold())
                    for pattern in TRAINER_PATTERNS[category]
                )
            ),
            key=str.casefold,
        )
        trainer_status[category] = {
            "matching_files": matches,
            "present": bool(matches),
            "status": "PRESENT" if matches else "ABSENT",
        }
    return {
        "classification_basis": "relative filename lexical match only; file contents not used",
        "file_count": len(files),
        "files": files,
        "path": _path_text(TOOLS_E2_ROOT),
        "status": "FOUND",
        "trainer_and_harness_presence": trainer_status,
        "walk_errors": walk_errors,
    }


def _census_one_root(root: Path) -> dict[str, Any]:
    files, errors = _walk_files(root)
    extension_counts: Counter[str] = Counter()
    total_bytes = 0
    stat_errors = list(errors)
    counted_files = 0
    for path in files:
        try:
            size = path.stat().st_size
        except OSError as exc:
            stat_errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
            continue
        counted_files += 1
        total_bytes += size
        extension_counts[path.suffix.lower() or "<none>"] += 1
    return {
        "access_errors": sorted(stat_errors, key=lambda row: row["path"].casefold()),
        "extension_distribution": {
            key: extension_counts[key] for key in sorted(extension_counts)
        },
        "file_count": counted_files,
        "path": _path_text(root),
        "total_bytes": total_bytes,
    }


def _inventory_corpora() -> dict[str, Any]:
    corpora: dict[str, Any] = {}
    for corpus_name in sorted(CORPUS_CANDIDATES):
        candidates = CORPUS_CANDIDATES[corpus_name]
        seen: set[str] = set()
        instances: list[dict[str, Any]] = []
        for candidate in candidates:
            if not candidate.is_dir():
                continue
            identity = os.path.normcase(str(candidate.resolve()))
            if identity in seen:
                continue
            seen.add(identity)
            instances.append(_census_one_root(candidate))
        if not instances:
            corpora[corpus_name] = {
                "candidate_paths": [str(path) for path in candidates],
                "status": "NOT_FOUND",
            }
            continue
        aggregate_extensions: Counter[str] = Counter()
        for instance in instances:
            aggregate_extensions.update(instance["extension_distribution"])
        corpora[corpus_name] = {
            "candidate_paths": [str(path) for path in candidates],
            "extension_distribution": {
                key: aggregate_extensions[key] for key in sorted(aggregate_extensions)
            },
            "file_count": sum(instance["file_count"] for instance in instances),
            "instances": instances,
            "status": "FOUND",
            "total_bytes": sum(instance["total_bytes"] for instance in instances),
        }
    return {
        "content_parsed": False,
        "corpora": corpora,
        "discovery_method": "exact metadata-only candidate paths on local C: and D: drives",
    }


def _extract_report_metadata(report_path: Path) -> dict[str, Any]:
    elapsed: list[dict[str, Any]] = []
    markers: list[dict[str, Any]] = []
    try:
        with report_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, start=1):
                marker = STATUS_MARKER_RE.match(line)
                if marker:
                    markers.append(
                        {
                            "line": line_number,
                            "marker": marker.group(1).upper(),
                            "value": marker.group(2),
                        }
                    )
                for match in ELAPSED_RE.finditer(line):
                    elapsed.append(
                        {
                            "key": match.group(1).lower(),
                            "line": line_number,
                            "unit": "seconds" if "second" in line.lower() else "as_recorded",
                            "value": match.group(2),
                        }
                    )
    except OSError as exc:
        return {
            "elapsed_records": [],
            "read_error": f"{type(exc).__name__}: {exc}",
            "status_markers": [],
        }
    return {
        "elapsed_records": elapsed,
        "status_markers": markers,
    }


def _inventory_in_flight() -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    if not CELLS_ROOT.is_dir():
        return {"cells": cells, "path": str(CELLS_ROOT), "status": "NOT_FOUND"}
    directories = sorted(
        (path for path in CELLS_ROOT.iterdir() if path.is_dir()),
        key=lambda path: path.name.casefold(),
    )
    for directory in directories:
        outputs, errors = _metadata_listing(directory)
        report_path = directory / "REPORT.md"
        report_meta = (
            _extract_report_metadata(report_path)
            if report_path.is_file()
            else {"elapsed_records": [], "status_markers": []}
        )
        marker_files = sorted(
            (
                row["relative_path"]
                for row in outputs
                if Path(row["relative_path"]).name.casefold() in COMPLETION_FILE_NAMES
            ),
            key=str.casefold,
        )
        completion_markers = [
            row
            for row in report_meta.get("status_markers", [])
            if row["marker"] in {"CELL_COMPLETE", "BUILD_COMPLETE"}
        ]
        cells.append(
            {
                "cell": directory.name,
                "completion_marker_present": bool(completion_markers or marker_files),
                "elapsed_records": report_meta.get("elapsed_records", []),
                "file_count": len(outputs),
                "outputs": outputs,
                "report_exists": report_path.is_file(),
                "report_status_markers": report_meta.get("status_markers", []),
                "standalone_marker_files": marker_files,
                "total_bytes": sum(row["bytes"] for row in outputs),
                "walk_errors": errors,
                **(
                    {"report_read_error": report_meta["read_error"]}
                    if "read_error" in report_meta
                    else {}
                ),
            }
        )
    return {
        "cells": cells,
        "path": _path_text(CELLS_ROOT),
        "snapshot_semantics": "recursive filename and byte-size snapshot; REPORT parsing limited to elapsed and status marker lines",
        "status": "FOUND",
    }


def _run_command(argv: list[str], timeout_seconds: int) -> dict[str, Any]:
    started = time.perf_counter()
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            check=False,
            creationflags=creation_flags,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "returncode": completed.returncode,
            "stderr": completed.stderr.strip(),
            "stdout": completed.stdout.strip(),
        }
    except FileNotFoundError as exc:
        return {
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "error": f"FileNotFoundError: {exc}",
            "returncode": None,
            "stderr": "",
            "stdout": "",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "error": f"TimeoutExpired after {timeout_seconds} seconds",
            "returncode": None,
            "stderr": (exc.stderr or "").strip() if isinstance(exc.stderr, str) else "",
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
        }


def _inventory_environment() -> dict[str, Any]:
    torch_record: dict[str, Any] = {
        "import_attempted": False,
        "module_spec_present": importlib.util.find_spec("torch") is not None,
    }
    if torch_record["module_spec_present"]:
        torch_record["import_attempted"] = True
        started = time.perf_counter()
        try:
            import torch  # type: ignore

            torch_record.update(
                {
                    "import_elapsed_seconds": round(time.perf_counter() - started, 6),
                    "import_ok": True,
                    "version": str(torch.__version__),
                }
            )
        except Exception as exc:  # environment census must preserve an honest failure
            torch_record.update(
                {
                    "error": f"{type(exc).__name__}: {exc}",
                    "import_elapsed_seconds": round(time.perf_counter() - started, 6),
                    "import_ok": False,
                }
            )

    nvidia = _run_command(
        [
            "nvidia-smi",
            "--query-gpu=name,uuid,driver_version,memory.total",
            "--format=csv,noheader,nounits",
        ],
        timeout_seconds=20,
    )
    gpu_rows: list[dict[str, str]] = []
    if nvidia.get("returncode") == 0:
        for line in nvidia.get("stdout", "").splitlines():
            pieces = [piece.strip() for piece in line.split(",")]
            if len(pieces) >= 4:
                gpu_rows.append(
                    {
                        "driver_version": pieces[2],
                        "memory_total_mib": pieces[3],
                        "name": pieces[0],
                        "uuid": pieces[1],
                    }
                )
    gpu_rows.sort(key=lambda row: (row["name"].casefold(), row["uuid"]))

    user_profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
    key_path = user_profile / ".ssh" / "dgx_edgexpert"
    ssh_argv = [
        "ssh",
        "-i",
        str(key_path),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        "StrictHostKeyChecking=yes",
        "sunapse@172.30.1.1",
        "hostname",
    ]
    ssh = _run_command(ssh_argv, timeout_seconds=20)

    docker = _run_command(
        ["docker", "image", "ls", "--no-trunc", "--format", "{{json .}}"],
        timeout_seconds=30,
    )
    docker_images: list[dict[str, Any]] = []
    docker_parse_errors: list[str] = []
    if docker.get("returncode") == 0:
        for line_number, line in enumerate(docker.get("stdout", "").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as exc:
                docker_parse_errors.append(f"line {line_number}: {exc}")
                continue
            if isinstance(parsed, dict):
                docker_images.append(parsed)
    docker_images.sort(
        key=lambda row: (
            str(row.get("Repository", "")).casefold(),
            str(row.get("Tag", "")).casefold(),
            str(row.get("ID", "")),
        )
    )

    return {
        "dgx_ssh": {
            "command": "ssh -i %USERPROFILE%\\.ssh\\dgx_edgexpert sunapse@172.30.1.1 hostname",
            "key_exists": key_path.is_file(),
            "key_path": str(key_path),
            "probe": ssh,
            "reachable": ssh.get("returncode") == 0 and bool(ssh.get("stdout", "").strip()),
        },
        "docker": {
            "image_count": len(docker_images),
            "images": docker_images,
            "parse_errors": docker_parse_errors,
            "probe": {
                key: value
                for key, value in docker.items()
                if key != "stdout"
            },
        },
        "gpu": {
            "gpus": gpu_rows,
            "nvidia_smi_probe": nvidia,
            "rtx_5070_ti_recognized": any(
                "rtx 5070 ti" in row["name"].casefold() for row in gpu_rows
            ),
        },
        "python": {
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "torch": torch_record,
    }


def _authority_inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in (PACKET_PATH, *AUTHORITY_PATHS):
        if path.is_file():
            rows.append(
                {
                    "bytes": path.stat().st_size,
                    "path": _path_text(path),
                    "sha256": _sha256_file(path),
                    "status": "FOUND",
                }
            )
        else:
            rows.append({"path": str(path), "status": "NOT_FOUND"})
    rows.sort(key=lambda row: row["path"].casefold())
    return rows


def _collect_not_found(inventory: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    for authority in inventory["authorities"]:
        if authority["status"] == "NOT_FOUND":
            rows.append(authority["path"])
    for split, record in inventory["data_inventory"]["cubicasa_ir"]["splits"].items():
        if record["status"] == "NOT_FOUND":
            rows.append(f"CubiCasa {split}: {record['path']}")
    gen2 = inventory["data_inventory"]["gen2_full_pack"]
    if gen2["status"] == "NOT_FOUND":
        rows.append(f"gen2 full pack: {gen2['path']}")
    for scene_name, record in inventory["data_inventory"]["scene_counts"].items():
        if record["status"] == "NOT_FOUND":
            rows.append(f"{scene_name} scenes: {record['path']}")
    for ledger_name, record in inventory["family_manifests"].items():
        if record["status"] == "NOT_FOUND":
            rows.append(f"{ledger_name}: {record['source_path']}")
    code = inventory["code_landing_inventory"]
    if code["status"] == "NOT_FOUND":
        rows.append(f"tools/e2: {code['path']}")
    for corpus_name, record in inventory["unlabeled_corpus_census"]["corpora"].items():
        if record["status"] == "NOT_FOUND":
            rows.append(f"{corpus_name}: {', '.join(record['candidate_paths'])}")
    return sorted(set(rows), key=str.casefold)


def _collect_unresolved(inventory: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    gen2 = inventory["data_inventory"]["gen2_full_pack"]
    if gen2.get("status") == "FOUND":
        if not gen2.get("expected_150_match"):
            rows.append(f"gen2 drawing count is {gen2.get('drawing_count')}, expected 150")
        if gen2.get("manifest_or_artifact_mismatch_count"):
            rows.append(
                "gen2 manifest/artifact hash mismatches: "
                f"{gen2['manifest_or_artifact_mismatch_count']}"
            )
    for corpus_name, corpus in inventory["unlabeled_corpus_census"]["corpora"].items():
        if corpus.get("status") == "FOUND":
            error_count = sum(len(instance["access_errors"]) for instance in corpus["instances"])
            if error_count:
                rows.append(f"{corpus_name} metadata access errors: {error_count}")
    environment = inventory["environment_inventory"]
    if not environment["torch"].get("import_ok", False):
        rows.append("torch import unavailable or failed")
    if environment["gpu"]["nvidia_smi_probe"].get("returncode") != 0:
        rows.append("nvidia-smi query failed")
    if not environment["dgx_ssh"]["reachable"]:
        rows.append("DGX SSH hostname probe did not succeed")
    if environment["docker"]["probe"].get("returncode") != 0:
        rows.append("docker image listing did not succeed")
    rows.extend(
        f"protocol breach: {breach}"
        for breach in inventory["execution"]["protocol_breaches"]
    )
    return sorted(set(rows), key=str.casefold)


def _render_report(inventory: dict[str, Any]) -> str:
    protocol_status = inventory["execution"]["protocol_status"]
    cubicasa = inventory["data_inventory"]["cubicasa_ir"]["splits"]
    gen2 = inventory["data_inventory"]["gen2_full_pack"]
    scenes = inventory["data_inventory"]["scene_counts"]
    corpora = inventory["unlabeled_corpus_census"]["corpora"]
    environment = inventory["environment_inventory"]
    lines = [
        "# G0-A Non-label Inventory Report",
        "",
        f"- Protocol status: `{protocol_status}`",
        f"- Snapshot UTC: `{inventory['execution']['snapshot_utc']}`",
        f"- Collection elapsed seconds: `{inventory['execution']['collection_elapsed_seconds']}`",
        "- Write scope: this cell directory only; repository writes and Git commands were not used by the collector.",
        "- Model execution, model comparison, threshold selection, and label-statistic calculation: not performed.",
        "",
        "## Collection method",
        "",
        "- CubiCasa: filenames and byte sizes only; drawing IDs are filename-derived and only their canonical sorted-list SHA-256 is emitted.",
        "- Gen2: manifests are parsed; DXF/truth artifacts are hashed but their contents are not parsed.",
        "- Family ledgers: only `family_audit` and `repaired_split_hash` values are selectively decoded from their source JSON.",
        "- Corpora and in-flight cells: recursive filename, extension, size, report-marker, and elapsed-field census only.",
        "- Environment: Python facts, torch import attempt, `nvidia-smi` query, bounded SSH hostname probe, and Docker image listing; no benchmark.",
        "",
        "## Data inventory summary",
        "",
        "| Source | Files/drawings | Total bytes | Metadata hash/status |",
        "|---|---:|---:|---|",
    ]
    for split in ("train", "val", "test"):
        record = cubicasa[split]
        if record["status"] == "FOUND":
            lines.append(
                f"| CubiCasa {split} | {record['file_count']} | {record['total_bytes']} | "
                f"`{record['drawing_id_list_sha256']}` |"
            )
        else:
            lines.append(f"| CubiCasa {split} | — | — | NOT_FOUND |")
    if gen2["status"] == "FOUND":
        lines.append(
            f"| gen2 full pack | {gen2['drawing_count']} | — | "
            f"root `{gen2['root_manifest_sha256']}`; mismatches {gen2['manifest_or_artifact_mismatch_count']} |"
        )
    else:
        lines.append("| gen2 full pack | — | — | NOT_FOUND |")
    for scene_name in ("C0", "L1"):
        record = scenes[scene_name]
        if record["status"] == "FOUND":
            lines.append(
                f"| {scene_name} scenes | {record['file_count']} | {record['total_bytes']} | FOUND |"
            )
        else:
            lines.append(f"| {scene_name} scenes | — | — | NOT_FOUND |")
    lines.extend(
        [
            "",
            "## Code landing",
            "",
            f"- `tools/e2` files hashed: {inventory['code_landing_inventory'].get('file_count', 0)}",
        ]
    )
    for category, record in sorted(
        inventory["code_landing_inventory"].get(
            "trainer_and_harness_presence", {}
        ).items()
    ):
        lines.append(f"- {category}: `{record['status']}`")
    lines.extend(["", "## Unlabeled corpus census", ""])
    for corpus_name in sorted(corpora):
        record = corpora[corpus_name]
        if record["status"] == "FOUND":
            lines.append(
                f"- {corpus_name}: FOUND; files {record['file_count']}; bytes {record['total_bytes']}"
            )
        else:
            lines.append(f"- {corpus_name}: NOT_FOUND")
    lines.extend(
        [
            "",
            "## Environment summary",
            "",
            f"- Python: `{environment['python']['version']}`",
            f"- torch import: `{environment['torch'].get('import_ok', False)}`",
            f"- RTX 5070 Ti recognized by nvidia-smi: `{environment['gpu']['rtx_5070_ti_recognized']}`",
            f"- DGX SSH hostname probe reachable: `{environment['dgx_ssh']['reachable']}`",
            f"- Docker images transcribed: {environment['docker']['image_count']}",
            "",
            "## NOT_FOUND",
            "",
        ]
    )
    if inventory["not_found"]:
        lines.extend(f"- {item}" for item in inventory["not_found"])
    else:
        lines.append("- None")
    lines.extend(["", "## Unresolved", ""])
    if inventory["unresolved"]:
        lines.extend(f"- {item}" for item in inventory["unresolved"])
    else:
        lines.append("- None")
    lines.extend(["", "## Protocol breaches", ""])
    if inventory["execution"]["protocol_breaches"]:
        lines.extend(
            f"- {item}" for item in inventory["execution"]["protocol_breaches"]
        )
    else:
        lines.append("- None")
    final_marker = (
        "CELL_COMPLETE: g0a"
        if protocol_status == "COMPLIANT"
        else "CELL_INVALID: g0a"
    )
    lines.extend(["", final_marker])
    return "\n".join(lines) + "\n"


def _validate_outputs() -> list[str]:
    errors: list[str] = []
    if not INVENTORY_PATH.is_file():
        return [f"missing {INVENTORY_PATH}"]
    if not REPORT_PATH.is_file():
        return [f"missing {REPORT_PATH}"]
    try:
        inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"inventory JSON parse failed: {type(exc).__name__}: {exc}"]
    required = {
        "authorities",
        "code_landing_inventory",
        "data_inventory",
        "environment_inventory",
        "execution",
        "family_manifests",
        "in_flight_ledger",
        "not_found",
        "schema",
        "unlabeled_corpus_census",
        "unresolved",
    }
    missing = sorted(required - set(inventory))
    if missing:
        errors.append(f"missing top-level fields: {missing}")
    if inventory.get("schema") != "e2.g0a_inventory.v1":
        errors.append("unexpected schema")
    protocol_status = inventory.get("execution", {}).get("protocol_status")
    report_lines = REPORT_PATH.read_text(encoding="utf-8").splitlines()
    expected_marker = (
        "CELL_COMPLETE: g0a"
        if protocol_status == "COMPLIANT"
        else "CELL_INVALID: g0a"
    )
    if not report_lines or report_lines[-1] != expected_marker:
        errors.append(f"REPORT final marker is not {expected_marker!r}")
    files = inventory.get("code_landing_inventory", {}).get("files", [])
    paths = [row.get("relative_path", "") for row in files]
    if paths != sorted(paths, key=str.casefold):
        errors.append("tools/e2 file inventory is not deterministically sorted")
    if inventory.get("code_landing_inventory", {}).get("file_count") != len(files):
        errors.append("tools/e2 file_count differs from file rows")
    forbidden_metric_keys = {
        "auprc",
        "auc",
        "f1",
        "precision",
        "recall",
        "score",
        "threshold",
    }

    def visit_keys(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).casefold() in forbidden_metric_keys:
                    errors.append(f"forbidden metric key present in inventory: {key}")
                visit_keys(child)
        elif isinstance(value, list):
            for child in value:
                visit_keys(child)

    visit_keys(inventory)
    return sorted(set(errors))


def collect(protocol_breaches: list[str]) -> dict[str, Any]:
    started = time.perf_counter()
    snapshot_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    collection_errors: list[str] = []

    def safe_collect(name: str, function: Callable[[], Any], fallback: Any) -> Any:
        try:
            return function()
        except Exception as exc:
            collection_errors.append(f"{name}: {type(exc).__name__}: {exc}")
            return fallback

    inventory: dict[str, Any] = {
        "authorities": safe_collect("authorities", _authority_inventory, []),
        "code_landing_inventory": safe_collect(
            "code_landing_inventory",
            _inventory_code_landing,
            {"path": str(TOOLS_E2_ROOT), "status": "ERROR"},
        ),
        "data_inventory": {
            "cubicasa_ir": safe_collect(
                "cubicasa_ir",
                _inventory_cubicasa,
                {
                    "root": str(CUBICASA_IR_ROOT),
                    "splits": {
                        split: {"path": str(CUBICASA_IR_ROOT / split), "status": "ERROR"}
                        for split in ("test", "train", "val")
                    },
                },
            ),
            "gen2_full_pack": safe_collect(
                "gen2_full_pack",
                _inventory_gen2,
                {"path": str(GEN2_PACK_ROOT), "status": "ERROR"},
            ),
            "scene_counts": safe_collect(
                "scene_counts",
                _inventory_scenes,
                {
                    "C0": {"path": str(C0_SCENES_ROOT), "status": "ERROR"},
                    "L1": {"path": str(L1_SCENES_ROOT), "status": "ERROR"},
                },
            ),
        },
        "environment_inventory": safe_collect(
            "environment_inventory",
            _inventory_environment,
            {
                "dgx_ssh": {"reachable": False},
                "docker": {"image_count": 0, "images": [], "probe": {"returncode": None}},
                "gpu": {
                    "nvidia_smi_probe": {"returncode": None},
                    "rtx_5070_ti_recognized": False,
                },
                "python": {"version": platform.python_version()},
                "torch": {"import_ok": False},
            },
        ),
        "execution": {
            "collection_elapsed_seconds": None,
            "collection_errors": collection_errors,
            "content_boundaries": {
                "cubicasa_payloads_parsed": False,
                "gen2_truth_payloads_parsed": False,
                "model_executed": False,
                "score_bearing_result_objects_parsed_wholesale": False,
            },
            "git_commands_used_by_collector": False,
            "output_directory": str(CELL_DIR),
            "protocol_breaches": sorted(set(protocol_breaches), key=str.casefold),
            "protocol_status": "INVALID_PROTOCOL_BREACH" if protocol_breaches else "COMPLIANT",
            "repository_writes_by_collector": False,
            "snapshot_utc": snapshot_utc,
        },
        "family_manifests": safe_collect(
            "family_manifests",
            _inventory_family_ledgers,
            {
                "baseline_freeze": {
                    "source_path": str(BASELINE_RESULTS_PATH),
                    "status": "ERROR",
                },
                "bstar_repair": {
                    "source_path": str(BSTAR_MANIFEST_PATH),
                    "status": "ERROR",
                },
            },
        ),
        "in_flight_ledger": {},
        "not_found": [],
        "schema": "e2.g0a_inventory.v1",
        "unlabeled_corpus_census": safe_collect(
            "unlabeled_corpus_census",
            _inventory_corpora,
            {"content_parsed": False, "corpora": {}, "status": "ERROR"},
        ),
        "unresolved": [],
    }
    inventory["execution"]["collection_errors"] = sorted(collection_errors, key=str.casefold)
    inventory["not_found"] = _collect_not_found(inventory)
    inventory["unresolved"] = _collect_unresolved(inventory)
    inventory["unresolved"].extend(inventory["execution"]["collection_errors"])
    inventory["unresolved"] = sorted(set(inventory["unresolved"]), key=str.casefold)
    inventory["in_flight_ledger"] = safe_collect(
        "in_flight_ledger",
        _inventory_in_flight,
        {"cells": [], "path": str(CELLS_ROOT), "status": "ERROR"},
    )
    inventory["execution"]["collection_elapsed_seconds"] = round(
        time.perf_counter() - started, 6
    )

    _atomic_write_text(REPORT_PATH, _render_report(inventory))

    # Iterate the cell census so inventory.json and REPORT.md sizes are reflected
    # without leaving a self-size drift.  All timing fields are frozen above.
    for _ in range(8):
        inventory["in_flight_ledger"] = _inventory_in_flight()
        _write_json(INVENTORY_PATH, inventory)
        own_cell = next(
            (
                row
                for row in inventory["in_flight_ledger"]["cells"]
                if row["cell"].casefold() == CELL_DIR.name.casefold()
            ),
            None,
        )
        if own_cell is None:
            continue
        recorded_size = next(
            (
                row["bytes"]
                for row in own_cell["outputs"]
                if row["relative_path"] == INVENTORY_PATH.name
            ),
            None,
        )
        if recorded_size == INVENTORY_PATH.stat().st_size:
            break
    return inventory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol-breach",
        action="append",
        default=[],
        help="record an executor-side breach and emit CELL_INVALID instead of CELL_COMPLETE",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate existing inventory.json and REPORT.md without recollecting",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.validate_only:
        errors = _validate_outputs()
        if errors:
            for error in errors:
                print(f"VALIDATION_ERROR: {error}", file=sys.stderr)
            return 1
        inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
        print(
            "VALIDATION_RESULT: PASS "
            f"protocol_status={inventory['execution']['protocol_status']}"
        )
        return 0
    inventory = collect(args.protocol_breach)
    errors = _validate_outputs()
    if errors:
        for error in errors:
            print(f"VALIDATION_ERROR: {error}", file=sys.stderr)
        return 1
    print(
        "COLLECTION_RESULT: WRITTEN "
        f"protocol_status={inventory['execution']['protocol_status']} "
        f"inventory={INVENTORY_PATH} report={REPORT_PATH}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
