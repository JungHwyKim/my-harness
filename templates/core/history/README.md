# Project History

미래 작업자가 알아야 할 중요한 이유와 근거만 보존한다.

- `plan/`: 구현 전에 내린 중요한 결정
- `task/`: 구현 중 계획과 달라진 결정, 실패, 제약
- `verify/`: 미래 비교 가치가 있는 측정과 판정

단순 작업 완료, 일반 테스트 성공, Git으로 확인 가능한 변경은 기록하지 않는다.

기록 경로는 `.claude/harness.json`의 `wiki_root`와 `history`가 정한다.
세 폴더는 비어 있는 상태로 설치되며, 기록 절차는 `.claude/skills/`의
`plan-log`·`task-log`·`verify-log`가 소유한다.
