# 1. 하네스 변경 감지와 Windows·Linux 검증 기반 보강

- 작업 ID: `harness-quality-ci`
- 실행 순번: **1 / 3**
- 상태: 완료 — 2026-11-23 최종 리뷰 승인. 보존된 두 OS hosted CI 보고 확인, 최신 판정 보존·임시 파일 정리 대기.
- 명세: `tasks/harness-quality-ci.md`
- 리뷰: `tasks/harness-quality-ci.review.md`
- 선행 작업: 완료된 `quality-env-setup`, `doctor`. 환경 계약은
  `.claude/wiki/knowledge/quality-env.md`, Doctor 구현 커밋은 `ceae2ca`다.
- 관계: 검증 환경 구축의 후속 작업이다. 의존성 설치를 다시 설계하지 않고 변경 감지,
  수동 실행 진입점, CI를 보강한다. 끝난 명세를 대체하거나 다시 열지 않는다.
- 조사 기준: 2026-11-22, `C:\my-harness`, `main / 675b461`.

## 목적

하네스의 훅·설정을 바꿨는데 Fast 검사가 실행되지 않는 빈틈을 닫는다. 같은 Quality Profile을
Codex의 수동 검사와 CI에서 실행해, 명령을 여러 곳에 복사하면서 기준이 갈라지는 것을 막는다.

실행 순서는 이 작업 → `tasks/template-core-packs.md` →
`tasks/template-install-smoke.md`다. 다음 구현은 선행 작업의 Codex 최종 리뷰가 끝난 뒤 시작한다.
설계 검토와 결과 리뷰, 명세 반영은 기존 인수인계 절차를 따른다.

## 실행 계약

새 표준 라이브러리 CLI `.claude/harness/scripts/run_quality.py`를 둔다.

```text
python .claude/harness/scripts/run_quality.py --profile full
python .claude/harness/scripts/run_quality.py --profile fast --changed .claude/settings.json
python .claude/harness/scripts/run_quality.py --profile fast --changed .claude/harness.json --changed tests/conftest.py
```

- `--profile`은 `fast`, `full`만 받는다. `--changed`는 프로젝트 상대 파일 경로로 반복 지정한다.
  절대 경로·루트 밖으로 해결되는 경로·파일 대신 디렉터리를 준 입력은 사용 오류다.
  삭제된 파일의 상대 경로는 허용하고, 존재하지 않는 매핑 대상은 stage 실행 실패로 드러낸다.
- 대상 루트는 CLI 자신의 배치 경로에서 결정한다. cwd나 상위 프로젝트의
  `CLAUDE_PROJECT_DIR`로 대상을 바꾸지 않는다. Doctor처럼 `__file__`의 배치를 검증하고,
  자신의 프로세스에서 `CLAUDE_PROJECT_DIR`를 그 루트로 설정하고 hooks를 `sys.path`에 넣은
  **다음** `_hookutil`·`auto_test_check`·`_quality`를 import한다. 임포트 뒤 전역값 패치는 하지 않는다.
- `_quality.run_profile()`을 호출한다. argv·timeout·성공 코드·중단 규칙을 새로 구현하지 않는다.
- Fast 대상 계산은 실제 훅의 `test_target_for()`와 `_matches_tracked()`, 공통 artifact 판정을
  재사용한다. `None`만 보고 원인을 추측하지 않고 아래 분류 표의 이유를 공유 함수로 제공한다.
  CLI는 훅 `main()`이나 세션 이벤트 처리기를 호출하지 않고 마커를 조작하지 않는다.
- 단계별 실행 명령, 실제 선택된 인터프리터, PASS/FAIL/SKIP/NOT RUN과 종료 코드를 출력한다.
  앞 단계 실패로 아직 도달하지 못한 단계는 NOT RUN(미실행)과 중단 원인을 표시한다.
- 수동 CLI는 훅의 `SKIP_*` 환경변수로 검사를 생략하지 않는다. 이 사실을 출력과 Knowledge에
  명시하고, CI에는 우회 변수를 설정하지 않는다. 임의의 stage 명령이 환경변수를 읽는 것까지
  통제한다는 뜻은 아니며, 자식 환경에서 모든 `SKIP_*`를 무차별 삭제하지 않는다.
- 이 CLI는 설정된 명령을 **실행한다**. 읽기 전용 Doctor와 구분한다. 명령 실행에 따른 pytest·Ruff
  캐시는 생길 수 있지만 **CLI 자체는** History·세션 마커를 만들지 않는다. 사용자가 설정한
  stage의 임의 부작용을 금지하거나 검증하는 샌드박스는 아니다.
- `full`은 변경 파일과 관계없이 실행한다. Fast에 `--changed`가 없거나 Full에 주면 사용 오류다.
  이 CLI의 설정 계약은 V2다. V1 런타임은 유지하지만 CLI에 V1을 주면 미지원 오류를 낸다.

## 범위와 제외

- 포함: `.claude/harness.json`, `.claude/settings.json`의 시간 예산, 위 CLI,
  V2 Fast 경로 분류·비차단 알림·매핑 수정, Doctor의 `check_python()`·`_target_for()`·관련 안내,
  공통 분기 대조 및 시간 예산 테스트,
  `.github/workflows/harness-quality.yml`, `README.md`, `quality-env.md`, `doctor.md`의 현재 상태.
- 제외: Codex 자동 훅 배선·승인, 유료 테스트 보호 계약 변경, RAG 기능 변경, 패키지 버전 일괄 갱신,
  공통·선택 구성 이동, 배포 ref 생성·푸시, 브랜치 보호 설정.
- Linux 실패는 원인을 분류하고 이 범위의 경로·인코딩·테스트 이식성 문제를 수정한다.
  대규모 동작 변경이 필요하면 근거를 리뷰에 남겨 설계로 돌린다. Linux 전체 skip으로 숨기지 않는다.
- 이 작업과 2번 사이에는 저장소 설정이 하네스 개발용으로 바뀌지만 배포 예시 분리는 아직
  끝나지 않은 과도기가 있다. README와 `test_v2_templates.py`의 설명을 개발 설정 검사로
  바로잡고, 이 시점의 `.claude/` 전체를 새 범용 설치물로 배포하지 않는다. 별도 배포 설정은
  2번이 소유하며 그 작업의 Profile 비활성 기본값을 이 작업에서 미리 구현하지 않는다.

## 기존 코드 근거

- `.claude/harness.json:14` — Quality 추적이 `src/`, `tests/`, `pyproject.toml`, 설정 하나뿐이다.
- `.claude/harness.json:17` — 매핑은 `src/` → `tests/` 하나다. 저장소에는 `src/`가 없다.
- `.claude/harness.json:32` — Fast가 pytest 수집 0건인 종료 코드 5도 성공으로 처리한다.
- `.claude/harness/hooks/auto_test_check.py:67` — V2 추적 경로를 읽는다.
- `.claude/harness/hooks/auto_test_check.py:108` — 설정의 매핑을 읽는다.
- `.claude/harness/hooks/auto_test_check.py:156` — `test_target_for()`는 직접 테스트 파일을 좁혀 실행하지만
  `tests/conftest.py` 같은 보조 파일은 매핑보다 먼저 `None`으로 돌려준다.
- `.claude/harness/hooks/_quality.py:94` — 없는 Profile은 빈 단계 목록이다.
- `.claude/harness/hooks/_quality.py:169` — 빈 목록 치환값은 단계를 SKIP한다.
- `.claude/harness/hooks/_quality.py:256` — Profile 실행과 실패 시 중단의 공통 엔진이다.
- `.claude/harness/hooks/_hookutil.py:181` — 설정 경로, Windows/POSIX venv, 현재 인터프리터 순으로 고른다.
- `tests/conftest.py:81` — 테스트 프로세스의 마커 저장소를 임시 폴더로 격리한다.
- `.claude/harness/scripts/doctor.py:1722` — `python` 키가 없어도 venv 선택을 설정 경로 누락으로
  표시해 `None`에 환경을 만들라는 WARN을 낸다. Codex 임시 루트 호출에서도 재현했다.
