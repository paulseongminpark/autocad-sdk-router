# Population Forensics

## Transition Matrix

| transition | defs |
| --- | --- |
| clean_both | 88 |
| dirty_both | 1 |
| healed | 3 |
| regressed | 3 |
| a_only | 199 |
| b_only | 0 |
| absent_both | 113 |

## Healed And Regressed

| transition | census_name | R4n | R4o |
| --- | --- | --- | --- |
| healed | X-평면도(기본형)$0$A$C41D360DF | a_total=107, diff0=104, modified=3, removed=0, added=0 | a_total=107, diff0=107, modified=0, removed=0, added=0 |
| healed | X-평면도(기본형)$0$IW990 | a_total=451, diff0=448, modified=3, removed=0, added=0 | a_total=464, diff0=464, modified=0, removed=0, added=0 |
| healed | X-평면도(기본형)$0$hd1050 | a_total=244, diff0=239, modified=5, removed=0, added=0 | a_total=333, diff0=333, modified=0, removed=0, added=0 |
| regressed | X-평면도(기본형)$0$ev13k | a_total=47, diff0=47, modified=0, removed=0, added=0 | a_total=115, diff0=114, modified=0, removed=1, added=0 |
| regressed | X-평면도(기본형)$0$ev16x2k | a_total=94, diff0=94, modified=0, removed=0, added=0 | a_total=230, diff0=228, modified=0, removed=2, added=0 |
| regressed | X-평면도(기본형)$0$우수관_100A | a_total=6, diff0=6, modified=0, removed=0, added=0 | a_total=16, diff0=14, modified=0, removed=2, added=0 |

## Key Diagnosis

| measure | value |
| --- | --- |
| R4n names matching selected census | {'count': 294, 'total': 294} |
| R4o names matching selected census | {'count': 91, 'total': 245} |
| R4n key strategy | name |
| R4o key strategy | mixed_name_and_unique_a_total |
| R4n unique-count fallback rows | 0 |
| R4o unique-count fallback rows | 4 |
| R4n unmatchable rows | 0 |
| R4o unmatchable rows | 150 |
| R4n name/population mismatches | 0 |
| R4o name/population mismatches | 9 |
| optional census consistency | ordered_name_handle_identical=False, primary_defs=407, other_defs=245, first_mismatch={'index': 0, 'primary': ['DIMDOT', '2D9'], 'other': ['X-평면도(기본형)$0$국기계양대', '2D9']} |
| R4n names matching optional census | {'count': 91, 'total': 294} |
| R4o names matching optional census | {'count': 245, 'total': 245} |
| R4n b-side names matching post IR | {'count': 290, 'total': 294} |
| R4o b-side names matching post IR | {'count': 245, 'total': 245} |

R4n: 294/294 per_def names match the selected census. R4o: 91/245 per_def names match the selected census. Rows whose names did not match the selected census were assigned only when a_total matched exactly one census definition entity count; ambiguous and unmatched rows are listed without forced mapping. The optional second census does not have identical block-definition name/handle pairs.

## Unmatchable Rows

