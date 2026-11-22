"""이 저장소의 **개발용** V2 설정과 Context Router의 최소 계약.

**한때 이 파일은 「새 프로젝트용 설정」을 잰다고 적혀 있었다.** `.claude/harness.json` 하나가
개발용 설정과 배포 예시를 겸하고 있었기 때문이다. 그 설정이 하네스 자신을 개발하는 값으로
바뀌면서(매핑이 `.claude/harness/` → `tests/`) 그 설명은 더 이상 맞지 않는다 — 대상
프로젝트에는 `.claude/harness/`를 재는 `tests/`가 없다.

배포용 기본 설정을 따로 떼는 것은 `tasks/template-core-packs.md`의 몫이다. 그때까지 이
저장소에는 범용 설치물로 쓸 설정이 없고, 이 파일이 재는 것은 **개발 설정이 성립하는가**뿐이다.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLAUDE_DIR = REPO / ".claude"


def test_dev_config_loads_both_quality_profiles(load_hook) -> None:
    config = json.loads((CLAUDE_DIR / "harness.json").read_text(encoding="utf-8"))
    quality, _ = load_hook("_quality", config)

    assert quality.load_profile("fast")
    assert quality.load_profile("full")
    assert quality.profile_has_trigger("fast", "post_change")
    assert quality.profile_has_trigger("full", "stop")
    assert quality.profile_has_trigger("full", "pre_commit")


def test_schema_and_dev_config_agree_on_version() -> None:
    schema = json.loads(
        (CLAUDE_DIR / "harness" / "schemas" / "harness.schema.json").read_text(encoding="utf-8")
    )
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
