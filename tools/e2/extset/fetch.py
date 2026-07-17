#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""External dataset fetch tooling (CARD S3-A).

Subcommands:
  download --set NAME --dest DIR   resumable HTTP GET (Range) + optional sha256
  inventory --dest DIR             write inventory.json under DIR
  --selftest                       offline validation (no sockets / no network)

sources.json schema: sources=src.v1; every artifact url carries verified:false
until a later online step flips them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

SOURCES_REL = Path("reports") / "e2" / "s3" / "sources.json"
URL_RE = re.compile(
    r"^https?://[^\s/$.?#].[^\s]*$",
    re.IGNORECASE,
)
CHUNK = 1024 * 256


def _repo_root() -> Path:
    # tools/e2/extset/fetch.py -> repo root is parents[3]
    return Path(__file__).resolve().parents[3]


def load_sources(path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or (_repo_root() / SOURCES_REL)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("sources") != "src.v1":
        raise ValueError(f"unsupported sources schema: {data.get('sources')!r}")
    if "sets" not in data or not isinstance(data["sets"], dict):
        raise ValueError("sources.json missing sets object")
    return data


def validate_url_format(url: str) -> bool:
    if not isinstance(url, str) or not url.strip():
        return False
    if url.startswith("file://"):
        # offline / selftest local reads only
        parsed = urllib.parse.urlparse(url)
        return bool(parsed.path)
    return bool(URL_RE.match(url))


def validate_sources(data: Dict[str, Any]) -> List[str]:
    """Return list of violation strings (empty = ok)."""
    violations: List[str] = []
    sets = data.get("sets") or {}
    for set_name, meta in sets.items():
        homepage = meta.get("homepage")
        if not validate_url_format(homepage or ""):
            violations.append(f"{set_name}.homepage invalid url: {homepage!r}")
        arts = meta.get("artifacts")
        if not isinstance(arts, list) or not arts:
            violations.append(f"{set_name}.artifacts missing or empty")
            continue
        for i, art in enumerate(arts):
            if not isinstance(art, dict):
                violations.append(f"{set_name}.artifacts[{i}] not object")
                continue
            url = art.get("url")
            if not validate_url_format(url or ""):
                violations.append(f"{set_name}.artifacts[{i}].url invalid: {url!r}")
            if art.get("verified") is not False:
                violations.append(
                    f"{set_name}.artifacts[{i}].verified must be false "
                    f"(got {art.get('verified')!r})"
                )
            if "name" not in art or not art["name"]:
                violations.append(f"{set_name}.artifacts[{i}].name missing")
            if "sha256" not in art:
                violations.append(f"{set_name}.artifacts[{i}].sha256 key missing")
            if "size_hint" not in art:
                violations.append(f"{set_name}.artifacts[{i}].size_hint key missing")
        if not meta.get("license_note"):
            violations.append(f"{set_name}.license_note missing")
    return violations


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _file_url_to_path(url: str) -> Path:
    parsed = urllib.parse.urlparse(url)
    # Windows: file:///C:/path or file:///D:/path
    path = urllib.request.url2pathname(parsed.path)
    return Path(path)


def _http_download_resumable(
    url: str,
    dest_file: Path,
    expected_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """Resumable HTTP download using Range. Uses urllib (stdlib)."""
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    existing = dest_file.stat().st_size if dest_file.is_file() else 0
    headers: Dict[str, str] = {}
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            mode = "ab" if status == 206 and existing > 0 else "wb"
            if mode == "wb" and existing > 0:
                # server ignored Range — restart
                existing = 0
            written = 0
            with dest_file.open(mode) as out:
                while True:
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
                    written += len(chunk)
    except urllib.error.HTTPError as e:
        if e.code == 416 and existing > 0:
            # already complete per server
            written = 0
        else:
            raise

    result: Dict[str, Any] = {
        "url": url,
        "path": str(dest_file),
        "bytes_on_disk": dest_file.stat().st_size if dest_file.is_file() else 0,
        "resumed_from": existing if existing > 0 else 0,
        "ok": True,
    }
    if expected_sha256:
        digest = sha256_file(dest_file)
        result["sha256"] = digest
        result["sha256_ok"] = digest.lower() == expected_sha256.lower()
        if not result["sha256_ok"]:
            result["ok"] = False
            raise ValueError(
                f"sha256 mismatch for {dest_file}: got {digest}, "
                f"expected {expected_sha256}"
            )
    return result


def download_file_url_resumable(
    url: str,
    dest_file: Path,
    expected_sha256: Optional[str] = None,
    *,
    simulate_partial: Optional[int] = None,
) -> Dict[str, Any]:
    """Resume-capable local file:// copy (no sockets).

    Reads source via Path I/O. If dest exists with size N, continues from offset N.
    If simulate_partial is set on first call path, only that many bytes are copied
    (used by selftest to force a partial then resume).
    """
    src = _file_url_to_path(url)
    if not src.is_file():
        raise FileNotFoundError(f"file:// source missing: {src}")

    dest_file.parent.mkdir(parents=True, exist_ok=True)
    existing = dest_file.stat().st_size if dest_file.is_file() else 0
    total = src.stat().st_size

    if existing > total:
        dest_file.unlink()
        existing = 0

    to_copy = total - existing
    if simulate_partial is not None and existing == 0:
        to_copy = min(to_copy, max(0, simulate_partial))

    with src.open("rb") as inf, dest_file.open("ab" if existing else "wb") as out:
        inf.seek(existing)
        remaining = to_copy
        while remaining > 0:
            chunk = inf.read(min(CHUNK, remaining))
            if not chunk:
                break
            out.write(chunk)
            remaining -= len(chunk)

    result: Dict[str, Any] = {
        "url": url,
        "path": str(dest_file),
        "bytes_on_disk": dest_file.stat().st_size,
        "source_size": total,
        "resumed_from": existing,
        "complete": dest_file.stat().st_size == total,
        "ok": True,
    }
    if expected_sha256 and result["complete"]:
        digest = sha256_file(dest_file)
        result["sha256"] = digest
        result["sha256_ok"] = digest.lower() == expected_sha256.lower()
        if not result["sha256_ok"]:
            result["ok"] = False
            raise ValueError(
                f"sha256 mismatch for {dest_file}: got {digest}, "
                f"expected {expected_sha256}"
            )
    return result


def download_url(
    url: str,
    dest_file: Path,
    expected_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    if url.startswith("file://"):
        return download_file_url_resumable(url, dest_file, expected_sha256)
    return _http_download_resumable(url, dest_file, expected_sha256)


def artifact_dest_name(art: Dict[str, Any]) -> str:
    name = art.get("name") or "artifact"
    url = art.get("url") or ""
    parsed = urllib.parse.urlparse(url)
    base = os.path.basename(parsed.path.rstrip("/"))
    if base and "." in base:
        # keep remote filename if it looks like a file
        return base
    # homepage-style URLs: use artifact name + .bin placeholder
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "artifact"
    return safe


def cmd_download(set_name: str, dest: Path, sources_path: Optional[Path] = None) -> int:
    data = load_sources(sources_path)
    sets = data["sets"]
    if set_name not in sets:
        print(f"ERROR: unknown set {set_name!r}; known={sorted(sets)}", file=sys.stderr)
        return 2
    meta = sets[set_name]
    dest.mkdir(parents=True, exist_ok=True)
    results = []
    for art in meta.get("artifacts") or []:
        url = art["url"]
        out_name = artifact_dest_name(art)
        out_path = dest / out_name
        sha = art.get("sha256")
        print(f"download set={set_name} artifact={art.get('name')} -> {out_path}")
        print(f"  url={url} verified={art.get('verified')}")
        if url.startswith("http://") or url.startswith("https://"):
            if art.get("verified") is not True:
                print(
                    "  SKIP network fetch: artifact verified!=true "
                    "(offline card / unverified URL). Use online step to flip."
                )
                results.append(
                    {
                        "name": art.get("name"),
                        "url": url,
                        "skipped": True,
                        "reason": "unverified_or_offline",
                    }
                )
                continue
        info = download_url(url, out_path, sha if sha else None)
        results.append({"name": art.get("name"), **info})
        print(f"  ok bytes={info.get('bytes_on_disk')} resumed_from={info.get('resumed_from')}")

    manifest = {"set": set_name, "dest": str(dest), "results": results}
    man_path = dest / "fetch_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {man_path}")
    return 0


def build_inventory(dest: Path) -> Dict[str, Any]:
    files: List[Dict[str, Any]] = []
    ext_hist: Dict[str, int] = {}
    total_bytes = 0
    if not dest.is_dir():
        raise FileNotFoundError(f"inventory dest not a directory: {dest}")
    for root, _dirs, names in os.walk(dest):
        # skip our own inventory output if re-run
        for name in names:
            if name == "inventory.json":
                continue
            p = Path(root) / name
            try:
                size = p.stat().st_size
            except OSError:
                continue
            total_bytes += size
            ext = p.suffix.lower() if p.suffix else "(none)"
            ext_hist[ext] = ext_hist.get(ext, 0) + 1
            rel = str(p.relative_to(dest)).replace("\\", "/")
            files.append({"path": rel, "size": size, "ext": ext})
    inv = {
        "inventory": "inv.v1",
        "dest": str(dest),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "extensions": dict(sorted(ext_hist.items())),
        "files": sorted(files, key=lambda x: x["path"]),
    }
    return inv


def cmd_inventory(dest: Path) -> int:
    inv = build_inventory(dest)
    out = dest / "inventory.json"
    out.write_text(json.dumps(inv, indent=2), encoding="utf-8")
    print(
        f"inventory ok file_count={inv['file_count']} "
        f"total_bytes={inv['total_bytes']} extensions={inv['extensions']}"
    )
    print(f"wrote {out}")
    return 0


def path_to_file_url(path: Path) -> str:
    return Path(path).resolve().as_uri()


def run_selftest() -> int:
    print("=== S3-A fetch.py --selftest (OFFLINE) ===")
    failures: List[str] = []

    # 1) URL format validation for all sources.json entries
    sources_path = _repo_root() / SOURCES_REL
    print(f"[1] load+validate {sources_path}")
    data = load_sources(sources_path)
    violations = validate_sources(data)
    if violations:
        for v in violations:
            print(f"  FAIL: {v}")
            failures.append(v)
    else:
        n_sets = len(data["sets"])
        n_arts = sum(len(m.get("artifacts") or []) for m in data["sets"].values())
        print(f"  PASS: {n_sets} sets, {n_arts} artifacts, all urls ok, verified=false")

    # 2) resume-logic unit check via file:// (no sockets)
    print("[2] resume-logic file:// unit check")
    with tempfile.TemporaryDirectory(prefix="s3a_fetch_resume_") as td:
        td_path = Path(td)
        src = td_path / "payload.bin"
        payload = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" * 64  # 2304 bytes
        src.write_bytes(payload)
        src_url = path_to_file_url(src)
        dest = td_path / "out" / "payload.bin"
        expected = hashlib.sha256(payload).hexdigest()

        # partial first
        r1 = download_file_url_resumable(
            src_url, dest, expected_sha256=None, simulate_partial=500
        )
        if r1["bytes_on_disk"] != 500 or r1["complete"]:
            msg = f"partial write unexpected: {r1}"
            print(f"  FAIL: {msg}")
            failures.append(msg)
        else:
            print(f"  partial ok bytes={r1['bytes_on_disk']} resumed_from={r1['resumed_from']}")

        # resume to completion + sha256
        r2 = download_file_url_resumable(src_url, dest, expected_sha256=expected)
        if not r2["complete"] or r2["resumed_from"] != 500:
            msg = f"resume unexpected: {r2}"
            print(f"  FAIL: {msg}")
            failures.append(msg)
        elif not r2.get("sha256_ok"):
            msg = f"sha256 failed: {r2}"
            print(f"  FAIL: {msg}")
            failures.append(msg)
        elif dest.read_bytes() != payload:
            msg = "payload bytes mismatch after resume"
            print(f"  FAIL: {msg}")
            failures.append(msg)
        else:
            print(
                f"  PASS: resume complete bytes={r2['bytes_on_disk']} "
                f"resumed_from={r2['resumed_from']} sha256_ok=True"
            )

    # 3) inventory on temp dir with 3 fake files
    print("[3] inventory on temp dir (3 fake files)")
    with tempfile.TemporaryDirectory(prefix="s3a_fetch_inv_") as td:
        td_path = Path(td)
        (td_path / "a.txt").write_text("one", encoding="utf-8")
        (td_path / "b.DXF").write_bytes(b"0\nSECTION\n")
        sub = td_path / "sub"
        sub.mkdir()
        (sub / "c.svg").write_text("<svg/>", encoding="utf-8")
        inv = build_inventory(td_path)
        out = td_path / "inventory.json"
        out.write_text(json.dumps(inv, indent=2), encoding="utf-8")
        ok = (
            inv["file_count"] == 3
            and inv["extensions"].get(".txt") == 1
            and inv["extensions"].get(".dxf") == 1
            and inv["extensions"].get(".svg") == 1
            and out.is_file()
        )
        if not ok:
            msg = f"inventory unexpected: {inv}"
            print(f"  FAIL: {msg}")
            failures.append(msg)
        else:
            print(
                f"  PASS: file_count={inv['file_count']} "
                f"extensions={inv['extensions']} total_bytes={inv['total_bytes']}"
            )

    if failures:
        print(f"SELFTEST FAIL count={len(failures)}")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("SELFTEST PASS")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="S3-A external dataset fetch tooling")
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="offline selftest (no network)",
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=None,
        help="override path to sources.json",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_dl = sub.add_parser("download", help="download a named set")
    p_dl.add_argument("--set", dest="set_name", required=True)
    p_dl.add_argument("--dest", type=Path, required=True)

    p_inv = sub.add_parser("inventory", help="write inventory.json for a directory")
    p_inv.add_argument("--dest", type=Path, required=True)

    args = parser.parse_args(argv)

    if args.selftest:
        return run_selftest()

    if args.cmd == "download":
        return cmd_download(args.set_name, args.dest, args.sources)
    if args.cmd == "inventory":
        return cmd_inventory(args.dest)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
