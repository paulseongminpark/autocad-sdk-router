# build_log.md -- lane cc2-cpp (branch `cados/cc-cpp`)

Native C++ work log for tickets #118 and #128. Referenced by an existing
inline comment in `families/m08g_handlers.inc` ("1002 ... and 1004 (binary
chunk) are excluded -- see build_log.md") that predates this file's creation
in this worktree; this file is now that reference.

## #128 -- VPORT record circle_sides UPDATE-path anomaly

**Symptom (as given):** `write.vport.create`'s upsert -- create persists
`circle_sides`, updating an existing record does not.

**Code reading (before any live probe):** `upsertVportRecord` /
`applyVportProperties` in `AriadneNativeJob.cpp` -- the UPDATE branch opens
`kForWrite` (not `kForRead`) and calls the exact same `applyVportProperties`
the CREATE branch calls, which calls `pRec->setCircleSides(...)`
unconditionally when `props.hasCircleSides`. No code-level asymmetry between
create and update was found by inspection -- the ticket's hypothesized root
cause ("update branch opens kForRead or skips setCircleSides") does not
match what the code does.

**Live reproduction** (`op_roundtrip_probe.probe_vport_mutation`, baseline
`circle_sides=8` -> change `circle_sides=16`, staged copy of
`tests/fixtures/native_sample.dwg`): reproduced. `pre_record.circle_sides=8`,
`post_record.circle_sides=8` (unchanged) after the update call reported
`errorstatus:0, updated:true`. `status=hollow`,
`reason="the requested change to ['circle_sides'] was not detected on
re-extraction (invisible data)"`.

**Control test** (same driver, `height` instead of `circle_sides`,
9 -> 20): `status=ok`, height persisted correctly. Rules out a
generically-broken update path -- only `circle_sides` is affected.

**In-process readback (temporary diagnostic, since removed):** added a debug
field to `write.vport.create`'s own result JSON that re-opens the
just-written record for read in the SAME accoreconsole session, before that
session's own subsequent `_QSAVE`. Result: `circle_sides_readback_debug: 16`
-- `setCircleSides()` DOES update the in-memory value correctly. The value is
lost somewhere between "in-memory, correct" and "the saved DWG file",
specifically only when `circle_sides` is the ONLY field an update call
touches.

**Combo test:** bundling `circle_sides` with `height` in the SAME update
call (`{"height": 20, "circle_sides": 16}`): both persisted correctly.
`status=ok`, `changed_fields=["circle_sides","height"]`.

**Conclusion:** a `circle_sides`-only update to an EXISTING
`AcDbViewportTableRecord` is not recognized as a real drawing modification
by AutoCAD's own save pipeline (measured behavior, not something this
codebase's C++ controls) -- the in-memory value is correct but the file
save silently keeps the old on-disk value. Any OTHER field change bundled
into the same update call causes the whole record (including the
already-correct in-memory `circle_sides`) to be recognized and saved.

**Fix:** in `upsertVportRecord`'s UPDATE branch, when `props.hasCircleSides`
is set, re-assert `pRec->setHeight(pRec->height())` immediately after
`applyVportProperties` -- a true no-op (re-sets height to its own current
value) that reliably forces AutoCAD to recognize the record as modified.
Scoped to the UPDATE branch only (CREATE was never broken); scoped to
`hasCircleSides` only (this ticket's field; other "newer" per-record toggles
-- `grid_enabled`/`snap_enabled`/`ucs_follow_mode`/`ucs_per_viewport` -- were
not reported broken and were not touched or investigated further here).

**Live re-verification (final binary):** `probe_vport_mutation` circle_sides
8->16 alone: `status=ok, changed_fields=["circle_sides"]`,
`post_record.circle_sides=16`. Verdict: **FIXED**.

## #118 -- xdata 1004 (binary chunk) read classification

**Code reading:** `resbufItemJson` (`AriadneNativeJob.cpp`) already
classified codes 310/1004 as `"value_kind":"binary"` (not "unhandled") --
not a misclassification in the sense of being lumped into the wrong bucket.
But it emitted ONLY `byte_count`, never the actual bytes -- unlike every
other supported group code, which always carries a `"value"`. That is the
real gap: the payload is genuinely dropped, just not misclassified.

