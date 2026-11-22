# Windows에서 POSIX 모양 `CLAUDE_PROJECT_DIR`는 검사를 우연히 통과시킨다

- 날짜: 2026-11-22
- 관련 계획: `.claude/wiki/history/plan/2026-11-22-doctor-target-root.md`의 루트 결정과 같은 자리다
- 영향 범위: Windows에서 bash로 하네스 훅·스크립트를 부르는 모든 호출.
  `.github/workflows/harness-quality.yml`의 「인터프리터 일치 확인」이 첫 사례다.

## 원래 예상

CI에 「하네스가 준비한 그 venv를 고르는지」 확인하는 단계를 넣었다. 두 OS 공통으로 bash를
쓰므로 `CLAUDE_PROJECT_DIR="$PWD"`로 루트를 알려 주고, `_hookutil.venv_python()`이 고른 경로와
지금 돌고 있는 `sys.executable`을 비교하면 된다고 보았다.

## 실제로 드러난 것

Windows 러너의 bash에서 `$PWD`는 `/d/a/my-harness/my-harness` 모양이다. Windows의
`Path()`는 그것을 **현재 드라이브 기준 경로**로 읽는다 — 실측으로
`Path('/d/a/my-harness/my-harness').resolve()`가 `C:\d\a\my-harness\my-harness`가 되고
그 아래에 `.claude`는 없다.

그래서 `_find_root()`가 위로 올라가도 `.claude`를 못 찾고 그 엉뚱한 경로를 그대로 쓴다.
`venv_python()`은 거기서 `.venv`를 못 찾아 **현재 프로세스로 대체**하는데, 그 프로세스가
바로 비교 대상인 venv의 python이다. 두 값이 같아지므로 **검사가 통과한다** — 루트가 통째로
틀렸는데도.

## 원인

두 전제가 겹쳤다. `_find_root()`는 환경변수를 신뢰하고 못 찾으면 시작 자리를 그대로 쓴다
(조용히 통과하는 쪽이 기본값이다). `venv_python()`의 마지막 대체값은 현재 인터프리터다.
둘 다 각자 맞는 설계인데, **대체값이 비교 대상과 같아지는 자리**에서 겹치면 실패가 성공으로
보인다.

## 내린 결정

CI에서 `CLAUDE_PROJECT_DIR`를 **설정하지 않는다.** 비워 두면 `_find_root()`가 `os.getcwd()`를
쓰고, Python이 보고하는 그 값은 제대로 된 Windows 경로다.

더해서 그 단계가 **루트를 먼저 단정한다** — `_hookutil.PROJECT_ROOT`가 cwd와 같은지 보고,
그 다음에 인터프리터를 비교한다. 순서가 중요하다. 루트 검사가 없으면 위의 우연한 통과가
그대로 남는다.

## 기각하거나 되돌린 접근

- `CLAUDE_PROJECT_DIR="$(pwd -W)"`로 Windows 경로를 넘기는 것 — `pwd -W`는 Git Bash에만
  있어서 두 OS 공통 step에서 분기가 또 생긴다. 환경변수를 안 쓰면 분기가 아예 없다.
- Windows step만 PowerShell로 가르는 것 — 그 셸에서 외부 명령 여러 개를 한 step에 넣으면
  중간 실패가 마지막 종료 코드에 가려지는 다른 함정이 있다. bash 공통이 그쪽보다 싸다.
- 인터프리터 비교만 남기고 루트 단정을 빼는 것 — 위 우연한 통과를 못 잡으므로 의미가 없다.

## 재발 방지와 남은 제약

- **bash에서 얻은 경로를 Windows의 Python에 경로로 넘기지 않는다.** 이 함정은 CI만의 것이
  아니다. Windows에서 bash로 훅이나 스크립트를 부르는 모든 자리에 같다.
- 이 교훈은 아직 **테스트가 아니라 주석과 이 기록이 들고 있다.** hosted CI를 돌려 본 근거가
  없고, Windows 러너의 `$PWD` 모양을 로컬에서 재현하는 테스트는 두지 않았다. CI가 한 번
  돌면 그때 실제 값으로 확인한다.
- 일반화하면 **대체값이 비교 대상과 같아지는 검사는 믿을 수 없다.** 그런 비교를 쓸 때는
  대체가 일어나지 않았다는 것을 따로 단정한다.

## Knowledge 반영

인터프리터 자동 탐색이 무엇을 보장하지 않는지는
`.claude/wiki/knowledge/quality-env.md`의 「인터프리터」가 소유한다. 위 Windows 경로 함정은
현재 계약이 아니라 한 번 밟은 원인이라 이 기록에만 둔다.
