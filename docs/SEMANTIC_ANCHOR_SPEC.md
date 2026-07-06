# Semantic Anchor Spec (Wave 5, Lane W5-ANCHOR)

## Why

The program goal is agents that read a drawing, interpret it, and verify their
own interpretation by writing it back. The missing piece between "read" and
"interpret" is a place to put the interpretation: a semantic anchor lets an
agent stamp its reading of one entity (a wall is load-bearing, a block is a
door of a specific family, a dimension means X) directly onto that entity, in
a staged copy of the drawing, and read it back later -- in the same session,
in a later session, or from a different agent. The drawing becomes an
externalized semantic database, not just geometry.

## Substrate this reuses (no new native op)

Everything here is a Python-layer composition of two ALREADY LIVE-CERTIFIED
native capabilities:

* **Write**: the `set_entity_xdata_by_handle` patch op (native op
  `modify.entity.xdata`, `tools/patch_ops/entities.py` /
  `src/Ariadne.AcadNative/families/m08g_handlers.inc`). Args:
  `{handle, app_name, values:[{code,value}]}`. `setXData` REPLACES only the
  xdata registered under the given `app_name`; other applications' xdata on
  the same entity is untouched.
* **Read**: xdata is already carried through into every entity in the
  extracted IR (`entity["xdata"]`, `tools/ir_builder.py`, sourced from
  `collectModelSpaceGraph`'s `xdataBlocksJson`), and independently via
  `inspect.entity.get_xdata`. No new native read path was needed.

`tools/anchor_ops.py` adds ONLY the encode/decode/patch-building logic; it
never touches `src/` C++.

## Envelope schema (schema_version 1)

```json
{
  "schema_version": 1,
  "author_agent": "claude-w5-anchor",
  "timestamp": "2026-07-06T12:00:00+00:00",
  "tags": ["load_bearing", "verified"],
  "body": { "...": "arbitrary JSON, the actual interpretation" },
  "tombstone": false
}
```

`tombstone` is an addition beyond the plan's original 5-field schema -- see
"Clear semantics" below for why it exists.

Stored under registered application **`ARIADNE_ANCHOR`** as entity xdata.

## Wire-safety discovery (load-bearing finding)

**First implementation attempt used a plain JSON header/chunk and failed
live.** The native `modify.entity.xdata` handler's `values` array
item-boundary scanner (`m08g_handlers.inc`) finds each `{...}` item with
naive, non-nesting-aware `job.find('{', scan)` / `job.find('}', ob)` calls.
A `"value"` string that itself contains a literal `{` or `}` -- which any
JSON-serialized header or chunk necessarily does, since JSON syntax is full of
braces and neither character needs escaping inside a JSON string -- makes the
scanner latch onto the WRONG closing brace: the one embedded in the string's
own content, not the outer item's real terminator. This truncates the item
and corrupts every subsequent `jsonFindString()` read of `"value"`.

Live-reproduced on `tests/fixtures/native_sample.dwg`: a JSON header
`{"v":1,"n":5,"len":123,"sha256":"..."}` written via `anchor.set` and read
back through a fresh accoreconsole reopen came back as the 2-byte garbage
string `{\` -- not a crash, not an error, a silently wrong read. That is
exactly the class of bug this codebase's no-fake-success discipline exists to
catch, and it was caught here by the live cert, not assumed away.

This is a Python-layer-only lane (no C++ changes here; `src/` is owned by a
concurrent lane), so the fix had to be on the wire-format side: **never put a
brace or quote character in an xdata string value in the first place.** The
JSON envelope is base64-encoded (`base64.b64encode`, alphabet exactly
`[A-Za-z0-9+/=]` -- no braces, quotes, or backslashes) BEFORE chunking, and
the header is a plain `key=value`, pipe-delimited string, never JSON.

## Encoding / chunking

DXF/ObjectARX's documented hard limit for a single extended-data string
(group codes 1000/1003/1005) is **255 characters**. The envelope is
JSON-serialized (UTF-8, `ensure_ascii=False`) and then **base64-encoded**
(see "Wire-safety discovery" above). The resulting pure-ASCII base64 text is
split into chunks of at most **`MAX_CHUNK_BYTES = 250`** bytes each -- a
5-byte safety margin under the 255 ceiling. Because base64 output is 1 byte
per character, chunk boundaries can fall anywhere without any multi-byte
concern; the general-purpose `_utf8_chunks` helper (which DOES carefully
avoid splitting a multi-byte UTF-8 sequence, backing off from any
continuation byte `(b & 0xC0) == 0x80`) is reused here for the base64 text,
where that safety property is automatically satisfied since every base64
character is a single ASCII byte. Korean/CJK text in the anchor body is
handled once, earlier, by the UTF-8-to-base64 round trip treating it as
opaque bytes -- it is never split as text at all.

The `values` array sent to `modify.entity.xdata` is:

```
values[0]    = {"code": 1000, "value": "ANCHOR1|n=<chunk_count>|len=<total_utf8_bytes>|sha256=<hex digest>"}
values[1..n] = {"code": 1000, "value": "<base64 chunk i>"}
```

On read, `anchor.get` reassembles chunks 1..n in order, base64-decodes the
joined text, verifies the decoded byte length and sha256 against the header,
and only then `json.loads()`s the result. Any mismatch (truncated xdata,
tampered chunk, wrong chunk count, invalid base64) raises `AnchorError` --
never a silent partial/garbage reconstruction.

## Size guard

ObjectARX documents a per-entity xdata ceiling of roughly 16 KB, **shared
across every registered application** on that entity, not just ours.
`tools/anchor_ops.py` enforces **`MAX_ANCHOR_BYTES = 8192`** (half that
nominal ceiling) as a conservative cap on the whole envelope's UTF-8 byte
size, checked BEFORE any chunking or native call. An oversized anchor is
rejected with a `blocked` status and an honest `AnchorError` message -- it is
never silently truncated to fit.

## Clear semantics (known limitation)

`anchor.clear` is a **logical (tombstone) clear, not true XDATA removal**.

The ObjectARX-documented way to delete an application's xdata from an entity
is `setXData()` with a resbuf chain containing ONLY the `{1001, appName}`
record and no other codes. The existing `modify.entity.xdata` native handler
(`m08g_handlers.inc`) unconditionally rejects an empty `values` array with
`MISSING_ARG` **before** it ever builds the resbuf chain:

```cpp
if (items.empty()) {
    emitNativeError(r, "MISSING_ARG", "modify.entity.xdata requires at least one item in 'values'");
    return true;
}
```

That check runs regardless of the caller -- there is no way to reach the
"only the appname record" resbuf shape from the Python layer without relaxing
this guard, which is a C++ change and out of this lane's scope (Python layer
only; `src/` is owned by a concurrent lane). Given that constraint,
`anchor.clear` instead overwrites the entity's `ARIADNE_ANCHOR` xdata with a
minimal envelope carrying `tombstone: true` and an empty `body`/`tags`.
`anchor.get` and `anchor.list` both treat `tombstone: true` as "no anchor
present" -- so from every anchor-API consumer's point of view, clearing does
make the anchor disappear. The one honest caveat: the raw xdata bytes remain
attached to the entity (now holding a small tombstone marker) until a future
lane relaxes the native guard or adds a dedicated removal op.

## API surface

Four operations, registered in `config/operations.v2.json` under family
`anchor`, reachable via `cadctl.Cad` and the `cad.anchor_*` MCP tools
(mirrors how `query.entities`/`validate.ir` are exposed):

| Op | cadctl | MCP tool | Kind |
|---|---|---|---|
| `anchor.set`   | `Cad.anchor_set(dwg_path, handle, body, out_dir, author_agent, tags?)` | `cad.anchor_set`   | write (staged copy) |
| `anchor.get`   | `Cad.anchor_get(ir_path, handle)`                                     | `cad.anchor_get`   | read (already-extracted IR) |
| `anchor.list`  | `Cad.anchor_list(ir_path)`                                            | `cad.anchor_list`  | read (already-extracted IR) |
| `anchor.clear` | `Cad.anchor_clear(dwg_path, handle, out_dir, author_agent)`           | `cad.anchor_clear` | write (staged copy), tombstone only |

`anchor.set` upserts naturally: calling it twice on the same handle replaces
the previous anchor (setXData replaces only its own app's xdata block), it
does not stack duplicate anchors.

## Truthful statuses

Following this codebase's no-fake-success convention:

* `anchor.get`/`anchor.list`: `not_found` (no entity / no anchor block /
  tombstoned), `malformed` (xdata present but fails checksum/schema
  validation -- reported, never swallowed), `ok`.
* `anchor.set`/`anchor.clear`: `blocked` (size-guard rejection, before any
  DWG touch), `not_implemented` (a required sibling module is absent),
  otherwise the `patch_engine.apply_staged` result status is passed through
  unchanged (`ok`/`partial`/`blocked`/`unavailable`/`not_implemented`).

## Live cert evidence

See `build_log.md`, section "Lane W5-ANCHOR", for the numbers: fixture
sha256 before/after, the exact envelope written (Korean text + nested JSON),
the independent fresh-process reopen, and the byte-identical reassembly
proof.
