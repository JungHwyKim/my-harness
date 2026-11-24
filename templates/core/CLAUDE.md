# Project Context

## Purpose

프로젝트의 목적을 두세 문장으로 적는다.

## Global Rules

- 모든 작업에 항상 필요한 규칙만 둔다.
- 상세 모듈 계약과 과거 결정은 이 파일에 추가하지 않는다.
- **Quality Gate는 이 프로젝트가 설정하기 전까지 비활성이다.** `.claude/harness.json`의
  `fast`·`full` Profile은 `triggers`와 `stages`가 비어 있어 아무 검사도 돌지 않는다.
  비활성은 검사 통과가 아니다 — 이 상태를 완료 근거로 쓰지 않는다.
- Profile을 구성해 활성화한 뒤에는 **그 설정에 적은 명령과 완료 기준**을 따른다.
  설정 절차와 언어별 예시는 `HARNESS-INSTALL.md`에 있다.

## Context Router

1. 프로젝트 지도는 `.claude/wiki/overview/README.md`에서 찾는다.
2. 현재 유효한 계약은 관련 `.claude/wiki/knowledge/` 문서에서 찾는다.
3. 결정 이유가 필요할 때만 `.claude/wiki/history/`를 검색한다.
4. 전체 History를 기본 Context로 읽지 않는다.

## 설치 직후

`HARNESS-INSTALL.md`가 설치 직후 설정, Doctor 사용법, 비활성 Quality의 활성화 절차,
기존 파일 병합, 선택 구성의 외부 전제를 소유한다. 그 내용을 이 파일에 복사하지 않는다.

## 작업 인수인계

- Codex와 Claude Code 사이의 작업 인수인계는 `.claude/skills/handoff/SKILL.md`를 읽고 따른다.

## Information Ownership

- `CLAUDE.md`: 항상 필요한 최소 Context와 Router
- `overview/`: 어디에 무엇이 있는가
- `knowledge/`: 현재 무엇이 참인가
- `history/`: 왜 그렇게 되었는가
- `.claude/skills/`: 되풀이하는 다단계 절차를 어떻게 하는가
- `HARNESS-INSTALL.md`: 이 하네스를 이 프로젝트에 맞추는 방법
- Git: 무엇이 변경되었는가
- Tests / CI: 현재 동작이 검증되는가