| side | index | name | a_total | reason | candidate_count |
| --- | --- | --- | --- | --- | --- |
| R4o | 0 | U100 (X-평면도(기본형)$0$ins-l) | 296 | no_census_entity_count | 0 |
| R4o | 1 | U101 (X-평면도(기본형)$0$ins-l) | 60 | ambiguous_entity_count | 2 |
| R4o | 2 | U102 (X-평면도(기본형)$0$ins-l) | 52 | no_census_entity_count | 0 |
| R4o | 3 | U103 (X-평면도(기본형)$0$ins-l) | 152 | no_census_entity_count | 0 |
| R4o | 4 | U104 (X-평면도(기본형)$0$ins-l) | 88 | no_census_entity_count | 0 |
| R4o | 5 | U105 (X-평면도(기본형)$0$ins-l) | 48 | no_census_entity_count | 0 |
| R4o | 6 | U106 (X-평면도(기본형)$0$ins-l) | 164 | no_census_entity_count | 0 |
| R4o | 7 | U107 (X-평면도(기본형)$0$ins-l) | 52 | no_census_entity_count | 0 |
| R4o | 8 | U108 (X-평면도(기본형)$0$ins-l) | 596 | no_census_entity_count | 0 |
| R4o | 9 | U109 (X-평면도(기본형)$0$ins-l) | 116 | no_census_entity_count | 0 |
| R4o | 10 | U110 (X-평면도(기본형)$0$ins-l) | 312 | no_census_entity_count | 0 |
| R4o | 11 | U111 (X-평면도(기본형)$0$ins-l) | 64 | no_census_entity_count | 0 |
| R4o | 12 | U112 (X-평면도(기본형)$0$ins-l) | 160 | no_census_entity_count | 0 |
| R4o | 14 | U114 (X-평면도(기본형)$0$ins-l) | 204 | no_census_entity_count | 0 |
| R4o | 15 | U115 (X-평면도(기본형)$0$ins-l) | 40 | target_already_mapped | 1 |
| R4o | 16 | U116 (X-평면도(기본형)$0$ins-l) | 216 | no_census_entity_count | 0 |
| R4o | 17 | U117 (X-평면도(기본형)$0$ins-l) | 276 | no_census_entity_count | 0 |
| R4o | 18 | U118 (X-평면도(기본형)$0$ins-l) | 120 | no_census_entity_count | 0 |
| R4o | 19 | U119 (X-평면도(기본형)$0$ins-l) | 204 | no_census_entity_count | 0 |
| R4o | 20 | U120 (X-평면도(기본형)$0$ins-l) | 24 | ambiguous_entity_count | 8 |
| R4o | 21 | U121 (X-평면도(기본형)$0$ins-l) | 24 | ambiguous_entity_count | 8 |
| R4o | 22 | U122 (X-평면도(기본형)$0$ins-l) | 68 | ambiguous_entity_count | 2 |
| R4o | 23 | U123 (X-평면도(기본형)$0$ins-l) | 24 | ambiguous_entity_count | 8 |
| R4o | 24 | U124 (X-평면도(기본형)$0$ins-l) | 24 | ambiguous_entity_count | 8 |
| R4o | 25 | U125 (X-평면도(기본형)$0$ng) | 20 | ambiguous_entity_count | 2 |
| R4o | 26 | U126 (X-평면도(기본형)$0$ins-l) | 56 | no_census_entity_count | 0 |
| R4o | 27 | U127 (X-평면도(기본형)$0$ins-l) | 28 | ambiguous_entity_count | 4 |
| R4o | 28 | U128 (X-평면도(기본형)$0$ins-l) | 80 | no_census_entity_count | 0 |
| R4o | 29 | U129 (X-평면도(기본형)$0$ins-l) | 128 | no_census_entity_count | 0 |
| R4o | 30 | U130 (X-평면도(기본형)$0$ins-l) | 36 | ambiguous_entity_count | 2 |
| R4o | 31 | U131 (X-평면도(기본형)$0$ins-l) | 40 | target_already_mapped | 1 |
| R4o | 32 | U132 (X-평면도(기본형)$0$ng) | 20 | ambiguous_entity_count | 2 |
| R4o | 33 | U133 (X-평면도(기본형)$0$ng) | 20 | ambiguous_entity_count | 2 |
| R4o | 34 | U134 (X-평면도(기본형)$0$ins-l) | 60 | ambiguous_entity_count | 2 |
| R4o | 35 | U135 (X-평면도(기본형)$0$ins-l) | 380 | no_census_entity_count | 0 |
| R4o | 36 | U137 (X-평면도(기본형)$0$ins-l) | 56 | no_census_entity_count | 0 |
| R4o | 37 | U138 (X-평면도(기본형)$0$ins-l) | 64 | no_census_entity_count | 0 |
| R4o | 38 | U139 (X-평면도(기본형)$0$ins-l) | 636 | no_census_entity_count | 0 |
| R4o | 39 | U140 (X-평면도(기본형)$0$ins-l) | 48 | no_census_entity_count | 0 |
| R4o | 41 | U142 (X-평면도(기본형)$0$ins-l) | 308 | target_already_mapped | 1 |
| R4o | 42 | U143 (X-평면도(기본형)$0$ins-l) | 100 | target_already_mapped | 1 |
| R4o | 43 | U144 (X-평면도(기본형)$0$ins-l) | 96 | no_census_entity_count | 0 |
| R4o | 44 | U145 (X-평면도(기본형)$0$ins-l) | 84 | no_census_entity_count | 0 |
| R4o | 45 | U148 (X-평면도(기본형)$0$ins-l) | 12 | ambiguous_entity_count | 5 |
| R4o | 46 | U149 (X-평면도(기본형)$0$ins-l) | 368 | no_census_entity_count | 0 |
| R4o | 47 | U150 (X-평면도(기본형)$0$ins-l) | 32 | ambiguous_entity_count | 6 |
| R4o | 48 | U151 (X-평면도(기본형)$0$ins-l) | 68 | ambiguous_entity_count | 2 |
| R4o | 49 | U152 (X-평면도(기본형)$0$ins-l) | 72 | no_census_entity_count | 0 |
| R4o | 50 | U153 (X-평면도(기본형)$0$ins-l) | 348 | no_census_entity_count | 0 |
| R4o | 51 | U154 (X-평면도(기본형)$0$ins-l) | 360 | no_census_entity_count | 0 |
| R4o | 52 | U155 (X-평면도(기본형)$0$ins-l) | 324 | no_census_entity_count | 0 |
| R4o | 53 | U156 (X-평면도(기본형)$0$ins-l) | 300 | no_census_entity_count | 0 |
| R4o | 54 | U157 (X-평면도(기본형)$0$ins-l) | 148 | no_census_entity_count | 0 |
| R4o | 55 | U158 (X-평면도(기본형)$0$ins-l) | 144 | ambiguous_entity_count | 2 |
| R4o | 56 | U159 (X-평면도(기본형)$0$ins-l) | 52 | no_census_entity_count | 0 |
| R4o | 57 | U160 (X-평면도(기본형)$0$ins-l) | 120 | no_census_entity_count | 0 |
| R4o | 58 | U161 (X-평면도(기본형)$0$ins-l) | 56 | no_census_entity_count | 0 |
| R4o | 59 | U162 (X-평면도(기본형)$0$ins-l) | 424 | no_census_entity_count | 0 |
| R4o | 60 | U163 (X-평면도(기본형)$0$ng) | 20 | ambiguous_entity_count | 2 |
| R4o | 61 | U164 (X-평면도(기본형)$0$ins-l) | 116 | no_census_entity_count | 0 |
| R4o | 62 | U165 (X-평면도(기본형)$0$ng) | 20 | ambiguous_entity_count | 2 |
| R4o | 63 | U166 (X-평면도(기본형)$0$ins-l) | 72 | no_census_entity_count | 0 |
| R4o | 64 | U167 (X-평면도(기본형)$0$ins-l) | 176 | no_census_entity_count | 0 |
| R4o | 65 | U168 (X-평면도(기본형)$0$ins-l) | 232 | no_census_entity_count | 0 |
| R4o | 66 | U169 (X-평면도(기본형)$0$ins-l) | 120 | no_census_entity_count | 0 |
| R4o | 67 | U170 (X-평면도(기본형)$0$ng) | 20 | ambiguous_entity_count | 2 |
| R4o | 68 | U172 (X-평면도(기본형)$0$ins-l) | 80 | no_census_entity_count | 0 |
| R4o | 69 | U173 (X-평면도(기본형)$0$ins-l) | 248 | no_census_entity_count | 0 |
| R4o | 70 | U174 (X-평면도(기본형)$0$ng) | 20 | ambiguous_entity_count | 2 |
| R4o | 71 | U176 (X-평면도(기본형)$0$ins-l) | 172 | no_census_entity_count | 0 |
| R4o | 72 | U177 (X-평면도(기본형)$0$ins-l) | 104 | no_census_entity_count | 0 |
| R4o | 73 | U178 (X-평면도(기본형)$0$ins-l) | 184 | no_census_entity_count | 0 |
| R4o | 74 | U179 (X-평면도(기본형)$0$ins-l) | 72 | no_census_entity_count | 0 |
| R4o | 75 | U180 (X-평면도(기본형)$0$ins-l) | 112 | target_already_mapped | 1 |
| R4o | 76 | U181 (X-평면도(기본형)$0$ins-l) | 332 | no_census_entity_count | 0 |
| R4o | 77 | U182 (X-평면도(기본형)$0$ins-l) | 588 | no_census_entity_count | 0 |
| R4o | 78 | U184 (X-평면도(기본형)$0$ins-l) | 144 | ambiguous_entity_count | 2 |
| R4o | 79 | U185 (X-평면도(기본형)$0$ins-l) | 164 | no_census_entity_count | 0 |
| R4o | 80 | U186 (X-평면도(기본형)$0$ins-l) | 128 | no_census_entity_count | 0 |
| R4o | 81 | U187 (X-평면도(기본형)$0$ins-l) | 20 | ambiguous_entity_count | 2 |
| R4o | 82 | U188 (X-평면도(기본형)$0$ins-l) | 60 | ambiguous_entity_count | 2 |
| R4o | 83 | U189 (X-평면도(기본형)$0$ins-l) | 152 | no_census_entity_count | 0 |
| R4o | 84 | U190 (X-평면도(기본형)$0$ng) | 20 | ambiguous_entity_count | 2 |
| R4o | 85 | U192 (X-평면도(기본형)$0$ins-l) | 68 | ambiguous_entity_count | 2 |
| R4o | 87 | U194 (X-평면도(기본형)$0$ins-l) | 28 | ambiguous_entity_count | 4 |
| R4o | 88 | U195 (X-평면도(기본형)$0$ins-l) | 48 | no_census_entity_count | 0 |
| R4o | 89 | U225 (X-평면도(기본형)$0$ins-l) | 108 | no_census_entity_count | 0 |
| R4o | 90 | U229 (X-평면도(기본형)$0$ins-l) | 244 | target_already_mapped | 1 |
| R4o | 92 | U231 (X-평면도(기본형)$0$ins-l) | 856 | no_census_entity_count | 0 |
| R4o | 93 | U232 (X-평면도(기본형)$0$ins-l) | 636 | no_census_entity_count | 0 |
| R4o | 94 | U233 (X-평면도(기본형)$0$ins-l) | 424 | no_census_entity_count | 0 |
| R4o | 95 | U234 (X-평면도(기본형)$0$ins-l) | 76 | no_census_entity_count | 0 |
| R4o | 96 | U265 (X-평면도(기본형)$0$ins-l) | 180 | no_census_entity_count | 0 |
| R4o | 97 | U266 (X-평면도(기본형)$0$ins-l) | 68 | ambiguous_entity_count | 2 |
| R4o | 98 | U267 (X-평면도(기본형)$0$ins-l) | 28 | ambiguous_entity_count | 4 |
| R4o | 99 | U268 (X-평면도(기본형)$0$ins-l) | 72 | no_census_entity_count | 0 |
| R4o | 100 | U271 (X-평면도(기본형)$0$ins-l) | 316 | no_census_entity_count | 0 |
| R4o | 101 | U272 (X-평면도(기본형)$0$ins-l) | 168 | no_census_entity_count | 0 |
| R4o | 102 | U273 (X-평면도(기본형)$0$ins-l) | 380 | no_census_entity_count | 0 |
| R4o | 103 | U274 (X-평면도(기본형)$0$ins-l) | 92 | target_already_mapped | 1 |
| R4o | 104 | U275 (X-평면도(기본형)$0$ins-l) | 168 | no_census_entity_count | 0 |
| R4o | 105 | U276 (X-평면도(기본형)$0$ins-l) | 280 | no_census_entity_count | 0 |
| R4o | 106 | U283 (X-평면도(기본형)$0$ins-l) | 120 | no_census_entity_count | 0 |
| R4o | 107 | U38 (X-평면도(기본형)$0$ins-l) | 152 | no_census_entity_count | 0 |
| R4o | 108 | U40 (X-평면도(기본형)$0$ins-l) | 152 | no_census_entity_count | 0 |
| R4o | 109 | U41 (X-평면도(기본형)$0$ins-l) | 48 | no_census_entity_count | 0 |
| R4o | 110 | U42 (X-평면도(기본형)$0$ins-l) | 420 | no_census_entity_count | 0 |
| R4o | 111 | U43 (X-평면도(기본형)$0$ins-l) | 164 | no_census_entity_count | 0 |
| R4o | 112 | U44 (X-평면도(기본형)$0$ins-l) | 404 | no_census_entity_count | 0 |
| R4o | 113 | U45 (X-평면도(기본형)$0$ins-l) | 408 | no_census_entity_count | 0 |
| R4o | 114 | U46 (X-평면도(기본형)$0$ins-l) | 76 | no_census_entity_count | 0 |
| R4o | 115 | U47 (X-평면도(기본형)$0$ins-l) | 272 | no_census_entity_count | 0 |
| R4o | 116 | U48 (X-평면도(기본형)$0$ins-l) | 92 | target_already_mapped | 1 |
| R4o | 117 | U49 (X-평면도(기본형)$0$ins-l) | 520 | no_census_entity_count | 0 |
| R4o | 118 | U50 (X-평면도(기본형)$0$ins-l) | 448 | no_census_entity_count | 0 |
| R4o | 119 | U51 (X-평면도(기본형)$0$ins-l) | 76 | no_census_entity_count | 0 |
| R4o | 120 | U52 (X-평면도(기본형)$0$ins-l) | 252 | no_census_entity_count | 0 |
| R4o | 121 | U53 (X-평면도(기본형)$0$ins-l) | 72 | no_census_entity_count | 0 |
| R4o | 122 | U54 (X-평면도(기본형)$0$ins-l) | 64 | no_census_entity_count | 0 |
| R4o | 123 | U55 (X-평면도(기본형)$0$ins-l) | 92 | target_already_mapped | 1 |
| R4o | 124 | U56 (X-평면도(기본형)$0$ins-l) | 604 | no_census_entity_count | 0 |
| R4o | 125 | U57 (X-평면도(기본형)$0$ins-l) | 100 | target_already_mapped | 1 |
| R4o | 126 | U60 (X-평면도(기본형)$0$ng) | 21 | ambiguous_entity_count | 2 |
| R4o | 127 | U61 (X-평면도(기본형)$0$ng) | 20 | ambiguous_entity_count | 2 |
| R4o | 128 | U63 (X-평면도(기본형)$0$ins-l) | 212 | no_census_entity_count | 0 |
| R4o | 129 | U64 (X-평면도(기본형)$0$ins-l) | 164 | no_census_entity_count | 0 |
| R4o | 130 | U65 (X-평면도(기본형)$0$ins-l) | 60 | ambiguous_entity_count | 2 |
| R4o | 131 | U66 (X-평면도(기본형)$0$ng) | 20 | ambiguous_entity_count | 2 |
| R4o | 132 | U67 (X-평면도(기본형)$0$ins-l) | 32 | ambiguous_entity_count | 6 |
| R4o | 133 | U68 (X-평면도(기본형)$0$ng) | 21 | ambiguous_entity_count | 2 |
| R4o | 134 | U69 (X-평면도(기본형)$0$ng) | 20 | ambiguous_entity_count | 2 |
| R4o | 135 | U70 (X-평면도(기본형)$0$ins-l) | 168 | no_census_entity_count | 0 |
| R4o | 136 | U72 (X-평면도(기본형)$0$ins-l) | 132 | target_already_mapped | 1 |
| R4o | 137 | U74 (X-평면도(기본형)$0$ins-l) | 156 | no_census_entity_count | 0 |
| R4o | 138 | U75 (X-평면도(기본형)$0$ins-l) | 76 | no_census_entity_count | 0 |
| R4o | 139 | U76 (X-평면도(기본형)$0$ins-l) | 36 | ambiguous_entity_count | 2 |
| R4o | 140 | U77 (X-평면도(기본형)$0$ins-l) | 284 | no_census_entity_count | 0 |
| R4o | 141 | U78 (X-평면도(기본형)$0$ins-l) | 72 | no_census_entity_count | 0 |
| R4o | 142 | U79 (X-평면도(기본형)$0$ins-l) | 64 | no_census_entity_count | 0 |
| R4o | 143 | U80 (X-평면도(기본형)$0$ins-l) | 272 | no_census_entity_count | 0 |
| R4o | 144 | U81 (X-평면도(기본형)$0$ins-l) | 32 | ambiguous_entity_count | 6 |
| R4o | 145 | U82 (X-평면도(기본형)$0$ins-l) | 120 | no_census_entity_count | 0 |
| R4o | 146 | U83 (X-평면도(기본형)$0$ins-l) | 164 | no_census_entity_count | 0 |
| R4o | 147 | U84 (X-평면도(기본형)$0$ins-l) | 24 | ambiguous_entity_count | 8 |
| R4o | 148 | U85 (X-평면도(기본형)$0$ins-l) | 92 | target_already_mapped | 1 |
| R4o | 149 | U86 (X-평면도(기본형)$0$ins-l) | 24 | ambiguous_entity_count | 8 |
| R4o | 150 | U96 (X-평면도(기본형)$0$ins-l) | 636 | no_census_entity_count | 0 |
| R4o | 151 | U97 (X-평면도(기본형)$0$ins-l) | 100 | target_already_mapped | 1 |
| R4o | 152 | U98 (X-평면도(기본형)$0$ins-l) | 152 | no_census_entity_count | 0 |
| R4o | 153 | U99 (X-평면도(기본형)$0$ins-l) | 96 | no_census_entity_count | 0 |

