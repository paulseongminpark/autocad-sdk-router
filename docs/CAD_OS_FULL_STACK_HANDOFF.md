# CAD OS Full Stack Handoff

CAD OS Layer v1.0.0 is frozen from cados/cad-os-v1.0-final.

Use:
- python tools/cadctl_cli.py status
- python tools/cadctl_cli.py registry coverage
- python tools/cadctl_cli.py registry list
- python tools/cadctl_cli.py registry explain <operation>
- python tools/cadctl_cli.py inspect --dwg <read-only-or-staged.dwg> --out <run_dir> --include-rich
- python tools/cadctl_cli.py query --ir <run_dir>\dwg_graph_ir.json --sql "SELECT COUNT(*) FROM entities"
- python tools/cadctl_cli.py patch dry-run --patch <cad_patch.v1.json>
- python tools/cadctl_cli.py patch apply-staged --patch <cad_patch.v1.json> --dwg <input.dwg> --out <run_dir>

Do not use raw AutoCAD command strings as an agent API. Use typed registry operations and staged patch policy.

Final report: reports/release/CADOS_V1_FINAL.json
Handoff zip: handoff/zip/CADOS_M09_V1_RELEASE_FREEZE_AND_DAEDALUS_HANDOFF.zip
Daedalus next packet: D04_IMPORT_CAD_OS_CAPABILITIES
