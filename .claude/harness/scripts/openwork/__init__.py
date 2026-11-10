"""프로젝트가 지정한 작업 정보원에서 열린 항목을 모으는 결정적 수집기.

V2에서는 `.claude/harness.json`의 `checks.openwork.sources`만 읽는다. V1 프로젝트에는 기존
`plan_log`와 `task_log` 수집 계약을 그대로 제공한다.
"""

from __future__ import annotations
