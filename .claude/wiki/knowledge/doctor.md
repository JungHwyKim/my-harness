# Doctor 정적 진단 계약

`python .claude/harness/scripts/doctor.py`는 하네스를 복사해 넣은 직후의 **공유 설정**을
정적으로 점검한다. 실행 방법과 한계 요약은 `README.md`의 「설치 직후 점검 — Doctor」에
있고, 이 문서는 그 판정이 **무엇을 근거로 하는지**를 둔다.

## 이 명령이 존재하는 이유

설정 오류가 **에러 없이 통과한다**. 세 자리가 실측으로 그렇다.

- `_hookutil.config()`는 읽기·파싱 실패를 빈 사전으로 흡수한다. 설정이 통째로 없는 것과
  같아지는데 아무도 모른다.
- `_hookutil.schema_version()`은 bool을 제외한 양의 정수만 받고 나머지를 1로 떨군다.
  `"2"`나 `2.0`을 적으면 **V2 Quality·History 분기가 꺼진 채로** 돈다.
- 추적 경로 항목에서 끝의 `/`가 빠지면 두 소비자가 「정확한 파일 하나」로 읽는다.
  `tracked_paths: ["tests"]`는 그 디렉터리 아래 어떤 변경도 잡지 못한다.

세 경우 모두 검사가 **꺼진 채로 통과**한다. Doctor는 그 조용한 자리만 모아 본다.

## 보장하지 않는 것

**명령을 실행하지 않는 것이 보안·비용 경계다.** 훅·stage·Git·다른 인터프리터를 돌리지
않고, 대상 프로젝트의 Python 모듈이나 pytest 설정을 import하지 않는다. 파일·세션 마커·
캐시를 만들지 않고 외부를 호출하지 않는다.

| 보지 않는 것 | 이유 |
|---|---|
| 명령의 실행 성공 | 실행하지 않는다. 결선 PASS는 「연결이 있다」까지다 |
| `pytest`·`ruff` 설치 상태와 버전 | 실행하지 않으므로 미검증이다 |
| 사용자·로컬·관리자 설정 | 공유 파일만 본다. 병합 결과와 활성 상태는 모른다 |
| 실제 세션의 훅 활성 여부 | 설정 파일이 세션 보호를 뜻하지 않는다 |
| 유료 테스트 정책·승인 | `paid-test-approval.md`가 소유한다 |
| 디렉터리 전체의 매핑 커버리지 | 확정 가능한 파일만 본다. 하위 전수 탐색은 하지 않는다 |

`.agents/`와 `.codex/`는 로컬 전용이라 검사하지 않고 부재를 실패로 보지 않는다.

## 대상 루트

배포 전제는 `<root>/.claude/harness/scripts/doctor.py`에 복사해 쓰는 **저장소 로컬
CLI**다. 자기 파일 경로의 상위 세 칸이 `scripts`·`harness`·`.claude`인지 먼저 보고, 맞을
때만 `Path(__file__).resolve().parents[3]`을 루트로 쓴다. 어긋나면 진단을 시작하지 않고
종료 코드 2를 반환한다. cwd나 `CLAUDE_PROJECT_DIR`가 다른 곳을 가리켜도 루트는 바뀌지
않는다.

**훅의 루트 결정(`_hookutil._find_root()`)과 반대이고, 그것이 의도다.** 두 전제가 왜 다른지,
그리고 기각한 대안(`_hookutil` import 포함)은
`.claude/wiki/history/plan/2026-11-22-doctor-target-root.md`에 있다.

그 결과 인터프리터 선택은 **Doctor의 루트 기준**이고, 실제 훅의 환경변수 기반 루트와
중첩 프로젝트에서 갈릴 수 있다. 출력이 그 사실을 함께 적는다. Doctor는 실제 훅이 고를
인터프리터를 관찰한 것이 아니다.

`_hookutil`을 import하지 않고 `venv_python`·`_wiki_root`·`history_prefix`·추적 경로
선택과 정규화의 순서와 분기를 옮겨 적었다. **그쪽이 바뀌면 Doctor가 조용히 어긋난다.**

