#!/usr/bin/env python
"""catalog_completeness.py -- CADOS WAVE-0 F0: Catalog-completeness meter.

Grounded in `.build/cados_plan/final/PLAN.md` PART 0 section 0.2 / PART 2
section 2.6 and `.build/cados_plan/redteam/R3_coverage.md` finding G0 (measured
2026-07-01, HEAD 543ae61 of `D:\\dev\\99_tools\\autocad-sdk-router`):

  "The 517-op catalog is not 'full SDK parity'. The plan's PART 2 section 2.6
  treats ~446 legitimate parity targets (517 - 60 blocked - ~11 host/charter)
  as the honest denominator, but that denominator is measured against a
  catalog that OMITS whole AcDbEntity/AcDbObject classes present in ordinary
  production DWGs (viewport/group/annotative/field/underlay/draworder/light/
  pointcloud/section/material/... all measured 0 catalog ops). F0 diffs the
  517-op catalog against the AcRxClass hierarchy actually present across a
  real corpus and forces an explicit disposition -- author / non-goal-preserve
  / corpus-exclude -- onto every uncatalogued class. No silent omission."

This module answers two questions, both derived LIVE from the registry/corpus
(never hardcoded -- PLAN.md explicitly warns "counts jitter +/-1, never
hard-code" for the derived denominator):

  1. `compute_catalog_denominator(ops)` -- of the 517 catalogued ops, how many
     are legitimate v1 parity targets once hard-blocked ops, charter-forbidden
     write_original ops, and session-bound com_activex automation are excluded
     (the "~446" figure)?
  2. `run(corpus_paths, ...)` -- for a corpus of `ariadne.dwg_graph_ir.v1`
     drawing IRs, what is the observed `dxf_name`/`class` (AcRxClass) set, and
     for each observed class: is it referenced anywhere in the operation
     catalog (`catalogued`), and if not, what forced disposition -- exactly one
     of {author, non-goal-preserve, corpus-exclude} -- does it get? This is the
     uncatalogued set U that PLAN.md section 2.6 says must annotate the 446
     denominator.

Matching discipline (why literal class-name substring, not a bare keyword):
  R3_coverage.md's own G0 table used a bare-keyword id-search ("id contains
  'viewport'") and got a FALSE POSITIVE: `render.draw.viewportgeom` and
  `extend.customentity.draw_viewport` matched "viewport" but are NOT a real
  AcDbViewport read/write path. This module instead searches for the exact
  runtime class-name literal (e.g. "AcDbViewport", not "viewport") inside each
  op record's own serialized JSON text. Verified this session: the exact-class
  search reproduces R3's 0-hit findings for every class in its G0 table (and is
  MORE precise than R3's own method -- e.g. it correctly separates
  AcDbPlotSettings [1 hit: plot.config.settings] from the AcDbPlotStyle* table
  R3 measured as 0, which R3's coarser "plotstyle" keyword search conflated).

Catalog sources searched (discovered by reading tools/operation_coverage_matrix.py
+ tools/reconcile_native_registry.py + config/*.json, per the F0 task): the
517-op registry `config/operations.v2.json` (the canonical catalogue --
its op COUNT is the "517-op catalogue" and the denominator source), plus the
480-op native source catalog `config/autocad_native_arx_operation_catalog.json`
(richer `summary`/`citation` text) as a secondary corroborating search corpus.
Both are read-only inputs; this tool never writes either registry.

Corpus input: one or more `ariadne.dwg_graph_ir.v1` JSON files (or directories,
recursively scanned for `*.json` and filtered to that schema). Per-entity
`class`/`dxf_name` are collected from the top-level `entities[]` array, from
`block_definitions[].def_entities` (the schema's alternate "inlined" block
geometry strategy), and from `custom_objects[].class_name`/`dxf_name` (the
schema's dedicated proxy/custom-object record -- directly relevant to the G8
proxy/OLE non-reconstructable-object finding).

Stdlib only. Registry/catalog JSON on this box is BOM-prefixed (utf-8-sig);
this tool's own output artifacts are written plain utf-8 (no BOM), matching
tools/operation_coverage_matrix.py's `_dump()` convention for generated reports
(only the registry itself round-trips with a BOM).

Usage:
  python tools/catalog_completeness.py <ir.json | dir> [<ir.json | dir> ...]
  python tools/catalog_completeness.py --out-dir measure D:\\path\\to\\corpus_dir

Public API (INTERFACE CONTRACT):
  load_operations_catalog(path=CATALOG_PATH) -> list[dict]
  compute_catalog_denominator(ops) -> dict
  discover_corpus_files(paths) -> list[Path]
  load_corpus(paths) -> (ir_docs, skipped)
  collect_observed_classes(ir_docs) -> dict[str, dict]
  build_catalog_text_index(catalog_sources) -> list[tuple]
  catalogued_by(class_name, text_index) -> list[dict]
  disposition_for(class_name, dxf_names, matched_ops, is_proxy) -> dict
  run(corpus_paths, ...) -> {"rows": [...], "summary": {...}}
  write_reports(result, out_dir) -> (jsonl_path, summary_path)
  main(argv=None) -> int
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_THIS_DIR = Path(__file__).resolve().parent
_ROOT = _THIS_DIR.parent

_JSON_ENCODING = "utf-8-sig"
IR_SCHEMA_ID = "ariadne.dwg_graph_ir.v1"

CATALOG_PATH = _ROOT / "config" / "operations.v2.json"
NATIVE_ARX_CATALOG_PATH = _ROOT / "config" / "autocad_native_arx_operation_catalog.json"
DEFAULT_OUT_DIR = _ROOT / "measure"
OUT_FILENAME = "uncatalogued_classes.jsonl"
SUMMARY_FILENAME = "catalog_completeness_summary.json"

# The forced disposition vocabulary (F0 task / PLAN.md section 2.6 / R3-G0 fix).
# Every observed class gets exactly one of these -- never left unclassified.
DISPOSITIONS = ("author", "non-goal-preserve", "corpus-exclude")

# Seeded from redteam/R3_coverage.md finding G0 (measured 2026-07-01, HEAD
# 543ae61): every one of these classes had ZERO matching ops in the live
# catalog this session. This table is CONSULTED ONLY when the live
# `catalogued_by()` check already found zero matches -- if the catalog later
# gains real ops for one of these (the live check, not this seed, is the
# source of truth), the class is reported catalogued regardless of this seed.
# Keyword matched case-insensitively as a substring of the observed class name
# or any of its observed dxf_names. Ordered most-specific-keyword first so an
# overlapping generic keyword (e.g. "ole") never shadows a more specific one
# (e.g. "ole2frame") that would otherwise report a less precise basis note.
KNOWN_UNCATALOGUED_DISPOSITIONS: List[Tuple[str, str, str]] = [
    # (keyword, disposition, note)
    ("ole2frame", "non-goal-preserve",
     "AcDbOle2Frame embedded OLE object -- G8: embed.ole.frame exists but carries "
     "no read/extract path; an IR roundtrip cannot reconstruct the embedded blob."),
    ("ole", "non-goal-preserve",
     "OLE-embedded content -- G8: non-reconstructable from an IR fingerprint."),
    ("zombie", "non-goal-preserve",
     "Zombie entity (proxy whose owning ARX app is now missing) -- G8."),
    ("proxy", "non-goal-preserve",
     "AcDbProxyEntity/AcDbProxyObject -- G8: graphics+data from an unloaded ARX "
     "app cannot be reconstructed from an IR fingerprint by definition; "
     "inspect.proxy.detect is detect-only, never a preserve/regen path."),
    ("objectcontext", "author",
     "AcDbObjectContextData (annotative scale representations) -- R3 G0: 0 ops."),
    ("annotativ", "author", "Annotative scaling -- R3 G0: 0 ops."),
    ("viewport", "author",
     "AcDbViewport (paperspace viewport) -- R3 G0: 0 real read/write ops "
     "(render.draw.viewportgeom / extend.customentity.draw_viewport are unrelated "
     "custom-entity draw hooks, not a viewport-entity path)."),
    ("sortentstable", "author", "AcDbSortentsTable (draw order) -- R3 G0: 0 ops."),
    ("sortents", "author", "Draw order (AcDbSortentsTable) -- R3 G0: 0 ops."),
    ("draworder", "author", "Draw order -- R3 G0: 0 ops."),
    ("group", "author", "AcDbGroup (named/unnamed group) -- R3 G0: 0 ops."),
    ("field", "author",
     "AcDbField (fields in text/mtext/table/attrib) -- R3 G0: 0 ops."),
    ("pdfreference", "author", "AcDbPdfReference underlay -- R3 G0: 0 ops."),
    ("dwfreference", "author", "AcDbDwfReference underlay -- R3 G0: 0 ops."),
    ("dgnreference", "author", "AcDbDgnReference underlay -- R3 G0: 0 ops."),
    ("underlay", "author", "Underlay reference (pdf/dwf/dgn) -- R3 G0: 0 ops."),
    ("pointcloud", "author", "AcDbPointCloud/PointCloudEx -- R3 G0: 0 ops."),
    ("light", "author", "AcDbLight -- R3 G0: 0 ops."),
    ("sun", "author", "AcDbSun -- R3 G0: 0 ops."),
    ("camera", "author", "AcDbCamera -- R3 G0: 0 ops."),
    ("section", "author", "AcDbSection/AcDbSectionSettings -- R3 G0: 0 ops."),
    ("helix", "author", "AcDbHelix -- R3 G0: 0 ops."),
    ("visualstyle", "author", "AcDbVisualStyle -- R3 G0: 0 ops."),
    ("scalelist", "author", "AcDbScaleList -- R3 G0: 0 ops."),
    ("layerstate", "author", "Layer state (named-object-dictionary content) -- R3 G0: 0 ops."),
    ("material", "author", "AcDbMaterial -- R3 G0: 0 ops."),
]


# --------------------------------------------------------------------------- #
# JSON helpers
# --------------------------------------------------------------------------- #

def _load_json(path: Path) -> Any:
    with open(path, "r", encoding=_JSON_ENCODING) as fh:
        return json.load(fh)


def _write_jsonl(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False))
            fh.write("\n")


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


# --------------------------------------------------------------------------- #
# 1. The op-level "~446" denominator (never hardcoded -- derived live)
# --------------------------------------------------------------------------- #

def load_operations_catalog(path: Path = CATALOG_PATH) -> List[dict]:
    """The 517-op catalogue (config/operations.v2.json `operations` array)."""
    doc = _load_json(Path(path))
    return doc.get("operations") or []


def compute_catalog_denominator(ops: List[dict]) -> dict:
    """Derive the PLAN.md section 2.6 "~446 catalogued parity targets" figure
    LIVE from ``ops`` -- never hardcode the final number (PLAN.md: "counts
    jitter +/-1 -- never hard-code"). The three exclusions, each independently
    countable against the registry:

      - hard_blocked:                     status == "blocked"            (PLAN's "60")
      - write_original_charter_forbidden: implemented but
                                           family == "active_document_write_original"
                                           (implemented-but-charter-forbidden; PLAN's "4")
      - com_activex_session_bound:        implemented ids under the "automate."
                                           prefix (live COM automation surface that
                                           needs a full-AutoCAD session; PLAN's "~7",
                                           re-triage at freeze) -- excludes the much
                                           larger extend.opm.*/extend.property.*/
                                           inspect.* catalog-only classification ops
                                           in the same com_activex family, which are
                                           NOT session-bound automation.
    """
    total = len(ops)
    blocked = [o for o in ops if o.get("status") == "blocked"]
    write_original_forbidden = [
        o for o in ops
        if o.get("status") == "implemented"
        and o.get("family") == "active_document_write_original"
    ]
    com_session_bound = [
        o for o in ops
        if o.get("status") == "implemented"
        and (o.get("id") or o.get("operation") or "").startswith("automate.")
    ]
    parity_targets = (total - len(blocked) - len(write_original_forbidden)
                       - len(com_session_bound))
    return {
        "total_catalogued_ops": total,
        "hard_blocked": len(blocked),
        "write_original_charter_forbidden": len(write_original_forbidden),
        "com_activex_session_bound_estimate": len(com_session_bound),
        "catalog_parity_targets": parity_targets,
        "formula": "total - hard_blocked - write_original_charter_forbidden - com_activex_session_bound_estimate",
        "source": (
            "PLAN.md PART 2 section 2.6: 517 - 60 blocked - 4 write_original "
            "- ~7 com_activex ~= 446 catalogued parity targets. Recomputed live "
            "from config/operations.v2.json every run; never hardcoded (PLAN.md: "
            "counts jitter +/-1 as the registry evolves)."
        ),
    }


# --------------------------------------------------------------------------- #
# 2. Corpus loading -- a corpus of ariadne.dwg_graph_ir.v1 drawing IRs
# --------------------------------------------------------------------------- #

def discover_corpus_files(paths: Iterable[str]) -> List[Path]:
    """Expand a mix of file paths and directories into a flat file list.
    Directories are scanned recursively for ``*.json`` (shape-filtered later by
    ``load_corpus``, so an unrelated json file alongside real IRs is skipped,
    never a crash)."""
    files: List[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.json")))
        elif p.is_file():
            files.append(p)
        else:
            raise FileNotFoundError("corpus path not found: {0}".format(raw))
    return files


def load_corpus(paths: Iterable[str]) -> Tuple[List[Tuple[Path, dict]], List[dict]]:
    """Load every ``ariadne.dwg_graph_ir.v1`` document found under ``paths``.

    Returns (ir_docs, skipped): ir_docs is [(path, ir_dict), ...]; skipped
    records every json file that parsed but was not a dwg_graph_ir document
    (wrong schema) or failed to parse -- never a silent drop, never a crash."""
    ir_docs: List[Tuple[Path, dict]] = []
    skipped: List[dict] = []
    for f in discover_corpus_files(paths):
        try:
            doc = _load_json(f)
        except (OSError, json.JSONDecodeError) as exc:
            skipped.append({"file": str(f), "reason": "json_parse_error: {0}".format(exc)})
            continue
        if not isinstance(doc, dict) or doc.get("schema") != IR_SCHEMA_ID:
            skipped.append({"file": str(f), "reason": "not_a_dwg_graph_ir_document"})
            continue
        ir_docs.append((f, doc))
    return ir_docs, skipped


def _iter_ir_entities(ir: dict) -> Iterable[dict]:
    """Every entity-shaped record in one IR: top-level entities[] plus any
    block_definitions[].def_entities (the schema's alternate inlined-block
    extraction strategy -- an extractor picks one strategy per
    diagnostics.coverage, so both must be walked to never under-count)."""
    for e in ir.get("entities") or []:
        yield e
    for bd in ir.get("block_definitions") or []:
        for e in bd.get("def_entities") or []:
            yield e


def _iter_ir_custom_objects(ir: dict) -> Iterable[dict]:
    """custom_objects[] -- the schema's dedicated proxy/custom-object record
    (required class_name + dxf_name, optional is_proxy). Directly relevant to
    the G8 proxy/OLE finding."""
    for c in ir.get("custom_objects") or []:
        yield c


def collect_observed_classes(ir_docs: List[Tuple[Path, dict]]) -> Dict[str, dict]:
    """Aggregate the observed dxf_name/AcRxClass set across a corpus of IRs.

    Returns {class_name: {"class", "dxf_names": set, "observed_count": int,
    "files": set[str], "sources": set[str], "is_proxy": bool}}. A record
    missing its required `class` field is never dropped -- it is bucketed
    under a visible "UNKNOWN_CLASS:<dxf_name>" sentinel so it still surfaces
    (and still gets forced a disposition downstream), rather than silently
    vanishing from the count."""
    observed: Dict[str, dict] = {}

    def _bump(class_name, dxf_name, file_label, source_kind, is_proxy=False):
        if not class_name:
            class_name = "UNKNOWN_CLASS:{0}".format(dxf_name or "UNKNOWN_DXF_NAME")
        row = observed.setdefault(class_name, {
            "class": class_name,
            "dxf_names": set(),
            "observed_count": 0,
            "files": set(),
            "sources": set(),
            "is_proxy": False,
        })
        if dxf_name:
            row["dxf_names"].add(dxf_name)
        row["observed_count"] += 1
        row["files"].add(file_label)
        row["sources"].add(source_kind)
        if is_proxy:
            row["is_proxy"] = True

    for path, ir in ir_docs:
        label = str(path)
        for e in _iter_ir_entities(ir):
            _bump(e.get("class"), e.get("dxf_name"), label, "entities")
        for c in _iter_ir_custom_objects(ir):
            _bump(c.get("class_name"), c.get("dxf_name"), label, "custom_objects",
                  is_proxy=bool(c.get("is_proxy")))

    return observed


# --------------------------------------------------------------------------- #
# 3. Catalog text-corpus + literal class-name matching
# --------------------------------------------------------------------------- #

def build_catalog_text_index(catalog_sources: List[Tuple[str, List[dict]]]) -> List[Tuple[str, str, str]]:
    """[(source_label, op_id, blob), ...] -- blob is the op record's own
    serialized JSON text. A MECHANICAL, deterministic corpus search (the same
    registry text always yields the same match set) -- not a hand-curated
    alias table."""
    index: List[Tuple[str, str, str]] = []
    for label, ops in catalog_sources:
        for op in ops:
            op_id = op.get("id") or op.get("op_id") or op.get("operation") or "?"
            blob = json.dumps(op, ensure_ascii=False)
            index.append((label, op_id, blob))
    return index


def catalogued_by(class_name: str, text_index: List[Tuple[str, str, str]]) -> List[dict]:
    """Every (source, op_id) whose serialized record literally contains the
    exact runtime class-name substring (e.g. "AcDbLine"). Deliberately matches
    on the full class name, NEVER on the bare dxf_name/keyword -- R3_coverage.md
    G0 measured that a bare "viewport" keyword search false-positives against
    unrelated ops (render.draw.viewportgeom / extend.customentity.draw_viewport).
    An empty/unknown class name never vacuously matches."""
    if not class_name or class_name.startswith("UNKNOWN_CLASS:"):
        return []
    return [{"source": label, "op_id": op_id}
            for label, op_id, blob in text_index if class_name in blob]


# --------------------------------------------------------------------------- #
# 4. Forced disposition -- every observed class gets exactly one
# --------------------------------------------------------------------------- #

def _keyword_disposition(class_name: str, dxf_names: Iterable[str]) -> Optional[Tuple[str, str, str]]:
    haystacks = [class_name.lower()] + [d.lower() for d in dxf_names]
    for keyword, disposition, note in KNOWN_UNCATALOGUED_DISPOSITIONS:
        if any(keyword in h for h in haystacks):
            return keyword, disposition, note
    return None


def disposition_for(class_name: str, dxf_names: Iterable[str], matched_ops: List[dict],
                     is_proxy: bool) -> dict:
    """Force exactly one of DISPOSITIONS onto (class_name, dxf_names) --
    never leave a class unclassified (mirrors
    operation_coverage_matrix.assign_owner_ticket's "never leave an op
    unowned"). Precedence: (1) already catalogued -- author, evidence-backed by
    the live match; (2) the curated R3 seed table; (3) an is_proxy flag carried
    by the corpus itself; (4) a forced, explicitly-flagged-for-review default."""
    if matched_ops:
        return {
            "disposition": "author",
            "disposition_basis": "catalogued",
            "basis_detail": "{0} op(s) in the live catalog already reference this class".format(
                len(matched_ops)),
            "needs_review": False,
        }
    seeded = _keyword_disposition(class_name, dxf_names)
    if seeded:
        keyword, disposition, note = seeded
        return {
            "disposition": disposition,
            "disposition_basis": "known_uncatalogued_seed:" + keyword,
            "basis_detail": note,
            "needs_review": False,
        }
    if is_proxy:
        return {
            "disposition": "non-goal-preserve",
            "disposition_basis": "custom_object_is_proxy_flag",
            "basis_detail": ("IR flagged this occurrence is_proxy=true (G8: cannot "
                              "reconstruct from an IR fingerprint by definition)"),
            "needs_review": False,
        }
    # Forced default: never leave a class without a disposition. Flagged for
    # human review since -- unlike the three cases above -- nothing here is
    # actual evidence about the RIGHT disposition, only that one was owed.
    return {
        "disposition": "author",
        "disposition_basis": "default_uncatalogued_fallback",
        "basis_detail": ("no catalog op references this class and it is not in the "
                          "curated R3 seed table; defaulting to the conservative "
                          "'we owe coverage' bucket"),
        "needs_review": True,
    }


# --------------------------------------------------------------------------- #
# 5. Orchestration
# --------------------------------------------------------------------------- #

def run(corpus_paths: Iterable[str], *, catalog_path: Path = CATALOG_PATH,
        native_catalog_path: Optional[Path] = NATIVE_ARX_CATALOG_PATH) -> dict:
    """Pure (no disk writes beyond reading inputs): compute the full F0 result.
    Returns {"rows": [...one dict per observed class...], "summary": {...}}."""
    ops = load_operations_catalog(catalog_path)
    native_ops: List[dict] = []
    if native_catalog_path is not None and Path(native_catalog_path).exists():
        native_ops = _load_json(Path(native_catalog_path)).get("operations") or []

    text_index = build_catalog_text_index([
        ("config/operations.v2.json", ops),
        ("config/autocad_native_arx_operation_catalog.json", native_ops),
    ])

    ir_docs, skipped = load_corpus(corpus_paths)
    observed = collect_observed_classes(ir_docs)

    rows = []
    for class_name in sorted(observed):
        rec = observed[class_name]
        matched = catalogued_by(class_name, text_index)
        disp = disposition_for(class_name, rec["dxf_names"], matched, rec["is_proxy"])
        rows.append({
            "schema": "ariadne.cad_os.f0_uncatalogued_class.v1",
            "class": class_name,
            "dxf_names": sorted(rec["dxf_names"]),
            "observed_count": rec["observed_count"],
            "corpus_files": sorted(rec["files"]),
            "sources": sorted(rec["sources"]),
            "catalogued": bool(matched),
            "matched_op_count": len(matched),
            "matched_ops": matched[:10],
            **disp,
        })

    uncatalogued = [r for r in rows if not r["catalogued"]]
    denom = compute_catalog_denominator(ops)
    denom["uncatalogued_class_count_U"] = len(uncatalogued)
    denom["catalog_parity_denominator_annotated"] = (
        "{0} catalogued parity targets + U({1}) uncatalogued classes requiring disposition".format(
            denom["catalog_parity_targets"], len(uncatalogued))
    )

    missing_disposition = [r["class"] for r in rows if r.get("disposition") not in DISPOSITIONS]
    needs_review = [r["class"] for r in rows if r.get("needs_review")]

    summary = {
        "schema": "ariadne.cad_os.f0_catalog_completeness_summary.v1",
        "packet": "CADOS_WAVE0_F0",
        "generated_from": {
            "catalog": "config/operations.v2.json",
            "native_catalog": "config/autocad_native_arx_operation_catalog.json",
        },
        "corpus_files_scanned": [str(p) for p, _ in ir_docs],
        "corpus_files_skipped": skipped,
        "observed_class_count": len(rows),
        "catalogued_class_count": len(rows) - len(uncatalogued),
        "uncatalogued_class_count": len(uncatalogued),
        "denominator": denom,
        "gate": {
            "every_observed_class_has_disposition": len(missing_disposition) == 0,
            "no_class_silently_omitted": len(rows) == len(observed),
        },
        "missing_disposition": missing_disposition,
        "classes_needing_review": needs_review,
    }

    return {"rows": rows, "summary": summary}


def write_reports(result: dict, out_dir: Path = DEFAULT_OUT_DIR) -> Tuple[Path, Path]:
    """DISK-FIRST: write measure/uncatalogued_classes.jsonl (one row per
    observed class) + measure/catalog_completeness_summary.json (the
    denominator/U accounting + gate)."""
    out = Path(out_dir)
    jsonl_path = out / OUT_FILENAME
    summary_path = out / SUMMARY_FILENAME
    _write_jsonl(jsonl_path, result["rows"])
    _write_json(summary_path, result["summary"])
    return jsonl_path, summary_path


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="catalog_completeness.py",
        description=("F0 -- diff the observed dxf_name/AcRxClass set of a corpus of "
                      "drawing IRs against the 517-op catalog; force a disposition "
                      "for every uncatalogued class."))
    ap.add_argument("corpus", nargs="+",
                     help="drawing-IR json file(s) and/or director(ies) to scan")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--catalog", default=str(CATALOG_PATH))
    ap.add_argument("--native-catalog", default=str(NATIVE_ARX_CATALOG_PATH))
    args = ap.parse_args(argv)

    result = run(args.corpus, catalog_path=Path(args.catalog),
                 native_catalog_path=Path(args.native_catalog))
    jsonl_path, summary_path = write_reports(result, out_dir=Path(args.out_dir))

    s = result["summary"]
    print("F0 catalog-completeness: observed={0} catalogued={1} uncatalogued={2}".format(
        s["observed_class_count"], s["catalogued_class_count"], s["uncatalogued_class_count"]))
    print("  denominator:", s["denominator"]["catalog_parity_denominator_annotated"])
    print("  gate.every_observed_class_has_disposition:", s["gate"]["every_observed_class_has_disposition"])
    if s["corpus_files_skipped"]:
        print("  skipped (not a dwg_graph_ir document):", len(s["corpus_files_skipped"]))
    print("  wrote:", jsonl_path)
    print("  wrote:", summary_path)
    return 0 if s["gate"]["every_observed_class_has_disposition"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