- `.claude/harness/scripts/doctor.py:1956` — `_target_for()`가 훅의 테스트 특례를 복제한다.
- `.claude/harness/scripts/doctor.py:2000` — 의도적 제외도 단순 `None`이면 누락 경고가 된다.
  이유 있는 제외와 실제 매핑 누락은 구분해야 한다.
- `.claude/harness/hooks/auto_test_check.py:281` — V2 Fast가 빈 대상의 SKIP 결과를 알리지 않는다.
- `.claude/harness/hooks/_hookutil.py:448` — `_is_artifact()`가 생성물 폴더 판정의 원본이다.
- `tests/test_hook_wiring.py:175` — 시간 예산 검사는 V1 상수만 보고 V2 stage 값을 보지 않는다.
- `.claude/settings.json:136` — Stop의 품질 훅 예산은 600초다. 현재 Full의 최장 stage도
  600초이고 합계는 840초다. 개별 stage뿐 아니라 순차 실행 합계도 밖의 예산을 넘는다.
- `.github/workflows/` — 조사 기준 리비전에는 추적 파일이 없다(`git ls-files .github`로 확인).

## 구현 범위

1. `.claude/harness.json`을 이 저장소의 실제 개발용 설정으로 바꾼다. 없는 `src/`·`pyproject.toml`
   기본값을 제거하고 아래 표를 반영한다. `source_prefixes`는 `.claude/harness/`, `tests/`로,
   `history.tracked_paths`는 이 두 경로와 `.claude/settings.json`, `.claude/harness.json`,
   `requirements.txt`, `ruff.toml`로 한다. 훅 변경도 기록의 중요성을 **판단**하는 대상이다.
   판단 결과가 중요하지 않으면 기존대로 무기록이 가능하며 매 수정마다 History를 쓰라는 뜻은 아니다.
   `.github/workflows/`, Wiki·스킬 전체·작업 명세는 History 추적에 추가하지 않는다.
2. 이 저장소의 Fast `success_codes`는 `[0]`으로 한다. 공통 엔진이나 V1의 `[0, 5]` 호환 동작은
   바꾸지 않는다. 실제 pytest를 실행했는데 수집이 0건인 경우(작성 중인 빈 `test_*.py` 포함)를
   검증 성공과 구분하기 위함이다. **매핑 자체의 누락은 별도 분류로 잡는다.** 종료 코드 5이면
   실패 메시지에 「수집된 테스트 없음」을 명시한다. 빈 파일 작성 중의 일시 실패도 이 정책의 비용이다.
3. `auto_test_check.py`의 V2 직접 테스트 분기에서 `test_*.py`는 기존처럼 해당 파일,
   `conftest.py`·`_escape_hatches.py` 같은 나머지 테스트 Python 파일은 `tests/`를 돌린다.
   캐시·비Python 파일 제외 및 V1 동작은 보존한다. Doctor의 `_target_for()`에도 같은 V2
   테스트 특례를 적용하고, 실제 훅과의 대조 테스트를 추가한다. Doctor는 런타임 훅을 import하지 않는다.
   `check_mapping()`도 의도적 제외·비Python 테스트 파일과 매핑 누락을 구분해 거짓 누락 WARN을
   내지 않게 한다. 디렉터리 전수 탐색은 추가하지 않는다.
4. 아래 경로 분류를 공통 함수로 구현해 수동 CLI와 V2 Fast가 같은 이유를 사용하게 한다.
   기존 `test_target_for()`와 추적·artifact 원본을 사용하며, 별도의 독립 매핑 엔진을 만들지 않는다.
   추적 파일의 매핑 누락이 있으면 Fast 훅은 세션당 한 번 비차단 `systemMessage`를 낸다.
   해당 파일, `quality.mappings` 추가 또는 이유 있는 `unmapped_by_design` 등록을 안내한다.
   `claim_session()`과 전용 namespace를 사용하되 CLI는 그 마커를 만들지 않는다.
   올바른 대상도 함께 있으면 알림 뒤 그 대상 검사는 실행한다. 의도적 제외만 있으면 알리지 않는다.
   이 알림을 `_hookutil.block()`으로 바꾸거나 매 수정마다 차단하지 않는다. V1은 유지한다.
   매핑이 필요한지는 stage가 `{mapped_targets}`를 쓰는지로 판단한다. `{changed_files}`만 쓰는
   언어 중립 명령에 pytest 매핑을 강요하지 않는다.
5. `run_quality.py`를 구현한다. 설정 부재·손상, 없는/빈 Profile, 필요한 단계의 빈 치환값은
   성공으로 포장하지 않는다. CLI에서 먼저 검증하되 공통 엔진의 기존 실패 허용 계약은 바꾸지 않는다.
   복수 파일 중 하나라도 실제 매핑 오류면 실행 전 ERROR로 종료한다. 사용자가 제외한 파일과
   생성물은 따로 SKIP 이유를 출력하고, 실행 가능한 대상은 중복을 제거해 엔진에 전달한다.
6. Doctor의 `check_python()`은 **키 부재 + venv 발견**을 정상 자동 탐색 PASS로 표시한다.
   선택 경로·출처·Doctor 루트 기준이라는 한계를 적고, 실행 성공이나 모듈 설치를 보장하지 않는다.
   명시한 경로가 없어서 대체된 경우는 WARN을 유지한다. venv도 없으면 현재 인터프리터 대체의
   기존 WARN을 유지하되 `None`에 환경을 만들라는 안내는 제거한다. 소비자의 탐색 순서는 바꾸지 않는다.
7. 시간 예산은 아래 표로 고치고, V2 stage 값과 실제 배선의 외부 timeout을 비교하는 테스트를
   추가한다. V1 상수 검사도 유지하되 두 계약을 구분한다. V2는 각 stage의 개별 상한과 함께
   `sum(stage.timeout) + 30 <= 해당 훅 timeout`을 검사한다. 합산 대상은 그 Profile을
   순차 실행하는 stage 전부다. 종전 테스트의 「최댓값만 본다」는 설명을 V1 범위로 한정한다.
8. CI는 Python **3.12**, 하나의 `quality` job 정의와 OS matrix로 한다.
   `strategy.matrix.os: [windows-latest, ubuntu-latest]`, `runs-on: ${{ matrix.os }}`,
   `strategy.fail-fast: false`로 두 실행 결과를 모두 얻는다. 각 실행은
   checkout → Python 준비 → `.venv` 생성 → 고정 requirements 설치 → `pip check` →
   Doctor → `run_quality.py --profile full` 순으로 실행한다. venv 실행 파일은 OS별로 명시한다.
   가상환경 디렉터리는 캐시하지 않는다. 일반 Profile 명령을 YAML에 다시 적지 않는다.
9. 트리거는 `push`, `pull_request`, `workflow_dispatch`, 권한은 `contents: read`로 한다.
   최초에는 경로 필터를 두지 않는다. PowerShell에서 여러 외부 명령을 한 step에 넣으면
   중간 실패도 명시적으로 전파하거나 명령별 step으로 나눠 마지막 코드에 가려지지 않게 한다.
   각 단계 실패가 job 실패로 전파되며 `continue-on-error`로 필수 검사를 감추지 않는다.
10. README·Knowledge·`test_v2_templates.py`의 설명에 현재 개발 설정, 수동 CLI, CI,
    실제 timeout, 추적·분류, Python 3.12 검증 범위를 반영한다. 3.11의 오래된 캐시는 지원
    근거가 아니다. 이 작업에서 3.11 지원이나 런타임 최소 버전을 새로 보장하지 않는다.
    `doctor.md`의 「scripts는 추적 범위 밖」 설명을 고친다. 과거 실측 행은 날짜·주체와
    함께 보존하고 새 실행 결과를 별도로 기록한다. 405·651 같은 수치를 새 결과로 덮어쓰지 않는다.

### 심각도와 종료 코드

