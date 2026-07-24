# 데이터셋 조달 이력 (W3 다운로드 — Paul 승인 2026-07-20)

근거: D9 추출 감사(@298a1bc)로 로컬본 3종이 불완전 추출본 확정. Paul "다운로드 받자 모두"
→ Zenodo10K 제외(242GB PPTX 무관, Paul 확정) → FloorPlanCAD·ArchCAD 조달.

## FloorPlanCAD 정본 — 완료·검증됨
- 경로: `D:\datasets\FloorPlanCAD_official\{train,val,test}\` (+ *.zip 원본)
- 출처: CADTransformer(github.com/VITA-Group/CADTransformer) `preprocess/download_data.py`의
  Google Drive ID 3종 → gdown. 공식 배포 floorplancad.github.io(2022 종료, 링크는 생존 실측).
- 규모: **train 6,965 + val 810 + test 3,827 = 11,602 SVG** (기존 로컬 5,308 test-only의 2.2배).
- 라벨 검증: SVG에 `semanticId`+`instanceId` 실재. 샘플 semanticId=33(wall) 159회 등장.
  프로젝트-격리 분할 구조(train/val/test 디렉토리) 확인.
- zip 무결성: train/val/test 전건 PK magic VALID_ZIP.
- 효과: M-8 NOT_QUALIFIED의 근인(분할 격리 부재·불완전본)이 해소 — W4 재측정 대상.

## ArchCAD 40k 공개본 — 완료·검증됨 (전체 400K 아님)
- 경로: `D:\datasets\ArchCAD_hf_full\data\{png,json,svg,point,caption}.zip`
- 출처: HF jackluoluo/ArchCAD (gated=manual, Paul 약관 동의 2026-07-20). 인증=paulparkhere.
- 규모: png 1.74GB + json 375MB + svg 297MB + point 77MB + caption 19MB = **2.45GB** (5 모달).
- 정직 경계: README가 명시적 **"40k Samples" 공개 부분집합**. 논문 전체 **ArchCAD-400K**(41만
  청크)는 별도. 벽 = semantic ID 20. 라이선스 cc-by-nc-4.0.
- 전체 400K 조달 = 별도 조사(archcad_full_recon 셀, sol high) 진행 중.

## Zenodo10K — 조달 안 함 (Paul 확정)
- 242GB PPTX(프레젠테이션), 벽 탐지 무관. 스킵.

## 미해소 결재 항목
- ArchCAD 전체 400K: OpenReview/저자 배포 경로 조사 중 → 결과 나오면 Paul 결재.
- CubiCasa 라이선스 출처 불일치(Zenodo CC BY-NC-SA vs GitHub CC BY-NC): 연구 단계 무영향,
  제품 탑재 시 확정 필요.
