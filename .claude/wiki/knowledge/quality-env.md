# 검증 환경과 Quality Profile 계약

개발 의존성은 저장소 전용 가상환경에 두고, 품질 검사는 `.claude/harness.json`의 Quality
Profile이 돌린다. 설치 절차 자체는 `README.md`의 「검증과 주의 사항」이 안내한다. 이
문서는 그 설정이 무엇을 보장하고 무엇을 보장하지 않는지를 둔다.

## 인터프리터

`.claude/harness.json`에 `python` 키가 **없다.** 그래서 `_hookutil.venv_python()`이
`.venv/Scripts/python.exe` → `.venv/bin/python` 순으로 찾고, Windows와 Linux가 각자의
환경을 쓴다. 한 저장소를 두 OS에서 검증하려면 이쪽이어야 한다 — 한 OS의 경로를 적어 두면
다른 OS에서는 그 경로가 없어 매번 대체된다.

**두 자리 모두 없으면 검사가 실패하지 않고 현재 프로세스로 조용히 대체된다.** 검사가
통과했다는 보고만으로 의도한 환경에서 돌았다고 볼 수 없다. `run_quality.py`가 실제로 고른
경로를 출력하고, CI는 준비한 venv와 같은지 따로 확인한다.

Doctor는 이 상태를 D-PYTHON PASS로 본다. 키가 없는 것은 결함이 아니다. 반대로 **적어 둔
경로가 없을 때는 WARN**이다 — 사람이 의도한 환경이 거기 없다는 뜻이기 때문이다.

`.venv/`는 `.gitignore`가 제외한다. 환경은 배포하지 않고 프로젝트마다 다시 만든다.

## 고정 의존성

`requirements.txt`에는 **Full이 실제로 돌리는 두 도구만** 둔다. 전역 `pip freeze`를 복사
하지 않고 간접 의존성은 pip가 해석한다.

| 항목 | 계약 |
|---|---|
| 내용 | `pytest`·`ruff`의 고정 버전 두 줄 |
| 인코딩 | **ASCII만.** pip가 이 파일을 로케일 인코딩으로 읽어서, 한국어 주석을 넣으면 cp949 환경의 `pip install -r`가 깨진다. 한국어 설명은 `README.md`에 둔다 |
| 성격 | 이 저장소를 검증하는 도구다. 대상 프로젝트의 제품 의존성이 아니고 모든 프로젝트의 필수 품질 도구도 아니다 |

## Profile 두 개

| Profile | 트리거 | 단계 | 비고 |
|---|---|---|---|
| `fast` | `post_change` | 매핑된 대상의 `pytest -q` | timeout 90. `success_codes`가 `[0]`이라 **수집 0건은 실패**다 |
| `full` | `stop`, `pre_commit` | `ruff check .` → `ruff format --check .` → `pytest -q` | timeout 120·120·540 |

`success_codes`를 `[0]`으로 둔 것은 **실제로 돌렸는데 수집이 0건인 상태**를 통과와 가르기
위해서다. 작성 중인 빈 `test_*.py`가 흔한 원인이고, 그때는 실패 메시지에 「수집된 테스트
없음」이 적힌다. V1의 `[0, 5]` 호환 동작과 공통 엔진은 바꾸지 않았다.

**매핑 누락은 `success_codes`가 잡는 것이 아니다.** 대상이 비면 stage 자체가 실행되지 않아
pytest의 종료 코드가 나오지 않는다. 그 자리는 아래 분류가 따로 본다.

### 추적 경로와 Fast 대상

| 추적 경로 | Fast 대상 | 이유 |
|---|---|---|
| `.claude/harness/` | `tests/` | 훅·공유 모듈·스크립트·스키마가 서로 영향을 준다 |
| `.claude/settings.json` | `tests/` | 배선과 timeout 계약을 검증한다 |
| `.claude/harness.json` | `tests/` | 매핑·Profile·Doctor 계약에 영향을 준다 |
| `tests/` | 직접 테스트는 그 파일, 보조 Python은 `tests/` | `test_target_for()`의 V2 특례다 |
| `requirements.txt`, `ruff.toml` | `tests/` | 도구·설정 변경 뒤 회귀를 확인한다 |
| `.github/workflows/` | 없음. `unmapped_by_design`에 사유를 적었다 | Python 테스트로 hosted CI 실행을 증명할 수 없다 |