| 상황 | CLI 판정 / 코드 |
|---|---|
| 필요한 모든 단계가 실제 실행되어 성공 | PASS / 0 |
| Profile stage 실패·timeout·실행 불가 | FAIL / 1 |
| 사용 오류, 설정 손상, 미지원 버전, 없는/빈 Profile, 필요한 단계의 빈 치환값 | ERROR / 2 |
| Fast의 변경 파일 전부가 아래 표의 의도된 검사 제외 | SKIP / 0. 검사 통과라고 쓰지 않는다 |
| 매핑을 요구하는 stage인데 추적 파일에 매핑도 제외 이유도 없음 | ERROR / 2. 혼합 입력도 실행 전에 실패 |
| 앞 단계 실패 뒤 도달하지 못한 단계 | NOT RUN. 전체 종료 코드는 처음 실패에 따른다 |

Fast 경로 분류의 우선순위는 사용 오류 → 생성물 → 비추적 → 의도적 제외 → 테스트 특례 →
일반 매핑이다. 훅 입력은 기존 루트 정규화를 거친 경로를 사용한다. CLI의 외부 경로는 사용
오류지만, 훅의 무관한 외부 파일 호출은 기존처럼 무시한다.

| 원인 | CLI | V2 Fast 훅 |
|---|---|---|
| 절대 경로·루트 밖·디렉터리 입력 | ERROR / 2 | 도구 payload의 절대 파일 경로는 기존대로 루트 상대 경로로 정규화 |
| `_hookutil._is_artifact()`에 해당 | SKIP / 0, 생성물 사유 | 조용히 제외 |
| 추적 밖 | SKIP / 0, 비추적 사유 | 조용히 제외 |
| `unmapped_by_design`에 사유가 있는 일치 | SKIP / 0, 설정된 사유 | 조용히 제외 |
| `tests/` 아래 비Python 파일 | SKIP / 0, 현재 테스트 특례가 검사하지 않는 파일임을 명시 | 기존대로 제외 |
| `tests/test_*.py` | 해당 파일 실행 | 해당 파일 실행 |
| `tests/` 아래 기타 Python 보조 파일 | `tests/` 실행 | `tests/` 실행 |
| 일반 매핑 일치 | 매핑 대상 실행 | 매핑 대상 실행 |
| 추적되지만 필요한 매핑이 없음 | ERROR / 2 | 세션당 한 번 비차단 알림. 유효 대상이 있으면 그 검사는 실행 |

테스트 fixture 같은 비Python 파일도 이 작업에서는 자동 테스트 대상에 넣지 않는 기존
정책을 유지한다. 그 한계를 Knowledge에 적으며, 이를 검증했다고 보고하지 않는다.

Doctor는 기존 0/1/2 의미를 유지한다. WARN을 일괄 실패로 바꾸지 않는다. 이 저장소에서
설정 누락·매핑 누락으로 생긴 WARN은 해결하고, 미검사 WARN은 실제 한계로 보고한다.

### 열거해야 할 표

Fast 매핑은 우선 보수적으로 전체 테스트를 사용한다. 정밀 매핑 최적화는 이 작업에 포함하지 않는다.
Claude의 Round 1 보고에서 전체 실행은 651 passed·1 skipped, 15.80~20.97초였다.
Codex가 재측정한 전체 실행 시간은 아니다. 하네스 코드 한 파일 수정에도 이 비용이 생기는
선택을 수용한다. Fast timeout 90초는 유지하고, 향후 초과 시 실패를 숨기지 않고 매핑을 재검토한다.

| 추적 경로 | Fast 대상 | 이유 |
|---|---|---|
| `.claude/harness/` | `tests/` | 훅·공유 모듈·스크립트·스키마가 서로 영향을 준다 |
| `.claude/settings.json` | `tests/` | 배선과 timeout 계약을 검증한다 |
| `.claude/harness.json` | `tests/` | 매핑·Profile·Doctor 계약에 영향을 준다 |
| `tests/` | 직접 테스트는 해당 파일, 보조 Python은 `tests/` | 위 V2 분기 변경으로 보장한다 |
| `requirements.txt`, `ruff.toml` | `tests/` | 도구·설정 변경 뒤 회귀를 확인한다. Ruff 자체 실행은 Full이 담당한다 |
| `.github/workflows/` | 의도적 제외 이유 기록 | Python 테스트로 hosted CI 실행을 증명하지 않는다. Full 및 실제 CI 결과로 확인한다 |

추적 파일을 추가하면 매핑 또는 이유가 있는 제외가 필요하다. `why`에 각 매핑의 근거를 적는다.
workflow는 Quality 추적에 **포함한다**. Fast만 의도적으로 제외하고 workflow만 고쳐도
Stop/Full은 실행하는 정책이다. hosted CI가 검증됐다는 주장은 실제 원격 실행 결과로만 한다.

| V2 실행 경로 | stage timeout | 바깥 훅 timeout | 순차 합계와 여유 |
|---|---|---|---|
| Fast / PostToolUse | test 90초 | 120초 유지. 두 matcher 그룹 모두 검사 | 90 + 30 <= 120 |
| Full / Stop | lint 120, format 120, test **540초** | **900초로 변경** | 780 + 30 <= 900 |
| Full / pre_commit | 같은 Full Profile | 900초 유지 | 780 + 30 <= 900 |

개별 최대만 비교하면 앞 단계에서 쓴 시간이 빠진다. 따라서 C-02의 최소 제안보다 강화해
V2에서는 순차 합계도 검사한다. 이 값은 바깥 프로세스가 실패 사유를 내기 전에 죽는 위험을
줄이는 설정 검사이며, OS 스케줄링 지연까지 엄밀히 보장하는 전체 deadline 구현은 아니다.

### 호환성

스키마 V2를 유지한다. 새로운 필수 설정 키를 만들지 않는다. Windows/POSIX venv 자동 탐색이
이미 있으므로 설정의 `python` 키는 제거해 두 OS가 각자의 `.venv`를 쓰게 한다. CLI는 실제
선택 경로를 출력하고 CI는 준비한 venv와 일치하는지 확인한다. Doctor의 복제한 선택 분기도
소비자와 대조한다. 선택 알고리즘 변경 없이도 **진단 메시지의 오류는 이번 범위에서 고친다**.
`check_python()`과 `_target_for()`의 판정·메시지 수정은 포함 범위다. Doctor가 실제 훅의
루트나 명령 성공을 관찰한다고 표현하지 않고, 정적 진단·표준 라이브러리 전용 경계를 유지한다.

### 보안·비용 경계

LLM·RAG API·실제 문서 처리를 호출하지 않는다. CI 패키지 설치 외 외부 서비스는 필요 없다.
API 키·개인 노트·사용자 홈을 테스트 입력으로 사용하지 않는다. 실패 주입은 임시 프로젝트에서
수행하고 실제 체크아웃을 망가뜨리거나 커밋하지 않는다. CI 파일 작성은 이 작업 범위지만
원격 커밋·푸시·브랜치 설정 변경을 자동으로 수행하지 않는다.

## 구현 및 검증

- 기존 테스트를 먼저 실행해 기준선을 기록한 뒤, 매핑과 실행 진입점의 실제 동작을 검증한다.
- 임시 프로젝트에서 훅 파일·공유 설정·테스트 보조 파일 변경 각각이 실행 대상으로 이어지는지 본다.
  매핑 함수만 확인하지 않고 PostToolUse payload → stage 호출까지 연결되는 검사도 둔다.
- 임시 프로젝트에서 실패 stage, 비어 있는 Profile, 잘못된 훅 경로, 없는 테스트 대상,
  테스트 0건을 넣어 실패가 보이는지 확인한다. CLI의 실제 subprocess 종료 코드도 확인한다.
- 경로 분류 표의 각 원인, 유효 파일 + 매핑 누락의 혼합 입력, `{changed_files}`만 사용하는
  stage를 검사한다. artifact 판정은 기존 원본을 사용했는지 확인한다.
