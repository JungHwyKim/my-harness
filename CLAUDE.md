# Project Context

## Purpose

프로젝트의 목적을 두세 문장으로 적는다.

## Global Rules

- 모든 작업에 항상 필요한 규칙만 둔다.
- 상세 모듈 계약과 과거 결정은 이 파일에 추가하지 않는다.
- 완료 전 `.claude/harness.json`에 정의된 Quality Gate를 만족한다.

## Context Router

1. 프로젝트 지도는 `.claude/wiki/overview/README.md`에서 찾는다.
2. 현재 유효한 계약은 관련 `.claude/wiki/knowledge/` 문서에서 찾는다.
3. 결정 이유가 필요할 때만 `.claude/wiki/history/`를 검색한다.
4. 전체 History를 기본 Context로 읽지 않는다.

## Information Ownership

- `CLAUDE.md`: 항상 필요한 최소 Context와 Router
- `overview/`: 어디에 무엇이 있는가
- `knowledge/`: 현재 무엇이 참인가
- `history/`: 왜 그렇게 되었는가
- Git: 무엇이 변경되었는가
- Tests / CI: 현재 동작이 검증되는가
