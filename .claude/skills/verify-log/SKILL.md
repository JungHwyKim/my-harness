---
name: verify-log
description: 새로운 baseline, 중요한 회귀, 의미 있는 성능·품질·비용 변화처럼 미래 비교 가치가 있는 측정과 판정을 V2 Verify History에 남긴다. 일반 lint·build·test 성공은 기록하지 않는다.
---

# verify-log

Verify History는 Quality Gate 실행 로그가 아니다. 미래에 같은 조건으로 비교할 가치가 있는
측정과 판정만 보존한다.

1. `.claude/harness.json`의 `history.verify` 경로와 같은 대상을 잰 기존 baseline을
   확인한다. 기본 경로는 `.claude/wiki/history/verify/`다.
2. 비교 기준과 재현 조건이 없는 숫자, 평소와 같은 테스트 통과는 기록하지 않는다.
3. `YYYY-MM-DD-<측정-주제>.md`에 아래 내용을 기록한다.

```markdown
# <측정·판정 제목>

- 날짜: YYYY-MM-DD
- 대상: <커밋·기능·데이터>
- 비교 기준: <이전 History·baseline·없음>
- 판정: 유지 | 개선 | 악화 | 회귀 | 판단 보류

## 왜 미래 비교 가치가 있는가
## 조건과 방법
## 결과
| 측정 | 기준 | 현재 | 차이 |
|---|---:|---:|---:|
## 판정과 근거
## 한계와 재지 못한 것
## 다시 재는 방법
## Knowledge 반영
```

유료·외부·장시간 검증은 실행 전에 사용자 승인과 프로젝트의 expensive-test 정책을 확인한다.