하네스 코드 한 파일만 고쳐도 Fast가 전체 테스트를 돌린다. 정밀 매핑은 하지 않았다 — 훅·공유
모듈·스키마가 서로 영향을 주어 부분 실행의 근거가 약하다. 그 비용은 아래 실측에 있다.

**추적 경로를 추가하면 매핑 또는 사유 있는 제외가 함께 필요하다.** 둘 다 없으면 Fast 훅이
세션당 한 번 비차단 알림을 내고 `run_quality.py`는 ERROR로 끝난다. 막지 않는 쪽을 고른 이유는
설정이 고쳐지기 전까지 조건이 그대로라서다 — 차단으로 두면 모든 도구 호출이 빨개지고,
그러면 `SKIP_AUTOTEST=1`이 습관이 된다.

**사유 없는 제외는 제외가 아니다.** `unmapped_by_design`의 값이 비어 있거나 공백뿐이거나
문자열이 아니면 유효한 제외로 보지 않는다 — 이 집합이 있는 이유가 「왜 뺐는지 적어 두는
것」이라, 사유가 없으면 그 목적을 채우지 못한다. 그 상태는 매핑 누락과 같게 다룬다(CLI는
ERROR, 훅은 알림, Doctor는 WARN). V1의 목록형 제외는 사유 자리가 없었으므로 그대로 받는다.

**문서·스킬 파일 변경에는 매핑된 검사가 없다.** `.claude/skills/`나 Wiki는 추적 경로 밖이라
`fast`가 돌릴 대상이 없다. 그때는 돌리지 않은 이유를 보고하고, 검사가 통과했다고 적지
않는다.

**`full`의 두 트리거는 조건이 다르다.** `pre_commit`은 `git commit`을 보면 경로와 무관하게
돌린다. `stop`은 그렇지 않다 — `_v2_session_changes()`가 추적 경로의 변경을 찾지 못하면
세션이 그냥 끝난다. 추적 밖만 고친 세션에는 Stop 게이트가 돌지 않는다.

### 시간 예산

stage의 timeout은 그 훅의 `settings.json` timeout보다 **합계로도** 짧아야 한다. 한 훅 호출이
Profile의 stage를 순서대로 돌리므로, 앞 단계가 쓴 시간이 뒤 단계의 몫을 깎는다.

| V2 실행 경로 | stage 합계 | 바깥 예산 |
|---|---|---|
| Fast / PostToolUse | 90 | 120 |
| Full / Stop | 780 | 900 |
| Full / pre_commit | 780 | 900 |

여유 30초는 훅이 설정·git·마커를 보는 시간이다. `tests/test_hook_wiring.py`가 이 표를
설정에서 직접 읽어 검사한다. 개별 상한만 비교하던 V1 규칙은 V1 상수에만 적용된다.

## 수동 실행

`python .claude/harness/scripts/run_quality.py --profile full`이 훅과 **같은 설정**을 읽어
돌린다. `--profile fast`는 `--changed <프로젝트 상대 경로>`를 반복 지정해야 한다.

종료 코드는 `0`(PASS 또는 SKIP), `1`(stage 실패), `2`(사용 오류·설정 결함)다. SKIP은 0이지만
**검사 통과가 아니다.** 앞 단계 실패로 도달하지 못한 단계는 `NOT RUN`으로 따로 적는다.

`--require-venv`를 주면 **하네스가 고른 인터프리터가 이 프로젝트의 `.venv` 안인지**를 실행
전에 확인하고, 아니면 ERROR로 끝낸다. CI가 그 플래그를 쓴다. 설정 경로와 두 venv 자리를 모두
찾지 못해 현재 프로세스로 조용히 대체된 상태가 이 검사에 걸린다.

**판정은 경로 문자열로 하고 symlink를 따라가지 않는다.** POSIX의 `.venv/bin/python`은 기반
Python의 symlink라, `realpath()`로 풀어 비교하면 venv를 고른 것과 기반 Python을 고른 것이
같은 경로로 모인다. Windows는 실행 파일을 복사해서 그 함정이 없다 — 즉 풀어서 비교하면 같은
검사가 OS마다 다른 것을 잰다. 실제로 CI의 Linux job이 그 상태로 통과한 적이 있다
(`git log --all -- .github/workflows/harness-quality.yml`).

