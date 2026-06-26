# CAD OS v1 Final Main Merge Plan

- Status: BLOCKED_DIRTY_MAIN
- Main updated: no
- Release branch: cados/cad-os-v1.0-final

Safe merge is intentionally deferred because the main checkout is dirty.

Resume:
1. Resolve unrelated dirty main work.
2. Verify git status --short is empty on main.
3. Merge cados/cad-os-v1.0-final with --no-ff after approval.
4. Re-run final tests and native build.
5. Do not push without approval.
