# Symbol Tables P5

## Charter

Pane 5 needs linetype replay to synthesize an AutoCAD `.lin` sidecar the same
way custom hatch replay synthesizes `.pat`. The writer must stay honest about
unsupported complex segments, and it must reuse the proven numeric rule from
`.pat` synthesis: fixed-point output only, with `abs(value) < 1e-9` clamped to
literal `0`.

## `.lin` Extractor Contract

`tools/lin_synthesis.py:synthesize_lin_file()` accepts the extractor rows below:

```python
{
    "name": str,
    "description": str,
    "pattern_length": float,
    "is_scaled_to_fit": bool,
    "dashes": [
        {
            "length": float,
            "text": Any,   # optional, complex segment marker
            "shape": Any,  # optional, complex segment marker
        }
    ],
}
```

V1 semantics:

- Write `*NAME,description` followed by `A,<pattern items>`.
- Positive `length` emits a dash, negative emits a space, and zero emits a dot.
- `pattern_length` and `is_scaled_to_fit` are carried through as extractor
  metadata but do not change the v1 `A,...` serialization.
- Any row containing `text` or `shape` is deferred for now and must be reported
  back to the caller; it is never silently dropped.

Return shape:

```python
{
    "written": [name1, name2],
    "deferred": [{"name": name3, "reason": "..."}],
}
```

## Batch Wiring Plan

Later `patch_engine.py` wiring should mirror `_synthesize_batch_pat_files` at
the batch-build seam, but with one batch `.lin` sidecar that can hold multiple
linetype definitions:

1. Collect extracted linetype rows for the batch.
2. Call `synthesize_lin_file(rows, <batch_dir>/<batch_id>.lin)`.
3. Attach the absolute forward-slash `.lin` path plus linetype name to replay
   jobs that need it.
4. Surface `deferred` rows in batch results so text/shape linetypes stay honest
   until complex segment replay is implemented.
