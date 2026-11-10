---
name: plan-log
description: 구현 전에 내린 중요한 결정과 그 이유를 V2 Plan History에 남긴다. 여러 대안을 비교했거나 아키텍처·공용 계약·정책을 정한 경우에만 사용하며, 일반 작업 계획은 기록하지 않는다.
---

# plan-log

Plan History는 계획서 저장소가 아니다. 미래 작업자가 무엇을 골랐고 무엇을 버렸는지
알아야 할 때만 쓴다.

1. `.claude/harness.json`의 `history.plan` 경로를 확인한다. 기본은
   `.claude/wiki/history/plan/`이다.
2. 같은 결정이 Knowledge 또는 Plan History에 있는지 먼저 검색한다. 새 사실이 없다면
   중복 기록하지 않는다.
3. `YYYY-MM-DD-<결정-주제>.md`를 만들고 아래 내용을 남긴다.

```markdown
# <결정 제목>

- 날짜: YYYY-MM-DD
- 상태: 제안 | 승인 | 대체됨
- 영향 범위: <모듈·계약·사용자>

## 결정할 문제
## 검토한 선택지
## 결정
## 이유
## 기각한 대안
## 영향과 후속 조건
## Knowledge 반영
```

결정이 현재 시스템의 계약이 되면 Knowledge에는 지금 지켜야 할 규칙만 압축해 반영한다.
