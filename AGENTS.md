# Codex 작업 지침

## 시작하기

- 작업을 시작하기 전에 `CLAUDE.md`를 읽고 **Global Rules**, **Context Router**,
  **Information Ownership** 항목을 따른다.
- 이 파일은 Codex의 진입점이다. 프로젝트 공통 맥락의 기준은 `CLAUDE.md`이며,
  그 내용을 이 파일에 복사하지 않는다.

## 맥락 읽기

작업에 필요한 맥락만 다음 순서로 읽는다.

1. `.claude/wiki/overview/README.md`에서 프로젝트 구조를 확인한다.
2. `.claude/wiki/knowledge/`의 관련 문서에서 현재 유효한 계약과 동작을 확인한다.
3. 안전하게 변경하기 위해 과거 결정의 이유가 필요한 경우에만
   `.claude/wiki/history/`를 읽는다.
4. 작업에 맞는 반복 절차가 있으면 실행 전에 해당
   `.claude/skills/<name>/SKILL.md`를 읽는다.

전체 wiki나 history 문서를 기본 맥락으로 읽지 않는다.

## 품질 검증

- `.claude/settings.json`의 Claude Code 훅은 Codex에서 자동으로 실행되지 않는다.
- 코드나 하네스 설정을 변경한 뒤에는 `.claude/harness.json`에 정의된
  해당 Quality Profile을 수동으로 실행한다.
  - `fast`: 범위가 한정된 변경 후 영향받는 테스트를 실행한다.
  - `full`: 완료 또는 커밋 전에 변경의 성격에 따라 린트, 포맷 검사,
    전체 테스트를 실행한다.
- 실행하지 않은 검사와 그 이유를 보고한다.

## 작업 인수인계

- Claude Code와 작업을 주고받을 때는 `CLAUDE.md`의 작업 인수인계 경로를 따른다.

## 지침의 소유 위치

`AGENTS.md`는 120줄 미만으로 유지한다. 오래 유지되는 저장소 공통 규칙과
원본 문서로 가는 경로만 둔다.

규칙을 추가하기 전에 다음 세 조건을 모두 확인한다.

1. 대부분의 작업에 적용되는가?
2. 작업별 문서를 열기 전에 알아야 하는가?
3. 최소 3개월 이상 유효할 것으로 예상되는가?

하나라도 해당하지 않으면 적절한 소유 위치에 기록한다.

- 현재 모듈 계약: `.claude/wiki/knowledge/`
- 프로젝트 지도: `.claude/wiki/overview/`
- 결정의 이유: `.claude/wiki/history/`
- 반복되는 다단계 절차: `.claude/skills/`
- 명령과 품질 설정: `.claude/harness.json` 또는 관련 스크립트
- 임시 문제 대응: 이슈, 계획, 작업 로그 또는 풀 리퀘스트

원본 문서로 연결하고, 긴 절차나 체크리스트 또는 모듈별 규칙을 이 파일에 중복하지 않는다.
