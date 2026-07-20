# ArchCAD-400K full-corpus acquisition recon

- 조사일: 2026-07-20 (Asia/Seoul)
- 판정: **전체 400K 조달 경로 = UNKNOWN**
- 범위: 공개 웹 자료 조사만 수행했다. 데이터 다운로드, 이메일 발송, `git` 사용은 하지 않았다.

## Executive conclusion

공식 GitHub는 현재 Hugging Face 배포본을 **full collection의 curated 40K subset인 첫 공개 배치**라고 명시하고, 이후 배포는 미래 계획이라고만 쓴다. 따라서 현재 공식 링크는 413,062-chunk 전체본의 링크가 아니다: [official README, Dataset & Preprocess](https://github.com/ArchiAI-LAB/ArchCAD#datasetpreprocess), [official HF dataset card](https://huggingface.co/datasets/jackluoluo/ArchCAD).

확인한 공식 표면 어디에도 전체 413,062 chunks를 받는 별도 공개 URL, 승인형(gated) 신청 폼, 또는 저자 요청 시 제공한다는 정책이 없다: [GitHub README](https://github.com/ArchiAI-LAB/ArchCAD), [GitHub releases](https://github.com/ArchiAI-LAB/ArchCAD/releases), [GitHub issues](https://github.com/ArchiAI-LAB/ArchCAD/issues), [arXiv HTML](https://arxiv.org/html/2503.22346), [OpenReview forum](https://openreview.net/forum?id=rAGWvnpcKe), [NeurIPS proceedings](https://proceedings.neurips.cc/paper_files/paper/2025/hash/b96ce7d38339874a8704e8895f743284-Abstract-Conference.html). 그러므로 **public URL**, **gated full-corpus route**, **request-only** 중 어느 것도 검증할 수 없으며 최종 분류는 **UNKNOWN**이다.

현재 가능한 구체적 에스컬레이션은 논문에 명시된 두 corresponding author에게 사람이 직접 문의하는 것이다. 연락처는 **Hongjie Zhang — `nju.zhanghongjie@gmail.com`**, **Xianzhong Zhao — `x.zhao@tongji.edu.cn`**이다: [arXiv author block](https://arxiv.org/html/2503.22346#Sx1). 이것은 권장 문의 경로일 뿐, 저자가 full corpus를 요청 시 제공한다고 공표한 **request-only 정책을 뜻하지 않는다**.

## 1. GitHub repository, releases, issues, and data route

### README / data section

- 공식 저장소는 ArchCAD-400K를 400K+ 규모라고 소개하지만, 데이터 절에서는 2025-10-16 배포를 “initial public release”와 “first batch”라고 부르고, **full collection의 refined portion인 curated 40K subset**만 열었다고 명시한다. 후속 공개는 “plans for subsequent releases in the future”로만 적혀 있고 날짜나 전체본 URL은 없다: [official README](https://github.com/ArchiAI-LAB/ArchCAD#archcad-400k).
- README가 연결하는 유일한 데이터 URL은 `jackluoluo/ArchCAD`이며, 해당 카드도 명시적으로 **40k Samples**라고 표시한다: [GitHub dataset link](https://github.com/ArchiAI-LAB/ArchCAD#datasetpreprocess), [official HF card](https://huggingface.co/datasets/jackluoluo/ArchCAD).
- 이 40K 저장소 자체는 Hugging Face 계정 로그인, 연락처 공유, 비상업 목적 동의, 심사를 요구하는 **gated dataset**이며 승인에는 최대 3 business days가 걸릴 수 있다고 적혀 있다: [HF access notice](https://huggingface.co/datasets/jackluoluo/ArchCAD), [HF file tree](https://huggingface.co/datasets/jackluoluo/ArchCAD/tree/main). 이 gating은 **40K 공개 subset**에 관한 것이지 전체 413,062 chunks에 관한 것이 아니다: [official README](https://github.com/ArchiAI-LAB/ArchCAD#archcad-400k).

### Releases

- 공식 GitHub Releases 페이지에는 공개된 release가 없다: [GitHub releases](https://github.com/ArchiAI-LAB/ArchCAD/releases). 따라서 release asset으로 제공되는 full-corpus archive도 확인되지 않는다.

### Issues / community evidence

- Issue #5의 사용자는 데이터셋과 split 사용법을 질문했지만 저자 답변이나 full-corpus 획득 절차는 페이지에 없다: [GitHub issue #5](https://github.com/ArchiAI-LAB/ArchCAD/issues/5).
- Issue #8은 제3자가 내려받은 공개본을 “released 40K subset”이라고 부르며 41,097 JSON 파일을 보고했지만, 이 게시물에도 저자 답변이나 full-corpus 링크는 없다: [GitHub issue #8](https://github.com/ArchiAI-LAB/ArchCAD/issues/8).
- 공식 HF discussion #1에는 “Have you released the full 400k dataset somewhere?”라는 공개 질문이 있으나, 현재 표시된 페이지에는 답변이 없다: [HF discussion #1](https://huggingface.co/datasets/jackluoluo/ArchCAD/discussions/1).

### Unverified look-alike lead

- `kashiten/rubbish`라는 비공식 HF 페이지는 “400K samples”를 주장하지만, 총 파일 크기가 10.3 kB로 표시되고 공식 GitHub가 연결한 `jackluoluo/ArchCAD`와 계정/저장소가 다르다: [unverified HF page](https://huggingface.co/datasets/kashiten/rubbish), [official GitHub link](https://github.com/ArchiAI-LAB/ArchCAD#datasetpreprocess). 저자 소유 또는 full corpus라는 provenance를 검증할 수 없으므로 획득 경로로 취급하지 않는다.

**질문 1 답:** HF 40K가 논문 전체 corpus는 아니다. 그러나 별도 전체본 배포처는 공식 README, releases, 확인 가능한 issues에서 찾지 못했다. **Full-corpus URL = UNKNOWN.**

## 2. Paper data availability and author contact

### Corpus identity

- 논문은 ArchCAD-400K를 **5,538 standardized drawings에서 만든 413,062 chunks**라고 정의한다: [arXiv abstract/body](https://arxiv.org/html/2503.22346#S1).
- train/validation/test는 drawing 단위 격리를 유지하는 **7:1:2** 분할이며 각각 289,144 / 41,306 / 82,612 samples라고 명시한다: [arXiv experiments](https://arxiv.org/html/2503.22346#S6).

### Availability statement

- arXiv 본문에는 별도의 “Data Availability” 절이나 full-corpus 다운로드/요청 절차가 확인되지 않는다: [arXiv full HTML](https://arxiv.org/html/2503.22346).
- 본문은 저작권/윤리 조치로 데이터 익명화와 메타데이터 비가역 난독화를 설명하며, copyright/IP를 침해할 수 있는 raw data는 공개하지 않는다고 한다: [Ethical and Copyright Considerations](https://arxiv.org/html/2503.22346#S3.SS3.SSS0.Px1).
- OpenReview/NeurIPS 체크리스트는 코드와 데이터가 각각 GitHub와 Hugging Face에 공개되어 있다고 답하지만, full 413K인지 별도로 밝히지 않는다: [OpenReview paper/checklist PDF](https://openreview.net/pdf?id=rAGWvnpcKe). 현재 공식 GitHub가 그 HF 링크를 40K first batch로 한정하므로, 체크리스트 문구만으로 전체본 공개를 입증할 수 없다: [official README](https://github.com/ArchiAI-LAB/ArchCAD#archcad-400k).
- 같은 체크리스트는 dataset license를 **CC BY-NC 4.0**, code license를 **CC BY 4.0**이라고 적는다: [NeurIPS paper/checklist PDF](https://proceedings.neurips.cc/paper_files/paper/2025/file/b96ce7d38339874a8704e8895f743284-Paper-Conference.pdf). 공식 HF 40K 카드도 `cc-by-nc-4.0`을 표시한다: [HF card](https://huggingface.co/datasets/jackluoluo/ArchCAD). 단, 미공개 full corpus에 실제로 적용될 라이선스와 추가 조건은 **UNKNOWN**이다.

### Author contact

- Corresponding authors: Hongjie Zhang — `nju.zhanghongjie@gmail.com`; Xianzhong Zhao — `x.zhao@tongji.edu.cn`: [arXiv author block](https://arxiv.org/html/2503.22346#Sx1).
- 저자들이 이메일 요청을 full-corpus의 공식 신청 방식으로 선언한 문서는 찾지 못했다. 따라서 **request-only = unverifiable / UNKNOWN**이다: [GitHub README](https://github.com/ArchiAI-LAB/ArchCAD), [arXiv HTML](https://arxiv.org/html/2503.22346), [OpenReview forum](https://openreview.net/forum?id=rAGWvnpcKe).

**질문 2 답:** 논문/체크리스트는 공개를 주장하지만 실제 연결 표면은 40K subset뿐이다. 전체본의 public 또는 request-only availability는 **UNKNOWN**이다. 저자 연락처는 위 두 주소로 검증됐다.

## 3. OpenReview forum and supplementary

- 이 논문의 OpenReview forum ID는 **`rAGWvnpcKe`**이며 PDF endpoint도 같은 ID를 사용한다: [forum](https://openreview.net/forum?id=rAGWvnpcKe), [PDF](https://openreview.net/pdf?id=rAGWvnpcKe).
- NeurIPS 2025 proceedings는 이 논문에 별도 **Supplemental** 링크를 노출한다: [proceedings record](https://proceedings.neurips.cc/paper_files/paper/2025/hash/b96ce7d38339874a8704e8895f743284-Abstract-Conference.html), [supplemental ZIP endpoint](https://proceedings.neurips.cc/paper_files/paper/2025/file/b96ce7d38339874a8704e8895f743284-Supplemental-Conference.zip).
- 조사 중 OpenReview는 browser verification challenge를 반환했고, 검색으로 확인 가능한 checklist 내용 외 forum review/rebuttal 본문을 검증하지 못했다: [forum endpoint](https://openreview.net/forum?id=rAGWvnpcKe). Packet의 no-download 규율에 따라 supplemental ZIP은 내려받지 않았다. 따라서 supplemental 안에 full-corpus 데이터 또는 획득 지침이 있는지는 **UNKNOWN**이다.
- 공개 HTML arXiv에는 appendix와 “Baseline Results on the Public Subset of ArchCAD-400k” 절이 포함되지만, full-corpus archive URL은 표시되지 않는다: [arXiv table of contents/full HTML](https://arxiv.org/html/2503.22346).

**질문 3 답:** OpenReview forum은 존재하고 NeurIPS supplemental ZIP도 존재한다. 그러나 no-download 조건에서 ZIP contents는 검증하지 못했으며, 공개 인덱스에는 full dataset asset/link가 없다. **Supplementary full-corpus route = UNKNOWN.**

## 4. Acquisition classification, size, license, gating

| 항목 | 판정 | 근거 |
|---|---|---|
| 전체 413,062 chunks 공개 URL | **UNKNOWN / 찾지 못함** | 공식 README는 40K first batch만 연결: [GitHub](https://github.com/ArchiAI-LAB/ArchCAD#archcad-400k) |
| 전체 corpus gated URL/form | **UNKNOWN / 찾지 못함** | 공식 HF gating은 40K 카드에 적용: [HF](https://huggingface.co/datasets/jackluoluo/ArchCAD) |
| 저자 request-only 정책 | **UNKNOWN / 공표 없음** | 연락처는 있으나 요청 제공 정책은 없음: [arXiv](https://arxiv.org/html/2503.22346#Sx1) |
| 공식 라이선스 진술 | dataset **CC BY-NC 4.0** | [NeurIPS checklist](https://proceedings.neurips.cc/paper_files/paper/2025/file/b96ce7d38339874a8704e8895f743284-Paper-Conference.pdf), [HF card](https://huggingface.co/datasets/jackluoluo/ArchCAD) |
| 미공개 full corpus의 실제 조건 | **UNKNOWN** | full-corpus access instrument/terms가 공개되지 않음: [official README](https://github.com/ArchiAI-LAB/ArchCAD) |
| full corpus 압축 크기 | **UNKNOWN** | 공식 sources에 full archive size가 없음: [GitHub](https://github.com/ArchiAI-LAB/ArchCAD), [HF](https://huggingface.co/datasets/jackluoluo/ArchCAD/tree/main/data) |

공식 40K HF 파일 목록은 caption 19.8 MB, JSON 393 MB, PNG 1.83 GB, point 80.4 MB, SVG 311 MB로 합계 약 **2.63 GB**를 표시한다: [HF data tree](https://huggingface.co/datasets/jackluoluo/ArchCAD/tree/main/data). 이를 40,000 → 413,062 비율로 단순 선형 외삽하면 약 **27 GB compressed**지만, 이는 파일 구성/압축률이 동일하다는 가정의 조사자 추정일 뿐 저자 발표치가 아니다; 운영 용량 계획에는 사용하지 말고 저자에게 실제 archive size/checksum을 확인해야 한다: [40K count](https://huggingface.co/datasets/jackluoluo/ArchCAD), [413,062 count](https://arxiv.org/html/2503.22346#S1).

## Concrete next steps (no automatic send)

1. Paul 승인 후 두 corresponding author에게 **동일한 수동 이메일**을 보낸다: `nju.zhanghongjie@gmail.com`, `x.zhao@tongji.edu.cn` ([source](https://arxiv.org/html/2503.22346#Sx1)).
2. 문의에서 “현재 HF 40K subset이 아니라 논문 실험의 413,062 chunks / 5,538 drawings / drawing-isolated 7:1:2 split”이라고 범위를 고정한다: [corpus size](https://arxiv.org/html/2503.22346#S1), [split](https://arxiv.org/html/2503.22346#S6), [40K subset](https://github.com/ArchiAI-LAB/ArchCAD#archcad-400k).
3. 공개/gated URL, 신청/NDA 요건, 정확한 압축/해제 GB, checksum, full-corpus license/terms, split manifest, annotations 포함 여부를 요청한다.
4. 저자 답변 전에는 `kashiten/rubbish`를 사용하지 않는다. 공식 provenance도 없고 표시 용량도 10.3 kB뿐이다: [unverified page](https://huggingface.co/datasets/kashiten/rubbish), [official route](https://github.com/ArchiAI-LAB/ArchCAD#datasetpreprocess).
5. 저자 답변이 없으면 official HF discussion #1 또는 GitHub issue #5에 공개적으로 follow-up하되, 이는 별도 승인 후 사람이 수행한다: [HF discussion](https://huggingface.co/datasets/jackluoluo/ArchCAD/discussions/1), [GitHub issue](https://github.com/ArchiAI-LAB/ArchCAD/issues/5).

### Manual email draft (not sent)

**Subject:** Request for access instructions for the full ArchCAD-400K corpus (413,062 chunks)

Dear Prof. Zhang and Prof. Zhao,

I am seeking the full ArchCAD-400K corpus used in your paper—not the currently released 40K Hugging Face subset. Specifically, I need the 413,062 annotated chunks from 5,538 drawings with the drawing-isolated 7:1:2 train/validation/test split.

Could you please confirm whether the full corpus is (1) publicly downloadable, (2) available through a gated application, or (3) available only by direct request? If access is possible, please provide the authoritative URL or application procedure, the exact license/usage terms, compressed and extracted size, checksums, split manifest, and confirmation that semantic and instance annotations are included.

Intended use: [academic/non-commercial project description].  
Affiliation: [organization].

Thank you.

## Final answer

**전체 400K 조달 경로 = UNKNOWN.** 공식 경로는 gated 40K first batch뿐이며, full 413K의 public/gated/request-only 절차는 검증되지 않았다. Paul 승인 후 위 템플릿으로 두 corresponding author에게 수동 문의하는 것이 현재의 구체적 다음 단계다.
