# my-harness

Claude Code 프로젝트에 그대로 복사해 쓰는 개인용 개발 하네스다. 반복해서 커지는
`CLAUDE.md`, 누락되기 쉬운 품질 검사, 현재 규칙과 과거 결정이 섞이는 문제를 분리된
프로젝트 문서와 훅으로 다룬다. 플러그인 마켓플레이스나 별도 설치는 필요 없다.

## 빠른 시작

길이 둘이다. 새 프로젝트를 이 저장소로 시작하거나, 이미 있는 프로젝트에 하네스만
가져온다.

### 새 프로젝트로 시작

```powershell
git clone https://github.com/JungHwyKim/my-harness <your_dir>
```

`main`을 그대로 clone 하면 `.claude/wiki/history/`에 **이 하네스를 개발하면서 쌓인
기록**이 들어 있다. 새 프로젝트에서는 그것을 지우고 시작한다 — 공통 README와 세 하위
폴더의 `.gitkeep`만 남긴다. 이렇게 받은 사본에는 커밋 이력이 다 있으므로, 지운 기록은
`git show <커밋>:<경로>`로 다시 읽는다. 템플릿용 ref를 따로 배포한 경우에는 그 ref의
History가 이미 비어 있으니 지울 것이 없다.

배포용 ref는 `template/<버전>` 이름을 쓴다 — `main`에서 끊어 History만 비운 스냅샷이다.
그 ref가 있으면 거기서 바로 받고 지울 것이 없다.

```powershell
git clone --branch template/v2.1 --depth 1 https://github.com/JungHwyKim/my-harness <your_dir>
```

`--depth 1`은 커밋 이력까지 따라오지 않게 한다. 그래서 이 사본에서는
`git show <커밋>:<경로>`가 통하지 않는다 — 가리킬 커밋이 로컬에 없다. 지운 기록을 읽어야
하면 둘 중 하나다.

- 원본 저장소에서 바로 본다 —
  `https://github.com/JungHwyKim/my-harness/blob/<커밋>/<경로>`. 푸시된 커밋만 열린다.
- `git fetch --unshallow`로 이력을 받은 뒤 `git show <커밋>:<경로>`를 쓴다. 배포 ref에서
  이어지는 조상 커밋이 함께 따라온다.

배포 ref는 `main`으로 병합하지 않는다 — 기록을 지운 커밋이 `main`에 섞인다. ref를 끊는
쪽의 계약은 `.claude/wiki/knowledge/template-deploy.md`에 있다.

이 프로젝트가 앞으로 만드는 기록은 기존 Plan·Task·Verify 절차대로 쌓인다.

가상환경은 저장소마다 새로 만든다. 아래 「검증과 주의 사항」의 설치 명령을 따른다.

### 기존 프로젝트에 적용

이 저장소의 `CLAUDE.md`와 `.claude/`를 가져온다. Codex도 함께 쓴다면 `AGENTS.md`도
가져온다. 기존 `CLAUDE.md`, `AGENTS.md`, `.claude/settings.json`이 있다면 덮어쓰지 말고,
프로젝트의 규칙과 `hooks` 항목을 병합한다.

대상 프로젝트의 파일은 덮어쓰지 않는다. `requirements.txt`가 이미 있으면 하네스의 의존성
목록은 `requirements-harness.txt`처럼 다른 이름으로 가져와 검증 도구만 설치한다. 기존
가상환경과 pytest 설정, `.claude/wiki/`에 이미 있는 기록도 그대로 둔다.

### 적용 직후 고칠 네 곳

1. `CLAUDE.md` — 프로젝트 목적과 항상 지켜야 할 공통 규칙
2. `.claude/harness.json` — Python 경로, 소스·테스트 경로, Quality Profile
3. `.claude/wiki/overview/` — 디렉터리, 진입점, 관련 문서 링크
4. `.claude/wiki/knowledge/` — 현재 유효한 계약과 정책

Claude Code는 프로젝트의 `.claude/settings.json`에서 훅을,
`.claude/skills/<이름>/SKILL.md`에서 프로젝트 스킬을 읽는다.

### 설치 직후 점검 — Doctor

위 네 곳을 고치고 `hooks`를 병합한 뒤 저장소 루트에서 한 번 돌린다.

```text
python .claude/harness/scripts/doctor.py
```

표준 라이브러리만 쓰므로 Git 저장소나 별도 패키지가 없어도 된다. 어느 디렉터리에서
불러도 **그 스크립트가 속한 프로젝트**를 진단한다.

| 표시 | 뜻 |
|---|---|
| `[PASS]` | 실제로 확인했고 문제가 없다 |
| `[WARN]` | 비활성 설정, 아직 만들지 않은 경로, 선택 파일 부재, 그리고 **미검사** |
| `[FAIL]` | 지금 조용히 안 도는 설정이다. 위치와 고치는 법이 함께 나온다 |

