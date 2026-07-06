#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""anchor_ops -- semantic anchor read/write (CAD OS Layer, Wave 5 / Lane W5-ANCHOR).

The bridge between an agent READING a drawing and an agent INTERPRETING it:
this module lets an agent stamp its interpretation of an entity INTO the
drawing itself (a staged copy, never the original) as XDATA under the
registered application ``ARIADNE_ANCHOR``, then read that interpretation back
later -- the drawing becomes the agent's externalized semantic memory.

Design (full spec: docs/SEMANTIC_ANCHOR_SPEC.md):
  * NO new native (C++/ObjectARX) op. Every write reuses the existing, already
    live-certified ``set_entity_xdata_by_handle`` patch op (native op
    ``modify.entity.xdata``, see tools/patch_ops/entities.py and
    src/Ariadne.AcadNative/families/m08g_handlers.inc). This module's only job
    is Python-side: encode an anchor envelope into that op's ``values`` array,
    and decode it back out of the xdata this codebase already extracts into
    every entity's IR (``entity["xdata"]``, see tools/ir_builder.py).
  * Anchor envelope schema (schema_version 1):
        {schema_version, author_agent, timestamp, tags[], body{}, tombstone}
    ``tombstone`` is an addition beyond the originally specified 5 fields --
    see build_anchor_clear_patch's docstring for why anchor.clear needs it.
  * Encoding: the envelope is JSON-serialized (UTF-8, ensure_ascii=False so
    Korean/etc. text is decoded correctly before re-encoding to base64 below).
    DISCOVERED CONSTRAINT (live-cert finding): the native modify.entity.xdata
    handler's values-array item scanner does naive brace-matching
    (job.find('{')/job.find('}')) with no string-literal awareness, so a
    "value" string that itself contains a literal '{' or '}' -- which any
    JSON-shaped text does -- corrupts item parsing (live-reproduced: a JSON
    header round-tripped back as 2-byte garbage). The fix (Python-layer only,
    no C++ touched): the JSON payload is **base64-encoded** before chunking,
    so every value on the wire uses only the brace/quote-free alphabet
    [A-Za-z0-9+/=]. See encode_anchor_values' docstring and
    docs/SEMANTIC_ANCHOR_SPEC.md, "Wire-safety discovery". DXF/ObjectARX group
    codes 1000/1003/1005 (string xdata) are documented to cap a single string
    at 255 characters; the base64 text is therefore chunked across several
    1000-code items, each independently under that cap (see _utf8_chunks --
    applied here to the base64 ASCII string, so there is no multi-byte
    concern for the chunks themselves; Korean/etc. text safety is handled
    once, before encoding, by round-tripping through UTF-8/base64 as opaque
    bytes).
  * values[0] is a small plain-text *header* item (pipe-delimited
    "ANCHOR1|n=..|len=..|sha256=.."), never JSON and never part of the payload
    text itself; values[1:1+n] are the base64 payload chunks in order.
    Reassembly re-joins them, base64-decodes, verifies length + sha256, then
    json.loads()s the result -- any mismatch is a loud AnchorError, never a
    silently-wrong partial read.
  * Size guard: MAX_ANCHOR_BYTES is a conservative cap well under ObjectARX's
    ~16KB-per-entity-ALL-APPS xdata ceiling (this module owns only its own
    app's slice of that shared budget). Oversized payloads are REJECTED
    (AnchorError) before any native call -- never silently truncated.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SCHEMA_ID = "ariadne.semantic_anchor.v1"
SCHEMA_VERSION = 1

#: the AcDbRegAppTable application name every anchor's xdata is registered
#: under. Reusing the same handle-targeted xdata write set_entity_xdata_by_handle
#: already uses for arbitrary app_name values -- ARIADNE_ANCHOR is just OUR
#: choice of app name, not a new native capability.
APP_NAME = "ARIADNE_ANCHOR"

#: DXF/ObjectARX hard limit for a single extended-data string item (group
#: codes 1000/1003/1005) is 255 characters. We stay well under that so a
#: chunk is never rejected regardless of any per-call overhead; empirically
#: exercised at the 250-byte boundary in tests/unit/test_anchor_ops.py and in
#: the live cert (see build_log.md "Lane W5-ANCHOR").
MAX_CHUNK_BYTES = 250

#: Conservative cap on the TOTAL anchor envelope (UTF-8 bytes of the whole
#: JSON envelope, before chunking/header overhead). ObjectARX's documented
#: per-entity xdata ceiling is shared across ALL registered applications
#: (~16KB total); this cap keeps our own app's slice small and leaves
#: generous headroom for whatever else may be attached to the same entity.
MAX_ANCHOR_BYTES = 8192

#: Reserved envelope field. anchor.clear cannot truly remove RegApp xdata
#: (see build_anchor_clear_patch); it overwrites with a tombstone envelope
#: instead, and anchor.get/anchor.list both treat tombstone=True as absent.
_TOMBSTONE_FIELD = "tombstone"


class AnchorError(ValueError):
    """A caller-facing anchor encode/decode failure: size-guard rejection,
    malformed chunk header, checksum mismatch, bad schema_version, ...

    Callers must surface this as a truthful status (blocked/malformed) and
    must never fabricate a fallback anchor or silently drop the error.
    """


# --------------------------------------------------------------------------- #
# Chunking primitives (pure, no I/O -- unit-testable without AutoCAD)
# --------------------------------------------------------------------------- #

def _utf8_chunks(text: str, max_bytes: int) -> List[str]:
    """Split ``text`` into chunks of at most ``max_bytes`` UTF-8 bytes each,
    never cutting a multi-byte code point in half.

    Returns at least one chunk (possibly empty) so an empty ``text`` still
    round-trips through encode/decode.
    """
    data = text.encode("utf-8")
    if not data:
        return [""]
    chunks: List[str] = []
    start = 0
    n = len(data)
    while start < n:
        end = min(start + max_bytes, n)
        # Back off from a UTF-8 continuation byte (0b10xxxxxx) so we never
        # split a multi-byte sequence mid-character. Only meaningful when
        # end < n -- at end == n there is no next byte to examine, and the
        # chunk simply reaches the end of the buffer.
        while end < n and end > start and (data[end] & 0xC0) == 0x80:
            end -= 1
        if end == start:
            raise AnchorError(
                "max_bytes=%d is too small to hold a single UTF-8 code point "
                "at byte offset %d" % (max_bytes, start))
        chunks.append(data[start:end].decode("utf-8"))
        start = end
    return chunks


def encode_anchor_envelope(body: Dict[str, Any], *, author_agent: str,
                           tags: Optional[List[str]] = None,
                           tombstone: bool = False,
                           timestamp: Optional[str] = None) -> Dict[str, Any]:
    """Build the anchor envelope dict: {schema_version, author_agent,
    timestamp, tags, body, tombstone}."""
    if not isinstance(author_agent, str) or not author_agent.strip():
        raise AnchorError("author_agent is required and must be a non-empty string")
    if not isinstance(body, dict):
        raise AnchorError("body must be a JSON object (dict), got %r" % type(body).__name__)
    if tags is not None and not isinstance(tags, list):
        raise AnchorError("tags must be a list of strings, got %r" % type(tags).__name__)
    return {
        "schema_version": SCHEMA_VERSION,
        "author_agent": author_agent,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "tags": list(tags or []),
        "body": body,
        _TOMBSTONE_FIELD: bool(tombstone),
    }


#: Header item prefix. The header and every chunk value must contain ONLY
#: characters from this safe set: no '{', '}', '"', or '\\'. See
#: encode_anchor_values' docstring for why -- this is a discovered, load-
#: bearing constraint of the native job transport, not a stylistic choice.
_HEADER_PREFIX = "ANCHOR1"


def encode_anchor_values(envelope: Dict[str, Any], *,
                         max_chunk_bytes: int = MAX_CHUNK_BYTES,
                         max_total_bytes: int = MAX_ANCHOR_BYTES) -> List[Dict[str, Any]]:
    """Serialize ``envelope`` into a ``modify.entity.xdata`` ``values`` array:
    one plain-text header item followed by N base64-chunk items (all group
    code 1000). Raises AnchorError if the encoded payload exceeds
    ``max_total_bytes`` -- an honest, upfront rejection, never a silent
    truncation.

    DISCOVERED CONSTRAINT (live-cert finding, Lane W5-ANCHOR): the native
    modify.entity.xdata handler's ``values`` array item-boundary scanner
    (m08g_handlers.inc) finds each item with naive ``job.find('{', scan)`` /
    ``job.find('}', ob)`` calls -- it does not track string-literal nesting.
    A "value" string that itself contains a literal ``{`` or ``}`` (e.g. a
    JSON-serialized header/chunk, since JSON syntax is full of braces and
    those characters need no escaping inside a JSON string) makes the scanner
    find the WRONG closing brace -- the first one embedded in the string's
    own content -- truncating the item and corrupting every jsonFindString()
    read of "value" downstream. Live-reproduced: a JSON header item
    ``{"v":1,...}`` round-tripped back as the 2-character garbage ``{\\``.
    This is a Python-layer-only lane (no C++ changes here), so the fix is to
    never put a brace or quote character on the wire in the first place:
    the JSON payload is base64-encoded (alphabet is exactly
    ``[A-Za-z0-9+/=]`` -- no braces, quotes, or backslashes) BEFORE chunking,
    and the header is a plain ``key=value`` pipe-delimited string, not JSON.
    See docs/SEMANTIC_ANCHOR_SPEC.md, "Wire-safety discovery".
    """
    payload = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    payload_bytes = payload.encode("utf-8")
    if len(payload_bytes) > max_total_bytes:
        raise AnchorError(
            "anchor payload is %d UTF-8 bytes, exceeds the %d-byte size guard "
            "(ObjectARX's per-entity xdata budget is shared across ALL "
            "registered applications -- keep anchor bodies small)"
            % (len(payload_bytes), max_total_bytes))
    b64 = base64.b64encode(payload_bytes).decode("ascii")
    chunks = _utf8_chunks(b64, max_chunk_bytes)  # b64 is pure ASCII: byte-safe, brace-free
    header = "%s|n=%d|len=%d|sha256=%s" % (
        _HEADER_PREFIX, len(chunks), len(payload_bytes),
        hashlib.sha256(payload_bytes).hexdigest())
    values: List[Dict[str, Any]] = [{"code": 1000, "value": header}]
    values.extend({"code": 1000, "value": c} for c in chunks)
    return values


def decode_anchor_values(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Reassemble the envelope dict from a ``values``-shaped xdata item list
    (the same ``{"code","value"}`` shape ``entity["xdata"][i]["items"]``
    already carries in the extracted IR, or ``inspect.entity.get_xdata``'s
    result). Raises AnchorError on any malformed/tampered/truncated chunk set
    -- this never guesses at a partial reconstruction.
    """
    if not items:
        raise AnchorError("no xdata items for app %r" % APP_NAME)
    header_raw = items[0].get("value")
    if not isinstance(header_raw, str) or not header_raw.startswith(_HEADER_PREFIX + "|"):
        raise AnchorError("unrecognized or missing anchor chunk header: %r" % (header_raw,))
    fields: Dict[str, str] = {}
    for part in header_raw[len(_HEADER_PREFIX) + 1:].split("|"):
        key, sep, value = part.partition("=")
        if not sep:
            raise AnchorError("malformed anchor header field %r in %r" % (part, header_raw))
        fields[key] = value
    try:
        n = int(fields["n"])
        declared_len = int(fields["len"])
        expected_sha = fields["sha256"]
    except (KeyError, ValueError) as exc:
        raise AnchorError("malformed anchor header %r: %s" % (header_raw, exc))
    if n < 0:
        raise AnchorError("anchor header has an invalid chunk count n=%d" % n)
    chunk_items = items[1:1 + n]
    if len(chunk_items) != n:
        raise AnchorError(
            "anchor header declares n=%d chunks but only %d chunk item(s) are "
            "present (truncated xdata)" % (n, len(chunk_items)))
    b64_joined = "".join(it.get("value") or "" for it in chunk_items)
    try:
        payload_bytes = base64.b64decode(b64_joined, validate=True)
    except Exception as exc:
        raise AnchorError("reassembled anchor payload is not valid base64: %s" % exc)
    if len(payload_bytes) != declared_len:
        raise AnchorError(
            "reassembled anchor body is %d bytes, header declares len=%d "
            "(truncated or corrupted xdata)" % (len(payload_bytes), declared_len))
    if hashlib.sha256(payload_bytes).hexdigest() != expected_sha:
        raise AnchorError("anchor body sha256 mismatch -- corrupted or tampered xdata")
    try:
        envelope = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, TypeError, ValueError) as exc:
        raise AnchorError("reassembled anchor body is not valid JSON: %s" % exc)
    if not isinstance(envelope, dict) or envelope.get("schema_version") != SCHEMA_VERSION:
        raise AnchorError(
            "unrecognized anchor envelope schema_version=%r (expected %r)"
            % (envelope.get("schema_version") if isinstance(envelope, dict) else None,
               SCHEMA_VERSION))
    return envelope


# --------------------------------------------------------------------------- #
# Read side: operates on an already-extracted dwg_graph_ir.v1 document (same
# convention as cadctl.Cad.query/get_entity -- no new native read op needed,
# xdata is already carried through by ir_builder.py/collectModelSpaceGraph).
# --------------------------------------------------------------------------- #

def find_anchor_xdata_items(entity: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """Return this entity's ``ARIADNE_ANCHOR`` xdata items list, or None if
    the entity carries no anchor block at all (xdata absence is not an error,
    just "no anchor here")."""
    for block in (entity.get("xdata") or []):
        if isinstance(block, dict) and block.get("app") == APP_NAME:
            return block.get("items") or []
    return None


def get_anchor_from_ir(ir: Dict[str, Any], handle: str) -> Dict[str, Any]:
    """anchor.get: locate ``handle`` in an already-extracted dwg_graph_ir.v1
    document and reassemble its ``ARIADNE_ANCHOR`` payload.

    Truthful statuses: not_found (no entity / no anchor block / tombstoned),
    malformed (xdata present but fails to decode -- a real finding, never
    swallowed), ok (envelope returned).
    """
    entities = ir.get("entities") or []
    entity = next(
        (e for e in entities if isinstance(e, dict) and e.get("handle") == handle), None)
    if entity is None:
        return {"schema": SCHEMA_ID, "status": "not_found", "handle": handle,
                "reason": "no entity with this handle in the IR"}
    items = find_anchor_xdata_items(entity)
    if items is None:
        return {"schema": SCHEMA_ID, "status": "not_found", "handle": handle,
                "reason": "entity carries no %s xdata block" % APP_NAME}
    try:
        envelope = decode_anchor_values(items)
    except AnchorError as exc:
        return {"schema": SCHEMA_ID, "status": "malformed", "handle": handle,
                "reason": str(exc)}
    if envelope.get(_TOMBSTONE_FIELD):
        return {"schema": SCHEMA_ID, "status": "not_found", "handle": handle,
                "reason": "anchor was cleared (tombstone)"}
    return {"schema": SCHEMA_ID, "status": "ok", "handle": handle, "anchor": envelope}


def list_anchors_from_ir(ir: Dict[str, Any]) -> Dict[str, Any]:
    """anchor.list: every entity in the IR carrying a live (non-tombstoned)
    ``ARIADNE_ANCHOR`` block. Malformed anchors are reported, never swallowed.
    """
    entities = ir.get("entities") or []
    live: List[Dict[str, Any]] = []
    malformed: List[Dict[str, Any]] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        items = find_anchor_xdata_items(entity)
        if items is None:
            continue
        handle = entity.get("handle")
        try:
            envelope = decode_anchor_values(items)
        except AnchorError as exc:
            malformed.append({"handle": handle, "reason": str(exc)})
            continue
        if envelope.get(_TOMBSTONE_FIELD):
            continue
        live.append({
            "handle": handle,
            "class": entity.get("class"),
            "author_agent": envelope.get("author_agent"),
            "timestamp": envelope.get("timestamp"),
            "tags": envelope.get("tags"),
            "body": envelope.get("body"),
        })
    return {"schema": SCHEMA_ID, "status": "ok", "count": len(live), "anchors": live,
            "malformed_count": len(malformed), "malformed": malformed}


# --------------------------------------------------------------------------- #
# Write side: builds a cad_patch.v1 that reuses the EXISTING
# set_entity_xdata_by_handle patch op (native modify.entity.xdata) -- no new
# native op. Caller (cadctl.Cad.anchor_set/anchor_clear) hands this to
# patch_engine.apply_staged, exactly like any other staged write.
# --------------------------------------------------------------------------- #

def build_anchor_set_patch(handle: str, body: Dict[str, Any], *, author_agent: str,
                           tags: Optional[List[str]] = None,
                           patch_id: Optional[str] = None,
                           source_agent: str = "anchor_ops") -> Dict[str, Any]:
    """anchor.set: build the cad_patch.v1 that writes (upserts) this anchor.

    ``setXData`` REPLACES only the xdata registered under our own app name
    (other applications' xdata on the same entity is untouched), so calling
    this twice for the same handle is naturally an upsert -- the second call
    replaces the first anchor, it does not stack.

    Raises AnchorError (before touching any patch/DWG) if the envelope fails
    the size guard.
    """
    if not handle:
        raise AnchorError("handle is required")
    envelope = encode_anchor_envelope(body, author_agent=author_agent, tags=tags)
    values = encode_anchor_values(envelope)
    return {
        "schema": "ariadne.cad_patch.v1",
        "patch_id": patch_id or ("anchor-set-%s" % handle),
        "title": "Set semantic anchor on %s" % handle,
        "source_agent": source_agent,
        # target_dwg is schema-required descriptive metadata only -- the REAL
        # staged copy is created and tracked by patch_engine.apply_staged
        # itself from the (dwg_path, out_dir) arguments the caller passes;
        # these placeholders just need to be non-empty and distinct (see
        # patch_engine.validate_patch_schema / _sample_patch's own convention).
        "target_dwg": {
            "staged_path": "<staged-copy-of-%s>" % handle,
            "original_path": "<original-dwg-for-%s>" % handle,
        },
        "operations": [
            {"step_id": "s1", "operation": "set_entity_xdata_by_handle",
             "args": {"handle": handle, "app_name": APP_NAME, "values": values}},
        ],
        # an xdata write never changes entity_count; declaring this postcondition
        # satisfies patch_engine's require_validation guard (mutating patches
        # must declare something to validate) and mirrors the same postcondition
        # tools/op_roundtrip_probe.py's probe_entity_xdata_roundtrip already uses
        # for this exact native op.
        "postconditions": [{"subject": "entity_count", "op": "delta_eq", "value": 0}],
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }


def build_anchor_clear_patch(handle: str, *, author_agent: str,
                             patch_id: Optional[str] = None,
                             source_agent: str = "anchor_ops") -> Dict[str, Any]:
    """anchor.clear: KNOWN LIMITATION -- this is a LOGICAL (tombstone) clear,
    not true XDATA removal.

    The native modify.entity.xdata handler unconditionally rejects an empty
    'values' array (m08g_handlers.inc's modify.entity.xdata branch: `if
    (items.empty()) { emitNativeError(..."requires at least one item"...); }`,
    checked BEFORE the resbuf chain -- which in ObjectARX would otherwise be
    exactly how you delete an app's xdata: setXData() with a resbuf containing
    ONLY the {1001, appName} record and no other codes). That guard is a
    Python-layer-only lane (no C++ changes here), so it cannot be relaxed from
    this side. anchor.clear instead overwrites the entity's ARIADNE_ANCHOR
    xdata with a minimal tombstone envelope (tombstone=true, empty body/tags);
    anchor.get/anchor.list both treat tombstone=true as "absent". See
    docs/SEMANTIC_ANCHOR_SPEC.md, "Clear semantics (known limitation)".
    """
    if not handle:
        raise AnchorError("handle is required")
    envelope = encode_anchor_envelope({}, author_agent=author_agent, tags=[], tombstone=True)
    values = encode_anchor_values(envelope)
    return {
        "schema": "ariadne.cad_patch.v1",
        "patch_id": patch_id or ("anchor-clear-%s" % handle),
        "title": "Clear (tombstone) semantic anchor on %s" % handle,
        "source_agent": source_agent,
        # see build_anchor_set_patch's target_dwg comment -- placeholder only.
        "target_dwg": {
            "staged_path": "<staged-copy-of-%s>" % handle,
            "original_path": "<original-dwg-for-%s>" % handle,
        },
        "operations": [
            {"step_id": "s1", "operation": "set_entity_xdata_by_handle",
             "args": {"handle": handle, "app_name": APP_NAME, "values": values}},
        ],
        "postconditions": [{"subject": "entity_count", "op": "delta_eq", "value": 0}],
        "policy": {"staged_copy": True, "write_mode": "write_copy"},
    }
