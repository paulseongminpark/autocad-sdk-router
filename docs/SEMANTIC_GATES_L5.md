# Semantic Gates L5

L5 is the semantic layer: instead of asking whether a rebuilt drawing matches a human golden set, it asks whether a deterministic semantic extractor preserves the same meaning before and after roundtrip. That is the O4 metamorphic principle from P10b: apply the same extractor `f_sem` to census IR `A` and rebuilt IR `B'`, then gate on preservation of the extracted relation table. The first concrete gate is N5, dimension-geometry consistency, because dimension entities carry high semantic mass and expose quiet geometry drift that count-based diffs miss.

This N5 gate extracts one row per dimension, recomputes span from the xline geometry along the dimension rotation axis, and compares the extracted tables between `A` and `B'` without using DWG handles as identity. The fixture-backed self-test mutates a real corpus sample three ways so the gate proves it can convict measurement drift, geometry drift, and deletion. That keeps the judge golden-free but not toothless.

Next wiring step: surface this report inside the full roundtrip capstone `gate_statuses` payload so N5 can block regressions alongside the lower-layer structural gates. After N5, the roadmap is the same extractor-preservation pattern at richer semantics: centerline rulepack counts and scores, then wall-adjacency and related topology-aware relation tables.

The capstone now wires this semantic gate directly through `main()`: it extracts dimension relations from both census IR and post-regen IR, writes `dim_semantic_gate.json`, records the result at `summary["regen"]["dim_semantic_gate"]`, and appends its status into the existing `gate_statuses` list. `--no-semantic-gates` disables this check; default is ON.
