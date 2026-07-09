# XDATA & 테이블 커버리지 보완 실행 계획 (SECTION_COVERAGE_R3b 기준)

목표: `reports/interior100/section_coverage_R3b.json` 기준으로 `xdata`/`app_ids`/`dim_styles`/`block_table_records`/`xrecords`/`extension_dictionaries` 갭을 최소 변경으로 100%에 가깝게 복구한다.

## 0. 현재 수치
- xdata: 64 → 0
- symbol_tables.layers: 91 → 66
- symbol_tables.app_ids: 25 → 7
- symbol_tables.dim_styles: 6 → 2
- symbol_tables.block_table_records: 410 → 251
- xrecords: 2 → 1
- extension_dictionaries: 1 → 0
- 전체 weighted: 67.84%

## 1. 병목 정합성 근거
- `tools/full_roundtrip_capstone.py`의 `run_records_batch()`는 `RECORD_TABLE_CLASSES`가 layer, dimstyle, linetype, textstyle, ucs, view, vport로 고정되어 있어 다른 테이블/DB 메타가 아예 생성되지 않는다.
- `run_regen_batch()`는 `ir_to_patch.build_patch_from_ir()`로 엔티티 중심 패치만 만들며, dict/xrecord/appid/xrecord-like 메타가 분리 emit 되지 않는다.
- `tools/patch_ops/tables.py`는 위 7개 테이블 CREATE 외에는 거의 없음.
- `tools/patch_ops/db.py`는 현재 `WRITE_OP_MAP`가 비어 있어 데이터베이스 메타 write lane을 확장할 경로가 없다.
- 네이티브 레지스트리 기준으로는 `write.xdata.set`, `write.xrecord.set`, `write.dictionary.set`, `write.regapp.register`가 존재하지만, 현재 런너에서 호출되지 않는다.

## 2. 갭별 분석

### A. xdata (64 → 0)
- Why drop: 엔티티 IR 패치 생성 시 `set_entity_xdata_by_handle` 같은 emission이 없음. 레지스트리 앱도 선행 emit 안 됨.
- 최소 op: `write.xdata.set` + `write.regapp.register`
- op args: `entity_handle`, `regapp`, `xdata_payload`, (필요 시 `merge_mode`)
- Native API: 엔티티 핸들 기준 XData 채움 경로 (native xdata set binding)
- Verify: `section_coverage_R3b.json`의 `xdata.entities`가 0→64
- Risk: 동일 엔티티 다중 xdata 병합 충돌, 핸들 미일치, regapp 미등록 시 실패
- T-shirt: M

### B. symbol_tables.layers (91 → 66)
- Why drop: `write.layer.create`는 존재하지만 생성군/갱신군 혼합 처리에서 일부 레이어가 생략되는 패턴 존재.
- 최소 op: `write.layer.create`
- op args: 레이어 기본 속성/색/lineweight/ltype/plot 여부 등 기존 write 스키마 그대로
- Native API: `createLayer` 계열
- Verify: `section_coverage_R3b.json`의 `symbol_tables.layers`가 66→91
- Risk: 기존 도면의 보호 레이어, 잠금/숨김 속성의 overwrite 충돌
- T-shirt: S

### C. symbol_tables.app_ids (25 → 7)
- Why drop: regapp/register lane가 pipeline에 emit되지 않으며 db 레지스터 패스도 비어 있음.
- 최소 op: `write.regapp.register`
- op args: `name`
- Native API: regapp 등록 API(문자열 등록/조회)
- Verify: `section_coverage_R3b.json`의 `symbol_tables.app_ids`가 7→25
- Risk: 중복 등록 처리 미구현 시 충돌, 생성 순서 미준수 시 xdata 경로 실패
- T-shirt: S

### D. symbol_tables.dim_styles (6 → 2)
- Why drop: dimstyle은 기존에 target lane이 있으나 degenerate 처리 및 업서트 조건 미충분으로 일부 재생성되지 않음.
- 최소 op: `write.dimstyle.create`
- 보강 op: `modify.dimstyle.properties`(선택)
- Native API: `upsertDimStyleRecord`
- Verify: `section_coverage_R3b.json`의 `symbol_tables.dim_styles`가 2→6
- Risk: 기존 기본 dimstyle과 속성 충돌, 덮어쓰기 정책 차이
- T-shirt: M

### E. symbol_tables.block_table_records (410 → 251)
- Why drop: block table record가 block 엔티티 생성 루트와 분리되어 있으며 `RECORD_TABLE_CLASSES`에 해당 클래스 토큰이 없음.
- 최소 op: 기존 `write.block.simple_create`로 즉시 대체 불가한 갭 존재
- 최소 신설 op: `write.block_table_record.create`
- op args: `name`, `xref`, `is_layout`, `flags`, `units`, `origin`, `path_name`
- Native API: BlockTable에 대한 레코드 추가 (`BlockTable.Add(...)`) 후 후속 속성 업서트
- Verify: `section_coverage_R3b.json`의 `symbol_tables.block_table_records`가 251→410
- Risk: xref 중복, layout/anonymous 블록 충돌, 트랜잭션·락 경합
- T-shirt: L

### F. xrecords (2 → 1)
- Why drop: `write.xrecord.set`는 정의되어 있으나 dictionary/owner 체인 emit이 없어 호출되지 않음.
- 최소 op: `write.xrecord.set`
- op args: `owner_handle`, `xrecord_name`, `payload`, `overwrite`
- Native API: Xrecord 객체 생성/삽입 API
- Verify: `section_coverage_R3b.json`의 `xrecords`가 1→2
- Risk: owner/dictionary 핸들 미존재, 이름 충돌, 순서 역전
- T-shirt: M