## Name Population Mismatches

| side | index | name | row_a_total | census_entity_count |
| --- | --- | --- | --- | --- |
| R4o | 157 | X-평면도(기본형)$0$A$C019C01BD | 143 | 117 |
| R4o | 200 | X-평면도(기본형)$0$IW990 | 464 | 451 |
| R4o | 210 | X-평면도(기본형)$0$ba15002700 | 170 | 144 |
| R4o | 219 | X-평면도(기본형)$0$ev13k | 115 | 47 |
| R4o | 220 | X-평면도(기본형)$0$ev16x2k | 230 | 94 |
| R4o | 222 | X-평면도(기본형)$0$hd1050 | 333 | 244 |
| R4o | 240 | X-평면도(기본형)$0$수전-1 | 22 | 15 |
| R4o | 241 | X-평면도(기본형)$0$씽크$0$59C$0$gasdfasdfs$0$COK3 | 83 | 38 |
| R4o | 243 | X-평면도(기본형)$0$우수관_100A | 16 | 6 |

## Verdict

Verdict: indeterminate. R4o cannot be claimed as strictly improved over R4n def-for-def because 150 diff rows could not be re-keyed onto the selected census without ambiguity and 9 name-matched rows have population mismatches. Mapped evidence shows healed=3, regressed=3, dirty_both=1, a_only=199, b_only=0.
