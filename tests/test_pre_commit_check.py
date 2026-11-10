"""V2 pre_commit_check가 Full Quality Profile의 트리거로만 동작하는지 확인한다."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import _hookutil

HOOK = Path(_hookutil.__file__).parent / "pre_commit_check.py"


def _config(command: list[str]) -> dict:
    return {
        "schema_version": 2,
        "wiki_root": ".claude/wiki/",
        "history": {
            "plan": "history/plan/",
            "task": "history/task/",
            "verify": "history/verify/",
            "tracked_paths": ["src/"],
        },
        "quality": {
            "profiles": {
                "full": {
                    "triggers": ["pre_commit"],
                    "stages": [{"id": "custom", "label": "Custom", "argv": command}],
                }
            }
        },
    }


def _run(root: Path, command: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "CLAUDE_PROJECT_DIR": str(root),
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=30,
        check=False,
    )


def test_failing_full_profile_denies_commit(harness_project) -> None:
    root = harness_project(_config([sys.executable, "-c", "raise SystemExit(7)"]))

    result = _run(root, 'git commit -m "test"')

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "stage: Custom" in reason
    assert "exit status: 7" in reason


def test_non_commit_command_does_not_run_profile(harness_project) -> None:
    root = harness_project(_config(["definitely-missing-command"]))

    result = _run(root, "git status")

    assert result.returncode == 0
    assert result.stdout == ""


def test_no_verify_preserves_escape_hatch(harness_project) -> None:
    root = harness_project(_config(["definitely-missing-command"]))

    result = _run(root, 'git commit --no-verify -m "test"')

    assert result.returncode == 0
    assert result.stdout == ""
