# PATCH_BATCHING_DESIGN_BRIEF — staged-write 파이프라인 native 실행 배칭

Status: DRAFT (설계 브리프, 미구현) · 작성일 2026-07-08

## 1. 문제 정의 · 실측 근거

`tools/patch_engine.py`의 `apply_staged`는 op 목록(`applied_records`)을 순차 loop로
돌며, **op 1개당 accoreconsole(native AutoCAD 코어) 프로세스를 1회 기동**한다.

```
for n, op_record in enumerate(applied_records):
    apply_dir = out_dir/apply/op_%02d
    job_path  = apply_dir/cad_job.json          # op 1개짜리 job doc
    run_job.run_router_cad_job(current_input, apply_dir, op_record["native_op"],
                                write_mode="write_copy", job_path=job_path)
```

각 iteration은 별도 `run_router_cad_job` 호출 → 별도 accoreconsole 기동 → 별도
`staged_step.dwg` 산출로 이어진다. 이 구조의 증거는 실제 run 산출물의
`apply/op_NN/` 서브디렉토리 나열 자체다 — op 개수만큼 독립된 job/log 폴더가
생긴다. pre/post-inspect(`inspect.database.graph`)도 각각 별도 기동이므로,
op N개짜리 패치는 최소 N+2회의 native 프로세스 launch를 발생시킨다.

**실측 비용 (2개 데이터 포인트):**

| 런 | ops | wall-clock | s/op |
|---|---|---|---|
| 2026-07-06 native_sample capstone | 14 | 181 s | 12.9 |
| 2026-07-08 1.dwg R1a | 9 | 129.4 s | 14.4 |

두 런의 s/op가 서로 다른 규모(14 vs 9 ops)에서도 12.9~14.4 s/op 범위로 수렴한다는
점은, 비용이 "op 내부에서 무엇을 하는가"보다 "프로세스를 몇 번 기동하는가"에 더
크게 좌우된다는 정황이다 (확정적 프로파일링은 아님 — §4 참조).

**결과 — 확장 불가능성이 실제로 발현한 사례:** 1.dwg의 거대 블록 정의
"X-평면도(기본형)"(폐쇄, 20,567개 def 엔티티)를 기존 per-op 구조로 그대로
처리하면 13 s/op 가정 시 약 74시간이 소요된다 (20,567 × 13 s ≈ 267,000 s ≈
74.3 h). 이는 한 세션·한 배치 작업으로 감당 불가능한 규모다. 오늘 런
(`runs/e2e_1dwg_R1b2_20260708`)은 이 블록을 실제로 처리한 것이 아니라
`--max-def-entities-per-block` 예산으로 **정직하게 유예**했다 — 즉 현재 구조는
이 규모의 블록 정의에 대해 fail-loud 회피(조용한 축소)가 아니라 명시적 미처리로
대응했을 뿐, 근본 해소는 아직 없다.

## 2. 요구사항

- **R1 (집약)**: 한 native job(accoreconsole 프로세스 1회 기동)에 N개 op의 명령
  스크립트를 집약해 실행한다. launch당 op 수를 늘려 launch 횟수를 줄이는 것이
  목표지 op 자체의 native 처리 로직을 바꾸는 것이 아니다.
- **R2 (블록 정의 원자성)**: `create_block` + 그 블록에 대한 append 계열 op는
  하나의 원자 그룹으로 유지한다. 배치 경계가 이 그룹 중간을 자르면 안 된다 —
  block table record 생성과 엔티티 append는 같은 배치, 같은 순서로 실행되어야
  한다.
- **R3 (per-op 개별 보고 유지)**: 배치가 프로세스 1개로 실행되더라도, 현재
  `journal.json`의 `apply[n]` 레벨 pass/fail 레코드는 그대로 보존한다. "배치가
  성공했다"는 하나의 신호로 N개 op 결과를 뭉뚱그리면 안 된다 (§5의 판정 방법
  이슈와 직결).
