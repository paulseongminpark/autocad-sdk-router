# Native Module SHA-256 Manifest — ObjectARX 2027

> Integrity fingerprint of the built native modules. Generated 2026-07-14, session 0aa41075.
> No C++ source (`src/Ariadne.AcadNative*`) changed this session (git diff --stat src/ = empty), so these
> deployed binaries match the current source. Toolchain: VS2026 MSBuild + C:\ObjectARX 2027 SDK
> (tools/build_native_acad.ps1). A byte-exact reproducibility rebuild is not expected (MSBuild embeds
> build timestamps); an isolated clean rebuild confirms the toolchain (see build note below).

| module | role | host | SHA-256 |
|---|---|---|---|
| `prebuilt/2027/Ariadne.AcadNative.crx` | headless native op surface | accoreconsole.exe | `ab5a3277899d1f223b001435ff75ac5eeec67360966d932871c1eec28021f626` |
| `prebuilt/2027/Ariadne.AcadNativeDbx.dbx` | ObjectDBX Object Enabler | acdbmgd / ObjectDBX host | `299d5d970f84b0e071d86fba0b724b0c53f054683217f6916a50bd0808fab0f5` |
| `prebuilt/2027/Ariadne.AcadNative.arx` | full-AutoCAD op surface | acad.exe | `66e81d6b45465fc6e73e3fe2210224c6c6d66152e10d349bfce65aaace1cee28` |

## Verification

```
cd D:/dev/99_tools/autocad-sdk-router
sha256sum prebuilt/2027/Ariadne.AcadNative.crx prebuilt/2027/Ariadne.AcadNativeDbx.dbx prebuilt/2027/Ariadne.AcadNative.arx
```

## Fresh-rebuild note

Isolated clean rebuild 2026-07-14 (`tools/build_native_acad.ps1 -OutputRoot <temp>`): **PASS (EXIT=0)** — all
three modules built and existence+byte-size-validated by the build script (`.arx` = 1,083,392 B). This proves
the current source compiles cleanly with the pinned VS2026 + ObjectARX 2027 toolchain; the isolated `-OutputRoot`
did not overwrite the deployed `prebuilt/2027/` binaries stamped above.