**훅의 `SKIP_*` 우회 변수가 이 명령에는 적용되지 않는다.** 저 변수는 「모델이 돌리는 자동
검사를 잠시 끈다」는 뜻이고, 이 명령은 사람이나 CI가 일부러 돌리는 것이다. 환경변수 하나로
CI 게이트가 꺼지면 그건 검사가 아니다. 출력 머리에도 같은 말이 적힌다. 반대로 자식 환경에서
그 변수들을 지우지는 않는다 — stage 명령이 무엇을 읽는지는 그 설정의 몫이다.

이 CLI는 `schema_version`이 **정확히 정수 2**인 설정만 실행한다. 1·부재는 V1이고, 3 이상과
정수가 아닌 값은 실행 전에 ERROR다. 훅의 `is_v2()`는 `>= 2`라 뜻이 다르다 — 그쪽은 기능
분기이고 이쪽은 지원 범위다. Doctor도 3 이상을 FAIL로 본다.

**분류 결과가 실행 입력을 정한다.** 정책상 제외한 파일은 stage 인자에 넣지 않는다. 변경
파일이 전부 제외면 아무 명령도 돌지 않고 SKIP이다. 유효한 파일이 섞여 있으면 그 파일만
인자로 간다.

## 운영 비용

하네스 코드(`.claude/harness/`)나 `tests/`를 고친 세션은 **Stop에서 한 번 막힌다.**
`history.tracked_paths`가 그 경로를 포함하므로 History 중요도 판단이 필요하고, 그 판단은
`history-significance` Skill을 호출해야 표시된다. 판단한 뒤 「중요하지 않다」면 기록 없이
마칠 수 있다 — 그러나 **판단 호출 자체는 건너뛸 수 없다.** 이 저장소에서는 거의 모든 세션이
해당한다. 끄려면 `SKIP_HISTORY=1`이다.

## Ruff 설정

`ruff.toml`이 선택 규칙을 명시한다. **설정을 비우면 Ruff가 버전마다 다른 자기 기본값을
쓰므로**, 저장소가 고른 적 없는 규칙이 업그레이드와 함께 기준이 되어 버린다.

- `select = ["E4", "E7", "E9", "F"]` — Ruff 문서가 기본으로 적는 선택이고 현재 통과 범위다.
- `line-length = 100` — 포매터가 줄 너비를 **표시 폭**으로 세고 한글은 한 글자가 두 칸이다.
  88은 한국어 한 줄을 쪼개고, 100보다 넓히면 지은이가 일부러 쪼갠 줄을 거꾸로 합친다.
- `I`(import 정렬)·`RUF100`(죽은 noqa) 추가는 아직 정하지 않은 별도 결정이다.

## 현재 확인된 상태