**진단 런타임에서 import를 금지한 것과 테스트에서 대조하는 것은 다르다.**
`tests/test_doctor.py`의 「복제한 분기 대조」가 conftest의 `load_hook`으로 실제 소비자
모듈을 읽어 같은 설정에서 같은 값이 나오는지 본다 — `auto_test_check.QUALITY_TRACKED_PATHS`,
`history_check.TRACKED_PATHS`, `_hookutil.WIKI_ROOT`, `history_prefix()`, `venv_python()`의
대체 순서, 그리고 끝의 `/` 유무에 따른 `tracked_paths_newer_than()`의 실제 결과다.

## 종료 코드

| 코드 | 조건 |
|---|---|
| 0 | 진단을 마쳤고 FAIL이 없다. WARN만 있어도 0이다 |
| 1 | 진단을 마쳤고 FAIL이 하나 이상이다 |
| 2 | **진단을 못 마쳤다** — 배치 오류, 루트 접근 불가, 예상하지 못한 내부 오류 |

2가 0/1보다 우선한다. 필수 파일 누락과 JSON 오류는 정상 진단의 FAIL이므로 1이다 — 사용자
데이터에서 예상 가능한 오류를 내부 오류로 숨기지 않는다. Python이 시작조차 못 한 경우의
종료 코드는 이 CLI가 통제하지 않는다.

**미검사는 PASS가 아니다.** 선행 오류로 못 본 검사는 `[WARN] 미검사`로 나온다. 없는 선택
파일과 비활성 설정도 PASS로 꾸미지 않는다.

## 버전 판정

`schema_version`은 **D-VERSION만** 판정한다. D-CONFIG는 같은 사실을 스키마 required·const
오류로 다시 보고하지 않는다. 그러지 않으면 정상 V1 프로젝트가 WARN과 FAIL을 동시에 받아
종료 1이 된다 — 하네스를 막 복사한 프로젝트가 바로 그 상태다.

| 값 | 판정 | 실제 런타임 |
|---|---|---|
| 필드 부재, 정수 1 | WARN. V2 상세 검사는 미검사 | V1 경로. V2 분기 안 돎 |
| 정수 2 | 계속 | V2 경로 |
| bool·문자열·실수·0 이하·null | FAIL | **1로 대체되어 V2 분기가 꺼진다** |
| 정수 3 이상 | FAIL. V2 상세 검증은 생략 | `is_v2()`가 참이라 **V2로 돈다** |

마지막 두 줄이 이 표의 요점이다. 「지원하지 않는다」만 적으면 지금 게이트가 어느 쪽으로
도는지가 빠지는데, 그것이 정작 고칠 때 필요한 사실이다.

## 스키마보다 엄격한 자리

V2 핵심 구조는 `harness.schema.json`을 표준 라이브러리로 옮겨 검증한다. `jsonschema`를
새로 깔지 않으므로 스키마와 어긋날 수 있고, 그 대응은 `tests/test_doctor.py`가 스키마
파일을 읽어 상수와 대조해 잠근다.

스키마가 허용하는데 **소비자가 무시하거나 항상 건너뛰는** 조합은 FAIL로 올린다. 스키마만
봐서는 안 보이고, 그런 설정은 조용히 안 도는 쪽으로 고장 나기 때문이다.

| 자리 | 스키마 | Doctor | 근거 |
|---|---|---|---|
| fast에 `post_change` 외 트리거, full에 `stop`·`pre_commit` 외 트리거 | enum 허용 | FAIL | `auto_test_check.py:281`·`:316`, `pre_commit_check.py:165`만 이 조합을 읽는다 |
| full stage의 `{changed_files}`·`{mapped_targets}` | 허용 | FAIL | 두 full 트리거가 빈 목록을 넘겨(`pre_commit_check.py:169`, `auto_test_check.py:324`) 그 stage는 **항상 건너뛰면서 성공으로 보고**된다 |
| 같은 profile의 중복 stage id | 제약 없음 | FAIL | `_quality.py:113`이 `QualityConfigError`로 막는다 |
| 기존 디렉터리를 가리키는데 끝에 `/`가 없는 추적 항목 — **그 항목이 실제로 선택될 때만** | 허용 | FAIL | `auto_test_check.py:88`·`_hookutil.py:499`가 정확한 파일로 읽어 아무것도 안 잡는다 |
| 같은 항목이지만 선택되지 않는 대체 필드에 있을 때 | 허용 | **WARN** | 읽는 소비자가 없어 지금 꺼진 것이 없다. 대체로 쓰일 때를 대비해 알리기만 한다 |
| `fast`/`full` 둘 다 필수 | required 없음 | **WARN** | 스키마가 허용하므로 실패시키지 않는다. 비활성이라고만 알린다 |

