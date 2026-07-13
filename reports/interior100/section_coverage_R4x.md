# IR Section Coverage

A: `runs\e2e_1dwg_R4x_ccw_20260711\census\dwg_graph_ir.json`
B: `runs\e2e_1dwg_R4x_ccw_20260711\regen\post\dwg_graph_ir.json`

Overall weighted coverage: 99.63%
Sections absent: b.extension_dictionaries

| Section | A | B | Coverage | Notes |
| --- | ---: | ---: | ---: | --- |
| entities | 375 | 375 | 100.00% | |
| block_definitions | 407 | 407 | 100.00% | missing sample: *U45, *U47, *U48, *U49, *U50, *U51, *U52, *U53, *U54, *U55, *U56, *U57, *U58, *U59, *U60, *U61, *U62, *U63, *U64, *U67 |
| block_definitions.def_entities | 28183 | 28260 | 100.00% | |
| layouts | 3 | 3 | 100.00% | missing names: (none) |
| dictionaries | 1 | 1 | 100.00% | |
| xrecords | 2 | 1 | 50.00% | |
| extension_dictionaries | 1 | 0 | 0.00% | |
| xdata entities | 64 | 0 | 0.00% | |
| symbol_tables.app_ids | 25 | 7 | 28.00% | |
| symbol_tables.block_table_records | 410 | 410 | 100.00% | |
| symbol_tables.dim_styles | 6 | 2 | 33.33% | |
| symbol_tables.layers | 91 | 91 | 100.00% | |
| symbol_tables.linetypes | 18 | 3 | 16.67% | |
| symbol_tables.text_styles | 8 | 2 | 25.00% | |
| symbol_tables.ucs | 0 | 0 | 100.00% | |
| symbol_tables.viewports | 1 | 1 | 100.00% | |
| symbol_tables.views | 0 | 0 | 100.00% | |

Worst sections:
- xdata: missing 64 (64 -> 0)
- symbol_tables.app_ids: missing 18 (25 -> 7)
- symbol_tables.linetypes: missing 15 (18 -> 3)
- symbol_tables.text_styles: missing 6 (8 -> 2)
- symbol_tables.dim_styles: missing 4 (6 -> 2)
