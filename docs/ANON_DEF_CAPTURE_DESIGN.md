# Anonymous Block Definition Capture Design

## Investigation

Measured defect: `inspect.database.graph` reports anonymous block references (`*U172`, `*U144`, etc.) from nested `INSERT` entities, but emits zero anonymous entries under `block_definitions`. That leaves nested synthesis without a source definition for roughly 320 deferred references in `reports/interior100/anon_probe_R3b.json`.

Native emission site:

- `src/Ariadne.AcadNative/AriadneNativeJob.cpp`
- Function: `blockTableRecordsJson(...)`
- Before this packet, the block-definition projection used:

```cpp
const bool isUserBlock = !isLayout && !isAnon && !isXref;
...
if (isUserBlock) {
    defs << "{\"handle\":\"...\",\"name\":\"...\",\"entity_count\":...,
             \"def_entities\":...}";
}
```

Exact drop condition:

- `pBTR->isLayout()` excludes layout BTRs such as `*Model_Space` / `*Paper_Space`.
- `pBTR->isAnonymous()` excludes anonymous BTRs such as dynamic-block snapshots (`*U###`) and dimension defs (`*D###`).
- `pBTR->isFromExternalReference()` excludes xref-owned BTRs.

Impact of the pre-packet filter:

- `block_table_records[]` still enumerated anonymous BTRs and marked them with `"is_anonymous": true`.
- `block_definitions[]` omitted the same BTRs entirely because of `!isAnonymous()`.
- `coverage.counts.block_definitions` reused that filtered count, so the graph under-reported capturable definitions.

Python post-processing check:

- `tools/ir_builder.py`
- `_normalize_block_definitions(...)` shallow-copies each raw block-definition dict (`bd = dict(bd)`) and only normalizes `def_entities`.
- No `*`-prefix filter, `isAnonymous` filter, or block-name allowlist exists in `ir_builder.py`.
- Result: the loss happens in native extraction, not Python post-processing. Python already passes additive block-definition fields through if native emits them.

Nearby but out of scope for this packet:

- `countBlockDefinitions(...)` and `listBlockDefinitionsDetailed(...)` in `AriadneNativeJob.cpp` also use `!pBTR->isAnonymous()`.
- Those helpers are not the measured `inspect.database.graph` defect path, so this packet leaves them unchanged.

## Tree of Thoughts

### C1. Capture anonymous defs now and rebuild them later as deterministic named clones

Plan:

- Emit anonymous BTRs in `block_definitions[]` with additive `"anonymous": true`.
- At rebuild time, synthesize legal clone names such as `ARIADNE_ANON__U172`.
- Remap nested/top-level `block_reference.block_name` values from `*U172` to the clone name during patch synthesis.

Pros:

- End-to-end rebuildable from a static snapshot.
- Preserves def geometry and nested topology.

Cons:

- Dynamic behavior is not preserved; this is a static clone, not a live dynamic block.
- Real rebuild logic belongs in `ir_to_patch.py`, which this packet must not edit.

Score:

- Correctness: 4/5
- Scope fit for this packet: 2/5
- Immediate unblock value: 4/5
- Total: 10/15

### C2. Rebuild true anonymous BTRs via ObjectARX anonymous-block creation

Pros:

- Closer to native semantics if fully implemented.

Cons:

- Higher API risk.
- Anonymous naming/lifetime is less controllable.
- Not viable without a broader native/write-side change set.

Score:

- Correctness: 3/5
- Scope fit: 1/5
- Immediate unblock value: 2/5
- Total: 6/15

### C3. Extractor-only in this packet: emit anonymous defs + flag, defer rebuild remap

Pros:

- Smallest honest change.
- Fixes the measured blind spot directly.
- Makes anonymous defs capturable in IR immediately.

Cons:

- Rebuild remains deferred until a follow-up `ir_to_patch.py` packet lands.

Score:

- Correctness: 3/5
- Scope fit: 5/5
- Immediate unblock value: 5/5
- Total: 13/15

## Decision

Choose `C3` for this packet.

Reason:

- The measured failure is extraction loss, not rebuild logic.
- `ir_builder.py` already preserves additive fields, so emitting anonymous defs natively unblocks measurement with the smallest truthful diff.
- Full clone/remap rebuild belongs in `ir_to_patch.py`; forcing a partial write-side solution into this packet would increase risk without a runnable CAD gate here.

## Implemented Packet Scope

Native extractor change:

- `block_definitions[]` now emits every non-layout, non-xref BTR.
- Named definitions keep their existing JSON shape unchanged.
- Anonymous definitions add only `"anonymous": true`.
- Layout BTRs and xref BTRs remain excluded.
- `coverage.counts.block_definitions` now tracks emitted block definitions, including anonymous ones.

Python scope:

- No `ir_builder.py` filtering fix was required because the existing normalization already preserves additive block-definition fields.
- A Python test guards that passthrough explicitly.

## Follow-up Patch Plan for Rebuild

Owner:

- `tools/ir_to_patch.py`

Minimal C1 follow-up:

1. Build a deterministic remap table from anonymous source names to legal clone names.
2. Create clone block definitions under the remapped names before any referencing `INSERT`.
3. Rewrite `geometry.block_name` for both modelspace and nested block-reference emissions when the referenced source block definition is anonymous.
4. Record provenance on the deferred/diagnostic side that the rebuild is a static clone of a dynamic/anonymous definition, not a live dynamic block.

Suggested helper contract:

- Input: source block name such as `*U172`
- Output: legal deterministic clone name such as `ARIADNE_ANON__U172`
- Inverse metadata should be carried in diagnostics or op annotations, not inferred from geometry alone.

Why it belongs there:

- `ir_to_patch.py` owns block-definition synthesis order and block-reference emission.
- `ir_builder.py` should stay an extraction/normalization layer, not a write-time remap owner.

## Backtrack Trigger

Abort the extractor-only direction and switch to the follow-up rebuild packet if either condition appears after measurement reruns:

1. Anonymous definitions are present in IR, but deferred nested `INSERT` counts remain dominated by anonymous names because the missing piece is now purely write-side remap.
2. Downstream consumers reject additive `block_definitions[].anonymous` fields or assume every block name is directly legal/rebuildable without remapping.
