"""배포 사본을 **실제로 실행해 보는** 검증.

소스 저장소에서 테스트가 통과해도 내보낸 설치물에서는 import·참조 경로가 끊길 수 있다.
그 차이는 파일 목록을 비교해서는 안 보이고 **사본 안에서 명령을 돌려야** 드러난다.

그래서 이 파일은 `tests/test_export_template.py` 와 역할이 다르다. 저쪽은 manifest 의 분류와
exporter 의 거부 계약을 **정적으로** 본다 — 어떤 파일이 어디로 가는지, 무엇이 빠졌는지.
이쪽은 그 출력물에서 Doctor·Quality 엔진·훅·수집기를 **돌린다.** 그래서 정적 집합 단언을
여기서 되풀이하지 않는다. 겹치면 둘이 갈라졌을 때 어느 쪽이 계약인지 알 수 없게 된다.

**세 가지 루트 해석이 서로 다르다.** 실측(2026-11-25)으로:

- `doctor.py`·`run_quality.py` 는 **자기 배치**로 루트를 정한다. 엉뚱한
  `CLAUDE_PROJECT_DIR` 와 외부 cwd 에서도 사본을 읽는다.
- 훅은 `CLAUDE_PROJECT_DIR` → cwd 로 정한다(`_hookutil` 의 `PROJECT_ROOT` 는 **import 때**
  정해진다). 그래서 훅 subprocess 에는 사본 루트를 **명시해야** 한다.
- `openwork/collect.py` 는 환경·cwd 기반이고 자기 배치 fallback 이 **없다** — 둘 다 어긋나면
  종료 2 로 죽는다. 그래서 `--root` 를 명시한다.

**여기서 증명하지 않는 것**: 실제 Claude/Codex 세션의 이벤트 전달과 신뢰 승인이다. 아래
훅 검사는 합성 payload 를 직접 넘긴 것이고, 세션이 그 payload 를 보낸다는 사실은 이 파일의
범위가 아니다.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EXPORTER = REPO / ".claude" / "harness" / "scripts" / "export_template.py"

DOCTOR = ".claude/harness/scripts/doctor.py"
RUN_QUALITY = ".claude/harness/scripts/run_quality.py"
OPENWORK = ".claude/harness/scripts/openwork/collect.py"
QUIZ = ".claude/harness/scripts/quiz/collect.py"
AUTO_TEST_HOOK = ".claude/harness/hooks/auto_test_check.py"


# ───────────────────────── 공용 도구 ─────────────────────────


def _export(dest: Path, *packs: str) -> Path:
    argv = [sys.executable, str(EXPORTER), "--dest", str(dest)]
    for name in packs:
        argv += ["--pack", name]
    done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert done.returncode == 0, done.stdout + done.stderr
    return dest


# **`PYTHONPATH` 를 지우는 것이 요점이다.** `conftest.py` 는 소스 hooks·scripts 를
# `sys.path` 에 직접 넣고 `PYTHONPATH` 는 건드리지 않으므로 자식에게 새지 않는다. 그래도
# 여기서 명시적으로 지운다 — 완료 기준이 「소스 import 경로 도움 없이」이고, 나중에 누가
# 편의로 `PYTHONPATH` 를 쓰면 이 검증이 조용히 무의미해진다
def _run(
    script: Path,
    *args: str,
    cwd: Path,
    env_extra: dict[str, str] | None = None,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        input=stdin,
        env=env,
    )


def _config(copy: Path) -> dict:
    return json.loads((copy / ".claude" / "harness.json").read_text(encoding="utf-8"))


def _write_config(copy: Path, config: dict) -> None:
    (copy / ".claude" / "harness.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# 사본 설정을 **사본 자신의 배포 설정에서 출발해** 고친다. 손으로 새 설정을 적으면 배포
# 기본값이 바뀌었을 때 이 테스트만 과거 모양을 들고 초록으로 남는다
def _configure_profile(
    copy: Path, profile: str, stages: list[dict], *, triggers: list[str] | None = None
) -> None:
    config = _config(copy)
    config["python"] = sys.executable
    config["quality"]["profiles"][profile] = {
        "triggers": triggers or [],
        "stages": stages,
    }
    _write_config(copy, config)


def _probe(tmp_path: Path, name: str, *, exit_code: int = 0) -> tuple[Path, Path]:
    """표준 라이브러리만 쓰는 probe. 호출 흔적을 JSON 으로 남긴다."""
    trace = tmp_path / f"{name}.trace.json"
    script = tmp_path / f"{name}.py"
    # f-string 으로 짜지 않는다 — 중괴호를 이중으로 써야 해서 한 글자만 틀려도 생성된
    # 스크립트가 SyntaxError 로 죽고, 그때 실패 메시지는 **probe 가 아니라 엔진 쪽**을
    # 가리킨다. 실제로 그렇게 한 번 헤맸다
    script.write_text(
        "import json, os, sys\n"
        "trace = r'''" + str(trace) + "'''\n"
        "json.dump(\n"
        "    {'cwd': os.getcwd(), 'executable': sys.executable, 'argv': sys.argv[1:]},\n"
        "    open(trace, 'w', encoding='utf-8'),\n"
        ")\n"
        "sys.exit(" + str(exit_code) + ")\n",
        encoding="utf-8",
    )
    return script, trace


def _stage(stage_id: str, script: Path, *args: str) -> dict:
    return {
        "id": stage_id,
        "label": f"probe {stage_id}",
        "argv": ["{python}", str(script), *args],
        "success_codes": [0],
        "timeout": 60,
    }


def _digests(paths: list[Path]) -> dict[str, str]:
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths if path.is_file()
    }


@pytest.fixture
def core(tmp_path: Path) -> Path:
    return _export(tmp_path / "core")


# ───────────────────── 내보내기와 경계 ─────────────────────


# 네 구성을 **실제 exporter 로** 만든다. 손으로 복사하면 manifest 가 빠뜨린 파일이 테스트에
# 들어와 「설치물에는 없는데 테스트는 통과」가 된다
@pytest.mark.parametrize(
    ("packs", "name"),
    [((), "core"), (("rag",), "rag"), (("interview",), "iv"), (("rag", "interview"), "both")],
)
def test_four_configurations_export_and_carry_no_dev_tests(
    tmp_path: Path, packs: tuple[str, ...], name: str
) -> None:
    copy = _export(tmp_path / name, *packs)

    assert (copy / ".claude" / "harness.json").is_file()
    # **경계 단언이다.** 사본에 개발 `tests/` 가 있으면 아래 probe 들이 소스 테스트를
    # 자동 발견해 돌 수 있고, 그러면 「설치물이 돈다」가 아니라 「소스가 돈다」를 재게 된다
    assert not (copy / "tests").exists()
    assert not (copy / "conftest.py").exists()
    # 개발 History 가 따라오지 않았다는 것도 여기서 본다 — 빈 폴더와 `.gitkeep` 만이다
    assert list((copy / ".claude" / "wiki" / "history" / "task").iterdir()) == [
        copy / ".claude" / "wiki" / "history" / "task" / ".gitkeep"
    ]


# ───────────────────────── Doctor ─────────────────────────


# `D-PROFILE` 은 **비활성 Profile** 의 WARN 이라 개발 설정에서는 나오지 않는다. 그래서
# 「사본의 설정을 읽었다」의 판별자로 쓴다 — 종료 코드만 보면 소스를 읽어도 0 이다
@pytest.mark.parametrize(
    ("packs", "name"),
    [((), "core"), (("rag",), "rag"), (("rag", "interview"), "both")],
)
def test_copy_doctor_reads_the_copy_config(
    tmp_path: Path, packs: tuple[str, ...], name: str
) -> None:
    copy = _export(tmp_path / name, *packs)

    done = _run(copy / DOCTOR, cwd=copy)
    output = done.stdout + done.stderr

    assert done.returncode == 0, output
    assert "D-PROFILE" in output, "비활성 Profile WARN 이 없으면 사본 설정을 읽은 것이 아니다"
    assert "FAIL 0" in output, output[-400:]


# 엉뚱한 프로젝트 환경변수와 외부 cwd 에서도 사본을 읽는지 본다.
#
# **소스 저장소를 가리키지 않고 decoy 를 쓴다.** 소스를 가리키면 누출이 났을 때 소스의
# 활성 Profile 이 돌아 전체 테스트가 시작된다 — 실패가 느리고 시끄럽다. decoy 는 그 대신
# **즉시 관측 가능한 흔적**(trace 파일)을 남기므로 누출을 더 분명히 잡는다
def test_copy_cli_ignores_a_wrong_project_env_and_outside_cwd(tmp_path: Path, core: Path) -> None:
    decoy = _export(tmp_path / "decoy")
    script, decoy_trace = _probe(tmp_path, "decoy")
    _configure_profile(decoy, "full", [_stage("decoy", script)])

    outside = tmp_path / "outside"
    outside.mkdir()
    env = {"CLAUDE_PROJECT_DIR": str(decoy)}

    doctor = _run(core / DOCTOR, cwd=outside, env_extra=env)
    quality = _run(core / RUN_QUALITY, "--profile", "full", cwd=outside, env_extra=env)

    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert "D-PROFILE" in doctor.stdout + doctor.stderr
    # 사본의 full 은 비어 있으므로 2 다. decoy 를 읽었다면 0 이 되고 trace 가 생긴다
    assert quality.returncode == 2, quality.stdout + quality.stderr
    assert not decoy_trace.exists(), "엉뚱한 환경변수의 Profile 을 실행했습니다"

    # 거부만으로는 「아무것도 안 돌았다」와 구분되지 않는다. 사본에 성공 probe 를 심어
    # **외부 cwd 에서** 돌려, 실행된 stage 의 cwd 가 사본인지까지 본다
    ours, our_trace = _probe(tmp_path, "outside-run")
    _configure_profile(core, "full", [_stage("ours", ours)])

    again = _run(core / RUN_QUALITY, "--profile", "full", cwd=outside, env_extra=env)

    assert again.returncode == 0, again.stdout + again.stderr
    assert our_trace.is_file(), "사본의 Profile 이 실행되지 않았습니다"
    assert Path(json.loads(our_trace.read_text(encoding="utf-8"))["cwd"]) == core
    assert not decoy_trace.exists()


# 두 pack 을 고른 사본에서도 기본 거부가 같아야 한다 — 선택 구성이 공통 설정을 덮지
# 않는다는 것을 설치물 쪽에서 보는 자리다
@pytest.mark.parametrize(("packs", "name"), [((), "core"), (("rag", "interview"), "both")])
def test_unconfigured_full_is_refused_not_passed(
    tmp_path: Path, packs: tuple[str, ...], name: str
) -> None:
    copy = _export(tmp_path / name, *packs)

    done = _run(copy / RUN_QUALITY, "--profile", "full", cwd=copy)
    output = done.stdout + done.stderr

    assert done.returncode == 2, output
    assert "PASS" not in output.split("판정")[-1], "빈 Profile 을 통과로 보고합니다"


# ──────────────────── 설정한 Profile 의 실제 실행 ────────────────────


def test_configured_profile_runs_the_installed_engine(tmp_path: Path, core: Path) -> None:
    script, trace = _probe(tmp_path, "ok")
    _configure_profile(core, "full", [_stage("ok", script, "--flag")])

    done = _run(core / RUN_QUALITY, "--profile", "full", cwd=core)
    output = done.stdout + done.stderr

    assert done.returncode == 0, output
    assert trace.is_file(), "probe 가 실행되지 않았습니다"
    seen = json.loads(trace.read_text(encoding="utf-8"))
    assert Path(seen["cwd"]) == core, f"stage 가 사본 밖에서 돌았습니다: {seen['cwd']}"
    # **설정한 값과 대조한다.** 「소스 venv 안이다」로 판정하면 테스트를 돌린 인터프리터가
    # 원래 거기 있으므로 늘 참이 된다
    assert Path(seen["executable"]) == Path(sys.executable)
    assert seen["argv"] == ["--flag"]


def test_failing_stage_stops_the_profile(tmp_path: Path, core: Path) -> None:
    bad, bad_trace = _probe(tmp_path, "bad", exit_code=3)
    later, later_trace = _probe(tmp_path, "later")
    _configure_profile(core, "full", [_stage("bad", bad), _stage("later", later)])

    done = _run(core / RUN_QUALITY, "--profile", "full", cwd=core)
    output = done.stdout + done.stderr

    assert done.returncode == 1, output
    assert bad_trace.is_file(), "실패 probe 가 실제로 돌지 않았습니다"
    assert "bad" in output, output[-400:]
    assert not later_trace.exists(), "앞 단계가 실패했는데 뒤 단계를 돌렸습니다"


# ─────────────────── 합성 payload 로 훅 실행 ───────────────────


def _hook_env(copy: Path, tmp_path: Path, session: str) -> dict[str, str]:
    # 훅은 환경으로 루트를 정한다. 마커도 세션마다 갈라 둔다 — 성공과 실패가 같은 마커를
    # 쓰면 뒤 호출이 앞 호출의 상태를 물려받는다
    return {
        "CLAUDE_PROJECT_DIR": str(copy),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / f"plugin-{session}"),
    }


def _payload(copy: Path, session: str, target: Path) -> str:
    return json.dumps(
        {
            "session_id": session,
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": str(target)},
        }
    )


def _wire_fast(copy: Path, script: Path, *, exit_code: int = 0) -> Path:
    target = copy / "tracked.txt"
    target.write_text("변경된 파일\n", encoding="utf-8")
    config = _config(copy)
    config["python"] = sys.executable
    config["quality"]["tracked_paths"] = ["tracked.txt"]
    config["quality"]["profiles"]["fast"] = {
        "triggers": ["post_change"],
        "stages": [_stage("fast", script)],
    }
    _write_config(copy, config)
    return target


def test_post_tool_use_payload_runs_the_installed_probe(tmp_path: Path, core: Path) -> None:
    script, trace = _probe(tmp_path, "hookok")
    target = _wire_fast(core, script)

    done = _run(
        core / AUTO_TEST_HOOK,
        cwd=core,
        env_extra=_hook_env(core, tmp_path, "ok-session"),
        stdin=_payload(core, "ok-session", target),
    )

    assert done.returncode == 0, done.stdout + done.stderr
    assert trace.is_file(), "훅이 사본의 Profile 을 돌리지 않았습니다"
    seen = json.loads(trace.read_text(encoding="utf-8"))
    assert Path(seen["cwd"]) == core


# 실패는 **훅 프로토콜**로 드러난다 — `block()` 의 종료 2 와 stderr 다. 수동 CLI 의 stage
# 실패(종료 1)와 다른 자리이므로 섞어 읽지 않는다
def test_failing_fast_blocks_with_exit_two(tmp_path: Path, core: Path) -> None:
    script, trace = _probe(tmp_path, "hookbad", exit_code=5)
    target = _wire_fast(core, script)

    done = _run(
        core / AUTO_TEST_HOOK,
        cwd=core,
        env_extra=_hook_env(core, tmp_path, "bad-session"),
        stdin=_payload(core, "bad-session", target),
    )

    assert trace.is_file(), "probe 가 돌지 않았으면 차단의 근거가 없다"
    assert done.returncode == 2, (
        f"훅 차단은 종료 2 다. 받은 값: {done.returncode}\n{done.stdout}\n{done.stderr}"
    )
    assert "Fast" in done.stderr, done.stderr


# ───────────────────────── 깨진 배선 ─────────────────────────


def test_broken_hook_path_makes_the_copy_doctor_fail(tmp_path: Path, core: Path) -> None:
    source_hook = REPO / ".claude" / "harness" / "hooks" / "heredoc_write_check.py"
    before = _digests([source_hook])

    copied_hook = core / ".claude" / "harness" / "hooks" / "heredoc_write_check.py"
    assert copied_hook.is_file(), "배선 대상이 사본에 없으면 이 검사는 의미가 없다"

    # **정상 사본과 대조한다.** 깨뜨린 뒤의 종료 1 만 보면, 사본이 원래부터 1 이었는지
    # 이 변경 때문에 1 이 됐는지 알 수 없다
    healthy = _run(core / DOCTOR, cwd=core)
    assert healthy.returncode == 0, healthy.stdout + healthy.stderr

    copied_hook.unlink()

    done = _run(core / DOCTOR, cwd=core)
    output = done.stdout + done.stderr

    assert done.returncode == 1, output[-600:]
    assert "FAIL" in output
    assert "heredoc_write_check.py" in output
    # 사본을 망가뜨린 것이 소스를 건드리지 않았다
    assert _digests([source_hook]) == before


# ─────────────────────── 기존 대상 보호 ───────────────────────


def test_existing_target_is_refused_and_sentinels_survive(tmp_path: Path) -> None:
    dest = tmp_path / "already"
    (dest / ".claude").mkdir(parents=True)
    sentinels = {
        dest / ".claude" / "harness.json": '{"schema_version": 2, "sentinel": "설정"}\n',
        dest / ".claude" / "settings.json": '{"sentinel": "규칙"}\n',
        dest / "README.md": "사람이 쓴 문서\n",
    }
    for path, text in sentinels.items():
        path.write_text(text, encoding="utf-8")
    before = _digests(list(sentinels))

    done = subprocess.run(
        [sys.executable, str(EXPORTER), "--dest", str(dest)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert done.returncode == 2, done.stdout + done.stderr
    assert _digests(list(sentinels)) == before, "거부했는데 기존 파일이 바뀌었습니다"
    for path, text in sentinels.items():
        assert path.read_text(encoding="utf-8") == text


# ───────────────────── 설치된 수집기 실행 ─────────────────────


# `--root` 를 명시한다. 이 수집기는 환경·cwd 로 루트를 정하고 **자기 배치 fallback 이
# 없어서**, 외부 cwd 에서 환경변수 없이 부르면 종료 2 로 죽는다(실측 2026-11-25)
def test_installed_openwork_reports_empty_then_collects_one(core: Path) -> None:
    empty = _run(core / OPENWORK, "--flat", "--root", str(core), cwd=core)
    assert empty.returncode == 0, empty.stdout + empty.stderr
    first = json.loads(empty.stdout)
    assert Path(first["root"]) == core, "사본이 아닌 프로젝트를 읽었습니다"
    assert first["items"] == []
    assert first["warnings"], "빈 정보원인데 경고가 없습니다"

    bullet = "재순위화 임계값을 정해야 한다"
    folder = core / ".claude" / "wiki" / "followups"
    folder.mkdir(parents=True)
    (folder / "search.md").write_text(f"# 검색\n\n## 남은 일\n\n- {bullet}\n", encoding="utf-8")
    config = _config(core)
    config["checks"]["openwork"]["sources"] = [
        {
            "folder": "followups",
            "heading": "남은 일",
            "kind": "followup",
            "file_is_feature": True,
        }
    ]
    _write_config(core, config)

    filled = _run(core / OPENWORK, "--flat", "--root", str(core), cwd=core)
    assert filled.returncode == 0, filled.stdout + filled.stderr
    second = json.loads(filled.stdout)

    assert len(second["items"]) == 1, json.dumps(second, ensure_ascii=False)[:600]
    body = json.dumps(second["items"], ensure_ascii=False)
    assert bullet in body, body
    assert "search" in body, "항목의 출처 파일을 알 수 없습니다"


# 노트 문법이 어긋나면 수집기는 **종료 0 으로 0 건**을 낸다. 그래서 개수와 본문을 단언한다 —
# 종료 코드와 JSON 파싱만 보면 잘못된 fixture 가 초록으로 지나간다(실측 2026-11-25)
@pytest.mark.parametrize(
    ("packs", "name"), [(("interview",), "iv"), (("rag", "interview"), "both")]
)
def test_installed_quiz_collects_known_counts(
    tmp_path: Path, packs: tuple[str, ...], name: str
) -> None:
    copy = _export(tmp_path / name, *packs)
    notes = tmp_path / "notes"
    notes.mkdir()
    first = "재순위화가 필요한 이유는?"
    (notes / "unit.md").write_text(
        f"# 면접 노트\n\n## Q. {first}\n\n재현율과 정확도가 갈린다.\n\n"
        "## ★ Q. 벡터 인덱스의 trade-off 는?\n\n메모리와 지연의 교환이다.\n",
        encoding="utf-8",
    )

    done = _run(
        copy / QUIZ,
        cwd=copy,
        env_extra={"CLAUDE_PROJECT_DIR": str(copy), "QUIZ_NOTE_DIR": str(notes)},
    )

    assert done.returncode == 0, done.stdout + done.stderr
    seen = json.loads(done.stdout)
    assert seen["counts"]["questions"] == 2, done.stdout[:400]
    assert seen["counts"]["starred"] == 1
    assert seen["selected"] == 2
    texts = [item["question"] for item in seen["questions"]]
    assert first in texts, texts
    assert {item["file"] for item in seen["questions"]} == {"unit"}


# ─────────────────── 소스 import 경로 도움 없음 ───────────────────


# 위 검사들이 「설치물이 돈다」를 재려면 **소스의 hooks·scripts 가 자식의 import 경로에
# 없어야** 한다. `conftest.py` 는 그 둘을 이 프로세스의 `sys.path` 에 넣으므로, 그것이
# 자식에게 새지 않는다는 것을 여기서 못 박는다
def test_children_get_no_source_harness_on_sys_path(core: Path) -> None:
    done = subprocess.run(
        [sys.executable, "-c", "import json, sys; print(json.dumps(sys.path))"],
        cwd=str(core),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
    )
    assert done.returncode == 0, done.stdout + done.stderr

    source_harness = REPO / ".claude"
    leaked = [
        item
        for item in json.loads(done.stdout)
        if item and Path(item).is_absolute() and Path(item).is_relative_to(source_harness)
    ]
    assert not leaked, f"소스 하네스 경로가 자식에게 샜습니다: {leaked}"
