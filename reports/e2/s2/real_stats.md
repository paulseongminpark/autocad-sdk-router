# S2-A real-corpus wall statistics (rs.v1)

Fidelity yardstick for the E2 synthetic generator. Extracted deterministically from E1 shard projections (LINE coords only) and annot_v1 judge annotations.

- units parsed: **384** (with reference-judge role: 384)
- defs with >=2 sampled LINEs: **237**
- reference judge (roles): `opus48_max`
- wall-handle union judges: opus48_max, fable5_high, sol56_xhigh, sonnet5_xhigh, grok45_xhigh

## 1. Parallel LINE-pair spacing (candidate thickness)

Pairs: within-def LINE pairs (same definition); parallel within 2.0 deg; overlap ratio >= 0.3. Gap = perpendicular spacing of the parallel pair (drawing units). Total pairs: **4877** ({'WALL': 253, 'DOOR': 207, 'DIM': 110, 'other': 4307}).

Histogram (drawing units ~mm), counts per class:

| bin [lo,hi) | WALL | DOOR | DIM | other | all |
|---|---|---|---|---|---|
| 0..1 | 0 | 28 | 0 | 11 | 39 |
| 1..2 | 0 | 47 | 0 | 28 | 75 |
| 2..5 | 0 | 87 | 0 | 57 | 144 |
| 5..10 | 0 | 24 | 0 | 116 | 140 |
| 10..25 | 0 | 6 | 0 | 529 | 535 |
| 25..50 | 0 | 7 | 0 | 219 | 226 |
| 50..75 | 0 | 4 | 2 | 312 | 318 |
| 75..100 | 0 | 0 | 4 | 189 | 193 |
| 100..125 | 0 | 2 | 0 | 153 | 155 |
| 125..150 | 0 | 2 | 7 | 199 | 208 |
| 150..175 | 0 | 0 | 5 | 92 | 97 |
| 175..200 | 0 | 0 | 2 | 75 | 77 |
| 200..250 | 3 | 0 | 5 | 80 | 88 |
| 250..300 | 34 | 0 | 1 | 148 | 183 |
| 300..400 | 0 | 0 | 6 | 227 | 233 |
| 400..500 | 2 | 0 | 2 | 142 | 146 |
| 500..750 | 18 | 0 | 9 | 271 | 298 |
| 750..1000 | 10 | 0 | 12 | 325 | 347 |
| 1000..1500 | 7 | 0 | 10 | 299 | 316 |
| 1500..2500 | 11 | 0 | 20 | 233 | 264 |
| 2500..5000 | 69 | 0 | 15 | 205 | 289 |
| 5000..10000 | 59 | 0 | 5 | 234 | 298 |
| 10000..20000 | 40 | 0 | 5 | 133 | 178 |
| 20000..50000 | 0 | 0 | 0 | 9 | 9 |
| 50000..300000 | 0 | 0 | 0 | 21 | 21 |

Top candidate thickness bands per class (bin, count):
- **WALL**: [2500,5000)=69, [5000,10000)=59, [10000,20000)=40
- **DOOR**: [2,5)=87, [1,2)=47, [0,1)=28
- **DIM**: [1500,2500)=20, [2500,5000)=15, [750,1000)=12
- **other**: [10,25)=529, [750,1000)=325, [50,75)=312

Judge-wall-confirmed subset (both handles flagged as wall_line_handles by the union of all 5 judges): **504** pairs {'WALL': 158, 'DOOR': 13, 'DIM': 0, 'other': 333}.

## 2. Entity-type mix per def role (reference judge)

| role | n_defs | total_entities | 3DFACE | ARC | CIRCLE | ELLIPSE | HATCH | INSERT | LINE | LWPOLYLINE | MTEXT | POINT | POLYLINE | SPLINE | TEXT | WIPEOUT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 평면 부분도 | 174 | 18793 | 0 | 960 | 35 | 71 | 255 | 914 | 7852 | 6705 | 0 | 0 | 0 | 1920 | 76 | 5 |
| 치수캐시 | 113 | 1053 | 0 | 0 | 0 | 0 | 0 | 226 | 375 | 0 | 113 | 339 | 0 | 0 | 0 | 0 |
| 심볼 | 52 | 1680 | 0 | 142 | 17 | 28 | 7 | 15 | 1043 | 364 | 0 | 2 | 0 | 28 | 6 | 28 |
| 가구 | 39 | 6302 | 34 | 1092 | 53 | 102 | 2 | 2 | 2725 | 266 | 0 | 0 | 1 | 2025 | 0 | 0 |
| 기타 | 6 | 293 | 0 | 4 | 36 | 0 | 0 | 1 | 115 | 65 | 0 | 0 | 0 | 0 | 72 | 0 |

## 3. Layer-token frequency ($ + non-alnum split)

90 distinct tokens across 79 distinct layers (weighted by entity count). Top 30:

| token | weighted count |
|---|---|
| `0` | 27040 |
| `X` | 26434 |
| `기본형` | 26203 |
| `평면도` | 26203 |
| `FUR` | 10817 |
| `INSUL` | 6235 |
| `W1` | 1664 |
| `I` | 1183 |
| `FL` | 1181 |
| `W2` | 1013 |
| `S` | 920 |
| `DIM` | 692 |
| `CEN` | 624 |
| `DOOR` | 597 |
| `INS` | 563 |
| `7GYP` | 556 |
| `MC` | 467 |
| `4GYP` | 447 |
| `KIT` | 409 |
| `WID` | 382 |
| `DEFPOINTS` | 375 |
| `수전` | 368 |
| `A` | 270 |
| `B` | 261 |
| `TIL` | 242 |
| `FORM` | 231 |
| `SHEET` | 231 |
| `청주` | 231 |
| `4ELE` | 211 |
| `40HAT` | 182 |

## LIMITS

- Spacing is over **sampled** LINEs (<=30 per def); defs with more entities have partial LINE coverage.
- WALL class = LINE on a wall-family layer (W/W<n>/WALL); a WALL pair's gap is NOT necessarily a wall thickness (wall layers also carry room-boundary spans).
- Polylines (LWPOLYLINE) carry no coordinates in projections and contribute no spacing pairs.
