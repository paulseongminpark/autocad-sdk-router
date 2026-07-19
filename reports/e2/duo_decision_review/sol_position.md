# sol 독립 포지션 — L1 결재안(A/B/C/D) 적대 재설계

- 작성 좌석: OpenAI `sol`
- 작성일: 2026-07-19 (Asia/Seoul)
- 판정 대상: `reports/e2/chainverify_L1f/PAUL_DECISION_L1_LOOP.md`
- 실행 경계: 보고·코드·기존 산출물 READ-ONLY, Git 0회, 서브에이전트 0회. 유일한 쓰기는 본 파일이다.

## 0. 독립 결론

**결재안은 현재 문안 그대로는 기각한다. 권고 A를 구현 승인안으로 채택하지 말라.** A의 방향—post 표면
복사가 아닌 독립적 구성 증거—는 옳지만, 현재 코드에는 그 의미의 구성적 증인이 없고, 결재안의
“수리 1~2회” 비용은 근거가 없다. A는 완성된 설계안이 아니라 아직 검증해야 할 연구 가설이다.

**독립 권고는 누락된 E안이다.**

> **E — 즉시 격리(C의 안전조치) + 사전 봉인된 A0 타당성 게이트.** 지금 L1을 자기인증 계측기에서
> 참고 신호로 강등하고 C2를 닫아 둔다. 별도 A0에서 정직 생성 문법·독립 membership/certificate·
> abstain 규칙을 먼저 설계하고, 다섯 함대 반례를 통과할 때만 새 자격 심사로 간다. 실패하거나
> 비용이 예상보다 커지면 C 상태를 유지한다. 이것은 중단선을 어기는 L1g 점수리가 아니다.

A/B/C/D 중 하나만 지금 강제로 고르라면 **C**가 맞다. A는 “승인”이 아니라 E 안의 제한된 A0
실험으로만 허용한다. B는 목표를 바꾸면서도 현존 GRID gate 위반을 해결하지 못하고, D는 성문화된
중단선을 정면으로 위반한다.

## 1. 근거 범위와 독립 실행

필수 입력인 L1f 폴더 12개 파일 전부와 L1e `SYNTHESIS.md`를 읽었다. 다섯 함대의 실제 결함 배열을
확인하기 위해 L1b/L1c/L1d `SYNTHESIS.md`도 추가로 읽었다. 핵심 원문 근거는 다음과 같다.

- 5차 종합 결함 지도와 상신 논리: `reports/e2/chainverify_L1f/SYNTHESIS.md:L25-L67`
- A/B/C/D 문안과 A 비용 주장: `reports/e2/chainverify_L1f/PAUL_DECISION_L1_LOOP.md:L55-L81`
- 독립성 위조·증인 항진·모집단 마스킹: `reports/e2/chainverify_L1f/lens1_verdict.md:L55-L148`
- GRID neutrality 회귀와 44건의 수치-Tier 판별: `reports/e2/chainverify_L1f/lens2_verdict.md:L108-L164`, `L168-L250`
- 타입 심판 공백·44건의 증인-축 판별·90건 post 투영: `reports/e2/chainverify_L1f/seat4_verdict.md:L39-L58`, `L73-L164`
- 장부·해시·replay의 수치 무결: `reports/e2/chainverify_L1f/lens3_verdict.md:L30-L105`
- 1~4차 결함의 실제 종합: `reports/e2/chainverify_L1b/SYNTHESIS.md:L16-L34`,
  `chainverify_L1c/SYNTHESIS.md:L17-L54`, `chainverify_L1d/SYNTHESIS.md:L14-L57`,
  `chainverify_L1e/SYNTHESIS.md:L16-L47`

비쓰기 실행 결과:

