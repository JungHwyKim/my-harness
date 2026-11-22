"""수동 Quality CLI 가 **무엇을 실행하고 무엇을 거절하는지** 검사한다.

훅과 같은 엔진을 쓰는지만 보는 것이 아니다. 이 CLI 가 닫으려는 빈틈은 「돌릴 것이 없었다」가
「검사가 통과했다」로 보고되는 자리라, 아래 단정의 절반은 **성공으로 포장하지 않는가**를 묻는다.

**실제 프로세스로 돌린다.** 종료 코드가 이 CLI 의 계약이고, in-process 호출로는 그것을
재지 못한다. 그래서 임시 프로젝트에 실제 모듈을 복사해 배치까지 같은 모양으로 만든다 —
루트를 `__file__` 로 세는 CLI 라 배치가 틀리면 아무것도 성립하지 않는다.

stage 명령은 `sys.executable -c` 다. pytest·ruff 를 쓰지 않는 이유는 이 파일이 재는 것이
도구의 결과가 아니라 **엔진과 CLI 의 판정**이기 때문이다.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_HOOKS = REPO_ROOT / ".claude" / "harness" / "hooks"
REAL_SCRIPTS = REPO_ROOT / ".claude" / "harness" / "scripts"

# CLI 가 실제로 기대는 것들. `doctor.py` 는 배치 검증(`resolve_root`)을 빌려 쓰므로 함께 간다
HOOK_MODULES = ("_hookutil.py", "_quality.py", "auto_test_check.py")
SCRIPT_MODULES = ("doctor.py", "run_quality.py")


def stage(stage_id: str, code: str, **extra) -> dict:
    return {"id": stage_id, "argv": [sys.executable, "-c", code], **extra}


def ok_stage(stage_id: str = "ok") -> dict:
    return stage(stage_id, "pass")


def cli_config(**patch) -> dict:
    config = {
        "schema_version": 2,
        "wiki_root": ".claude/wiki/",
        "history": {
            "plan": "history/plan/",
            "task": "history/task/",
            "verify": "history/verify/",
            "tracked_paths": ["src/"],
        },
        "quality": {
            "tracked_paths": ["src/", "docs/", ".claude/settings.json"],
            "mappings": [{"path": "src/", "tests": "tests/"}],
            "unmapped_by_design": {"docs/": "문서에는 대응하는 테스트가 없다"},
            "profiles": {
                "fast": {
                    "triggers": ["post_change"],
                    "stages": [
                        {
                            "id": "test",
                            "argv": [
                                sys.executable,
                                "-c",
                                "import sys; print('대상:', sys.argv[1:])",
                                "{mapped_targets}",
                            ],
                        }
                    ],
                },
                "full": {
                    "triggers": ["stop"],
                    "stages": [ok_stage("lint"), ok_stage("format"), ok_stage("test")],
                },
            },
        },
    }
    for key, value in patch.items():
        config["quality"]["profiles"][key] = value
    return config


@pytest.fixture
def cli_project(tmp_path: Path):
    def build(config: dict | str) -> Path:
        root = tmp_path / "proj"
        hooks = root / ".claude" / "harness" / "hooks"
        scripts = root / ".claude" / "harness" / "scripts"
        hooks.mkdir(parents=True, exist_ok=True)
        scripts.mkdir(parents=True, exist_ok=True)
        for module in HOOK_MODULES:
            shutil.copy2(REAL_HOOKS / module, hooks / module)
        for module in SCRIPT_MODULES:
            shutil.copy2(REAL_SCRIPTS / module, scripts / module)
        for folder in ("src", "tests", "docs"):
            (root / folder).mkdir(parents=True, exist_ok=True)
            (root / folder / "keep.txt").write_text("", encoding="utf-8")

        target = root / ".claude" / "harness.json"
        if isinstance(config, str):
            target.write_text(config, encoding="utf-8")
        else:
            target.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        return root

    return build


def plugin_data(root: Path) -> Path:
    return root.parent / "_cli_plugin_data"


def run_cli(
    root: Path,
    *args: str,
    cwd: Path | None = None,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDE_PLUGIN_DATA"] = str(plugin_data(root))
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [
            sys.executable,
            str(root / ".claude" / "harness" / "scripts" / "run_quality.py"),
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd or root),
        env=env,
        stdin=subprocess.DEVNULL,
        check=False,
    )


# ───────────────────────── 돌아간다 ─────────────────────────


def test_full_profile_passes(cli_project):
    proc = run_cli(cli_project(cli_config()), "--profile", "full")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "판정: PASS" in proc.stdout
    assert "NOT RUN 0" in proc.stdout


def test_chosen_interpreter_is_reported(cli_project):
    proc = run_cli(cli_project(cli_config()), "--profile", "full")

    assert "인터프리터:" in proc.stdout


def test_fast_runs_the_mapped_target(cli_project):
    proc = run_cli(cli_project(cli_config()), "--profile", "fast", "--changed", "src/app.py")

    assert proc.returncode == 0, proc.stdout
    assert "[대상] src/app.py → tests/" in proc.stdout
    assert "대상: ['tests/']" in proc.stdout
    assert "판정: PASS" in proc.stdout


def test_repeated_changed_is_deduplicated(cli_project):
    proc = run_cli(
        cli_project(cli_config()),
        "--profile",
        "fast",
        "--changed",
        "src/a.py",
        "--changed",
        "src/b.py",
    )

    # 두 파일이 같은 대상으로 가면 pytest 에 한 번만 넘긴다
    assert "대상: ['tests/']" in proc.stdout
    assert proc.returncode == 0


# ───────────────────────── 실패를 숨기지 않는다 ─────────────────────────


def test_failure_marks_the_later_stages_not_run(cli_project):
    config = cli_config(
        full={
            "triggers": ["stop"],
            "stages": [
                ok_stage("lint"),
                stage("format", "raise SystemExit(3)"),
                ok_stage("test"),
            ],
        }
    )
    proc = run_cli(cli_project(config), "--profile", "full")

    assert proc.returncode == 1, proc.stdout
    assert "[FAIL] format" in proc.stdout
    assert "[NOT RUN] test" in proc.stdout
    assert "앞 단계가 실패해 도달하지 않았습니다" in proc.stdout
    assert "판정: FAIL" in proc.stdout


# 종료 코드 5는 **돌았지만 수집이 0건**이다. 「테스트가 실패했다」로 읽히면 고칠 곳을
# 잘못 가리킨다 — 작성 중인 빈 `test_*.py` 가 흔한 원인이다
def test_exit_five_says_no_tests_were_collected(cli_project):
    config = cli_config(
        full={"triggers": ["stop"], "stages": [stage("test", "raise SystemExit(5)")]}
    )
    proc = run_cli(cli_project(config), "--profile", "full")

    assert proc.returncode == 1
    assert "수집된 테스트 없음" in proc.stdout


# ───────────────────────── 사용 오류 ─────────────────────────


@pytest.mark.parametrize(
    "args",
    [
        ("--profile", "fast"),
        ("--profile", "full", "--changed", "src/app.py"),
        ("--profile", "fast", "--changed", "/etc/passwd"),
        ("--profile", "fast", "--changed", "../바깥.py"),
        ("--profile", "fast", "--changed", "src"),
        ("--profile", "fast", "--changed", "src/"),
        ("--profile", "fast", "--changed", ""),
    ],
)
def test_usage_errors_exit_two(cli_project, args):
    proc = run_cli(cli_project(cli_config()), *args)

    assert proc.returncode == 2, proc.stdout
    assert "[ERROR]" in proc.stdout


def test_windows_absolute_path_is_rejected(cli_project):
    proc = run_cli(
        cli_project(cli_config()), "--profile", "fast", "--changed", "C:/proj/src/app.py"
    )

    assert proc.returncode == 2
    assert "상대 경로" in proc.stdout


# ───────────────────────── 설정 결함 ─────────────────────────


def test_missing_config_is_an_error(cli_project):
    root = cli_project(cli_config())
    (root / ".claude" / "harness.json").unlink()

    proc = run_cli(root, "--profile", "full")

    assert proc.returncode == 2
    assert "설정이 없습니다" in proc.stdout


def test_corrupt_config_is_an_error(cli_project):
    proc = run_cli(cli_project("{ 이건 JSON 이 아니다"), "--profile", "full")

    assert proc.returncode == 2
    assert "읽지 못했습니다" in proc.stdout


def test_v1_config_is_unsupported(cli_project):
    config = cli_config()
    config.pop("schema_version")

    proc = run_cli(cli_project(config), "--profile", "full")

    assert proc.returncode == 2
    assert "schema_version" in proc.stdout


def test_absent_profile_is_an_error(cli_project):
    config = cli_config()
    config["quality"]["profiles"].pop("full")

    proc = run_cli(cli_project(config), "--profile", "full")

    assert proc.returncode == 2
    assert "실행할 stage 가 없습니다" in proc.stdout


def test_empty_stages_is_an_error(cli_project):
    proc = run_cli(
        cli_project(cli_config(full={"triggers": ["stop"], "stages": []})), "--profile", "full"
    )

    assert proc.returncode == 2
    assert "실행할 stage 가 없습니다" in proc.stdout


def test_broken_stage_shape_is_an_error(cli_project):
    config = cli_config(full={"triggers": ["stop"], "stages": [{"id": "test", "argv": []}]})

    proc = run_cli(cli_project(config), "--profile", "full")

    assert proc.returncode == 2


# full 이 목록 치환값을 쓰면 그 stage 는 절대 돌 수 없다. 돌려서 SKIP 으로 통과시키는
# 대신 실행 전에 거절한다 — Doctor 의 D-ARGV 가 같은 조합을 FAIL 로 보는 것과 짝이다
def test_full_with_a_list_placeholder_is_an_error(cli_project):
    config = cli_config(
        full={
            "triggers": ["stop"],
            "stages": [{"id": "test", "argv": [sys.executable, "-c", "pass", "{mapped_targets}"]}],
        }
    )
    proc = run_cli(cli_project(config), "--profile", "full")

    assert proc.returncode == 2
    assert "치환값이 비어" in proc.stdout


# ───────────────────────── SKIP 과 매핑 누락 ─────────────────────────


# **「돌릴 것이 없었다」를 「통과」라고 쓰지 않는다.** 이 저장소가 막으려는 실패가 그것이다
def test_everything_excluded_is_skip_and_says_so(cli_project):
    proc = run_cli(cli_project(cli_config()), "--profile", "fast", "--changed", "docs/안내.md")

    assert proc.returncode == 0, proc.stdout
    assert "[SKIP] docs/안내.md — 문서에는 대응하는 테스트가 없다" in proc.stdout
    assert "검사가 통과했다는 뜻이 아닙니다" in proc.stdout
    assert "판정: PASS" not in proc.stdout


def test_untracked_file_is_skipped_with_its_reason(cli_project):
    proc = run_cli(cli_project(cli_config()), "--profile", "fast", "--changed", "기타/메모.md")

    assert proc.returncode == 0
    assert "quality.tracked_paths 밖입니다" in proc.stdout


def test_artifact_is_skipped_as_an_artifact(cli_project):
    proc = run_cli(
        cli_project(cli_config()), "--profile", "fast", "--changed", "src/__pycache__/a.pyc"
    )

    assert proc.returncode == 0
    assert "산물" in proc.stdout


def test_tracked_file_without_a_mapping_is_an_error(cli_project):
    proc = run_cli(
        cli_project(cli_config()), "--profile", "fast", "--changed", ".claude/settings.json"
    )

    assert proc.returncode == 2, proc.stdout
    assert "유효한 매핑도 사유 있는 제외도 없습니다" in proc.stdout


# 혼합 입력도 **실행 전에** 멈춘다. 유효한 대상이 있다고 결함을 덮지 않는다
def test_a_mixed_input_fails_before_running(cli_project):
    proc = run_cli(
        cli_project(cli_config()),
        "--profile",
        "fast",
        "--changed",
        "src/app.py",
        "--changed",
        ".claude/settings.json",
    )

    assert proc.returncode == 2
    assert "대상: " not in proc.stdout, "실행 전에 멈춰야 한다"


# 매핑을 요구하지 않는 Profile 에서는 매핑이 없는 것이 결함이 아니다
def test_a_profile_without_target_placeholders_does_not_demand_mappings(cli_project):
    config = cli_config(
        fast={
            "triggers": ["post_change"],
            "stages": [
                {
                    "id": "test",
                    "argv": [sys.executable, "-c", "import sys; print(sys.argv[1:])"],
                }
            ],
        }
    )
    proc = run_cli(cli_project(config), "--profile", "fast", "--changed", ".claude/settings.json")

    assert proc.returncode == 0, proc.stdout
    assert "판정: PASS" in proc.stdout


# ───────────────────────── 경계 ─────────────────────────


# 잘못된 환경변수와 외부 cwd 에서도 **자기** 프로젝트를 검사해야 한다
def test_the_cli_targets_its_own_root(cli_project, tmp_path):
    root = cli_project(cli_config())
    outside = tmp_path / "밖"
    outside.mkdir()

    proc = run_cli(
        root,
        "--profile",
        "fast",
        "--changed",
        "src/app.py",
        cwd=outside,
        env_extra={"CLAUDE_PROJECT_DIR": str(outside)},
    )

    assert proc.returncode == 0, proc.stdout
    assert f"대상 루트: {root}" in proc.stdout


# 훅 우회 변수로 CI 게이트가 꺼지면 그건 검사가 아니다
def test_hook_escape_hatches_do_not_skip_the_cli(cli_project):
    config = cli_config(
        full={"triggers": ["stop"], "stages": [stage("test", "raise SystemExit(3)")]}
    )
    proc = run_cli(
        cli_project(config),
        "--profile",
        "full",
        env_extra={"SKIP_AUTOTEST": "1", "SKIP_PRECOMMIT": "1", "SKIP_HISTORY": "1"},
    )

    assert proc.returncode == 1, proc.stdout
    assert "[FAIL] test" in proc.stdout


# **이 CLI 자체는** History 와 세션 마커를 만들지 않는다. stage 로 설정한 임의 명령의
# 부작용까지 없다고 주장하는 것은 아니다 — 여기서 재는 것은 도구 자신의 흔적이다
def test_the_cli_leaves_no_markers_or_history(cli_project):
    root = cli_project(cli_config())
    history = root / ".claude" / "wiki" / "history"

    proc = run_cli(root, "--profile", "full")

    assert proc.returncode == 0
    markers = plugin_data(root)
    assert not markers.exists() or not list(markers.rglob("*")), "세션 마커를 만들었다"
    assert not history.exists(), "History 경로를 만들었다"


# 배치가 전제와 다르면 남의 폴더를 검사하는 대신 멈춘다
# ───────────────── 분류가 실행 입력을 정한다 (HQCI-01) ─────────────────


# **흔적을 파일로 남기는 stage.** 「SKIP 이라고 적고 실제로는 돌았다」를 잡으려면 출력만
# 봐서는 안 된다 — 명령이 돌았는지와 **무엇을 인자로 받았는지**를 따로 확인해야 한다
def recording_stage(mark: Path, placeholder: str | None) -> dict:
    code = (
        "import sys, pathlib;"
        f"pathlib.Path(r'{mark}').write_text(repr(sys.argv[1:]), encoding='utf-8')"
    )
    argv = [sys.executable, "-c", code]
    if placeholder is not None:
        argv.append(placeholder)
    return {"id": "test", "argv": argv}


@pytest.fixture
def changed_files_project(cli_project, tmp_path: Path):
    """`{changed_files}` 만 쓰는 Fast — 매핑이 필요 없는 언어 중립 Profile."""
    mark = tmp_path / "ran.txt"

    def build() -> tuple[Path, Path]:
        config = cli_config(
            fast={
                "triggers": ["post_change"],
                "stages": [recording_stage(mark, "{changed_files}")],
            }
        )
        return cli_project(config), mark

    return build


def received(mark: Path):
    return eval(mark.read_text(encoding="utf-8")) if mark.exists() else None  # noqa: S307


# 정책상 제외한 파일만 줬으면 **아무 명령도 돌지 않아야 한다.** 매핑이 필요 없는
# Profile 이라는 것은 「무엇이든 돌려도 된다」는 뜻이 아니다
@pytest.mark.parametrize(
    ("path", "label"),
    [
        ("docs/안내.md", "사유 있는 제외"),
        ("src/__pycache__/a.pyc", "생성물"),
        ("tests/a.json", "비Python 테스트 파일"),
        ("기타/메모.md", "비추적"),
    ],
)
def test_excluded_only_input_runs_nothing(changed_files_project, path, label):
    root, mark = changed_files_project()
    (root / Path(path).parent).mkdir(parents=True, exist_ok=True)

    proc = run_cli(root, "--profile", "fast", "--changed", path)

    assert proc.returncode == 0, proc.stdout
    assert received(mark) is None, f"{label}인데 stage 가 실행됐다"
    assert "검사가 통과했다는 뜻이 아닙니다" in proc.stdout
    assert "판정: PASS" not in proc.stdout


def test_valid_only_input_runs_with_that_file(changed_files_project):
    root, mark = changed_files_project()

    proc = run_cli(root, "--profile", "fast", "--changed", "src/a.py")

    assert proc.returncode == 0, proc.stdout
    assert received(mark) == ["src/a.py"]


# **제외한 파일이 인자에 섞이면 안 된다.** 분류 결과가 실행 입력을 제한하지 않으면
# 「문서에는 테스트가 없다」고 적어 둔 파일이 그대로 명령에 전달된다
def test_a_mixed_input_passes_only_the_valid_file(changed_files_project):
    root, mark = changed_files_project()

    proc = run_cli(
        root,
        "--profile",
        "fast",
        "--changed",
        "src/a.py",
        "--changed",
        "docs/안내.md",
    )

    assert proc.returncode == 0, proc.stdout
    assert received(mark) == ["src/a.py"]
    assert "[SKIP] docs/안내.md" in proc.stdout


# 매핑이 필요 없는 **정상 추적 파일**은 매핑 부재만으로 막거나 건너뛰지 않는다.
# 출력에서도 SKIP 이라고 오표시하지 않는다 — 실제로는 실행 대상이다
def test_a_tracked_file_needing_no_mapping_runs_and_is_not_labelled_skip(changed_files_project):
    root, mark = changed_files_project()

    proc = run_cli(root, "--profile", "fast", "--changed", ".claude/settings.json")

    assert proc.returncode == 0, proc.stdout
    assert received(mark) == [".claude/settings.json"]
    assert "[SKIP] .claude/settings.json" not in proc.stdout
    assert "[대상] .claude/settings.json" in proc.stdout


# `{mapped_targets}` 를 쓰는 기존 Fast 는 그대로 동작해야 한다
def test_the_mapped_targets_profile_still_works(cli_project, tmp_path: Path):
    mark = tmp_path / "ran.txt"
    config = cli_config(
        fast={
            "triggers": ["post_change"],
            "stages": [recording_stage(mark, "{mapped_targets}")],
        }
    )
    proc = run_cli(cli_project(config), "--profile", "fast", "--changed", "src/a.py")

    assert proc.returncode == 0, proc.stdout
    assert received(mark) == ["tests/"]


# ───────────────── 정확히 버전 2만 (HQCI-02) ─────────────────


# `is_v2()` 는 `>= 2` 라 버전 3 설정의 명령까지 실행하고 PASS 로 보고했다. Doctor 는 같은
# 설정을 FAIL 로 본다 — CLI 가 그 판정과 어긋나면 안 된다
@pytest.mark.parametrize("version", [3, 4, 99, 1, 0, -1, "2", 2.0, True, None, [2]])
def test_only_exact_version_two_runs(cli_project, tmp_path: Path, version):
    mark = tmp_path / "ran.txt"
    config = cli_config(full={"triggers": ["stop"], "stages": [recording_stage(mark, None)]})
    if version is None:
        config.pop("schema_version")
    else:
        config["schema_version"] = version

    proc = run_cli(cli_project(config), "--profile", "full")

    assert proc.returncode == 2, proc.stdout
    assert received(mark) is None, f"버전 {version!r} 인데 stage 가 실행됐다"
    assert "정확히 정수 2" in proc.stdout


def test_exact_version_two_runs(cli_project, tmp_path: Path):
    mark = tmp_path / "ran.txt"
    config = cli_config(full={"triggers": ["stop"], "stages": [recording_stage(mark, None)]})

    proc = run_cli(cli_project(config), "--profile", "full")

    assert proc.returncode == 0, proc.stdout
    assert received(mark) == []


# ───────────────── 사유 없는 제외 (HQCI-03) ─────────────────


# 사유를 비워 둔 제외는 「사유 있는 의도적 제외」가 아니다. 없는 사유를 대신 만들어
# 정상 SKIP 으로 바꾸면 사람이 왜 뺐는지 아무도 모르는 채 검사가 꺼진다
@pytest.mark.parametrize(
    ("label", "unmapped"),
    [
        ("빈 문자열", {"src/": ""}),
        ("공백만", {"src/": "   "}),
        ("null", {"src/": None}),
        ("숫자", {"src/": 42}),
        ("목록형", ["src/"]),
    ],
)
def test_an_exclusion_without_a_reason_is_a_config_error(
    cli_project, tmp_path: Path, label, unmapped
):
    mark = tmp_path / "ran.txt"
    config = cli_config(
        fast={
            "triggers": ["post_change"],
            "stages": [recording_stage(mark, "{mapped_targets}")],
        }
    )
    config["quality"]["unmapped_by_design"] = unmapped

    proc = run_cli(cli_project(config), "--profile", "fast", "--changed", "src/a.py")

    assert proc.returncode == 2, f"{label}: {proc.stdout}"
    assert received(mark) is None
    assert "사유가 없습니다" in proc.stdout


def test_an_exclusion_with_a_reason_is_still_a_silent_skip(cli_project, tmp_path: Path):
    mark = tmp_path / "ran.txt"
    config = cli_config(
        fast={
            "triggers": ["post_change"],
            "stages": [recording_stage(mark, "{mapped_targets}")],
        }
    )
    config["quality"]["unmapped_by_design"] = {
        "src/": "전 영역에 영향을 주어 부분 실행이 무의미하다"
    }

    proc = run_cli(cli_project(config), "--profile", "fast", "--changed", "src/a.py")

    assert proc.returncode == 0, proc.stdout
    assert received(mark) is None
    assert "전 영역에 영향을 주어" in proc.stdout


# ───────────────── --require-venv (Linux guard 보강) ─────────────────


# **이 검사가 생긴 이유는 CI 의 Linux job 이 통과해 놓고 아무것도 증명하지 못한 것이다.**
# 예전 workflow 단계는 고른 경로와 `sys.executable` 을 각각 `realpath()` 로 비교했는데,
# POSIX venv 의 `bin/python` 은 기반 Python 의 symlink 라 양쪽이 같은 파일로 모인다.
# Windows 는 실행 파일을 복사하므로 그 함정이 없어서, 같은 단계가 OS 마다 다른 것을 재고 있었다
def venv_stub(root: Path, relative: str) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("", encoding="utf-8")
    return target


# 준비한 venv 를 고르면 통과한다
@pytest.mark.parametrize("relative", [".venv/Scripts/python.exe", ".venv/bin/python"])
def test_require_venv_accepts_the_projects_own_venv(cli_project, tmp_path: Path, relative):
    mark = tmp_path / "ran.txt"
    config = cli_config(full={"triggers": ["stop"], "stages": [recording_stage(mark, None)]})
    config["python"] = relative
    root = cli_project(config)
    venv_stub(root, relative)

    proc = run_cli(root, "--profile", "full", "--require-venv")

    assert proc.returncode == 0, proc.stdout
    assert received(mark) == []
    assert "venv 확인" in proc.stdout


# **실패 주입: 기반 Python 을 고르게 만든다.** 설정의 `python` 이 `.venv` 밖을 가리키면
# 검사가 실제로 거부해야 한다 — 이것이 예전 Linux 검사가 못 잡던 바로 그 상태다
def test_require_venv_rejects_an_interpreter_outside_the_venv(cli_project, tmp_path: Path):
    mark = tmp_path / "ran.txt"
    config = cli_config(full={"triggers": ["stop"], "stages": [recording_stage(mark, None)]})
    config["python"] = "기반파이썬"
    root = cli_project(config)
    venv_stub(root, "기반파이썬")

    proc = run_cli(root, "--profile", "full", "--require-venv")

    assert proc.returncode == 2, proc.stdout
    assert received(mark) is None, "거부했는데 stage 가 돌았다"
    assert ".venv 밖입니다" in proc.stdout


# 설정 경로와 `.venv` 둘 다 없으면 `venv_python()` 은 현재 프로세스로 대체한다.
# 그 대체값은 `.venv` 밖이므로 이 검사가 잡아야 한다 — 조용한 대체가 이 작업의 출발점이었다
def test_require_venv_rejects_the_silent_fallback(cli_project, tmp_path: Path):
    mark = tmp_path / "ran.txt"
    config = cli_config(full={"triggers": ["stop"], "stages": [recording_stage(mark, None)]})
    root = cli_project(config)  # .venv 를 만들지 않는다

    proc = run_cli(root, "--profile", "full", "--require-venv")

    assert proc.returncode == 2, proc.stdout
    assert received(mark) is None
    assert "대체된 상태일 수 있습니다" in proc.stdout


# 플래그가 없으면 예전처럼 돈다. 이 검사는 CI 가 켜는 것이고 기본 동작이 아니다
def test_without_the_flag_the_interpreter_is_not_policed(cli_project, tmp_path: Path):
    mark = tmp_path / "ran.txt"
    config = cli_config(full={"triggers": ["stop"], "stages": [recording_stage(mark, None)]})

    proc = run_cli(cli_project(config), "--profile", "full")

    assert proc.returncode == 0, proc.stdout
    assert received(mark) == []
    assert "venv 확인" not in proc.stdout


# **symlink 를 따라가지 않는다.** POSIX 에서 `.venv/bin/python` 이 밖을 가리켜도 경계 판정은
# 경로로 한다. 이 단정이 없으면 `realpath()` 로 되돌아가도 테스트가 초록이다
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink 전용 분기")
def test_require_venv_judges_by_path_not_by_symlink_target(cli_project, tmp_path: Path):
    mark = tmp_path / "ran.txt"
    config = cli_config(full={"triggers": ["stop"], "stages": [recording_stage(mark, None)]})
    config["python"] = ".venv/bin/python"
    root = cli_project(config)
    outside = venv_stub(root, "기반파이썬")
    link = root / ".venv" / "bin" / "python"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)

    proc = run_cli(root, "--profile", "full", "--require-venv")

    # 링크 대상은 `.venv` 밖이지만 **고른 경로**는 안쪽이다 — 경로로 판정하므로 통과한다
    assert proc.returncode == 0, proc.stdout
    assert "venv 확인" in proc.stdout


def test_a_misplaced_script_refuses_to_run(cli_project, tmp_path):
    root = cli_project(cli_config())
    stray = tmp_path / "stray"
    stray.mkdir()
    shutil.copy2(
        root / ".claude" / "harness" / "scripts" / "run_quality.py", stray / "run_quality.py"
    )
    shutil.copy2(root / ".claude" / "harness" / "scripts" / "doctor.py", stray / "doctor.py")

    proc = subprocess.run(
        [sys.executable, str(stray / "run_quality.py"), "--profile", "full"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(stray),
        stdin=subprocess.DEVNULL,
        check=False,
    )

    assert proc.returncode == 2
    assert "배치 전제와 다릅니다" in proc.stdout
