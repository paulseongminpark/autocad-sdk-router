# CADOS V1 Final Main Merge Plan

- Status: BLOCKED_DIRTY_MAIN
- Main: main @ bc0832ab86bae410a89c8913294b5d7531e9f47b
- Release branch: cados/cad-os-v1.0-release-freeze @ 2d5902461d5f3479feb1d59e405d9e11eb40d53f
- Push allowed: no
- Dirty tracked count: 238
- Untracked count: 25

Blocked reason: Main checkout has tracked/untracked dirty work; packet forbids reset/clean and forbids touching dirty main.

## Safe Resume Commands
Run only after main is clean or in a separate merge worktree:

```powershell
git -C D:\dev\99_tools\autocad-sdk-router status --short
git -C D:\dev\99_tools\autocad-sdk-router merge --no-ff cados/cad-os-v1.0-release-freeze
python -m pytest tests -q -rs
.\tools\build_native_acad.ps1
```
