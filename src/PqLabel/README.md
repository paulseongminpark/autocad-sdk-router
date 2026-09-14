# PQ Label for AutoCAD

`PqLabel.dll` is an AutoCAD 2027 managed .NET plug-in for assigning and querying
`CLASS_ID` labels stored as Rhino-compatible AutoCAD XData.

The application bundle uses command-invocation lazy loading, so the DLL is not
loaded while AutoCAD itself is starting.

## Commands

| Command | Action |
| --- | --- |
| `PQPALETTE` | Open the dockable class-management window. |
| `PQSETCLASS` | Assign a class to selected entities. For blocks, writes to leaf entities in the shared block definition. |
| `PQSETCLASSKIND` | Set `CLASS_KIND=THING|STUFF` on every authored record of one class. |
| `PQUNSETCLASS` | Remove a class from selected entities/block contents. |
| `PQSETINSTANCE` | Apply one entered `INSTANCE_ID` to all selected objects/references. |
| `PQNEWINSTANCE` | Generate one UUID and apply it to all selected objects/references. |
| `PQUNSETINSTANCE` | Remove `INSTANCE_ID` from selected objects/references. |
| `PQSELECTCLASS` | Replace the current selection with matching objects. |
| `PQDESELECTCLASS` | Remove matching objects from the current selection. |
| `PQSHOWCLASS` | Isolate matching objects. |
| `PQHIDECLASS` | Hide matching objects, including objects inside mixed nested blocks. |
| `PQSHOWALL` | End object isolation. |
| `PQSYNCCLASS` | Rebuild derived `CLASS_ID` caches on nested/parent block references. |
| `PQINFO` | Display stored and effective class information. |
| `PQINFONESTED` | Inspect the exact nested entity plus its container path. |
| `PQAUDITCLASS` | Count direct class XData records by entity type. |
| `PQVALIDATE` | Validate raw XData structure and semantic/instance integrity. |
| `PQMIGRATERHINO` | Convert legacy `COMPANY_PQ` records to Rhino Attribute User Text XData. |
| `PQHELP` | List commands. |

## Label model

- Canonical records use the `Rhino` registered application name and one
  `{ key, value }` XData group per field, matching Rhino's DWG Attribute User
  Text exchange format. Legacy `COMPANY_PQ` records remain readable.
- Any edited legacy record is migrated automatically. `PQMIGRATERHINO` converts
  every existing legacy record in the current DWG while preserving other Rhino
  Attribute User Text keys.

- Leaf drawing entities store `SCHEMA=1.1`, `CLASS_ID=<value>`, and
  `CLASS_KIND=THING|STUFF`.
- Assigning a class scans the selected leaf scope first. If any existing class
  labels are found, the command reports how many differ and requires an explicit
  `Yes` before overwriting them. Instance IDs are preserved.
- A block reference normally stores no class. Its effective class is inferred only
  when every descendant leaf is labeled and all labels agree.
- For top-level interoperability, that inferred value is also materialized on each
  homogeneous parent BlockReference as `CLASS_ID` plus `CLASS_SOURCE=DERIVED`.
  Mixed or incomplete parents have this cache removed.
- Setting a class on a block changes its shared block definition and therefore
  affects every reference to that definition.
- Instance operations never recurse into a block definition. An ID on a
  BlockReference belongs only to that placement. Applying one ID to several
  selected primitives groups them as one explicit instance.
- Xref definitions are read-only and are skipped by set/unset operations.
- Mixed or incompletely labeled blocks are not selected/hidden as a whole.
- `PQSETCLASS` and `PQUNSETCLASS` refresh parent caches automatically. Run
  `PQSYNCCLASS` once for drawings labeled by an older plug-in version.

## Palette

Run `PQPALETTE` to open the dockable window. It lists classes and their kind in the current
Model/Layout space and shows object, instance, block, and entity counts. Inventory
walking is occurrence-path aware: a mixed outer block is expanded recursively,
while each homogeneous nested block is collapsed to one semantic instance. Shared
definitions are counted once for every actual BlockReference placement. A block
reference counts as an implicit instance; standalone entities count as instances
only when they share an explicit `INSTANCE_ID`. Select a row or type a new class
and use the buttons to run the same labeling, selection, and visibility operations
as the commands. The inventory refreshes automatically after PQ class/instance
mutation and synchronization commands complete; a manual Refresh remains available.
The palette refreshes automatically when the active drawing changes.

Choose `THING` or `STUFF` before assigning a class. `Save kind` updates all
existing authored records of the entered class, which upgrades older drawings
without having to select every nested entity. `Validate` runs `PQVALIDATE` and
selects top-level objects containing an issue.

`STUFF` must never carry `INSTANCE_ID`. Instance assignment is rejected when any
selected semantic object is stuff. Assigning or changing a class to stuff is also
rejected until instance records in the affected scope are removed. Existing
invalid data is reported as an error by `PQVALIDATE`; `PQUNSETINSTANCE` remains
available to repair it.

Validation has two independent passes. The physical pass scans every entity in
host-owned block table records once and checks brace/pair structure, duplicate or
conflicting keys, Rhino/legacy conflicts, schema, blank/invalid fields, orphan
fields, invalid derived records, and stuff carrying an instance. The occurrence
pass treats each homogeneous BlockReference occurrence as an implicit
thing instance. A thing leaf reached through a mixed/incomplete path must have an
explicit `INSTANCE_ID`. Explicit IDs are compared within their actual occurrence
scope; one ID associated with multiple classes is invalid. Missing or inconsistent
`CLASS_KIND` values are reported because rule 1 cannot be evaluated without them.
Errors and warnings are reported separately. Current-space issue containers are
selected; definition-only issues are identified by `BTR:<name>/<handle>` paths.

`Generate UUID when setting ID` is checked by default. In that mode, the `Set ID`
button creates a new UUID, displays it in the `INSTANCE_ID` field, and assigns it
to the selection. When unchecked, `Set ID` uses the manually entered value and
shows a warning without creating an instance if the field is empty.

## Nested visibility

`PQSHOWCLASS` and `PQHIDECLASS` walk mixed/incomplete block definitions and apply
a temporary graphics overrule to matching nested block references and leaf
entities. Homogeneous blocks are handled as one semantic unit. The filter does
not modify entity visibility, layers, or saved DWG data; `PQSHOWALL` removes it.
Because block definitions are shared, a hidden definition entity is hidden in
every placement of that definition.

During isolation, each nested block subtree is also checked for at least one
matching descendant. If an unlabeled or mixed child block contains no target at
all, its BlockReference is suppressed as a whole. This prevents AutoCAD's cached
block graphics from displaying an unrelated subtree while bypassing leaf-level
overrules.

## Load

1. Put the bundle folder under `%APPDATA%\Autodesk\ApplicationPlugins`, then restart AutoCAD; or
2. Run `NETLOAD` and select `Contents\Windows\PqLabel.dll`.

AutoCAD may require the bundle folder to be included in `TRUSTEDPATHS` when
`SECURELOAD` is enabled.

## Build

AutoCAD 2027 uses .NET 10. Run:

```powershell
dotnet build -c Release
```

The project references the managed API assemblies from
`C:\Program Files\Autodesk\AutoCAD 2027`. Override the `AutoCADDir` MSBuild
property if AutoCAD is installed elsewhere.
