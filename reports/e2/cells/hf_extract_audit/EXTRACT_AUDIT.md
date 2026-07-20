# Local Dataset Extract Audit

- Audit date: 2026-07-20 (Asia/Seoul)
- Packet: `D:\runs\e2_program\build\PACKET_hf_extract_audit.md`
- Inventory: `D:\dev\99_tools\autocad-sdk-router\reports\e2\DATASET_INVENTORY.md`
- Scope: every one of the 11 inventory entries.
- Local evidence boundary: read-only filesystem metadata only (file and directory counts, byte sizes, extensions, shallow structure, and presence of split/license/README filenames). No dataset payload, archive member, split-file content, label file, CSV/JSON/Parquet/NPY/PPTX/CAD content, hash, or full parser was used.
- Canonical evidence boundary: public Hugging Face dataset cards/file trees plus original paper, GitHub, or Zenodo metadata viewed on the web. No canonical dataset was downloaded.
- Original data remained read-only. No git command was used.

## Verdict semantics

- **COMPLETE**: the allowed disk census matches the published canonical footprint and structure, with no positive incomplete-extract signal. It is not a hash or payload-integrity guarantee.
- **INCOMPLETE_EXTRACT**: a positive, source-backed mismatch exists between the local footprint/structure and the HF or upstream canonical.
- **UNKNOWN**: no authoritative public canonical was identified, or the allowed evidence cannot distinguish a complete copy from an extract.

An `UNKNOWN` sub-axis does not automatically erase a positive scale/structure determination. In particular, local label class counts are normally `UNKNOWN` because the task prohibited reading label payloads.

## Executive result

| # | Inventory entry | Verdict | Decisive evidence |
|---:|---|---|---|
| 1 | FloorPlanCAD | **INCOMPLETE_EXTRACT** | Local is the 5,308-image HF test derivative, while the upstream card reports 15,663 CAD drawings and vector annotations. |
| 2 | ArchCAD | **INCOMPLETE_EXTRACT** | Local has 41,097 aligned samples; the paper canonical has 413,062 chunks from 5,538 drawings and drawing-isolated train/val/test splits. |
| 3 | pseudo-floor-plan-12k | **COMPLETE** | Local has all 8/8 train Parquet shards and 3.922945924 GB; HF reports 12,000 train rows and 3.92 GB. |
| 4 | Zenodo10K partial | **INCOMPLETE_EXTRACT** | Local has 823 PPTX payloads versus 10,448 canonical examples: 9,625 payloads are absent. |
| 5 | Text2CAD | **COMPLETE** | Local is 604.874254779 GB and exposes both v1.0/v1.1, all 43 archive shards, and split manifests; the HF card reports 605 GB and the same structure. |
| 6 | CubiCasa5K | **COMPLETE** | Extracted tree has exactly 5,000 sample directories and 5,000 SVGs plus train/val/test manifests; upstream reports 5,000 samples. Two local ZIPs also match the canonical rounded 5.5 GB archive size. |
| 7 | E1 annotation corpus | **UNKNOWN** | Local-generated silver corpus; no authoritative public upstream canonical identified. |
| 8 | interior-100 / E1 real source axis | **UNKNOWN** | One local DWG plus one derived DXF; no authoritative public upstream canonical identified. |
| 9 | Hyundai304 | **UNKNOWN** | One local 3DM; no authoritative public upstream canonical identified. |
| 10 | Cheongju S1BL drawing archive | **UNKNOWN** | Local project archive; public pages about the development do not publish a canonical drawing dataset manifest. |
| 11 | Isolated implementation-drawing ZIP | **UNKNOWN** | Unopened local ZIP with no authoritative public upstream manifest; relation to entry 10 cannot be established without forbidden archive inspection or hashing. |

## 1. FloorPlanCAD — INCOMPLETE_EXTRACT

Local root: `D:\datasets\FloorPlanCAD`