빈 profile은 WARN이고, 잘못된 트리거 조합은 **stages가 비어 있어도** FAIL이다 — 나중에
stages를 채우는 순간 조용히 안 도는 설정이 되기 때문이다.

## 치환값 판정

인자별 거부 조건은 실행기와 **글자 그대로 같다**(`_quality.py:131`).

```text
arg.startswith("{") and arg.endswith("}") and arg not in {python}/{changed_files}/{mapped_targets}
```

그래서 `{unknown}`·`{a}x{b}`·`{}`는 FAIL이다. 더 좁게 「알 수 없는 단독 치환값」으로 읽으면
`{a}x{b}`를 통과시키는데, 실행기는 그 설정을 `QualityConfigError`로 거부한다 — Doctor가
실행기보다 **느슨한** 쪽이 되는 것이 가장 나쁘다.

알려진 치환값이 문자열 안에 든 `{python} --version`·`--opt={python}`은 WARN이다. 실행기는
항목 전체가 치환값일 때만 확장하므로(`_quality.py:169`) 이 값은 글자 그대로 전달된다.

## 추적 경로의 대체 선택

네 필드를 무조건 같은 기준으로 보지 않는다. **실제로 선택되는 것만 FAIL 대상이다.**
선택 규칙은 두 소비자와 같다(`auto_test_check.py:67`, `history_check.py:41`) — 리스트이고
공백이 아닌 문자열이 하나라도 있으면 그 값을 쓰고, 아니면 대체로 내려간다.

| 필드 | 쓰이는 조건 |
|---|---|
| `quality.tracked_paths` | 비어 있지 않으면 Fast/Full이 그대로 쓴다 |
| `history.tracked_paths` | 비어 있지 않으면 History Gate가 그대로 쓴다 |
| `source_prefixes` | 위 둘 **중 하나라도** 비었을 때. History 대체는 둘을 이어 붙인다 |
| `harness_paths` | `history.tracked_paths`가 비었을 때만 |

**V2에서 이 두 대체 필드의 다른 소비자는 모두 버전 게이트로 꺼져 있다** —
`task_log_check.py:193`은 `is_v2()`면 즉시 반환하고, `auto_test_check.py:416`은 V2
핸들러로 보내고 돌아와 `:245`·`:376`·`:426`에 닿지 않는다. Doctor의 V2 검사에서 저 둘이
오직 대체일 뿐인 근거가 이것이다.

## matcher 해석

Claude Code 공식 Hooks reference(2026-11-22 확인)를 따른다. 순서대로 적용하고, 각 단계는
앞 단계에 걸리지 않은 값만 받는다.

1. 누락·빈 문자열·**정확히** `*`는 정규식으로 컴파일하기 전에 **전체 적용**으로 본다.
   원본을 `strip()`하지 않는다 — `" * "`를 전체 적용으로 바꾸는 것은 제품이 strip한다는
   쪽에 걸고 PASS를 내는 것이다.
2. 영문자·숫자·`_`·`-`·공백·`,`·`|`만 있는 값은 **이름 목록**이다. `|`와 `,`로 나눠 도구
   이름과 정확히 비교한다. 그래서 `ri`는 `Write`를 덮지 않는다. 쪼갠 뒤 이름이 하나도
   남지 않으면(공백뿐인 값) 빈 목록으로 비교하지 않고 「확인 불가」다.
3. 그 밖은 정규식이다. **두 엔진에서 뜻이 같다고 확인한 문법만** Python `re.search`로
   부분 일치를 본다. 그 밖은 「확인 불가」다.

**3의 판정 기준은 차단 목록이 아니라 허용 목록이다.** Python이 컴파일했다는 사실은
JavaScript와 같다는 근거가 못 된다. 실측(V8, 2026-11-22)이 그 이유다.

