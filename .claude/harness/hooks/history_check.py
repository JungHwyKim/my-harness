"""V2 History Significance 판단과 기록 이행을 확인하는 훅.

의미 판단은 `history-significance` Skill이 맡는다. 이 훅은 다음 사실만 결정론적으로 확인한다.

* 기록 대상 변경이 있었는데 중요도 판단을 수행했는가
* Plan/Task/Verify History를 남기기로 했다면 해당 종류를 실제로 썼는가

`history-significance`만 호출되고 기록 Skill이 호출되지 않으면 Not Significant 판정으로 본다.
`plan-log`·`task-log`·`verify-log`가 호출되거나 해당 폴더에 파일이 쓰이면 Significant로 본다.
차단은 상태별로 세션당 한 번만 한다. 판단 오류보다 끝나지 않는 Stop 루프의 비용이 더 크기
때문이다.
"""

from __future__ import annotations

import os

import _hookutil

ASSESS_SKILL = "history-significance"
RECORD_SKILLS = {
    "plan-log": "plan",
    "task-log": "task",
    "verify-log": "verify",
}

ASSESSED_NS = "claude_history_assessed"
EXPECTED_NS = {kind: f"claude_history_expected_{kind}" for kind in RECORD_SKILLS.values()}
WRITTEN_NS = {kind: f"claude_history_written_{kind}" for kind in RECORD_SKILLS.values()}
ASSESS_BLOCKED_NS = "claude_history_assessment_blocked"
RECORD_BLOCKED_NS = {kind: f"claude_history_record_blocked_{kind}" for kind in RECORD_SKILLS.values()}


def _history_section() -> dict:
    value = _hookutil.config().get("history")
    return value if isinstance(value, dict) else {}


def tracked_paths() -> tuple[str, ...]:
    raw = _history_section().get("tracked_paths")
    if isinstance(raw, list):
        values = tuple(item for item in raw if isinstance(item, str) and item.strip())
        if values:
            return values
    return (*_hookutil.config_list("source_prefixes"), *_hookutil.config_list("harness_paths"))


TRACKED_PATHS = tracked_paths()


def _normalized(path: str) -> str:
    value = path.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value.lstrip("/")


def _matches_entry(path: str, entry: str) -> bool:
    candidate = _normalized(entry)
    if not candidate:
        return False
    return path.startswith(candidate) if candidate.endswith("/") else path == candidate


def is_recordable(path: str) -> bool:
    normalized = _normalized(path)
    return any(_matches_entry(normalized, entry) for entry in TRACKED_PATHS)


def _skill_name(payload: dict) -> str:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    raw = str(tool_input.get("skill") or "").strip()
    return raw.rsplit(":", 1)[-1]


def _written_kind(payload: dict) -> str | None:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    rel = _hookutil.relative_to_root(str(tool_input.get("file_path") or ""))
    if rel is None:
        return None
    for kind, prefix in _hookutil.HISTORY_PREFIXES.items():
        if rel.startswith(prefix):
            return kind
    return None


def _handle_post_tool_use(payload: dict, session_id: str) -> None:
    skill = _skill_name(payload)
    if skill == ASSESS_SKILL:
        _hookutil.claim_session(ASSESSED_NS, session_id)
    kind = RECORD_SKILLS.get(skill)
    if kind is not None:
        _hookutil.claim_session(ASSESSED_NS, session_id)
        _hookutil.claim_session(EXPECTED_NS[kind], session_id)

    written = _written_kind(payload)
    if written is not None:
        _hookutil.claim_session(ASSESSED_NS, session_id)
        _hookutil.claim_session(EXPECTED_NS[written], session_id)
        _hookutil.claim_session(WRITTEN_NS[written], session_id)


def _recorded_this_session(kind: str, session_id: str, *, trust_mtime: bool) -> bool:
    if _hookutil.is_marked(WRITTEN_NS[kind], session_id):
        return True
    if not trust_mtime:
        return False
    return _hookutil.wrote_under(_hookutil.HISTORY_PREFIXES[kind], session_id) is True


def _session_changes(session_id: str) -> list[str]:
    found: set[str] = set()
    paths = _hookutil.changed_paths()
    if paths is not None:
        found.update(path for path in paths if is_recordable(path))
    started = _hookutil.session_started_at(session_id)
    if started is not None:
        newer = _hookutil.tracked_paths_newer_than(TRACKED_PATHS, started)
        if newer:
            found.update(path for path in newer if is_recordable(path))
    return sorted(found)


def _block_once(namespace: str, session_id: str, reason: str) -> None:
    if _hookutil.claim_session(namespace, session_id):
        _hookutil.block(reason)


def _handle_stop(payload: dict, session_id: str, *, trust_mtime: bool) -> None:
    if payload.get("stop_hook_active"):
        return

    # Bash/PowerShell로 쓴 History도 종류를 추론한다. Write/Edit에만 file_path가 있으므로
    # mtime 보조 경로가 없으면 기록을 잘 남기고도 Significant 상태를 확인하지 못한다.
    if trust_mtime:
        for kind, expected_namespace in EXPECTED_NS.items():
            if _hookutil.wrote_under(_hookutil.HISTORY_PREFIXES[kind], session_id) is True:
                _hookutil.claim_session(ASSESSED_NS, session_id)
                _hookutil.claim_session(expected_namespace, session_id)
                _hookutil.claim_session(WRITTEN_NS[kind], session_id)

    expected = tuple(
        kind for kind, namespace in EXPECTED_NS.items() if _hookutil.is_marked(namespace, session_id)
    )
    changes = _session_changes(session_id)
    if not changes and not expected:
        return

    if not _hookutil.is_marked(ASSESSED_NS, session_id) and not expected:
        sample = ", ".join(changes[:5])
        _block_once(
            ASSESS_BLOCKED_NS,
            session_id,
            "기록 대상 변경이 있지만 History 중요도 판단을 하지 않았습니다.\n\n"
            f"변경: {sample or '(경로 확인 불가)'}\n\n"
            "history-significance Skill로 미래 작업자에게 중요한 결정·이탈·실패·제약·측정이 "
            "생겼는지 판단하세요. 중요하지 않으면 기록 없이 다시 마칠 수 있습니다.\n"
            "사용자가 의도적으로 끄려면 SKIP_HISTORY=1 을 설정할 수 있습니다.",
        )
        return

    for kind in expected:
        if _recorded_this_session(kind, session_id, trust_mtime=trust_mtime):
            continue
        _block_once(
            RECORD_BLOCKED_NS[kind],
            session_id,
            f"{kind.title()} History를 남기기로 판단했지만 기록이 없습니다.\n\n"
            f"{_hookutil.HISTORY_PREFIXES[kind]} 아래에 중요한 이유와 근거를 기록한 뒤 마치세요.\n"
            "단순 변경 목록과 일반 테스트 성공은 적지 않습니다.",
        )
        return


def main() -> None:
    payload = _hookutil.read_payload()
    if payload is None or not _hookutil.is_v2() or os.environ.get("SKIP_HISTORY"):
        return

    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        return
    baseline_is_fresh = _hookutil.mark_session_start(session_id)
    event = str(payload.get("hook_event_name") or "")
    if event == "PostToolUse":
        _handle_post_tool_use(payload, session_id)
    elif event == "Stop":
        _handle_stop(payload, session_id, trust_mtime=not baseline_is_fresh)


if __name__ == "__main__":
    main()
