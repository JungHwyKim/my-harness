"""V2 Quality Profile 공통 실행기의 계약."""

from __future__ import annotations

import sys

import pytest


def _config(stages: list[dict], *, triggers: list[str] | None = None) -> dict:
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
                "fast": {
                    "triggers": triggers or ["post_change"],
                    "stages": stages,
                }
            }
        },
    }


def test_arbitrary_executable_runs_without_python_prefix(load_hook) -> None:
    config = _config(
        [
            {
                "id": "custom",
                "argv": [sys.executable, "-c", "print('generic-runner')"],
            }
        ]
    )
    quality, _ = load_hook("_quality", config)

    result = quality.run_profile("fast")[0]

    assert result.ok is True
    assert result.argv[0] == sys.executable
    assert result.output == "generic-runner"


def test_placeholders_expand_as_separate_arguments(load_hook) -> None:
    script = "import sys; print('|'.join(sys.argv[1:]))"
    config = _config(
        [
            {
                "id": "scoped",
                "argv": [sys.executable, "-c", script, "{changed_files}", "{mapped_targets}"],
            }
        ]
    )
    quality, _ = load_hook("_quality", config)

    result = quality.run_profile(
        "fast",
        changed_files=("src/a file.ts", "src/b.ts"),
        mapped_targets=("tests/a test.ts",),
    )[0]

    assert result.ok is True
    assert result.output == "src/a file.ts|src/b.ts|tests/a test.ts"


def test_empty_list_placeholder_skips_stage(load_hook) -> None:
    config = _config([{"id": "scoped", "argv": ["missing-command", "{mapped_targets}"]}])
    quality, _ = load_hook("_quality", config)

    result = quality.run_profile("fast")[0]

    assert result.ok is True
    assert result.skipped is True


def test_success_codes_are_project_defined(load_hook) -> None:
    config = _config(
        [
            {
                "id": "no-tests",
                "argv": [sys.executable, "-c", "raise SystemExit(5)"],
                "success_codes": [0, 5],
            }
        ]
    )
    quality, _ = load_hook("_quality", config)

    result = quality.run_profile("fast")[0]

    assert result.ok is True
    assert result.returncode == 5


def test_profile_stops_at_first_failure(load_hook) -> None:
    config = _config(
        [
            {"id": "lint", "argv": [sys.executable, "-c", "raise SystemExit(7)"]},
            {"id": "test", "argv": [sys.executable, "-c", "print('must-not-run')"]},
        ]
    )
    quality, _ = load_hook("_quality", config)

    results = quality.run_profile("fast")

    assert [result.stage_id for result in results] == ["lint"]
    assert results[0].returncode == 7


def test_failure_message_contains_stage_command_and_status(load_hook) -> None:
    config = _config(
        [{"id": "build", "label": "Build", "argv": [sys.executable, "-c", "raise SystemExit(3)"]}]
    )
    quality, _ = load_hook("_quality", config)
    result = quality.run_profile("fast")[0]

    message = quality.failure_message(result)

    assert "stage: Build" in message
    assert "command:" in message
    assert "exit status: 3" in message


def test_unknown_placeholder_is_configuration_error(load_hook) -> None:
    quality, _ = load_hook(
        "_quality",
        _config([{"id": "lint", "argv": ["tool", "{mystery}"]}]),
    )

    with pytest.raises(quality.QualityConfigError, match="알 수 없는 치환값"):
        quality.load_profile("fast")


def test_trigger_is_read_from_profile(load_hook) -> None:
    quality, _ = load_hook("_quality", _config([], triggers=["stop"]))

    assert quality.profile_has_trigger("fast", "stop") is True
    assert quality.profile_has_trigger("fast", "post_change") is False
