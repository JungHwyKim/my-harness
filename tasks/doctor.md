# Doctor 명령 구현 작업 명세

- 작업 ID: `doctor`
- 상태: 구현 완료 · Codex Round 4 최종 리뷰 승인 · 보존·임시 파일 정리 대기
- 최신 검토: 2026-11-22 · `C:\my-harness`, `main` / `bd89a04`, 작업 트리의 명세·리뷰 기준
- 명세: `tasks/doctor.md`
- 리뷰: `tasks/doctor.review.md` — Round 4 구현·실행 보고 검토. 차단 지적 없이 최종 승인
- 선행 작업: 환경 구축과 인수인계 절차 설치 완료. 현재 계약은
  `.claude/wiki/knowledge/quality-env.md`와 공통 인수인계 절차에 있다
- 관계: 같은 Doctor 작업의 구현 결과를 검토하고 범위 안의 결함 수정을 지시한다.
  다른 작업의 훅 정책이나 품질 설정을 바꾸는 후속 작업을 포함하지 않는다

현재 판정과 검증 결과는 하단 「Codex Round 4 최종 결과 리뷰」를 따른다. 앞선 명세 검토 절의
「구현 전」·「검사 미실행」 표기는 그때의 기록이며 현재 결과를 대신하지 않는다.

## 목적

템플릿을 받거나 기존 프로젝트에 하네스를 복사한 직후, 필수 파일과 공유 설정의 정적 연결을
한 명령으로 확인한다. 설정 오류 때문에 훅이나 품질 검사가 조용히 빠지는 경우에는 위치와
수정 방법을 알린다. 실행 성공이나 실제 Claude Code 세션의 보호까지 보장하는 명령은 아니다.

## 실행 계약

- 저장소 루트에서 `python .claude/harness/scripts/doctor.py`로 실행한다. Python 표준
  라이브러리만 쓰며 Git 저장소, Claude Code 실행 환경, 별도 패키지를 요구하지 않는다.
- 배포 전제는 `<root>/.claude/harness/scripts/doctor.py`에 복사해 쓰는 저장소 로컬 CLI다.
  먼저 자기 파일 경로가 이 배치와 일치하는지 검사하고, 맞을 때만
  `Path(__file__).resolve().parents[3]`을 루트로 사용한다. 플러그인 설치 위치·다른 패키지
  깊이에서 임의 프로젝트를 진단하지 않는다. cwd나 `CLAUDE_PROJECT_DIR`가 다른 곳을
  가리켜도 루트는 바뀌지 않으며 출력 첫머리에 표시한다.
- 읽기 전용이다. 훅·stage·Git·다른 인터프리터를 실행하거나, 대상 프로젝트의 Python
  모듈·pytest 설정을 import하지 않는다. 설치, 파일·세션 마커·캐시 생성, 외부 호출도 없다.
- JSON은 UTF-8 BOM 유무를 모두 받는다. 파일 부재·읽기/디코딩 실패·잘못된 JSON·최상위
  객체가 아닌 입력을 처리하며, 한 파일이 깨져도 독립적인 검사는 이어간다. 선행 오류 때문에
  할 수 없는 검사는 `[WARN] 미검사`로 알리고 PASS로 표시하지 않는다.
- `[PASS]`, `[WARN]`, `[FAIL]`마다 안정적인 검사 ID, 파일과 JSON 필드 위치 또는 경로,
  이유를 출력한다. WARN·FAIL에는 구체적인 수정 안내가 있어야 한다. 마지막에 개수를 요약한다.
  진단을 마쳤을 때 FAIL이 하나라도 있으면 종료 코드 1, WARN만 있거나 전부 PASS이면 0이다.
- Doctor 자체의 배치 오류·대상 루트 접근 불가·예상하지 못한 내부 오류로 진단을 완료하지
  못하면 `[FAIL] D-RUN`과 「진단 미완료」 사유를 표시하고 종료 코드 2를 반환한다. 이 경우
  2가 발견 사항의 0/1보다 우선한다. 개별 필수 파일 누락·JSON 오류는 정상 진단의 FAIL/1이며,
  모든 예외를 내부 오류로 묶지 않는다. Python이 시작조차 못 한 경우의 종료 코드는 통제하지 않는다.

## 범위와 제외

- 포함: 새 `.claude/harness/scripts/doctor.py`, `tests/test_doctor.py`의 구현,
  README의 설치 직후 실행 안내, 완료 시 `.claude/wiki/knowledge/doctor.md`에 현재 계약 보존.
- 제외: 자동 복구·설치, CI 추가, 전체 JSON Schema 검증기, 셸 해석기, 훅 정책·기존 실행기
  변경, 품질 추적 범위 확대, 유료 마커 정책 검사, 훅 타임아웃 예산 분석, Codex 훅 배선.
- `.agents/`와 `.codex/`는 로컬 전용이다. 검사·수정하거나 부재를 실패로 취급하지 않는다.
  기존 프로젝트의 추가 훅, 문서, 의존성 파일을 덮어쓰지 않는다.

## 기존 코드 근거

- `.claude/harness/schemas/harness.schema.json:6` — V2의 필수 루트 필드는
  `schema_version`·`wiki_root`·`history`·`quality`다. `:63`의 profiles에는 fast/full을
  반드시 모두 넣으라는 required가 없고, `:113`·`:118`도 빈 triggers/stages를 허용한다.
- `.claude/harness/hooks/_hookutil.py:64` — 설정 오류를 빈 사전으로 흡수한다.
  `:80`은 버전 부재를 V1으로 보고 `:86`은 2 이상에서 V2 기능을 켠다.
- `.claude/harness/hooks/_hookutil.py:181` — Python 선택은 설정의 파일 경로 →
  `.venv/Scripts/python.exe` → `.venv/bin/python` → `sys.executable` 순이다.
- `.claude/harness/hooks/_hookutil.py:40` — 실제 훅의 루트는 환경변수/cwd에서 `.claude/`를
  가진 상위 디렉터리를 찾는다. `:30`의 플러그인 배치에 관한 과거 결정은 이 훅에 유효하며,
  저장소 로컬 CLI의 배치 전제와 다르다. `:121`은 wiki_root 기본값을 `.claude/wiki/`로 둔다.
- `.claude/harness/hooks/_hookutil.py:478`·`auto_test_check.py:80` — 추적 경로는 끝의 `/`로
  디렉터리 접두사와 정확한 파일을 구분한다. `history_check.py:41`·`:124`도 같은 규약을 쓴다.
- `.claude/harness/hooks/_quality.py:73`·`:94` — cwd와 stage 구조 검증.
  `:169`는 치환값이 argv 한 항목 전체일 때만 확장하며 빈 목록이면 stage를 건너뛴다.
- `.claude/harness/hooks/auto_test_check.py:67` — 추적 경로는 quality 설정의 유효한 목록,
  없으면 source_prefixes를 쓴다. `:281`은 fast/post_change, `:316`은 full/stop만 처리한다.
- `.claude/harness/hooks/pre_commit_check.py:165` — full/pre_commit만 처리한다.
  full을 호출할 때 변경 파일·매핑 대상을 전달하지 않는다. Stop도 같다(`auto_test_check.py:324`).
- `.claude/settings.json:19`·`:74`·`:105`·`:131` — 커밋 전, 파일 수정, 셸 명령 뒤,
  종료 시점의 현재 배선. `tests/test_hook_wiring.py:33`의 기존 추출은 파일명 중심이므로,
  Doctor의 프로젝트 경로 판정과 병합 설정 처리를 그대로 대신하지 못한다.
- `tests/conftest.py:31` — scripts 디렉터리가 테스트 import 경로에 들어 있다.
  `README.md:77`은 다른 언어 프로젝트가 Quality Profile을 자기 도구로 바꾼다고 명시한다.
