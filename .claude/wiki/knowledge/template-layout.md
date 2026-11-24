# 내보내기 계약 — packs · templates · manifest · exporter

**이 문서는 소스 전용이다.** 설치물에는 `packs/`·`templates/`·exporter가 없으므로 이 문서도
내보내지 않는다. 설치물에서 무엇이 어디 있는지는 출력의 `HARNESS-INSTALL.md`와
`.claude/wiki/overview/README.md`가 소유한다.

## 왜 나눴는가

이 저장소는 하네스를 **개발하는 자리**이면서 동시에 **다른 프로젝트로 가져갈 원본**이었다.
그래서 `.claude/` 전체를 복사하는 방식에서는 두 가지가 같이 따라왔다.

- RAG 프로젝트 전용 에이전트·스킬과 개인 면접 도구가 **일반 프로젝트에서 자동으로 로드**됐다.
- 하네스 자신을 개발하는 Quality 설정(`.claude/harness/` → `tests/` 매핑)이 **대상
  프로젝트의 필수 도구**처럼 보였다.

이제 기본 설치물은 공통 기능만 담고, 선택 구성은 고를 때만 들어가며, 배포 설정은 개발 설정과
다른 파일에서 생성된다.

## 세 자리

| 자리 | 무엇인가 | 로드되는가 |
|---|---|---|
| `packs/<이름>/.claude/...` | 선택 구성의 **원본** | 저장소 전체 범위에서는 아니다. 아래 주의 참고 |
| `templates/core/` | 설치물의 진입점·설정·설치 안내·배포 Knowledge | 아니다. 생성용 템플릿이다 |
| `templates/manifest.json` | `source` → `destination` 목록 | 아니다. exporter가 읽는다 |

`packs/` 아래 경로는 **저장 위치**이고 설치될 최종 경로와 다르다. 예를 들어
`packs/rag/.claude/agents/code-reviewer.md`는 출력에서 `.claude/agents/code-reviewer.md`가
된다. 그 대응은 manifest가 정한다.

**주의 — `packs/`는 완전히 「로드되지 않는 자리」가 아니다.** Claude Code는 중첩된
`.claude/skills/`를 **디렉터리 범위 스킬**로 읽는다. 실측으로 `packs/interview/` 아래의 파일을
작업하는 동안 `quiz`가 그 범위 스킬로 올라왔다. 저장소 전역에서 `/quiz`가 동작하지는 않지만,
「pack에 두면 아무 데서도 안 보인다」는 설명은 정확하지 않다. 활성 폴더와 pack에 **같은 파일의
사본을 두지 않는다**는 규칙은 그대로 유효하다 — 사본을 두면 둘이 갈라진다.

## exporter 계약

```text
python .claude/harness/scripts/export_template.py --dest <새 경로> [--pack rag] [--pack interview]
```

- 복사 목록은 **manifest 하나가** 소유한다. CLI 안에 같은 목록을 다시 적지 않는다.
- 소스 루트는 **스크립트 자신의 경로**에서 정한다(`doctor.py`와 같은 전제). cwd나 환경변수로
  바꾸지 않는다.
- `--dest`는 **없는 경로**여야 하고 부모는 있어야 한다. 기존 빈 디렉터리도 거부한다.
  `--force`·덮어쓰기·자동 삭제는 제공하지 않는다.
- 쓰기 전에 검사한다: 절대 경로·드라이브 경로·`..` 항목, 누락된 소스, 루트 밖으로 벗어나는
  소스, 출력이 소스 루트와 겹치는 것, 그리고 아래 둘.
  - **소스 경로의 링크** — 마지막 파일만이 아니라 루트 아래 **각 구성 요소**를 본다.
    symlink과 junction 둘 다다. 링크가 루트 안을 가리켜도 거부한다. 「루트 밖으로
    resolve되는 것을 막는다」와 「링크 자체를 거부한다」는 다른 조건이다.
  - **같은 자리를 차지하는 두 destination** — 완전히 같은 것, 대소문자만 다른 것,
    한쪽이 다른 쪽의 부모인 것(`docs`와 `docs/guide.md`) 셋 다 거부한다. 같은 폴더 아래
    형제 파일은 정상이다.
- 대소문자 별칭은 **두 OS에서 똑같이** 거부한다. Linux에서는 둘이 다른 파일이지만, 거부
  계약이 OS마다 갈리면 한쪽에서 통과한 manifest가 다른 쪽에서 깨진다.
- **symlink과 junction의 생성 조건은 서로 다르고, 둘 다 실행 환경에 달렸다.** 그래서 두
  capability를 **따로** 검사한다 — 한쪽을 만들 수 없는 것이 다른 쪽 검사를 건너뛸 이유가
  되지 않는다. 만들 수 없는 종류만 이유를 밝히고 skip하며, 조용히 통과시키지 않는다.
  **어느 종류가 어디서 되는지를 이 문서가 보장하지 않는다** — 같은 머신에서도 세션에 따라
  갈린 실측이 있다(`history/task/2026-11-25-link-capability-varies-by-session.md`). 그래서
  CI 로그는 건수가 아니라 **테스트별 skip 사유**로 읽는다.
