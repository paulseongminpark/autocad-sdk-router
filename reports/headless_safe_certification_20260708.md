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

- The NO_STAGED_EFFECT results are fixture-bound (`native_sample.dwg` may lack suitable source geometry for the surface ops); those templates are honestly "not certifiable from THIS evidence," not proven unsafe. Re-testing on a fixture with appropriate source surfaces could reclassify some.
- Evidence artifacts: per-template envelopes under `reports/headless_cert_20260708/`, per-template IR diffs under `reports/headless_cert_20260708/_ir/<tag>/`.
