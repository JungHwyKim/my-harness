"""V2 History Significance Gate의 상태 전이와 경로 계약."""

from __future__ import annotations

import time

import pytest

V2_CONFIG = {
    "schema_version": 2,
    "wiki_root": ".claude/wiki/",
    "source_prefixes": ["src/"],
    "history": {
        "plan": "history/plan/",
        "task": "history/task/",
        "verify": "history/verify/",
        "tracked_paths": ["src/", "package.json", ".claude/harness.json"],
    },
    "quality": {"profiles": {}},
}


def _skill(name: str) -> dict:
    return {"tool_input": {"skill": name}}


def test_non_python_project_files_are_recordable(load_hook) -> None:
    history, _ = load_hook("history_check", V2_CONFIG)

    assert history.is_recordable("src/app.ts") is True
    assert history.is_recordable("package.json") is True
    assert history.is_recordable("README.md") is False


def test_assessment_without_record_means_not_significant(load_hook, monkeypatch) -> None:
    history, _ = load_hook("history_check", V2_CONFIG)
    session = "not-significant"
    monkeypatch.setattr(history, "_session_changes", lambda _session: ["src/app.ts"])

    history._handle_post_tool_use(_skill("history-significance"), session)
    history._handle_stop({}, session, trust_mtime=False)


def test_missing_assessment_is_blocked_once(load_hook, monkeypatch, capsys) -> None:
    history, _ = load_hook("history_check", V2_CONFIG)
    session = "missing-assessment"
    monkeypatch.setattr(history, "_session_changes", lambda _session: ["src/app.ts"])

    with pytest.raises(SystemExit) as caught:
        history._handle_stop({}, session, trust_mtime=False)
    assert caught.value.code == 2
    assert "중요도 판단" in capsys.readouterr().err

    # 같은 상태에서 무한 Stop 루프를 만들지 않는다.
    history._handle_stop({}, session, trust_mtime=False)


def test_significant_plan_requires_plan_history(load_hook, monkeypatch, capsys) -> None:
    history, _ = load_hook("history_check", V2_CONFIG)
    session = "plan-required"
    monkeypatch.setattr(history, "_session_changes", lambda _session: [])
    history._handle_post_tool_use(_skill("plan-log"), session)

    with pytest.raises(SystemExit) as caught:
        history._handle_stop({}, session, trust_mtime=False)
    assert caught.value.code == 2
    assert "Plan History" in capsys.readouterr().err


def test_wrong_history_kind_does_not_satisfy_expected_plan(load_hook, monkeypatch) -> None:
    history, _ = load_hook("history_check", V2_CONFIG)
    session = "wrong-kind"
    monkeypatch.setattr(history, "_session_changes", lambda _session: [])
    history._handle_post_tool_use(_skill("plan-log"), session)
    history._handle_post_tool_use(
        {"tool_input": {"file_path": ".claude/wiki/history/task/wrong.md"}},
        session,
    )

    with pytest.raises(SystemExit):
        history._handle_stop({}, session, trust_mtime=False)


def test_matching_history_write_satisfies_expected_kind(load_hook, monkeypatch) -> None:
    history, _ = load_hook("history_check", V2_CONFIG)
    session = "right-kind"
    monkeypatch.setattr(history, "_session_changes", lambda _session: [])
    history._handle_post_tool_use(_skill("plan-log"), session)
    history._handle_post_tool_use(
        {"tool_input": {"file_path": ".claude/wiki/history/plan/decision.md"}},
        session,
    )

    history._handle_stop({}, session, trust_mtime=False)


def test_history_written_by_shell_is_recognised_by_mtime(load_hook, monkeypatch) -> None:
    history, root = load_hook("history_check", V2_CONFIG)
    session = "shell-write"
    monkeypatch.setattr(history._hookutil, "PROJECT_ROOT", root)
    history._hookutil.mark_session_start(session)
    time.sleep(0.01)
    target = root / history._hookutil.HISTORY_PREFIXES["verify"] / "baseline.md"
    target.parent.mkdir(parents=True)
    target.write_text("baseline", encoding="utf-8")

    assert history._recorded_this_session("verify", session, trust_mtime=True) is True


def test_shell_written_history_satisfies_stop_gate(load_hook, monkeypatch) -> None:
    history, root = load_hook("history_check", V2_CONFIG)
    session = "shell-stop"
    monkeypatch.setattr(history._hookutil, "PROJECT_ROOT", root)
    monkeypatch.setattr(history, "_session_changes", lambda _session: [])
    history._hookutil.mark_session_start(session)
    time.sleep(0.01)
    target = root / history._hookutil.HISTORY_PREFIXES["plan"] / "decision.md"
    target.parent.mkdir(parents=True)
    target.write_text("decision", encoding="utf-8")

    history._handle_stop({}, session, trust_mtime=True)

    assert history._hookutil.is_marked(history.ASSESSED_NS, session)
    assert history._hookutil.is_marked(history.EXPECTED_NS["plan"], session)


def test_v1_config_does_not_enable_v2_gate(load_hook) -> None:
    history, _ = load_hook("history_check", {"source_prefixes": ["src/"]})

    assert history._hookutil.is_v2() is False
