"""쓰기 전 거부 계약: destination 별칭·부모 충돌과 소스 경로의 링크.

**정상 manifest 가 통과하는 것은 이 계약의 증거가 아니다.** 이 저장소의 manifest 에는 겹치는
destination 이 없으므로, 거부 조건은 **변형 manifest** 로만 잴 수 있다. 그래서 임시 소스 트리를
정상 배치(`<루트>/.claude/harness/scripts/export_template.py`)로 만들고 그 안에 어긋난
manifest 를 넣어 실제 CLI 를 돌린다 — 사용자 저장소는 건드리지 않는다.

여기서 재는 세 가지는 모두 실측으로 터진 자리다.

1. `CLAUDE.md` 와 `claude.md` — Windows 에서 같은 파일이라, 문자열 비교만 하면 종료 0 으로
   끝나고 출력에는 **나중 내용 하나만** 남았다.
2. `docs` 와 `docs/guide.md` — `docs` 파일을 만든 뒤 mkdir 이 WinError 183 으로 죽어
   **부분 출력이 남은 채** 종료 1 이 됐다.
3. 소스 경로의 **상위** 구성 요소가 링크인 경우 — 마지막 파일만 보면 통과한다.

계약은 셋 다 **쓰기 전 종료 2**이고 대상 디렉터리가 생기지 않는 것이다.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import export_template

REPO = Path(__file__).resolve().parents[1]
EXPORTER = REPO / ".claude" / "harness" / "scripts" / "export_template.py"


def _fake_source(
    root: Path,
    core: list[tuple[str, str]],
    packs: dict[str, list[tuple[str, str]]] | None = None,
    files: dict[str, str] | None = None,
) -> Path:
    """정상 배치의 임시 소스 트리. exporter 는 자기 경로에서 루트를 정한다."""
    scripts = root / ".claude" / "harness" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(EXPORTER, scripts / "export_template.py")

    (root / "templates").mkdir()
    manifest = {
        "schema_version": 1,
        "core": [{"source": source, "destination": destination} for source, destination in core],
        "packs": {
            name: [
                {"source": source, "destination": destination} for source, destination in entries
            ]
            for name, entries in (packs or {}).items()
        },
    }
    (root / "templates" / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for relative, text in (files or {}).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def _run_in(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(root / ".claude" / "harness" / "scripts" / "export_template.py"),
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# ───────────────────── TCP-01 destination 충돌 ─────────────────────


@pytest.mark.parametrize(
    ("core", "label"),
    [
        ([("a.txt", "CLAUDE.md"), ("b.txt", "claude.md")], "대소문자 별칭"),
        ([("b.txt", "claude.md"), ("a.txt", "CLAUDE.md")], "대소문자 별칭 역순"),
        ([("a.txt", "docs"), ("b.txt", "docs/guide.md")], "부모가 파일"),
        ([("b.txt", "docs/guide.md"), ("a.txt", "docs")], "부모가 파일, 역순"),
        ([("a.txt", "x/y.md"), ("b.txt", "X/y.md")], "상위 폴더 대소문자 별칭"),
    ],
)
def test_destination_conflicts_are_refused_before_writing(
    tmp_path: Path, core: list[tuple[str, str]], label: str
) -> None:
    root = _fake_source(tmp_path / "src", core, files={"a.txt": "FIRST", "b.txt": "SECOND"})
    dest = tmp_path / "out"

    result = _run_in(root, "--dest", str(dest))

    assert result.returncode == export_template.EXIT_ERROR, f"{label}: {result.stdout}"
    assert not dest.exists(), f"{label}: 거부했는데 대상을 만들었습니다"
    # 소스는 그대로여야 한다
    assert (root / "a.txt").read_text(encoding="utf-8") == "FIRST"
    assert (root / "b.txt").read_text(encoding="utf-8") == "SECOND"


# core 와 pack 사이의 충돌도 같은 자리에서 걸려야 한다 — pack 을 고를 때만 겹치는 manifest 는
# 기본 내보내기에서 통과해 버리므로 더 늦게 드러난다
def test_core_and_pack_conflict_is_refused(tmp_path: Path) -> None:
    root = _fake_source(
        tmp_path / "src",
        [("a.txt", "CLAUDE.md")],
        packs={"extra": [("b.txt", "claude.md")]},
        files={"a.txt": "FIRST", "b.txt": "SECOND"},
    )

    assert _run_in(root, "--dest", str(tmp_path / "core-only")).returncode == 0
    dest = tmp_path / "with-pack"
    result = _run_in(root, "--dest", str(dest), "--pack", "extra")
    assert result.returncode == export_template.EXIT_ERROR
    assert not dest.exists()


# 과잉 거부도 결함이다. 같은 폴더 아래 형제 파일은 정상이다
def test_siblings_in_one_folder_are_allowed(tmp_path: Path) -> None:
    root = _fake_source(
        tmp_path / "src",
        [("a.txt", "docs/a.md"), ("b.txt", "docs/b.md"), ("c.txt", "docs/deep/c.md")],
        files={"a.txt": "A", "b.txt": "B", "c.txt": "C"},
    )
    dest = tmp_path / "out"

    assert _run_in(root, "--dest", str(dest)).returncode == 0
    assert (dest / "docs" / "a.md").read_text(encoding="utf-8") == "A"
    assert (dest / "docs" / "b.md").read_text(encoding="utf-8") == "B"
    assert (dest / "docs" / "deep" / "c.md").read_text(encoding="utf-8") == "C"


def test_missing_source_is_refused_by_the_cli(tmp_path: Path) -> None:
    root = _fake_source(tmp_path / "src", [("gone.txt", "out.md")])
    dest = tmp_path / "out"

    assert _run_in(root, "--dest", str(dest)).returncode == export_template.EXIT_ERROR
    assert not dest.exists()


# ───────────────────── TCP-02 소스 경로의 링크 ─────────────────────


# **capability 검사를 수집 시점에 하지 않는다.** 전에는 모듈 수준 `skipif` 가
# `os.environ.get("TEMP", ".")` 아래에 `link-target` 폴더를 만들고 지우지 않았다. `TEMP` 가
# 없는 환경에서는 그 자리가 **cwd — pytest 를 띄운 저장소 체크아웃** 이다(Linux 가 그렇다.
# 거기서는 `TMPDIR` 를 쓴다). 실측으로 `TEMP` 만 지운 임시 cwd 에서 이 모듈을 수집하자 빈
# cwd 에 `link-target` 이 남았다. 그래서 검사를 **각 테스트의 `tmp_path` 안에서 실행
# 시점에** 한다 — 격리되고, 실제 테스트와 같은 파일시스템이고, pytest 가 치운다.
#
# **symlink 와 junction 의 생성 조건은 다르고, 둘 다 실행 환경에 달렸다.** 실측으로 한
# 세션에서는 `os.symlink` 가 WinError 1314 로 거부되는데 `mklink /J` 는 종료 0 이었고,
# **같은 머신의 다른 세션에서는** 그 `mklink /J` 가 `Access is denied.` 로 종료 1 이었다.
# 기전은 **미확인이다** — 세션마다 실행 조건이 다르다는 것까지가 관측이고, 변인을 제거한
# 실험은 하지 않았다(`history/task/2026-11-25-link-capability-varies-by-session.md`).
#
# 그래서 둘을 한 조건으로 묶지 않고, **각각** 만들어 보고 안 되는 쪽만 이유를 밝히고 skip
# 한다. 묶으면 돌 수 있는 검사까지 skip 하고, 묶지 않아도 **어느 환경에서도 자동으로
# 통과하지는 않는다.**


def _require_symlink(tmp_path: Path) -> None:
    target = tmp_path / "_probe_target"
    target.mkdir(exist_ok=True)
    probe = tmp_path / "_probe_symlink"
    try:
        os.symlink(target, probe, target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError) as exc:
        pytest.skip(f"이 환경에서 symlink 를 만들 수 없습니다 ({exc!r}). 이 거부는 미검증이다")
    probe.unlink()


def _make_junction(link: Path, target: Path) -> bool:
    """junction 을 만든다. symlink 과 **다른** 권한 조건을 쓰므로 따로 검사한다."""
    if os.name != "nt":
        return False
    done = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return done.returncode == 0 and link.exists()


def _require_junction(tmp_path: Path) -> None:
    if os.name != "nt":
        pytest.skip("junction 은 Windows 의 개념이다. 다른 OS 에서는 symlink 쪽이 같은 자리를 잰다")
    target = tmp_path / "_probe_target"
    target.mkdir(exist_ok=True)
    probe = tmp_path / "_probe_junction"
    if not _make_junction(probe, target):
        pytest.skip("이 환경에서 junction 을 만들 수 없습니다. 이 거부는 미검증이다")
    probe.rmdir()  # 링크만 지운다. `rmdir` 은 대상을 따라가지 않는다


def test_symlinked_final_file_is_refused(tmp_path: Path) -> None:
    _require_symlink(tmp_path)
    root = _fake_source(tmp_path / "src", [("link.txt", "out.md")], files={"real.txt": "X"})
    os.symlink(root / "real.txt", root / "link.txt")
    dest = tmp_path / "out"

    assert _run_in(root, "--dest", str(dest)).returncode == export_template.EXIT_ERROR
    assert not dest.exists()


# **이것이 TCP-02 의 핵심이다.** `alias` 가 루트 **안**을 가리키면 마지막 파일은 평범한
# 파일이고 resolve 결과도 루트 안이라, 링크 검사와 탈출 검사를 둘 다 통과했다
def test_symlinked_parent_inside_root_is_refused(tmp_path: Path) -> None:
    _require_symlink(tmp_path)
    root = _fake_source(tmp_path / "src", [("alias/a.txt", "out.md")], files={"real/a.txt": "X"})
    os.symlink(root / "real", root / "alias", target_is_directory=True)
    dest = tmp_path / "out"

    result = _run_in(root, "--dest", str(dest))
    assert result.returncode == export_template.EXIT_ERROR
    assert not dest.exists()


def test_symlinked_parent_outside_root_is_refused(tmp_path: Path) -> None:
    _require_symlink(tmp_path)
    outside = tmp_path / "outside"
    (outside / "secret").mkdir(parents=True)
    (outside / "secret" / "a.txt").write_text("LEAK", encoding="utf-8")

    root = _fake_source(tmp_path / "src", [("alias/a.txt", "out.md")])
    os.symlink(outside / "secret", root / "alias", target_is_directory=True)
    dest = tmp_path / "out"

    assert _run_in(root, "--dest", str(dest)).returncode == export_template.EXIT_ERROR
    assert not dest.exists()


# ─────────────────── TCP-02 실제 junction (모사 아님) ───────────────────
#
# **junction 은 `is_symlink()` 에 False 를 낸다.** 그래서 `_is_link()` 의
# `os.path.isjunction` 가지가 정말 필요한지는 실제 reparse point 로만 알 수 있다. 아래 셋이
# 그 가지를 지난다 — **만들 수 있는 환경에서만** 돌고, 그렇지 않으면 이유를 밝히고 skip 한다.
#
# 링크 대상은 모두 `tmp_path` 안에 둔다. 「루트 밖」은 **소스 루트** 기준이므로, 정리가
# 링크를 따라가더라도 pytest 가 어차피 지울 자리만 지운다. (실측: Python 3.12 의
# `shutil.rmtree` 는 junction 을 따라가지 않았고 대상 파일이 남았다.)


def test_junction_is_invisible_to_is_symlink(tmp_path: Path) -> None:
    _require_junction(tmp_path)
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "alias"
    assert _make_junction(link, target)

    assert link.is_symlink() is False, "junction 이 symlink 로 보이면 이 분기는 필요 없다"
    assert export_template._is_link(link) is True, "junction 을 링크로 보지 않는다"


@pytest.mark.parametrize("where", ["inside", "outside"])
def test_junction_parent_is_refused(tmp_path: Path, where: str) -> None:
    _require_junction(tmp_path)
    root = _fake_source(tmp_path / "src", [("alias/a.txt", "out.md")], files={"real/a.txt": "X"})
    if where == "inside":
        target = root / "real"
    else:
        target = tmp_path / "outside" / "secret"
        target.mkdir(parents=True)
        (target / "a.txt").write_text("LEAK", encoding="utf-8")
    assert _make_junction(root / "alias", target)
    dest = tmp_path / "out"

    result = _run_in(root, "--dest", str(dest))
    output = result.stdout + result.stderr

    assert result.returncode == export_template.EXIT_ERROR, output
    assert not dest.exists(), "거부했는데 대상을 만들었습니다"
    assert "alias" in output, "링크 자리를 알려야 고칠 수 있다"
    if where == "outside":
        # 링크를 따라가 읽지 않았다
        assert (target / "a.txt").read_text(encoding="utf-8") == "LEAK"


# 링크를 만들 수 없는 환경에서도 **검사 자체가 있는지**는 잴 수 있다. 루트 아래 각 구성
# 요소를 보는지 확인한다 — 마지막 파일만 보던 것이 TCP-02 였다
def test_check_sources_inspects_every_component(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "src"
    (root / "real").mkdir(parents=True)
    (root / "real" / "a.txt").write_text("X", encoding="utf-8")

    seen: list[str] = []
    original = Path.is_symlink

    def spy(self: Path) -> bool:
        seen.append(self.name)
        return original(self)

    monkeypatch.setattr(Path, "is_symlink", spy)
    export_template.check_sources(root, [(Path("real/a.txt"), Path("out.md"))])

    assert "real" in seen, "상위 디렉터리를 검사하지 않습니다"
    assert "a.txt" in seen


def test_check_sources_reports_the_link_position(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "src"
    (root / "real").mkdir(parents=True)
    (root / "real" / "a.txt").write_text("X", encoding="utf-8")

    # 상위 `real` 만 링크라고 답하게 만든다
    monkeypatch.setattr(Path, "is_symlink", lambda self: self.name == "real")

    with pytest.raises(export_template.ExportError) as caught:
        export_template.check_sources(root, [(Path("real/a.txt"), Path("out.md"))])
    assert "real" in str(caught.value)


def test_normal_source_tree_passes(tmp_path: Path) -> None:
    root = tmp_path / "src"
    (root / "real").mkdir(parents=True)
    (root / "real" / "a.txt").write_text("X", encoding="utf-8")

    export_template.check_sources(root, [(Path("real/a.txt"), Path("out.md"))])
