# headless_safe certification run — 2026-07-08

This run executes decision #4 of `reports/cad_write_policy_decisions_20260708.md` — the `headless_safe` certification gate. 13 templates that were conservatively flagged `headless_safe=false` were run through `tools/certify_headless_safe.py` on a staged copy of the immutable fixture; a template earns `headless_safe=true` only with real evidence. Tool commit: `553d0dc`.

## Methodology

A template is **CERTIFIED** only if all 5 gate conditions hold:

1. **Headless completion** — exit 0, status ok, no crash/timeout.
2. **Original DWG byte-immutable** — sha unchanged before/after.
3. **Real LOGICAL effect on the staged copy** — measured by the router's handle-based IR diff (`cad.inspect include_rich` original vs staged_result → `diff_before_after`; `effect_took` = added+removed+modified > 0). This REPLACES the earlier whole-file-sha check, which was non-discriminating: `run_template` unconditionally `_QSAVE`s and QSAVE rewrites volatile header bytes (timestamp + next-handle seed) on every save, so a raw-sha delta was ALWAYS true even for a no-op (finding 6). The IR diff is QSAVE-immune because existing entity handles are preserved across a save.
4. **No attended/interactive prompt marker** in the accoreconsole stdout/stderr tail.
5. **Under the timeout budget** (120s).

Fixture: `tests/fixtures/native_sample.dwg`, 21747 entities, sha256 prefix `eac5d4b1…`, confirmed byte-identical before and after the whole run.

## Results

| Template | Verdict | Reason | effect (a/r/m) | Note |
|---|---|---|---|---|
| define.arrayrect | CERTIFIED | CERTIFIED | 1/1/0 | flipped headless_safe=true; associative array object created (+1) and source consumed (−1) |
| define.arrayedit | NOT_CERTIFIED | CRASH_OR_NONZERO_EXIT | 0/0/0 | nonzero exit headless |
| define.arraypolar | NOT_CERTIFIED | CRASH_OR_NONZERO_EXIT | 0/0/0 | nonzero exit headless |
| define.surfblend | NOT_CERTIFIED | CRASH_OR_NONZERO_EXIT | 0/0/0 | nonzero exit headless |
| define.surftrim | NOT_CERTIFIED | CRASH_OR_NONZERO_EXIT | 0/0/0 | nonzero exit headless |
| define.assocaudit | NOT_CERTIFIED | NO_STAGED_EFFECT | 0/0/0 | ran clean, no logical change on this fixture |
| define.surfextrude | NOT_CERTIFIED | NO_STAGED_EFFECT | 0/0/0 | ran clean, no logical change on this fixture |
| define.surffillet | NOT_CERTIFIED | NO_STAGED_EFFECT | 0/0/0 | ran clean, no logical change on this fixture |
| define.surfloft | NOT_CERTIFIED | NO_STAGED_EFFECT | 0/0/0 | ran clean, no logical change on this fixture |
| define.surfoffset | NOT_CERTIFIED | NO_STAGED_EFFECT | 0/0/0 | ran clean, no logical change on this fixture |
| define.surfpatch | NOT_CERTIFIED | ATTENDED_MARKERS_PRESENT | 0/0/0 | interactive default-bracket prompt detected |
| maintenance.drawing.overkill | NOT_CERTIFIED | TIMEOUT_ATTENDED_SUSPECT | 0/0/0 | did not exit within 120s (attended-suspect) |
| maintenance.drawing.recover | NOT_CERTIFIED | SAMPLE_ARGS_REQUIRED | — | needs a runtime staging path arg; cannot derive offline |

**Summary:** 1 CERTIFIED, 12 NOT_CERTIFIED (4 crash, 5 no-effect, 1 attended-marker, 1 timeout, 1 sample-args). Registry change scope = exactly one fragment: `config/command_templates.d/define.arrayrect.json`.

## Safety value