- **R4 (안전 불변식 무변경)**: staged-only(원본 `dwg_path`는 절대 열리지 않거나,
  열리더라도 write 없이 read 전용), 원본 sha256 before/after 동일성 검증,
  사후 native_full IR 재추출 기반 diff(`cad_diff.v1`) — 이 세 가지는 배칭 도입
  전후로 동일해야 한다. 배칭은 실행 방식의 변경이지 검증 계약의 변경이 아니다.
- **R5 (fail-loud)**: 배치 내부 op 하나가 실패했을 때 나머지를 조용히 계속
  진행하거나, 배치 전체를 성공으로 보고하는 것을 금지한다. no-fake-success
  원칙(`apply_staged` 기존 docstring의 truthful statuses 계약)은 배치 단위가
  아니라 op 단위로 계속 적용되어야 한다.

## 3. 인터페이스 스케치

배치 계획 자체는 이 브리프의 스코프가 아니다 — 별도 패킷이
`tools/patch_batch_planner.py`를 만들어 `ariadne.patch_batch_plan.v1` 산출물을
낸다고 가정한다:

```
{
  "schema": "ariadne.patch_batch_plan.v1",
  "batches": [{"batch_id": "...", "op_indices": [0,1,2, ...]}],
  "atomic_groups": [[3,4,5]],       # create_block+append처럼 분리 불가한 op 묶음
  "oversized": [{"op_index": 7, "reason": "..."}]  # 예산 초과 → 개별/유예 처리
}
```

이 브리프가 다루는 것은 `apply_staged`(또는 신규 `apply_staged_batched`)가 이
plan을 **소비하는 쪽**의 구도다:

- 배치 1개 = `run_router_cad_job` 호출 1회 = accoreconsole 기동 1회. 현재
  op 1개당 만들던 `cad_job.json` + 개별 스크립트 대신, 배치 1개당 job doc 1개 +
  스크립트 1개를 만든다. 스크립트 내부에서 `op_indices` 순서대로 명령을 이어
  붙인다 (원자 그룹은 스크립트 내에서 인접·순서 보장).
- 현재 loop의 `current_input` 체이닝(이전 op의 mutated 결과를 다음 op 입력으로)
  은 배치 내부에서는 파일 체이닝이 아니라 **같은 프로세스 내 순차 명령 실행**으로
  대체된다 — 배치 경계에서만 파일(`staged_step.dwg` 상당)을 끊어 다음 배치로
  넘긴다.
- **배치 내부 per-op 결과 회수**: 스크립트가 각 op 실행 직전/직후 표준출력에
  마커를 프린트한다(예: `OP_START:03`, `OP_END:03:OK` / `OP_END:03:FAIL:<reason>`).
  배치 실행 후 stdout을 마커 기준으로 split해, 현재 `_step("apply[%d]", ...)`가
  만들던 것과 동일한 형태의 op별 journal 레코드로 재구성한다. 즉 "배치"는 실행
  단위일 뿐 보고 단위는 여전히 op다 (R3).

## 4. 예상 효과 (추정 — 확정 아님)

s/op(12.9~14.4)의 대부분이 프로세스 launch(코어 기동·라이선스·템플릿 로드·
시스템 변수 세팅)이고 op 내부 처리 시간이 그에 비해 작다는 **가정**을 세우면,
20,567 ops를 100-op 배치로 묶었을 때 launch 횟수는 20,567회 → 약 206회로
줄어든다. launch 오버헤드 성분만 놓고 보면 이론상 74h 규모가 launch 비용
기준으로는 수십 분대(206 × ~13s ≈ 45분)까지 줄어들 여지가 있다는 뜻이다.

