"""내보내기 계약: manifest 의 분류, exporter 의 거부, 출력물의 경로 참조.

**이 파일이 막으려는 것은 「조용히 빠진 파일」이다.** 새 훅이나 공통 스킬을 추가하고
manifest 에 적는 것을 잊으면, 내보내기는 종료 코드 0 으로 끝나고 설치물에서는 그 파일만
없다. 설치한 뒤에야 드러나므로 분류 누락을 여기서 잡는다.

반대 방향도 본다 — 소스에만 있어야 하는 파일(`tests/`, exporter, 개발용 설정, 개발 History)이
출력에 섞이면 설치물이 돌지 않는 경로를 안내하게 된다.

계약의 원본은 `.claude/wiki/knowledge/template-layout.md` 다.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import export_template

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "templates" / "manifest.json"
EXPORTER = REPO / ".claude" / "harness" / "scripts" / "export_template.py"

# 소스에만 두는 것으로 **일부러** 분류한 것들. 사유 없이 빠진 것과 가르기 위해 여기 적는다.
# `template-layout.md` 의 「분류 규칙」과 같아야 한다
SOURCE_ONLY = {
    ".claude/harness/scripts/export_template.py": "exporter 자체는 설치물에 넣지 않는다",
    ".claude/harness.json": "개발용 설정. 출력은 templates/core/harness.json 에서 만든다",
    ".claude/wiki/knowledge/doctor.md": "개발용 원본. 출력은 배포 템플릿에서 만든다",
    ".claude/wiki/knowledge/quality-env.md": "개발용 원본. 출력은 배포 템플릿에서 만든다",
    ".claude/wiki/knowledge/template-deploy.md": "배포 ref 정책. 소스 전용",
    ".claude/wiki/knowledge/template-layout.md": "내보내기 계약. 소스 전용",
    ".claude/wiki/overview/README.md": "소스 저장소의 지도. 출력은 배포 템플릿에서 만든다",
    ".claude/wiki/knowledge/README.md": "소스 인덱스. 출력은 배포 템플릿에서 만든다",
    ".claude/wiki/history/README.md": "소스 인덱스. 출력은 배포 템플릿에서 만든다",
}


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _pairs(manifest: dict, packs: list[str] | None = None) -> list[tuple[str, str]]:
    rows = list(manifest["core"])
    for name in packs or []:
        rows += manifest["packs"][name]
    return [(row["source"], row["destination"]) for row in rows]


# ───────────────────────── manifest 계약 ─────────────────────────


def test_manifest_shape(manifest: dict) -> None:
    assert manifest["schema_version"] == 1
    assert isinstance(manifest["core"], list) and manifest["core"]
    assert set(manifest["packs"]) == {"rag", "interview"}


def test_every_manifest_source_exists(manifest: dict) -> None:
    missing = [
        source
        for source, _destination in _pairs(manifest, ["rag", "interview"])
        if not (REPO / source).is_file()
    ]
    assert missing == []


# 같은 destination 을 두 소스가 차지하면 어느 쪽이 설치되는지 순서에 달린다.
# 개발용 원본과 배포 템플릿이 같은 이름을 쓰므로 이 검사가 그 실수를 직접 막는다
def test_destinations_are_unique(manifest: dict) -> None:
    destinations = [destination for _source, destination in _pairs(manifest, ["rag", "interview"])]
    duplicated = {item for item in destinations if destinations.count(item) > 1}
    assert duplicated == set()


def test_manifest_paths_are_relative_and_contained(manifest: dict) -> None:
    for source, destination in _pairs(manifest, ["rag", "interview"]):
        for raw in (source, destination):
            candidate = Path(raw)
            assert not candidate.is_absolute(), raw
            assert ".." not in candidate.parts, raw


# ───────────────────── 분류 누락 ─────────────────────


def _classified(manifest: dict) -> set[str]:
    return {source for source, _destination in _pairs(manifest, ["rag", "interview"])}


def _candidates() -> list[str]:
    found: list[str] = []
    groups = (
        (REPO / ".claude" / "harness" / "hooks", "*.py"),
        (REPO / ".claude" / "harness" / "scripts", "*.py"),
        (REPO / ".claude" / "harness" / "schemas", "*.json"),
        (REPO / ".claude" / "skills", "*/SKILL.md"),
        (REPO / ".claude" / "wiki" / "knowledge", "*.md"),
        (REPO / "templates" / "core", "*"),
        (REPO / "packs", "*"),
    )
    for base, pattern in groups:
        for path in base.rglob(pattern if "/" not in pattern else pattern.split("/")[-1]):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            found.append(path.relative_to(REPO).as_posix())
    return sorted(set(found))


# **이 검사가 이 파일의 이유다.** 새 훅·스킬·템플릿·pack 자원을 추가하고 manifest 에 적지
# 않으면 여기서 걸린다. 일부러 뺀 것은 `SOURCE_ONLY` 에 사유와 함께 적어야 통과한다
def test_no_file_is_silently_unclassified(manifest: dict) -> None:
    classified = _classified(manifest)
    unclassified = [
        path for path in _candidates() if path not in classified and path not in SOURCE_ONLY
    ]
    assert unclassified == [], (
        "manifest 에도 없고 SOURCE_ONLY 에도 없는 파일입니다. 내보낼 것이면 manifest 에, "
        "소스 전용이면 SOURCE_ONLY 에 사유와 함께 적으세요."
    )


def test_source_only_entries_still_exist(manifest: dict) -> None:
    classified = _classified(manifest)
    for path, reason in SOURCE_ONLY.items():
        assert (REPO / path).is_file(), f"{path}: SOURCE_ONLY 항목이 사라졌습니다"
        assert path not in classified, f"{path}: SOURCE_ONLY 인데 manifest 에도 있습니다"
        assert reason.strip(), f"{path}: 사유가 비어 있습니다"


# 설치물의 같은 이름 파일은 배포 템플릿에서 만든다. 소스 Wiki README 가 manifest 에 들어가면
# 그 독립성이 깨지고, 소스 인덱스에 소스 전용 링크를 더하는 순간 출력이 끊어진다
@pytest.mark.parametrize(
    "source_index",
    [
        ".claude/wiki/overview/README.md",
        ".claude/wiki/knowledge/README.md",
        ".claude/wiki/history/README.md",
    ],
)
def test_source_wiki_indexes_are_not_exported(manifest: dict, source_index: str) -> None:
    assert source_index not in _classified(manifest)


@pytest.mark.parametrize(
    ("template", "destination"),
    [
        ("templates/core/overview/README.md", ".claude/wiki/overview/README.md"),
        ("templates/core/knowledge/README.md", ".claude/wiki/knowledge/README.md"),
        ("templates/core/history/README.md", ".claude/wiki/history/README.md"),
    ],
)
def test_deployment_indexes_come_from_templates(
    manifest: dict, template: str, destination: str
) -> None:
    pairs = dict(_pairs(manifest, ["rag", "interview"]))
    assert pairs[template] == destination


# ───────────────────── 배포 설정 ─────────────────────


def test_deployment_config_is_explicitly_inactive() -> None:
    config = json.loads((REPO / "templates" / "core" / "harness.json").read_text(encoding="utf-8"))

    assert config["schema_version"] == 2
    # `python` 을 적지 않는 것이 두 OS 가 각자의 `.venv` 를 쓰게 하는 정상 상태다
    assert "python" not in config
    for name in ("fast", "full"):
        profile = config["quality"]["profiles"][name]
        assert profile["triggers"] == []
        assert profile["stages"] == []
    assert config["quality"]["tracked_paths"] == []
    assert config["quality"]["mappings"] == []
    assert config["history"]["tracked_paths"] == []
    assert config["checks"]["openwork"]["sources"] == []
    assert config["checks"]["expensive_tests"]["pytest_markers"] == []
    # 문체 검사는 섹션이 없으면 아무것도 세지 않는다. 대상 프로젝트에 자동 적용하지 않는다
    assert "prose_style" not in config["checks"]


def test_deployment_config_validates_against_schema() -> None:
    schema = json.loads(
        (REPO / ".claude" / "harness" / "schemas" / "harness.schema.json").read_text(
            encoding="utf-8"
        )
    )
    config = json.loads((REPO / "templates" / "core" / "harness.json").read_text(encoding="utf-8"))

    for key in schema["required"]:
        assert key in config, key
    for key in schema["properties"]["history"]["required"]:
        assert key in config["history"], key
    assert "profiles" in config["quality"]


# ───────────────────── exporter 단위 검사 ─────────────────────


def test_safe_rel_refuses_escape() -> None:
    for raw in ("/etc/passwd", "../outside.md", "a/../../b", "C:/windows/x"):
        with pytest.raises(export_template.ExportError):
            export_template._safe_rel(raw, "테스트")


def test_safe_rel_refuses_empty() -> None:
    for raw in ("", "   ", None, 7):
        with pytest.raises(export_template.ExportError):
            export_template._safe_rel(raw, "테스트")


def test_collision_is_refused() -> None:
    pairs = [(Path("a.md"), Path("CLAUDE.md")), (Path("b.md"), Path("CLAUDE.md"))]
    with pytest.raises(export_template.ExportError):
        export_template.check_collisions(pairs)


def test_missing_source_is_refused(tmp_path: Path) -> None:
    with pytest.raises(export_template.ExportError):
        export_template.check_sources(REPO, [(Path("no/such/file.md"), Path("x.md"))])


def test_source_root_refuses_wrong_placement(tmp_path: Path) -> None:
    stray = tmp_path / "export_template.py"
    stray.write_text("", encoding="utf-8")
    with pytest.raises(export_template.ExportError):
        export_template.source_root(stray)


def test_source_root_finds_repo() -> None:
    assert export_template.source_root(EXPORTER) == REPO


# ───────────────────── exporter 실행 ─────────────────────


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(EXPORTER), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _tree(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


@pytest.fixture(scope="module")
def core_export(tmp_path_factory: pytest.TempPathFactory) -> Path:
    dest = tmp_path_factory.mktemp("export") / "core"
    result = _run("--dest", str(dest))
    assert result.returncode == 0, result.stderr
    return dest


def test_core_export_matches_manifest(core_export: Path, manifest: dict) -> None:
    expected = {destination for _source, destination in _pairs(manifest)}
    assert _tree(core_export) == expected


@pytest.mark.parametrize(
    "absent",
    [
        "README.md",
        ".gitattributes",
        "requirements.txt",
        "ruff.toml",
        ".claude/agents/code-reviewer.md",
        ".claude/skills/quiz/SKILL.md",
        ".claude/skills/rag-code-review/SKILL.md",
        ".claude/harness/scripts/quiz/collect.py",
        ".claude/harness/scripts/export_template.py",
        ".claude/wiki/knowledge/template-deploy.md",
        ".claude/wiki/knowledge/template-layout.md",
        "templates/manifest.json",
    ],
)
def test_core_export_omits_source_only(core_export: Path, absent: str) -> None:
    assert not (core_export / absent).exists()


@pytest.mark.parametrize(
    "present",
    [
        "CLAUDE.md",
        "AGENTS.md",
        ".gitignore",
        "HARNESS-INSTALL.md",
        ".claude/harness.json",
        ".claude/settings.json",
        ".claude/wiki/knowledge/doctor.md",
        ".claude/wiki/knowledge/quality-env.md",
        ".claude/wiki/knowledge/paid-test-approval.md",
        ".claude/wiki/history/plan/.gitkeep",
    ],
)
def test_core_export_includes_required(core_export: Path, present: str) -> None:
    assert (core_export / present).is_file()


# 개발 History 의 `*.md` 는 출력에서 제외한다. `.gitkeep` 세 개만 간다
def test_core_export_has_no_development_history(core_export: Path) -> None:
    history = core_export / ".claude" / "wiki" / "history"
    assert sorted(path.name for path in history.rglob("*.md")) == ["README.md"]
    assert len(list(history.rglob(".gitkeep"))) == 3


def test_pack_export_adds_exactly_the_pack_files(
    tmp_path: Path, core_export: Path, manifest: dict
) -> None:
    dest = tmp_path / "all"
    result = _run("--dest", str(dest), "--pack", "rag", "--pack", "interview")
    assert result.returncode == 0, result.stderr

    added = _tree(dest) - _tree(core_export)
    expected = {
        destination
        for name in ("rag", "interview")
        for _source, destination in [
            (row["source"], row["destination"]) for row in manifest["packs"][name]
        ]
    }
    assert added == expected


def test_interview_pack_installs_quiz_at_the_runtime_path(tmp_path: Path) -> None:
    dest = tmp_path / "interview"
    assert _run("--dest", str(dest), "--pack", "interview").returncode == 0
    # 스킬이 `${CLAUDE_PROJECT_DIR}/.claude/harness/scripts/quiz/` 를 부른다. 설치 위치가
    # 그 자리가 아니면 출력 프로젝트에서 스킬이 깨진다
    assert (dest / ".claude" / "harness" / "scripts" / "quiz" / "collect.py").is_file()
    assert (dest / ".claude" / "skills" / "quiz" / "SKILL.md").is_file()
    assert not (dest / ".claude" / "agents").exists()


@pytest.mark.parametrize(
    ("argv", "why"),
    [
        ([], "--dest 없음"),
        (["--dest"], "값 없는 --dest"),
    ],
)
def test_usage_errors_exit_2(argv: list[str], why: str) -> None:
    assert _run(*argv).returncode == export_template.EXIT_ERROR, why


def test_existing_dest_is_refused(tmp_path: Path) -> None:
    dest = tmp_path / "already"
    dest.mkdir()
    result = _run("--dest", str(dest))
    assert result.returncode == export_template.EXIT_ERROR
    # 빈 디렉터리도 거부한다. 안 그러면 사용자가 「비어 있으니 괜찮다」로 덮어쓰게 된다
    assert list(dest.iterdir()) == []


def test_missing_parent_is_refused(tmp_path: Path) -> None:
    result = _run("--dest", str(tmp_path / "no" / "such" / "parent" / "out"))
    assert result.returncode == export_template.EXIT_ERROR


def test_unknown_pack_is_refused(tmp_path: Path) -> None:
    result = _run("--dest", str(tmp_path / "out"), "--pack", "nope")
    assert result.returncode == export_template.EXIT_ERROR
    assert not (tmp_path / "out").exists()


def test_dest_inside_source_root_is_refused() -> None:
    inside = REPO / ".export-should-never-exist"
    result = _run("--dest", str(inside))
    assert result.returncode == export_template.EXIT_ERROR
    assert not inside.exists(), "거부했는데 소스 트리에 디렉터리를 만들었습니다"


def test_dest_equal_to_source_root_is_refused() -> None:
    assert _run("--dest", str(REPO)).returncode == export_template.EXIT_ERROR


def test_repeated_pack_flag_is_idempotent(tmp_path: Path) -> None:
    once = tmp_path / "once"
    twice = tmp_path / "twice"
    assert _run("--dest", str(once), "--pack", "rag").returncode == 0
    assert _run("--dest", str(twice), "--pack", "rag", "--pack", "rag").returncode == 0
    assert _tree(once) == _tree(twice)


# 완료 기준의 문장은 「**소스 파일·History** 를 바꾸지 않는다」 다. `templates/` 만 보면 그
# 절반이 안 잡힌다 — manifest 가 읽는 소스는 `packs/` 와 `.claude/` 에 흩어져 있고, History
# 세 폴더는 **manifest 의 읽기 대상이면서** 하네스가 평소 기록을 쓰는 자리다. 그래서
# 내보내기가 읽는 파일 전부와 History 전부를 본다.
#
# **목록을 미리 굳히면 안 된다.** 처음에 `rglob` 을 한 번만 돌려 경로 목록을 만들어 두면
# 그 목록에 없는 **새 파일**은 비교에서 빠진다 — History 에 기록을 하나 새로 쓰는 것이
# 바로 이 완료 기준이 걱정하는 동작인데, 실측으로 그 probe 가 「NOT CAUGHT」 였다.
# 그래서 호출마다 다시 훑는다
def _fingerprint(manifest: dict) -> dict[str, tuple[int, str]]:
    paths = [MANIFEST]
    paths += [REPO / source for source, _ in _pairs(manifest, list(manifest["packs"]))]
    paths += list((REPO / ".claude" / "wiki" / "history").rglob("*"))
    # 내용까지 본다. mtime 만 보면 같은 타임스탬프로 다시 쓴 것을 놓치고, 지워진 파일은
    # `is_file()` 에서 떨어져 나가 사전이 달라지므로 삭제도 함께 잡힌다
    return {
        path.relative_to(REPO).as_posix(): (
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(set(paths))
        if path.is_file()
    }


def test_export_does_not_touch_the_source(tmp_path: Path, manifest: dict) -> None:
    before = _fingerprint(manifest)
    # 감시 대상이 비거나 History 가 빠지면 이 테스트는 아무것도 재지 않으면서 초록으로 남는다
    assert len(before) > 50, f"감시 대상이 너무 적습니다: {len(before)}"
    assert any(key.startswith(".claude/wiki/history/") for key in before), (
        "History 를 감시하지 않습니다 — 완료 기준이 이름으로 지목한 자리다"
    )

    done = _run("--dest", str(tmp_path / "out"), "--pack", "rag", "--pack", "interview")

    assert done.returncode == 0, done.stdout + done.stderr
    assert _fingerprint(manifest) == before


# ───────────────────── 출력물의 경로 참조 ─────────────────────

SOURCE_ONLY_MARKERS = ("packs/", "templates/core/", "templates/manifest.json", "export_template.py")


# 설치물에 없는 것을 「지금 여기 있다」처럼 안내하면 설치한 사람이 그 경로를 찾다 멈춘다.
# 출처를 밝힌 서술(「원본 저장소가 소유한다」)은 금지하지 않는다 — 금지하는 것은 **설치된
# 현재 경로처럼** 적는 것이다. 그래서 코드 울타리 안의 명령 형태만 본다
def test_exported_docs_do_not_command_source_only_paths(core_export: Path) -> None:
    offenders: list[str] = []
    for path in core_export.rglob("*.md"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if not stripped.startswith(("python ", "$ python", "```text", "- `python")):
                continue
            if any(marker in stripped for marker in SOURCE_ONLY_MARKERS):
                offenders.append(f"{path.relative_to(core_export).as_posix()}:{number}")
    assert offenders == []


def test_exported_doctor_doc_does_not_point_at_source_files(core_export: Path) -> None:
    text = (core_export / ".claude" / "wiki" / "knowledge" / "doctor.md").read_text(
        encoding="utf-8"
    )
    # 소스 README 와 개발 History 두 파일은 설치물에 없다
    assert "README.md`의" not in text
    assert ".claude/wiki/history/plan/" not in text


def test_exported_knowledge_index_links_only_installed_docs(core_export: Path) -> None:
    knowledge = core_export / ".claude" / "wiki" / "knowledge"
    text = (knowledge / "README.md").read_text(encoding="utf-8")
    for name in ("doctor.md", "quality-env.md", "paid-test-approval.md"):
        assert f"({name})" in text, name
        assert (knowledge / name).is_file(), name
    for absent in ("template-deploy.md", "template-layout.md"):
        assert absent not in text, absent


def test_exported_overview_links_resolve(core_export: Path) -> None:
    overview = core_export / ".claude" / "wiki" / "overview" / "README.md"
    text = overview.read_text(encoding="utf-8")
    for target in ("../knowledge/doctor.md", "../knowledge/quality-env.md"):
        assert target in text
        assert (overview.parent / target).resolve().is_file(), target


def test_exported_entry_points_disclose_inactive_quality(core_export: Path) -> None:
    for name in ("CLAUDE.md", "AGENTS.md"):
        text = (core_export / name).read_text(encoding="utf-8")
        assert "비활성" in text, name
        assert "HARNESS-INSTALL.md" in text, name


def test_install_guide_covers_every_wired_hook(core_export: Path) -> None:
    settings = json.loads((core_export / ".claude" / "settings.json").read_text(encoding="utf-8"))
    wired: set[str] = set()
    for entries in settings["hooks"].values():
        for entry in entries:
            for hook in entry["hooks"]:
                for part in hook["command"].split("/"):
                    if part.endswith(".py") or part.endswith('.py"'):
                        wired.add(part.strip('"'))

    guide = (core_export / "HARNESS-INSTALL.md").read_text(encoding="utf-8")
    missing = sorted(name for name in wired if name not in guide)
    assert missing == [], "설치 안내가 설명하지 않는 훅입니다"


# ───────────────────── 출력 .gitignore ─────────────────────


@pytest.mark.skipif(shutil.which("git") is None, reason="git 이 없어 check-ignore 를 못 돈다")
@pytest.mark.parametrize(
    "ignored",
    [
        "__pycache__/x.pyc",
        "a.pyc",
        ".pytest_cache/x",
        ".ruff_cache/x",
        ".venv/x",
        ".agents/x",
        ".codex/x",
    ],
)
def test_exported_gitignore_covers_artifacts(
    tmp_path: Path, core_export: Path, ignored: str
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    shutil.copyfile(core_export / ".gitignore", project / ".gitignore")

    result = subprocess.run(
        ["git", "check-ignore", "-q", ignored],
        cwd=project,
        capture_output=True,
    )
    assert result.returncode == 0, f"{ignored} 가 ignore 되지 않습니다"


@pytest.mark.skipif(shutil.which("git") is None, reason="git 이 없어 check-ignore 를 못 돈다")
def test_exported_gitignore_keeps_history(tmp_path: Path, core_export: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    shutil.copyfile(core_export / ".gitignore", project / ".gitignore")

    result = subprocess.run(
        ["git", "check-ignore", "-q", ".claude/wiki/history/plan/x.md"],
        cwd=project,
        capture_output=True,
    )
    # History 는 ignore 하지 않는다. 비어 있는 것은 초기 상태이고 정책이 아니다
    assert result.returncode == 1


def test_exported_gitignore_has_no_unresolvable_pointer(core_export: Path) -> None:
    text = (core_export / ".gitignore").read_text(encoding="utf-8")
    assert "git show" not in text
    assert "README.md" not in text