| 종료 코드 | 뜻 |
|---|---|
| 0 | FAIL 없음. WARN만 있어도 0이다 |
| 1 | FAIL이 하나 이상 |
| 2 | **진단 자체를 못 마쳤다** — 스크립트 배치 오류, 루트 접근 불가, 내부 오류 |

2를 따로 둔 이유는 「문제 없음」과 「못 봤음」이 같은 0으로 보이면 안 되기 때문이다.
같은 이유로 선행 오류 때문에 못 본 검사는 PASS가 아니라 `[WARN] 미검사`로 나온다.

**이 명령이 보장하지 않는 것**을 먼저 읽는다.

- **명령을 실행하지 않는다.** 훅·stage·Git·다른 인터프리터를 돌리지 않고 대상 프로젝트의
  모듈을 import하지도 않는다. 그래서 결선 `[PASS]`는 「연결이 있다」까지만 말하고 「그
  명령이 성공한다」는 말하지 않는다.
- `pytest`·`ruff` 같은 **모듈의 설치 상태와 버전은 미검증**이다. 어떤 언어나 도구도 필수로
  요구하지 않으므로, 다른 언어 프로젝트가 Quality Profile을 자기 도구로 바꿔도 실패하지
  않는다.
- 공유 파일인 `.claude/harness.json`과 `.claude/settings.json`만 본다. 사용자·로컬·관리자
  설정과 실제 세션에서 훅이 켜져 있는지는 보지 않는다.
- 인터프리터 선택은 **Doctor의 루트 기준**이다. 실제 훅은 `CLAUDE_PROJECT_DIR`에서 찾은
  루트를 쓰므로 중첩 프로젝트에서는 선택이 달라질 수 있다.

현재 계약은 `.claude/wiki/knowledge/doctor.md`에 있다.

### 무엇이 따라오고 무엇이 안 따라오는가

| 가져온다 | 가져오지 않는다 |
|---|---|
| `CLAUDE.md`·`AGENTS.md` 진입점 | `.venv/`와 설치된 패키지 — 프로젝트마다 다시 만든다 |
| `.claude/` 전체 — 설정·훅·스킬·Wiki 구조 | `.agents/`·`.codex/` — 다른 에이전트용 로컬 사본 |
| `requirements.txt` — 하네스의 검증 도구 목록 | 하네스를 개발하며 쌓인 Plan·Task·Verify 기록 |
| `tasks/_template.md` — 작업 명세 템플릿 | 끝난 작업의 임시 명세와 리뷰 |
| `.claude/wiki/knowledge/`의 현재 계약 | 대상 프로젝트에 이미 있는 파일 |

`requirements.txt`의 `pytest`·`ruff`는 **이 저장소를 개발하고 검증하는** 도구다. 대상
프로젝트의 제품 의존성도 아니고, 모든 프로젝트가 꼭 써야 하는 품질 도구도 아니다. 다른
언어 프로젝트는 `.claude/harness.json`의 Quality Profile을 그 언어의 도구로 바꾼다.

History를 `.gitignore`로 막지 않는다. 비어 있는 것은 초기 상태이고, 기록을 남기지 않는
정책이 아니다.

## Codex와 함께 사용

`AGENTS.md`는 Codex의 진입점이다. 이 파일은 `CLAUDE.md`를 공통 규칙의 원본으로
참조하고, Wiki·Skill·Quality Gate를 언제 확인해야 하는지만 안내한다. 따라서 두 에이전트에
같은 긴 규칙을 복사할 필요가 없다.

Codex에서는 `.claude/settings.json`의 Claude Code 훅이 자동으로 실행되지 않는다. 코드나
하네스 설정을 바꾼 뒤에는 `AGENTS.md`의 안내에 따라 `.claude/harness.json`의 Fast 또는
Full Quality Profile을 직접 실행한다.

## 구조

```text
AGENTS.md                Codex용 최소 규칙과 Context Router
CLAUDE.md                최소 공통 규칙과 Context Router
.claude/settings.json    프로젝트 공용 훅 설정
.claude/harness.json     프로젝트별 품질·History 설정
.claude/skills/          필요할 때만 로드되는 작업 절차
.claude/harness/         훅·보조 스크립트·설정 스키마
.claude/wiki/            프로젝트 지식
├─ overview/             어디에 무엇이 있는가
├─ knowledge/            현재 무엇이 참인가
└─ history/              왜 그렇게 되었는가
```

`CLAUDE.md`는 상세 지식 저장소가 아니라 문서 탐색 경로를 제공하는 짧은 라우터다. 작업자는
먼저 Overview를 보고, 관련 Knowledge만 읽으며, 과거의 결정 이유가 필요할 때만 History를
검색한다.

## 동작 흐름

```text
파일 수정
  → Fast Quality Gate: 영향 범위 검사
  → 작업 종료 또는 커밋 시도
  → Full Quality Gate: lint · format · 전체 테스트
  → history-significance: 미래에 남길 이유가 생겼는지 판단
```