**Write-side finding (unexpected):** the ticket assumed "the existing xdata
write op" already supports writing a 1004 item. It does not:
`modify.entity.xdata` (`families/m08g_handlers.inc`) explicitly rejects code
1004 at parse time (`"unsupported or reserved xdata group code 1004"`, by
design, pre-existing). Live-probed baseline (before any change):
`probe_entity_xdata_roundtrip` with a `{"code":1004,...}` item ->
`status=fail`, `actual_items=[]` (the write was refused, no exception, no
crash, original untouched).

**Read-side fix:** added `bytesToHexLower(buf, len)` and changed the
310/1004 branch in `resbufItemJson` to also emit
`"value": "<lowercase hex>"` alongside `byte_count`. Guards `buf==nullptr`
and `len<=0` (returns empty string). Verified correct in isolation (a
standalone Python transliteration of the identical nibble-splitting logic,
all-256-byte-value round trip, null/zero/negative-length edge cases --
`ALL PASS`), and live-verified NOT to regress ordinary string xdata
(`probe_entity_xdata_roundtrip` with a plain `{"code":1000,...}` item after
the fix: `status=ok`, diff empty) or the full-database graph walk used by
every other probe in this session (multiple `inspect.database.graph` runs
against the real fixture, no crash).

**Write-side attempt and retraction (important, do not repeat without new
information):** to get a REAL 1004-bearing entity for a genuine live
round-trip, `modify.entity.xdata` was extended to accept code 1004 (`value`
as a hex string, decoded via a new `hexToBytes`, built into the resbuf chain
via `acutBuildList(1004, ads_binary{...}, 0)` -- the same
by-value-struct-through-varargs shape already used for `ads_point` on codes
1010-1013). Rebuilt, deployed, live-probed:

- The WRITE call itself returned success (`"set":true,"errorstatus":0`).
- The VERY NEXT step (a completely separate accoreconsole process
  re-opening the saved staged file for `inspect.database.graph`) crashed:
  `Unhandled Access Violation Reading 0x0005 Exception at 61DA7F13h`,
  `engine_exit_code: -3`. `original_unchanged` stayed true throughout (the
  crash was on a STAGED copy; the original fixture was never touched).
- Isolation: the plain-fixture graph walk (no 1004 anywhere, e.g. the #128
  probes above, run with the SAME binary) never crashed -- ruling out a
  generic regression in the read-side hex change. The crash only appears
  once a REAL 1004 chunk written by this new code exists in the file, which
  means the WRITE side produced a malformed/corrupt resbuf (the ABI
  assumption that `ads_binary`-by-value flows through `acutBuildList`'s
  varargs the same way `ads_point` does was not actually verified anywhere
  and turned out to be unsafe in practice), not that the read side has a
  live bug.
- **Retracted.** All three write-side edits (`XdItem::bin` field, the 1004
  parse branch, the 1004 resbuf-build branch) and the now-unused
  `hexToBytes` helper were reverted. `modify.entity.xdata` is back to
  exactly its original behavior (1004 still excluded, matching the
  ORIGINAL pre-#118 code and comment). This is a deliberate, live-probed
  finding, not a fabricated pass -- write support for 1004 needs a properly
  verified manual `acutNewRb` + explicit-ownership construction (and
  confirmation of what `acutRelRb` actually does with `rbinary.buf`) before
  it is safe to ship; that is future work, out of this ticket's scope.

**Verdict:** #118 **FIXED** (read path: `byte_count`-only -> real hex
`value`, verified safe against regression and against a full live database
walk). A genuine end-to-end "AutoCAD-written real 1004 xdata reads back
correctly" proof was not obtained in this pass -- the safe way to construct
one needs write-side work this ticket explicitly did not ask for and that
this investigation showed is non-trivial to get right. Recorded here rather
than silently dropped (Rule 12 / no fake success).

## Regression baseline

`pytest tests/unit`: **1073 passed, 14 skipped** (1087 total) -- 0 failed,
both before and after these changes.