- [Claude Code 공식 Hooks reference](https://code.claude.com/docs/en/hooks#matcher-patterns)
  (2026-11-22 확인) — matcher의 누락·빈 값·`*`는 전체 일치이며, 이름 목록과 정규식은
  구분해 해석한다. 정규식은 JavaScript의 부분 일치다. 기존 배선 테스트의 Python fullmatch를
  실제 제품의 matcher 의미로 그대로 복제하지 않는다.

## 구현 범위

### 1. 입력과 버전

훅용 `_hookutil`을 import해서 설정을 읽지 않는다. 그 모듈의 환경변수/cwd 기반 루트와
오류 흡수 동작은 이 CLI의 계약과 다르다. 순수 진단 함수와 CLI 출력을 분리해 테스트한다.
설정의 원본 객체와 필드 위치를 유지해 오류를 보고한다.

처리 순서는 JSON 읽기 → D-VERSION → 버전별 검사다. `schema_version`은 D-VERSION만
판정하며 D-CONFIG가 스키마의 required/const 오류로 중복 보고하지 않는다. 부재·정수 1은
정상 V1 호환 경로다. 정수 2일 때만 V2 루트 required와 history·quality·profile·stage·mapping
검증을 실행한다. V1 또는 잘못된/미지원 버전에서는 이 V2 검사들을 `[WARN] 미검사`로
남긴다. 읽기 가능한 설정과 독립된 공통 파일·settings 훅 검사는 계속한다.

V2 핵심 구조는 위 스키마의 `history`, `quality`, profile, stage, mappings 정의를 따라
표준 라이브러리로 명시적으로 검증한다. 필수 필드·타입·enum·중복 금지·알 수 없는 필드의
허용 여부도 해당 정의를 따른다. 스키마가 확장을 허용한 루트와 checks의 추가 키는 거부하지
않으며, checks의 개별 정책까지 전체 검증한다고 주장하지 않는다. 스키마 정의와의 대응은
테스트로 확인하며 `jsonschema` 등 새 의존성을 추가하지 않는다.
루트 선택 필드 python·source_prefixes·harness_paths의 스키마 타입 검사는 현재 D-CONFIG의
열거 범위에 포함하지 않는다(Round 3의 R3-01). 이 명령을 전체 스키마 검증기로 안내하지
않으며, 해당 확대는 별도 후속 범위로 남긴다. 실제 fallback 동작을 설명하는 검사와는 별개다.

Wiki의 두 README는 설정된 wiki_root 아래에서 찾는다. V2 상세 검사를 생략하는 분기에서는
`_wiki_root()`와 같이 부재·비문자열·공백 값에 `.claude/wiki/` 기본값을 쓴다.
정수 버전 2에서 wiki_root가 없거나 잘못되면 D-CONFIG FAIL,
Wiki 파일 검사는 선행 오류에 따른 미검사다. harness.json 자체를 읽거나 파싱하지 못한
경우에도 임의의 기본 위치로 검사해 추가 FAIL을 만들지 않고 Wiki 경로 검사를 미검사로 남긴다.
프로젝트 루트의 CLAUDE.md와 두 JSON의 존재 확인은 이 의존 관계와 무관하다.

### 2. 검사별 심각도와 종료 코드

| 검사 ID | 조건 | 판정과 안내 |
|---|---|---|
| D-RUN | 배치 전제 위반·루트 접근 불가·예상하지 못한 내부 오류 | 진단 미완료, 종료 2. 아래의 정상 진단 결과 집계와 구분 |
| D-FILES | CLAUDE.md, 두 설정 JSON, wiki_root 아래의 두 README 부재·읽기 불가 | FAIL. 실제 경로 안내. Wiki 경로를 확정할 수 없으면 미검사 WARN |
| D-OPTIONAL | AGENTS.md 부재 | WARN. Codex를 쓸 때 필요한 선택 파일로 안내 |
| D-JSON | 두 JSON의 읽기·인코딩·문법·최상위 객체 오류 | FAIL. 파일과 가능한 줄·열 표시. 종속 검사에는 미검사 사유 표시 |
| D-VERSION | 버전 부재 또는 정수 1 | WARN. 실제 훅도 V1 경로이며 V2 Quality·History 분기는 실행되지 않음을 안내. V2 검사는 미검사, 자동 마이그레이션 없음 |
| D-VERSION | 정수 2 | V2 검사 계속 |
| D-VERSION | bool·문자열·실수·0 이하·기타 잘못된 타입 | FAIL. `_hookutil.schema_version()`은 1로 대체하여 V2 분기가 꺼진다는 실제 동작과 `schema_version: 2`로 고칠 위치 안내 |
| D-VERSION | 정수 3 이상 | FAIL. 현재 스키마는 2만 지원하지만 실제 `is_v2()`는 참이라 V2 분기로 동작함을 안내. Doctor는 미지원 버전의 V2 상세 검증 생략 |
| D-CONFIG | 정수 버전 2의 핵심 구조 위반 또는 동일 profile 내 중복 stage ID | FAIL. 버전은 여기서 중복 판정하지 않음. V1에 V2 required를 강제하지 않음 |
| D-CONFIG | settings 훅 구조 오류 | FAIL. 버전에 관계없이 해당 설정 위치 안내 |
| D-PROFILE | fast/full 중 하나가 없거나 triggers/stages가 비어 있음 | WARN. 스키마상 허용되지만 해당 자동 검사가 비활성임을 명시. 둘 다 필수라고 실패시키지 않음 |
| D-TRIGGER | fast에 post_change 외의 트리거 또는 full에 stop/pre_commit 외의 트리거 | FAIL. stages가 비어 있어도 검사. 스키마 enum에 있어도 소비자가 처리하지 않는 조합 안내 |
| D-WIRING | 필수 스크립트의 직접 연결이 없거나, 해석 가능한 matcher가 필수 도구를 누락 | FAIL. 이벤트·도구·예상 경로와 원인 안내. 스크립트 연결은 확인됐으나 matcher만 미확인인 경우는 WARN이며 PASS 금지 |
| D-HOOK | 해석 가능한 명령이 프로젝트 내 존재하지 않는 훅 스크립트를 가리킴 | FAIL. 설정 항목과 끊어진 경로 안내 |
| D-HOOK | 외부·플러그인·래퍼 등 정적으로 해석하지 못하는 추가 명령 | WARN. 미확인으로 표시하며 정상 결선의 근거로 쓰지 않음 |
| D-STAGE | cwd가 프로젝트 밖·없는 디렉터리·잘못된 형식 | FAIL. 기본 cwd는 루트, 명시 값은 `_quality`와 같이 resolve 후 판단 |
| D-ARGV | 빈 실행 파일·잘못된 argv 또는 아래의 실행기 거부 조건에 맞는 인자 | FAIL. 인자가 `{`로 시작하고 `}`로 끝나며 알려진 치환값 세 개와 정확히 일치하지 않으면 거부 |
| D-ARGV | 알려진 치환값을 문자열 중간에 넣음 | WARN. 실행기가 문자열 그대로 전달하며 치환하지 않는다고 안내 |
| D-ARGV | full stage에 changed_files/mapped_targets 단독 치환값 사용 | FAIL. 두 full 트리거가 빈 목록을 전달해 항상 건너뛰는 설정임을 안내 |
| D-EXEC | 정적으로 해석한 절대 실행 경로 부재·POSIX 실행 권한 없음 | FAIL. 실행 없이 파일 확인. 상대 실행 경로는 아래 제한 적용 |
| D-EXEC | 단순 명령 이름을 Doctor 프로세스의 PATH에서 찾지 못함 | WARN. 실제 훅 프로세스의 PATH와 다를 수 있음을 안내. 발견해도 그 PATH에서만 확인한 결과로 표시 |
| D-PYTHON | python 설정 파일 부재로 다른 인터프리터 선택 | WARN. 요청 경로·실제 선택 경로·대체 순서를 출력 |
| D-TRACKED | fast/post_change나 full/stop이 활성인데 유효 추적 경로가 전혀 없음 | WARN. quality.tracked_paths → source_prefixes 대체 후에도 변경을 감지할 대상이 없음을 안내 |
| D-TRACKED | 추적 항목이 기존 디렉터리를 가리키는데 정규화 후 끝에 `/`가 없음 | FAIL. 필드·항목·영향받는 소비자와 끝에 `/`를 붙이라는 수정 안내. 실제 파일은 이 오류 대상이 아님 |
| D-MAPPING | 활성 Fast가 mapped_targets를 쓰는데 기존의 명시적 추적 파일에 대상 매핑·직접 테스트 특례·의도적 제외가 없음 | WARN. 정적으로 확정 가능한 파일만 검사하며 아래의 범위 제한 적용 |
| D-SCAFFOLD | 설정이 참조하는 추적 경로, mapping의 path/tests, History 디렉터리가 아직 없음 | WARN. 프로젝트별 경로를 그대로 안내. src/tests 등의 이름을 하드코딩하지 않음. stage.cwd 부재는 D-STAGE FAIL 유지 |

표의 해당 오류·경고가 없고 실제 확인할 수 있던 항목만 PASS다. 없는 선택 파일과 미검사는
PASS로 꾸미지 않는다. 진단을 완료한 경우에만 FAIL 존재 여부로 1/0을 결정하고,
진단 자체가 미완료이면 D-RUN의 종료 코드 2가 우선한다.

### 3. 트리거와 훅 연결 대응

triggers와 stages가 모두 비어 있지 않은 profile을 활성 대상으로 본다. 지정하지 않은
트리거를 무조건 추가하도록 요구하지 않으며, 비활성 상태는 위 경고로 알린다.
구조와 D-TRIGGER 검사는 비활성 profile에도 적용한다. 따라서 triggers가 잘못되고
stages가 비어 있으면 D-TRIGGER FAIL과 D-PROFILE WARN이 함께 나올 수 있다.

| profile / trigger | 이벤트 | 모두 덮어야 할 도구 | 프로젝트 내 스크립트 |
|---|---|---|---|
| fast / post_change | PostToolUse | Write, Edit, Bash, PowerShell | `.claude/harness/hooks/auto_test_check.py` |
| full / stop | Stop | 도구 matcher 검사 없음 | `.claude/harness/hooks/auto_test_check.py` |
| full / pre_commit | PreToolUse | Bash, PowerShell | `.claude/harness/hooks/pre_commit_check.py` |

동일 이벤트의 여러 group/hook을 합쳐 도구별로 연결을 찾는다. matcher는 다음 순서로 처리한다.

- 누락·빈 문자열·`*`는 정규식 컴파일 전에 모든 도구에 적용한다.
- 영문자·숫자·`_`·`-`·공백·`,`·`|`만 있는 값은 이름 목록으로 읽는다. `|` 또는 `,`로
  나누고 각 항목의 주위 공백을 제거해 도구 이름과 정확히 비교한다.
- 그 외는 정규식 경로다. JavaScript와 의미가 같은 공통 문법에 한해 Python `re.search`로
  부분 일치를 확인하며, fullmatch를 강제하지 않는다. JS 전용 문법 등 동등성을 확인할 수
  없는 패턴은 미확인 WARN으로 남긴다. Python 컴파일 실패만으로 JS 문법 오류라고 FAIL하지
  않는다. 공통 문법에서도 명백히 깨진 패턴(예: 닫히지 않은 `[`)은 해당 위치의 FAIL이다.

전체 적용 특례는 원본 matcher가 누락·`""`·`"*"`일 때만 적용한다. `" "`나 `" * "`를
strip해서 전체 적용으로 바꾸지 않는다. 목록 항목의 주변 공백 제거와 이 특례는 구분한다.
Python에서 컴파일된다는 사실만으로 JS와 동등하다고 보지 않는다. 지원하는 공통 문법을
한정하고, 전역 `(?i)`·possessive quantifier 등 JS가 거부하는 문법이 PASS로
흘러가지 않게 한다. 구체적인 반례와 회귀 기준은 아래 R2-02를 따른다.
단, 전역 `(?i)`와 범위가 있는 `(?i:...)`는 다르다. JavaScript의 유효한 `i`·`m`·`s`
modifier 그룹을 「Python 전용 문법」이라고 FAIL하지 않는다. 이번 구현은 해당 scoped
modifier를 지원 부분집합 밖의 UNKNOWN/WARN으로 남기며, 전체 JS 지원을 추가하지 않는다.
자세한 근거와 회귀 기준은 R3-04를 따른다.

다른 이벤트의 같은 파일이나 같은 basename만으로 통과시키지 않고, 정규화한 전체 프로젝트
경로와 `type: command`를 함께 확인한다. matcher를 해석하지 못해 필수 결선을 입증할 수
없으면 D-WIRING WARN으로 확인 불가 원인을 명시하며, 미확인 matcher만으로 PASS하지 않는다.
JS에서도 잘못됐다고 확정할 수 있는 패턴은 FAIL이며 단순 미확인과 구분한다.

settings의 hooks는 없으면 빈 객체로 보고, 있으면 객체여야 한다. 각 이벤트 값은 group 배열,
각 group은 hooks 배열을 가진 객체이고 matcher가 있으면 문자열이어야 한다. 각 hook도
비어 있지 않은 문자열 type을 가진 객체여야 하며, command 타입의 command는 비어 있지 않은
문자열이어야 한다. 이 기본 구조 오류는 D-CONFIG FAIL이며 내부 오류/2로 처리하지 않는다.
기존 프로젝트의 추가 설정·이벤트·비 command 훅을 삭제하거나 일괄 오류로 만들지 않는다.
해석 범위 밖의 훅은 미확인으로 안내한다.
스크립트 존재 확인인 D-HOOK은 품질 훅에 한정하지 않고, 모든 이벤트에 연결된 해석 가능한
프로젝트 내부 스크립트를 대상으로 한다. 필수 연결 확인인 D-WIRING만 위 세 행으로 한정한다.
현재 파일에 없는 나머지 훅을 일괄 복원하거나 설치하도록 요구하지 않는다.

직접 Python 호출(`python`, `python3`, `py -3`, 따옴표로 감싼 Python 실행 파일 경로)과
따옴표 유무가 다른 스크립트 경로를 처리한다. 이 저장소의
`python "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/<파일>.py"`는 필수 지원 형식이다.
여기서 `${CLAUDE_PROJECT_DIR}`는 대상 루트로 정적으로 치환한다. 스크립트의 프로젝트
상대 경로와 현재 OS의 절대 경로, 공백·한글 경로를 지원한다. basename만 일치하는 외부
파일은 하네스 결선이 아니다. 셸 연산자·변수·래퍼를 실행하거나 임의로 풀어 추측하지 않는다.
해석 불가 명령은 WARN이며, 그것만으로 필수 연결이 성립한다고 PASS하지 않는다.
`.py`로 끝나는 인자가 있다는 사실은 그 스크립트를 실행한다는 증거가 아니다. Python의
실제 스크립트 실행 위치를 확인한 직접 호출만 인정한다. `-c`·`-m`·`--version`·도움말 모드,
모르는 실행 옵션, 셸 주석·치환 때문에 호출 대상을 확정하지 못하면 해당 경로를 결선에
사용하지 않는다. 스크립트 이후의 임의 `.py` 인자를 실행 대상으로 다시 선택하지 않는다.
토큰화에서는 `""`·`''`도 빈 인자 하나로 보존한다. 첫 스크립트 인자가 비었다고 다음
인자를 실행 대상으로 당기거나 프로젝트 루트 경로로 해석하지 않는다. 빈 값이 옵션의
값이거나 스크립트 뒤 인자일 수 있으므로, 모든 빈 인자를 일괄 거부하지 않고 위치로 구분한다.

### 4. stage와 환경의 정적 점검

- stage의 id는 스키마 패턴, argv는 비어 있지 않은 문자열 배열이며 첫 항목은 비어 있을 수
  없다. timeout은 bool이 아닌 1~3600 정수(기본 120), success_codes는 bool을 제외한
  정수의 비어 있지 않은 중복 없는 배열(기본 [0]), label은 비어 있지 않은 문자열(기본 id).
  리스트 치환값을 실행 파일 자리(argv[0])에 둔 경우도 D-ARGV FAIL이다.
- 인자별 거부 조건은 실행기와 동일한
  `arg.startswith("{") and arg.endswith("}") and arg not in _KNOWN_PLACEHOLDERS`다.
  `_KNOWN_PLACEHOLDERS`는 `{python}`, `{changed_files}`, `{mapped_targets}`다.
  `{unknown}`·`{a}x{b}`·`{}`는 FAIL이다. 거부 조건을 먼저 적용한 뒤, 알려진 치환값이
  들어 있지만 정확히 한 항목 전체가 아닌 `{python} --version`·`--opt={python}`는 WARN으로
  표시한다. 후자는 값이 그대로 전달되는 경우이며 치환값 검사 자체로 FAIL하지 않는다.
- `{python}`은 `_hookutil.venv_python`의 파일 선택 순서를 그대로 설명·재현한다. PATH에서
  설정의 python 값을 임의로 찾지 않는다. 최종 선택이 현재 프로세스라면 sys.executable을
  표시한다. 이 점검은 `{python}`을 쓰는 stage가 있을 때만 필수이며, 없는 `.venv`나
  python 설정만으로 다른 언어 프로젝트를 실패시키거나 환경 생성을 요구하지 않는다.
- 인터프리터를 표시할 때 항상 「Doctor의 루트 기준 선택」이라고 밝힌다. 실제 훅은
  `CLAUDE_PROJECT_DIR`/cwd에서 찾은 루트를 쓰므로 중첩 프로젝트·다른 환경변수 값에서는
  선택이 달라질 수 있다. Doctor가 실제 훅의 루트·인터프리터까지 관찰했다고 표시하지 않는다.
- 절대 실행 파일 경로는 존재와 현재 OS에서 확인 가능한 실행 권한, 단순 명령 이름은
  `shutil.which`로 검사한다. 조회한 PATH는 Doctor 프로세스의 것이며, 못 찾으면 WARN이다.
  찾은 경우도 그 환경에서 확인한 경로를 출력한다. 상대 실행 파일은 stage.cwd 기준 후보와 함께
  WARN으로 표시한다. Windows/POSIX의 실제 프로세스 경로 해석까지 검증한 것으로
  표시하지 않는다. 다른 OS의 절대 경로를 현재 OS의 PATH 명령 이름으로 오인하지 않는다.
- `{changed_files}`·`{mapped_targets}`는 동적 입력이다. 더미 파일을 만들어 채우거나
  실제 변경을 수집하지 않는다. Fast의 입력이 현재 없다는 사실만으로 stage가 깨졌다고
  단정하지 않는다. 설정된 mapping 경로의 부재는 D-SCAFFOLD 경고로만 처리한다.
- D-TRACKED의 디렉터리 접미사 검사는 quality.tracked_paths와 history.tracked_paths,
  그리고 실제로 대체에 쓰이는 source_prefixes/harness_paths에 적용한다. 런타임과 같이
  역슬래시를 `/`로 바꾸고 앞의 `./`와 `/`를 처리한 뒤 파일·디렉터리 구분을 검사한다.
  quality의 오류는 Fast와 Stop의 변경 감지, history의 오류는 V2 History 변경 감지에
  영향을 준다고 해당 필드별로 설명한다. 파일·디렉터리가 모두 없으면 FAIL로 추정하지 않고
  D-SCAFFOLD WARN으로 남긴다. `tests`를 `tests/`로 자동 수정하지 않는다.
  quality는 유효한 quality.tracked_paths가 있을 때 source_prefixes를 대체에 쓰지 않는다.
  history도 유효한 history.tracked_paths가 있으면 source_prefixes/harness_paths를 대체에
  쓰지 않는다. 각각의 실제 선택을 먼저 계산하며, 어느 쪽에서도 선택되지 않은 fallback
  항목의 접미사를 이유로 D-TRACKED FAIL을 만들지 않는다. 구조 오류 검사는 이와 별개다.
- D-MAPPING은 활성 fast/post_change stage에 `{mapped_targets}`가 있을 때만 검사한다.
  명시된 추적 항목이 기존 파일일 때 `test_target_for()`처럼 의도적 제외를 먼저 확인하며,
  unmapped_by_design에 해당하면 이 경고에서 제외한다. 나머지는 직접 테스트 특례
  (`tests/` 아래 `test_*.py`)와 최장 접두사 매핑으로 대상이 나오는지 확인한다.
  확정적으로 대상이 없는 파일만 WARN으로 보고한다. 디렉터리
  전체·부분 중첩 매핑의 커버리지는 증명하지 않으며 하위 파일 전수 탐색이나 설정 수정은 없다.
- `python -m ruff`·`pytest` 등의 모듈 설치 상태와 버전은 실행하지 않으므로 **미검증**이다.
  어떤 언어·린터·테스트 도구도 하드코딩해 필수로 만들지 않는다. 결선 PASS는 명령 실행
  성공을 뜻하지 않으며 이 한계를 출력과 README에 명시한다.
- History 저장 경로는 wiki_root와 history의 현재 상대 경로 규약을 따라 표시한다.
  빈 History나 디렉터리 부재는 설치 실패가 아니다. 기록·.gitkeep을 생성하지 않는다.

### 호환성과 보안·비용 경계

V1에서는 공통 파일·JSON·해석 가능한 훅 경로만 점검하고 V2 구조·stage·트리거 점검은
미검사 경고로 남긴다. 버전 판정은 위 표대로 하며 기존 실행기의 V1/V2 분기를 바꾸지 않는다.
V2 스키마와 실행기보다 엄격한 부분은 명시된 정적 진단뿐이다. 비활성 설정은 경고로,
무시되는 잘못된 조합과 항상 건너뛰는 full stage는 실패로 구분한다.

보안·비용 경계는 명령을 실행하지 않는 것이다. 유료 테스트의 제외 정책·사용자 승인·실제
세션의 훅 활성 여부는 이 CLI의 보장 대상이 아니다. 공유 settings 외의 사용자·로컬·관리자
설정과 활성화 상태도 읽거나 병합하지 않는다. 출력에서 공유 파일만 검토했음을 명시한다.

## 구현 및 검증

Claude는 구현 전 이 명세와 현재 코드를 검토해 충돌·수정 제안을 같은 ID의 리뷰에 쓴다.
막는 지적이 없고 구현이 승인되면 스크립트·테스트·README·Knowledge를 구현한다.

`tests/test_doctor.py`는 임시 프로젝트에서 다음을 검증한다. 현재 저장소에만 기대는
스냅샷 테스트나 구현 함수 호출 여부만 복제한 테스트로 대신하지 않는다.

1. 정상 V2의 PASS/종료 0, WARN만 있는 설정의 종료 0, 여러 FAIL의 종료 1과 독립 검사 계속.
   필수 파일 부재, BOM JSON, 손상된 JSON, 최상위 배열·잘못된 중첩 타입에서도 traceback 없음.
   잘못된 스크립트 배치·루트 접근 실패·내부 오류는 「진단 미완료」와 종료 2이며, JSON 오류의
   종료 1과 구별한다. 사용자 데이터에서 예상 가능한 오류를 내부 오류로 숨기지 않는다.
2. 버전 부재/1/2/미지원/잘못된 타입과 스키마의 필수·선택 구분. 빈·누락 profile은 WARN,
   잘못된 trigger 조합·중복 stage ID·timeout·success_codes·argv 오류는 FAIL.
   공통 파일이 갖춰진 V1 `{}` 또는 V1 키만 있는 fixture는 WARN/0, 같은 설정에 정수 2만
   추가하면 누락된 V2 구조는 FAIL/1이다. `"2"`, `2.0`, `true`, `0`, `-1`, null의 FAIL/1은
   V1 대체와 V2 분기 비활성을 설명하고, `3`의 FAIL/1은 실제 V2 분기 활성과 스키마 미지원을
   설명한다. stages가 비어도 잘못된 trigger 조합은 FAIL이다.
3. 각 연결을 제거하거나 잘못된 이벤트·부분 matcher·외부 동명 파일로 바꾸면 FAIL.
   여러 group으로 나눈 정상 연결, Bash/PowerShell 양쪽, 병합된 외부 훅은 오판하지 않는다.
   matcher의 누락·빈 값·`*`, `Write, Edit` 같은 목록, 정규식의 부분 일치를 각각 검증한다.
   공통 문법 오류와 해석 불가 JS 패턴을 구분한다. 품질 훅이 아닌 해석 가능한 내부 스크립트
   하나가 없어도 D-HOOK FAIL이다. custom wiki_root와 JSON 오류 때 Wiki 미검사도 확인한다.
4. 공백·한글 경로, 직접 호출 형식, 해석 불가 래퍼, cwd 이탈·부재, PATH 이름 부재,
   Python fallback, 다른 언어의 품질 도구와 선택 가상환경. placeholder의 단독/중간 삽입,
   Fast 동적 입력 부재와 full의 항상 skip되는 목록 치환도 구분한다.
   PATH 이름 부재는 WARN이며 조회 환경을 명시한다. 인자 위치를 나눠 `{a}x{b}`, `{}`,
   `{unknown}`의 FAIL과 `{python} --version`, `--opt={python}`의 치환 미적용 WARN을 확인한다.
   quality와 history 각각의 기존 디렉터리 `src`·`tests`는 끝의 `/` 누락 FAIL, `src/`·`tests/`와
   실제 파일은 그 검사에 통과한다. 아직 없는 항목은 WARN이고 fallback 추적 항목도 검사한다.
   D-MAPPING은 명시 추적 파일의 누락 매핑을 WARN으로 알리되 직접 테스트·의도적 제외·정상
   매핑·mapped_targets를 쓰지 않는 Fast에서는 오탐하지 않는다.
5. A 프로젝트 cwd·CLAUDE_PROJECT_DIR에서 B 프로젝트의 Doctor를 절대 경로로 실행하면
   B만 진단한다. Git 없는 임시 프로젝트도 진단하며 Git 프로세스를 실행하지 않는다.
   두 프로젝트에 각각 `.claude/`가 있어도 같다. 인터프리터 선택은 Doctor 루트 기준임과
   실제 훅의 환경변수 기반 루트와 다를 수 있음을 출력한다.
6. Doctor 실행 전후 대상 프로젝트의 파일 목록·내용을 비교한다. 실행·import되면 파일을
   쓰는 가짜 훅·stage를 둬도 흔적이 생기지 않고, 진단 코드가 자식 프로세스를 만들지
   않았음을 별도로 확인한다. CLI 테스트 자체의 Python 실행은 이 금지와 구분한다.
7. 현재 OS에서 경로·실행 권한을 검증한다. 반대 OS의 경로 분류는 순수 입력 테스트와
   실제 OS 실행 검증을 구분한다. Linux 실행 환경이 없으면 미검증으로 명확히 보고한다.

영향 테스트는 지정 인터프리터로 `-m pytest tests/test_doctor.py -q`를 직접 실행한다.
새 스크립트는 현재 Fast 추적 경로 밖이므로 자동 Fast로 검증됐다고 주장하지 않는다.
이 범위 유지는 의도적이며 이번 작업에서 자동 추적 경로나 매핑을 추가하지 않는다.
완료 전 Full의 lint·format 검사·전체 pytest를 실행한다. 실제 명령·종료 코드·통과 수와
실행하지 않은 검사 및 이유를 리뷰에 남긴다. 현재 405개 통과 기록을 새 변경의 결과로
재사용하지 않는다. 범위 밖 실패는 별도 지적으로 구분하며 기준을 완화해 통과시키지 않는다.

## 완료 기준

1. 표의 입력별 판정과 정상 진단 0/1·진단 미완료 2가 테스트로 확인되며,
   경고와 미검사를 성공 확인으로 출력하지 않는다.
2. 활성 트리거의 끊어진 결선·잘못된 stage는 설정 위치와 수정 안내를 내고 종료 1이다.
   비활성 profile, 새 프로젝트의 미생성 대상, V1은 명시된 경고로 구별된다.
3. 어느 cwd에서든 스크립트가 속한 프로젝트를 진단하고, Git·별도 패키지 없이 동작한다.
   진단 중 대상 파일 쓰기와 설정 명령 실행이 없다는 검증이 있다.
4. README에 설치·병합 후 실행할 명령, FAIL/WARN과 종료 코드 0/1/2, 정적 점검의 한계가 있다.
   현재 계약은 Knowledge에 한국어로 보존되고, 필요한 결정 이유만 기존 Plan 절차로 남긴다.
5. Claude의 새 검증 보고를 Codex가 완료 기준과 대조해 최종 승인한다. 구현만으로 이 명세를
   삭제하지 않으며, 두 임시 파일은 최종 리뷰·검증·보존 조건을 충족한 뒤 Claude가 정리한다.

## Codex 명세 재검토 — 2026-11-22

판정: 기존 방향은 유지하되, 아래 구현 전 명세 누락을 이 파일에 반영했다. 현재는 설계
재검토이며 구현 완료 판정이 아니다. 실제 Doctor 실행·구현 테스트 결과도 아직 없다.

| 지적 | 기존 위치·근거 | 반영한 수정과 확인 기준 |
|---|---|---|
| DR-01 · P1 | 점검 범위 2~3. 스키마만으로 profile 비활성·소비자가 무시하는 trigger·항상 skip되는 full을 구별할 수 없음 | 심각도와 실제 소비자 대응표 추가. 빈 profile은 WARN, 무효 조합·full 목록 치환은 FAIL인 테스트 요구 |
| DR-02 · P1 | 점검 범위 3. 경로 추출·matcher·병합 group의 기준 부재 | 전체 경로와 도구별 결선을 판정. 외부 동명 파일·부분 연결·다른 이벤트를 PASS하지 않는 테스트 요구 |
| DR-03 · P2 | 점검 범위 2·4와 실행 계약. 버전 호환과 fallback·정적 검증의 한계 불명확 | V1/미지원 버전·Python 대체·미설치 모듈의 미검증을 명시. cwd/env 격리와 무실행 테스트 요구 |
| DR-04 · P2 | 완료 기준. 삭제·영구 계약 보존·새 품질 검사 결과의 기준 누락 | 반증 가능한 완료 기준과 검증 주체·보존 조건 추가. 현재 구현 대기 상태를 명시 |

이번 변경은 명세만 수정한다. 코드·하네스 설정 변경이 없어 Fast 대상이 없으며 Full도
재실행하지 않는다. 저장 후 명세 재독과 diff·공백 검사를 수행한다. 새 구현과 품질 검증은
Claude가 같은 ID의 리뷰에 보고한다.

## Claude 구현 전 리뷰 반영 — 2026-11-22

대상은 `tasks/doctor.review.md`의 C-01~C-12 및 질문 4개다. 보고는 구현 전 검토가
끝났고 아직 구현하지 않았다고 명시하므로, 이 명세만 수정했다. 리뷰 원본·공통 절차·구현
파일은 수정하지 않는다. 현재 코드의 해당 분기와 공식 matcher 문서를 대조했으며,
Claude가 보고한 probe 결과를 Codex가 독립 재실행한 것으로 표시하지 않는다.

판정: 차단 지적 C-01~C-04를 모두 채택해 요구사항과 검증 기준에 반영했다. 나머지는
아래와 같이 채택·부분 채택했다. 이는 명세 보완이며 구현 완료나 품질 검사 통과 판정이 아니다.

| 지적 | 결정 | 반영 내용과 검증 기준 |
|---|---|---|
| C-01 · P1 | 채택 | 잘못된 버전의 FAIL에 실제 V1 대체/V2 활성 분기를 출력. 정상 V1의 WARN은 유지. 버전별 메시지와 종료 코드 테스트 |
| C-02 · P1 | 채택 | 버전 판정은 D-VERSION 소유. V1/미지원 버전에 V2 required 검사를 중복 적용하지 않음. V1 `{}`와 정수 2 fixture의 0/1 구별 |
| C-03 · P1 | 채택 | quality·history와 실제 fallback 항목에서 기존 디렉터리의 끝 `/` 누락을 FAIL. 필드별 영향·수정 방법, 실제 파일과 미생성 경로 구별 |
| C-04 · P1 | 채택 | `_quality.py:131`의 거부 조건을 그대로 명시. `{a}x{b}`·`{}`·`{unknown}`은 FAIL, 삽입된 알려진 치환값은 그 검사에서 WARN |
| C-05 · P2 | 부분 채택 | `*` 특례는 채택. fullmatch 유지 제안은 공식 문서와 달라 채택하지 않음. 정확한 이름 목록과 JS 정규식 부분 일치·해석 한계로 구분 |
| C-06 · P2 | 채택 | 단순 명령의 PATH 조회 실패를 WARN으로 조정. Doctor PATH에서 확인한 결과이며 실제 훅 환경은 미검증이라고 출력 |
| C-07 · P2 | 채택 | Python 선택은 Doctor 루트 기준임을 항상 설명. 실제 훅 루트와 달라질 수 있다는 한계 및 중첩 프로젝트 테스트 추가 |
| C-08 · P2 | 채택 | Wiki README는 wiki_root 기준. JSON/필수 wiki_root 오류가 있으면 종속 파일 검사는 미검사. custom Wiki와 손상된 JSON 테스트 |
| C-09 · P2 | 채택 | 저장소 로컬 배포 전제와 자기 배치 검사 추가. 과거 플러그인 훅의 루트 결정은 유지. 잘못된 배치는 진단 미완료/2 |
| C-10 · P3 | 채택 | 경로 이름을 설정 참조로 일반화. stage.cwd 부재의 기존 FAIL은 유지하고 scaffold WARN과 구별 |
| C-11 · P3 | 부분 채택 | 정적으로 확정 가능한 기존 추적 파일의 매핑 누락만 WARN. 디렉터리 전체 커버리지나 부분 중첩 매핑의 완전성은 보장하지 않음 |
| C-12 · 참고 | 현행 유지 | 단일 doctor.py와 기존 import 경로 유지. 패키지로 이동하지 않으며 배치 검사로 깊이 결합을 명시 |

| 질문 | 확정한 답 |
|---|---|
| 1. Doctor 자체 실패의 종료 코드 | 시작 후 진단 자체를 완료하지 못하면 2. 발견 사항은 0/1. Python 미시작은 CLI 통제 밖 |
| 2. 비품질 훅도 검사하는가 | 모든 해석 가능한 내부 연결 스크립트에 D-HOOK 적용. 필수 결선 D-WIRING만 세 행으로 제한 |
| 3. 새 스크립트의 자동 Fast 미포함 | 의도적으로 유지. 영향 테스트 직접 실행과 Full을 요구하며 자동 추적 확대는 포함하지 않음 |
| 4. stages가 없는 profile의 잘못된 trigger | D-TRIGGER는 여전히 FAIL. 비활성 경고와 구성 오류는 함께 보고할 수 있음 |

남은 일은 Claude의 수정 명세 확인, 승인 범위의 구현과 새 검증 보고다. 이번에는 명세만
수정해 Fast·Full을 실행하지 않았다. 저장한 명세 재독·diff·공백 검사로 반영을 확인한다.

## Codex Round 2 결과 리뷰 — 수정 요청 (2026-11-22)

대상은 `main` / `bd89a04` 작업 트리의 구현·테스트·README·Knowledge·Plan 문서와
`tasks/doctor.review.md`의 Round 2다. Claude의 구현·보고 단계가 끝난 결과를 검토했다.
**판정은 완료 승인 보류다.** 기존 C-01~C-04에 대한 기본 구현은 확인됐지만, 아래의
실행 가능한 반례 4건이 남아 완료 기준 1·2를 충족하지 못한다. 보존·임시 파일 삭제 단계로
넘기지 않는다. Codex는 이 명세만 수정하며 구현·테스트·리뷰·영구 문서는 Claude가 고친다.

### 독립 검증 결과

| 검증 | Codex가 직접 확인한 결과 |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_doctor.py -q` | 128 passed, 1 skipped, 4.20초 |
| `.venv/Scripts/python.exe -m ruff check .` | All checks passed, 종료 0 |
| `.venv/Scripts/python.exe -m ruff format --check .` | 71 files already formatted, 종료 0 |
| `.venv/Scripts/python.exe -m pytest -q` | 533 passed, 1 skipped, 12.95초 |
| 현재 저장소의 Doctor 실행 | PASS 24 · WARN 5 · FAIL 0, 종료 0 |
| 추가 임시 프로젝트 probe | 정상 fixture를 기준으로 아래 한 조건씩 바꿔 CLI 종료 코드와 findings 재현 |

skip 1건은 POSIX 실행 권한 검사다. Linux에서는 재실행하지 않았으며 Windows 결과로
대체하지 않는다. 기존 테스트가 모두 통과하는 것과 추가 반례가 없다는 것은 별개다.
아래 반례는 기존 테스트의 fixture를 임시 디렉터리에 구성했고 작업 트리의 구현을 바꾸지
않았다. 정규식의 JS 거부 여부는 별도 JavaScript 엔진의 `new RegExp`로 확인했다.

### R2-01 · P1 · 실행하지 않는 `.py` 인자를 훅 연결로 인정함

- 위치: `.claude/harness/scripts/doctor.py:907`~`:914`의 `parse_command`,
  `:1166`의 필수 연결 후보 선택.
- 재현: 정상 fixture의 훅 명령 각각을
  `python -c pass "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/<스크립트>.py"`로 바꾼다.
  `python -m not_a_hook "<스크립트>.py"`, `python --version "<스크립트>.py"`도 같다.
- 실제 결과: 세 경우 모두 CLI 종료 0, D-WIRING 세 행 전부 PASS다. Python은 이 모드에서
  그 파일을 스크립트로 실행하지 않는다. 현재 코드는 뒤의 인자 중 첫 `.py`를 찾아 인정한다.
- 기대 동작: 지원하는 Python/py 직접 호출 문법에서 실행 파일과 스크립트 위치를 구분한다.
  `-c`·`-m`·버전/도움말 모드 및 미지원 옵션을 임의로 스크립트 호출로 추정하지 않는다.
  명령은 D-HOOK 미확인 WARN, 이 명령만으로 남은 필수 연결은 D-WIRING FAIL/종료 1이어야 한다.
  셸 해석기로 확장하거나 설정 명령을 실행해 확인하지 않는다.
- 검증 기준: 위 세 부정 사례와 스크립트 뒤 다른 `.py` 인자·주석 사례를 추가한다. 기존
  python/python3/py -3, 인용한 경로, 공백·한글 경로의 실제 직접 호출은 계속 통과해야 한다.

### R2-02 · P1 · Python 정규식과 JS matcher의 차이를 PASS로 숨김

- 위치: `.claude/harness/scripts/doctor.py:108`의 `_PY_ONLY_SYNTAX`,
  `:967`~`:984`의 `matcher_covers`.
- 재현: 필수 matcher를 `(?i)Write|Edit|Bash|PowerShell`로 바꾸면 Doctor는 네 도구를 모두
  덮는다고 판정하고 CLI 종료 0·D-WIRING PASS를 낸다. 그러나 JavaScript `new RegExp`는
  Invalid group으로 거부한다. `Bash++`도 Doctor는 Bash 일치, JS는 Nothing to repeat 오류다.
  또한 `" * "`는 Doctor에서 전체 적용이지만 JS 정규식은 Write에 일치하지 않는다.
- 기대 동작: 불일치 문법을 몇 개 배제한 뒤 Python이 받아들이는 나머지를 전부 공통 문법으로
  인정하지 않는다. 정적으로 지원할 수 있는 공통 범위를 한정한다. 위 두 JS 오류 사례는
  FAIL/종료 1이며, 유효성을 확정하지 못한 JS 구문은 미확인 WARN으로 남기되 PASS 근거로
  쓰지 않는다. wildcard 특례 전에 원본 matcher를 strip하지 않는다.
- 검증 기준: 위 세 반례, 공백뿐인 이름 목록, 정확한 `*`/빈 값/누락, `Write, Edit`,
  `[Ww]ri`의 부분 일치, 미확인 JS 문법을 구분한다. JavaScript를 Doctor 런타임 의존성이나
  자식 프로세스로 추가하지 않는다. 단순 차단 목록을 늘린 것만으로 일반 동등성을 주장하지 않는다.

### R2-03 · P2 · 명시적으로 검증하기로 한 스키마 필드의 값 타입을 누락함

- 위치: `.claude/harness/scripts/doctor.py:499`~`:506`과 `:530`~`:538`.
- 재현: 정상 fixture에 `quality.unmapped_by_design: {"src/": 42}`를 넣거나,
  `quality.mappings[0].why: []`를 넣어도 각각 D-CONFIG FAIL이 없고 CLI 종료 0이다.
- 근거: `harness.schema.json:59`~`:61`은 unmapped_by_design의 각 값을 문자열로 제한하며,
  `:54`도 why를 문자열로 제한한다. 이는 전체 스키마 검증 확대가 아니라 이 명세가 이미
  점검 대상으로 정한 quality/mappings의 타입 계약이다.
- 기대 동작: 객체 자체의 타입과 필수 path/tests만 검사하고 끝내지 않는다. 해당 값의
  스키마 타입을 필드별 D-CONFIG FAIL/종료 1로 보고한다. 유효한 문자열과 optional why의
  부재는 허용하고, 스키마가 허용하는 빈 문자열을 임의로 거부하지 않는다.
- 검증 기준: 두 반례와 정상 값의 테스트를 추가한다. 스키마 상수 일치 테스트만으로 실제
  값 검증이 동작한다고 주장하지 않는다. 같은 명시 점검 범위에 다른 타입 누락도 없는지 확인한다.

### R2-04 · P2 · 사용되지 않는 fallback 항목도 현재 게이트 오류로 단정함

- 위치: `.claude/harness/scripts/doctor.py:1508`~`:1529`의 모든 필드 순회.
- 재현: 실제 src/tests 디렉터리를 갖춘 정상 fixture에서 quality와 history의 tracked_paths는
  `["src/", "tests/"]`로 유지하고 source_prefixes만 `["src"]`, harness_paths만 `["tests"]`로
  바꾼다. 실제 두 소비자는 명시한 tracked_paths를 쓰지만 Doctor는 fallback 두 항목을
  FAIL로 보고하고 「변경 감지가 꺼진다」며 종료 1을 낸다.
- 기대 동작: quality/history의 실제 fallback 선택을 먼저 계산한다. 명시적 tracked_paths가
  선택됐을 때 미사용 fallback의 접미사 때문에 실패시키지 않는다. 미래에 사용될 수 있다는
  안내가 필요하면 비차단 WARN으로 구분하고 현재 게이트가 꺼졌다고 단정하지 않는다.
- 검증 기준: 위 fixture는 접미사 검사에서 FAIL하지 않는다. 반대로 quality/history의
  tracked_paths를 비워 실제 fallback이 선택되면 같은 디렉터리 항목은 FAIL이어야 한다.
  두 소비자 중 한쪽만 fallback을 쓰는 조합도 검사하고, 현재 `_v2_tracked_paths()`와
  `history_check.tracked_paths()`의 선택 순서에 맞춘다.

### Round 2의 판단 요청 7건에 대한 결정

| 번호 | 결정 |
|---|---|
| 1. D-EXEC에 적용 대상이 없음 | WARN 유지 허용. D-PYTHON의 별도 검사와 구분하고 설치 실패로 안내하지 않는다. PASS로 꾸미지 않았으므로 차단 지적 아님 |
| 2. 명백한 정규식 오류의 범위 | 짝 오류만 확정 실패로 보는 보수적 출발은 허용. 그 외 패턴을 Python이 컴파일했다고 동등하다고 보는 부분은 R2-02 수정 필요 |
| 3. JS/Python 불일치 문법 목록 | 현재 목록은 불충분. R2-02의 실제 오판을 고치고 지원 부분집합과 미확인 처리를 명확히 한다 |
| 4. 명시 null과 부재 구별 | 채택. 부재는 V1 호환 WARN, null은 잘못된 명시 값이라 FAIL. 두 경우의 실제 V1 대체 설명은 유지 |
| 5. 해석 불가 셸 연산자·변수 | 보수적으로 미확인 처리하는 방향은 채택. R2-01에서 실행 옵션과 스크립트 위치를 구분해야 하며 단순 토큰 발견은 결선 증거가 아님 |
| 6. 네 추적 필드를 무조건 FAIL 검사 | 채택하지 않음. 명세의 「실제로 대체에 쓰이는」 조건을 R2-04처럼 구현한다 |
| 7. unmapped_by_design의 dict/list 재현 | 허용. V2의 list는 D-CONFIG FAIL로 구분하므로 재현 함수의 관대한 읽기 자체는 차단 사유가 아님. dict 값의 타입 누락은 R2-03 |

### 완료·문서·후속 검증

- 현재 완료 기준은 충족하지 못했다. Claude는 R2-01~R2-04를 같은 구현·테스트에서 고치고
  회귀 사례와 실제 재실행 결과를 Round 3에 보고한다. 첫 구현에서 발견한 지적이므로 아직
  같은 결함의 수정 실패로 세지 않는다. 모델 상향을 자동 요구하지 않는다.
- README와 Knowledge의 기본 실행 방법·비용 경계·0/1/2 계약은 확인됐다. 수정한 matcher와
  fallback 판정은 Knowledge에도 일치시킨다. Plan의 결정 이유는 유지하되, 검사하지 않은
  복제 로직을 「테스트로 대조했다」는 표현은 실제 검증 범위와 맞춘다.
- 진단 런타임에서 `_hookutil` import를 금지한 것과, 테스트에서 기존 load_hook fixture로
  비교하는 것은 다르다. 복제 계약 비교 테스트는 가능하다. 미래의 drift 가능성 자체를
  이번 차단 근거로 세지는 않는다.
- 일반 테스트 성공을 별도 Verify History로 남기지 않은 판단은 허용한다. 보존 커밋이나
  영구 계약 갱신 전에는 임시 파일을 삭제하지 않는다. 현재 새 파일은 미추적이며,
  Codex의 이번 수정 판정도 아직 보존 커밋에 들어 있지 않다.
- 수정 후 영향 테스트와 Full을 새로 실행한다. 현재 533 passed는 수정 전 구현의 결과다.
  Codex는 위 기존 검사와 추가 probe를 실행했으며 구현·테스트·리뷰·영구 문서는 수정하지 않았다.
  이 명세 저장 뒤 재독·diff·공백 검사로 판정과 남은 작업을 확인한다.

## Codex Round 3 결과 리뷰 — 수정 요청 (2026-11-22)

확인 대상은 `main` / `bd89a04`의 작업 트리와 리뷰 파일의 Round 3 사전 검토·구현 보고
두 절이다. 구현·보고 종료 상태에서 실제 수정 함수, 추가 테스트, README, Knowledge와
Plan 갱신을 대조했다. **최종 완료 승인은 보류한다.** 기존 반례에 대한 수정은 대부분
확인됐지만, R2-01의 실행 대상 오인과 신규 R3-04의 정상 설정 오탐이 재현됐다.
Codex는 명세만 수정하며 Claude 소유의 구현·테스트·리뷰·영구 문서는 수정하지 않는다.

### 독립 검증과 완료 기준

| 검증 | Codex가 직접 확인한 결과 |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_doctor.py -q` | 210 passed, 1 skipped, 8.51초 |
| `.venv/Scripts/python.exe -m ruff check .` | All checks passed, 종료 0 |
| `.venv/Scripts/python.exe -m ruff format --check .` | 71 files already formatted, 종료 0 |
| `.venv/Scripts/python.exe -m pytest -q` | 615 passed, 1 skipped, 15.94초 |
| 기존 R2-01 명령 3종을 넣은 임시 프로젝트 CLI | `-c pass`·`-m not_a_hook`·`--version` 모두 D-WIRING FAIL, 종료 1로 개선 |
| 새 경계 사례 | 아래의 빈 스크립트 인자와 scoped modifier를 각각 CLI로 재현 |

skip은 POSIX 실행 권한 테스트이며 Linux는 여전히 미검증이다. 기존 테스트 통과가 아래
추가 반례의 해소를 뜻하지 않는다. 테스트용 임시 프로젝트에서 실행 대상을 확인했으며
저장소의 훅 설정이나 구현 파일을 바꾸지 않았다.

| 완료 기준 | 현재 판정 |
|---|---|
| 1. 입력별 판정·종료 코드 | 미충족. 정상·비정상 설정의 반대 판정 2건이 남음 |
| 2. 실제로 끊긴 결선과 잘못된 stage 감지 | 미충족. 빈 스크립트 인자로 끊긴 결선을 PASS함 |
| 3. 자기 루트·표준 라이브러리·읽기 전용 | 구현과 관련 테스트에서 확인. 런타임 훅 import 금지도 유지 |
| 4. README·Knowledge·필요한 결정 보존 | 문서 존재와 갱신 확인. R3-04의 잘못된 문법 설명은 수정 필요 |
| 5. 최종 승인·보존 뒤 정리 | 미충족. 미해결 지적과 미추적 파일이 있으므로 임시 파일 유지 |

### 기존 지적과 새 보고의 처리

| 항목 | 판정 |
|---|---|
| R2-01 | 부분 해소. 실행 모드와 스크립트 위치 파서는 개선됐으나 아래 빈 인자 반례가 남음 |
| R2-02 | 기존 전역 `(?i)`·possessive·padded wildcard 반례는 해소. scoped modifier의 신규 오탐은 R3-04로 별도 추적 |
| R2-03 | 해소. unmapped_by_design 값과 mappings[].why의 문자열 검증 및 빈 문자열·부재 허용 확인 |
| R2-04 | 해소. 실제 fallback 선택 뒤 접미사를 검사하며, 선택 함수가 실제 소비자와 같은지 비교하는 테스트도 통과 |
| R3-01 | 비차단 후속 검토로 보류. 루트 선택 필드의 타입 검사 확대를 이번 수정에 추가하지 않음. 전체 스키마 검증을 보장하지 않는다는 한계는 문서에 명시 |
| R3-02 | 같은 날짜·주제의 Plan 결정을 제자리 보완한 방식 수용. 아래 R3-04의 문법 설명 정정까지 일치시킬 것 |
| R3-03 | 해소. 변경 감지 영향 설명을 새 문장으로 정리한 것 확인 |

### R2-01 추가 재현 · P1 · 빈 인자를 버려 실행 대상을 바꿈

- 위치: `.claude/harness/scripts/doctor.py:892`~`:924`의 `tokenize`, 특히 `:914`~`:916`과
  `:922`~`:923`의 `if current` 조건. `_script_token()`은 이미 소실된 인자를 복구할 수 없다.
- 재현: 정상 fixture의 각 훅을
  `python "" "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/<스크립트>.py"`로 바꾼다.
  `tokenize('python "" "a.py"')`의 결과는 `['python', 'a.py']`다.
- 실제 결과: Doctor CLI는 D-WIRING 세 행 모두 PASS·종료 0이다. 같은 임시 프로젝트에서
  실제 Python에 빈 스크립트 인자와 훅 경로를 차례로 전달하면 종료 1이며 훅은 실행되지
  않는다. 실행되면 파일을 쓰는 훅을 두었으나 흔적이 없었다. Python이 읽은 대상은 빈
  스크립트 자리이지 두 번째 인자가 아니다.
- 기대 동작: 인자 내용이 비어 있는 것과 인자가 없는 것을 구별한다. 따옴표를 열었다 닫은
  토큰도 argv에 남기고, 빈 스크립트 자리에서는 확인 불가로 중단한다. D-HOOK은 미확인
  WARN, 그 명령밖에 없는 필수 연결은 D-WIRING FAIL·종료 1이어야 한다.
- 검증 기준: `python "" <훅>`와 `python '' <훅>`는 PASS하지 않는다. 반대로 `-W ""` 같은
  옵션 값의 빈 인자와 실제 스크립트 뒤 빈 인자는 역할을 유지해야 한다. 기존 정상 직접
  호출 및 `-c`·`-m`·`--version` 부정 테스트도 유지한다.
- 시도 기록: 첫 수정은 기존 세 예를 해결했지만 동일한 실행 대상 오인이 남았으므로 이
  지적의 수정 실패 1회로 센다. 서로 다른 지적의 횟수와 합산하지 않는다.

### R3-04 · P2 · 유효한 scoped modifier를 JS 문법 오류로 오판함

- 위치: `.claude/harness/scripts/doctor.py:109`의 `_INLINE_FLAG_RE`, `:1075`~`:1076`의
  `_classify_group`; `tests/test_doctor.py`의 `test_inline_flags_are_js_errors`도
  `(?s:Write)`를 오류로 고정하고 있다.
- 재현: `(?i:Write|Edit|Bash|PowerShell)`을 필수 matcher로 쓰면 Doctor는
  「Python 인라인 플래그는 JavaScript에 없습니다」라며 D-WIRING FAIL·종료 1을 낸다.
  하지만 현재 V8의 `new RegExp`는 이를 컴파일하고 Write에 일치한다. `(?i:Write)`와
  `(?-i:Write)`도 Doctor에서 js-error로 분류된다.
- 근거: [ECMAScript 2025의 정규식 문법](https://tc39.es/ecma262/2025/multipage/text-processing.html#sec-patterns)은
  `i`·`m`·`s` modifier 그룹을 정의하며,
  [MDN의 modifier 설명](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Regular_expressions/Modifier)도
  범위가 있는 그룹과 전역 형식을 구별한다(2026-11-22 원문 확인). 실제 Claude Code의 JS
  엔진 버전을 관찰했다는 뜻은 아니므로, 지원 여부를 모르는 경우도 언어 자체의 문법 오류로
  단정하면 안 된다.
- 기대 동작: `(?i)`처럼 JS가 거부하는 전역 형식과 `(?i:...)`·`(?-i:...)` 같은 유효한
  scoped 형식을 구별한다. 이번에는 후자를 UNKNOWN/WARN으로 남기고 D-WIRING의 PASS나
  FAIL 근거로 쓰지 않는다. scoped 플래그의 모든 의미를 새로 구현할 필요는 없다.
- 검증 기준: `(?i:Write)`·`(?s:Write)`·`(?-i:Write)`·유효한 `i/m/s` 조합은 js-error가
  아니며 해당 matcher밖에 없는 결선은 WARN·미확인이다. 전역 `(?i)Write`와 기존 확정
  JS 오류 예는 계속 FAIL이다. 잘못된 테스트 기대값과 Knowledge·Plan의 일괄 오류 설명도
  고친다. Doctor에 JS 실행 의존성을 추가하지 않는다.
- 명세 정정: 이전 Codex 지시의 「Python 인라인 플래그」 표현이 너무 넓었다. 이를 전역
  형식으로 한정해 수정했다. 이 새 오탐을 R2-02의 두 번째 수정 실패라고 계산하지 않는다.

### 열린 질문과 구현 판단의 확정

| 질문·판단 | 결정 |
|---|---|
| Q-1: padded `*` | 원본의 정확한 `*`만 wildcard라는 현재 문서 기준 유지. 공백이 붙은 패턴은 별도 해석하고 자동 strip하지 않음. 제품 자체의 trim 동작은 미관찰이라는 한계 유지 |
| 공백뿐인 matcher | UNKNOWN/WARN 수용. 전체 적용이나 PASS로 만들지 않음 |
| 판단 1: 모르는 Python 옵션 | D-HOOK 미확인 WARN과 필수 연결 D-WIRING FAIL의 결합 유지. 실행 위치를 입증하지 못한다는 이유를 표시 |
| 판단 2: JS 오류 검사 범위 | 필수 도구 행의 D-WIRING으로 제한하는 현 범위 수용. Stop의 matcher와 다른 이벤트의 모든 matcher까지 검사 범위를 넓히지 않음 |
| 판단 3~5: 빈 클래스·느슨한 수량자·미확인 escape | 보수적 UNKNOWN 수용. 지원 부분집합 밖인 것을 무리하게 Python 결과로 인증하지 않음 |
| 실제 훅과의 비교 테스트 | 수용. 런타임 import 금지와 테스트 비교를 구분했고 현재 선택 순서·반환값을 검증함. 미래의 모든 신규 분기를 증명한 것은 아니라는 한계 유지 |

남은 일은 R2-01의 추가 반례와 R3-04 수정, 문서 정정, 영향 테스트·Full의 새 실행이다.
Claude는 결과를 Round 4에 덧붙인다. R3-01의 별도 범위 확대 때문에 이번 완료를 추가로
막지 않는다. 보존·임시 파일 삭제는 최종 리뷰 이후이며, 이번 판정과 새 파일은 아직 커밋으로
보존되지 않았다. Codex는 구현을 대신 고치지 않고 명세만 저장했으며 재독·diff·공백 검사로
기록과 현재 상태를 확인한다.

## Codex Round 4 최종 결과 리뷰 — 승인 (2026-11-22)

대상은 `C:\my-harness`, `main` / `bd89a04`의 현재 작업 트리다. 리뷰의 Round 4 사전
검토·구현 보고를 읽고, 수정 함수와 회귀 테스트, README, Knowledge, Plan 문서의 현재
내용을 완료 기준과 대조했다. **이번 작업의 구현 완료를 차단 지적 없이 승인한다.**
보존·임시 파일 정리는 아직 끝나지 않았으며, 구현 승인과 별개로 남는다.

### 검증 근거

| 검증 | Codex가 직접 확인한 결과 |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_doctor.py -q` | 246 passed, 1 skipped, 5.19초 |
| `.venv/Scripts/python.exe -m ruff check .` | All checks passed, 종료 0 |
| `.venv/Scripts/python.exe -m ruff format --check .` | 71 files already formatted, 종료 0 |
| `.venv/Scripts/python.exe -m pytest -q` | 651 passed, 1 skipped, 13.78초 |
| 현재 저장소의 Doctor 실행 | PASS 24 · WARN 5 · FAIL 0, 종료 0 |
| 빈 스크립트 인자를 넣은 임시 프로젝트 | `python "" <훅>`·`python '' <훅>`는 D-WIRING 세 행 모두 FAIL, 종료 1 |
| 빈 인자가 정상인 호출의 임시 프로젝트 | `python -W "" <훅>`·`python <훅> ""`는 세 행 모두 PASS, 종료 0 |
| 유효한 scoped modifier의 임시 프로젝트 | `(?i:...)`·`(?im-s:...)`는 대상 행 WARN만 표시, 종료 0. 네 도구를 포함한 실제 패턴으로 검증 |
| 확정 JS 오류 matcher의 임시 프로젝트 | 전역 `(?i)`, 범위 밖 `x`, 중복 `i-i`, 빈 `-`, 닫히지 않은 그룹은 FAIL·종료 1 |

각 probe는 기존 테스트 fixture를 임시 디렉터리에 구성하고 실제 Doctor CLI로 확인했다.
Codex는 구현·테스트·공유 설정을 고치지 않았다. 현재 소스와 테스트의 변경은 Claude의
작업이며, Codex의 수정 대상은 이 명세뿐이다.

skip 1건은 POSIX 실행 권한 테스트다. Windows에서 확인한 결과이며 Linux 전체 동작은
미검증이다. 실제 Claude Code의 JS 엔진 버전과 matcher 공백 정규화도 관찰하지 않았다.
이 한계 때문에 scoped modifier는 지원한다고 인증하지 않고 UNKNOWN으로 남긴다.

### 완료 기준 판정

| 기준 | 판정과 근거 |
|---|---|
| 1. 판정·종료 코드·미검사 구분 | 충족. 핵심 입력별 회귀 테스트와 0/1/2 계약의 테스트 통과. 미확인 matcher는 PASS로 꾸미지 않음 |
| 2. 끊긴 결선·잘못된 stage 감지 | 충족. 기존 실행 모드·치환값 반례와 새 빈 인자 반례가 FAIL로 구분됨. 올바른 호출의 오탐도 해소 |
| 3. 루트·의존성·읽기 전용 | 충족. 자기 파일 기반 루트, 표준 라이브러리 실행과 무자식 프로세스·무쓰기 테스트 유지 |
| 4. 사용 안내·영구 계약·결정 이유 | 충족. README의 명령·표시·0/1/2·한계와 Knowledge 및 필요한 Plan 기록 확인. 전역/범위 플래그 설명도 정정됨 |
| 5. 최종 리뷰·보존 후 정리 | 최종 구현 리뷰 승인. 보존을 확인하기 전 삭제하지 않는 조건은 계속 적용하며 정리는 대기 |

### 지적 종료와 판단 요청의 결정

| 항목 | 최종 판정 |
|---|---|
| R2-01 및 빈 인자 추가 반례 | 해소. `tokenize()`가 quoted 빈 토큰을 보존하고 `_script_token()`이 빈 스크립트 자리에서 중단. 옵션 값·후행 빈 인자는 역할 유지 |
| R2-02 | 종료 유지. 공통 문법만 판정하고 전역 플래그·possessive 등 기존 반례는 계속 FAIL |
| R2-03 | 종료 유지. 지정한 quality 필드의 값 타입 검증과 정상 빈 문자열·부재 허용 유지 |
| R2-04 | 종료 유지. 실제 선택된 fallback만 현재 변경 감지 오류로 판정 |
| R3-04 | 해소. 전역 형식과 유효 scoped 형식을 분리하고 후자는 UNKNOWN. 잘못된 테스트 기대값 및 Knowledge·Plan 설명도 수정됨 |
| 판단 1: i/m/s 밖·중복·양쪽 빈 플래그 | 확정 JS 문법 오류로 FAIL 유지 수용. 유효 modifier를 UNKNOWN으로 두라는 지시와 충돌하지 않음 |
| 판단 2: `(?i-:...)` | 한쪽만 비어 있는 유효 형식이므로 UNKNOWN 수용. 양쪽이 빈 `(?-:...)`와 구분 |
| 판단 3: `""#x` | 빈 인용과 이어지는 문자를 한 토큰으로 유지한 처리 수용. `"" #x`와 구분하는 회귀 테스트 확인 |
| 판단 4: modifier의 pending UNKNOWN | 이번 수정에서 확정 오류가 뒤따르면 FAIL이 우선하는 처리 수용. 다른 UNKNOWN 분기를 전체 재설계하지 않음. UNKNOWN은 계속 미검증이며 PASS가 아님 |
| WARN 사유 중복 제거 | 같은 도구의 같은 사유를 순서 보존해 합친 출력 변경 수용. 판정 의미는 바꾸지 않음 |
| R3-01 | 비차단 후속 검토로 보류 유지. 루트 선택 필드 타입 검사를 이번 작업에 추가하지 않으며 전체 스키마 검증을 보장하지 않음 |
| Q-1 및 제품 동작의 미관찰 항목 | 문서 기준의 현재 해석과 명시한 한계 유지. 이번 구현의 미해결 차단 항목으로 취급하지 않음 |

### 남은 9단계 — 보존과 정리

1. `.claude/wiki/knowledge/doctor.md`를 현재 계약의 원본으로 유지하고, 필요하면 이 최종
   승인과 독립 검증 요약을 보존한다. 기존 결정 이유는 두 Plan 문서에 남긴다.
2. 새 CLI·테스트·Knowledge·Plan과 README 변경, 최신 명세·리뷰의 필요한 내용이 확인된
   커밋 또는 적절한 영구 문서에 보존됐는지 확인한다. 현재 새 파일은 untracked이고 이번
   승인도 커밋에 없으므로, 완료 승인만으로 보존이 끝났다고 판단하지 않는다.
3. 보존 조건을 만족한 다음 Claude가 `tasks/doctor.md`와 `tasks/doctor.review.md`만
   정리한다. 최신 판정·근거를 잃거나 다른 작업 파일과 영구 템플릿을 지우지 않는다.

추가 구현이나 Round 5 수정 보고는 요구하지 않는다. 후속 범위 확대는 별도 작업 ID로
설계한다. Codex는 커밋·삭제를 수행하지 않았으며, 명세 저장 후 재독·diff·공백 검사로
승인 상태·지적 종료·보존 대기가 일치하는지 확인한다.
