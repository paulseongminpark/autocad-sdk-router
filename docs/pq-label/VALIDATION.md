# PQ Label integration validation

Local runtime observation on 2026-09-11, Windows / AutoCAD 2027 Core Console.
This is historical test evidence, not a claim that every future host is ready.
The router DLL and source hashes are recorded in `prebuilt/2027/pq-label/router/manifest.json`.

The explicit `tests/integration/pq_label_runtime.py` smoke generates its own drawing
through the existing router, starting from a copy of the blank fixture. It uses
existing native IR extraction and SQL entity discovery, then the same cadctl
runner exposed by MCP. Local receipts were recorded under
`runs/pq-label-runtime-958f5cfecbab4723b158a013c7810eab/` (ignored runtime artifacts).

Observed outcomes:

- All 11 PQ operations completed successfully on their valid scenarios.
- The A-WALL line was found by existing SQL, labeled, saved, reopened and read back.
- STUFF instance assignment and unapproved overwrites were rejected.
- A nested shared definition changed both outer placements; an unapproved shared-definition edit was rejected.
- Instance creation, explicit assignment, removal, class-kind change, class removal and cache synchronization were exercised.
- Legacy COMPANY_PQ was migrated. Independent final native extraction confirmed the unrelated Rhino CUSTOM=preserve-me value survived and no entity retained COMPANY_PQ data.
- Final PQ validation reported zero errors and zero warnings.
- Successful cadctl receipts verified operation identity, provenance and original immutability.

Compilation used the checked-in Roslyn build script. Source/DLL manifest, argument
refusal, registry/DAG, existing execution-provenance contracts and MCP stdio are
covered separately by automated tests. Runtime testing is explicit and is not
run by ordinary CI without AutoCAD.

Final focused regression run: 230 passed, 1 skipped, 44 subtests passed.
This included both the existing official MCP stdio suite and PQ operation
discovery/invalid-argument refusal over an actual stdio session.

Not covered by this fixture: every AutoCAD entity type, xref fixture combinations,
every layout occurrence, or an attended persistent GUI session. The original
1.9.1 GUI distribution is preserved; live selection/isolation is not exposed by
the one-shot MCP job lane.
