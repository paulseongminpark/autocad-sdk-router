# ADN 기술지원 케이스 초안 2건 (2026-07-24)

> ADN 멤버십의 무제한 1:1 API 지원 채널에 제출할 케이스. Paul이 ADN 포털에서 제출.

## Case 1 — accoreconsole QUIT hang (batched write session)

- **Title**: AutoCAD Core Console 2027 hangs on QUIT after scripted ObjectARX batch job (workaround: timeout kill)
- **Product/Version**: AutoCAD 2027 Core Console (accoreconsole.exe), ObjectARX 2027 (.dbx/.crx custom modules)
- **Body (영문 초안)**:
  > We run headless write jobs against staged DWG copies: an ASCII .scr loads
  > our .dbx/.crx modules, runs a custom command per job entry, issues _QSAVE,
  > then QUIT. Intermittently the process completes all work (all per-op result
  > files written, QSAVE persisted, sha256 of the DWG changes as expected) but
  > never exits on QUIT — we currently kill it on a timeout and treat the
  > presence of a qsave_done marker as the success signal.
  > Questions: (1) Is there a known issue with QUIT after heavy AcDb
  > transactions in Core Console 2027? (2) Is there a recommended clean-exit
  > sequence for scripted batch sessions (e.g. flags, _.QUIT variants,
  > acedPostQuit-equivalents usable from a .crx)? (3) Is the timeout-kill
  > pattern after verified QSAVE safe with respect to database integrity?
- **재현 자료**: tools/autocad-router.ps1 `run-native-write-batch` 액션 + 잡 파일 스켈레톤 (수령 시 첨부)

## Case 2 — DXF import rejection ErrorStatus=53: ELLIPSE major_axis orthogonality tolerance

- **Title**: What exact orthogonality/normalization rule does AutoCAD enforce between ELLIPSE major axis (code 11) and extrusion (code 210) at DXF import? (eNotApplicable/53 rejects whole file)
- **Product/Version**: AutoCAD 2027 (DXF import), files pass ezdxf audit
- **Body (영문 초안)**:
  > DXF files whose ELLIPSE major_axis has a tiny out-of-plane component
  > relative to the extrusion direction (dot product ≈ 2.6e-8 from float
  > round-trip noise) are rejected wholesale by AutoCAD at import with
  > ErrorStatus=53, while third-party validators accept them.
  > Questions: (1) What is the documented tolerance/validation rule for
  > major-axis vs extrusion orthogonality (and normal unit-length) on
  > AcDbEllipse::set / DXF filing? (2) Is rejection of the ENTIRE file (vs
  > the single entity) intended behavior? (3) Recommended canonical
  > normalization for writers (we now project major_axis onto the plane of the
  > recorded extrusion and preserve mirror (negative-Z) normals — is sign
  > preservation of the normal the correct convention?)
- **참조**: repo 이슈 #46 (재현 수치 포함), 646/648 왕복 검증 데이터