Under the pre-fix whole-file-sha logic, the 5 NO_STAGED_EFFECT templates plus surfpatch (whose attended marker the older narrow patterns missed) would have FALSELY certified — QSAVE's byte churn read as "effect took". The logical-IR-diff gate + broadened markers reduce that to the single template with a genuine, evidence-backed effect. No original byte was mutated at any point.

## Honesty / limitations

This run has **no false positives** (nothing was certified without a real logical
effect), but `1 / 13 CERTIFIED` is an **undercount**, not proof that the other 12 are
headless-unsafe. An adversarial false-negative audit of the 12 rejections (decoded
UTF-16LE accoreconsole stdout, cross-checked against `config/operations.v2.json`
`host_eligibility`) classifies them as:

**Fixable false-negatives (4) — harness/fixture/template bugs, not headless-unsafety:**
- `maintenance.drawing.overkill` — the 120s timeout is **not** an attended prompt; the
  template sends option letter `N` but this Korean-locale build uses `O` for 공차
  (tolerance), so the invalid option hangs. Single-char fix (`N`→`O`) very likely
  certifies with a real dedup effect.
- `define.assocaudit` — ran **perfectly** (audited 68800 objects, "0 errors found, 0
  fixed", clean `_QSAVE`+`QUIT`). Zero diff is *correct* for a healthy drawing with
  `fix_answer=N`; the gate's effect_took bar cannot distinguish "correct no-op" from
  "silent no-op" for diagnostic-class ops. Needs a fixture with a deliberate repairable
  defect + `fix_answer=Y`, or an audit-class methodology carve-out.
- `define.arraypolar` — real `command_sequence` prompt-mapping bug (center x/y/z sent as
  3 lines into a 1-line prompt; mismatched option letters). Structurally analogous to the
  one template that certified (`arrayrect`); a corrected sequence would plausibly certify.
- `define.arrayedit` — fixture-sequencing gap: `L` selected a non-array entity because the
  staged copy has no pre-existing associative array. Needs to run chained after `arrayrect`
  (or on a fixture that already has an array).

**Registry-corroborated honest exclusions (7):** all `define.assocsurface.*` /
`define.surf*` ops are independently marked `status: blocked`,
`host_eligibility: [arx_adapter, full_autocad]` (coreconsole NOT listed) in
`operations.v2.json` from an earlier re-audit. Two (`surfextrude`, `surfloft`) aren't
even recognized command names in accoreconsole. Fixing their template/fixture gaps
likely won't flip them via the headless lane — they belong on the attended/arx pump.

**Unfinished wiring (1):** `maintenance.drawing.recover` needs the staged-copy path
wired into `render_script()` args (a known engine gap, documented in the template notes)
before it can be attempted at all.

**Gate-scope caveat:** `headless_safe` is a **template-level** flag, and
`derive_sample_args` exercises a single boundary value per slot (enum→first value, etc.).
Certifying one argument branch (e.g. an enum's first option) authorizes headless use of
the untested branches too. Argument-conditional certification is out of scope here.

**Evidence artifacts:** per-template envelopes under `reports/headless_cert_20260708/`
(committed); the multi-GB native IR artifacts (`_ir/`, ~169 MB stdout each) and batch
logs are gitignored — the distilled envelope (verdict + effect diff summary) is the
durable record.

## Follow-ups (next certification wave)

1. `overkill`: fix the tolerance-option literal `N`→`O`, re-run.
2. `arraypolar`: comma-join the center point into one literal + drop the mismatched
   `I`/`A` literals, re-run.
3. `arrayedit`: re-run chained onto an array-bearing staged drawing.
4. `assocaudit`: decide the diagnostic-op methodology (defect fixture + `fix_answer=Y`,
   or accept clean-zero-diff as PASS for audit-class ops).
5. `recover`: close the staged-path `render_script` wiring gap.
6. Surface family (7): route through the `arx_adapter`/`full_autocad` attended lane, not
   the headless gate.