| 패턴 | Python 3.12 | V8 | Doctor |
|---|---|---|---|
| `(?i)Write` (전역 플래그) | 컴파일, `Write` 일치 | `Invalid group` | **FAIL** |
| `(?i:W)` `(?-i:W)` `(?im-s:W)` | 컴파일 | 컴파일 | 확인 불가 WARN |
| `(?x:W)` `(?u:W)` `(?i-i:W)` `(?-:W)` | 일부 컴파일 | `Invalid group`·`Repeated flag` | **FAIL** |
| `Bash++` `Bash*+` `Bash?+` `Bash{1,2}+` | 컴파일(possessive), 일치 | `Nothing to repeat` | **FAIL** |
| `(?P<n>W)` `(?#c)` `(?>x)` | 컴파일 | `Invalid group` | **FAIL** |
| `\AWrite` | 시작 앵커로 `Write` 일치 | 리터럴 `AWrite`, 불일치 | 확인 불가 WARN |
| `(?<=x)W` `(?<n>W)` `[]W` `W{,2}` | — | — | 확인 불가 WARN |
| `.*` `[Ww]ri` `Write$` `(A|B)` `\b` `a*?` | 같다 | 같다 | 부분 일치로 판정 |

**전역 플래그와 범위가 있는 modifier 그룹은 다르다.** JavaScript에는 `(?ims-ims:…)`처럼
범위가 있는 형태만 있고 전역 `(?i)`는 없다(MDN `Modifier`, 2026-11-22 확인). 받는 플래그는
`i`·`m`·`s`뿐이며 켜는 쪽과 끄는 쪽에서 중복될 수 없고, 한쪽은 비어 있어도 되지만 둘 다
비면 오류다. 그래서 **그 밖의 글자(`a`·`L`·`u`·`x`)와 중복·빈 플래그는 엔진과 무관한 확정
오류**이고, 올바른 `i`/`m`/`s` 그룹은 **확인 불가**다 — 뜻이 Python과 달라서가 아니라
2025에 들어온 문법이라 그 전 엔진은 `(?i:`를 `(?i)`와 똑같이 거부하고, 제품이 어느 엔진을
쓰는지 보지 못했기 때문이다. modifier 그룹의 확인 불가가 **뒤의 확정 오류를 덮지는 않는다**
— `(?i:Bash++)`와 짝이 안 맞는 `(?i:Write`는 FAIL이다.

JS가 거부한다고 **확정한** 패턴은 FAIL이고 단순 미확인과 구분한다. 그 항목은 어느 도구에도
걸릴 수 없으므로 도구별 계산에서 빼고, 남은 결선은 따로 판정한다. 다만 FAIL 문구는 측정
가능한 사실(「JavaScript 정규식이 아니다」)까지만 말하고 제품이 그 값을 만났을 때 어떻게
행동하는지는 단정하지 않는다 — 제품 소스를 읽어 확인한 것이 아니다.

**`tests/test_hook_wiring.py:158`은 자기 목적으로 Python `fullmatch`를 계속 쓴다. 두 곳의
규칙이 다른 것은 버그가 아니다** — 통일하지 않는다. 그 이유와 기각한 대안은
`.claude/wiki/history/plan/2026-11-22-doctor-matcher-semantics.md`에 있다.

**확인 불가 matcher만으로 필수 결선을 PASS하지 않는다.** 같은 이유로 해석할 수 없는 훅
명령(셸 연산자·래퍼·알 수 없는 변수)은 WARN이며 결선의 근거가 되지 못한다.

## 훅 명령의 스크립트 자리

**`.py`로 끝나는 인자가 있다는 것은 그 파일을 실행한다는 증거가 아니다.** Python의 실행
옵션 표를 지나 **첫 비옵션 토큰**을 스크립트로 본다. 확장자는 따지지 않는다 — Python은
`.py`가 아닌 파일도 실행한다.

| 명령 | 판정 |
|---|---|
| `python -u <훅>` `py -3 <훅>` `python -X utf8 <훅>` | 그 훅을 실행한다 |
| `python <훅> --opt other.py` | 그 훅이다. 뒤의 `.py`를 다시 고르지 않는다 |
| `python <훅> # 주석` | 그 훅이다. `#` 뒤는 명령이 아니다 |
| `python -W "" <훅>` `python <훅> ""` | 그 훅이다. 옵션 값이나 스크립트 뒤의 빈 인자는 자리를 바꾸지 않는다 |
| `python -c pass <훅>` `python -m x <훅>` `python --version <훅>` | **확인 불가.** 그 파일을 열지 않는다 |
| `python -Z <훅>` | **확인 불가.** 모르는 옵션이 값을 받으면 그 값을 스크립트로 읽게 된다 |
| `python "" <훅>` `python '' <훅>` | **확인 불가.** 빈 스크립트 자리다 |

