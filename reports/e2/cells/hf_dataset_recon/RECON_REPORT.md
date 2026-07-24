# HF / Public-Source Dataset Recon — E2 Wall-Semantic Detector Program

**Cell**: hf_dataset_recon
**Date**: 2026-07-20
**Method**: WebSearch + WebFetch/ctx_fetch_and_index (metadata & dataset cards only; NO downloads).
**Discipline**: every factual claim carries a source URL. Unconfirmed items are marked UNKNOWN.

---

## TL;DR — do our two local gaps get fixed upstream?

- **FloorPlanCAD: YES, fully.** Our local copy is the **Voxel51 test-split-only mirror**; the official source has train/val/test with project-isolation, and the "stored 35 vs doc 30" mystery is a real 35-class schema (class 31-35 = row chairs / parking spot / wall / curtain wall / railing).
- **ArchCAD-400K: PARTIALLY.** The paper defines an official **drawing-isolated 7:1:2 split** and a documented **14m×14m chunk** scale — but the public HF release is **gated** (must accept non-commercial terms), so whether the split manifest and a machine-readable mm/pixel scale ship inside the public 40K subset is **UNKNOWN without accepting the license**.
- **Most promising NEW candidate**: **CubiCasa5K** — 5,000 floor plans, SVG vector, ~83 classes incl. explicit **wall** polygons + **door/window** openings, and an **official train/val/test split (train.txt/val.txt/test.txt)**. (Note: sibling cells M-10/M-15 already reference "CubiCasa SEG-IR" data — likely already in our inventory; confirm.)

---

## Q1. FloorPlanCAD — official distribution

### Official train/val/test split — EXISTS, project-isolated
- The dataset paper (ICCV 2021, not CVPR) states: *"The annotated dataset is split into two sets: 60 projects are randomly chosen for training and the remaining for testing... 10,161 training and 5,502 testing drawings... 800 random CAD drawings are split from the training set for validation."* → split is **by project** (project-isolation), and a val set is carved from train.
  Source: https://ar5iv.labs.arxiv.org/html/2105.07147 (§4.3 Properties)
