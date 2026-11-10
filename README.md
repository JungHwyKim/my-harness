# my-harness V1

Claude Code 프로젝트에 그대로 복사해 쓰는 V1 개발 하네스다. 플러그인 마켓플레이스와
별도 설치는 사용하지 않는다.

```text
CLAUDE.md             최소 공통 규칙과 문서 탐색 경로
.claude/settings.json 프로젝트 공용 훅 설정
.claude/harness.json  프로젝트별 검사·경로 설정
.claude/hooks/        Hook 구현
.claude/scripts/      openwork·quiz 보조 스크립트
.claude/skills/       필요할 때 로드되는 작업 절차
.claude/agents/       RAG 프로젝트용 담당 에이전트
.claude/wiki/         Overview · Knowledge · V1 기록 로그
```

## 적용

새 프로젝트는 GitHub의 **Use this template**으로 시작한다.

기존 프로젝트에 적용할 때는 이 저장소의 `CLAUDE.md`와 `.claude/`를 가져온다. 기존
`CLAUDE.md`나 `.claude/settings.json`이 있으면 덮어쓰지 말고 규칙과 `hooks` 항목을
병합한다.

적용한 뒤에는 아래 내용을 프로젝트에 맞게 수정한다.

1. `CLAUDE.md`의 프로젝트 목적과 공통 규칙
2. `.claude/harness.json`의 Python 경로, 소스 경로, 테스트 매핑, 커밋 전 검사 명령
3. `.claude/wiki/overview/`, `knowledge/`의 프로젝트 문서

Claude Code는 프로젝트의 `.claude/settings.json`과 `.claude/skills/`를 바로 읽으므로,
별도의 플러그인 설치 없이 훅과 스킬이 동작한다.

## V1 기록 흐름

```text
설계 논의          → wiki/plan_log/
구현 중 결정·실패  → wiki/task_log/
검증 수치          → wiki/verify_log/
```

V1은 설계·작업 기록 게이트를 통해 기록 누락을 막는다. Git은 변경 사실을, 테스트는 현재
동작을, Wiki는 설계·구현 과정의 맥락을 보존한다.

## 검증

```powershell
python -m pytest tests -q
```

훅은 표준 라이브러리만 사용한다. 실제 프로젝트의 pytest·ruff·빌드 명령은
`.claude/harness.json`에 정의한다.
