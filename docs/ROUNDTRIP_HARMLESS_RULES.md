# Roundtrip 무해/유해 규칙 거버넌스

`tools/roundtrip_report.py` 는 DWG 왕복(round-trip) diff에서 나타나는 각 diff 패턴을
`harmless` / `harmful` / `unreviewed` 셋 중 하나로 판정한다. 이 문서는 그 판정 규칙을
데이터로 분리 관리하는 이유와 절차를 정의한다. 레지스트리 파일:
`config/roundtrip_harmless_rules.json`.

## 1. 왜 규칙이 데이터인가

ALM(Ariadne Lexicon Model) 관점에서 "이 diff 패턴은 무해하다"는 판단은 **코드가 아니라
입법(legislate)된 사실**이다. 코드는 판단 로직(매칭·집계)만 갖고, 무엇을 무해로 볼지는
별도 JSON 레지스트리가 규정한다. 근거:

- **profile 분리 원칙**: 같은 리포트 엔진이라도 프로젝트/도면군마다 "허용 가능한 drift"의
  기준이 다를 수 있다 (예: 이 프로젝트는 POLYLINE→LWPOLYLINE 재생성을 무해로 보지만,
  다른 프로젝트는 폭(width) 속성 손실을 이유로 유해로 볼 수 있다). 규칙을 코드에 하드코딩하면
  프로젝트마다 스크립트를 fork해야 한다 — 데이터로 분리하면 `--harmless-rules <json>` 플래그
  하나로 profile을 교체한다.
- **감사 가능성**: 규칙이 데이터이면 git diff로 "언제 누가 무엇을 무해로 재분류했는가"를
  그대로 추적할 수 있다. 코드 로직에 파묻힌 판단은 코드 리뷰 없이는 드러나지 않는다.
- **사람의 비준(ratification)이 코드 리뷰가 아니라 데이터 리뷰가 되게 한다**: 규칙 승격은
  PR로 코드를 고치는 행위가 아니라, evidence run을 확인하고 JSON 필드 몇 개를 채우는 행위다
  (§3 참조). 이 분리가 없으면 "무해 판정"과 "판정 로직 변경"이 뒤섞여 리뷰 부담이 커진다.

`tools/roundtrip_report.py`의 `HARMLESS_RULES` 상수는 이 레지스트리의 **내장 기본값**이다.
`--harmless-rules` 로 넘긴 JSON은 `id` 기준으로 기본값을 오버라이드/병합한다
(`_normalize_rules` 참조) — 즉 레지스트리 파일이 코드보다 우선한다.

## 2. 규칙 스키마 필드

`config/roundtrip_harmless_rules.json` 은 규칙 객체의 JSON 배열이다. 필드:

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `id` | string | 예 | 규칙 식별자. 리포트의 `pattern.rule_id` 에 그대로 기록된다. |
| `match` | string | 아니오 | deferred 패턴의 reason 컨텍스트(`_context_from_reason`)에 대한 부분 문자열 매칭. 소문자 비교. |
| `judgment` | string | 아니오 | 이 규칙이 확정하는 판정값. 현재 `harmful` 만 명시적으로 쓰인다 — `harmless`는 POLYLINE/LWPOLYLINE 페어링처럼 코드 내 별도 로직으로 결정되고, 규칙은 그 note만 공급한다. |
| `note` | string | 예 | 리포트 Markdown/JSON에 노출되는 사람이 읽는 설명. |
| `status` | string | 예 | `candidate` \| `ratified`. §3 참조. |
| `ratified_by` | string\|null | 예 | 비준한 사람. 비준 전에는 `null`. |
| `ratified_at` | string\|null | 예 | 비준 시각(ISO 8601). 비준 전에는 `null`. |
| `evidence` | string[] | 예 | 이 규칙을 뒷받침하는 산출 run 디렉토리 경로 목록 (FM9 대응, §4). |

`status`/`ratified_by`/`ratified_at`/`evidence` 는 `roundtrip_report.py`의 판정 로직이
읽지 않는 **거버넌스 부가 필드**다 — 스크립트 동작에는 영향이 없고, 사람과 감사자를 위한
메타데이터다.

## 3. 비준 절차

- 새 규칙 또는 새 발견은 항상 `status: "candidate"` 로 시작한다.
- candidate 규칙이 만든 무해 판정은 리포트에 그 규칙의 `note` 그대로 노출되며,
  현재 두 내장 규칙의 note는 `"... candidate harmless pending human ratification"` 문구를
  포함해 candidate 상태를 리포트 소비자에게도 드러낸다.
- **에이전트는 candidate 추가까지만 한다.** `status`를 `ratified`로 올리는 행위,
  `ratified_by`/`ratified_at`을 채우는 행위는 **사람(Paul)만** 수행한다.
- Paul이 evidence run을 열어 diff 패턴이 실제로 무해함을 확인한 뒤, 해당 규칙 객체에
  `status: "ratified"`, `ratified_by: "<이름>"`, `ratified_at: "<날짜>"` 를 기입한다.
- `R_DEFERRED_BLOCK_DEF` 는 `judgment: "harmful"`로 구성 자체가 유해 확정이다 — 그럼에도
  레지스트리 거버넌스는 동일하게 적용되며 비준 전까지는 `status: "candidate"`로 남는다
  (비준은 "무해로 인정"이 아니라 "이 규칙이 계속 유효함을 확인"이라는 의미로도 쓰인다).

## 4. 새 규칙 추가 방법과 증거 의무

1. 최소 하나의 실제 run(measure 또는 e2e 산출물)에서 반복되는 diff 패턴을 관찰한다.
2. `config/roundtrip_harmless_rules.json` 에 새 객체를 추가한다 — `id`는
   `R_` 접두사 + 스크린 가능한 이름, `note`에는 왜 이 패턴이 (무)해한지 근거를 서술.
3. **`evidence` 배열에 그 패턴을 만든 run 디렉토리 경로를 반드시 병기한다.** 경로 없는
   수치·판정 주장은 FM9(출처 없는 수치)에 해당한다 — "측정했다"는 주장은 그것을 낳은
   run 디렉토리를 인용할 수 있어야 유효하다.
4. `status: "candidate"`, `ratified_by: null`, `ratified_at: null` 로 시작한다.
5. Paul에게 비준을 요청하거나, 다음 세션에서 스스로 검토하도록 남겨둔다.

## 5. 사용법

```powershell
python tools/roundtrip_report.py `
  --run-dir <run_dir> `
  --out-json <run_dir>/roundtrip_report.json `
  --out-md <run_dir>/roundtrip_report.md `
  --harmless-rules config/roundtrip_harmless_rules.json
```

- `--run-dir`: `census_report.json` / `verdict.json` / `deferred.json` / `summary.json` 등을
  담은 capstone/e2e run 디렉토리.
- `--harmless-rules`: 이 문서가 다루는 레지스트리 파일. 생략하면 스크립트 내장
  `HARMLESS_RULES` 만 적용된다.
- `--strict`: 리포트에 `harmful` 패턴이 하나라도 있으면 exit code 3으로 종료 (CI 게이트용).

레지스트리를 프로젝트별로 분기하고 싶다면 `config/roundtrip_harmless_rules.json` 을 복제해
별도 profile 파일로 관리하고, 호출 시 그 경로를 `--harmless-rules` 로 넘긴다 — 스크립트
수정은 필요 없다.
