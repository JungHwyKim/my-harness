# Project Overview

이 저장소는 Claude Code 하네스**이면서** 그 하네스를 다른 프로젝트로 내보내는 원본이다.
**설치물의 구조는 이 트리와 다르다** — 무엇이 따라가고 무엇이 소스에만 남는지는 아래
내보내기 계약이 소유한다.

## 어디에 무엇이 있는가

| 경로 | 무엇인가 |
|---|---|
| `.claude/settings.json` | 훅 배선. 고유 스크립트 9개를 이벤트별로 연결한다 |
| `.claude/harness/hooks/` | 훅 스크립트와 공유 모듈 |
| `.claude/harness/scripts/` | Doctor, 수동 Quality CLI, openwork 수집기, exporter |
| `.claude/harness/schemas/` | `harness.json` 스키마 |
| `.claude/harness.json` | **이 저장소를 개발하는** 품질·History 설정 |
| `.claude/skills/` | 공통 작업 절차 7개 |
| `packs/` | 선택 구성의 원본 — `rag`, `interview` |
| `templates/core/` | 설치물의 진입점·설정·설치 안내·배포 Knowledge |
| `templates/manifest.json` | `source` → `destination` 목록. 복사 목록의 유일한 소유자 |
| `tests/` | 이 저장소의 테스트 |
| `tasks/` | 진행 중인 작업 명세와 리뷰 |

## 현재 유효한 계약

- [내보내기 계약](../knowledge/template-layout.md) — packs·templates·manifest·exporter.
  **소스 전용 문서**다
- [템플릿 배포 모델](../knowledge/template-deploy.md) — 배포 ref와 History 보존.
  **소스 전용 문서**다
- [검증 환경과 Quality Profile](../knowledge/quality-env.md)
- [Doctor 정적 진단](../knowledge/doctor.md)
- [유료 테스트 승인](../knowledge/paid-test-approval.md)

상세 계약이나 과거 결정은 이 문서에 복제하지 않는다.