| 실행 | 결과 | 무엇을 증명하는가 |
|---|---:|---|
| `python feyerabend_c1_v5.py --selftest` | 관측 5/5 `true` | 현재 자기시험은 재실행 가능. 구성적 증인의 독립성은 시험하지 않음 (`feyerabend_c1_v5.py:L1170-L1257`). |
| `python loop_l1f.py --verify-only` | exit 0; 13파일, 400 replay 장면, 15/15 술어 | 현존 산출물의 형식·공표 수치는 읽기 전용으로 검증 가능 (`loop_l1f.py:L1624-L1676`). |
| `python loop_l1f.py --compute-only` | exit 0, **18.083초** | 현재 실험 전체 계산은 이 머신에서 재실행 가능. 출력은 쓰지 않았음 (`loop_l1f.py:L1679-L1698`). |
| in-memory 타입/중복 프로브 | 아래 2개 반례 재현 | 현재 witness가 독립 생성기가 아님을 코드와 실행 양쪽에서 확인. |

`--compute-only`가 재구성한 주요 수치는 641 property, 55 non-dilution 행, P5 2,000 부모/50 기존
위반/44 v5 상승, replay 400장면/218,469행/zero-delta 32,538행, witness 90건/violation 0이었다.
명령 stdout과 `lens3_verdict.md:L30-L105`가 일치한다. 이 일치는 **현재 하니스의 재현성**이지 현재
분류 의미의 타당성 증명이 아니다.

독립 in-memory 프로브의 관측값은 다음과 같다.

1. `text_height={"invalid":"non_numeric"}`를 3개 clean anchor 중 하나에 넣어도
   `tier_B=0`, `declared_field_type_and_presence=0`, witness accepted=`true`, witness==post=`true`였다.
2. 두 clean handle 중 하나를 새 handle로 복제하고 두 레코드에 같은 `source_span_id="SHARED"`를
   주면 `n_independent 2→3`, `unit_status LOW→HIGH`, `tier_B=0`, witness accepted=`true`였다.

재현 논리는 `exact_fixture()`에서 anchor를 복사해 위 두 필드만 바꾼 뒤
`suspicion_analysis`, `fit_anchor_model`, `build_honest_witness`를 호출하는 것이다. 같은 수치는
`seat4_verdict.md:L88-L101` 및 `lens1_verdict.md:L55-L116`의 더 큰 탐색과 교차 일치한다.

## 2. A안의 코드 수준 실현 가능성

### 2.1 현재 코드에서 가능한 것과 불가능한 것

현재 run-local 코드와 repo 코드는 byte-identical이다.

- `feyerabend_c1_v5.py`: 1,273행, SHA-256
  `6D1D0AA113AF1045EAA54FE0504032B86AA217251BCDF5454E61CA184164C489`
- `loop_l1f.py`: 1,702행, SHA-256
  `461B03EDE7B112DCF32AD2FF5043C88FF307DFCC90F5FFA5C35DCDD2238563C2`

근거 명령은 각 run/repo 경로에 대한 `Get-FileHash -Algorithm SHA256`과 UTF-8 line count이며,
첫 해시는 `lens3_verdict.md:L121`에도 독립 기록돼 있다.

`feyerabend_c1_v5.py`의 `build_honest_witness`는 A가 말하는 생성기가 아니다.

1. post anchor 자체를 입력으로 받는다 (`L948-L950`).
2. 같은 분석기로 Tier-B가 0인지 먼저 본다 (`L957-L960`).
3. post의 모든 필드를 `raw_span` 하나만 제외하고 generator parameter로 복사한다 (`L963-L979`).
4. 같은 post `p0/p1`에서 `raw_span`만 재계산한다 (`L973-L983`).
5. 생성 결과가 post와 byte-identical하지 않으면 거절한다 (`L984-L987`).
6. 그 post-derived spec의 digest를 witness ID로 쓴다 (`L988-L1011`).

따라서 이 함수는 독립적인 정직 장면 생성이 아니라 **post 표면의 거의 항등 투영**이다. 하니스도
`exact and tier_B==0`만으로 `information_limit_record`를 부여한다
(`loop_l1f.py:L290-L357`). 봉인 조문은 반대로 독립 지정 장면을 요구하고 post round-trip을 명시적으로
금지한다 (`prereg.json:L111-L138`, `L377-L391`).