### G. extension_dictionaries (1 → 0)
- Why drop: extension dictionary 생성 op는 존재하지만 호출 경로가 없어 대상 객체에 연결되지 않음.
- 최소 op: `write.dictionary.set`
- op args: `owner_handle`, `dictionary_name`, `entries`, `is_extension=true`
- Native API: 객체 extension dictionary 생성/바인딩 API
- Verify: `section_coverage_R3b.json`의 `extension_dictionaries`가 0→1
- Risk: 비확장 객체에 대한 호출, 확장 dict 중복 키 충돌
- T-shirt: S

## 3. 실행 의존성 래더
1. layers 보강
2. dim_styles 보강
3. app_ids 등록
4. block_table_records 생성
5. extension_dictionary 생성
6. xrecords 채움
7. xdata 채움

## 4. 최소 구현 순서
1. `tools/full_roundtrip_capstone.py`의 `RECORD_TABLE_CLASSES`에 xdata/app_ids/block_table_records/dictionary/xrecord/ 관련 토큰 반영(혹은 별도 배치 lane 추가)
2. `tools/patch_ops/db.py`에 `WRITE_OP_MAP` 확장: `write.regapp.register`, `write.dictionary.set`, `write.xrecord.set`, `write.xdata.set` 라우팅 정합성 확보
3. `tools/ir_to_patch.py`에서 엔티티->테이블/딕셔너리/xrecord/xdata emit 경로 확장
4. `write.block_table_record.create`는 새 op로 추가 필요 시 `operations.v2.json` + alias + native 래퍼 등록
5. `SECTION_COVERAGE_R3b.json` 재측정 후 갭별 목표치 확인

## 5. 검증 기준
- `xdata`: 0 → 64, 키: `xdata.entities`
- `symbol_tables.layers`: 66 → 91, 키: `symbol_tables.layers`
- `symbol_tables.app_ids`: 7 → 25, 키: `symbol_tables.app_ids`
- `symbol_tables.dim_styles`: 2 → 6, 키: `symbol_tables.dim_styles`
- `symbol_tables.block_table_records`: 251 → 410, 키: `symbol_tables.block_table_records`
- `xrecords`: 1 → 2, 키: `xrecords`
- `extension_dictionaries`: 0 → 1, 키: `extension_dictionaries`

## 6. 최종 갭 표

| gap | current | target | op | cost | verify |
| --- | --- | --- | --- | --- | --- |
| xdata | 0 / 64 | 64 / 64 | write.xdata.set + write.regapp.register | M | `xdata.entities` |
| symbol_tables.layers | 66 / 91 | 91 / 91 | write.layer.create | S | `symbol_tables.layers` |
| symbol_tables.app_ids | 7 / 25 | 25 / 25 | write.regapp.register | S | `symbol_tables.app_ids` |
| symbol_tables.dim_styles | 2 / 6 | 6 / 6 | write.dimstyle.create | M | `symbol_tables.dim_styles` |
| symbol_tables.block_table_records | 251 / 410 | 410 / 410 | write.block_table_record.create (신규) | L | `symbol_tables.block_table_records` |
| xrecords | 1 / 2 | 2 / 2 | write.xrecord.set | M | `xrecords` |
| extension_dictionaries | 0 / 1 | 1 / 1 | write.dictionary.set | S | `extension_dictionaries` |

## 7. P4a extraction emission schema
- `inspect.database.graph` entity records emit `xdata` only when `entity->xData(nullptr)` returns non-null; null xdata is omitted and empty arrays are not emitted.
- Shape: `"xdata":[{"app":"REGAPP","rows":[{"code":1000,"value":"text"},{"code":1005,"value":"ABCD"},{"code":1040,"value":1.25},{"code":1010,"value":[1,2,3]}]}]`
- Group code `1001` starts a new app group and supplies `app`; it is not repeated as a row.
- String codes, including `1005` handles, emit UTF-8 JSON strings. `1005` values are extracted verbatim; handle remap belongs to the following write packet.
- Real and integer codes emit JSON numbers. Point codes emit `[x,y,z]` arrays.

## 8. P4b replay design log
- Python replay is opt-in only: `ir_to_patch.build_patch_from_ir(..., include_xdata=True)` appends a Pass B stream after all entity/block creation ops. The default remains off so the current capstone packet is unchanged until the orchestrator enables it after native verification.
- Pass B emits all `write.regapp.register` ops first, deduped by app name in first-seen order, then emits `modify.entity.xdata` ops for replayable entity/app groups.
- The xdata builder is handle-map driven. Entity targets and 1005 soft-pointer rows use `handle_map`; dangling 1005 rows are deferred and dropped, never written with verbatim old handles.
- 1002 control rows are retained only after app-local brace balance validation. An unbalanced app group is deferred as `unbalanced 1002 braces`.
- 1004 rows are deferred as `binary xdata excluded by design`. Long string rows over 255 characters are deferred; the total 16KB entity xdata limit is left to native `setXData` loud failure with no Python truncation.
- Honest native caveat: current `modify.entity.xdata` still excludes 1002 and 1004 in its native handler. This Python stage prepares validated 1002 replay, but full 1002 persistence needs a native follow-up before the orchestrator should enable full-fidelity xdata replay.
