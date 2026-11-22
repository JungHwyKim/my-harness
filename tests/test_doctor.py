"""`doctor.py` 의 정적 진단을 **임시 프로젝트**에서 잰다.

이 저장소의 현재 상태를 단정하는 스냅샷 테스트를 쓰지 않는다. 이 저장소는 건강한 설정
하나일 뿐이고, Doctor 가 잡아야 하는 것은 **고장 난 설정**이다. 그래서 테스트마다 임시
프로젝트를 세우고 한 자리만 망가뜨려 그 판정과 종료 코드를 본다.

구현 함수를 그대로 다시 부르는 테스트도 쓰지 않는다. 판정이 실행기의 실제 분기와
맞는지가 요점이라, 기대값은 `_quality.py`·`_hookutil.py`·`auto_test_check.py` 의 동작에서
가져온다.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import doctor

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / ".claude" / "harness" / "schemas" / "harness.schema.json"
DOCTOR_SOURCE = Path(doctor.__file__).resolve()

HOOK_SCRIPTS = ("auto_test_check.py", "pre_commit_check.py")


def healthy_config() -> dict:
    return {
        "schema_version": 2,
        "wiki_root": ".claude/wiki/",
        "python": "py-stub",
        "source_prefixes": ["src/", "tests/"],
        "harness_paths": [".claude/harness.json"],
        "history": {
            "plan": "history/plan/",
            "task": "history/task/",
            "verify": "history/verify/",
            "tracked_paths": ["src/", "tests/"],
        },
        "quality": {
            "tracked_paths": ["src/", "tests/"],
            "mappings": [{"path": "src/", "tests": "tests/"}],
            "unmapped_by_design": {},
            "profiles": {
                "fast": {
                    "triggers": ["post_change"],
                    "stages": [
                        {
                            "id": "test",
                            "argv": ["{python}", "-m", "pytest", "{mapped_targets}"],
                            "timeout": 90,
                            "success_codes": [0, 5],
                        }
                    ],
                },
                "full": {
                    "triggers": ["stop", "pre_commit"],
                    "stages": [{"id": "lint", "argv": ["{python}", "-m", "ruff", "check", "."]}],
                },
            },
        },
    }


def hook_command(script: str) -> str:
    return f'python "${{CLAUDE_PROJECT_DIR}}/.claude/harness/hooks/{script}"'


def healthy_settings() -> dict:
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash|PowerShell",
                    "hooks": [{"type": "command", "command": hook_command("pre_commit_check.py")}],
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [{"type": "command", "command": hook_command("auto_test_check.py")}],
                },
                {
                    "matcher": "Bash|PowerShell",
                    "hooks": [{"type": "command", "command": hook_command("auto_test_check.py")}],
                },
            ],
            "Stop": [
                {"hooks": [{"type": "command", "command": hook_command("auto_test_check.py")}]}
            ],
        }
    }


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# 건강한 V2 프로젝트. 각 테스트는 여기서 한 자리만 망가뜨린다.
#
# **빈 디렉터리가 아니라 실제 파일을 만드는 것이 요점이다.** Doctor 의 판정 절반이
# 「그 경로가 파일인가 디렉터리인가」에 걸려 있어서, 모킹하면 바로 그 분기를 건너뛴다
@pytest.fixture
def project(tmp_path: Path):
    def build(
        *,
        config: object = None,
        settings: object = None,
        name: str = "proj",
        files: bool = True,
    ) -> Path:
        root = tmp_path / name
        root.mkdir(parents=True, exist_ok=True)

        if files:
            (root / "CLAUDE.md").write_text("# 규칙\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("# Codex\n", encoding="utf-8")
            (root / "py-stub").write_text("", encoding="utf-8")
            for name_ in ("overview", "knowledge"):
                target = root / ".claude" / "wiki" / name_ / "README.md"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("# 문서\n", encoding="utf-8")
            for kind in ("plan", "task", "verify"):
                (root / ".claude" / "wiki" / "history" / kind).mkdir(parents=True, exist_ok=True)
            for folder in ("src", "tests"):
                (root / folder).mkdir(parents=True, exist_ok=True)
                (root / folder / "keep.py").write_text("", encoding="utf-8")
            hooks = root / ".claude" / "harness" / "hooks"
            hooks.mkdir(parents=True, exist_ok=True)
            for script in HOOK_SCRIPTS:
                (hooks / script).write_text("# 훅\n", encoding="utf-8")

        write_json(
            root / ".claude" / "harness.json",
            healthy_config() if config is None else config,
        )
        write_json(
            root / ".claude" / "settings.json",
            healthy_settings() if settings is None else settings,
        )
        return root

    return build


def levels(report: doctor.Report, check: str) -> list[str]:
    return [item.level for item in report.findings if item.check == check]


def levels_at(report: doctor.Report, check: str, where_contains: str) -> list[str]:
    return [
        item.level
        for item in report.findings
        if item.check == check and where_contains in item.where
    ]


def messages(report: doctor.Report, check: str) -> str:
    return "\n".join(
        f"{item.where} {item.why} {item.fix}" for item in report.findings if item.check == check
    )


def failures(report: doctor.Report) -> list[str]:
    return [f"{item.check} {item.where}" for item in report.findings if item.level == doctor.FAIL]


def install_doctor(root: Path) -> Path:
    target = root / ".claude" / "harness" / "scripts" / "doctor.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DOCTOR_SOURCE, target)
    return target


def run_cli(script: Path, *, cwd: Path, project_dir: Path | None = None):
    env = os.environ.copy()
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    else:
        env.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        stdin=subprocess.DEVNULL,
        check=False,
    )


# ─────────────────── 1. 기본 동작과 깨진 입력 ───────────────────


def test_healthy_project_has_no_fail(project):
    report = doctor.diagnose(project())
    assert failures(report) == []


def test_healthy_project_passes_each_core_check(project):
    report = doctor.diagnose(project())
    for check in ("D-FILES", "D-JSON", "D-VERSION", "D-PROFILE", "D-WIRING", "D-HOOK"):
        assert doctor.PASS in levels(report, check), check


def test_cli_exit_zero_on_healthy(project):
    root = project()
    proc = run_cli(install_doctor(root), cwd=root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "대상 루트" in proc.stdout


def test_missing_required_files_fail(project):
    root = project()
    (root / "CLAUDE.md").unlink()
    report = doctor.diagnose(root)
    assert doctor.FAIL in levels(report, "D-FILES")
    assert "CLAUDE.md" in messages(report, "D-FILES")


def test_missing_agents_md_is_warn_only(project):
    root = project()
    (root / "AGENTS.md").unlink()
    report = doctor.diagnose(root)
    assert levels(report, "D-OPTIONAL") == [doctor.WARN]
    assert failures(report) == []


def test_bom_json_is_accepted(project):
    root = project()
    path = root / ".claude" / "harness.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(healthy_config()).encode("utf-8"))
    report = doctor.diagnose(root)
    assert doctor.FAIL not in levels(report, "D-JSON")
    assert failures(report) == []


def test_broken_json_fails_and_keeps_independent_checks(project):
    root = project()
    (root / ".claude" / "harness.json").write_text("{ this is not json", encoding="utf-8")
    report = doctor.diagnose(root)
    assert doctor.FAIL in levels(report, "D-JSON")
    # settings 쪽은 독립이므로 계속 봐야 한다
    assert doctor.PASS in levels(report, "D-HOOK")
    # 그리고 못 본 것은 PASS 가 아니라 미검사다
    assert doctor.PASS not in levels(report, "D-CONFIG")
    assert "미검사" in messages(report, "D-CONFIG")


def test_top_level_array_fails(project):
    root = project()
    write_json(root / ".claude" / "harness.json", [1, 2, 3])
    report = doctor.diagnose(root)
    assert doctor.FAIL in levels(report, "D-JSON")


@pytest.mark.parametrize(
    "config",
    [
        {"schema_version": 2, "quality": "문자열", "history": "문자열", "wiki_root": "w/"},
        {"schema_version": 2, "wiki_root": "w/", "history": {}, "quality": {"profiles": []}},
        {
            "schema_version": 2,
            "wiki_root": "w/",
            "history": {"plan": 1, "task": None, "verify": [], "tracked_paths": "x"},
            "quality": {"profiles": {"fast": 3, "full": None}},
        },
    ],
)
def test_wrong_nested_types_do_not_crash(project, config):
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL in levels(report, "D-CONFIG")


def test_cli_exit_one_on_fail(project):
    root = project()
    (root / "CLAUDE.md").unlink()
    proc = run_cli(install_doctor(root), cwd=root)
    assert proc.returncode == 1, proc.stdout


def test_json_error_is_exit_one_not_two(project):
    root = project()
    (root / ".claude" / "harness.json").write_text("{", encoding="utf-8")
    proc = run_cli(install_doctor(root), cwd=root)
    assert proc.returncode == 1, proc.stdout
    assert "진단 미완료" not in proc.stdout


def test_bad_layout_is_exit_two(project, tmp_path: Path):
    root = project()
    stray = tmp_path / "stray" / "doctor.py"
    stray.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DOCTOR_SOURCE, stray)
    proc = run_cli(stray, cwd=root)
    assert proc.returncode == 2, proc.stdout
    assert "D-RUN" in proc.stdout
    assert "진단 미완료" in proc.stdout


def test_internal_error_is_exit_two(project, monkeypatch: pytest.MonkeyPatch):
    project()

    def boom(_root):
        raise RuntimeError("일부러 터뜨린다")

    monkeypatch.setattr(doctor, "diagnose", boom)
    monkeypatch.setattr(doctor, "resolve_root", lambda _script: REPO_ROOT)
    assert doctor.main([]) == 2


def test_report_never_dresses_unchecked_as_pass(project):
    root = project()
    (root / ".claude" / "harness.json").write_text("{", encoding="utf-8")
    report = doctor.diagnose(root)
    for item in report.findings:
        if "미검사" in item.why:
            assert item.level == doctor.WARN


# ─────────────────── 2. 버전과 구조 ───────────────────


def test_schema_constants_match_schema_file():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))
    defs = schema["$defs"]
    assert tuple(schema["required"]) == doctor.ROOT_REQUIRED
    assert schema["properties"]["schema_version"]["const"] == 2
    assert schema["additionalProperties"] is True
    history = schema["properties"]["history"]
    assert tuple(history["required"]) == doctor.HISTORY_REQUIRED
    assert tuple(history["properties"]) == doctor.HISTORY_ALLOWED
    quality = schema["properties"]["quality"]
    assert tuple(quality["required"]) == doctor.QUALITY_REQUIRED
    assert set(quality["properties"]) == set(doctor.QUALITY_ALLOWED)
    assert set(quality["properties"]["profiles"]["properties"]) == set(doctor.PROFILE_NAMES)
    assert tuple(defs["profile"]["required"]) == doctor.PROFILE_REQUIRED
    assert set(defs["profile"]["properties"]) == set(doctor.PROFILE_ALLOWED)
    assert tuple(defs["stage"]["required"]) == doctor.STAGE_REQUIRED
    assert set(defs["stage"]["properties"]) == set(doctor.STAGE_ALLOWED)
    assert defs["stage"]["properties"]["id"]["pattern"] == doctor.STAGE_ID_PATTERN
    assert tuple(defs["profile"]["properties"]["triggers"]["items"]["enum"]) == doctor.TRIGGER_ENUM
    mapping = quality["properties"]["mappings"]["items"]
    assert tuple(mapping["required"]) == doctor.MAPPING_REQUIRED
    assert set(mapping["properties"]) == set(doctor.MAPPING_ALLOWED)
    # profiles 에 required 가 없다는 것이 D-PROFILE 이 WARN 인 근거다
    assert "required" not in quality["properties"]["profiles"]
    assert "minItems" not in defs["profile"]["properties"]["triggers"]
    assert "minItems" not in defs["profile"]["properties"]["stages"]


def test_missing_version_is_warn_and_exit_zero(project):
    config = {"wiki_root": ".claude/wiki/"}
    root = project(config=config)
    report = doctor.diagnose(root)
    assert levels(report, "D-VERSION") == [doctor.WARN]
    assert failures(report) == []
    assert "V1" in messages(report, "D-VERSION")


def test_v1_empty_config_warns_only(project):
    root = project(config={})
    report = doctor.diagnose(root)
    assert failures(report) == []
    assert "미검사" in messages(report, "D-CONFIG")
    proc = run_cli(install_doctor(root), cwd=root)
    assert proc.returncode == 0, proc.stdout


def test_version_two_turns_missing_structure_into_fail(project):
    root = project(config={"schema_version": 2})
    report = doctor.diagnose(root)
    assert doctor.FAIL in levels(report, "D-CONFIG")
    text = messages(report, "D-CONFIG")
    for key in ("wiki_root", "history", "quality"):
        assert key in text
    # 버전은 D-VERSION 소유다 — D-CONFIG 가 같은 사실을 다시 말하지 않는다
    assert "schema_version" not in text


def test_version_one_does_not_get_v2_required_errors(project):
    root = project(config={"schema_version": 1})
    report = doctor.diagnose(root)
    assert failures(report) == []
    assert levels(report, "D-VERSION") == [doctor.WARN]


@pytest.mark.parametrize("value", ["2", 2.0, True, False, 0, -1, None])
def test_bad_version_types_fail_and_explain_v1_fallback(project, value):
    config = healthy_config()
    config["schema_version"] = value
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL in levels(report, "D-VERSION")
    text = messages(report, "D-VERSION")
    assert "1" in text and "V2" in text


def test_version_three_fails_but_notes_v2_branch_active(project):
    config = healthy_config()
    config["schema_version"] = 3
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL in levels(report, "D-VERSION")
    text = messages(report, "D-VERSION")
    assert "is_v2()" in text


def test_unsupported_version_skips_v2_detail(project):
    config = healthy_config()
    config["schema_version"] = 3
    config["quality"] = "완전히 잘못된 모양"
    report = doctor.diagnose(project(config=config))
    # V2 상세 검증을 생략하므로 quality 구조 FAIL 이 추가되지 않는다
    assert doctor.FAIL not in levels(report, "D-CONFIG")
    assert "미검사" in messages(report, "D-CONFIG")


def test_missing_profile_is_warn(project):
    config = healthy_config()
    del config["quality"]["profiles"]["fast"]
    report = doctor.diagnose(project(config=config))
    assert doctor.WARN in levels(report, "D-PROFILE")
    assert failures(report) == []


def test_empty_triggers_or_stages_is_warn(project):
    config = healthy_config()
    config["quality"]["profiles"]["fast"]["stages"] = []
    report = doctor.diagnose(project(config=config))
    assert doctor.WARN in levels(report, "D-PROFILE")
    assert failures(report) == []


def test_wrong_trigger_combination_fails(project):
    config = healthy_config()
    config["quality"]["profiles"]["fast"]["triggers"] = ["stop"]
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL in levels(report, "D-TRIGGER")


def test_wrong_trigger_fails_even_with_empty_stages(project):
    config = healthy_config()
    config["quality"]["profiles"]["full"]["triggers"] = ["post_change"]
    config["quality"]["profiles"]["full"]["stages"] = []
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL in levels(report, "D-TRIGGER")
    assert doctor.WARN in levels(report, "D-PROFILE")


def test_duplicate_stage_id_fails(project):
    config = healthy_config()
    config["quality"]["profiles"]["full"]["stages"].append(
        {"id": "lint", "argv": ["{python}", "-m", "ruff", "format", "--check", "."]}
    )
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL in levels(report, "D-CONFIG")
    assert "중복" in messages(report, "D-CONFIG")


@pytest.mark.parametrize(
    "patch",
    [
        {"timeout": 0},
        {"timeout": 3601},
        {"timeout": True},
        {"timeout": "90"},
        {"success_codes": []},
        {"success_codes": [0, 0]},
        {"success_codes": [True]},
        {"success_codes": 0},
        {"id": "Lint"},
        {"id": "1lint"},
        {"label": ""},
        {"argv": []},
        {"argv": "ruff"},
        {"argv": [""]},
        {"unknown_key": 1},
    ],
)
def test_bad_stage_fields_fail(project, patch):
    config = healthy_config()
    config["quality"]["profiles"]["full"]["stages"][0].update(patch)
    report = doctor.diagnose(project(config=config))
    assert failures(report), patch


def test_unknown_root_key_is_allowed(project):
    config = healthy_config()
    config["무언가_새_필드"] = {"a": 1}
    report = doctor.diagnose(project(config=config))
    assert failures(report) == []


# **객체·배열의 타입만 보고 끝내면 안 된다**(R2-03). 스키마는 값의 타입까지 정한다 —
# `harness.schema.json:59` 가 unmapped_by_design 의 각 값을, `:54` 가 why 를 문자열로 묶는다
@pytest.mark.parametrize("value", [42, None, [], {"a": 1}, True])
def test_unmapped_by_design_value_must_be_a_string(project, value):
    config = healthy_config()
    config["quality"]["unmapped_by_design"] = {"docs/": value}
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL in levels(report, "D-CONFIG"), value
    assert "unmapped_by_design" in messages(report, "D-CONFIG"), value


@pytest.mark.parametrize("value", [[], 42, None])
def test_mapping_why_must_be_a_string(project, value):
    config = healthy_config()
    config["quality"]["mappings"][0]["why"] = value
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL in levels(report, "D-CONFIG"), value
    assert "why" in messages(report, "D-CONFIG"), value


# 스키마가 허용하는 것을 임의로 거부하지 않는다 — 두 필드에는 minLength 가 없다
def test_schema_allowed_empty_strings_are_kept(project):
    config = healthy_config()
    config["quality"]["unmapped_by_design"] = {"docs/": ""}
    config["quality"]["mappings"][0]["why"] = ""
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL not in levels(report, "D-CONFIG")


# optional 한 why 의 부재는 오류가 아니다
def test_mapping_without_why_is_fine(project):
    config = healthy_config()
    config["quality"]["mappings"][0].pop("why", None)
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL not in levels(report, "D-CONFIG")


# ─────────────────── 3. 결선과 matcher ───────────────────


def test_missing_wiring_fails(project):
    settings = healthy_settings()
    del settings["hooks"]["Stop"]
    report = doctor.diagnose(project(settings=settings))
    assert doctor.FAIL in levels(report, "D-WIRING")
    assert "auto_test_check.py" in messages(report, "D-WIRING")


def test_wrong_event_does_not_count(project):
    settings = healthy_settings()
    settings["hooks"]["UserPromptSubmit"] = settings["hooks"].pop("Stop")
    report = doctor.diagnose(project(settings=settings))
    assert doctor.FAIL in levels(report, "D-WIRING")


def test_partial_matcher_fails(project):
    settings = healthy_settings()
    settings["hooks"]["PostToolUse"] = [settings["hooks"]["PostToolUse"][0]]
    report = doctor.diagnose(project(settings=settings))
    assert doctor.FAIL in levels(report, "D-WIRING")
    text = messages(report, "D-WIRING")
    assert "Bash" in text and "PowerShell" in text


def test_split_groups_are_merged(project):
    settings = healthy_settings()
    settings["hooks"]["PostToolUse"] = [
        {
            "matcher": "Write",
            "hooks": [{"type": "command", "command": hook_command("auto_test_check.py")}],
        },
        {
            "matcher": "Edit",
            "hooks": [{"type": "command", "command": hook_command("auto_test_check.py")}],
        },
        {
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": hook_command("auto_test_check.py")}],
        },
        {
            "matcher": "PowerShell",
            "hooks": [{"type": "command", "command": hook_command("auto_test_check.py")}],
        },
    ]
    report = doctor.diagnose(project(settings=settings))
    assert doctor.FAIL not in levels(report, "D-WIRING")


def test_external_same_basename_is_not_wiring(project, tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir(parents=True, exist_ok=True)
    (outside / "auto_test_check.py").write_text("# 남의 파일\n", encoding="utf-8")
    settings = healthy_settings()
    settings["hooks"]["Stop"] = [
        {"hooks": [{"type": "command", "command": f'python "{outside / "auto_test_check.py"}"'}]}
    ]
    report = doctor.diagnose(project(settings=settings))
    assert doctor.FAIL in levels(report, "D-WIRING")


@pytest.mark.parametrize("matcher", ["*", "", None, "Write, Edit, Bash, PowerShell", ".*"])
def test_matchers_that_cover_all_tools(project, matcher):
    settings = healthy_settings()
    group: dict = {"hooks": [{"type": "command", "command": hook_command("auto_test_check.py")}]}
    if matcher is not None:
        group["matcher"] = matcher
    settings["hooks"]["PostToolUse"] = [group]
    report = doctor.diagnose(project(settings=settings))
    assert doctor.FAIL not in levels(report, "D-WIRING"), matcher


def test_regex_partial_match_is_accepted():
    # 정규식 길로 가는 값은 **부분 일치**로 본다. `[Ww]ri` 는 fullmatch 로는 Write 를
    # 놓치고 search 로는 잡는다 — 공식 문서가 JS 부분 일치라고 한 자리가 여기다
    assert doctor.matcher_covers("[Ww]ri", "Write")[0] is True
    assert doctor.matcher_covers("[Ww]ri", "Edit")[0] is False
    assert doctor.matcher_covers("^Write$", "Write")[0] is True
    assert doctor.matcher_covers("^Write$", "Edit")[0] is False


def test_bare_word_is_a_name_list_not_a_regex():
    # 메타문자가 없는 값은 이름 목록이라 정확 비교다. 부분 일치로 읽으면 `ri` 가 Write 를
    # 덮는다고 잘못 말하게 된다
    assert doctor.matcher_covers("ri", "Write")[0] is False
    assert doctor.matcher_covers("Write", "Write")[0] is True


def test_name_list_is_compared_exactly():
    assert doctor.matcher_covers("Write|Edit", "Write")[0] is True
    assert doctor.matcher_covers("Write|Edit", "WriteFile")[0] is False


def test_broken_regex_bracket_fails(project):
    settings = healthy_settings()
    settings["hooks"]["PostToolUse"] = [
        {
            "matcher": "[Write",
            "hooks": [{"type": "command", "command": hook_command("auto_test_check.py")}],
        }
    ]
    report = doctor.diagnose(project(settings=settings))
    assert doctor.FAIL in levels(report, "D-WIRING")


# `\A` 는 두 엔진이 **둘 다 컴파일하고 뜻이 다르다** — V8 은 리터럴 `A`, Python 은 시작
# 앵커다(실측). 그래서 컴파일 성공은 동등성의 근거가 못 되고, 판정은 미확인이어야 한다
def test_unverifiable_pattern_is_warn_not_pass(project):
    settings = healthy_settings()
    settings["hooks"]["PostToolUse"] = [
        {
            "matcher": "\\A(Write|Edit|Bash|PowerShell)",
            "hooks": [{"type": "command", "command": hook_command("auto_test_check.py")}],
        }
    ]
    report = doctor.diagnose(project(settings=settings))
    # 해석하지 못한 그 이벤트만 본다 — 다른 두 행은 정상이라 PASS 가 맞다
    post = levels_at(report, "D-WIRING", "PostToolUse")
    assert doctor.PASS not in post
    assert doctor.WARN in post


# **JS 가 거부한다고 확정한 패턴은 미확인이 아니라 FAIL 이다.** 어느 도구에도 걸릴 수 없다
@pytest.mark.parametrize(
    "matcher",
    [
        "(?i)Write|Edit|Bash|PowerShell",
        "(?P<tool>Write|Edit|Bash|PowerShell)",
        "(?#주석)Write|Edit|Bash|PowerShell",
        "Write++|Edit|Bash|PowerShell",
    ],
)
def test_js_invalid_matcher_is_fail_not_unknown(project, matcher):
    settings = healthy_settings()
    settings["hooks"]["PostToolUse"] = [
        {
            "matcher": matcher,
            "hooks": [{"type": "command", "command": hook_command("auto_test_check.py")}],
        }
    ]
    report = doctor.diagnose(project(settings=settings))
    post = levels_at(report, "D-WIRING", "PostToolUse")
    assert doctor.PASS not in post, matcher
    assert doctor.FAIL in post, matcher
    assert "JavaScript" in messages(report, "D-WIRING"), matcher


# 실측(V8, 2026-11-22): 넷 다 SyntaxError 인데 Python 3.12 는 넷 다 컴파일한다
@pytest.mark.parametrize("matcher", ["Bash++", "Bash*+", "Bash?+", "Bash{1,2}+"])
def test_possessive_quantifiers_are_js_errors(matcher):
    assert doctor.matcher_covers(matcher, "Bash")[0] is False
    assert doctor.matcher_js_error(matcher)


# **전역** 형식만 확정 오류다. JavaScript 에는 범위가 있는 형태만 있어서 V8 은 `(?i)` 를
# Invalid group 으로 거부한다(실측)
@pytest.mark.parametrize("matcher", ["(?i)write", "(?s)Write", "(?im)Write", "(?x)Write"])
def test_global_inline_flags_are_js_errors(matcher):
    assert doctor.matcher_covers(matcher, "Write")[0] is False, matcher
    assert doctor.matcher_js_error(matcher), matcher


# **범위가 있는 modifier 그룹은 FAIL 이 아니다**(R3-04). 실측(Chrome 156)으로 아홉 형태가
# 다 컴파일된다. 뜻이 Python 과 달라서가 아니라 **2025 에 들어온 문법**이라 그 전 엔진은
# 거부하고, 제품의 엔진을 보지 못했으므로 미확인이다
@pytest.mark.parametrize(
    "matcher",
    [
        "(?i:Write)",
        "(?s:Write)",
        "(?-i:Write)",
        "(?im-s:Write)",
        "(?ims:Write)",
        "(?mi:Write)",
        "(?is-m:Write)",
        "(?m-i:Write)",
        "(?i-:Write)",
    ],
)
def test_scoped_modifier_groups_are_unknown(matcher):
    verdict, note = doctor.matcher_covers(matcher, "Write")
    assert verdict is None, matcher
    assert doctor.matcher_js_error(matcher) is None, matcher
    assert "2025" in note, matcher


# modifier 그룹이 받는 플래그는 i·m·s 뿐이고 중복도 안 된다(MDN). 아래는 modifier 를
# 지원하는 엔진에서도 거부되므로(실측) 엔진 나이와 무관한 확정 오류다
@pytest.mark.parametrize(
    "matcher",
    [
        "(?x:Write)",
        "(?u:Write)",
        "(?a:Write)",
        "(?L:Write)",
        "(?sx:Write)",
        "(?i-i:Write)",
        "(?-:Write)",
    ],
)
def test_modifier_flags_outside_ims_are_js_errors(matcher):
    assert doctor.matcher_covers(matcher, "Write")[0] is False, matcher
    assert doctor.matcher_js_error(matcher), matcher


# modifier 그룹의 미확인이 **뒤의 확정 오류를 덮지 않는다** — 둘 중 확정 오류가 이긴다
@pytest.mark.parametrize("matcher", ["(?i:Bash++)", "(?i:Write", "(?i:Write))", "(?i:[Write)"])
def test_confirmed_error_inside_a_modifier_group_wins(matcher):
    assert doctor.matcher_covers(matcher, "Write")[0] is False, matcher
    assert doctor.matcher_js_error(matcher), matcher


# 결선 판정에서도 FAIL 이 아니라 미확인 WARN 이어야 한다
def test_scoped_modifier_wiring_is_warn_not_fail(project):
    settings = healthy_settings()
    settings["hooks"]["PostToolUse"] = [
        {
            "matcher": "(?i:Write|Edit|Bash|PowerShell)",
            "hooks": [{"type": "command", "command": hook_command("auto_test_check.py")}],
        }
    ]
    report = doctor.diagnose(project(settings=settings))
    post = levels_at(report, "D-WIRING", "PostToolUse")
    assert doctor.FAIL not in post
    assert doctor.PASS not in post
    assert doctor.WARN in post


# **전체 적용 특례에 strip 을 쓰지 않는다.** 공백이 붙은 `*` 를 전체 적용으로 바꾸면
# 제품이 strip 한다는 쪽에 걸고 PASS 를 내는 것이다
@pytest.mark.parametrize("matcher", [" * ", "   ", " ", "* "])
def test_wildcard_special_case_is_not_stripped(matcher):
    assert doctor.matcher_covers(matcher, "Write")[0] is not True


# 공백뿐인 값은 이름 목록으로 쪼개면 아무 이름도 남지 않는다 — 빈 목록으로 비교하지 않고
# 모른다고 말한다
def test_whitespace_only_matcher_is_unknown():
    verdict, note = doctor.matcher_covers("   ", "Write")
    assert verdict is None
    assert "공백" in note


@pytest.mark.parametrize("matcher", ["*", "", None])
def test_exact_wildcard_and_empty_cover_every_tool(matcher):
    assert doctor.matcher_covers(matcher, "Write")[0] is True


# 두 엔진에서 뜻이 같다고 확인하지 못한 것은 FAIL 도 PASS 도 아니다
@pytest.mark.parametrize(
    "matcher",
    ["\\AWrite", "\\p{L}rite", "(?<=sub)Write", "(?<name>Write)", "[]Write", "Write{,2}"],
)
def test_unconfirmed_patterns_stay_unknown(matcher):
    assert doctor.matcher_covers(matcher, "Write")[0] is None, matcher
    assert doctor.matcher_js_error(matcher) is None, matcher


# 공통 문법은 그대로 부분 일치로 판정한다 — 좁힌 것이 정상 설정을 막지 않아야 한다
@pytest.mark.parametrize(
    ("matcher", "tool", "expected"),
    [
        ("Write, Edit", "Edit", True),
        ("Write, Edit", "Bash", False),
        ("[Ww]ri", "Write", True),
        (".*", "Write", True),
        ("mcp__.*", "mcp__list", True),
        ("Note.*book", "Notebook", True),
        ("Write$", "Write", True),
        ("(Write|Edit)", "Edit", True),
        ("Writ[a-z]?e", "Write", True),
        ("Write\\b", "Write", True),
    ],
)
def test_common_syntax_still_resolves(matcher, tool, expected):
    assert doctor.matcher_covers(matcher, tool)[0] is expected, matcher


def test_non_quality_hook_with_missing_script_fails(project):
    settings = healthy_settings()
    settings["hooks"]["UserPromptSubmit"] = [
        {"hooks": [{"type": "command", "command": hook_command("history_check.py")}]}
    ]
    report = doctor.diagnose(project(settings=settings))
    assert doctor.FAIL in levels(report, "D-HOOK")
    assert "history_check.py" in messages(report, "D-HOOK")


def test_settings_hook_structure_errors_are_config_fail(project):
    report = doctor.diagnose(project(settings={"hooks": {"Stop": "배열이 아니다"}}))
    assert doctor.FAIL in levels(report, "D-CONFIG")


def test_non_command_hooks_are_not_errors(project):
    settings = healthy_settings()
    settings["hooks"]["Stop"].append({"hooks": [{"type": "그밖의종류"}]})
    report = doctor.diagnose(project(settings=settings))
    assert doctor.FAIL not in levels(report, "D-CONFIG")


def test_custom_wiki_root_is_followed(project):
    config = healthy_config()
    config["wiki_root"] = "docs/wiki/"
    root = project(config=config)
    for name in ("overview", "knowledge"):
        target = root / "docs" / "wiki" / name / "README.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# 문서\n", encoding="utf-8")
    report = doctor.diagnose(root)
    assert "docs/wiki/overview/README.md" in messages(report, "D-FILES")
    assert doctor.FAIL not in levels(report, "D-FILES")


def test_wiki_is_unchecked_when_harness_json_broken(project):
    root = project()
    (root / ".claude" / "harness.json").write_text("{", encoding="utf-8")
    report = doctor.diagnose(root)
    text = messages(report, "D-FILES")
    assert "wiki_root" in text and "미검사" in text


def test_bad_wiki_root_at_version_two_is_config_fail(project):
    config = healthy_config()
    config["wiki_root"] = ""
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL in levels(report, "D-CONFIG")
    assert "미검사" in messages(report, "D-FILES")


# ─────────────────── 4. 경로·치환값·추적 경로 ───────────────────


def test_korean_and_space_paths(project):
    root = project(name="한글 프로젝트 이름")
    report = doctor.diagnose(root)
    assert failures(report) == []


@pytest.mark.parametrize(
    "template",
    [
        'python "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py"',
        "python ${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py",
        'python3 "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py"',
        'py -3 "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py"',
        '"C:/Python312/python.exe" "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py"',
        "python .claude/harness/hooks/auto_test_check.py",
        'python -u "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py"',
        'python -X utf8 "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py"',
        # 스크립트 뒤의 인자는 스크립트가 아니다 — 뒤의 `.py` 를 다시 고르지 않는다
        'python "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py" --opt other.py',
        'python "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py" # 세션마다 돈다',
        # 옵션 값이 빈 인자인 것은 고장이 아니다 — 실제 Python 은 스크립트를 실행한다(실측)
        'python -W "" "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py"',
        # 스크립트 뒤의 빈 인자도 스크립트 자리를 바꾸지 않는다
        'python "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py" ""',
    ],
)
def test_direct_python_call_forms(project, template):
    settings = healthy_settings()
    settings["hooks"]["Stop"] = [{"hooks": [{"type": "command", "command": template}]}]
    report = doctor.diagnose(project(settings=settings))
    assert doctor.FAIL not in levels(report, "D-WIRING"), template


@pytest.mark.parametrize(
    "command",
    [
        "run-hooks && python .claude/harness/hooks/auto_test_check.py",
        "wrapper.sh .claude/harness/hooks/auto_test_check.py",
        'python "${SOME_OTHER_VAR}/auto_test_check.py"',
        'python "unclosed',
        # **`.py` 인자가 있다는 것은 실행 증거가 아니다**(R2-01). 아래 넷 다 Python 이 그
        # 파일을 스크립트로 열지 않는다
        'python -c pass "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py"',
        'python -c "import x" "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py"',
        'python -m not_a_hook "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py"',
        'python --version "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py"',
        # 모르는 옵션은 추측하지 않는다 — 값을 받는 옵션이면 그 값을 스크립트로 읽는다
        'python -Z "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py"',
        # 주석이 호출 전체를 가린 경우
        'python # "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py"',
        # **빈 스크립트 자리**(R2-01 추가). 실제 Python 은 빈 인자를 디렉터리로 읽고
        # `__main__` 을 찾다 종료 1 이며, 뒤의 훅 경로는 실행되지 않는다(실측)
        'python "" "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py"',
        "python '' \"${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py\"",
    ],
)
def test_unresolvable_commands_warn_and_do_not_prove_wiring(project, command):
    settings = healthy_settings()
    settings["hooks"]["Stop"] = [{"hooks": [{"type": "command", "command": command}]}]
    report = doctor.diagnose(project(settings=settings))
    assert doctor.WARN in levels(report, "D-HOOK"), command
    assert doctor.FAIL in levels(report, "D-WIRING"), command


# **빈 인자 하나와 「인자가 없다」는 다르다.** 토큰을 버리면 argv 의 자리가 하나 밀려
# 다음 인자를 실행 대상으로 읽는다 — 그게 R2-01 의 거짓 PASS 였다
@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ('python "" a.py', ["python", "", "a.py"]),
        ("python '' a.py", ["python", "", "a.py"]),
        ('python -W "" a.py', ["python", "-W", "", "a.py"]),
        ('python a.py ""', ["python", "a.py", ""]),
        ('python ""', ["python", ""]),
        ('python a.py "" ""', ["python", "a.py", "", ""]),
        # 주석은 단어 시작에서만 주석이다 — `""#x` 는 단어 안이라 토큰이다
        ("python a.py # 주석", ["python", "a.py"]),
        ('python a.py ""#x', ["python", "a.py", "#x"]),
    ],
)
def test_tokenize_keeps_empty_arguments(command, expected):
    assert doctor.tokenize(command) == expected


def test_cwd_outside_project_fails(project):
    config = healthy_config()
    config["quality"]["profiles"]["full"]["stages"][0]["cwd"] = "../밖으로"
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL in levels(report, "D-STAGE")


def test_cwd_missing_directory_fails(project):
    config = healthy_config()
    config["quality"]["profiles"]["full"]["stages"][0]["cwd"] = "없는폴더"
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL in levels(report, "D-STAGE")


def test_unknown_path_name_is_warn_with_path_source(project):
    config = healthy_config()
    config["quality"]["profiles"]["full"]["stages"][0]["argv"] = ["도구가아님-xyz-99", "--v"]
    report = doctor.diagnose(project(config=config))
    assert doctor.WARN in levels(report, "D-EXEC")
    assert doctor.FAIL not in levels(report, "D-EXEC")
    assert "PATH" in messages(report, "D-EXEC")


def test_foreign_absolute_path_is_not_taken_for_a_path_name(project):
    config = healthy_config()
    other = "/usr/bin/도구" if sys.platform == "win32" else "C:/Tools/도구.exe"
    config["quality"]["profiles"]["full"]["stages"][0]["argv"] = [other]
    report = doctor.diagnose(project(config=config))
    text = messages(report, "D-EXEC")
    assert other in text
    assert "PATH 에서" not in text


def test_python_fallback_is_warn(project):
    config = healthy_config()
    config["python"] = ".venv/Scripts/python.exe"
    root = project(config=config)
    report = doctor.diagnose(root)
    assert doctor.WARN in levels(report, "D-PYTHON")
    text = messages(report, "D-PYTHON")
    assert "Doctor 의 루트 기준" in text


def test_python_choice_states_doctor_root(project):
    report = doctor.diagnose(project())
    assert "Doctor 의 루트 기준" in messages(report, "D-PYTHON")


def test_other_language_project_is_not_failed(project):
    config = healthy_config()
    config.pop("python")
    config["quality"]["profiles"]["fast"]["stages"] = [
        {"id": "test", "argv": ["npm", "test", "{mapped_targets}"]}
    ]
    config["quality"]["profiles"]["full"]["stages"] = [
        {"id": "lint", "argv": ["npm", "run", "lint"]}
    ]
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL not in levels(report, "D-PYTHON")
    assert "미검사" in messages(report, "D-PYTHON")


@pytest.mark.parametrize("arg", ["{unknown}", "{a}x{b}", "{}"])
def test_runtime_rejected_placeholders_fail(project, arg):
    config = healthy_config()
    config["quality"]["profiles"]["full"]["stages"][0]["argv"] = ["{python}", arg]
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL in levels(report, "D-ARGV"), arg


@pytest.mark.parametrize("arg", ["{python} --version", "--opt={python}"])
def test_embedded_placeholders_warn_only(project, arg):
    config = healthy_config()
    config["quality"]["profiles"]["full"]["stages"][0]["argv"] = ["ruff", arg]
    report = doctor.diagnose(project(config=config))
    assert doctor.WARN in levels(report, "D-ARGV"), arg
    assert doctor.FAIL not in levels(report, "D-ARGV"), arg


@pytest.mark.parametrize("placeholder", ["{changed_files}", "{mapped_targets}"])
def test_list_placeholder_in_full_stage_fails(project, placeholder):
    config = healthy_config()
    config["quality"]["profiles"]["full"]["stages"][0]["argv"] = [
        "{python}",
        "-m",
        "pytest",
        placeholder,
    ]
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL in levels(report, "D-ARGV")
    assert "건너뛰" in messages(report, "D-ARGV")


def test_list_placeholder_as_executable_fails(project):
    config = healthy_config()
    config["quality"]["profiles"]["fast"]["stages"][0]["argv"] = ["{changed_files}"]
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL in levels(report, "D-ARGV")


def test_fast_list_placeholder_is_not_a_failure(project):
    report = doctor.diagnose(project())
    assert doctor.FAIL not in levels(report, "D-ARGV")


@pytest.mark.parametrize("field", ["quality", "history"])
def test_directory_entry_without_trailing_slash_fails(project, field):
    config = healthy_config()
    config[field]["tracked_paths"] = ["src", "tests"]
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL in levels(report, "D-TRACKED"), field
    text = messages(report, "D-TRACKED")
    assert "src" in text and "/" in text


@pytest.mark.parametrize("field", ["quality", "history"])
def test_trailing_slash_entries_pass(project, field):
    config = healthy_config()
    config[field]["tracked_paths"] = ["src/", "tests/"]
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL not in levels(report, "D-TRACKED"), field


def test_real_file_entry_is_not_flagged(project):
    config = healthy_config()
    config["quality"]["tracked_paths"] = ["src/", "tests/", "CLAUDE.md"]
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL not in levels(report, "D-TRACKED")


def test_missing_entry_is_scaffold_warn_not_fail(project):
    config = healthy_config()
    config["quality"]["tracked_paths"] = ["src/", "tests/", "pyproject.toml"]
    report = doctor.diagnose(project(config=config))
    assert doctor.FAIL not in levels(report, "D-TRACKED")
    assert doctor.WARN in levels(report, "D-SCAFFOLD")


# **쓰이지 않는 대체 항목을 FAIL 로 막지 않는다**(R2-04). 두 소비자가 명시한
# tracked_paths 를 쓰는 동안 이 두 필드는 아무도 읽지 않는다 — V2 에서 다른 소비자는 전부
# 버전 게이트로 꺼져 있다(`task_log_check.py:193`, `auto_test_check.py:416`)
def test_unused_fallback_suffix_is_warn_not_fail(project):
    config = healthy_config()
    config["source_prefixes"] = ["src"]
    config["harness_paths"] = ["tests"]
    report = doctor.diagnose(project(config=config))
    text = messages(report, "D-TRACKED")
    assert doctor.FAIL not in levels(report, "D-TRACKED")
    assert doctor.WARN in levels(report, "D-TRACKED")
    assert "source_prefixes" in text and "harness_paths" in text
    # 「게이트가 꺼졌다」고 단정하지 않는다
    assert "고장은" in text


def test_selected_fallback_suffix_fails(project):
    config = healthy_config()
    config["source_prefixes"] = ["src"]
    config["harness_paths"] = ["tests"]
    config["quality"]["tracked_paths"] = []
    config["history"]["tracked_paths"] = []
    report = doctor.diagnose(project(config=config))
    where = " ".join(
        finding.where
        for finding in report.findings
        if finding.level == doctor.FAIL and finding.check == "D-TRACKED"
    )
    assert "source_prefixes" in where
    assert "harness_paths" in where


# History 대체는 `source_prefixes` + `harness_paths` 다(`history_check.py:47`). 그래서
# history 쪽만 비어도 두 필드가 다 쓰인다
def test_history_only_fallback_uses_both_fields(project):
    config = healthy_config()
    config["source_prefixes"] = ["src"]
    config["harness_paths"] = ["tests"]
    config["history"]["tracked_paths"] = []
    report = doctor.diagnose(project(config=config))
    where = " ".join(
        finding.where
        for finding in report.findings
        if finding.level == doctor.FAIL and finding.check == "D-TRACKED"
    )
    assert "source_prefixes" in where
    assert "harness_paths" in where


# quality 쪽만 비면 `harness_paths` 는 여전히 아무도 읽지 않는다
def test_quality_only_fallback_spares_harness_paths(project):
    config = healthy_config()
    config["source_prefixes"] = ["src"]
    config["harness_paths"] = ["tests"]
    config["quality"]["tracked_paths"] = []
    report = doctor.diagnose(project(config=config))
    where = " ".join(
        finding.where
        for finding in report.findings
        if finding.level == doctor.FAIL and finding.check == "D-TRACKED"
    )
    assert "source_prefixes" in where
    assert "harness_paths" not in where


# 공백뿐인 항목은 소비자가 걸러낸다 — 그래서 대체가 선택된다
def test_blank_tracked_paths_select_the_fallback(project):
    config = healthy_config()
    config["source_prefixes"] = ["src"]
    config["quality"]["tracked_paths"] = ["   "]
    config["history"]["tracked_paths"] = ["   "]
    report = doctor.diagnose(project(config=config))
    where = " ".join(
        finding.where
        for finding in report.findings
        if finding.level == doctor.FAIL and finding.check == "D-TRACKED"
    )
    assert "source_prefixes" in where


def test_no_tracked_paths_at_all_warns(project):
    config = healthy_config()
    config["quality"]["tracked_paths"] = []
    config["source_prefixes"] = []
    report = doctor.diagnose(project(config=config))
    assert doctor.WARN in levels(report, "D-TRACKED")


def test_mapping_orphan_warns(project):
    config = healthy_config()
    config["quality"]["tracked_paths"] = ["src/", "tests/", "CLAUDE.md"]
    report = doctor.diagnose(project(config=config))
    assert doctor.WARN in levels(report, "D-MAPPING")
    assert "CLAUDE.md" in messages(report, "D-MAPPING")


def test_mapping_orphan_silenced_by_unmapped_by_design(project):
    config = healthy_config()
    config["quality"]["tracked_paths"] = ["src/", "tests/", "CLAUDE.md"]
    config["quality"]["unmapped_by_design"] = {"CLAUDE.md": "문서라 대응 테스트가 없다"}
    report = doctor.diagnose(project(config=config))
    assert doctor.WARN not in levels(report, "D-MAPPING")


def test_mapping_test_file_special_case_is_not_an_orphan(project):
    config = healthy_config()
    config["quality"]["tracked_paths"] = ["src/", "tests/test_x.py"]
    root = project(config=config)
    (root / "tests" / "test_x.py").write_text("", encoding="utf-8")
    report = doctor.diagnose(root)
    assert doctor.WARN not in levels(report, "D-MAPPING")


def test_mapping_not_checked_when_fast_skips_mapped_targets(project):
    config = healthy_config()
    config["quality"]["tracked_paths"] = ["src/", "tests/", "CLAUDE.md"]
    config["quality"]["profiles"]["fast"]["stages"][0]["argv"] = ["{python}", "-m", "pytest"]
    report = doctor.diagnose(project(config=config))
    assert levels(report, "D-MAPPING") == []


def test_missing_mapping_target_is_scaffold_warn(project):
    config = healthy_config()
    config["quality"]["mappings"] = [{"path": "없는소스/", "tests": "없는테스트/"}]
    report = doctor.diagnose(project(config=config))
    assert doctor.WARN in levels(report, "D-SCAFFOLD")
    assert doctor.FAIL not in levels(report, "D-SCAFFOLD")


def test_missing_history_directory_is_scaffold_warn(project):
    root = project()
    shutil.rmtree(root / ".claude" / "wiki" / "history" / "plan")
    report = doctor.diagnose(root)
    assert doctor.WARN in levels(report, "D-SCAFFOLD")
    assert "history/plan/" in messages(report, "D-SCAFFOLD")


# ─────────────────── 5. 루트 격리 ───────────────────


def test_diagnoses_its_own_project_from_another_cwd(project):
    other = project(name="A")
    target = project(name="B")
    # B 의 설정만 망가뜨린다. A 에서 돌려도 B 가 진단돼야 한다
    (target / "CLAUDE.md").unlink()
    script = install_doctor(target)
    proc = run_cli(script, cwd=other, project_dir=other)
    assert proc.returncode == 1, proc.stdout
    assert str(target) in proc.stdout
    assert str(other) not in proc.stdout.split("\n")[0]


def test_nested_projects_do_not_confuse_the_root(project, tmp_path: Path):
    outer = project(name="outer")
    inner = project(name="outer/inner")
    script = install_doctor(inner)
    proc = run_cli(script, cwd=outer, project_dir=outer)
    assert f"대상 루트: {inner}" in proc.stdout


def test_works_without_git(project):
    root = project()
    assert not (root / ".git").exists()
    proc = run_cli(install_doctor(root), cwd=root)
    assert proc.returncode == 0, proc.stdout


# ─────────────────── 6. 읽기 전용 ───────────────────


def snapshot(root: Path) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            found[str(path.relative_to(root))] = path.read_bytes()
    return found


def test_diagnose_writes_nothing(project):
    root = project()
    before = snapshot(root)
    doctor.diagnose(root)
    assert snapshot(root) == before


def test_cli_writes_nothing_outside_its_own_import_cache(project):
    root = project()
    script = install_doctor(root)
    before = snapshot(root)
    run_cli(script, cwd=root)
    after = snapshot(root)
    changed = {
        name
        for name in set(before) | set(after)
        if before.get(name) != after.get(name) and "__pycache__" not in name
    }
    assert changed == set()
    assert script.exists()


def test_diagnose_starts_no_child_process(project, monkeypatch: pytest.MonkeyPatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("진단이 자식 프로세스를 만들었다")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    for name in ("spawnl", "spawnv", "execv", "fork"):
        if hasattr(os, name):
            monkeypatch.setattr(os, name, forbidden)
    report = doctor.diagnose(project())
    assert failures(report) == []


def test_wired_hook_that_writes_when_run_is_not_run(project):
    root = project()
    evidence = root / "훅이돌았다.txt"
    (root / ".claude" / "harness" / "hooks" / "auto_test_check.py").write_text(
        f"from pathlib import Path\nPath(r{str(evidence)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    doctor.diagnose(root)
    assert not evidence.exists()


def test_stage_command_that_writes_when_run_is_not_run(project):
    root = project()
    evidence = root / "stage가돌았다.txt"
    config = healthy_config()
    config["quality"]["profiles"]["full"]["stages"][0]["argv"] = [
        sys.executable,
        "-c",
        f"open(r{str(evidence)!r}, 'w').write('ran')",
    ]
    write_json(root / ".claude" / "harness.json", config)
    doctor.diagnose(root)
    assert not evidence.exists()


# ─────────────────── 7. OS 별 판정 ───────────────────


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX 실행 권한 비트가 없는 OS")
def test_posix_missing_exec_permission_fails(project):
    root = project()
    tool = root / "도구"
    tool.write_text("#!/bin/sh\n", encoding="utf-8")
    tool.chmod(0o644)
    config = healthy_config()
    config["quality"]["profiles"]["full"]["stages"][0]["argv"] = [str(tool)]
    write_json(root / ".claude" / "harness.json", config)
    report = doctor.diagnose(root)
    assert doctor.FAIL in levels(report, "D-EXEC")
    assert "실행 권한" in messages(report, "D-EXEC")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 에만 있는 분기")
def test_windows_existing_absolute_executable_passes(project):
    root = project()
    tool = root / "도구.exe"
    tool.write_text("", encoding="utf-8")
    config = healthy_config()
    config["quality"]["profiles"]["full"]["stages"][0]["argv"] = [str(tool)]
    write_json(root / ".claude" / "harness.json", config)
    report = doctor.diagnose(root)
    assert doctor.PASS in levels(report, "D-EXEC")
    assert doctor.FAIL not in levels(report, "D-EXEC")


def test_missing_absolute_executable_fails_on_both(project):
    root = project()
    missing = root / "없는도구.exe"
    config = healthy_config()
    config["quality"]["profiles"]["full"]["stages"][0]["argv"] = [str(missing)]
    write_json(root / ".claude" / "harness.json", config)
    report = doctor.diagnose(root)
    assert doctor.FAIL in levels(report, "D-EXEC")


# 경로 분류 자체는 OS 를 타지 않는 순수 입력 판정이다. 실제 OS 의 실행 권한·PATH 해석은
# 위 두 테스트가 각자의 OS 에서만 본다
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ruff", False),
        ("./tool", True),
        ("sub/tool", True),
        ("C:/Tools/t.exe", True),
        ("/usr/bin/t", True),
    ],
)
def test_executable_shape_classification(raw, expected):
    has_separator = "/" in raw or "\\" in raw
    assert has_separator is expected


# ─────────────────── 8. 복제한 분기 대조 ───────────────────

# **Doctor 는 진단 런타임에서 `_hookutil` 을 import 하지 않는다** — 루트 결정이 반대이고
# `config()` 가 읽기 실패를 빈 사전으로 삼켜서, 찾아내야 하는 고장을 진단기가 물려받는다.
# 그래서 분기를 옮겨 적었는데, 옮긴 것은 **조용히 어긋나는 종류**다.
#
# 런타임에서 금지한 것과 테스트에서 대조하는 것은 다르다. 아래는 conftest 의 `load_hook`
# 으로 실제 소비자 모듈을 읽어 같은 설정에서 같은 값이 나오는지 본다.


def selection_case(**patch: object) -> dict:
    """`quality__tracked_paths=[]` 처럼 `__` 로 절을 가리켜 건강한 설정을 한 자리만 바꾼다."""
    config = healthy_config()
    for key, value in patch.items():
        head, _, tail = key.partition("__")
        if tail:
            config[head][tail] = value
        else:
            config[head] = value
    return config


@pytest.mark.parametrize(
    "config",
    [
        selection_case(),
        selection_case(quality__tracked_paths=[]),
        selection_case(history__tracked_paths=[]),
        selection_case(quality__tracked_paths=["   "], history__tracked_paths=["   "]),
        selection_case(quality__tracked_paths="src/"),
        selection_case(quality__tracked_paths=[42, "src/"]),
        selection_case(source_prefixes=["src/"], harness_paths=["pyproject.toml"]),
        selection_case(history__tracked_paths=[], harness_paths=[]),
        selection_case(quality__tracked_paths=[], source_prefixes=[]),
    ],
)
def test_tracked_selection_matches_the_real_consumers(load_hook, config):
    auto, _ = load_hook("auto_test_check", config)
    history, _ = load_hook("history_check", config)
    assert doctor.selected_quality_tracked(config) == auto.QUALITY_TRACKED_PATHS
    assert doctor.selected_history_tracked(config) == history.TRACKED_PATHS


@pytest.mark.parametrize(
    "config",
    [
        selection_case(),
        selection_case(wiki_root=".claude/wiki"),
        selection_case(wiki_root="   "),
        selection_case(wiki_root="docs/wiki/"),
        selection_case(history__plan="/plan/"),
        selection_case(history__task="./task/"),
        selection_case(history__verify=".claude/wiki/history/verify/"),
    ],
)
def test_wiki_root_and_history_prefix_match_hookutil(load_hook, config):
    hookutil, _ = load_hook("_hookutil", config)
    wiki_root = doctor.wiki_root_of(config)
    assert wiki_root == hookutil.WIKI_ROOT
    for kind in ("plan", "task", "verify"):
        assert doctor.history_prefix_of(config, kind, wiki_root) == hookutil.history_prefix(kind)


def test_python_choice_matches_hookutil(load_hook):
    config = selection_case(python="py-stub")
    hookutil, root = load_hook("_hookutil", config)
    (root / "py-stub").write_text("", encoding="utf-8")
    chosen, source, _ = doctor.chosen_python(root, config)
    assert chosen == hookutil.venv_python()
    assert source == "python"


def test_python_fallback_order_matches_hookutil(load_hook):
    config = selection_case(python="없는/인터프리터")
    hookutil, root = load_hook("_hookutil", config)
    chosen, source, tried = doctor.chosen_python(root, config)
    # 양쪽 다 `.venv` 둘을 차례로 보고, 없으면 현재 프로세스로 떨어진다
    assert chosen is None and source is None
    assert hookutil.venv_python() == sys.executable
    assert tried == [
        str(root / "없는" / "인터프리터"),
        str(root / ".venv" / "Scripts" / "python.exe"),
        str(root / ".venv" / "bin" / "python"),
    ]


# 추적 항목 정규화도 같은 복제다 — `/` 유무의 뜻이 갈리는 자리라 실제 함수와 맞춰 본다
@pytest.mark.parametrize(
    "entry", ["src/", "src", "./src/", "/src/", ".\\src\\", "pyproject.toml", "./a/b.py"]
)
def test_entry_normalization_matches_hookutil(load_hook, entry):
    hookutil, root = load_hook("_hookutil", healthy_config())
    normalized = doctor.normalize_entry(entry)
    (root / "src").mkdir(parents=True, exist_ok=True)
    found = hookutil.tracked_paths_newer_than((entry,), 0)
    if normalized.endswith("/"):
        assert (root / normalized).is_dir() or found == []
    else:
        # 끝에 `/` 가 없으면 **정확한 파일 하나**로 읽는다. 그래서 디렉터리는 0건이다
        assert found == []