또한 `analyze_frozen_surface`는 field inventory를 만들지만 타입 심판은 handle/type/geometry/raw_span/
region presence/weight의 제한된 조건뿐이다 (`feyerabend_c1_v5.py:L332-L419`). 그 뒤
`uncovered_declared_field_count`를 계산하지 않고 0으로 고정한다 (`L679-L712`). 타입·미래 필드·
교차-record provenance에 대한 일반 closed-world membership은 존재하지 않는다.

### 2.2 “생성기 재실행”의 세 의미를 분리해야 한다

| 의미 | 현재 상태 | 판정 |
|---|---|---|
| 추정기 자기시험 재실행 | `feyerabend_c1_v5.py`는 `--selftest`만 지원 (`L1260-L1269`) | 가능 |
| L1f 전체 계산 재실행 | `loop_l1f.py --compute-only`; 본 검토에서 18.083초 | 가능 |
| 독립 정직 생성기로 임의 post 표면의 membership 증명 | 해당 API·문법·solver 없음 | **불가능/미구현** |

기본 full-run은 기존 8개 산출물이 있으면 `FileExistsError`로 중단하고, 출력도 모두 `x`/`xb`로만
생성한다 (`loop_l1f.py:L1592-L1621`). 즉 fresh cell 복사본에서는 재생성 가능하지만 현재 폴더에
“그대로 재실행”하는 구조도 아니다. 별도 `--output-root`나 증인 전용 CLI는 없다.

실제 합성 scene factory인 `feyerabend_c0.py`는 존재하지만, runtime introspection 결과
`BASE_SCENE_COUNT=50`, scale 4종 `{0.001,0.01,1,1000}`인 결정적 factory다. full 실행은 200 JSON
scene을 자기 output 폴더에 쓴다(`python feyerabend_c0.py --help`; `build_base_corpus`). 이것은 A의
출발 자산일 수는 있어도, 임의의 관측 표면이 “정직 도시 의미 집합”에 속하는지를 판정하는 완전한
membership oracle는 아니다. 고정 200장면만 열거하면 정상 OOD를 위조로 오판하고, post의 모든 값을
자유 parameter로 받도록 확장하면 지금의 항진으로 되돌아간다.

### 2.3 “수리 1~2회” 비용 추정은 성립하지 않는다

결재안은 봉인 재입법과 구현을 “수리 1~2회”로 잡지만
(`PAUL_DECISION_L1_LOOP.md:L57-L62`), work breakdown, generator completeness 기준, membership 방식,
false-reject 예산, 독립 검증 비용이 하나도 없다. 최소한 다음은 서로 다른 납품물이다.

1. **도메인 문법**: 11개 현행 필드뿐 아니라 타입·값·관계·다중도·순서·source provenance·향후
   필드의 정책을 명시한다.
2. **독립 generator**: post anchor를 parameter로 받지 않는 latent semantic spec에서 surface를
   만든다. estimator와 canonicalizer의 공통 구현을 공유하지 않는다.
3. **membership/certificate**: 무작위 재실행이 아니라 “생성 가능/불가능/미정”을 구분한다. 정확
   비멤버십을 주장하려면 bounded exhaustive search, solver, 또는 검증 가능한 certificate가 필요하다.
4. **abstention과 운영 계약**: generator support 밖은 위조라고 단정하지 않고 `UNKNOWN/ABSTAIN`으로
   격리한다. C2와 downstream의 소비 규칙도 바꾼다.
5. **독립 자격 심사**: 다섯 함대 회귀, 합성 조합, OOD 정상 입력, 과차단/희석/절벽/마스킹을 새
   하니스로 검증하고 새 봉인을 선행한다.

현재 계산 18초는 runtime 비용이 작다는 증거일 뿐, 위 다섯 의미론 작업을 “두 번의 수리”로 끝낼
근거가 아니다. 코딩 iteration과 독립 fleet qualification을 같은 “1회”로 세어서도 안 된다.

