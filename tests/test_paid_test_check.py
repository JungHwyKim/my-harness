"""`paid_test_check` 판정 회귀 테스트.

이 훅은 두 방향으로 다 틀릴 수 있고, 두 실패의 비용이 다르다.

  놓치면(false negative)  LlamaParse/OpenAI 에 실제 과금이 발생한다. 되돌릴 수 없다.
  헛막으면(false positive) `pytest -q` 나 `git commit -m "..."` 처럼 하루에 수십 번 쓰는
                          명령이 막힌다. 그러면 훅이 곧바로 무시당하고 탈출구가 상시
                          켜져서, 결국 첫 번째 실패까지 같이 열린다.

그래서 통과해야 하는 케이스를 차단 케이스만큼 촘촘히 박는다.

## 정책은 **임시 프로젝트**에서 받는다 — 이 저장소 설정을 읽지 않는다

한때 판정 테스트가 모듈 수준 임포트를 그대로 썼다. 그러면 `_PAID_MARKERS` 가 **이 저장소의**
`.claude/harness.json` 에서 온다. V2 로 옮기며 마커 목록이 프로젝트 설정으로 내려가고 템플릿은
`[]` 가 되자, 훅이 아무것도 감지하지 않는 것이 맞는 동작인데 테스트 12개는 `integration` 감지를
단언하고 있어 **같은 설정에서 서로 반대를 요구했다** — `test_v2_without_markers_disables_
expensive_guard` 가 바로 그 «빈 목록이면 감지하지 않는다» 를 재는 테스트다. 그래서 14개가
HEAD 에서 빨간 채로 커밋돼 있었다(2026-11-18 확인: 14실패·17통과).

고치는 방향은 저장소 설정에 마커를 넣는 것이 **아니다.** 템플릿에 제품 테스트가 없으므로
`[]` 가 맞다. 판정을 재려면 테스트가 자기 정책을 들고 와야 한다 — 그것이 `paid_hook` 이다.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import _hookutil
import paid_test_check
import pytest

HOOK_PATH = Path(paid_test_check.__file__)

# tests/ -> 저장소 뿌리. 아래 복원 픽스처가 쓴다
REPO_ROOT = Path(__file__).resolve().parents[1]


# 마커를 명시한 임시 V2 프로젝트의 설정. 스키마 필수 절만 채운다
def _v2_config(markers: list[str]) -> dict:
    return {
        "schema_version": 2,
        "wiki_root": ".claude/wiki/",
        "history": {
            "plan": "history/plan/",
            "task": "history/task/",
            "verify": "history/verify/",
            "tracked_paths": ["src/"],
        },
        "quality": {"profiles": {}},
        "checks": {
            "expensive_tests": {
                "pytest_markers": markers,
                "reason": "실제 비용이 발생한다",
            }
        },
    }


# `load_hook` 은 `_hookutil` 과 훅을 **전역으로** 다시 임포트한다. 그 상태는 테스트가 끝나도
# 남아서, 임시 프로젝트의 마커가 다음 테스트로 샌다 — 모듈 수준 임포트를 쓰는 테스트가
# 하나라도 있으면 그쪽이 조용히 다른 정책으로 돌아간다.
#
# **`monkeypatch` 를 받아 가는 것이 요점이다.** 그래야 이 픽스처가 monkeypatch 보다 **뒤에**
# 세워지고, 따라서 **먼저** 걷힌다. 순서가 뒤집히면 monkeypatch 가 CLAUDE_PROJECT_DIR 을
# 되돌린 뒤에 우리가 그 값을 다시 읽어, 복원이 엉뚱한 뿌리를 가리킨다
@pytest.fixture(autouse=True)
def _restore_module_state(monkeypatch: pytest.MonkeyPatch):
    yield
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(REPO_ROOT))
    importlib.reload(_hookutil)
    importlib.reload(paid_test_check)


# 마커 `[integration]` 이 설정된 임시 V2 프로젝트로 비용 훅을 로드한다.
#
# 모듈을 돌려주는 것만이 아니다 — `load_hook` 이 `CLAUDE_PROJECT_DIR` 도 그 프로젝트로
# 세우므로, 훅을 **프로세스로** 돌리는 아래 테스트들도 같은 정책을 물려받는다
@pytest.fixture
def paid_hook(load_hook):
    module, _root = load_hook("paid_test_check", _v2_config(["integration"]))
    return module


# 막아야 하는 명령
BLOCKED = [
    "pytest -m integration",
    r".\.venv\Scripts\python.exe -m pytest -m integration",
    'python -m pytest -m "integration"',
    "pytest -m 'not slow and integration' tests/",
    "pytest -m integration or unit",
    "uv run pytest -m integration",
    # 복합 명령의 뒤쪽만 유료인 경우
    "git add -A && pytest -m integration",
    "ruff check . ; pytest -m integration",
    # PowerShell 호출 연산자와 변수. 이 저장소의 명령 예시가 이 형태다
    "& $py -m pytest -m integration",
    '& "C:\\agentic-rag-proj\\.venv\\Scripts\\python.exe" -m pytest -m integration',
    # -m 을 안 쓰고 기본 제외를 날리는 우회
    "pytest -o addopts= tests/",
    'pytest --override-ini "addopts=" ',
    # **수집 전용 예외를 없앴다.** 수집만 하면 과금이 없는 것은 맞지만, 「진짜 옵션인가」를
    # 문자열로 가리려다 우회가 여덟 건 나왔다. 유료 마커를 고르는 명령은 `--collect-only`
    # 가 붙어도 묻는다 — 잃는 것은 수집만 해 보는 호출의 승인창 한 번이다
    "pytest --collect-only -m integration",
]

# 막으면 안 되는 명령
ALLOWED = [
    "pytest -q",
    r".\.venv\Scripts\python.exe -m pytest",
    "& $py -m pytest -q",
    # pyproject 기본값과 같은 안전한 호출. 이걸 막으면 훅이 통째로 무시당한다
    "pytest -m 'not integration'",
    'pytest -m "not slow and not integration"',
    "pytest -o \"addopts=-m 'not integration'\"",
    # -m 과 integration 이 둘 다 있지만 pytest 가 아니다
    'git commit -m "integration 테스트 추가"',
    'git commit -m "pytest integration marker 추가"',
    "echo integration",
    "python -m ruff check .",
    "pytest tests/ingestion/loader/document/test_pdf.py",
]


@pytest.mark.parametrize("command", BLOCKED)
def test_paid_commands_are_blocked(paid_hook, command: str):
    assert paid_hook.blocked_reason(command) is not None, command


@pytest.mark.parametrize("command", ALLOWED)
def test_safe_commands_pass(paid_hook, command: str):
    assert paid_hook.blocked_reason(command) is None, command


# 훅을 실제로 실행해 확인한다. 판정 함수가 맞아도 배선이 틀리면 아무 소용이 없다.
#
# `env` 를 안 주면 자식이 `os.environ` 을 물려받는다 — `load_hook` 이 거기에
# `CLAUDE_PROJECT_DIR` 을 심어 두므로 자식도 임시 프로젝트의 마커를 읽는다. `env` 를 직접
# 줄 때는 `dict(os.environ, ...)` 로 그 경로를 **보존해야 한다**. 통째로 갈아끼우면 자식이
# 다시 이 저장소(마커 `[]`)를 보고, 테스트가 재려던 판정이 일어나지 않는다
def _run_hook(
    command: str,
    *,
    raw: bytes | None = None,
    env: dict | None = None,
    mode: str | None = "default",
):
    if raw is not None:
        payload = raw
    else:
        body: dict = {"tool_input": {"command": command}}
        # `mode=None` 은 **필드를 아예 안 보내는** 경우다. 빈 문자열과 구분해야 한다 —
        # 훅은 둘 다 deny 로 보내지만, 사유 문구가 다르고 그 차이가 사용자가 보는 안내다
        if mode is not None:
            body["permission_mode"] = mode
        payload = json.dumps(body).encode()
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=payload,
        capture_output=True,
        timeout=30,
        env=env,
        check=False,
    )


# 승인창을 띄울 수 있는 모드에서는 PreToolUse ask 형식을 정확히 내야 한다.
# 형식이 틀리면 하네스가 조용히 무시하고, 그러면 승인 없이 실행된다
def test_ask_payload_shape(paid_hook):
    proc = _run_hook("pytest -m integration", mode="default")

    assert proc.returncode == 0
    output = json.loads(proc.stdout.decode("utf-8"))
    specific = output["hookSpecificOutput"]
    assert specific["hookEventName"] == "PreToolUse"
    assert specific["permissionDecision"] == "ask"
    reason = specific["permissionDecisionReason"]
    # 무엇 때문에 묻는지가 사유에 있어야 사용자가 판단할 수 있다
    assert "integration" in reason
    # 승인의 범위를 적어두지 않으면 한 번 승인하면 끝이라고 오해한다
    assert "이 도구 호출 하나" in reason
    assert "승인" in output["systemMessage"]
    # 우회 안내는 더 이상 없다
    assert "ALLOW_PAID_TESTS" not in reason


# 승인창을 기대할 수 없는 모드에서는 막는다. 여기서 ask 를 내면 그대로 실행될 수 있다
def test_deny_payload_shape_in_unsupported_mode(paid_hook):
    proc = _run_hook("pytest -m integration", mode="bypassPermissions")

    assert proc.returncode == 0
    specific = json.loads(proc.stdout.decode("utf-8"))["hookSpecificOutput"]
    assert specific["permissionDecision"] == "deny"
    assert "bypassPermissions" in specific["permissionDecisionReason"]


# 모드를 못 읽었으면 막는다. **기본이 deny 인 것을 재는 테스트다** — 뒤집히면
# 승인창이 없는 환경에서 그대로 실행되는데 아무 신호도 남지 않는다
@pytest.mark.parametrize("mode", [None, "", "엉뚱한모드", "DEFAULT"])
def test_unknown_or_missing_mode_denies(paid_hook, mode: str | None):
    proc = _run_hook("pytest -m integration", mode=mode)

    specific = json.loads(proc.stdout.decode("utf-8"))["hookSpecificOutput"]
    assert specific["permissionDecision"] == "deny", mode


# 모드 표 전체. 아는 모드만 ask 로 가고 나머지는 전부 deny 다
@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("default", "ask"),
        ("acceptEdits", "ask"),
        ("auto", "ask"),
        ("plan", "deny"),
        ("dontAsk", "deny"),
        ("bypassPermissions", "deny"),
    ],
)
def test_permission_mode_table(paid_hook, mode: str, expected: str):
    proc = _run_hook("pytest -m integration", mode=mode)

    specific = json.loads(proc.stdout.decode("utf-8"))["hookSpecificOutput"]
    assert specific["permissionDecision"] == expected, mode


# 통과할 때는 아무 말도 하지 않아야 한다. 빈 출력이 곧 '허용'이다
def test_safe_command_produces_no_output(paid_hook):
    proc = _run_hook("pytest -q")
    assert proc.returncode == 0
    assert proc.stdout.strip() == b""


# **환경변수 우회는 없어졌다.** 단순 삭제가 아니라 회귀 테스트로 남긴다 — 이름이 다시
# 살아나면 여기서 잡힌다.
#
# 옛 우회의 문제는 두 가지였다. 값이 비어 있지 않은지만 봤으므로 `=0` 도 통과했고, 한 번
# 켜면 **세션의 모든 유료 테스트가 열렸다.** 그래서 `1` 과 `0` 을 둘 다 재고, 예전에
# 프로젝트가 `allow_env` 로 지정할 수 있던 이름도 함께 재서 그쪽 경로도 죽었는지 본다.
#
# `dict(os.environ, ...)` 인 이유는 `_run_hook` 주석에 있다 — 임시 프로젝트 경로를 지키면서
# 변수만 더한다
@pytest.mark.parametrize(
    "env_pair",
    [
        ("ALLOW_PAID_TESTS", "1"),
        ("ALLOW_PAID_TESTS", "0"),
        ("PROJECT_DEFINED_ALLOW", "1"),
    ],
)
def test_env_bypass_is_gone(paid_hook, env_pair: tuple[str, str]):
    name, value = env_pair
    proc = _run_hook(
        "pytest -m integration",
        env=dict(os.environ, **{name: value}),
        mode="default",
    )

    specific = json.loads(proc.stdout.decode("utf-8"))["hookSpecificOutput"]
    assert specific["permissionDecision"] == "ask", env_pair


# BOM 이 붙은 입력도 판정돼야 한다.
# 이게 이 훅의 제일 위험한 실패 모드였다 — json.load 가 실패하면 "판단 근거 없음" 경로로
# 빠져 조용히 통과한다. 훅이 죽지도, 경고를 내지도 않아서 알아챌 방법이 없다.
# 실제로 PowerShell 5.1 의 `Out-File -Encoding utf8` 이 BOM 을 붙여 겪었다
def test_bom_prefixed_input_is_still_judged(paid_hook):
    body = {"tool_input": {"command": "pytest -m integration"}, "permission_mode": "default"}
    raw = b"\xef\xbb\xbf" + json.dumps(body).encode()
    proc = _run_hook("", raw=raw)

    specific = json.loads(proc.stdout.decode("utf-8"))["hookSpecificOutput"]
    assert specific["permissionDecision"] == "ask"


# 판단이 서지 않으면 막지 않는다 — 훅 입력이 JSON 이 아니면 조용히 통과
def test_unreadable_input_does_not_block(paid_hook):
    proc = _run_hook("", raw=b"not json at all")
    assert proc.returncode == 0
    assert proc.stdout.strip() == b""


# 아래 셋은 **서로 독립된 정책 케이스**다. 하나를 지워서 다른 하나를 통과시키지 않는다 —
# 그렇게 하면 «설정이 없다»·«비워 뒀다»·«정했다» 가 한 칸으로 뭉쳐서, V2 마이그레이션이
# 조용히 감지를 끈 것을 아무도 못 본다


# V1: 설정 파일이 없으면 `integration` 이 기본 마커다. 기존 프로젝트의 호환 경계다.
#
# **`-m paid` 도 승인 대상이다.** 유료 마커가 아닌 이름이지만, 명령줄 `-m` 은 설정의 기본
# 제외를 덮으므로 `integration` 이 빠진다는 보장이 없다. 예전 판정("유료를 고르나")에서는
# 통과했던 자리다
def test_v1_without_config_uses_integration_default(load_hook):
    module, _ = load_hook("paid_test_check", None)

    assert module.blocked_reason("pytest -m integration") is not None
    assert module.blocked_reason("pytest -m paid") is not None
    assert module.blocked_reason("pytest -m 'not integration'") is None


# V2: 마커는 프로젝트가 정한다. 훅에 이름을 박아두지 않는다
def test_v2_marker_policy_is_project_defined(load_hook):
    module, _ = load_hook("paid_test_check", _v2_config(["paid"]))

    assert module.blocked_reason("pytest -m paid") is not None
    # 설정에 없는 이름이어도 기본 제외를 덮으므로 묻는다
    assert module.blocked_reason("pytest -m integration") is not None
    assert module.blocked_reason("pytest -m 'not paid'") is None


# V2: 목록이 비면 감지하지 않는다. 제품 테스트가 없는 템플릿의 상태가 이것이다
def test_v2_without_markers_disables_expensive_guard(load_hook):
    module, _ = load_hook("paid_test_check", _v2_config([]))

    assert module.blocked_reason("pytest -m integration") is None


# 임시 프로젝트의 정책이 **다음 테스트로 새지 않아야 한다.**
#
# `load_hook` 이 전역 모듈을 다시 임포트하므로, 복원이 없으면 이 파일 뒤에 오는 테스트가
# 임시 프로젝트의 마커로 판정한다. 위 `_restore_module_state` 가 그것을 되돌리는데,
# **되돌림 자체를 재지 않으면 그 픽스처가 조용히 망가져도 아무도 모른다**
def test_module_state_is_restored_between_tests(load_hook):
    module, _ = load_hook("paid_test_check", _v2_config(["leaked"]))
    assert module.blocked_reason("pytest -m leaked") is not None


def test_repo_config_is_seen_after_reload():
    # 이 저장소의 실제 설정이다 — 마커 목록이 비어 있으므로 아무것도 감지하지 않는다
    assert paid_test_check._PAID_MARKERS == ()
    assert paid_test_check.blocked_reason("pytest -m leaked") is None


# 유료 마커가 **둘인** 프로젝트. 하나만 빼는 식은 증명이 아니다 —
# 마커가 하나일 때만 재면 `all()` 을 `any()` 로 잘못 써도 초록인 채로 지나간다
@pytest.fixture
def two_marker_hook(load_hook):
    module, _ = load_hook("paid_test_check", _v2_config(["paid", "paid2"]))
    return module


# 명세의 명령 표. 승인을 **물어야** 하는 쪽
NEEDS_APPROVAL = [
    # 기본 제외를 덮지만 유료를 빼지 않는다
    "pytest -m unit",
    'pytest -m ""',
    # `not paid` 가 있어도 `or` 의 다른 가지로 유료가 선택된다
    "pytest -m 'not paid or unit'",
    # 둘 중 하나만 빠졌다
    "pytest -m 'not paid'",
    # 괄호는 해석하지 않고 보수적으로 묻는다
    "pytest -m '(not paid) and (not paid2)'",
    # 옵션 반복. 앞의 것이 안전해도 뒤의 것이 증명되지 않으면 묻는다
    "pytest -m 'not paid and not paid2' -m unit",
    # 다른 설정 파일을 고르면 그쪽 기본 제외를 알 수 없다
    "pytest -c other.ini",
    "pytest --config-file=other.ini",
    # addopts 를 통째로 날린다
    "pytest -o addopts= tests/",
    # addopts 를 덮었는데 paid2 가 빠지지 않았다
    "pytest -o \"addopts=-m 'not paid'\"",
    # **셸 주석으로 수집 전용 예외를 흉내낸다.** 주석일 뿐인데 글자만 보고 통과시키던
    # 구멍이다(2026-11-19 Codex 리뷰에서 실측). 주석을 지우지 않는 지금은 원문에 보이는
    # `-m paid` 로 걸린다
    "pytest -m paid -q # --collect-only",
    # 인용 문자열 안의 옵션처럼 보이는 글자도 옵션이 아니다
    'pytest -m paid -q -k "--collect-only"',
    # **공백이 든 경로를 따옴표로 감싼 실행기.** split() 만 쓰면 첫 토큰이 `"C:\\Program`
    # 이 되어 어떤 실행기 패턴에도 안 걸리고 유료 명령이 통째로 샜다
    r'& "C:\Program Files\Python\python.exe" -m pytest -m paid -q',
    r'"C:\Program Files\Python\python.exe" -m pytest -m paid -q',
    # **닫는 따옴표가 없는 형태.** shlex 가 여기서 ValueError 를 내는데, 처음 고칠 때는
    # `split()` 로 떨어뜨렸다 — 그러면 바로 위 두 줄이 막으려던 구멍이 그대로 되살아난다.
    # 고친 코드를 스스로 두드려 보다 찾은 회귀다(2026-11-19)
    r'& "C:\Program Files\Python\python.exe -m pytest -m paid -q',
    r'"C:\Program Files\Python\python.exe -m pytest -m paid -q',
    # 주석이 붙어 있어도 원문의 `-m paid` 로 묻는다. 이 형태는 따옴표까지 깨져 있어
    # 토큰화도 실패하고, 그쪽 경로 역시 보수적인 쪽으로 떨어진다
    "pytest -m paid -q # it's a comment",
    # **`#` 가 단어 중간이면 주석이 아니다.** 주석을 무조건 자르던 때는 뒤의 `-m paid` 가
    # 사라져 통과했다 — 주석 제거가 거꾸로 우회 수단이 된 자리다(2026-11-19 실측).
    # 전처리를 걷어낸 지금은 원문에 그대로 남아 있다
    "pytest ./foo# -m paid -q",
    # **경로 이름이 옵션처럼 보이는 경우.** pytest 는 이것을 인자로 받으므로 테스트가
    # 실제로 돈다. 앞 경계를 `\s` 로 못 박기 전에는 수집 전용으로 읽혔다
    "pytest -m paid ./--collect-only -q",
    "pytest -m paid -q ./sub/--collect-only",
    # **PowerShell 백틱으로 겹따옴표를 이스케이프한 형태.** 따옴표가 일찍 닫힌 것으로
    # 보여 뒤의 글자가 «따옴표 밖» 으로 분류되고, 그 틈으로 수집 전용 예외가 샜다
    'pytest -m paid -q -o "junit_suite_name=x`"--collect-only"',
    # **같은 수를 Bash 의 역슬래시로.** 훅은 `Bash|PowerShell` 양쪽에 배선돼 있는데
    # 백틱만 이스케이프로 보고 있어서 이쪽이 그대로 남아 있었다(2026-11-19 Codex 지적)
    r'pytest -m paid -q -o "junit_suite_name=x\"--collect-only"',
    r'pytest -m paid -q -k "a\" --collect-only"',
    # **수집 전용 예외를 없앴으므로 진짜 옵션이어도 묻는다.** 위 트릭들이 전부 그 예외를
    # 노렸고, 「진짜 옵션인가」를 문자열로 가리는 일을 그만두면 과녁이 사라진다.
    # 앞이든 뒤든, 주석이 달려 있든 유료 마커를 고르면 묻는다
    "pytest --collect-only -m paid",
    "pytest -m paid --collect-only",
    "pytest --collect-only -m paid # 설명",
    # **CDEX-08: 공백을 이스케이프해 `#` 을 값 안에 넣는다.** 그러면 `#` 은 주석이 아니고
    # 뒤의 `-m paid` 는 진짜 옵션이다. 주석 제거가 그것을 잘라 승인 없이 통과시켰고,
    # 두 셸 모두에서 유료 본문이 실제로 실행되는 것을 표식 파일로 확인했다(2026-11-19).
    # 주석 제거를 폐기한 지금은 두 셸의 이스케이프 규칙을 해석하지 않고도 걸린다
    "pytest -q -o junit_suite_name=x` # -m paid",
    r"pytest -q -o junit_suite_name=x\ # -m paid",
    # **진짜 주석에 적힌 위험 옵션도 묻는다 — 받아들인 오탐이다.** 셸은 이것을 주석으로
    # 보고 `-m paid` 를 pytest 에 넘기지 않으니 실제로는 과금되지 않는다. 그래도 묻는 쪽을
    # 고른다: 주석 경계를 문자열로 증명하려던 규칙이 CDEX-08 의 통로였고, 그 전처리를
    # 걷어낸 대가가 이 승인창 하나다(Round 8 설계 결정)
    "pytest -q # -m paid",
    "pytest -q -o junit_suite_name=x # -m paid",
    # **유료 마커를 고르는 글자만이 아니다.** 기본 제외를 덮을 수 있는 글자면 주석 안이어도
    # 묻는다 — 증명되지 않는 `-m`, 다른 설정을 고르는 `-c`, `addopts` 를 덮는 `-o`
    "pytest -q # -m unit",
    "pytest -q # -c other.ini",
    "pytest -q # -o addopts=",
]

# 물으면 안 되는 쪽. 여기서 헛물으면 훅이 통째로 무시당한다
FREE = [
    "pytest -q",
    "pytest -m 'not paid and not paid2'",
    'pytest -m "not slow and not paid and not paid2"',
    "pytest -o \"addopts=-m 'not paid and not paid2'\"",
    # pytest 가 아니다
    "git commit -m 'paid 마커 추가'",
    # 따옴표 **안** 의 `#` 은 주석이 아니다. 주석 제거가 여기까지 먹으면 커밋 메시지가
    # 잘려서, 하루에 수십 번 쓰는 명령이 엉뚱하게 판정된다
    'git commit -m "fix #123 paid"',
    # 주석이 붙어도 안전한 식은 그대로 안전하다
    "pytest -m 'not paid and not paid2' # 기본 제외 그대로",
    # 공백 경로 실행기라도 유료를 다 빼면 묻지 않는다
    r'& "C:\Program Files\Python\python.exe" -m pytest -m "not paid and not paid2"',
    # 따옴표가 깨진 명령에 pytest 라는 말이 있으면 보수적으로 묻지만, 애초에 pytest 가
    # 아닌 것은 그대로 통과해야 한다 — 그 선이 흐려지면 `echo` 한 줄에도 승인창이 뜬다
    "echo 'pytest -m paid'",
    # 유료 마커를 안 고르면 `--collect-only` 가 붙든 말든 그대로 통과한다
    "pytest --collect-only -q",
    "pytest --collect-only -m 'not paid and not paid2'",
    # **주석이 붙어도 안전한 식은 안전하다.** 오탐은 원문이 유료 마커를 고르는 명령에만
    # 생긴다 — 모든 유료 마커를 빼는 식이 원문에 보이면 주석이 뭐라고 적혀 있든 통과한다
    # `#` 가 단어 중간이어도 판정은 평소대로 — 안전한 식은 안전하다
    "pytest ./foo# -m 'not paid and not paid2' -q",
    # **역슬래시 이스케이프를 넓게 적용하면 여기가 깨진다.** Windows 경로는 겹따옴표 안에
    # 역슬래시를 그대로 담으므로, 다음 글자가 따옴표일 때만 이스케이프로 봐야 한다
    r'pytest -m "not paid and not paid2" --rootdir "C:\x\y"',
    r'& "C:\Program Files\Python\python.exe" -m pytest -m "not paid and not paid2"',
]


@pytest.mark.parametrize("command", NEEDS_APPROVAL)
def test_commands_that_need_approval(two_marker_hook, command: str):
    assert two_marker_hook.blocked_reason(command) is not None, command


@pytest.mark.parametrize("command", FREE)
def test_commands_that_stay_free(two_marker_hook, command: str):
    assert two_marker_hook.blocked_reason(command) is None, command


# 사유에 **무엇 때문에** 묻는지가 들어가야 사용자가 승인 여부를 판단할 수 있다.
# 설정된 마커와 문제가 된 옵션이 둘 다 보여야 한다
def test_reason_names_markers_and_option(two_marker_hook):
    reason = two_marker_hook.blocked_reason("pytest -m unit")

    assert "paid" in reason
    assert "paid2" in reason
    assert "-m unit" in reason