| 확인 | 결과 | 시점과 주체 |
|---|---|---|
| 설치 버전과 고정 버전 일치 | `pytest 9.2.0`, `ruff 0.17.5`, Python 3.12.5 | 2026-11-20, Codex가 지정 인터프리터로 직접 확인 |
| 설치 일관성 | `pip check` 종료 코드 0, `No broken requirements found.` | 2026-11-20, Codex 직접 확인 |
| Full 세 단계 | `ruff check` 통과, `ruff format --check`는 70 files already formatted, **405 passed**(8.32초) | 2026-11-20, Claude가 세 단계를 재실행해 보고. Codex는 그 검토에서 재실행하지 않았다 |
| 전체 테스트 | **651 passed · 1 skipped**, 15.80~20.97초(세 번) | 2026-11-22, Claude가 지정 인터프리터로 실행. Fast가 하네스 한 파일 수정마다 치르는 비용이 이 값이다 |
| `run_quality.py --profile full` | lint·format·test 세 단계 PASS, 종료 코드 0 | 2026-11-22, Claude가 새 CLI로 실행 |
| Doctor | PASS 26 · WARN 1 · FAIL 0, 종료 0. 남은 WARN은 D-EXEC 「미검사」 | 2026-11-22, Claude 실행 |
| Hosted CI / Ubuntu | `pip check`·Doctor·lint·format·Full 성공. **762 passed · 1 skipped / 7.93초**, format 75 files | 2026-11-22, Claude가 [run 45033823289](https://github.com/JungHwyKim/my-harness/actions/runs/45033823289)의 job 로그에서 확인해 `5f58805`에 보고. 실행 코드 `0e52390` |
| Hosted CI / Windows | 같은 단계 성공. **762 passed · 1 skipped / 23.37초**, format 75 files | 같은 실행과 보고 커밋. Windows 최초 실패의 출력 인코딩 수정은 `0e52390` |
| Hosted CI / Ubuntu (venv guard 적용 후) | 성공. **768 passed · 1 skipped / 10.41초**. 고른 인터프리터가 `/home/runner/work/my-harness/my-harness/.venv/bin/python`으로 보고됐다 | 2026-11-22, Claude가 [run 45043697211](https://github.com/JungHwyKim/my-harness/actions/runs/45043697211)의 job 로그에서 확인. 실행 코드 `7c540cb` |
| Hosted CI / Windows (venv guard 적용 후) | 성공. **767 passed · 2 skipped / 26.76초**. `D:\a\my-harness\my-harness\.venv\Scripts\python.exe` | 같은 실행. skip 수가 OS마다 다른 것은 아래 설명대로다 |

**`--require-venv` 도입 전 Linux job은 고른 경로를 기반 Python으로 보고했다** —
`/opt/hostedtoolcache/Python/3.12.16/x64/bin/python3.12`. 같은 실행의 Windows는 `.venv`
경로였다. 그 차이가 「풀어서 비교하면 OS마다 다른 것을 잰다」의 실측이고, 위 두 행에서 양쪽이
모두 `.venv` 경로를 보고하는 것이 보강의 근거다.

skip 수는 OS마다 다르다 — Windows는 POSIX 전용 둘(실행 권한 비트, venv symlink 판정)을,
Linux는 Windows 전용 하나를 건너뛴다. 합계 769개는 같다. 두 OS의 수가 **같아야** 한다는
규칙은 없으며, 같다는 사실을 플랫폼 결함이 없다는 증명으로 쓰지도 않는다.

2026-11-23 Codex는 위 보고와 커밋을 대조해 최종 리뷰했다. GitHub API·페이지 재조회는 이
검토 환경의 연결 오류로 하지 못했으므로, 위 hosted 수치는 **Claude가 보존한 실행 보고**에
근거한다. 실행 코드 뒤 `5f58805`는 리뷰 문서만 변경했다. 관련 코드와 로컬 Full의 이전
독립 검증 근거는 작업 명세의 최종 리뷰에 있고, **그 임시 파일은 정리되어 사라졌으므로 보존
커밋에서 읽는다** — `git show a91ad2e:tasks/harness-quality-ci.md`의 「Codex hosted CI 최종
리뷰 — 2026-11-23」절과 `git show a91ad2e:tasks/harness-quality-ci.review.md`다. 경로로 다시
찾을 때는 `git log --all -- tasks/harness-quality-ci.md`를 쓴다.

Windows의 skip은 POSIX 권한 검사, Linux의 skip은 Windows 전용 경로 검사다. 이는 현재
테스트가 의도한 OS별 제외를 설명하며 모든 플랫폼 문제가 없음을 보장하지 않는다.

**환경 구축 성공과 Full 통과는 따로 판정한다.** 위 수치를 이 문서에 적은 것은 실행 증거가
임시 파일에만 남지 않게 하기 위해서다. 설치 자체의 실행 기록은 인수인계 절차의 임시 리뷰에
있고, 그 파일은 정리되면 사라지므로 보존 커밋에서 읽는다 —
`git show 07bd76e:tasks/handoff.review.md`의 Round 2와 마지막 `F6 closed` 절이다. 경로로
다시 찾을 때는 `git log --all -- tasks/handoff.review.md`를 쓴다.

## 보장하지 않는 것

- Windows/Linux hosted CI는 위 실행에서 성공한 것으로 보고됐다. 다른 Python 버전·러너,
  이후 변경까지 검증됐다는 뜻은 아니다. Codex의 이번 원격 재조회 한계도 위에 명시했다.
- `--require-venv`는 **고른 경로가 `.venv` 안인지**만 본다. 그 venv에 pytest·Ruff가 깔려
  있는지, 버전이 맞는지는 보지 않는다 — 그쪽은 `pip check`와 Full의 몫이다.
- 테스트 fixture 같은 **`tests/` 아래 비Python 파일은 자동 검사 대상이 아니다.** 분류에서
  SKIP으로 사유를 적을 뿐이고, 그 파일의 내용이 맞는지는 아무 검사도 보지 않는다.
- `pip check` 성공은 설치 일관성만 말한다. Full 통과와 구분한다.
- 유료 테스트 보호는 이 문서가 아니라 `paid-test-approval.md`가 소유한다. Quality Profile의
  pytest는 하위 프로세스라 `PreToolUse` 훅을 거치지 않고, 그 경로의 보호는 설정의 기본
  제외다.
