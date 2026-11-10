"""새 프로젝트용 V2 설정과 Context Router 템플릿의 최소 계약."""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLAUDE_DIR = REPO / ".claude"


def test_example_config_loads_both_quality_profiles(load_hook) -> None:
    config = json.loads((CLAUDE_DIR / "harness.json").read_text(encoding="utf-8"))
    quality, _ = load_hook("_quality", config)

    assert quality.load_profile("fast")
    assert quality.load_profile("full")
    assert quality.profile_has_trigger("fast", "post_change")
    assert quality.profile_has_trigger("full", "stop")
    assert quality.profile_has_trigger("full", "pre_commit")


def test_schema_and_example_agree_on_version() -> None:
    schema = json.loads((CLAUDE_DIR / "harness" / "schemas" / "harness.schema.json").read_text(encoding="utf-8"))
    example = json.loads((CLAUDE_DIR / "harness.json").read_text(encoding="utf-8"))

    assert schema["properties"]["schema_version"]["const"] == 2
    assert example["schema_version"] == 2
    assert set(example["history"]) >= {"plan", "task", "verify", "tracked_paths"}


def test_router_targets_have_templates() -> None:
    router = (REPO / "CLAUDE.md").read_text(encoding="utf-8")

    assert ".claude/wiki/overview/README.md" in router
    assert ".claude/wiki/knowledge/" in router
    assert ".claude/wiki/history/" in router
    assert (CLAUDE_DIR / "wiki" / "overview" / "README.md").is_file()
    assert (CLAUDE_DIR / "wiki" / "knowledge" / "README.md").is_file()
    assert (CLAUDE_DIR / "wiki" / "history" / "README.md").is_file()
