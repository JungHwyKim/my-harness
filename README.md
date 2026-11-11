# my-harness

Claude Code 프로젝트에 그대로 복사해 쓰는 개인용 개발 하네스다. 반복해서 커지는
`CLAUDE.md`, 누락되기 쉬운 품질 검사, 현재 규칙과 과거 결정이 섞이는 문제를 분리된
프로젝트 문서와 훅으로 다룬다. 플러그인 마켓플레이스나 별도 설치는 필요 없다.

## 빠른 시작

```powershell
git clone https://github.com/JungHwyKim/my-harness <your_dir>
```

기존 프로젝트에 적용할 때는 이 저장소의 `CLAUDE.md`와 `.claude/`를 가져온다. Codex도
함께 쓴다면 `AGENTS.md`도 가져온다. 기존 `CLAUDE.md`, `AGENTS.md`,
`.claude/settings.json`이 있다면 덮어쓰지 말고, 프로젝트의 규칙과 `hooks` 항목을
병합한다.

적용 직후에는 아래 네 곳을 프로젝트에 맞게 수정한다.

1. `CLAUDE.md` — 프로젝트 목적과 항상 지켜야 할 공통 규칙
2. `.claude/harness.json` — Python 경로, 소스·테스트 경로, Quality Profile
3. `.claude/wiki/overview/` — 디렉터리, 진입점, 관련 문서 링크
4. `.claude/wiki/knowledge/` — 현재 유효한 계약과 정책

Claude Code는 프로젝트의 `.claude/settings.json`에서 훅을,
`.claude/skills/<이름>/SKILL.md`에서 프로젝트 스킬을 읽는다.

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

```powershell
python -m pytest tests -q
```

- `.claude/settings.local.json`은 개인 설정이므로 커밋하지 않는다.
- `.claude/harness.json`의 예시는 Python 프로젝트 기준이다. 다른 언어에서는 Quality
  Profile의 명령을 사용하는 도구에 맞게 바꾼다.
- `history/`는 이슈 트래커나 전체 백로그가 아니다. 열린 작업은
  `checks.openwork.sources`에 별도 정보원을 지정해 관리한다.
- 유료·외부·장시간 테스트는 `checks.expensive_tests`에 명시하고, 실행 전 사용자 승인을
  받는다.
