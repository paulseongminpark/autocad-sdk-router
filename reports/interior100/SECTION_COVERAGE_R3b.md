# IR Section Coverage

A: `runs\e2e_1dwg_R3b_full_20260708\census\dwg_graph_ir.json`
B: `runs\e2e_1dwg_R3b_full_20260708\regen\post\dwg_graph_ir.json`

Overall weighted coverage: 67.84%
Sections absent: b.extension_dictionaries

| Section | A | B | Coverage | Notes |
| --- | ---: | ---: | ---: | --- |
| entities | 375 | 375 | 100.00% | |
| block_definitions | 140 | 135 | 96.43% | missing sample: DIMDOT, _ArchTick, X-평면도(기본형)$0$ins-l, X-평면도(기본형)$0$국기계양대, X-평면도(기본형)$0$ng |
| block_definitions.def_entities | 20851 | 14074 | 67.50% | |
| layouts | 3 | 3 | 100.00% | missing names: (none) |
| dictionaries | 1 | 1 | 100.00% | |
| xrecords | 2 | 1 | 50.00% | |
| extension_dictionaries | 1 | 0 | 0.00% | |
| xdata entities | 64 | 0 | 0.00% | |
| symbol_tables.app_ids | 25 | 7 | 28.00% | |
| symbol_tables.block_table_records | 410 | 251 | 61.22% | |
| symbol_tables.dim_styles | 6 | 2 | 33.33% | |
| symbol_tables.layers | 91 | 66 | 72.53% | |
| symbol_tables.linetypes | 18 | 3 | 16.67% | |
| symbol_tables.text_styles | 8 | 2 | 25.00% | |
| symbol_tables.ucs | 0 | 0 | 100.00% | |
| symbol_tables.viewports | 1 | 1 | 100.00% | |
| symbol_tables.views | 0 | 0 | 100.00% | |

Worst sections:
- block_definitions.def_entities: missing 6777 (20851 -> 14074)
- symbol_tables.block_table_records: missing 159 (410 -> 251)
- xdata: missing 64 (64 -> 0)
- symbol_tables.layers: missing 25 (91 -> 66)
- symbol_tables.app_ids: missing 18 (25 -> 7)
