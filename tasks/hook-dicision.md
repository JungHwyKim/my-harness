# 유료 테스트 승인 훅 설계

- 작업 ID: `hook-dicision` — 기존 인수인계 경로를 유지한다.
- 상태: Round 5 코드·자동 검증 완료 · README 계약 정합성 반영 · 추가 승인창 실측 대기
- 명세: `tasks/hook-dicision.md`
- 리뷰·구현 보고: `tasks/hook-dicision.review.md`
- 기준: `release/v2`, HEAD `4f5300c`와 기존 미커밋 변경. 인수 시 다시 확인한다.

## 목적과 실행 계약

프로젝트가 지정한 유료 pytest 명령을 Claude Code가 실행하기 전에 호출마다 사용자 승인을
받는다. Codex는 설계·리뷰, Claude는 구현·무료 테스트를 맡는다. 환경변수로 세션 전체를
허용하지 않는다. 승인을 보장하지 못하는 권한 모드에서는 해당 유료 명령을 차단한다.

이 명세는 기존 리뷰의 누락을 수정한 같은 작업이다. 새 구현을 시작하기 전에 현재 코드와
대조하되, 이미 승인된 범위의 테스트 격리 수정과 구현에 다시 허락을 요청하지 않는다.
명세는 Codex가 관리하고, Claude는 기존 리뷰를 보존하면서 영어로 결과를 덧붙인다.

## 리뷰 대응과 범위

| 지적 | 수정 계약 |
|---|---|
| C1: 기존 14개 실패의 설정 격리 누락 | A단계에서 테스트 설정을 먼저 격리하고 기존 deny 동작으로 통과시킨다. |
| C2: 자동 검사와 승인창 확인 혼재 | 코드·자동 검증 완료와 사용자 승인 동작 확인 완료를 나눈다. 미확인은 계속 표시한다. |
| C3: 검증 전 보호 변경 | A는 기존 동작을 유지한다. B는 마커가 빈 이 템플릿에서 구현하고, 실제 프로젝트 적용 전 C의 무과금 검증을 요구한다. |
| C4: 다른 저장소 작업 포함 | 다른 저장소는 수정하지 않는다. README 적용 안내와 임시 프로젝트에서 기본 제외를 검증한다. |

포함: 비용 훅, 관련 설정·스키마·테스트, README 적용 안내, 비용 훅의 Codex 배선 제거,
현재 계약을 요약할 `.claude/wiki/knowledge/paid-test-approval.md`.
제외: 다른 프로젝트 파일 변경, 실제 유료 API 실행, CI, Quality 추적 경로 확대,
다른 Codex 훅 정리, 가상환경 재설치, 다른 작업 명세·리뷰 수정, 커밋·푸시.

템플릿의 `checks.expensive_tests.pytest_markers`는 `[]`를 유지한다. 제품 테스트가 없는
이 저장소에 `integration`을 기본 등록하거나 실제 프로젝트의 경로를 하드코딩하지 않는다.

## 현재 코드와 외부 계약의 근거

2026-11-18 작업 트리에서 다시 확인한 위치다. 인수 후 식별자와 내용을 재확인한다.

- `.claude/harness/hooks/paid_test_check.py:73` `_policy()`와 `:100`은 임포트할 때
  마커·사유·allow_env를 확정한다. `:209` `_deny()`는 deny JSON을 출력한다.
- 같은 파일 `:251`은 환경변수의 비어 있지 않은 모든 값을 우회로 인정하고,
  `:256`은 빈 마커면 응답 없이 반환한다. `:164`의 판정은 -m과 addopts만 검사한다.
- `.claude/harness.json:63`의 마커는 빈 목록이다.
  `tests/test_paid_test_check.py:67`의 직접 호출은 이 실제 설정에 의존한다.
  `:90` 응답 형식과 `:119` BOM 테스트도 명시적인 마커 프로젝트가 필요하다.
- `tests/conftest.py:94` `harness_project`는 실제 임시 설정 파일과 CLAUDE_PROJECT_DIR을
  준비한다. `:120` `load_hook`는 _hookutil과 대상 훅을 순서대로 다시 로드한다.
- `.claude/settings.json:3`은 Bash|PowerShell PreToolUse에 비용 훅을 연결한다.
  `.codex/hooks.json`도 같은 비용 훅을 연결한 미추적 파일이다.
- `.claude/harness/schemas/harness.schema.json:91`은 expensive_tests를 정의하고
  `:100`에 allow_env가 있다. 설정과 스키마에서 함께 제거해야 한다.