**단, 이 계산은 "op 내부 처리 시간 ≈ 0"이라는 가장 낙관적인 상한 가정 위에
있으며, 스크립트 내부에서 op가 실제로 얼마나 걸리는지는 아직 실측된 바 없다.**
100-op 배치가 실제로 어느 정도 시간이 걸릴지, 또 op 개수가 커질 때 배치 내부
누적 비용(엔티티 append, DB flush 등)이 선형인지 비선형인지는 §6의 파일럿
실측 전까지 미지수다. 이 문서는 어떤 확정 숫자도 성능 목표로 단정하지 않는다.

## 5. 리스크 · 오픈이슈

- **배치 중간 실패의 롤백/재개 의미론**: 배치의 op 50/100에서 실패하면, 이미
  적용된 1~49의 결과를 살려 51부터 재개할지, 배치 전체를 처음부터 재시도할지가
  정해져 있지 않다. `patch_batch_plan.v1`에 배치 단위 재개(resume) 정보가
  없다면, 부분 실패 시 어디서부터 다시 시작해야 안전한지 판단할 근거가 없다.
- **QSAVE 타이밍**: 현재는 op마다 프로세스가 끝나면서(write_copy 모드) 저장이
  일어난다. 배치화하면 프로세스가 여러 op에 걸쳐 살아있는 동안 QSAVE를 언제
  할지(원자 그룹 경계마다? 배치 끝에 1회만?) 정해야 한다. 매 그룹마다 저장하면
  launch 오버헤드는 줄어도 저장 오버헤드가 그대로 남을 수 있고, 배치 끝에
  1회만 저장하면 중간 실패 시 그 배치 전체를 잃는다 — 트레이드오프가 실측
  전까지 미확정.
- **에코 파싱 신뢰도(CMDECHO)**: op 경계를 표준출력 마커로 구분하는 방식은
  AutoCAD 커맨드라인 echo 설정(CMDECHO)과 명령 실패 시의 프롬프트/에러 다이얼로그
  출력 포맷에 의존한다. 명령이 실패해 예상 밖 프롬프트나 대화상자성 텍스트가
  섞여 나오면 마커 split이 깨질 수 있다 — 파싱 신뢰도를 사전에 검증해야 한다.
- **배치에서도 per-op 성공 판정을 개별 유지하는 방법**: 현재는 프로세스
  exit code + `staged_used` 파일 존재 여부로 op 성공/실패를 판정한다
  (`apply_run.get("exit_code")`). 배치에서는 exit code가 배치 전체에 대해
  1개뿐이므로, op 단위 판정은 오직 echo 마커 + 스크립트 내부에 삽입한 상태
  확인 명령(예: 엔티티 카운트 조회)에만 의존하게 된다. 이 판정 경로가 현재
  아키텍처가 요구하는 "op 단위 truthful status" 신뢰도에 못 미칠 위험이 있다.

## 6. 검증 계획

1. **동등성 재현**: 배칭 구현 후, 기존 R1b(비-배치, 9 ops) 런과 동일한 patch를
   배치 엔진으로 재실행한다. 결과 `staged_output.dwg`를 native_full IR로
   재추출해, 비-배치 R1b 결과와 `cad_diff.v1` 기준 엔티티 레벨 diff가 동일함을
   확인한다. 원본 `dwg_path`의 sha256 before/after 불변 검증은 그대로 유지한다.
   diff가 하나라도 다르면 배칭은 채택 불가.
2. **소규모 실측**: 10-op 배치로 먼저 실행해 실제 wall-clock을 측정하고, 기존
   9~14 s/op 기준선과 비교해 launch 횟수 감소분이 실제로 어느 정도 시간을
   절약하는지 재산출한다. §4의 낙관적 상한 가정을 이 실측치로 교체한다.
3. **확대**: 10-op 파일럿이 diff 동일성 + 실측 절감을 모두 통과하면 100-op
   규모로 확대하고, 그 시점에 20,567-entity 블록에 대해 실제 재실행을 시도해
   `--max-def-entities-per-block` 유예를 대체할 수 있는지 판단한다. 대체
   불가로 판명되면 그 사실 그대로 보고한다 — 배칭이 만능 해법이라는 가정은
   여기서도 없다.