## 3. A/B/C/D 선택지 구성의 적대 심사

### A — 방향은 유망, 승인안으로는 미성숙

살아 있는 장점은 분명하다. 독립적이고 sound한 정직 generator가 실제로 존재한다면 post-copy
항진을 없애고, generator가 허용하지 않는 비계약 타입을 거절할 수 있다. 그러나 다음 숨은 전제가
충족되지 않았다.

- **soundness와 completeness를 동시에 가정**한다. generator가 만드는 모든 표면이 정직해야 하고,
  모든 정직 표면도 generator support에 있어야 한다. 현재 400장면 실측은 이 둘의 증명이 아니다.
- **표본 생성과 비멤버십 증명을 혼동**한다. 여러 번 생성해 못 찾았다는 사실은 생성 불가능의 증명이
  아니다.
- **exact equality의 정책을 미정으로 둔다.** handle, order, source ID 같은 identity 필드를 자유롭게
  두면 독립성 위조가 통과하고, 고정하면 의미상 정상인 rename/reorder를 과차단할 수 있다.
- **generator 자체가 새 oracle이라는 위험을 누락**한다. 불완전 타입/관계 문법, post-derived latent,
  version drift, estimator와의 공통-mode bug가 새 “검사하지 않은 축”이 된다.
- **상승 외 실패축을 해결한다고 가정**한다. A는 GRID 과차단, saturation, 분모 청소, 희석, property
  모집단 마스킹을 구조적으로 막지 않는다. 기존 자산 승계를 선언하는 것만으로 조합 회귀가 사라지지
  않는다; L1f GRID 회귀가 바로 반례다.
- **44건의 계약 해석을 선결하지 않았다.** lens2는 사후 수치 표면의 Tier-B가 0/44라 정당하다고
  판정했고 (`lens2_verdict.md:L168-L250`), seat4는 독립 증인이 0/44라 전건 violation이라고 판정했다
  (`seat4_verdict.md:L103-L144`). generator 독립성과 membership 증거 형식을 봉인하기 전에는 A도
  이 불일치를 해결하지 못한다.

따라서 “A만이 메타패턴을 구조적으로 우회한다”는 결재안 문장
(`PAUL_DECISION_L1_LOOP.md:L79-L81`)은 과장이다. A는 **증인 항진 한 축의 구조적 후보**이지 전체
실패 메타패턴의 유일한 해법이 아니다.

### B — “즉시 통과” 주장이 틀렸다

증인 요건만 제거해도 현 구현에는 독립지지 위조에 의한 LOW→HIGH, 타입 공백의 0→0.778/1.0,
GRID neutrality gate 위반이 남는다. 특히 GRID 하나 추가로 reference 0.9071→0.0, HIGH→NONE이 된
실측은 witness 요건과 무관하다 (`lens2_verdict.md:L108-L164`). B가 정말 즉시 PASS하려면 witness뿐
아니라 completeness와 no-loss gate까지 같이 완화해야 한다. 그것은 “수치 조건 단독”이라는 작은
재입법이 아니라 제품 목표의 대폭 변경이다. 위험 수용 문서·소비자 격리 없이 승인할 수 없다.

### C — 즉시 안전조치로는 맞지만 독립 선택지로는 불완전

C는 현재 신뢰도 자기인증을 downstream에서 소비하지 않게 하므로 가장 즉각적이고 가역적인
containment다. 다만 “E2 본선은 이 부품 없이 진행 가능”이라는 주장에는 소비자별 dependency map,
fallback, fail-closed 규칙, telemetry가 붙어 있지 않다
(`PAUL_DECISION_L1_LOOP.md:L69-L73`). C2와 실도면 축척 트랙의 손실을 단순 “천장 저하”로만 쓰지
말고 정확한 block/대체 경로를 명시해야 한다. 그래서 C를 E의 1단계로 채택한다.