- 추적·매핑 누락 payload는 비차단 메시지를 세션당 한 번 내고, 새 세션에는 다시 알린다.
  의도적 제외는 알리지 않으며 다른 유효 대상 검사를 막지 않는다. CLI 호출은 알림 마커를 만들지 않는다.
- `python` 키 부재 + venv 발견은 D-PYTHON PASS이고 메시지에 `None`이 없어야 한다.
  명시 경로 누락 및 venv 미발견은 기존 WARN이고 대체 순서 대조 테스트도 유지한다.
- Doctor와 훅의 대상 대조 입력은 `tests/test_doctor.py`, `tests/conftest.py`,
  `tests/_escape_hatches.py`, `tests/fixtures/a.json`, `tests/__pycache__/x.pyc`,
  `.claude/harness/hooks/_quality.py`, `.claude/harness/scripts/doctor.py`, `.claude/settings.json`이다.
  의도적 제외 입력도 포함한다. 어느 한쪽 특례만 바꾸면 실패해야 한다.
- V2 실제 stage와 모든 관련 matcher 그룹의 외부 예산을 비교한다. 현재 600/600과
  `각 stage < outer`만 만족하지만 `sum + 30 > outer`인 설정 모두 테스트에서 실패해야 한다.
- 잘못된 `CLAUDE_PROJECT_DIR`와 외부 cwd에서도 CLI는 자기 프로젝트를 실행해야 한다.
- `SKIP_AUTOTEST=1`, `SKIP_PRECOMMIT=1`인 CLI 호출도 실패 stage를 실제 실행하고 1을 반환해야 한다.
  NOT RUN 출력과 종료 코드 5의 구체적인 사유도 검증한다.
- 부작용 없는 probe를 stage로 설정하고 CLI 실행 전후 임시 History·마커 경로의 상태를 비교한다.
  도구 자체가 History·마커를 만들지 않음을 검사하되 stage의 부작용까지 일반화하지 않는다.
