---
name: task-log
description: 구현 중 계획과 실제가 의미 있게 달라졌거나 반복할 실패, 예상하기 어려운 원인, 코드만으로 알기 어려운 제약을 발견했을 때 V2 Task History에 남긴다. 일반 작업 보고서나 변경 파일 목록은 만들지 않는다.
---

# task-log

Task History는 “무엇을 구현했다”를 적는 작업 일지가 아니다. Git으로 알 수 없는
이탈·실패·제약의 이유를 보존한다.

1. `.claude/harness.json`의 `history.task` 경로를 확인한다. 기본은
   `.claude/wiki/history/task/`이다.
2. 같은 원인이나 제약이 기존 Knowledge/History에 있는지 먼저 찾는다.
3. `YYYY-MM-DD-<이탈-또는-제약>.md`에 아래 내용을 기록한다.

```markdown
# <이탈·실패·제약 제목>

- 날짜: YYYY-MM-DD
- 관련 계획: <있으면 Plan History 링크>
- 영향 범위: <모듈·계약·운영>

## 원래 예상
## 실제로 드러난 것
## 원인
## 내린 결정
## 기각하거나 되돌린 접근
## 재발 방지와 남은 제약
## Knowledge 반영
```

현재도 유효한 제약은 Knowledge에 현재 규칙만 반영한다. 코드 변경과 일반 테스트 통과는
Git과 Quality Gate가 보존하므로 여기 적지 않는다.