| Axis | Local disk census | Canonical web evidence | Axis finding |
|---|---|---|---|
| Scale | 10,630 files, 454,847,042 bytes, 5 directories. Payload surface is `D:\datasets\FloorPlanCAD\data` with exactly 5,308 PNG files / 388,422,508 bytes; no SVG files. | The HF repository is 454 MB and explicitly calls itself the **test split** with 5,308 samples, but its card describes the upstream current dataset as 15,663 CAD drawings (10,094 in v1) with SVG plus PNG. [HF card](https://huggingface.co/datasets/Voxel51/FloorPlanCAD) The original paper describes over 10,000 vector floor plans. [Original paper](https://arxiv.org/abs/2105.07147) | Local appears complete relative to the smaller HF derivative but is only 5,308 / 15,663 = 33.9% of the current upstream count. At least 10,355 current-corpus drawings are not represented. |
| Official split / grouping | No `train`, `val`, `validation`, or `test` file/directory name was found. | The HF card labels this mirror as a test split and reports the original v1 split as 6,382 train / 3,712 test. [HF card](https://huggingface.co/datasets/Voxel51/FloorPlanCAD) | **Mismatch.** The local tree has neither the upstream training portion nor a visible upstream split manifest. |
| Label schema | Local class count is **UNKNOWN** under the no-payload-read rule. File types show only PNG payloads, not upstream SVG vector annotations. | Canonical documentation reports 30 categories: 28 thing classes plus wall and parking as two stuff classes, with line-grained semantic and instance annotations. [HF card](https://huggingface.co/datasets/Voxel51/FloorPlanCAD) [Original paper](https://arxiv.org/abs/2105.07147) | Schema count cannot be compared locally, but the canonical vector-label modality is visibly absent from the payload extension census. |
| Metadata / provenance / license | `README.md` exists; no standalone `LICENSE`/`COPYING` file and no project grouping surface was found. README content was not read in this audit. | HF exposes provenance and displays `cc-by-sa-4.0`; the original paper identifies the creators and line-grained vector source. [HF repository](https://huggingface.co/datasets/Voxel51/FloorPlanCAD/tree/main) [Original paper](https://arxiv.org/abs/2105.07147) | Local metadata is derivative-level, not a full upstream project/split surface. Exact local license text is **UNKNOWN** under the disk-only rule. |

Verdict basis: positive size, modality, and split mismatches against the upstream canonical. This is not a failed HF transfer: it is a complete-looking copy of a deliberately reduced HF test derivative.

## 2. ArchCAD — INCOMPLETE_EXTRACT

Local root: `D:\datasets\ArchCAD`

| Axis | Local disk census | Canonical web evidence | Axis finding |
|---|---|---|---|
| Scale | 205,504 files, 9,874,167,331 bytes, 14 directories. Each of `D:\datasets\ArchCAD\data\caption`, `D:\datasets\ArchCAD\data\json`, `D:\datasets\ArchCAD\data\png`, `D:\datasets\ArchCAD\data\point`, and `D:\datasets\ArchCAD\data\svg` contains exactly 41,097 files, so the visible local sample cardinality is 41,097. | The public HF card calls its release a 40k-sample, five-modality dataset. [HF card](https://huggingface.co/datasets/jackluoluo/ArchCAD/blob/main/README.md) The original ArchCAD-400K paper reports 413,062 chunks from 5,538 drawings. [Original paper](https://arxiv.org/abs/2503.22346) | Local is consistent with the public 40k HF subset, but is only 41,097 / 413,062 = 9.95% of the paper canonical; 371,965 chunks are not represented. |
| Official split / grouping | No split file/directory and no drawing/project grouping directory was found; the five modality directories are flat. | The paper splits by drawing in a 7:1:2 ratio, with 289,144 train, 41,306 validation, and 82,612 test samples, ensuring each drawing occurs in only one split. [Original paper PDF](https://openreview.net/pdf/a0f458843364c87feb914eb067244469683a5ec7.pdf) | **Mismatch.** Local has neither the canonical three-way split surface nor visible drawing-level grouping. Payload-embedded IDs remain **UNKNOWN** because payload reads were prohibited. |
| Label schema | Local label class count is **UNKNOWN**. The extension census confirms the five aligned modality types. | The HF card documents primitive semantic and instance labels and enumerates IDs 0–29 plus 100 (`Others`). [HF card](https://huggingface.co/datasets/jackluoluo/ArchCAD/blob/main/README.md) | Modality presence matches the HF subset; local class coverage cannot be verified without parsing JSON/SVG/NPY payloads. |
| Metadata / provenance / license | `README.md` exists; no standalone `LICENSE`/`COPYING`, split manifest, or source-drawing manifest was found. | HF identifies the release as CC BY-NC 4.0 and lists the five archives. [HF data tree](https://huggingface.co/datasets/jackluoluo/ArchCAD/tree/main/data) The paper supplies the 5,538-drawing provenance and split policy. [Original paper](https://arxiv.org/abs/2503.22346) | Public-subset provenance exists, but full-corpus drawing provenance/split metadata is absent from the local directory surface. |

Verdict basis: positive 10x scale mismatch and missing drawing-isolated split surface. Like FloorPlanCAD, this is a complete-looking local copy of the public HF subset, not the full paper corpus.

## 3. pseudo-floor-plan-12k — COMPLETE

Local root: `D:\datasets\pseudo-floor-plan-12k`

| Axis | Local disk census | Canonical web evidence | Axis finding |
|---|---|---|---|
| Scale | 22 files, 3,922,945,924 bytes, 5 directories. `D:\datasets\pseudo-floor-plan-12k\data` contains 8 Parquet files / 3,922,940,799 bytes. | HF reports 12,000 rows and 3.92 GB. [HF card](https://huggingface.co/datasets/zimhe/pseudo-floor-plan-12k) The file tree publishes exactly `train-00000-of-00008.parquet` through `train-00007-of-00008.parquet`. [HF data tree](https://huggingface.co/datasets/zimhe/pseudo-floor-plan-12k/tree/main/data) | **Match:** all 8/8 canonical shards and the published total size are present. |
| Official split / grouping | Eight shard names are `train-*`; no val/test surface exists. | Canonical exposes a single `train` split with 12,000 rows. [HF card](https://huggingface.co/datasets/zimhe/pseudo-floor-plan-12k) | **Match.** Absence of val/test is canonical design, not an extraction defect. |
| Label schema | Local schema and row counts are **UNKNOWN** without Parquet parsing. | HF viewer exposes `indices`, `plans`, `walls`, `colors`, `footprints`, and `captions`. [HF card](https://huggingface.co/datasets/zimhe/pseudo-floor-plan-12k) | File-level completeness matches; row/schema integrity is outside this audit. |
| Metadata / provenance / license | `README.md` exists; no standalone license file was found. | The card says the source is procedurally generated using Grasshopper with PlanFinder and warns that it is experimental; no license declaration was verifiable on the card. [HF card](https://huggingface.co/datasets/zimhe/pseudo-floor-plan-12k) | Provenance surface is present through README; canonical license is **UNKNOWN**, so no local-vs-canonical license omission can be established. |

Verdict basis: exact shard count, naming, split design, and rounded byte-size match. `COMPLETE` is repository-footprint completeness only.

## 4. Zenodo10K partial — INCOMPLETE_EXTRACT

Local root: `D:\datasets\Zenodo10K`

| Axis | Local disk census | Canonical web evidence | Axis finding |
|---|---|---|---|
| Scale | 1,654 files, 14,260,986,093 bytes, 55 directories. `D:\datasets\Zenodo10K\pptx` has 823 PPTX files / 14,257,508,634 bytes. One Parquet file is present at `D:\datasets\Zenodo10K\data`. | The HF dataset card declares one `pptx` split with 10,448 examples and identifies the corpus as more than 10,000 PowerPoint files. [HF card](https://huggingface.co/datasets/Forceless/Zenodo10K/blob/main/README.md) | **Mismatch:** 823 / 10,448 = 7.88%; 9,625 canonical PPTX payloads are absent. |
| Official split / grouping | No train/val/test surface. PPTX files are nested under 7 visible license-named directories and year subdirectories. | Canonical defines one split named `pptx`, not train/val/test. [HF card](https://huggingface.co/datasets/Forceless/Zenodo10K/blob/main/README.md) | Split naming is not defective, but payload membership is partial. |
| Label schema | No CAD/floor-plan label surface. Local Parquet schema was not parsed. | Canonical metadata fields are `filename`, `size`, `url`, `license`, `title`, `created`, `updated`, `doi`, and `checksum`. [HF card](https://huggingface.co/datasets/Forceless/Zenodo10K/blob/main/README.md) | Local metadata-row completeness is **UNKNOWN**; payload incompleteness is already proven independently. |
| Metadata / provenance / license | One Parquet file and license/year directory structure exist; no aggregate license file. | HF describes the data as Zenodo-sourced and per-item licensed and links the original PPTAgent project. [HF card](https://huggingface.co/datasets/Forceless/Zenodo10K/blob/main/README.md) [Original GitHub](https://github.com/icip-cas/PPTAgent) | Some provenance/license organization exists locally, but the 823-file payload surface cannot cover all 10,448 metadata records. |

Verdict basis: direct canonical example-count mismatch. The local tree is a payload subset even if its single metadata Parquet happens to be complete (not parsed here).

## 5. Text2CAD — COMPLETE

Local root: `C:\datasets\Text2CAD`

| Axis | Local disk census | Canonical web evidence | Axis finding |
|---|---|---|---|
| Scale | 113 files, 604,874,254,779 bytes, 21 directories. There are 43 ZIP files; non-cache data includes `cad_seq.zip`, both v1.0/v1.1 CSVs, v1.0 train/validation PKLs and model weights, v1.0 RGB/depth/minimal-JSON archives, and v1.1 RGB/minimal-JSON archives. | HF warns that full storage is 605 GB and documents the same v1.0/v1.1 components. [HF card](https://huggingface.co/datasets/SadilKhan/Text2CAD/blob/main/README.md) Its file tree exposes the two version roots, `cad_seq.zip`, and the root split manifest. [HF tree](https://huggingface.co/datasets/SadilKhan/Text2CAD/tree/main) | **Match at published precision:** 604.874 GB local versus 605 GB published, with the documented component structure present. |
| Official split / grouping | Three split manifests are present: `C:\datasets\Text2CAD\train_test_val.json`, `C:\datasets\Text2CAD\text2cad_v1.0\train_test_val.json`, and `C:\datasets\Text2CAD\text2cad_v1.1\train_test_val.json`. Contents were not read. | HF documents train/test/validation UID manifests for both versions. [HF card](https://huggingface.co/datasets/SadilKhan/Text2CAD/blob/main/README.md) | **Match by required presence.** Membership/disjointness is outside the disk-only audit. |
| Label schema | Local CSV/JSON row and field contents are **UNKNOWN**. | The paper reports about 170K CAD models and about 660K text annotations. [Original paper](https://arxiv.org/abs/2409.17106) HF documents abstract/beginner/intermediate/expert text levels, with description/keywords added in v1.1. [HF card](https://huggingface.co/datasets/SadilKhan/Text2CAD/blob/main/README.md) | Canonical annotation claims are sourced; local row-level equality is not tested. The complete repository footprint provides no extract signal. |
| Metadata / provenance / license | `README.md` and a local preservation manifest exist; no standalone `LICENSE` file. Both version roots and expected metadata filenames are present. | HF identifies DFKI provenance and CC BY-NC-SA 4.0 in the gated dataset card; its repository likewise uses the card rather than a visible standalone LICENSE at root. [HF repository](https://huggingface.co/datasets/SadilKhan/Text2CAD/tree/main) | Visible metadata surface matches the repository. Coordinate/unit details inside archives remain **UNKNOWN**. |

Verdict basis: published total size and all documented archive/version/split surfaces match. No hash or archive-member guarantee is claimed.

## 6. CubiCasa5K — COMPLETE

Local paths:

- `D:\datasets\cubicasa5k.zip` — 5,469,495,706 bytes
- `D:\dev\_ariadne\huggingface\datasets\cubicasa5k\zenodo\cubicasa5k.zip` — 5,469,495,706 bytes
- `D:\dev\_ariadne\huggingface\datasets\cubicasa5k\cubicasa5k` — extracted census below

| Axis | Local disk census | Canonical web evidence | Axis finding |
|---|---|---|---|
| Scale | Extracted tree: 17,345 files, 5,982,151,464 bytes, 5,003 directories; exactly 5,000 immediate sample directories, 5,000 SVGs, and 12,342 PNGs. Category counts are 276 under `D:\dev\_ariadne\huggingface\datasets\cubicasa5k\cubicasa5k\colorful`, 992 under `D:\dev\_ariadne\huggingface\datasets\cubicasa5k\cubicasa5k\high_quality`, and 3,732 under `D:\dev\_ariadne\huggingface\datasets\cubicasa5k\cubicasa5k\high_quality_architectural`, totaling 5,000. Each ZIP is 5.469 GB; same-size equality is not a duplicate/content proof because hashing was prohibited. | Original GitHub and paper report 5,000 samples with over 80 categories. [GitHub](https://github.com/CubiCasa/CubiCasa5k) [Original paper](https://arxiv.org/abs/1904.01920) Zenodo publishes one `cubicasa5k.zip` of 5.5 GB. [Zenodo record](https://zenodo.org/records/2613548) | **Match:** exact canonical sample/SVG count and rounded archive size. |
| Official split / grouping | `train.txt`, `val.txt`, and `test.txt` are all present. Three canonical style/category roots are present. Split contents were not read. | Original GitHub training instructions explicitly consume `train.txt`, `val.txt`, and `test.txt`. [GitHub](https://github.com/CubiCasa/CubiCasa5k) | **Match by presence.** Split membership/disjointness is outside scope. |
| Label schema | Local class count is **UNKNOWN** without SVG parsing; 5,000 SVG label files are present. | Original sources report dense polygon annotations over more than 80 floor-plan object categories. [GitHub](https://github.com/CubiCasa/CubiCasa5k) [Original paper](https://arxiv.org/abs/1904.01920) | Label-file cardinality matches sample cardinality; schema content is unparsed. |
| Metadata / provenance / license | Extracted data root contains split manifests but no README/LICENSE file. The two ZIPs were not opened. | Zenodo identifies version 1.0, creators, DOI, and CC BY-NC-SA 4.0. [Zenodo record](https://zenodo.org/records/2613548) The GitHub LICENSE instead states CC BY-NC 4.0. [GitHub LICENSE](https://github.com/CubiCasa/CubiCasa5k/blob/master/LICENSE) | Payload completeness is supported, but canonical license text is internally inconsistent across official surfaces; exact applicable license is **UNKNOWN / needs resolution**. |

Verdict basis: exact sample-directory, SVG-label, and split-manifest footprint match. The license conflict is a governance issue, not evidence that the data extract is partial.

## 7. E1 annotation corpus — UNKNOWN

Local root: `D:\dev\99_tools\autocad-sdk-router\reports\e1`

| Axis | Local disk census | Canonical web evidence | Axis finding |
|---|---|---|---|
| Scale | 178 files, 10,780,453 bytes, 17 directories. Main roots: `D:\dev\99_tools\autocad-sdk-router\reports\e1\annot_v1` (131 files), `D:\dev\99_tools\autocad-sdk-router\reports\e1\panel_20260717` (22), `D:\dev\99_tools\autocad-sdk-router\reports\e1\sonnet_annot` (20), plus 5 files at `D:\dev\99_tools\autocad-sdk-router\reports\e1`. | **UNKNOWN:** no authoritative public HF/paper/GitHub dataset canonical was identified for this local-generated corpus. | **UNKNOWN** |
| Official split / grouping | No train/val/test file or directory. | **UNKNOWN** | **UNKNOWN** |
| Label schema | 132 JSON, 21 Markdown, 20 TXT, 3 PY, 1 XLSX, and 1 JSONL by extension; contents not parsed. | **UNKNOWN** | **UNKNOWN** |
| Metadata / provenance / license | No README/LICENSE/split signal found by filename. | **UNKNOWN** | **UNKNOWN** |

No evidence permits calling this a partial extract of a public canonical. It is a local silver/weak-label work product according to the inventory, but that content claim was not re-read in this disk-only audit.

## 8. interior-100 / E1 real source axis — UNKNOWN

Local paths:

- `D:\dev\.build\1.dwg` — 2,368,524 bytes
- `D:\dev\99_tools\autocad-sdk-router\runs\e2_b3_dxfout_20260717\1_export.dxf` — 15,305,576 bytes

| Axis | Local disk census | Canonical web evidence | Axis finding |
|---|---|---|---|
| Scale | Two files, 17,674,100 bytes total. | **UNKNOWN:** exact-name web search did not identify an authoritative public dataset or manifest for this source axis. | **UNKNOWN** |
| Official split / grouping | One source file and one derived staging file; no split surface. | **UNKNOWN** | **UNKNOWN** |
| Label schema | No label file is present beside these two paths in the inventory entry. | **UNKNOWN** | **UNKNOWN** |
| Metadata / provenance / license | No adjacent canonical manifest/license is part of the entry. | **UNKNOWN** | **UNKNOWN** |

The DXF is a derived local staging artifact, not evidence of an upstream dataset extract.

## 9. Hyundai304 — UNKNOWN

Local path: `D:\dev\01_projects\02_dashboard\00_given\현대304동.3dm`

| Axis | Local disk census | Canonical web evidence | Axis finding |
|---|---|---|---|
| Scale | One 3DM file, 5,848,510 bytes. | **UNKNOWN:** exact-name web search did not identify an authoritative public dataset/model manifest for this file. | **UNKNOWN** |
| Official split / grouping | No split/grouping surface. | **UNKNOWN** | **UNKNOWN** |
| Label schema | No external label file in this inventory entry. | **UNKNOWN** | **UNKNOWN** |
| Metadata / provenance / license | No adjacent license/provenance file in this inventory entry. | **UNKNOWN** | **UNKNOWN** |

This is locally complete as one file, but “complete versus upstream canonical” is unverifiable.

## 10. Cheongju Technopolis S1BL implementation-drawing archive — UNKNOWN

Local root: `D:\dev\_ariadne\alm\build\실시도면 자료`

| Axis | Local disk census | Canonical web evidence | Axis finding |
|---|---|---|---|
| Scale | 163 files, 1,136,308,960 bytes, 12 directories: 144 DWG, 2 PDF, 2 JPG, 10 PNG, 2 LOG, 1 XLSX, 1 DWL, 1 DWL2. Top roots are `D:\dev\_ariadne\alm\build\실시도면 자료\01 건축(사업승인)` (67 files) and `D:\dev\_ariadne\alm\build\실시도면 자료\01_건축(실시설계)` (95 files), plus one file at `D:\dev\_ariadne\alm\build\실시도면 자료`. | **UNKNOWN:** web search found public references to the S1BL development, but no authoritative drawing-dataset release, file manifest, or canonical archive size. Those project references therefore cannot support a canonical completeness claim. | **UNKNOWN** |
| Official split / grouping | Approval/design-stage directories exist; no train/val/test split. | **UNKNOWN:** no public dataset split policy found. | **UNKNOWN** |
| Label schema | No separate label surface found by filename; CAD/PDF/image payloads were not parsed. | **UNKNOWN** | **UNKNOWN** |
| Metadata / provenance / license | No README/LICENSE/canonical manifest found in the tree. | **UNKNOWN** | **UNKNOWN** |

The archive may be internally complete for a project delivery, but public upstream completeness cannot be audited from authoritative web metadata.

## 11. Isolated implementation-drawing ZIP — UNKNOWN

Local path: `C:\Users\PAUL\Desktop\실시도면 자료.zip`

| Axis | Local disk census | Canonical web evidence | Axis finding |
|---|---|---|---|
| Scale | One unopened ZIP, 1,136,566,464 bytes. | **UNKNOWN:** no authoritative public dataset/archive manifest for this exact file was identified. | **UNKNOWN** |
| Official split / grouping | Archive members were not listed or opened; split surface is **UNKNOWN**. | **UNKNOWN** | **UNKNOWN** |
| Label schema | **UNKNOWN** without opening/parsing the archive, which was prohibited. | **UNKNOWN** | **UNKNOWN** |
| Metadata / provenance / license | No sidecar README/LICENSE/manifest is part of the inventory entry. | **UNKNOWN** | **UNKNOWN** |

Its size is close to entry 10, but size similarity alone cannot prove that it is a container for that tree. The required hashing/archive inspection was explicitly outside scope.

## What the upstream canonicals would add

This is an audit statement, not a download action:

- **FloorPlanCAD:** the current upstream surface adds 10,355 drawings beyond the 5,308-image HF test derivative, restores the vector SVG annotation modality, and exposes the upstream split/provenance documentation. [HF card](https://huggingface.co/datasets/Voxel51/FloorPlanCAD)
- **ArchCAD:** the paper corpus adds 371,965 chunks beyond the local 41,097 and restores the 5,538-drawing provenance plus drawing-isolated 7:1:2 split (289,144 / 41,306 / 82,612). [Original paper](https://arxiv.org/abs/2503.22346) [Original paper PDF](https://openreview.net/pdf/a0f458843364c87feb914eb067244469683a5ec7.pdf)
- **Zenodo10K:** the canonical payload set adds 9,625 PPTX files beyond the local 823, with per-item URL/license/title/date/DOI/checksum metadata. [HF card](https://huggingface.co/datasets/Forceless/Zenodo10K/blob/main/README.md)
- **pseudo-floor-plan-12k, Text2CAD, CubiCasa5K:** no missing-extract component was identified under the allowed disk census. Their `COMPLETE` verdicts remain metadata-footprint conclusions, not content-integrity attestations.
- **E1 corpus, interior-100 axis, Hyundai304, Cheongju archive, isolated ZIP:** public canonicals are unverified, so no missing component may be invented.

## Final audit counts

- **COMPLETE:** 3 — pseudo-floor-plan-12k, Text2CAD, CubiCasa5K
- **INCOMPLETE_EXTRACT:** 3 — FloorPlanCAD, ArchCAD, Zenodo10K partial
- **UNKNOWN:** 5 — E1 annotation corpus, interior-100 / E1 real source axis, Hyundai304, Cheongju S1BL archive, isolated implementation-drawing ZIP

`EXTRACT_AUDIT_COMPLETE`