- Fast는 위 변경의 영향 테스트, Full은 새 CLI로 실행한다. 출력에는 SKIP을 분리한다.
- GitHub 공식 문서에 따라 workflow를 작성한다:
  [Python CI](https://docs.github.com/en/actions/tutorials/build-and-test-code/python),
  [workflow 문법](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).
  액션 ref는 구현 시 공식 지원 버전을 확인하고 사용한 버전을 리뷰에 적는다.
- 원격 실행 권한이나 푸시가 없으면 로컬 구현 검증과 hosted CI 미검증을 구분해 보고한다.
  CI job이 실제로 돈 것처럼 기록하지 않는다. 후속 설계 검토는 가능하지만 다음 구현 착수 전에
  두 OS 성공 근거를 확보하거나 사용자가 미검증 제약을 명시적으로 수용해야 한다.

## 완료 기준

- [x] 현재 저장소 설정에서 훅·스크립트·공유 설정 변경이 Fast 테스트 대상과 연결된다.
  다른 Profile의 검사 제외 계약도 HQCI-01 수정 후 재확인했다.
- [x] 필요한 매핑 누락을 Fast 훅이 비차단 알림으로 드러내고, CLI는 ERROR로 구분한다.
  사유 없는 제외 항목도 HQCI-03 수정 후 문제로 분류한다.
- [x] 생성물·비추적·의도적 제외·비Python 테스트 파일을 매핑 오류로 잘못 판정하지 않는다.
  정책상 제외한 파일은 실행 입력에서도 빠지는 것을 확인했다.
- [x] 테스트 보조 Python 수정도 전체 테스트를 호출하고 직접 테스트 수정은 좁은 대상을 유지한다.
- [x] Doctor의 자동 인터프리터 선택 메시지와 대상 계산이 실제 소비자 분기와 일치한다.
- [x] V2 순차 stage 합계와 외부 시간 예산이 검사되고 배선의 모든 해당 이벤트가 덮인다.
- [x] 수동 CLI와 훅이 같은 Profile 엔진을 쓰며, 설정 결함·실패·SKIP을 구분한다.
  HQCI-01~HQCI-03의 입력·설정 경계도 수정 후 재확인했다.
- [x] CLI가 훅 우회 변수에 의해 생략되지 않고, 미도달 단계·수집 0건·자체 부작용의 범위가 검증된다.
- [x] 이 저장소의 Fast는 수집 0건을 성공으로 인정하지 않는다. V1 호환 테스트는 유지된다.
- [x] Windows 로컬 Full과 두 OS hosted CI가 성공한다.
  실행 코드 `0e52390`, run `45033823289`의 Windows/Linux 성공 보고를 확인했다.
  Codex의 원격 재조회는 연결 오류로 실패했으며 최종 판정의 근거와 한계를 아래에 기록했다.
- [x] Knowledge와 README가 실제 추적·실행 방식과 일치한다. HQCI-N01 보완을 확인했다.
- [x] Claude가 같은 ID의 리뷰에 실행 명령·인터프리터·결과·미실행 이유를 기록하고,
  Codex가 이 명세에 최종 판정과 남은 보존·정리 작업을 반영했다.

## Codex 설계 리뷰 반영 — Round 1

- 검토: 2026-11-22, `C:\my-harness`, `main / 675b461`.
- 대상: Claude의 `tasks/harness-quality-ci.review.md` Round 1. 구현 전 검토가 끝났으며
  실제 코드·설정 변경은 아직 없다. Claude 소유 리뷰 파일은 수정하지 않았다.
- 판정: **C-01~C-05의 핵심 지적을 채택해 설계에 반영했다. 수정 명세 재검토 대기이며
  구현 완료 판정은 아니다.** C-02는 최대 stage만 비교하는 제안보다 합산 예산까지 강화했다.
  C-03의 비차단 알림은 원래 목적의 누락을 보완하는 범위로 포함한다.

| ID | 판단과 수정 | 구현에서 확인할 기준 |
|---|---|---|
| C-01 | 채택. `check_python()` 메시지 수정 포함. 자동 venv 발견과 명시 경로 실패를 분리 | 키 부재 + venv는 PASS, `None` 안내 없음. 탐색 순서는 소비자와 같음 |
| C-02 | 채택·보강. Full test 540초, Stop 900초. V2 개별·순차 합산 예산 검사 | 현재 600/600 및 합산 초과 설정을 모두 검출 |
| C-03 | 채택. V2 Fast에 세션당 한 번 비차단 매핑 누락 알림 | 실제 payload에서 알림. 의도적 제외는 무알림. 유효 대상 실행은 유지 |
| C-04 | 채택. 경로 원인 분류와 추적·artifact 원본 재사용 명시 | 외부 경로 ERROR, 정책상 제외 SKIP, 필요한 매핑 누락 ERROR를 구별 |
| C-05 | 채택. Doctor의 대상 특례 수정과 실제 훅 대조 테스트 | 한쪽만 수정하면 대조 테스트 실패 |
| C-06 | 채택. `[0]` 유지 사유를 실제 수집 0건 구분으로 수정 | 매핑 누락 SKIP과 pytest exit 5를 혼동하지 않음 |
| C-07 | 채택. 전건 Fast의 보고된 15.80~20.97초 비용을 명시 | 향후 실제 실행 시간을 주체·날짜와 기록. 정밀 매핑은 후속 |
| C-08 | 채택. 하나의 job 정의와 두 OS matrix로 명확히 함 | `fail-fast: false`로 한 OS 실패가 다른 OS 검증을 취소하지 않음 |
| C-09 | 채택. 파일 배치 검증 → 환경·import 경로 고정 → import 순서 명시 | 잘못된 환경변수·외부 cwd에서도 자신의 루트 검사 |
| C-10 | 채택. 수동 CLI는 훅 우회 변수를 검사 생략 근거로 사용하지 않음 | SKIP 변수가 있어도 실패 probe 실행·비정상 종료 |
| C-11 | 채택. NOT RUN과 실패로 중단된 후속 단계 목록 추가 | 실패 뒤 미도달 단계를 성공·단순 누락으로 보이지 않게 함 |
| C-12 | 채택·한정. CLI 자체 History·마커 부작용 검증 | 임시 경로 불변. 임의 stage의 부작용까지 없다고 주장하지 않음 |
| C-13 | 채택. 개발 설정 전환과 2번 배포 설정 분리 사이의 과도기를 명시 | README·소스 테스트 설명 수정. 범용 배포 완료 주장은 2·3번 뒤 |
| C-14 | 채택. 경로·Profile·timeout·실측 문서 갱신 범위 구체화 | 과거 근거는 날짜·주체와 보존하고 이번 결과를 새로 적음 |
| C-15 | 채택. 반복 `--changed` 예제 추가 | 파일 두 개 입력의 의미가 명확함 |

추가 확인 D-01: `.claude/harness/scripts/doctor.py:2000`은 `_target_for()`의 `None`을 곧바로 누락으로 처리한다.
따라서 이유 있는 제외와 실제 누락의 구분도 구현 범위에 넣었다. Doctor의 정적 검사·한정된
매핑 확인 범위를 유지하며 디렉터리 전수 탐색으로 확대하지 않는다.

| 미결 질문 | Codex 결정 |
|---|---|
| Q-1 workflow Quality 추적 | 포함한다. Fast는 의도적 제외지만 Stop/Full 대상은 유지한다 |
| Q-2 History 추적 확대 | 실제 하네스 코드·공통 설정은 중요도 판단 대상으로 포함한다. 매 수정마다 기록할 의무는 추가하지 않는다 |
| Q-3 Python 버전 | 개발 권장·CI 검증은 3.12. 3.11 지원이나 런타임 최소 버전 보장은 이번 범위에서 정하지 않는다 |

### 검증 근거와 한계

- Codex 직접 실행:
  `.venv/Scripts/python.exe -m pytest tests/test_doctor.py tests/test_hook_wiring.py tests/test_auto_test_check.py -q`
  → **308 passed, 1 skipped, 15.39초**. skip은 기존 Windows 실행에서의 POSIX 검사다.
- 임시 루트에 가짜 venv 실행 파일을 두고 실행하지 않은 채 `check_python()`을 호출해 C-01의
  WARN과 `None` 안내를 재현했다. 실제 인터프리터의 동작·설치 검증은 아니다.
- Doctor의 `tests/conftest.py` 대상이 현재 `None`임을 확인했다. C-05는 아직 적용되지 않은
  훅 수정이 만들 불일치의 위험이며, 현재 코드에서 이미 두 함수가 다르다고 주장하지 않는다.
- 설정을 직접 읽어 Full `[120, 120, 600]`과 Stop `600`, 합계 `840`을 확인했다.
- GitHub 공식 workflow 문서의 `jobs.<job_id>.strategy.fail-fast`가 matrix 전체에 적용됨을
  확인했다. 위 문법 링크가 원본이다. hosted CI를 실행한 근거는 아니다.
- 소스·설정 변경 없이 명세만 수정했다. 기존 테스트는 리뷰 근거 확인용으로 한정 실행했으며
  Ruff·전체 pytest·Fast/Full Profile·Linux·hosted CI는 이번에 실행하지 않았다.
- 테스트 통과는 현재 검사 범위의 회귀가 없다는 뜻이다. 이번에 제안한 결함 방지 테스트와
  수정 구현의 성공 근거로 사용하지 않는다.

### 다음 인수인계

Claude는 수정된 같은 명세를 재검토하고 C-01~C-05 및 추가 반영의 모순·누락이 있으면 같은
리뷰 파일에 다음 라운드로 적는다. 구현을 마치면 실제 변경과 검증을 보고하고 Codex의 결과
리뷰를 받는다. 2·3번 명세와 Claude의 리뷰 파일은 이 설계 리뷰에서 수정하지 않았다.

## Codex 구현 결과 리뷰 — 2026-11-22

이 절은 **첫 구현 결과 리뷰의 이력**이다. 당시 지적 HQCI-01~HQCI-03은 아래
「Codex HQCI 수정 라운드 결과 리뷰」에서 해소를 확인했다. 현재 판정은 그 절과 머리글을 따른다.

- 체크아웃: `C:\my-harness`, `main / 675b461` + 미커밋 구현 변경.
- 대상: `tasks/harness-quality-ci.review.md`의 Round 2와 Implementation report, 실제 변경
  13개 추적 파일, 새 CLI·workflow·테스트. Claude의 구현 보고 단계가 끝난 것을 확인했다.
- 판정: **수정 필요. HQCI-01~HQCI-03이 남아 구현 완료로 승인하지 않는다.**
  현재 기본 설정의 Windows Full은 통과하지만 언어 중립 Profile과 설정 경계에서 재현된
  결함이 있다. Linux·hosted CI는 별도로 미검증이며, 통과한 로컬 검사로 대신하지 않는다.
- 이 결과 리뷰는 명세만 갱신한다. Claude의 코드·설정·리뷰 파일과 2·3번 명세는 수정하지 않는다.

### HQCI-01 · P1 · 매핑을 쓰지 않는 Fast가 제외된 파일까지 실행한다

- 현재 상태: **해소** — HQCI 수정 라운드 결과 리뷰 참조.
- 위치: `.claude/harness/scripts/run_quality.py:166`, `:316`, `:342` 및
  `.claude/harness/hooks/auto_test_check.py:447`, `:467`, `:474`.
- 재현: 임시 프로젝트의 Fast stage를 `{changed_files}`만 받는 표준 라이브러리 probe로
  설정한다. `docs/`는 추적하지만 `unmapped_by_design`에 실제 사유와 함께 등록한다.
  `--profile fast --changed docs/a.md`를 실행하면 출력은 파일을 SKIP으로 분류하면서
  **probe가 실제 실행되어 `['docs/a.md']`를 받고 전체 PASS / 0**이 된다.
  CLI에 비추적 `other/a.md`만 줘도 같은 일이 일어난다.
- 훅도 별도로 재현했다. 같은 임시 설정에 실제 `PostToolUse`/`Edit` payload와
  `docs/a.md` 절대 경로를 전달하면 exit 0이고 probe가 실행되어 `['docs/a.md']`를 받는다.
  두 경로 모두 `mapping_required and not targets`만으로 실행 여부를 정하기 때문이다.
- 혼합 입력도 문제다. `src/a.py`와 제외한 `docs/a.md`를 함께 주면 stage의
  `{changed_files}`에 두 파일이 모두 전달된다. 분류 결과가 실제 실행 인자를 제한하지 않는다.
- 기대 동작: **실행할 변경 파일의 존재**와 **매핑 필요 여부**를 분리한다.
  `CAUSE_TARGET`, `CAUSE_NO_MAPPING_NEEDED`는 실행 가능한 원인이고, 실제 정책상 제외된
  원인은 실행 대상이 아니다. 전부 제외면 CLI는 SKIP / 0, 훅은 실행하지 않는다.
  유효 파일이 섞이면 `{changed_files}`에는 정규화된 유효 파일만 전달한다.
  매핑이 필요 없는 정상 추적 파일은 매핑 부재만으로 막거나 건너뛰지 않는다.
  `CAUSE_NO_MAPPING_NEEDED`를 출력에서 「이 파일은 SKIP」이라고 오표시하지 않는다.
- 수정 지시: CLI와 훅이 공유 분류 결과를 실행 입력에 반영하게 고친다. 공통 엔진의
  placeholder 확장 계약을 바꾸거나 pytest 매핑을 언어 중립 Profile에 강요하지 않는다.
- 검증 기준: CLI·실제 훅 payload에서 각각 (1) 사유 있는 제외만, (2) 생성물만,
  (3) 비Python 테스트 파일만, (4) 유효 파일만, (5) 유효 파일 + 제외 파일을 검사한다.
  CLI에는 비추적만인 경우도 포함한다. 앞 세 경우는 probe 실행 흔적이 없어야 하고,
  유효 파일만인 경우는 실행, 혼합 입력은 유효 파일만 인자로 받아야 한다.
  `{mapped_targets}`를 쓰는 기존 Fast와 매핑 없는 정상 추적 파일도 계속 동작해야 한다.

### HQCI-02 · P2 · V2 전용 CLI가 미지원 버전 3도 실행 후 PASS로 보고한다

- 현재 상태: **해소** — HQCI 수정 라운드 결과 리뷰 참조.
- 위치: `.claude/harness/scripts/run_quality.py:265`, 원인인 공통 helper는
  `.claude/harness/hooks/_hookutil.py:80`·`:85`.
- 재현: 임시 프로젝트에 `schema_version: 3`과 성공 probe 하나의 Full을 설정한다.
  CLI가 probe를 실제 실행하고 **PASS / 0**으로 끝나는 것을 확인했다.
- 근거: CLI는 `if not _hookutil.is_v2()`로 검사하지만 이 helper의 의미는 `>= 2`다.
  기존 훅의 기능 분기 의미를 CLI의 「지원하는 버전은 정확히 2」 계약에 사용했다.
- 기대 동작: 버전 2만 실행하고 나머지는 실행 전 ERROR / 2다. 이후 버전의 설정을
  이해한 것처럼 명령을 실행하거나 성공을 보고하지 않는다.
- 수정 지시: CLI의 입력 검증에서 정확한 V2 계약을 확인한다. V1·기존 훅이 의존하는
  `_hookutil.is_v2()`의 `>= 2` 의미는 바꾸지 않는다.
- 검증 기준: 3 및 더 큰 정수, 1/부재, 문자열·실수·bool 등의 잘못된 버전은 ERROR / 2,
  probe 미실행이다. 정확한 정수 2는 정상 실행한다. Doctor의 버전 판정과도 모순되지 않아야 한다.

### HQCI-03 · P2 · 사유가 빈 제외 설정도 정상 SKIP으로 인정한다

- 현재 상태: **해소** — HQCI 수정 라운드 결과 리뷰 참조.
- 위치: `.claude/harness/hooks/auto_test_check.py:167`, `:315` 및 이를 소비하는
  `.claude/harness/scripts/run_quality.py:291`. Doctor의 `_benign_without_mapping()`도
  제외 key의 존재만 보는 관련 소비자다.
- 재현: 임시 V2 프로젝트에서 `unmapped_by_design: {"src/": ""}`로 두고
  `{mapped_targets}`를 쓰는 Fast에 `--changed src/a.py`를 준다.
  출력은 「등록돼 있지만 사유가 비어 있습니다」라고 적으면서도 이를 정상 제외로 분류해
  **SKIP / 0**, probe 미실행으로 끝난다.
- 근거: `_unmapped_reason()`이 빈 값에도 설명용 대체 문자열을 돌려주어, 문서화된 제외
  사유가 있는 것과 같은 `CAUSE_EXCLUDED`가 된다. non-string 값도 빈 문자열로 바뀐다.
  이번 명세가 허용한 것은 **사유가 있는 의도적 제외**이며 이 경우는 그 조건을 만족하지 않는다.
- 기대 동작: V2의 빈 값·공백뿐인 값·문자열이 아닌 값·사유 없는 목록형 설정을 유효한
  제외로 취급하지 않는다. CLI는 설정 결함 ERROR / 2로 실행 전에 알리고, 훅은 비차단
  알림 경로로 문제를 드러낸다. 유효한 사유는 지금처럼 조용히 제외한다.
  Doctor도 이 상태를 정상적인 사유 있는 제외라고 표시하지 않아야 한다.
- 수정 지시: 사유의 유효성을 분류에 반영한다. V1의 기존 목록형 제외 호환 동작은
  유지하며, 사용자에게 없는 사유를 자동으로 만들어 정상 제외로 바꾸지 않는다.
- 검증 기준: `""`, 공백, `null`/비문자열, 목록형에 대한 V2 실패와 비차단 알림을
  확인하고, 실제 사유가 있는 경우의 정상 SKIP·V1 기존 호환성을 함께 검사한다.

### 문서 보완 HQCI-N01 · P3

현재 상태: **반영 확인** — 아래 수정 라운드 결과 리뷰 참조.

핵심 수정과 함께 다음 누락·부정확한 설명도 정리한다.

- `quality-env.md`에 R2-03의 실제 운영 비용을 적는다. 하네스 코드를 수정한 세션은
  중요도 판단이 없으면 Stop이 한 번 차단되고 `history-significance` 호출이 필요하다.
  판단 후 기록을 생략할 수 있다는 것과 판단 호출 자체가 필요하다는 것을 구분한다.
- 수동 CLI가 훅 우회 변수에 의해 생략되지 않는 계약은 구현 docstring·테스트에는 있으나
  사용자 출력과 Knowledge에는 아직 명확하지 않다. 명세의 출력·Knowledge 요구를 반영한다.
- `doctor.md`의 새 실측 행은 해결된 WARN 넷에 D-PYTHON 메시지 결함을 포함하지만,
  기준 실행은 `python` 키가 있어 D-PYTHON PASS였다. 사라진 WARN은 없는 경로 관련
  D-SCAFFOLD 3건과 설정의 D-MAPPING 1건이며 메시지 수정은 별도 개선이다.
- `quality-env.md`의 「full은 경로와 무관하게 stop에서 돈다」는 설명은 실제 V2 Stop의
  `_v2_session_changes()` 추적 조건에 맞게 한정한다. pre_commit과 Stop의 조건은 다르다.

### 수용한 구현 선택과 확인한 사항

- `run_quality.py`가 표준 라이브러리 Doctor의 `resolve_root()`를 재사용한 것은 수용한다.
  Doctor가 훅을 import하지 않는 경계는 유지되고 배포 작업도 두 CLI를 포함하도록 설계돼 있다.
- workflow에서 두 OS 모두 bash를 사용하는 것은 수용한다. 설계의 목적은 명령 실패 전파이며
  PowerShell 사용 자체가 필수는 아니었다. Windows Python 실행과 PowerShell 셸 검증은 구분한다.
- JSON 비차단 알림 공통 helper와 기존 두 hint 호출부를 유지한 선택도 수용한다.
- R2-01의 배선 timeout 중복 수집과 최소값 선택, V2 합계 예산 검사,
  R2-02의 공통 알림 helper, Doctor의 자동 탐색·대상 대조, V1 테스트 보존을 확인했다.
- 설정과 CLI를 확인했고, GitHub 공식 릴리스에서 `checkout v7.0.1`과
  `setup-python v7.1.0`의 존재도 확인했다:
  [checkout 릴리스](https://github.com/actions/checkout/releases/tag/v7.0.1),
  [setup-python 릴리스](https://github.com/actions/setup-python/releases/tag/v7.1.0).
  이는 workflow 파일의 원격 실행 성공을 뜻하지 않는다.

### 직접 실행한 검증과 한계

| 검사 | Codex 직접 결과 |
|---|---|
| `.venv/Scripts/python.exe .claude/harness/scripts/run_quality.py --profile full` | lint PASS, format PASS(77 files), **718 passed · 1 skipped / 29.58초**, 전체 종료 0 |
| `.venv/Scripts/python.exe .claude/harness/scripts/doctor.py` | **PASS 26 · WARN 1 · FAIL 0**. WARN은 기존 D-EXEC 미검사 |
| 독립 임시 프로젝트 CLI probe | 버전 3 PASS, 변경 파일 전부 제외여도 실행, 유효·제외 혼합 인자 전달, 사유 빈 제외 SKIP을 재현 |
| 독립 임시 프로젝트 실제 PostToolUse probe | 사유 있는 제외 파일만 바꿨는데 `{changed_files}` stage가 실행됨을 재현 |
| `git diff --check` | 통과 |

추가 probe는 임시 디렉터리에 실제 CLI·훅 모듈을 복사하고 표준 라이브러리 stage의 실행 흔적과
수신 인자를 확인했다. 제품 코드·API·실문서·사용자 노트를 실행/사용하지 않았다.
기존 718개 테스트의 성공은 위 경계 결함이 없다는 근거가 아니며, 이 경우를 검사하는 회귀
테스트를 수정과 함께 추가해야 한다. Windows 로컬 Full을 이미 실행했으므로 같은 상태의
Fast 전체 테스트를 중복 실행하지 않았다. Linux·hosted CI·YAML parser 검증은 하지 않았다.

### 남은 일과 다음 인수인계

1. Claude가 HQCI-01~HQCI-03을 실제 코드에서 확인하고 최소 수정과 회귀 검증을 한다.
   잘못된 지적이면 반대 근거를 같은 리뷰 파일에 적는다. 이번은 첫 구현 결과 리뷰이며
   같은 결함 수정 실패 횟수는 아직 세지 않는다.
2. HQCI-N01 문서를 보완하고 같은 `.review.md`에 변경·실행 결과를 추가한다.
3. Codex가 다시 결과 리뷰해 막는 지적이 해소됐는지 확인한다.
4. 원격 실행은 아직 없다. 필요한 Git 작업이 승인·수행된 뒤 두 OS CI 결과를 확인한다.
   미검증 제약의 수용 없이 2번 구현으로 넘어가거나, 이 명세를 완료로 바꾸지 않는다.
5. 모든 변경은 아직 미커밋이고 두 인수인계 파일도 미추적이다. 구현 완료 판정 이후
   보존 여부를 확인한 뒤 정리하며, 현재는 파일을 삭제하지 않는다.

## Codex HQCI 수정 라운드 결과 리뷰 — 2026-11-22

이 절의 CI 미검증 상태는 당시 기록이다. 2026-11-23 최종 리뷰에서 보존된 hosted CI
보고를 확인해 완료 승인했다. 현재 판정은 아래 최종 리뷰와 머리글을 따른다.

- 체크아웃: `C:\my-harness`, `main / 675b461` + 미커밋 구현 변경.
- 대상: Claude의 `tasks/harness-quality-ci.review.md` 중
  「HQCI-01 … HQCI-03 — reproduced, fixed, re-verified」와 관련 코드·테스트·Knowledge.
  보고가 작성된 뒤 검토했으며, Claude 소유 리뷰 파일은 수정하지 않았다.
- 판정: **HQCI-01·HQCI-02·HQCI-03 해소. 검토한 수정 범위에 새로 막는 코드 지적 없음.**
  HQCI-N01의 문서 보완도 확인했다. **코드 리뷰 통과와 작업 전체 완료는 구분한다.**
  두 OS hosted CI가 아직 실행되지 않아 전체 완료 기준은 열린 채로 유지한다.

### 지적별 해소 근거

| ID | 실제 코드 근거 | 재검증 결과 |
|---|---|---|
| HQCI-01 | `auto_test_check.py`의 `RUNNABLE_CAUSES`를 훅과 CLI가 공유하고, 유효 행에서만 실행용 `changed_files`를 구성한다. CLI는 제외 전체일 때 엔진을 호출하지 않는다 | 제외·비추적·생성물·비Python 테스트 파일만인 CLI는 stage 미실행. 정상 파일은 실행되고, 정상+제외 혼합은 정상 파일만 전달. 실제 훅 제외 payload도 stage 미실행 |
| HQCI-02 | CLI가 설정의 raw 버전을 읽어 bool을 제외한 정수 2인지 검사한다. 공통 런타임의 `is_v2() >= 2` 의미는 보존 | 버전 3 probe는 ERROR / 2, stage 미실행. 정상 2는 실행. 추가 회귀 테스트가 다른 잘못된 버전들도 검사 |
| HQCI-03 | 사유를 `strip()`하고, 사용할 사유가 없는 일치는 `CAUSE_EXCLUDED_NO_REASON`으로 분류한다. CLI는 실행 전 ERROR, 훅은 비차단 알림. V1 목록형 호환 분기는 보존 | 빈 문자열·공백·null·목록형 제외의 CLI는 ERROR / 2, stage 미실행. Full에서 비문자열·훅 알림·V1 호환·유효 사유의 정상 제외 회귀도 통과 |

확인한 핵심 위치는 `.claude/harness/hooks/auto_test_check.py:250`·`:253`·`:273`·`:511`·`:520`,
`.claude/harness/scripts/run_quality.py:278`·`:313`·`:330`·`:342`다.
Doctor는 `.claude/harness/scripts/doctor.py:578`에서 빈 사유를 경고하고,
`:2013`·`:2096`에서 사유 있는 제외만 매핑 진단에 사용한다.

HQCI-01의 hook 혼합 입력은 테스트가 실제 변경 목록만 고정해
`_handle_v2_post_tool_use()` → 분류 → 공통 엔진 → probe 명령을 실행하는 방식으로 확인했다.
반면 제외 한 파일 사례는 실제 훅 스크립트 프로세스에 완전한 PostToolUse payload를 전달했다.
둘을 모두 실제 Claude/Codex 세션의 이벤트 전달 검증이라고 표현하지 않는다.

### 구현 선택과 문서 보완 판정

- **Doctor의 빈 사유 WARN은 수용한다.** 이번 요구는 이를 정상 제외로 조용히 인정하지
  않는 것이다. 경고를 내고 실제 CLI에서는 ERROR로 거부하므로 그 요구를 만족한다.
  비문자열·목록형에 대한 기존 스키마 오류는 유지하며, WARN만 있으면 Doctor 종료가 0일 수
  있다는 기존 계약도 바꾸지 않는다. Doctor 경고만으로 실제 검사 성공을 주장하지 않는다.
- 최장 접두사로 제외 사유를 선택한 변경은 설정 순서에 따른 표시 차이를 제거하는 범위로
  수용한다. 기존 V1 목록형 동작은 회귀 테스트로 확인했다.
- HQCI-N01: `quality-env.md`의 운영 비용·수동 실행·정확한 버전·제외/실행 입력 구분,
  Stop과 pre_commit의 조건 차이, `doctor.md`의 WARN 감소 원인 정정을 확인했다.
- 기존에 수용한 Doctor 루트 helper 재사용, 두 OS에서 bash 사용, JSON 비차단 알림 선택은
  그대로이며 이 라운드에서 새 외부 통합이나 자동 배포를 추가하지 않았다.

### Codex 직접 검증

| 검사 | 결과 |
|---|---|
| `.venv/Scripts/python.exe .claude/harness/scripts/run_quality.py --profile full` | lint PASS, format PASS(**77 files**), test **762 passed · 1 skipped / 38.15초**, 전체 종료 0 |
| `.venv/Scripts/python.exe .claude/harness/scripts/doctor.py` | **PASS 26 · WARN 1 · FAIL 0**. 남은 WARN은 D-EXEC 미검사 |
| 독립 임시 프로젝트 13개 probe | 모두 기대 결과. 제외/정상/혼합, 버전 3, 사유 없는 설정 네 형태, 실제 훅 제외 및 hook 혼합 실행 입력을 확인 |
| `git diff --check` | 통과 |

probe는 임시 디렉터리에 실제 모듈을 복사하고 표준 라이브러리 명령의 실행 흔적·수신 인자·
종료 코드를 확인했다. 제품 코드·유료 API·사용자 노트는 사용하지 않았다. 기존 테스트를
성공으로 고정한 모형 명령으로 바꿔 Full을 통과시킨 것이 아니라, probe 검증과 실제 전체
테스트 실행을 별도로 수행했다. 기존 skip 1건은 Windows에서 실행하지 않는 POSIX 검사다.

같은 상태의 Fast 전체 실행은 Full과 중복되므로 반복하지 않았다. **Linux·hosted CI·YAML
parser 검증은 이번에도 하지 않았다.** 원격 두 OS job의 성공을 추정하지 않는다.

### 현재 남은 일

1. 코드 결함 HQCI-01~HQCI-03의 추가 수정 요청은 없다. 이번 첫 수정으로 세 건 모두 해소됐다.
2. 아직 미커밋이므로 필요한 Git 작업이 승인·수행된 뒤 Windows/Linux hosted CI를 실행하고
   job 결과를 같은 리뷰에 보강한다. 코드를 검토했다는 이유만으로 원격 Git 작업을 수행하지 않는다.
3. CI 결과를 확인하거나, 기존 명세가 정한 미검증 제약 수용이 별도로 있어야 2번 구현에 착수한다.
   **현재 이 리뷰만으로 미검증 제약 수용이 있었다고 간주하지 않는다.**
4. 전체 완료 기준이 충족되기 전에는 상태를 완료로 바꾸거나 임시 명세·리뷰를 삭제하지 않는다.
   완료 뒤에도 커밋 또는 적절한 영구 문서로 보존됐는지 확인한 후 정리한다.

## Codex hosted CI 최종 리뷰 — 2026-11-23

- 체크아웃: `C:\my-harness`, `main / 5f58805`.
- 대상: `tasks/harness-quality-ci.review.md`의 「Hosted CI — run, failed once, green on both OSes」,
  구현 커밋 `63201d2`, CI 수정 `0e52390`, CI 보고 보존 커밋 `5f58805`.
- 판정: **구현 완료 승인. 기존 HQCI-01~HQCI-03은 해소 상태이고, 새로 막는 지적은 없다.**
  두 OS hosted CI 성공의 보존된 보고를 완료 근거로 수용한다. 최신 판정 보존과 임시 파일 정리는
  구현 완료와 별도로 남긴다. 2번 `template-core-packs`의 선행 작업 완료 조건도 충족한다.

### 확인한 결과와 근거 범위

성공 실행은 [run 45033823289](https://github.com/JungHwyKim/my-harness/actions/runs/45033823289),
실행 코드 `0e52390`이다. 아래 수치는 **Claude가 job 로그에서 확인해 `5f58805`에 보존한 보고**다.

| 항목 | Ubuntu | Windows |
|---|---|---|
| job | `quality (ubuntu-latest)` success / 16초 | `quality (windows-latest)` success / 44초 |
| job URL | [137243026598](https://github.com/JungHwyKim/my-harness/actions/runs/45033823289/job/137243026598) | [137243026924](https://github.com/JungHwyKim/my-harness/actions/runs/45033823289/job/137243026924) |
| 설치 일관성 | `No broken requirements found.` | 동일 |
| Doctor | PASS 26 · WARN 1 · FAIL 0 | 동일 |
| lint / format | PASS / 75 files already formatted | 동일 |
| pytest | **762 passed · 1 skipped / 7.93초** | **762 passed · 1 skipped / 23.37초** |
| 수동 CLI | PASS 3 · FAIL 0 · SKIP 0 · NOT RUN 0 | 동일 |

Codex가 직접 확인한 것은 다음과 같다.

- 로컬 Git 객체에서 구현 `63201d2`와 CI 수정 `0e52390`을 읽었다. 수정은 workflow의
  인터프리터 확인용 Python 코드에서 stdout UTF-8을 고정하는 내용이며, Profile·훅·제품 동작을
  추가로 바꾸지 않았다. Windows의 성공 메시지 출력 중 UnicodeEncodeError라는 보고와 부합한다.
- `0e52390`부터 현재 `5f58805`까지 diff는 **리뷰 파일의 보고 추가뿐**이다. 현재 런타임 코드가
  CI 성공 보고의 실행 코드와 달라졌다는 근거는 없다. 로컬 `origin/main`도 같은 리비전이다.
  이는 원격을 새로 fetch해 실시간 상태를 확인했다는 뜻은 아니다.
- 두 인수인계 파일이 `63201d2`에 들어 있고, 새 hosted 보고가 `5f58805`에 추가된 것을 확인했다.
  따라서 hosted 결과가 미추적 파일에만 있다는 이전 제약은 해소됐다.
- 이전 독립 로컬 검증은 Full **762 passed · 1 skipped**, 린트·포맷 PASS와 13개 probe다.
  새 원격 수치를 그때 직접 실행한 결과인 것처럼 바꾸지 않는다.

**원격 재조회 한계:** 이번 검토의 `gh run view`·`gh run list`는 `api.github.com` 연결 오류로
실패했다. 웹 조회도 실패했고 브라우저는 세션 연결 오류로 페이지를 열지 못했다. 따라서
Codex가 GitHub 화면·API·job 로그를 직접 다시 확인했다는 주장은 하지 않는다. 최종 판정은
보존된 실행 보고, 그 실행 코드 및 이후 diff, 앞선 독립 코드 검증을 대조한 결과다.

### Linux 인터프리터 확인 한계 — 비차단 후속 항목

보고서의 지적은 타당하다. 현재 workflow는 선택된 경로와 `sys.executable`을 각각
`realpath()`로 비교한다. Linux venv의 symlink가 기반 Python으로 풀리면 기반 Python을
잘못 선택해도 같은 경로로 보일 수 있다. 따라서 이 한 단계만으로 「준비한 그 venv를 선택함」을
엄밀히 증명했다고 표현하면 안 된다.

이번 완료를 막는 새 지적으로는 다루지 않는다. 현재 설정은 venv 자동 탐색이고, 이번 CI
실행에서 잘못된 환경 사용이나 검사 실패가 보고된 것은 아니다. 이미 수행한 코드 검토·
실행 보고의 명령·Full 결과를 함께 완료 근거로 삼으며, **guard의 위음성 가능성**은
`.claude/wiki/knowledge/quality-env.md`의 현재 한계로 보존했다. 「기반 Python에는 pytest·Ruff가
없어 반드시 다음 단계가 실패한다」는 설명에는 의존하지 않는다. 러너의 설치 상태는 별개다.

후속 보강 기준은 `.venv` 디렉터리와 `sys.prefix` 또는 symlink를 따라가지 않은 경로를
비교하고, 준비한 venv 대신 기반 Python을 선택하는 실패 주입이 검사에서 실제로 거부되는지
확인하는 것이다. 그 변경이 구현되면 두 OS CI를 다시 확인한다. 이번 최종 리뷰에서 workflow를
고치거나 새 원격 실행을 시작하지 않았다.

### 문서·검증·보존 판정

- 영구 Knowledge 두 곳의 「Linux·hosted CI 미검증」 설명을 이번 보고의 결과·출처·리비전과
  원격 재조회 한계로 갱신했다. `doctor.md`의 과거 WARN·skip 기록은 과거 시점으로 구분했다.
- Linux의 Windows 전용 skip과 Windows의 POSIX 전용 skip이 서로 교대한다는 보고는 수용한다.
  두 OS의 테스트 개수가 같다는 사실을 **숨은 플랫폼 결함이 전혀 없음**의 증명으로 쓰지는 않는다.
- workflow를 hosted 서비스가 실행한 근거가 보고돼 있으므로 별도 로컬 YAML parser 미설치는
  완료를 막지 않는다. 이를 위해 새 개발 의존성을 추가하지 않는다.
- 이번에는 명세·Knowledge 문서만 수정한다. 기존 코드 테스트는 해당 코드의 이전 독립
  Full과 hosted 실행 보고로 확인했고 같은 전체 테스트를 재실행하지 않았다. 문서 diff·공백·
  참조와 workflow Python 블록의 문법을 확인한다.
- **보존·정리 대기:** 이 최종 판정과 이번 Knowledge 갱신은 아직 커밋되지 않았다.
  Claude는 최신 내용이 확인된 커밋 또는 필요한 정보의 영구 문서 보존이라는 기존 조건을
  확인한 뒤 명세·리뷰를 정리한다. `63201d2` 하나에 최신 hosted 보고와 이번 최종 판정까지
  모두 들어 있다고 주장하지 않는다. 작업 2·3의 명세는 정리 대상이 아니다.

현재 남은 일은 최신 판정의 보존·임시 파일 정리와 위 비차단 후속 보강이다. 이 작업의
구현 완료를 위해 다시 고쳐야 할 blocking finding은 없다. 인수인계 파일을 삭제하거나
커밋·푸시하는 동작은 이번 최종 리뷰에서 수행하지 않는다.
