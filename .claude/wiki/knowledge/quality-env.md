# 검증 환경과 Quality Profile 계약

개발 의존성은 저장소 전용 가상환경에 두고, 품질 검사는 `.claude/harness.json`의 Quality
Profile이 돌린다. 설치 절차 자체는 `README.md`의 「검증과 주의 사항」이 안내한다. 이
문서는 그 설정이 무엇을 보장하고 무엇을 보장하지 않는지를 둔다.

## 인터프리터

`.claude/harness.json`의 `python`이 `.venv/Scripts/python.exe`를 가리킨다.

**그 자리에 환경이 없으면 검사가 실패하지 않고 다른 인터프리터로 조용히 대체된다.** 검사가
통과했다는 보고만으로 지정된 환경에서 돌았다고 볼 수 없다. 버전이 의심되면 실행에 쓴
인터프리터를 함께 확인한다.

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
| `fast` | `post_change` | 매핑된 대상의 `pytest -q` | timeout 90. `success_codes`가 `[0, 5]`라 **수집 0건도 성공**이다 |
| `full` | `stop`, `pre_commit` | `ruff check .` → `ruff format --check .` → `pytest -q` | timeout 120·120·600 |

추적 경로는 `src/`, `tests/`, `pyproject.toml`, `.claude/harness.json`이고 매핑은
`src/` → `tests/` 하나다.

**문서·스킬 파일 변경에는 매핑된 검사가 없다.** `.claude/skills/`나 Wiki만 고친 변경에
`fast`가 돌릴 대상은 없다. 그때는 돌리지 않은 이유를 보고하고, 검사가 통과했다고 적지
않는다. `full`은 경로와 무관하게 `stop`·`pre_commit`에서 돌아간다.

## Ruff 설정

`ruff.toml`이 선택 규칙을 명시한다. **설정을 비우면 Ruff가 버전마다 다른 자기 기본값을
쓰므로**, 저장소가 고른 적 없는 규칙이 업그레이드와 함께 기준이 되어 버린다.

- `select = ["E4", "E7", "E9", "F"]` — Ruff 문서가 기본으로 적는 선택이고 현재 통과 범위다.
- `line-length = 100` — 포매터가 줄 너비를 **표시 폭**으로 세고 한글은 한 글자가 두 칸이다.
  88은 한국어 한 줄을 쪼개고, 100보다 넓히면 지은이가 일부러 쪼갠 줄을 거꾸로 합친다.
- `I`(import 정렬)·`RUF100`(죽은 noqa) 추가는 아직 정하지 않은 별도 결정이다.

## 현재 확인된 상태

| 확인 | 결과 | 시점 |
|---|---|---|
| 설치 버전과 고정 버전 일치 | `pytest 9.2.0`, `ruff 0.17.5`, Python 3.12.5 | 2026-11-20 직접 확인 |
| Full 세 단계 | 린트·포맷 검사 통과, **405 passed** | `tasks/handoff.review.md`의 마지막 보고. 그 뒤로 재실행하지 않았다 |

## 보장하지 않는 것

- **Linux와 CI는 검증하지 않았다.** 위 결과는 Windows 로컬 보고다.
- `pip check` 성공은 설치 일관성만 말한다. Full 통과와 구분한다.
- 유료 테스트 보호는 이 문서가 아니라 `paid-test-approval.md`가 소유한다. Quality Profile의
  pytest는 하위 프로세스라 `PreToolUse` 훅을 거치지 않고, 그 경로의 보호는 설정의 기본
  제외다.