**토큰화에서 `""`·`''`는 빈 인자 하나로 남긴다.** 버리면 argv의 자리가 하나 밀려 다음
인자를 실행 대상으로 읽는다. 실제 Python은 빈 자리를 **디렉터리로** 읽고 `__main__`을 찾다
종료 1이며, 뒤의 훅 경로는 실행되지 않는다(실측). 빈 값이 옵션의 값일 수도 있으므로
(`-W ""`는 스크립트를 실행한다) 일괄 거부하지 않고 **자리로** 가른다.

확인 불가 명령은 D-HOOK WARN이고, 그 명령만으로는 필수 결선이 성립하지 않는다(D-WIRING
FAIL). 셸 해석기로 확장하거나 설정에 적힌 명령을 실행해 확인하지 않는다.

## 검사 범위의 두 갈래

- **D-HOOK**은 모든 이벤트에 연결된, 정적으로 해석 가능한 **프로젝트 내부** 스크립트의
  존재를 본다. 품질 훅에 한정하지 않는다.
- **D-WIRING**은 아래 세 줄만 필수로 요구한다. 활성 트리거가 아니면 요구하지 않는다.

| profile / trigger | 이벤트 | 덮어야 할 도구 | 스크립트 |
|---|---|---|---|
| fast / post_change | PostToolUse | Write, Edit, Bash, PowerShell | `auto_test_check.py` |
| full / stop | Stop | (matcher 검사 없음) | `auto_test_check.py` |
| full / pre_commit | PreToolUse | Bash, PowerShell | `pre_commit_check.py` |

같은 이벤트의 여러 group을 합쳐 도구별로 찾는다. 다른 이벤트의 같은 파일이나 같은
basename만으로 통과시키지 않고, 정규화한 전체 프로젝트 경로와 `type: command`를 함께 본다.
`${CLAUDE_PROJECT_DIR}`는 대상 루트로 정적으로 치환하며, 다른 변수는 추측해 풀지 않는다.

## 자동 추적 범위 밖이다

`.claude/harness/scripts/`는 현재 `quality.tracked_paths` 밖이다. 그래서 `doctor.py`를
고쳐도 **Fast 게이트가 돌지 않는다** — 이번 작업은 이 범위를 의도적으로 그대로 두었다.
영향 테스트는 지정 인터프리터로 직접 돌린다.

```text
.venv/Scripts/python.exe -m pytest tests/test_doctor.py -q
```

`tests/`는 추적 경로 안이고 `test_target_for()`의 직접 테스트 특례에 걸리므로,
`tests/test_doctor.py`를 고치면 그 파일만 Fast로 돈다.

## 현재 확인된 상태

| 확인 | 결과 | 시점과 주체 |
|---|---|---|
| `tests/test_doctor.py` | 246 passed, 1 skipped | 2026-11-22, Claude가 지정 인터프리터로 실행 |
| Full 세 단계 | `ruff check` 통과, `ruff format --check` 71 files already formatted, **651 passed · 1 skipped** | 2026-11-22, Claude 실행 |
| 이 저장소 자체 진단 | PASS 24 · WARN 5 · FAIL 0, 종료 0 | 2026-11-22, Claude 실행 |

1건 skip은 POSIX 실행 권한 비트 검사다. **Linux에서는 검증하지 않았다** — Windows 로컬
보고이며, 반대 OS의 경로 분류는 순수 입력 테스트로만 덮었다.

이 저장소 진단의 WARN 5건은 모두 설치 상태가 아니라 이 저장소의 실제 설정이다 — `src/`와
`pyproject.toml` 미생성(D-SCAFFOLD 3건), `{python}`뿐이라 확인 대상이 없는
D-EXEC 미검사 1건, 그리고 `.claude/harness.json`이 추적되지만 대응 테스트가 없다는
D-MAPPING 1건이다. 마지막 1건은 `quality-env.md`가 산문으로 적어 둔 사실
(「문서·스킬 파일 변경에는 매핑된 검사가 없다」)을 검사로 옮긴 것이다.
