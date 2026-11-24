# Project Overview

프로젝트의 주요 디렉터리, 진입점, 관련 Knowledge 문서로 가는 링크를 적는다.

상세 계약이나 과거 결정은 이 문서에 복제하지 않는다.

## 설치된 하네스의 자리

| 경로 | 무엇인가 |
|---|---|
| `CLAUDE.md`, `AGENTS.md` | 에이전트 진입점. 공통 규칙과 Router |
| `HARNESS-INSTALL.md` | 설치 직후 설정, Doctor 사용법, Quality 활성화 절차 |
| `.claude/harness.json` | 이 프로젝트의 Quality·History 설정. 설치 직후에는 비활성 |
| `.claude/settings.json` | Claude Code 훅 배선 |
| `.claude/harness/hooks/` | 훅 스크립트 |
| `.claude/harness/scripts/` | Doctor와 수동 Quality CLI |
| `.claude/harness/schemas/` | `harness.json` 스키마 |
| `.claude/skills/` | 되풀이하는 다단계 절차 |
| `.claude/wiki/` | overview · knowledge · history |

## 현재 유효한 계약

- [Doctor 정적 진단](../knowledge/doctor.md)
- [검증 환경과 Quality Profile](../knowledge/quality-env.md)
- [유료 테스트 승인](../knowledge/paid-test-approval.md)

프로젝트 고유의 Knowledge 문서는 여기에 덧붙인다.