### D — 현 형태는 기각

L1g 점수리 계속은 L1e에서 미리 정한 중단선
(`chainverify_L1e/SYNTHESIS.md:L49-L53`)을 어긴다. 다만 결재안은 “모든 추가 구현”과 “동일 계약의
무제한 수리 반복”을 섞고 있다. 사전 봉인된 A0 연구와 별도 자격 트랙은 D가 아니다. 이 구분이
없어 A를 승인하거나 전면 중단하는 거짓 양자택일이 생겼다.

## 4. 다섯 함대 이력으로 A의 메타패턴 차단을 반례화

| 함대 | 실증 결함 | 구성적 witness A가 구조적으로 막는가 | 반례 |
|---|---|---|---|
| L1b / 1차 | 모집단 변경으로 결함 잠복, 재현 문안 과장, 봉인 절차 공백 | **아니오** | generator와 property test가 같은 유한 corpus만 보면 똑같이 blind하다 (`chainverify_L1b/SYNTHESIS.md:L16-L29`). |
| L1c / 2차 | 가드 우회 4종, 분모 청소, 정상 혼합단위 과차단, 검사기 상수 성공 | **부분적/대부분 아니오** | post 표면이 generator support 안이어도 estimator 공식이 HIGH로 오르거나 정상 입력을 낮출 수 있다 (`chainverify_L1c/SYNTHESIS.md:L17-L40`). |
| L1d / 3차 | 0/1 절벽·포화로 시험 판별력 소실, 삭제형 정보 한계 | **아니오** | 정직 생성 장면을 제시해도 score cliff와 ceiling-start pool은 그대로다 (`chainverify_L1d/SYNTHESIS.md:L14-L40`). |
| L1e / 4차 | 탐지 맹창, 선언↔기하 불일치, mean 희석, post-copy witness, GRID 과차단, 역방향 창 | **post-copy만 직접 해결** | 희석·GRID·역방향은 별도 불변식이며 generator membership으로 자동 보장되지 않는다 (`chainverify_L1e/SYNTHESIS.md:L16-L46`). |
| L1f / 5차 | type 공백, source/multiplicity 독립성 위조, witness 항진, GRID 회귀, 6-fixture 마스킹 | **엄격한 문법이면 type/post-copy는 가능; 나머지는 아님** | 같은 source를 다른 handle로 표현하는 latent 문법이 열려 있으면 F1이 generator 안으로 이동한다. GRID와 표집 결함은 그대로다 (`chainverify_L1f/SYNTHESIS.md:L25-L43`). |

A에 대한 구체적 반례 시도는 다음과 같다.

1. **자유-parameter 반례**: generator가 exact post equality를 맞추기 위해 `text_height`, handle,
   `source_span_id`를 입력 parameter로 받으면 현 구현과 동형이며 타입·독립성 위조를 그대로 생성한다.
2. **유한-support 반례**: generator가 C0 200장면 같은 고정 support만 가지면 새로운 정상 도시 장면을
   생성하지 못해 위조로 오판한다. “못 만들었다”와 “부정직하다”가 동치가 아니다.
3. **alias/provenance 반례**: 서로 다른 handle이 같은 물리 source를 가리키는 surface가 generator
   문법상 허용되면 LOW→HIGH 위조가 정직 인증된다. 독립성은 문자열이 아니라 latent source 관계로
   강제해야 한다.
4. **과차단 반례**: before와 honest GRID-added after를 generator가 둘 다 정상 생성해도 현재
   estimator는 0.5τ~2.159τ 대역에서 HIGH→NONE으로 떨어진다. witness는 no-loss를 보장하지 않는다.
5. **공통-mode 반례**: generator, analyzer, certificate가 같은 canonicalization/type helper를
   공유하면 한 번의 normalization bug가 세 층을 동시에 속여 “독립” 검증이 사라진다.

