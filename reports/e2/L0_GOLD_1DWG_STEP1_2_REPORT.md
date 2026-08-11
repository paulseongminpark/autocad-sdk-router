# E2 L0 Gold 1DWG Step 1–2 Report

> **Historical snapshot (recorded 2026-08-05; refreshed 2026-08-11)**
>
> The wording “current synthesis” below means the state recorded at the snapshot
> commit `9b506051ca0ddbf7f40b324e2f224241e752559c`; it is not the current PR
> status. Counts and historical `PASS`/`PARTIAL_PASS`/`BLOCKED` judgments are
> preserved. The legacy target-oracle `status=PASS` artifacts described here are
> incompatible with the current v1 authoritative contract, so they must not be
> silently treated as current evidence.
>
> Every present-tense statement below belongs to that historical snapshot.
> Current implementation, CI and merge status must be established from the
> current source, receipts and GitHub checks rather than inferred from this file.

## Status and objective

Code-remediation status: **PASS** for the F1–F5 guarded-execution contract.

Overall scientific status: **PARTIAL_PASS / NEEDS_BUILD**. Step 1–2 establishes a native-first, hash-bound L0 gold-layer extraction and a guarded execution path. It does not authorize detector execution or make model-performance claims.

Scope was limited to the staged copy of `CODEX_E2_WALL_WORLD_MODEL_SOURCE_V1.dwg`, native graph observation, exact W1/W2 label-scope extraction, WorldIR transform/conservation checks, and the fail-closed experiment guard.

## Native-first route and gold-layer semantics

Primary truth was `inspect.database.graph` through the ObjectDBX-capable, hostless DBX-in-accoreconsole route. DXF and DWF were not used as primary truth.

The gold layer is label scope only. The exact UTF-8 layer names are:

- `X-평면도(기본형)$0$W1`
- `X-평면도(기본형)$0$W2`

`$0$` is not an externality rule. External scope comes only from explicit native XREF records and block-table-record flags. XCLIP is retained as display metadata but ignored for label-scope inclusion; this extraction is not a native-display visibility measurement.

## Source, staging, and exact counts

The immutable source and staged DWG are each **2,368,524 bytes**, read-only, and have SHA-256:

`14eb65eb292d8a07f38ab5662dcafe9761c6185bc5ff0c8a9a008be15b598961`

The actual guarded source observed `AC1032`. The bound WorldIR probe is:

`D:\runs\e2_program\l0_gold_1dwg\terra_fix\scoped_worldir_probe.json`

Exact extraction facts:

- XREF: observed present as an implemented empty list; **0 records**; scope identity resolved.
- Structural wall INSERT templates, raw/retained/omitted: W1 **54/37/17**; W2 **13/0/13**; total **67/37/30**.
- Omitted structural INSERT terminal dispositions: **30/30**, conserved.
- WorldIR wall expansion: W1 **6,094**, W2 **3,742**; total **9,836**; conservation/preservation passed.
- The gold segment artifact is labels-only and not a detector-feature projection.

## Guard design and F1–F5 closure

The implementation is in [`tools/e2/run_guarded_experiment.py`](../../tools/e2/run_guarded_experiment.py) and source-document qualification is in [`tools/e2/experiment_guard.py`](../../tools/e2/experiment_guard.py).

- F1: the requested source/probe paths are re-resolved before spawn and after execution. Requested path, canonical target, native file identity/stat fingerprint, and SHA-256 must all match. Byte-identical source and probe Windows Junction retargets fail closed.
- F2: runner exceptions and malformed result objects, including `object()` and invalid return codes, produce terminal blocked in-memory results and no terminal authorization.
- F3: a receipt is first persisted as explicitly non-terminal `PREFLIGHT`; receipt writes use a temporary file, flush/fsync, replace, and cleanup. Initial and final write failures fail closed.
- F4: supplied source bytes must satisfy the conservative `AC10dd` signature contract. A non-DWG with a matching probe hash is rejected before execution.
- F5: nonzero command exits are split from evidence validity: exit 7 is `COMMAND_FAILED`, `command_succeeded=false`, `terminal_success=false`, and `terminal_authorized=false`.
- Receipt paths that alias source or probe evidence fail closed before spawn without overwriting the evidence.

## Tests and evidence

The focused tests are in [`tests/unit/test_experiment_guard.py`](../../tests/unit/test_experiment_guard.py); L0 scope tests are in [`tests/unit/test_l0_gold_anchor.py`](../../tests/unit/test_l0_gold_anchor.py).

- Focused guard suite: **55 collected, 55 passed, 0 failed, 0 skipped**. Both real Junction retarget parametrizations (`source`, `probe`) passed.
- Exact qualification collection: **104 collected**.
- Exact qualification suite: **103 passed, 0 failed, 1 expected `CADOS_LIVE` skip**.
- WorldIR self-test: **26/26**.
- `git diff --check`: exit 0.
- Terra F1–F5 evidence: `D:\runs\e2_program\l0_gold_1dwg\terra_fix3\test_receipt.json`, `adversarial_f1_f5_summary.json`, and `adversarial_f1_f5_raw.txt`; all 25 adversarial cases passed and all recorded raw-file hashes recomputed exactly.
- Fresh direct reproductions: `D:\runs\e2_program\l0_gold_1dwg\luna_pass\direct_reproduction.json`; **5/5** passed for source Junction retarget, `object()` runner result, final receipt-write failure, invalid DWG with matching probe hash, and exit 7.
- Actual guard receipt: `D:\runs\e2_program\l0_gold_1dwg\terra_fix3\guard_actual_terminal.json`; READY, executed, exit 0, terminal success, AC1032, and valid pre/post bindings.
- Display/model receipt: `D:\runs\e2_program\l0_gold_1dwg\terra_fix3\guard_display_model_needs_build.json`; `NEEDS_BUILD`, unexecuted, sentinel calls 0.

## What PASS means and scientific limitations

The code-remediation PASS means no practical F1–F5 false-success or ambiguous-terminal defect remained in the current-code tests, Terra adversarial evidence, actual receipt, and fresh direct reproductions. It does not mean a detector ran or that scientific performance is established.

Scientific status remains **PARTIAL_PASS / NEEDS_BUILD** because:

- filesystem binding is detect-and-invalidate, not atomic filesystem immutability;
- native proxy/adapter coverage remains partial: the proxy section is partial and **5,488** full-native templates are outside the current adapter surface;
- the native display-membership oracle and exact model-input membership receipt are absent.

No detector performance, model result, or AUPRC claim is made.

## Next gate and retained junction

Build or supply a hash-bound AutoCAD native-display membership oracle and exact model-input receipt, then rerun the display/model guard. Detector execution and scientific scoring remain unauthorized until that gate is READY.

The retained policy-deferred junction is:

`D:\runs\e2_program\l0_gold_1dwg\terra_fix3\junction_probe_alias`

It is a `Junction` with sole exact target `D:\runs\e2_program\l0_gold_1dwg\terra_fix`; it is not evidence and was not deleted or followed recursively.
