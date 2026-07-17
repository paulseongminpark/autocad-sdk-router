# cluster_probe_v1 — 판정자 합의 두-무리 무늬의 법의학 분석

- 대상 defs: 384 (5 판정자 전원 존재분)
- 전원일치: 225 / A-B 완전분열(full split): 73 / A-B 다수결분열(soft): 28 / 기타 혼재: 58

## A무리(fable,sol) 역할 -> B무리(opus,sonnet,grok) 다수결 역할

- 기타 -> 평면 부분도: 97건  (예: *U110, *U111, *U112, *U113, *U114)
- 심볼 -> 기타: 3건  (예: X-평면도(기본형)$0$1000, X-평면도(기본형)$0$100012, X-평면도(기본형)$0$1000m)
- 기타 -> 심볼: 1건  (예: X-평면도(기본형)$0$jjbl)

## 벽확률(wall_likelihood)은 분열 def에서도 일치하는가
- 분열 def에서 무리간 평균 |Δwl| = 0.1538
- 전원일치 def에서 무리간 평균 |Δwl| = 0.0359

## rationale 대조 표본 (상위 혼동 셀)

### *U110 — 기타 -> 평면 부분도 (n=97)
- fable5_high: role=기타, wl=0.15
  - rule: An anonymous *U block whose contents are one entity type repeated with identical vertex counts on a single material/pattern layer (e.g. INSUL) is a machine-generated pattern cluster (group or hatch-proxy for insulation batting), not a semantic plan fragment, symbol, dimension cache, or furniture blo
  - evidence: The definition is an anonymous block (*U110) whose 38 entities are 100% LWPOLYLINE, all on the single xref-bound insulation layer 'X-평면도(기본형)$0$INSUL' (sampled handles 44F5..4512, consecutive). Every sampled polyline has exactly 5 vertices, the signature of one small repeated module rather than free
- opus48_max: role=평면 부분도, wl=0.5
  - rule: A definition whose entities are exclusively closed 5-vertex polylines on a plan-view '...$INSUL' layer is wall-cavity insulation hatch — a plan-construction fragment, not a reusable icon, a dimension cache, or furniture. Insulation only occurs inside walls, so the block is wall-associated even thoug
  - evidence: All 38 entities are LWPOLYLINE on layer X-평면도(기본형)$0$INSUL (insulation), each a closed 5-vertex quad (e.g. handles 44F5, 44F6); the dxf histogram is 100% LWPOLYLINE with no LINE entities, so bbox is not derivable. Content is homogeneous insulation fill with no wall-outline, text, or dimension geomet

### X-평면도(기본형)$0$1000 — 심볼 -> 기타 (n=3)
- fable5_high: role=심볼, wl=0.1
  - rule: DOOR 단일 레이어 + 스윙 ARC + 이름이 개구폭 수치인 소형 블록은 문 심볼로 분류하고, 내부 평행 LINE은 문틀·문지방 선으로 벽선에서 제외한다.
  - evidence: 16개 엔티티 전부가 DOOR 레이어이고 ARC 1개(문 스윙 호)와 다수의 소형 LWPOLYLINE(문짝·문틀 단면)으로 구성된다. bbox 폭이 약 980으로 블록명 '1000'(호칭 개구폭)과 일치한다. LINE (960,-40)->(40,-40)과 (960,-43)->(40,-43)은 3 간격 평행선으로 문지방/마감선이지 벽이 아니다.
- opus48_max: role=기타, wl=0.1
  - rule: A DOOR-layer block of two closely spaced (~3mm) long lines plus a swing arc and leaf polylines is an architectural door; it is neither furniture, symbol, dimension nor a multi-element plan fragment, hence 기타.
  - evidence: All entities are on X-평면도(기본형)$0$DOOR: one ARC is the door swing, the LWPOLYLINEs (5-19 vtx) form the leaf and hardware, and the paired LINEs 8218 (960,-40)->(40,-40) and 8219 (960,-43)->(40,-43) run 920mm but only 3mm apart - the drawn door frame/leaf, far below wall thickness. The door width (~960

### X-평면도(기본형)$0$jjbl — 기타 -> 심볼 (n=1)
- fable5_high: role=기타, wl=0.0
  - rule: Single-layer blocks consisting of one boundary polyline plus a uniform array of identical small circles are surface-pattern/finish symbols, which fall outside the plan-fragment/symbol-object/furniture buckets - hence 기타. Note: if 점자블록 (tactile paving), it is a finish element, still 기타.
  - evidence: All 37 entities are on $0$TILE and 36 of them are CIRCLEs of exactly radius 10 with a single 4-vertex LWPOLYLINE as boundary - a uniform dot array, i.e. a floor-finish/anti-slip tile pattern swatch. No lines exist at all (bbox not derivable from LINEs). The name jjbl is a shorthand (possibly 줄눈/점자블록
- opus48_max: role=기타, wl=0.02
  - rule: 동일 소형 원이 격자로 반복되는 TILE 레이어 블록은 패턴(기타)으로 분류하며 벽 기여는 없다.
  - evidence: 37개 엔티티가 TILE 레이어이며 CIRCLE(r=10) 36개+LWPOLYLINE 1(경계)로 동일 소원이 격자로 반복된다. 반복 소원 패턴은 단일 심볼이 아니라 타일/미끄럼방지 점 패턴에 해당한다.