결론적으로 다섯 함대의 메타패턴은 단순히 “선언형 심판”이 아니라 **불완전한 명세와 그 명세를
검사하는 모집단/술어의 공통 사각**이다. A는 oracle을 하나 더 만들 뿐이며, 독립성과 completeness를
별도로 증명하지 않으면 구멍이 estimator에서 generator로 이동한다.

## 5. 누락 선택지와 독립 권고

### E — 격리 + A0 타당성 게이트 (**권고**)

**즉시 상태**

- L1 estimator는 scale 후보와 진단 수치만 출력하고 `trusted/HIGH` 자기인증은 소비 금지.
- C2는 닫힌 상태 유지. downstream은 `UNKNOWN/ABSTAIN`을 fail-closed로 취급.
- 희석-불가 공식·봉인 절차·replay 장부는 보존하되 PASS 근거로 사용하지 않음.

**A0는 다음 네 gate를 순서대로 통과해야 한다.**

1. **G0 — 문법 봉인**: typed schema, dependent relations, identity/provenance, multiplicity/order,
   extension-field 정책, exact-equivalence에서 의미/비의미 필드 구분을 코드 전에 봉인한다.
2. **G1 — 독립성**: generator API는 post anchors를 받지 않는다. 사전 latent spec만 받고, estimator/
   analyzer와 canonicalization 구현을 공유하지 않는다. membership은 `YES/NO/UNKNOWN`과 검증 가능한
   trace를 낸다.
3. **G2 — 반례 자격**: 최소한 공개된 1,024/1,024 타입 반례, manufactured-support 20/20,
   witness post-copy 90/90, GRID 자유사냥 손실 32/1,500, property 마스크 40/40, P5 44건의 독립 증인
   판정을 모두 재심한다. 구성 증인은 희석·과차단·절벽·표집 검사를 대체하지 않는다.
4. **G3 — 운영 자격**: 정상 OOD에 대한 false reject/UNKNOWN을 공개하고, 소비자 dependency map과
   fail-closed 동작을 검증한다. 그 뒤에만 새 이름의 자격 트랙을 열고 독립 함대를 발사한다.

G0/G1에서 막히면 구현 수리로 밀어붙이지 않고 C 상태를 유지한다. G2/G3 성공 전에는 “1~2회면
완료”나 “구조적으로 차단”이라는 표현을 금지한다.

### F — estimator와 certifier 분리 + proof-carrying abstention

E의 A0에서 비교할 별도 설계안이다. estimator는 scale 후보만 제안하고, 별도 certifier가 typed
surface·provenance·단조성 증거를 확인해 certificate를 붙인다. certificate가 없거나 generator
membership이 미정이면 `ABSTAIN`; 단순 HIGH를 발행하지 않는다. A처럼 하나의 생성기가 모든 정직성을
대표한다고 가정하지 않고, 실패 축을 분리한다. 구현비는 들지만 공통-mode를 줄이고 C에서 단계적으로
도입할 수 있다.

## 6. 최종 결재 문구 제안

> **결정: E 승인.** L1의 자기인증 사용은 즉시 동결·강등한다. A는 구현 1~2회 약정으로 승인하지
> 않고, 독립 정직 생성 문법과 membership certificate의 원리적·코드적 타당성을 검증하는 A0로
> 한정한다. A0는 post-derived parameter 금지, YES/NO/UNKNOWN, 다섯 함대 전 회귀, 정상 OOD 과차단,
> 독립 fleet을 gate로 갖는다. 성공 시 새 자격 트랙을 결재에 다시 올리고, 실패 시 C를 유지한다.
> B와 L1g(D)는 승인하지 않는다.

이 결론은 A를 폐기하자는 뜻이 아니다. **A를 제품 결론에서 검증 대상 가설로 정확히 강등**하자는
것이다. 현재 증거가 보장하는 것은 “기존 수치 하니스는 빠르게 재현된다”까지이며, “독립 구성적
증인이 구현돼 있고 두 번의 수리로 0-violation에 도달한다”는 주장은 보장하지 않는다.