중요하지 않은 일반 구현과 테스트 성공은 History에 기록하지 않는다. 중요한 선택은
`history/plan/`, 구현 중의 이탈·실패·제약은 `history/task/`, 비교할 가치가 있는
측정·회귀는 `history/verify/`에 남긴다. 현재 시스템의 계약이 바뀌면 이유는 History에,
현재 규칙은 Knowledge에 짧게 반영한다.

## V1에서 V2로

V1과 V2 모두 프로젝트에 복사해 쓰지만, V2는 Context와 기록의 수명주기를 더 명확히
나눴다.

| 항목 | V1 | V2 |
|---|---|---|
| 프로젝트 구성 | 평탄한 `.claude/hooks`, `scripts`, `skills` | `.claude/harness/` 아래에 훅·스크립트·스키마를 묶음 |
| Wiki | `plan_log`, `task_log`, `verify_log` 중심 | Overview · Knowledge · History로 역할 분리 |
| Context | 기록과 현재 규칙이 가까이 섞일 수 있음 | 현재 계약과 과거 이유를 분리해 필요한 것만 읽음 |
| 품질 검사 | 자동 테스트·커밋 전 검사 설정 | Fast / Full Quality Profile을 명시적으로 구분 |
| 기록 기준 | 설계·작업 로그 게이트 | `history-significance`가 중요한 정보만 선별 |

- [V1 구조 보기](https://github.com/JungHwyKim/my-harness/tree/v1.0.0)
- [V2 구조 보기](https://github.com/JungHwyKim/my-harness/tree/v2.0.0)
- [V1 → V2 전체 비교](https://github.com/JungHwyKim/my-harness/compare/v1.0.0...v2.0.0)

## 검증과 주의 사항

개발 의존성은 저장소 전용 가상환경에 둔다. `.claude/harness.json`의 `python`이
`.venv/Scripts/python.exe`를 가리키므로, 그 자리에 환경이 없으면 Quality Profile이 다른
인터프리터로 조용히 대체된다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Full Quality Profile의 세 단계는 직접 실행할 수 있다.

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q
```

- `.venv/`는 Git 관리 대상이 아니다. 개발 의존성은 `requirements.txt`에 버전을 고정한다.
- `requirements.txt`는 ASCII로 유지한다. pip가 그 파일을 로케일 인코딩으로 읽어서,
  한국어 주석을 넣으면 cp949 환경에서 `pip install -r`가 실패한다.
- `.claude/settings.local.json`은 개인 설정이므로 커밋하지 않는다.
- `.claude/harness.json`의 예시는 Python 프로젝트 기준이다. 다른 언어에서는 Quality
  Profile의 명령을 사용하는 도구에 맞게 바꾼다.
- `history/`는 이슈 트래커나 전체 백로그가 아니다. 열린 작업은
  `checks.openwork.sources`에 별도 정보원을 지정해 관리한다.

Profile이 무엇을 보장하고 무엇을 보장하지 않는지는
`.claude/wiki/knowledge/quality-env.md`에 있다.

## 유료·외부 테스트 보호

비용이 드는 테스트는 **세 곳을 함께** 설정해야 보호된다. 하나만 하면 나머지 경로로 그냥
실행된다.

1. `.claude/harness.json`의 `checks.expensive_tests.pytest_markers`에 유료 마커를
   등록한다. 이 저장소는 제품 테스트가 없어 `[]`이고, 빈 목록이면 비용 훅은 아무것도
   감지하지 않는다.
2. 프로젝트의 pytest 기본 설정에서 그 마커를 **모두** 제외한다. 그래야 마커를 지정하지
   않은 `pytest -q`가 유료 테스트를 수집하지 않는다.

   ```toml
   # pyproject.toml
   [tool.pytest.ini_options]
   addopts = "-m 'not paid and not paid2'"
   markers = ["paid: 외부 API 과금", "paid2: 다른 과금 경로"]
   ```

3. Quality Profile의 `argv`에도 같은 제외를 적는다. Fast·Full 단계는 훅 안에서 pytest를
   자식 프로세스로 띄우므로 `PreToolUse` 승인을 거치지 않는다. 기본 설정과 별도로 실행
   명령 자체를 안전하게 만들어야 한다.

   ```json
   "argv": ["{python}", "-m", "pytest", "-m", "not paid and not paid2", "-q"]
   ```

비용 훅은 이 설정을 전제로 **명령줄이 그 제외를 덮는지**만 본다. 명령줄 `-m`이 있으면
설정된 모든 유료 마커를 AND 조건으로 빼는 것이 증명되는 단순 식만 통과한다. `or`·괄호·
다른 설정 파일(`-c`)은 승인을 요청한다. `-o addopts` 덮어쓰기도 모든 유료 마커의 제외를
증명할 수 없으면 승인을 요청한다. 승인은 그 도구 호출 하나에만 적용되고 **환경변수로
세션 전체를 허용하는 우회는 없다.**

승인창을 보장할 수 없는 권한 모드(`bypassPermissions` 등)와 모드를 읽지 못한 경우에는
승인 대신 차단한다. 자세한 계약과 한계는
`.claude/wiki/knowledge/paid-test-approval.md`에 있다.
