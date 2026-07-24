# Roundtrip Fidelity Report

## Source + SHA
- Original path: `D:\dev\.build\1.dwg`
- Original sha256: `14eb65eb292d8a07f38ab5662dcafe9761c6185bc5ff0c8a9a008be15b598961`
- Staged sha256: `14eb65eb292d8a07f38ab5662dcafe9761c6185bc5ff0c8a9a008be15b598961`

## Honest ceiling
- Modelspace entities: 375
- Certified total: 375
- Out-of-class total: 0
- Deferred count: 7187

### Deferred block-definition budget
- Max def entities per block: 25000
- Dropped definitions: 0
- Dropped def entities: 0
- Dropped pct of block-def entities: 0.0%

## Per-kind verdict table
PASS: 6 | FAIL: 0 | VACUOUS: 8

| DXF Name | Certified | Census | Attempted | Diff0 | Status |
| --- | --- | ---: | ---: | ---: | --- |
| ARC | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| CIRCLE | yes | 1 | 1 (live 1) | 1 | PASS [deferred 0] |
| DIMENSION | yes | 113 | 113 (live 113) | 113 | PASS [deferred 0] |
| ELLIPSE | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| INSERT | yes | 50 | 50 (live 50) | 50 | PASS [deferred 1263] |
| LEADER | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| LINE | yes | 21 | 21 (live 21) | 21 | PASS [deferred 0] |
| LWPOLYLINE | yes | 73 | 73 (live 73) | 73 | PASS [deferred 1443] |
| MLINE | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| MTEXT | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| MULTILEADER | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| POLYLINE | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| SPLINE | yes | 0 | 0 (live 0) | 0 | VACUOUS [deferred 0] |
| TEXT | yes | 117 | 117 (live 117) | 117 | PASS [deferred 0] |

## Per-layer example rollup
- Aggregated from verdict examples only; if row totals exceed recorded examples, this table is a sample rather than a full census.
| Layer | Removed | Added | Modified | Total |
| --- | ---: | ---: | ---: | ---: |
| (none) | 0 | 0 | 0 | 0 |

## Diff patterns table
| Signature | Count | Judgment | Note |
| --- | ---: | --- | --- |
| block_reference / deferred / reason:def_entity kind unsupported by write.block.append_entity | 943 | unreviewed |  |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U103' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U104' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U105' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U106' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U107' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U108' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U109' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U110' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U111' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U112' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U113' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U114' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U115' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U116' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U117' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U118' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U119' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U120' | 4 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U121' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U122' | 4 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U123' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U124' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U125' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U126' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U127' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U128' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U129' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U130' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U131' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U132' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U133' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U134' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U135' | 3 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U136' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U137' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U138' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U139' | 4 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U140' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U141' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U142' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U144' | 18 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U145' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U146' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U147' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U148' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U149' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U150' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U151' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U152' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U155' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U156' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U157' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U158' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U159' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U160' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U161' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U162' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U163' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U164' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U165' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U166' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U167' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U168' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U169' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U170' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U171' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U172' | 26 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U173' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U174' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U175' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U176' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U177' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U179' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U180' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U181' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U183' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U184' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U185' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U186' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U187' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U188' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U189' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U191' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U192' | 4 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U193' | 4 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U194' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U195' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U196' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U197' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U199' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U200' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U201' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U202' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U232' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U236' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U237' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U238' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U239' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U240' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U241' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U272' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U273' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U274' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U275' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U278' | 4 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U279' | 4 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U280' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U281' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U282' | 3 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U283' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U290' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U45' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U47' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U48' | 4 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U49' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U50' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U51' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U52' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U53' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U54' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U55' | 3 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U56' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U57' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U58' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U59' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U60' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U61' | 6 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U62' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U63' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U64' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U67' | 6 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U68' | 6 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U70' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U71' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U72' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U73' | 6 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U74' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U75' | 5 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U76' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U77' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U79' | 7 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U81' | 6 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U82' | 3 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U83' | 4 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U84' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U85' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U86' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U87' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U88' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U89' | 2 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U90' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U91' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U92' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| block_reference / deferred / reason:no block_definitions entry for nested block_name '*U93' | 1 | harmful | Deferred op references a missing block definition; real fidelity loss. |
| ellipse / deferred / reason:def_entity kind unsupported by write.block.append_entity | 201 | unreviewed |  |
| face3d / deferred / reason:def_entity kind unsupported by write.block.append_entity | 34 | unreviewed |  |
| hatch / deferred / reason:def_entity kind unsupported by write.block.append_entity | 265 | unreviewed |  |
| lwpolyline / deferred / reason:def_entity kind unsupported by write.block.append_entity | 1443 | unreviewed |  |
| point / deferred / reason:def_entity kind unsupported by write.block.append_entity | 2 | unreviewed |  |
| polyline / deferred / reason:def_entity kind unsupported by write.block.append_entity | 1 | unreviewed |  |
| spline / deferred / reason:def_entity kind unsupported by write.block.append_entity | 3973 | unreviewed |  |
| wipeout / deferred / reason:def_entity kind unsupported by write.block.append_entity | 5 | unreviewed |  |

## Naive-foil vs smart contrast
- naive_pass: `True`
- smart_all_diff0: `True`
- note: Naive foil and smart diff0 gate both pass on this run.

## Evidence paths
- `D:\dev\99_tools\autocad-sdk-router\runs\e2e_1dwg_R3b_full_20260708\summary.json`
- `D:\dev\99_tools\autocad-sdk-router\runs\e2e_1dwg_R3b_full_20260708\census_report.json`
- `D:\dev\99_tools\autocad-sdk-router\runs\e2e_1dwg_R3b_full_20260708\verdict.json`
- `D:\dev\99_tools\autocad-sdk-router\runs\e2e_1dwg_R3b_full_20260708\regen_summary.json`
- `D:\dev\99_tools\autocad-sdk-router\runs\e2e_1dwg_R3b_full_20260708\deferred.json`
