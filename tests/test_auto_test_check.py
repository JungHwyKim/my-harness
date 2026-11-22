"""자동 테스트 훅의 판정과 **매핑 커버리지**를 검사한다.

앞쪽은 경로 -> 테스트 대상 매핑이 맞는지 본다. 뒤쪽(커버리지)이 이 파일의 진짜 이유다.

새 파이프라인 단계를 만들고 `auto_test_check.py` 의 매핑 표에 줄을 추가하지 않으면,
**그 단계만 자동 테스트가 한 번도 안 도는데 아무 에러도 안 난다.** 훅들이 공통으로
두려워하는 실패 모드이고(`test_hook_wiring.py` 모듈 docstring), CLAUDE.md 에 한 줄 적어
두는 것으로는 못 막는다 — `paid_test_check.py` 가 그 교훈을 남겼다. 그래서 배선 테스트와
같은 모양의 짝을 여기 둔다.

  test_every_hook_script_is_wired  <->  test_every_stage_is_mapped
  test_wired_scripts_exist         <->  test_mapped_targets_exist
  LIBRARY_MODULES                  <->  UNMAPPED_BY_DESIGN
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import _hookutil
import auto_test_check
import pytest

# tests/ -> 플러그인 저장소 뿌리. 훅은 플러그인 안에 산다
REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / ".claude" / "harness" / "hooks"

# 아래 픽스처가 임시 프로젝트로 갈아끼운다
PROJECT_ROOT = REPO_ROOT

# 매핑 판정을 재기 위한 설정. 원 저장소 표의 **모양**만 가져온 것이고 전부가 아니다 —
# 여기서 재는 것은 «표가 맞나» 가 아니라 «표를 어떻게 읽나» 다
AUTO_TEST_CONFIG = {
    "source_prefixes": ["rag_pipeline/", "backend/", "evaluation/"],
    "checks": {
        "auto_test": {
            "mappings": [
                {
                    "path": "rag_pipeline/ingestion/loader/document/",
                    "tests": "tests/ingestion/loader/document",
                },
                {
                    "path": "rag_pipeline/ingestion/loader/content/",
                    "tests": "tests/ingestion/loader/content",
                },
                {"path": "rag_pipeline/ingestion/loader/", "tests": "tests/ingestion/loader"},
                {"path": "rag_pipeline/ingestion/cleaner/", "tests": "tests/ingestion/cleaner"},
                {
                    "path": "rag_pipeline/ingestion/pipeline.py",
                    "tests": "tests/ingestion/test_pipeline.py",
                },
                {"path": "rag_pipeline/query.py", "tests": "tests/test_query.py"},
                {"path": "rag_pipeline/runtime.py", "tests": "tests/test_runtime.py"},
                {"path": "backend/", "tests": "tests/api"},
                {"path": "evaluation/", "tests": "tests/evaluation"},
            ],
            "unmapped_by_design": {
                "rag_pipeline/config.py": "전 영역에 영향을 주므로 부분 실행이 무의미하다",
            },
        }
    },
}


# **설정이 없으면 매핑표가 비어 있고, 그러면 이 파일의 단정이 전부 «None 이 맞다» 로
# 통과한다** — 검사가 있는 줄 알았는데 없는 그 상태다. 그래서 모듈 전체가 설정을 깔고 시작한다
@pytest.fixture(autouse=True)
def _auto_test_config(load_hook, monkeypatch: pytest.MonkeyPatch) -> None:
    _, root = load_hook("auto_test_check", AUTO_TEST_CONFIG)
    monkeypatch.setattr(sys.modules[__name__], "PROJECT_ROOT", root)


# 소스 경로가 그 영역의 테스트로 간다
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("rag_pipeline/ingestion/cleaner/headers.py", "tests/ingestion/cleaner"),
        ("rag_pipeline/ingestion/loader/registry.py", "tests/ingestion/loader"),
        ("backend/app/api/routes/documents.py", "tests/api"),
        # **한때 `.claude/hooks/` → `tests/hooks` 가 여기 있었다.** 훅이 플러그인으로
        # 나가면서 프로젝트에 그 폴더가 없다. 자리를 지키는 것은 평가 하네스다 —
        # 거기가 어긋나면 그럴듯한 숫자가 계속 나온다는 점이 같다
        ("evaluation/scoring.py", "tests/evaluation"),
        ("rag_pipeline/ingestion/pipeline.py", "tests/ingestion/test_pipeline.py"),
        # **최상위 모듈은 커버리지 테스트가 안 잡는다** — 저쪽은 ingestion/ 아래 디렉터리만
        # 훑는다. 그래서 이 둘은 여기서 직접 못 박아야 조용히 빠지는 것을 막는다
        ("rag_pipeline/query.py", "tests/test_query.py"),
        ("rag_pipeline/runtime.py", "tests/test_runtime.py"),
    ],
)
def test_source_maps_to_area(source: str, expected: str):
    assert auto_test_check.test_target_for(source) == expected


# 더 깊은 접두사가 이겨야 한다. loader/document 가 loader 로 떨어지면 6배 넓게 돈다
def test_longest_prefix_wins():
    assert (
        auto_test_check.test_target_for("rag_pipeline/ingestion/loader/document/hwpx.py")
        == "tests/ingestion/loader/document"
    )
    assert (
        auto_test_check.test_target_for("rag_pipeline/ingestion/loader/content/router.py")
        == "tests/ingestion/loader/content"
    )


# 전 영역에 영향을 주는 것은 부분 실행이 무의미하다. Stop 게이트가 전체로 잡아야 한다
@pytest.mark.parametrize(
    "source",
    [
        "rag_pipeline/config.py",
        "rag_pipeline/exceptions.py",
        "rag_pipeline/schemas/document.py",
        "tests/conftest.py",
    ],
)
def test_broad_impact_is_not_scoped(source: str):
    assert auto_test_check.test_target_for(source) is None


# 테스트 파일을 직접 고치면 그 파일만 돌린다 — 제일 좁고 제일 빠르다
def test_editing_a_test_file_runs_that_file():
    rel = "tests/ingestion/cleaner/test_characters.py"
    assert auto_test_check.test_target_for(rel) == rel


# `tests/` 아래의 .py 가 아닌 것은 대상이 아니다.
#
# 이름이 `test_` 로 시작한다는 이유로 `__pycache__` 의 .pyc 가 pytest 대상이 된 적이 있다.
# pytest 는 .pyc 를 수집하지 못해 exit 4 로 죽고, 게이트는 «검사가 실패했다» 로 보인다 —
# 고칠 코드가 없는데 모든 도구 호출마다 빨개지므로 SKIP_AUTOTEST=1 이 습관이 된다
# (2026-11-18 실측: .pyc 15개). 산물 제외는 `_hookutil` 쪽이 먼저 막고 이것이 두 번째 선이다
@pytest.mark.parametrize(
    "path",
    [
        "tests/__pycache__/test_characters.cpython-312-pytest-9.2.0.pyc",
        "tests/__pycache__/test_characters.cpython-311.pyc",
        "tests/fixtures/test_sample.json",
        "tests/test_characters.pyc",
    ],
)
def test_non_python_under_tests_is_not_a_target(path: str):
    assert auto_test_check.test_target_for(path) is None


# 코드가 아닌 것에는 아무것도 안 돌린다. 문서를 고칠 때마다 테스트가 돌면 못 쓴다
@pytest.mark.parametrize(
    "path",
    [
        "CLAUDE.md",
        # 소스 폴더 **안**의 `.md` 는 `SOURCE_PREFIXES` 에 걸리고 이름이 아니라 `.py` 필터로만
        # 빠진다. 느슨해지면 문서를 고칠 때마다 그 영역 테스트가 도는데, 위 문단이 말하는
        # "못 쓴다"가 바로 그 상태다. **이 경로는 지금 실재하지 않는다** — 2026-08-31 에
        # 폴더별 `CLAUDE.md` 를 두었다가 2026-09-01 에 되돌렸다. 케이스를 남기는 것은
        # 파일이 있어서가 아니라 **필터가 이름이 아니라 확장자로 걸러야 하기 때문**이다
        "rag_pipeline/ingestion/loader/CLAUDE.md",
        ".claude/wiki/plan_log/하네스-확장.md",
        ".claude/wiki/task_log/phase1.md",
        "regression/baseline.json",
        ".claude/skills/rag-code-review/SKILL.md",
    ],
)
def test_non_source_maps_to_nothing(path: str):
    assert auto_test_check.test_target_for(path) is None


# 저장소 밖 경로(스크래치패드 등)는 우리가 볼 것이 아니다
def test_outside_repo_is_ignored(tmp_path: Path):
    assert auto_test_check.test_target_for(str(tmp_path / "scratch.py")) is None


# 절대 경로로 와도 같은 결과여야 한다. 훅 입력의 file_path 는 절대 경로다
def test_absolute_path_is_normalized():
    absolute = str(PROJECT_ROOT / "rag_pipeline" / "ingestion" / "cleaner" / "whitespace.py")
    assert auto_test_check.test_target_for(absolute) == "tests/ingestion/cleaner"


# 한국어 경로가 깨지지 않아야 한다. 이 저장소는 한국어 파일명이 흔하다
def test_korean_path_does_not_crash():
    assert auto_test_check.test_target_for(".claude/wiki/plan_log/평가-세트.md") is None
    assert auto_test_check.test_target_for("tests/fixtures/시행령 개정안.hwpx") is None


# 빈 입력에 죽지 않는다. 판단이 안 서면 막지 않는 것이 훅 전체의 규약이다
@pytest.mark.parametrize("raw", ["", "   "])
def test_empty_path_is_ignored(raw: str):
    assert auto_test_check.test_target_for(raw) is None


# ---- 매핑 커버리지 ----


# **커버리지 검사 셋은 여기서 못 잰다 — 프로젝트로 갔다.**
#
# 「만들어 놓고 매핑을 잊은 단계가 없나」 · 「매핑 대상이 실재하나」 ·
# 「일부러 안 매핑한 경로가 실재하나」 셋은 **훅의 동작이 아니라 그 프로젝트의 설정이
# 맞나**다. 임시 프로젝트를 만들어 재면 «내가 넣은 것이 있다» 를 재는 꼴이라 아무것도 안 지킨다.
#
# 게다가 이 셋은 설정이 없을 때 **빈 표를 훑어 조용히 통과한다** — 옮기지 않고 두면
# 초록인 채로 아무것도 안 지키는, 이 저장소가 제일 두려워하는 모양이 된다.
# 지금은 `agentic-rag-proj/tests/harness/test_harness_config.py` 가 잰다.
#
# 여기 남은 것은 **표를 어떻게 읽나** 뿐이다 — 최장 접두사, 절대 경로, 미매핑 우선.


# 설정이 없으면 아무 대상도 안 나온다. 없는 폴더에 pytest 를 거는 것보다 안 도는 쪽이 낫다
def test_without_config_nothing_is_mapped(load_hook):
    module, _ = load_hook("auto_test_check", None)

    assert module.test_target_for("rag_pipeline/ingestion/cleaner/headers.py") is None
    assert module._MAPPINGS == ()


# ---- 종료코드 판정 ----


# pytest 종료코드 5 는 "수집된 테스트가 없음"이지 실패가 아니다. 실패로 보면
# integration 전용 파일을 고칠 때마다 훅이 막는다 — addopts 가 전부 deselect 해서 5가 난다
def test_no_tests_collected_is_not_a_failure():
    assert 5 in auto_test_check._OK_RETURNCODES
    assert 0 in auto_test_check._OK_RETURNCODES
    # 진짜 실패(1)와 사용 오류(4)는 통과시키면 안 된다
    assert 1 not in auto_test_check._OK_RETURNCODES
    assert 4 not in auto_test_check._OK_RETURNCODES


# ---- 루프 방지 ----


# session_id 가 없으면 "세션당 한 번"을 보장할 수 없다. 그때는 반드시 통과해야 한다.
# 여기서 막으면 종료코드 2 가 대화를 이어가 영원히 안 끝난다
def test_stop_without_session_id_passes(monkeypatch):
    called: list[str] = []
    monkeypatch.setattr(
        auto_test_check, "_run_pytest", lambda *a, **k: called.append("ran") or (True, "")
    )

    auto_test_check._handle_stop({"hook_event_name": "Stop"})

    assert called == [], "session_id 가 없는데 테스트를 돌렸다 = 루프 위험"


# stop_hook_active 가 들어오면 존중한다. 마커가 주 안전장치이고 이건 덤이다
def test_stop_respects_stop_hook_active(monkeypatch):
    called: list[str] = []
    monkeypatch.setattr(
        auto_test_check, "_run_pytest", lambda *a, **k: called.append("ran") or (True, "")
    )

    auto_test_check._handle_stop({"stop_hook_active": True, "session_id": "abc"})

    assert called == []


# 탈출구가 실제로 통하는지. 문서에만 있고 안 통하면 사용자가 갇힌다
def test_skip_env_disables_everything(monkeypatch):
    called: list[str] = []
    monkeypatch.setenv("SKIP_AUTOTEST", "1")
    monkeypatch.setattr(
        auto_test_check._hookutil,
        "read_payload",
        lambda: {"hook_event_name": "Stop", "session_id": "abc"},
    )
    monkeypatch.setattr(
        auto_test_check, "_run_pytest", lambda *a, **k: called.append("ran") or (True, "")
    )

    auto_test_check.main()

    assert called == []


# --- file_path 가 없는 도구(Bash)로 고친 경우 ---
#
# 기록 훅이 2026-08-19 에 겪은 것과 같은 구멍인데 **방향이 반대다.** 저쪽은 오탐(막힘)이라
# 눈에 띄었지만 여기는 조용히 아무 검사도 안 돈다. auto mode 에서는 Bash 편집이 기본이다.


# Bash 로 소스를 고치면 tool_input 에 file_path 가 없다. 그래도 영역을 찾아야 한다
def test_bash_edit_is_mapped_by_filesystem(tmp_path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    stage = tmp_path / "rag_pipeline" / "ingestion" / "cleaner"
    stage.mkdir(parents=True)
    monkeypatch.setattr(_hookutil, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(auto_test_check, "PROJECT_ROOT", tmp_path)

    session = "sess-bash-edit"
    _hookutil.mark_session_start(session)
    time.sleep(0.01)
    (stage / "characters.py").write_text("# 고쳤다\n", encoding="utf-8")

    targets = auto_test_check._targets_for_call({"tool_input": {"command": "sed -i ..."}}, session)

    assert targets == [auto_test_check.test_target_for("rag_pipeline/ingestion/cleaner/x.py")]


# 아무것도 안 고쳤으면 돌릴 것이 없다. Bash 호출마다 테스트가 돌면 안 된다
def test_bash_call_without_edit_runs_nothing(tmp_path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "rag_pipeline").mkdir()
    monkeypatch.setattr(_hookutil, "PROJECT_ROOT", tmp_path)

    session = "sess-bash-noop"
    _hookutil.mark_session_start(session)

    assert (
        auto_test_check._targets_for_call({"tool_input": {"command": "git status"}}, session) == []
    )


# file_path 가 있으면 종전대로 그것 하나만 본다. 파일시스템을 훑지 않는다
def test_write_edit_still_uses_file_path(tmp_path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(_hookutil, "PROJECT_ROOT", tmp_path)

    payload = {"tool_input": {"file_path": "rag_pipeline/ingestion/cleaner/characters.py"}}

    assert auto_test_check._targets_for_call(payload, "sess-write") == [
        auto_test_check.test_target_for("rag_pipeline/ingestion/cleaner/characters.py")
    ]


# ---- schema_version 2: 언어에 종속되지 않는 Quality Gate ----


V2_QUALITY_CONFIG = {
    "schema_version": 2,
    "wiki_root": ".claude/wiki/",
    "source_prefixes": ["src/"],
    "history": {
        "plan": "history/plan/",
        "task": "history/task/",
        "verify": "history/verify/",
        "tracked_paths": ["src/"],
    },
    "quality": {
        "tracked_paths": ["src/", ".claude/harness.json"],
        "mappings": [{"path": "src/", "tests": "tests/"}],
        "profiles": {"fast": {"stages": []}, "full": {"stages": []}},
    },
}


def test_v2_mapping_accepts_non_python_sources(load_hook) -> None:
    module, _ = load_hook("auto_test_check", V2_QUALITY_CONFIG)

    assert module.test_target_for("src/app.ts") == "tests/"


def test_v2_direct_change_uses_quality_tracked_paths(load_hook) -> None:
    module, _ = load_hook("auto_test_check", V2_QUALITY_CONFIG)
    payload = {"tool_input": {"file_path": ".claude/harness.json"}}

    assert module._changed_files_for_call(payload, "v2-direct") == [".claude/harness.json"]


def test_v2_ignores_direct_change_outside_quality_scope(load_hook) -> None:
    module, _ = load_hook("auto_test_check", V2_QUALITY_CONFIG)
    payload = {"tool_input": {"file_path": "docs/notes.md"}}

    assert module._changed_files_for_call(payload, "v2-outside") == []


# ---- 경로 분류: `None` 하나로는 못 가르는 네 가지 ----

# 이 저장소의 실제 설정과 **같은 모양**이다. `.claude/settings.json` 을 일부러 매핑 없이
# 추적만 해 둔 것이 요점이다 — 그 자리가 「매핑 누락」이고, 나머지는 전부 정상이다
V2_CLASSIFY_CONFIG = {
    "schema_version": 2,
    "wiki_root": ".claude/wiki/",
    "source_prefixes": [".claude/harness/", "tests/"],
    "history": {
        "plan": "history/plan/",
        "task": "history/task/",
        "verify": "history/verify/",
        "tracked_paths": [".claude/harness/"],
    },
    "quality": {
        "tracked_paths": [
            ".claude/harness/",
            "tests/",
            ".claude/settings.json",
            ".github/workflows/",
        ],
        "mappings": [{"path": ".claude/harness/", "tests": "tests/"}],
        "unmapped_by_design": {
            ".github/workflows/": "Python 테스트로 hosted CI 실행을 증명할 수 없다",
        },
        "profiles": {
            "fast": {
                "triggers": ["post_change"],
                "stages": [
                    {
                        "id": "test",
                        "argv": ["{python}", "-m", "pytest", "{mapped_targets}", "-q"],
                        "timeout": 90,
                        "success_codes": [0],
                    }
                ],
            },
            "full": {
                "triggers": ["stop"],
                "stages": [{"id": "test", "argv": ["{python}", "-m", "pytest", "-q"]}],
            },
        },
    },
}


# 원인마다 다른 판정이 나와야 한다. **표가 아니라 이 단정이 계약이다** —
# 여섯 줄 중 하나라도 `unmapped` 로 떨어지면 평범한 파일에 설정 결함 판정이 붙는다
@pytest.mark.parametrize(
    ("path", "cause", "target"),
    [
        (".claude/harness/hooks/_quality.py", "target", "tests/"),
        (".claude/harness/scripts/doctor.py", "target", "tests/"),
        ("tests/test_doctor.py", "target", "tests/test_doctor.py"),
        ("tests/conftest.py", "target", "tests/"),
        ("tests/_escape_hatches.py", "target", "tests/"),
        ("tests/fixtures/a.json", "non_python_test", None),
        ("tests/__pycache__/x.pyc", "artifact", None),
        (".github/workflows/harness-quality.yml", "excluded", None),
        ("docs/notes.md", "untracked", None),
        (".claude/settings.json", "unmapped", None),
    ],
)
def test_classify_separates_the_causes(load_hook, path, cause, target) -> None:
    module, _ = load_hook("auto_test_check", V2_CLASSIFY_CONFIG)

    row = module.classify(path)

    assert row.cause == cause, f"{path}: {row.cause} — {row.reason}"
    assert row.target == target
    assert row.reason or row.cause == "target"


# 생성물이 비추적·테스트 특례보다 먼저 걸러져야 한다. `tests/__pycache__/x.pyc` 는 추적
# 경로 **안**이라, 순서가 뒤집히면 비Python 파일이나 매핑 누락으로 떨어진다
def test_artifact_wins_over_the_test_special_case(load_hook) -> None:
    module, _ = load_hook("auto_test_check", V2_CLASSIFY_CONFIG)

    assert module.classify("tests/__pycache__/conftest.pyc").cause == "artifact"
    assert module.classify(".ruff_cache/x.json").cause == "artifact"


# 루트 밖은 사용 오류 쪽이다. 매핑이 없다는 말로 보고하면 고칠 곳을 잘못 가리킨다
def test_classify_reports_paths_outside_the_root(load_hook, tmp_path) -> None:
    module, _ = load_hook("auto_test_check", V2_CLASSIFY_CONFIG)

    assert module.classify(str(tmp_path / "바깥.py")).cause == "outside"


# `{mapped_targets}` 를 쓰지 않는 Profile 에서는 매핑이 없는 것이 결함이 아니다
def test_mapping_is_not_required_when_the_profile_does_not_use_targets(load_hook) -> None:
    module, _ = load_hook("auto_test_check", V2_CLASSIFY_CONFIG)

    row = module.classify(".claude/settings.json", mapping_required=False)

    assert row.cause == "no_mapping_needed"


# ---- 매핑 누락 알림: 막지 않고, 세션당 한 번 ----


# `run_profile` 을 갈아끼워 실제 pytest 를 돌리지 않는다. 여기서 재는 것은 **무엇을
# 대상으로 넘겼나**와 **알렸나**이고, pytest 가 통과하는지는 이 테스트의 관심이 아니다
@pytest.fixture
def fake_profile(monkeypatch: pytest.MonkeyPatch):
    import _quality

    calls: list[dict] = []

    def fake(name, *, changed_files=(), mapped_targets=()):
        calls.append(
            {"name": name, "changed": tuple(changed_files), "targets": tuple(mapped_targets)}
        )
        return ()

    monkeypatch.setattr(_quality, "run_profile", fake)
    return calls


def test_unmapped_tracked_file_is_announced_without_blocking(
    load_hook, fake_profile, capsys
) -> None:
    module, _ = load_hook("auto_test_check", V2_CLASSIFY_CONFIG)
    payload = {"tool_input": {"file_path": ".claude/settings.json"}}

    # 막지 않는다 — 예외도 SystemExit 도 없이 돌아온다
    module._handle_v2_post_tool_use(payload, "notice-1")

    out = capsys.readouterr().out
    assert "systemMessage" in out
    assert ".claude/settings.json" in out
    assert "quality.mappings" in out and "unmapped_by_design" in out


def test_the_notice_is_once_per_session(load_hook, fake_profile, capsys) -> None:
    module, _ = load_hook("auto_test_check", V2_CLASSIFY_CONFIG)
    payload = {"tool_input": {"file_path": ".claude/settings.json"}}

    module._handle_v2_post_tool_use(payload, "notice-2")
    capsys.readouterr()
    module._handle_v2_post_tool_use(payload, "notice-2")

    assert capsys.readouterr().out == ""


def test_a_new_session_is_told_again(load_hook, fake_profile, capsys) -> None:
    module, _ = load_hook("auto_test_check", V2_CLASSIFY_CONFIG)
    payload = {"tool_input": {"file_path": ".claude/settings.json"}}

    module._handle_v2_post_tool_use(payload, "notice-3")
    capsys.readouterr()
    module._handle_v2_post_tool_use(payload, "notice-4")

    assert "systemMessage" in capsys.readouterr().out


# 이유를 적어 둔 제외는 알리지 않는다. 알리면 설정이 맞는데도 매 세션 같은 줄이 붙는다
def test_intentional_exclusion_is_silent(load_hook, fake_profile, capsys) -> None:
    module, _ = load_hook("auto_test_check", V2_CLASSIFY_CONFIG)
    payload = {"tool_input": {"file_path": ".github/workflows/harness-quality.yml"}}

    module._handle_v2_post_tool_use(payload, "notice-5")

    assert capsys.readouterr().out == ""
    assert fake_profile == [], "제외만 있으면 stage 를 돌릴 것이 없다"


# 유효한 대상이 함께 있으면 알린 **뒤에도** 그 검사는 돈다. 알림이 검사를 삼키면
# 매핑 하나가 빠진 것 때문에 나머지 검사가 통째로 멈춘다
def test_a_valid_target_still_runs_after_the_notice(load_hook, fake_profile, capsys) -> None:
    module, _ = load_hook("auto_test_check", V2_CLASSIFY_CONFIG)

    module._handle_v2_post_tool_use(
        {"tool_input": {"file_path": ".claude/settings.json"}}, "notice-6"
    )
    module._handle_v2_post_tool_use(
        {"tool_input": {"file_path": ".claude/harness/hooks/_quality.py"}}, "notice-6"
    )

    assert "systemMessage" in capsys.readouterr().out
    assert fake_profile == [
        {
            "name": "fast",
            "changed": (".claude/harness/hooks/_quality.py",),
            "targets": ("tests/",),
        }
    ]


# ---- 분류가 실행 입력을 정한다: `{changed_files}` 만 쓰는 Fast ----

# 매핑을 **요구하지 않는** Profile. 「매핑이 필요한가」만으로 실행 여부를 정하던 동안,
# 이 설정에서는 정책상 제외한 파일까지 그대로 stage 인자로 넘어가 실행됐다
V2_CHANGED_ONLY_CONFIG = {
    **V2_CLASSIFY_CONFIG,
    "quality": {
        **V2_CLASSIFY_CONFIG["quality"],
        "profiles": {
            "fast": {
                "triggers": ["post_change"],
                "stages": [{"id": "test", "argv": ["{python}", "-m", "probe", "{changed_files}"]}],
            },
            "full": {
                "triggers": ["stop"],
                "stages": [{"id": "test", "argv": ["{python}", "-m", "probe"]}],
            },
        },
    },
}


def payload_for(rel: str) -> dict:
    return {"tool_input": {"file_path": rel}}


@pytest.mark.parametrize(
    ("path", "label"),
    [
        (".github/workflows/x.yml", "사유 있는 제외"),
        ("tests/__pycache__/x.pyc", "생성물"),
        ("tests/fixtures/a.json", "비Python 테스트 파일"),
    ],
)
def test_hook_runs_nothing_for_excluded_input(load_hook, fake_profile, path, label) -> None:
    module, _ = load_hook("auto_test_check", V2_CHANGED_ONLY_CONFIG)

    module._handle_v2_post_tool_use(payload_for(path), f"changed-only-{label}")

    assert fake_profile == [], f"{label}인데 stage 를 불렀다"


def test_hook_runs_with_the_valid_file(load_hook, fake_profile) -> None:
    module, _ = load_hook("auto_test_check", V2_CHANGED_ONLY_CONFIG)

    module._handle_v2_post_tool_use(payload_for(".claude/harness/hooks/_quality.py"), "co-valid")

    assert fake_profile == [
        {
            "name": "fast",
            "changed": (".claude/harness/hooks/_quality.py",),
            "targets": ("tests/",),
        }
    ]


# 매핑이 필요 없는 정상 추적 파일은 실행된다 — 매핑 부재만으로 건너뛰지 않는다
def test_hook_runs_a_tracked_file_that_needs_no_mapping(load_hook, fake_profile) -> None:
    module, _ = load_hook("auto_test_check", V2_CHANGED_ONLY_CONFIG)

    module._handle_v2_post_tool_use(payload_for(".claude/settings.json"), "co-nomap")

    assert fake_profile == [{"name": "fast", "changed": (".claude/settings.json",), "targets": ()}]


# ---- 사유 없는 제외 ----


def test_an_exclusion_without_a_reason_is_a_problem(load_hook, fake_profile, capsys) -> None:
    config = {
        **V2_CLASSIFY_CONFIG,
        "quality": {**V2_CLASSIFY_CONFIG["quality"], "unmapped_by_design": {"tests/": ""}},
    }
    module, _ = load_hook("auto_test_check", config)

    row = module.classify("tests/fixtures/a.py")
    assert row.cause == module.CAUSE_EXCLUDED_NO_REASON
    assert "사유가 없습니다" in row.reason

    module._handle_v2_post_tool_use(payload_for("tests/fixtures/a.py"), "noreason")

    assert "systemMessage" in capsys.readouterr().out
    assert fake_profile == [], "사유 없는 제외는 유효한 제외가 아니므로 돌릴 것도 없다"


@pytest.mark.parametrize("why", ["", "   ", None, 42])
def test_every_empty_reason_shape_is_a_problem(load_hook, why) -> None:
    config = {
        **V2_CLASSIFY_CONFIG,
        "quality": {**V2_CLASSIFY_CONFIG["quality"], "unmapped_by_design": {"tests/": why}},
    }
    module, _ = load_hook("auto_test_check", config)

    assert module.classify("tests/fixtures/a.py").cause == module.CAUSE_EXCLUDED_NO_REASON


def test_a_real_reason_is_still_a_silent_exclusion(load_hook) -> None:
    module, _ = load_hook("auto_test_check", V2_CLASSIFY_CONFIG)

    row = module.classify(".github/workflows/x.yml")

    assert row.cause == module.CAUSE_EXCLUDED
    assert row.reason == "Python 테스트로 hosted CI 실행을 증명할 수 없다"


# **V1 목록형은 사유 자리가 아예 없었다.** 그 설정에서 사유 없음은 결함이 아니다 —
# 기존 동작을 깨지 않는다
def test_v1_list_exclusions_stay_valid(load_hook) -> None:
    v1_config = {
        "source_prefixes": ["src/"],
        "checks": {
            "auto_test": {
                "mappings": [{"path": "src/", "tests": "tests/"}],
                "unmapped_by_design": ["src/config.py"],
            }
        },
    }
    module, _ = load_hook("auto_test_check", v1_config)

    row = module.classify("src/config.py")

    assert row.cause == module.CAUSE_EXCLUDED
    assert module.test_target_for("src/config.py") is None


# 겹치는 제외 항목에서는 **최장 접두사**의 사유가 나온다. 설정 순서에 좌우되면
# 같은 파일이 실행마다 다른 사유로 보고될 수 있다
def test_the_longest_exclusion_prefix_supplies_the_reason(load_hook) -> None:
    config = {
        **V2_CLASSIFY_CONFIG,
        "quality": {
            **V2_CLASSIFY_CONFIG["quality"],
            "unmapped_by_design": {"tests/": "넓은 사유", "tests/fixtures/": "좁은 사유"},
        },
    }
    module, _ = load_hook("auto_test_check", config)

    assert module.classify("tests/fixtures/a.py").reason == "좁은 사유"
    assert module.classify("tests/다른.py").reason == "넓은 사유"