- junction은 `is_symlink()`에 False를 내므로 `os.path.isjunction` 분기가 반드시 필요하고,
  그 분기는 만들 수 있는 환경에서 실제 reparse point로 검증한다.
- 명령을 실행하지 않는다 — 네트워크·Git·pip·Doctor·Profile을 돌리지 않는다.

| 종료 코드 | 조건 |
|---|---|
| 0 | 선택한 파일을 새 경로에 모두 생성했다 |
| 1 | 읽기·쓰기 실패. **부분 출력 경로를 알리고 자동으로 지우지 않는다** |
| 2 | 인자·manifest 오류, 알 수 없는 pack, 누락 소스, 기존 대상, 경로 탈출·충돌 |

2는 **쓰기를 시작하기 전에만** 난다.

## 분류 규칙

- **공통**: 진입점 두 파일, 공용 `settings.json`과 훅 전체, 스키마, Doctor, 수동 Quality CLI,
  공통 스킬 7개, openwork 수집기, Knowledge 3문서와 배포 README, 비어 있는 History 세 폴더,
  `tasks/_template.md`.
- **선택**: `rag`(에이전트 4개·스킬 4개), `interview`(quiz 스킬과 Python 패키지).
- **소스 전용**: 이 `README.md`, `.gitattributes`, 개발용 `CLAUDE.md`·`AGENTS.md`·
  `.gitignore`·`.claude/harness.json`, Knowledge의 `doctor.md`·`quality-env.md` **원본**,
  Wiki 세 폴더의 **소스 README**, `template-deploy.md`와 이 문서, `tests/`, CI, 루트
  `requirements.txt`·`ruff.toml`, 개발 History, `packs/`·`templates/` 자체, exporter.

**두 소스가 같은 destination을 차지하지 않는다.** 설치물의 `CLAUDE.md`·`AGENTS.md`·
`.gitignore`·`.claude/harness.json`과 Knowledge 두 문서, Wiki 세 README는 모두
`templates/core/`에서 생성한다. 개발용 원본은 같은 이름이지만 출력에 가지 않는다.
exporter가 문자열을 치환해 두 용도를 겸하게 만들지 않는다 — 파일을 가른다.

## 추적 정책

`packs/`와 `templates/`는 **전체가** Quality 추적 대상이고 `tests/`로 매핑된다. 그쪽 문서의
실행 경로와 외부 전제가 설치 계약의 입력이어서, Python 파일과 manifest만으로 좁히지 않았다.
pack 문서 한 줄을 고쳐도 Fast가 전체 테스트를 돌리는 비용은 의도한 것이다.

같은 종류의 문서라도 **활성 `.claude/skills/`와 Wiki는 추적 밖**이다. 기준은 「문서인가」가
아니라 「내보내기 계약에 들어가는가」다. 자세한 것은
[quality-env.md](quality-env.md)의 「추적 경로와 Fast 대상」에 있다.

`history.tracked_paths`는 확대하지 않았다. pack·배포 문서 수정만으로 History 판단 의무를
새로 부과하지 않는다.

## 이 저장소에서 `/quiz`는 비활성이다

quiz는 **프로젝트에 설치하는 선택 구성**이다. 연습은 `--pack interview` 출력 디렉터리에서
하고, 고칠 일이 있으면 이 저장소의 `packs/interview/`에서 고친 뒤 새 경로로 다시 내보낸다.
출력 사본을 고쳐 별도 원본으로 관리하지 않는다. 스킬이 `${CLAUDE_PROJECT_DIR}` 기준으로
수집기를 부르므로 전역 설치로는 동작하지 않으며, 그 재설계는 이 작업의 범위가 아니다.

## 보장하지 않는 것

- exporter는 **파일 복사**까지다. 출력물이 실제로 동작하는지는 설치 검증이 따로 본다.
  구체적으로 **설치된 프로젝트 자신의 인터프리터 선택과 세션 훅의 실제 실행은 미검증**이고,
  그 통합 검증은 별도의 설치 smoke 작업이 소유한다.
- 이 계약은 **`9632b25`에 구현돼 있고 두 OS hosted CI로 검증됐다**(run 45426067451 — Ubuntu
  852 passed · 4 skipped, Windows 854 passed · 2 skipped). 거부 계약이 양쪽에서 실제로
  실행됐고 Windows에서는 symlink·junction 두 종류가 모두 돌았다. 그 수치의 근거와
  **독립 재조회가 없다는 한계**는 [quality-env.md](quality-env.md)의 CI 행에 있다.
- 대상 프로젝트와의 병합은 문서로만 안내한다. 자동 병합·덮어쓰기·배포 ref 발행은 없다.
- 배포 ref(`template/*`)와 이 내보내기 절차는 **다른 것**이다.
  [template-deploy.md](template-deploy.md)가 그 구분을 소유한다.