- The official download at **floorplancad.github.io** ships **svg/train**, **svg/val**, **svg/test** folders (confirmed by CADTransformer's data-prep instructions and directory tree).
  Sources: https://floorplancad.github.io/ ; https://github.com/VITA-Group/CADTransformer (Data Preparation section)

### Why our local copy has only a single 'test' split
- Our local package = the **Voxel51/FloorPlanCAD** HF mirror. Its dataset card is literally titled **"Dataset Card for FloorPlanCAD (test split)"** and the viewer shows **one `train` split of 5.31k rows** — i.e. it is the **test partition only**, re-exposed under the viewer's default `train` label.
  Source: https://huggingface.co/datasets/Voxel51/FloorPlanCAD
- **Fix**: pull the full train/val/test SVGs from the official site (floorplancad.github.io), not the Voxel51 HF mirror.

### Full label schema — 35 classes (resolves "30 vs 35" and class_31/32/34/35)
- The paper says *"35 object classes... including 30 thing classes... Two stuff classes, wall and parking."* The Voxel51 card lists only **30** named classes (28 things + wall + parking) — a simplified/earlier-revision view — which is the source of our "doc 30 vs stored 35" mismatch.
  Sources: https://ar5iv.labs.arxiv.org/html/2105.07147 (§4.2) ; https://huggingface.co/datasets/Voxel51/FloorPlanCAD
- **Authoritative machine-readable schema** is in CADTransformer `config/anno_config.py`:
  - `_C.num_class = 35` (config/default.py). Confirms 35, not 30.
  - `super_class_dict`: **countable = ids 1-30**, **uncountable/"stuff" = ids {31,32,33,34,35}**.
  - `anno_list_all` id→name (verbatim):
    1 single door · 2 double door · 3 sliding door · 4 folding door · 5 revolving door · 6 rolling door · 7 window · 8 bay window · 9 blind window · 10 opening symbol · 11 sofa · 12 bed · 13 chair · 14 table · 15 TV cabinet · 16 Wardrobe · 17 cabinet · 18 gas stove · 19 sink · 20 refrigerator · 21 airconditioner · 22 bath · 23 bath tub · 24 washing machine · 25 squat toilet · 26 urinal · 27 toilet · 28 stairs · 29 elevator · 30 escalator · **31 row chairs** · **32 parking spot** · **33 wall** · **34 curtain wall** · **35 railing**
  - So the previously-unresolved local labels are: **class_31 = row chairs, class_32 = parking spot, class_34 = curtain wall, class_35 = railing** (and class_33 = wall).
  - Note: the CODE treats **5** classes as uncountable/stuff {31 row chairs, 32 parking, 33 wall, 34 curtain wall, 35 railing}, broader than the PAPER's stated "2 stuff classes (wall, parking)." For wall-semantics work, **wall = 33** and **curtain wall = 34** are the wall-bearing labels.
  Sources: https://raw.githubusercontent.com/VITA-Group/CADTransformer/main/config/anno_config.py ; https://raw.githubusercontent.com/VITA-Group/CADTransformer/main/config/default.py

### Project/drawing grouping key
- File naming encodes the grouping: sample filepath `../image_data/0000-0003.png` → `<source-drawing id>-<block id>`, so the **filename prefix is the drawing-group key** (blocks sharing a prefix came from the same source drawing). Combined with the by-project official split, drawing/project isolation is recoverable.
  Source: https://huggingface.co/datasets/Voxel51/FloorPlanCAD (Dataset Structure sample)

### Physical coordinate scale / units
- FloorPlanCAD SVG coordinates are **metric (meters)**; entity lengths span mm→tens of meters. Original floor plans were cut into **10m×10m blocks** (paper §4.2); the Voxel51 mirror card instead states **20m×20m blocks** — a **discrepancy to flag** (paper vs mirror). Per-file exact mm/pixel is derivable from each SVG's viewBox + block size, but is not a single global constant.
  Sources: https://ar5iv.labs.arxiv.org/html/2105.07147 (§4.2) ; https://huggingface.co/datasets/Voxel51/FloorPlanCAD (Data Collection and Processing)

### License
- **CC BY-NC 4.0** (annotations); authors do not own the drawing copyright.
  Sources: https://raw.githubusercontent.com/floorplancad/floorplancad.github.io/master/index.md ; https://huggingface.co/datasets/Voxel51/FloorPlanCAD

---

## Q2. ArchCAD-400K — official distribution

Local "ArchCAD" = **ArchCAD-400K** (Luo et al., 2025; arXiv 2503.22346). HF repo: `jackluoluo/ArchCAD`.

### Official project/drawing-isolated split — EXISTS (for the full set)
- Paper §6: *"We split ArchCAD-400k into training, validation, and test sets using a 7:1:2 ratio, ensuring that each drawing and its corresponding annotations appear in only one split. This results in 289,144 ... training, 41,306 ... validation, and 82,612 ... testing."* → **drawing-isolated** split, exactly the property we need.
  Source: https://arxiv.org/html/2503.22346v3 (§6 Experiments)
- **BUT the public release is a curated SUBSET** (~40K), "further refined... with minor differences in annotation details." Whether the official split manifest ships inside the public subset is **UNKNOWN** — the HF repo is **gated** ("You need to agree to share your contact information... Access is restricted to non-commercial use"), so the file tree/split files are not inspectable without accepting terms.
  Sources: https://arxiv.org/html/2503.22346v3 (Appendix B.2) ; https://huggingface.co/datasets/jackluoluo/ArchCAD

### Physical coordinate scale (mm/pixel) — partly documented, not fully machine-readable in public docs
- Each sample is a **14m×14m chunk/slice** of a floor plan (confirmed across the HF card and multiple sources), and the **JSON modality stores real geometry coordinates** (`start:[x1,y1]`, `end:[x2,y2]`, etc.), so real-world scale is present in the data. But an explicit, documented **raster resolution (pixels) → meters/pixel** constant was **not found** in the public paper/card; the Q&A examples use pixel-space bbox coordinates (e.g. up to ~827) without a stated px-per-meter. → **UNKNOWN / needs the gated dataset's own config to confirm mm/pixel.**
  Sources: https://huggingface.co/datasets/jackluoluo/ArchCAD (Data Modalities) ; https://arxiv.org/html/2503.22346v3 (§4.2 Larger Data and Spatial Scale — avg drawing 11,000 m²)

### Labels / walls
- Primitive-level semantic + instance labels; layer-name→semantic regex mapping (doors, walls, stairs shown in paper Table 6). Wall is an annotated category. Public web reports "27 categories"; our local measured "31 classes (wall=class 20)" — a minor **category-count discrepancy** worth reconciling against the actual public-subset class map (gated).
  Sources: https://arxiv.org/html/2503.22346v3 (Appendix A.2) ; https://huggingface.co/datasets/jackluoluo/ArchCAD

### Scale / license
- 413,062 chunks from 5,538 drawings (>26× FloorPlanCAD). Public subset ~40K. License: **non-commercial** (HF gate).
  Sources: https://arxiv.org/html/2503.22346v3 (§4.2) ; https://huggingface.co/datasets/jackluoluo/ArchCAD

---

## Q3. Candidate datasets we may be missing

Criteria: floor-plan / CAD data with **wall (and ideally opening) semantic labels** + an **official project/scene-isolated split**.

| Dataset | URL | Scale | Format | Wall label? | Opening (door/window)? | Official split? | License |
|---|---|---|---|---|---|---|---|
| **CubiCasa5K** | https://github.com/CubiCasa/CubiCasa5k | 5,000 floor plans | Raster PNG + **SVG polygon** annotations | **Yes** (outer/inner wall polygons; "Wall" class) | **Yes** (Window, Door, opening polygons) | **Yes** — `train.txt`/`val.txt`/`test.txt` = 4,200 / 400 / 400 | LICENSE file in repo; non-commercial research (exact SPDX not captured — **verify**) |
| **Structured3D** | https://github.com/bertjiazheng/Structured3D | 3,500 house scenes (~21k rooms) | Synthetic 3D + 2D; vector floorplan/layout | **Yes** (wall/floor/ceiling planes, layout boundaries) | **Yes** (doors, windows; 16 room types) | **Yes** — scenes 00000–02999 train / 03000–03249 val / 03250–03499 test (scene-level) | "Structured3D Terms of Use", **registration/agreement required**, non-commercial research |
| **ResPlan** | https://arxiv.org/html/2508.14006v1 (HF paper: https://huggingface.co/papers/2508.14006) | 17,000 residential plans | **Vector** (JSON polygons/MULTIPOLYGON + room-adjacency graph, NetworkX) | **Yes** (walls, uniform `wall_depth`) | **Yes** (doors incl. `front_door`, windows) | **UNKNOWN** — paper describes benchmark tasks but no explicit train/val/test manifest confirmed | "permissive open-source license, free for research & development" (exact SPDX **UNKNOWN**) |
| **Modified Swiss Dwellings (MSD)** | https://data.4tu.nl/datasets/e1d89cb5-6872-48fc-be63-aadd687ee6f9 | 5,300 plans / 18,900 apartments (train split = 4,167) | Vector geometry (shapely) + graphs; multi-unit | **Yes** (structural walls) | Partial (openings via structure) | Partial — **train split public (4,167)**; **test split withheld** for ICCV'23 challenge (check if released since) | **CC BY 4.0** |
| **RPLAN** | http://staff.ustc.edu.cn/~fuxm/projects/DeepLayout/index.html | 80,788 plans | **Raster** 256×256 multi-channel (room type + structure) | Yes (structural channel) | Approx (door symbols noted as irregular) | Common fixed splits exist in downstream work | Request-access / research-only |
| FloorPlanCAD (ref) | https://floorplancad.github.io/ | 15,663 drawings | Vector SVG | Yes (id 33 wall, 34 curtain wall) | Yes | Yes (project-isolated) | CC BY-NC 4.0 |
| ArchCAD-400K (ref) | https://huggingface.co/datasets/jackluoluo/ArchCAD | 413k chunks (public ~40k) | 5-modal (raster/SVG/JSON/pointcloud/QA) | Yes | Yes | Yes (drawing-isolated 7:1:2; public-subset manifest UNKNOWN) | Non-commercial (gated) |

**Ranking for our need (wall semantics + clean project-isolated split, vector-native):**
1. **CubiCasa5K** — best fit: vector polygons, explicit wall + opening classes, ready-made official split. Caveat: raster-sourced (from marketing floor plans), not native CAD primitives; likely already in our inventory (M-10/M-15 mention CubiCasa).
2. **ResPlan** — largest clean vector set (17k) with walls/doors/windows and graph structure; needs split defined by us (no confirmed official split) + license SPDX check.
3. **Structured3D** — strong wall/door/window layout labels with a fixed scene-level split, but 3D-scene oriented and registration-gated.
4. **MSD** — multi-unit walls, CC BY 4.0, but test split may still be withheld.
5. **RPLAN** — large but raster-only and weaker opening geometry; lower priority for vector wall-semantics.

**Weaker/older (noted, not tabled)**: SESYD, FPLAN-POLY, CVC-FP, R-FP-500 — small symbol-spotting sets without modern project-isolated splits (per comparison table in the CubiCasa overview). Source: https://www.emergentmind.com/topics/cubicasa5k-dataset

---

## Source list (all URLs)
- FloorPlanCAD paper (ar5iv): https://ar5iv.labs.arxiv.org/html/2105.07147
- FloorPlanCAD official site: https://floorplancad.github.io/
- FloorPlanCAD site source (license): https://raw.githubusercontent.com/floorplancad/floorplancad.github.io/master/index.md
- Voxel51/FloorPlanCAD (HF, test-split mirror): https://huggingface.co/datasets/Voxel51/FloorPlanCAD
- CADTransformer repo: https://github.com/VITA-Group/CADTransformer
- CADTransformer class map (anno_config.py): https://raw.githubusercontent.com/VITA-Group/CADTransformer/main/config/anno_config.py
- CADTransformer config (num_class=35): https://raw.githubusercontent.com/VITA-Group/CADTransformer/main/config/default.py
- ArchCAD-400K paper (v3): https://arxiv.org/html/2503.22346v3
- jackluoluo/ArchCAD (HF, gated): https://huggingface.co/datasets/jackluoluo/ArchCAD
- CubiCasa5K repo: https://github.com/CubiCasa/CubiCasa5k
- CubiCasa5K overview: https://www.emergentmind.com/topics/cubicasa5k-dataset
- Structured3D repo: https://github.com/bertjiazheng/Structured3D
- Structured3D overview: https://www.emergentmind.com/topics/structure3d
- ResPlan paper: https://arxiv.org/html/2508.14006v1 (HF: https://huggingface.co/papers/2508.14006)
- Modified Swiss Dwellings (4TU): https://data.4tu.nl/datasets/e1d89cb5-6872-48fc-be63-aadd687ee6f9

## Open items / UNKNOWNs (not resolvable without accepting a license or downloading)
- ArchCAD public **40K subset**: does it ship the official 7:1:2 split manifest + per-drawing grouping key? (HF gated — not inspected.)
- ArchCAD machine-readable **mm/pixel** raster scale constant. (Not in public docs.)
- ArchCAD public-subset exact **class count** (web "27" vs our local "31") and canonical wall class id.
- ResPlan: existence of an **official train/val/test split** and exact **license SPDX**.
- CubiCasa5K + Structured3D: exact **license SPDX** strings (repo LICENSE/Terms not captured verbatim).
- MSD: whether the **test split** has been released since the ICCV'23 challenge.