- `tests/test_hook_wiring.py:257`은 사용하지 않는 우회 변수 이름을 검사한다.
  `tests/_escape_hatches.py`와 `tests/conftest.py:150`의 환경 격리를 함께 고려한다.
- `.claude/harness/hooks/_quality.py:216`은 stage를 subprocess로 직접 실행한다.
  Quality Profile의 자식 pytest는 별도 PreToolUse 승인을 거치지 않는다.
- 2026-11-18 Codex 확인: Claude Code 2.1.319. 비용 훅 테스트는 14실패·17통과였다.
  임시 프로젝트에 마커 []를 주면 응답 없음, [integration]이면 deny가 출력됐다.
- [Claude 훅 문서](https://code.claude.com/docs/en/hooks): PreToolUse ask는 사용자 확인을
  요청하고 permission_mode가 입력된다. [권한 문서](https://code.claude.com/docs/en/permissions)는
  bypassPermissions가 승인창을 건너뛰는 모드라고 설명한다. 문서 지원과 설치 환경의
  실동작 검증은 구분한다. 버전 번호만으로 승인 동작 확인을 대체하지 않는다.
- [Codex 훅 문서](https://learn.chatgpt.com/docs/hooks): PreToolUse ask는 미지원이며
  오류 보고 뒤 도구 호출이 계속된다. Claude용 ask 훅을 그대로 배선하지 않는다.
- [pytest 옵션 우선순위](https://docs.pytest.org/en/stable/example/simple.html): 명령줄 옵션이
  기본 addopts를 덮을 수 있다. 단순히 not paid라는 문자열이 있다고 안전하지 않다.

## A단계: 테스트 설정 격리 — 먼저 실행

1. `tests/test_paid_test_check.py`의 정책 의존 테스트는 저장소의 실제 설정을 읽지 않는다.
   직접 판정은 load_hook으로 마커 [integration]이 설정된 임시 V2 프로젝트를 로드한다.
   subprocess 응답·BOM·통과·우회 테스트도 그 프로젝트의 CLAUDE_PROJECT_DIR을 상속한다.
   env를 직접 전달할 때도 이 경로를 보존하고 개발자 환경의 우회 값을 격리한다.
2. 임포트 시 상수가 캐시되므로 환경변수만 바꾸지 말고 _hookutil, 비용 훅 순으로 재로드한다.
   각 정책 테스트는 자기 설정을 준비하고 앞선 테스트의 재로드 상태에 기대지 않는다.
   전역 모듈 재로드가 다른 테스트에 누출되지 않도록 격리 또는 원복을 확인한다.
3. V1 설정 없음, V2 명시 마커, V2 빈 마커를 서로 독립된 케이스로 유지한다.
   빈 마커 테스트를 삭제하거나 저장소 설정에 마커를 추가해 통과시키지 않는다.
4. 이 단계에서는 훅 동작·설정·스키마를 바꾸지 않는다. 기존 deny 응답과 우회 테스트를
   유지하고 비용 훅 테스트 및 전체 pytest가 통과하는 기준선을 먼저 만든다.
5. 리뷰에 A단계 결과를 기록한 뒤 같은 작업의 B단계로 이어간다.
   다른 코드에서 새 실패가 발견되면 기존 실패와 구분해 원인과 영향을 보고한다.

## B단계: 승인 훅 구현과 자동 검증

### 판정과 권한 모드

감지 대상은 pytest 터미널 명령이다. 마커가 없는 테스트, 임의 Python API 호출, 숨겨진
래퍼까지 막는다고 주장하지 않는다. 기존 명령 세그먼트 구분과 pytest 실행기 식별을 유지하되,
PowerShell에서 공백이 있는 경로를 따옴표로 감싼 Python 실행기도 식별한다.

| 마커가 설정된 프로젝트의 명령 | 판정 |
|---|---|
| 명시적 -m 또는 addopts에 유료 마커 포함 | 승인 필요 |
| -m unit, 빈 -m, -m not paid or unit | 기본 제외를 보장하지 못하므로 승인 필요 |
| -c 또는 --config-file로 다른 설정 선택 | 승인 필요 |
| -o/--override-ini addopts 덮어쓰기 | 모든 유료 마커 제외를 증명할 수 없으면 승인 필요 |
| -m not paid and not paid2 | 설정된 두 마커가 모두 제외되면 승인 불필요 |
| 괄호·중복 옵션·복합식의 안전성을 해석하지 못함 | 승인 필요로 보수적으로 판정 |
| pytest -q처럼 제외를 덮지 않는 호출 | 적용 안내의 기본 제외를 전제로 통과 |
| --collect-only | pytest의 독립된 실제 옵션일 때만 수집 전용 예외. 셸 주석·인용 문자열·`./--collect-only` 같은 경로의 일부는 예외가 아님. 임시 검증 프로젝트의 import·플러그인도 외부 호출이 없어야 함 |
| pytest가 아닌 명령 | 비용 훅은 관여하지 않음 |

모든 마커 제외를 보장하는 단순 AND 식만 무료로 인정한다. not paid라는 부분 문자열만으로
허용하지 않는다. 옵션 반복으로 앞선 제외가 무력화되는 경우도 검사한다. 문자열 eval은 쓰지 않는다.

아래 모드 표는 **승인 필요로 판정된 명령에만** 적용한다. 빈 마커나 무료 명령은 차단하지 않는다.

| 입력 permission_mode | 응답 |
|---|---|
| default, acceptEdits, auto | ask. 실제 승인창 확인은 C단계로 남긴다. |
| plan, dontAsk, bypassPermissions | deny. 일반·편집 허용 모드에서 호출별 승인을 받도록 안내한다. |
| 누락, 알 수 없는 값 | deny. 지원되는 모드인지 확인하도록 안내한다. |

다른 훅이나 권한 규칙의 deny를 이 훅이 뒤집지 않는다. mode 판정은 입력 payload를 사용한다.
안내·systemMessage·함수명은 ask와 deny를 구분하고, 사유에는 마커·위험 옵션·프로젝트 사유를
포함한다. stdout은 UTF-8 JSON이며 종료 코드는 정상 판정 시 기존처럼 0이다.

### 함께 변경할 파일

- paid_test_check.py의 _policy 반환값에서 allow_env를 제거하고 V1 분기도 맞춘다.
  환경변수 우회 분기를 제거하고 docstring·응답 안내를 새 계약에 맞춘다.
- .claude/harness.json과 harness.schema.json에서 allow_env를 함께 제거한다.
  기존 V2 설정의 allow_env는 런타임에서 더는 사용하지 않는다. 실제 프로젝트의 마이그레이션
  안내에는 해당 필드와 우회 환경변수 제거를 명시한다. V1의 기본 마커는 유지하지만
  V1에서도 환경변수 우회는 제거한다.
- tests/_escape_hatches.py에서 ALLOW_PAID_TESTS를 제거한다. conftest의 과거 실측 수치는
  보존하고 현재 비용 훅에는 우회가 없다고 설명한다. 기존 test_escape_hatch는 단순 삭제로
  끝내지 않고 ALLOW_PAID_TESTS=1 또는 0을 줘도 판정이 유지되는 회귀 테스트로 바꾼다.
  이전 사용자 정의 allow_env도 더는 우회가 되지 않는지 확인한다.
- A단계의 정책 격리를 유지하면서 ask/deny 형식, BOM, 모드 표, 명령 표, 여러 유료 마커,
  V1 기본 integration과 V2 빈 마커를 테스트한다. subprocess payload에 모드를 명시한다.
- `pytest -m paid -q # --collect-only` 같은 PowerShell 주석은 수집 전용으로 오인하지
  않는지, `& "C:\Program Files\Python\python.exe" -m pytest -m paid -q`처럼 따옴표로
  감싼 공백 경로도 유료 명령으로 판정하는지 회귀 테스트한다.
- `#`가 단어 중간에 있는 `pytest ./foo# -m paid -q`에서 뒤의 `-m paid`가 잘리지 않는지,
  `pytest -m paid ./--collect-only -q`의 경로 이름을 수집 전용 옵션으로 오인하지 않는지
  검증한다. PowerShell의 백틱으로 따옴표를 이스케이프한
  ``pytest -m paid -q -o "junit_suite_name=x`"--collect-only"``도 실제 수집 옵션이
  없으므로 승인 대상인지 확인한다.
- .codex/hooks.json에서는 비용 훅 항목만 제거한다. 다른 훅은 보존한다.
  이 정리는 Claude용 ask가 공유 훅 파일에 반영되기 전 또는 같은 변경에서 수행한다.
  현재 미커밋 파일이므로 기존 다른 변경을 덮어쓰지 않는다.
- README에는 실제 프로젝트에 마커 등록, pytest addopts의 전체 유료 마커 제외,
  Fast/Full argv에도 같은 제외를 명시하는 적용 예시를 제공한다. 이 저장소의 빈 마커와
  프로필은 그대로 둔다. 실제 프로젝트 수정·설치·유료 실행은 이 작업에서 하지 않는다.
- 임시 프로젝트에 unit·paid·paid2 표시만 가진 무과금 테스트를 만들고, README 예시의
  기본 pytest와 Fast/Full의 pytest argv가 유료 표시 테스트를 선택하지 않는지 검증한다.
  Quality subprocess가 훅 승인을 거치지 않는 경로도 기본 제외로 보호되는지 확인한다.
- 현재 계약과 한계, 적용 전 필요한 C단계 검증을 knowledge/paid-test-approval.md에
  한국어로 요약한다. 미검증 동작을 확인된 사실로 쓰지 않는다.

## C단계: 사용자와 무과금 승인 동작 확인

Claude가 준비하고 사용자가 승인창을 조작한다. 실제 API와 사용자 프로젝트는 사용하지 않는다.
임시 프로젝트의 paid_probe 테스트는 네트워크·API 키 없이 로컬 실행 표식만 남긴다.
후보 훅과 최소 설정을 복사하고 paid_probe를 등록하며 기본 pytest에서는 제외한다.
공유 템플릿 설정을 바꿔 가며 검증하지 않고 임시 세션에서 진행한다.

| 확인 | 기대 결과 |
|---|---|
| 기본 pytest 및 모든 유료 마커를 제외한 호출 | 유료 표식 없는 무료 실행. 기본 수집 결과에서 paid_probe 제외 |
| default/acceptEdits/사용 가능한 auto에서 paid_probe 선택 | ask 승인창, 응답 전 표식 없음 |
| 거절한 뒤 표식 확인 | 유료 표시 테스트 실행 표식 없음 |
| 해당 호출만 승인한 뒤 동일 명령 재요청 | 첫 호출 표식 생성, 두 번째는 다시 승인 필요 |
| 임시 permissions.allow에 해당 pytest 허용 규칙 존재 | 비용 훅의 호출별 승인 유지 |
| plan/dontAsk/bypassPermissions 또는 알 수 없는 모드 | 비용 훅 deny, 유료 표시 테스트 실행 없음 |
| 승인 전달 수단이 없는 비대화형 실행 | 승인 필요 명령 실행 없음. 문서/JSON 검사만으로 통과 처리하지 않음 |

Claude는 재현 명령, 예상 화면, 표식 확인 방법, 원복·정리 방법을 보고에 준비한다.
새 CLI 세션이나 LLM 호출을 자동 실행해 비용을 발생시키지 않는다. 사용자가 조작할 환경이
없거나 아직 응답하지 않았으면 코드·자동 검증 완료 및 C 미확인으로 보고한다. 없는 결과를
요구하며 A/B 구현을 중단하지 않고, 사용자 확인 전 최종 배포·실제 유료 프로젝트 적용은 하지 않는다.
승인 없이 실행되는 경로가 관찰되면 해당 경로의 deny 유지/복구를 먼저 하고 원인을 기록한다.

## 품질 검사·완료·보존

A단계는 비용 훅 테스트와 전체 pytest를 실행한다. B단계는 변경 성격에 맞는 Fast 대상 테스트와
Full 세 단계를 가상환경 Python으로 각각 실행하고 종료 코드·통과/실패/건너뜀 수를 기록한다.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_paid_test_check.py tests/test_hook_wiring.py tests/test_v2_templates.py -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q
```

훅 소스는 quality.tracked_paths 밖이므로 자동 Fast에 기대지 않는다. 다른 훅 테스트에 대한
영향은 전체 pytest로 확인한다. 규칙 완화나 전면 포맷으로 실패를 숨기지 않는다.

- A 완료: 기존 훅 동작을 유지한 상태에서 설정 격리와 pytest 기준선이 통과한다.
- 코드·자동 검증 완료: B의 명령·모드·우회 제거·스키마·배선·적용 예시 검증이 통과하고
  C용 무과금 검증 절차가 준비됐다. C 결과와 구분해서 보고한다.
- 승인 동작 확인 완료: C의 사용 가능한 대상 환경에서 실제 결과가 기록됐다.
  지원하지 않는 모드는 차단 또는 명시적 미지원으로 남기고 보호를 확인했다고 쓰지 않는다.
- 최종 완료: 자동 검증, 대상 환경의 승인 동작 확인, Codex 결과 리뷰와 영구 문서 보존이 끝났다.
  C가 미확인이면 최종 완료·배포 준비 완료를 주장하지 않는다.
- 기존 리뷰의 C1~C4별 해결 근거, 변경 파일, 실행 명령, 미실행 이유, 단계별 상태,
  남은 사용자 확인 항목을 같은 리뷰에 영어로 추가한다. 기존 지적을 지우지 않는다.
- 명세·리뷰는 최종 리뷰와 보존 조건을 만족할 때까지 유지한다. 다른 작업 파일은 정리하지 않는다.
