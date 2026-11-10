# Project Context

## Purpose

프로젝트의 목적과 핵심 사용자를 두세 문장으로 적는다.

## Global Rules

- 모든 작업에 항상 필요한 규칙만 둔다.
- 상세 계약, 긴 절차, 과거 결정은 이 파일에 쌓지 않는다.
- 코드·테스트·설정을 고쳤다면 완료 전에 프로젝트 Quality Gate를 통과한다.

## Context Router

1. 프로젝트의 구조와 진입점은 `.claude/wiki/overview/`에서 찾는다.
2. 현재 규칙과 모듈 계약은 `.claude/wiki/knowledge/`에서 찾는다.
3. 설계 논의와 구현 회고는 `.claude/wiki/plan_log/`, `task_log/`,
   `verify_log/`에서 필요한 문서만 읽는다.
4. 전체 Wiki나 모든 기록을 기본 컨텍스트로 읽지 않는다.

## Information Ownership

- `CLAUDE.md`: 최소 공통 규칙과 문서 탐색 경로
- `overview/`: 프로젝트 구조와 진입점
- `knowledge/`: 현재 유효한 계약
- `plan_log/`: 중요한 설계 논의와 미결
- `task_log/`: 구현 중의 결정·실패·후속 작업
- `verify_log/`: 비교할 수 있는 검증 수치
- Git: 변경 사실
- Tests / CI: 현재 동작

