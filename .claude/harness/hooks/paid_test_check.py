"""프로젝트가 지정한 pytest expensive marker 실행을 막는 PreToolUse 훅.

schema_version 2에서는 `checks.expensive_tests`가 marker와 사유를 정의한다. 아래 integration·
LlamaParse/OpenAI 설명은 schema_version 1 프로젝트의 기존 보호 동작을 설명한다.

`-m integration` 테스트는 LlamaParse/OpenAI 에 **실제 과금**을 일으킨다. 이 저장소는
그 사실을 CLAUDE.md, `rag-code-review`·`plan-log`·`task-log` 스킬, `code-reviewer`
에이전트까지 다섯 곳에 적어뒀지만 전부 모델을 향한 **설득**이다. 반면 그보다 덜
치명적인 "커밋 전 검사"는 `pre_commit_check.py` 로 하네스에 못 박혀 있었다. 이 훅은
그 비대칭을 없앤다 — 제일 비싼 실수를 제일 약한 장치로 막고 있던 상태를 뒤집는다.

`pyproject.toml` 의 `addopts = "-m 'not integration'"` 이 1차 방어선이지만 그건
**기본값**일 뿐이라 명령줄로 얼마든지 뒤집힌다. 그래서 뒤집는 두 경로를 다 본다.

  1. `-m` 마커 표현식이 integration 을 고르는 경우
  2. `-o addopts=...` / `--override-ini addopts=...` 로 기본 제외를 통째로 날리는 경우

**오탐을 줄이는 게 이 훅의 제일 어려운 부분이다.** `git commit -m "integration 테스트
추가"` 같은 명령에도 `-m` 과 `integration` 이 둘 다 들어 있다. 그래서 명령을 세그먼트로
자르고 **첫 토큰이 실제 pytest 실행기인 세그먼트에서만** 마커를 본다. 반대로
`-m "not integration"`(= 기본 안전 호출)을 막아버리면 훅이 쓸모없어지므로 부정도 판다.

**`--collect-only` 예외는 없앴다.** 수집만 하면 과금이 없는 것은 맞지만, 그 예외가 이
훅에서 나온 우회 **여덟 건 전부의 과녁**이었다 — 주석 속의 글자, `./--collect-only` 라는
경로 이름, 인용 문자열 안의 글자, PowerShell 백틱과 Bash 역슬래시로 따옴표를 속이는 두
가지. 전부 «실제 옵션인가» 를 문자열만 보고 가리려다 샜다.

두 셸의 인용·이스케이프 규칙을 문자열 검사만으로 완전히 판별할 수 없다는 것이 결론이다.
그래서 비용 경계에서는 예외 자체를 없앤다 — 유료 마커를 고르거나 기본 제외를 덮는 명령은
`--collect-only` 가 붙어 있어도 승인을 묻는다. 안전한 일반 호출은 예외 없이도 그대로
통과하므로, 잃는 것은 «유료 마커를 수집만 해 보는» 호출에 승인창이 한 번 더 뜨는 것뿐이다.

**같은 이유로 셸 주석도 지우지 않는다.** 예외를 없앤 뒤에도 주석 제거 단계가 남아 있었고,
CDEX-08 이 바로 그 한 군데를 통해 승인 없이 유료 본문을 실행했다. 이제 판정은 **원문
그대로** 한다 — 원문에 유료 마커를 고르거나 기본 제외를 덮는 옵션이 보이면, 그것이 셸에서
주석이든 아니든 묻는다. `pytest -q # -m paid` 가 그 오탐이고 그 대가는 받아들인다.

`pre_commit_check.py` 의 규약을 그대로 따른다 — 훅 입력을 못 읽으면 통과시키고,
사유는 stdout 에 UTF-8 로 낸다.

## 막는 대신 **호출마다 승인을 묻는다**

예전에는 무조건 `deny` 였고 탈출구가 `ALLOW_PAID_TESTS=1` 이었다. 그 조합의 문제는 탈출구
쪽이다 — 값이 비어 있지 않은지만 봤으므로 `=0` 도 통과했고, 한 번 켜면 **세션의 모든 유료
테스트가 열렸다.** 그래서 탈출구를 없애고 응답을 `ask` 로 바꿨다. 승인은 그 도구 호출
하나에만 적용되므로, 다음 유료 명령은 다시 묻는다.

**승인을 보장할 수 없는 권한 모드에서는 `ask` 를 쓰지 않는다.** `bypassPermissions` 처럼
승인창을 건너뛰는 모드에서 `ask` 를 내면 그대로 실행될 수 있어, 보호가 있다고 착각하게
된다. 그런 모드와 **모드를 못 읽은 경우**는 `deny` 다 — 틀리는 방향을 막는 쪽으로 둔다.

## `-m` 은 "유료를 고르나" 가 아니라 "유료를 **다** 빼나" 로 본다

예전에는 `-m` 표현식이 유료 마커를 고르는지만 봤다. 그러면 `-m unit` 이 통과한다 — 그런데
명령줄 `-m` 은 `pyproject` 의 기본 제외(`addopts = "-m 'not paid'"`)를 **덮어쓰므로**,
`-m unit` 은 기본 제외를 날리고 유료 테스트까지 수집될 수 있다. `-m 'not paid or unit'` 도
`not paid` 라는 문자열이 있지만 `or` 의 다른 가지로 유료가 선택된다.

그래서 판정을 뒤집었다. 명령줄에 `-m` 이 있으면 **설정된 모든 유료 마커를 AND 조건으로
빼는 것이 증명되는 단순 식만** 무료로 통과시킨다. `or` 나 괄호가 있으면 해석하지 않고
승인을 묻는다. 문자열 eval 은 쓰지 않는다.
"""

from __future__ import annotations

import json
import re
import shlex
import sys

import _hookutil

# 명령을 세그먼트로 자르는 구분자. `git add -A && pytest -m integration` 처럼 붙은 명령에서
# 뒤쪽만 걸러내기 위한 것이다
_SEGMENT_SPLIT_RE = re.compile(r"&&|\|\||[;|\n]")

# `-m <값>` 을 찾는다. `-m integration`, `-m=integration`, `-mintegration`, 따옴표 형태를
# 모두 잡는다. 앞의 (?<![\w-]) 는 `--m` 이나 `-xm` 에 걸리지 않게 한다
_MARKER_RE = re.compile(r"(?<![\w-])-m[\s=]*(\"[^\"]*\"|'[^']*'|[^\s]+)")

# addopts 를 명령줄에서 덮어쓰는 형태. 기본 제외(`-m 'not integration'`)가 날아간다
_ADDOPTS_OVERRIDE_RE = re.compile(
    r"(?<![\w-])(?:-o|--override-ini)[\s=]*(\"[^\"]*\"|'[^']*'|[^\s]+)"
)

# `-m pytest` 로 부르는 인터프리터. 이 형태면 세그먼트 안에 `-m pytest` 가 있어야 pytest 다
_PYTHON_RE = re.compile(r"^python[\d.]*(?:\.exe)?$", re.IGNORECASE)

# pytest 실행기 자체
_PYTEST_RE = re.compile(r"^py\.?test(?:\.exe)?$", re.IGNORECASE)

# pytest 를 대신 띄우는 러너들. 세그먼트 어딘가에 pytest 라는 말이 있어야 한다
_RUNNERS = frozenset({"uv", "uvx", "poetry", "hatch", "pdm", "rye", "nox", "tox"})

# 인터프리터가 pytest 를 모듈로 부르는 형태
_DASH_M_PYTEST_RE = re.compile(r"(?<![\w-])-m[\s=]*[\"']?pytest[\"']?\b")

# 러너 세그먼트에서 pytest 라는 말을 찾는다
_PYTEST_WORD_RE = re.compile(r"\bpy\.?test\b", re.IGNORECASE)

# 실행기가 변수에 담긴 형태(`& $py -m pytest`, `$env:X`). 정적으로는 무엇인지 알 수 없다
_VARIABLE_RE = re.compile(r"^[$%]\{?[\w:]")

# 다른 pytest 설정 파일을 고르는 형태. 그러면 기본 제외가 그 파일의 것으로 바뀌므로,
# 우리가 아는 `addopts` 가 적용된다고 볼 수 없다
_CONFIG_FILE_RE = re.compile(r"(?<![\w-])(?:-c|--config-file)[\s=]*(\"[^\"]*\"|'[^']*'|[^\s]+)")

# 마커 식에 `or` 가 섞이면 한쪽 가지가 유료를 고를 수 있다. 괄호도 같이 본다
_OR_RE = re.compile(r"(?<![\w-])or(?![\w-])", re.IGNORECASE)

# 승인창을 띄울 수 있는 모드. 여기서만 `ask` 를 쓴다
_ASK_MODES = frozenset({"default", "acceptEdits", "auto"})

# 승인창을 기대할 수 없는 모드. `plan` 은 실행 자체가 아니고, `dontAsk`·`bypassPermissions`
# 는 확인을 건너뛴다. **모르는 값과 누락도 이쪽이다** — 모드를 못 읽었는데 `ask` 를 내면
# 승인 없이 실행될 수 있고, 그러면 보호가 있다고 착각하게 된다
_DENY_MODES = frozenset({"plan", "dontAsk", "bypassPermissions"})


def _policy() -> tuple[tuple[str, ...], str]:
    """(유료 pytest marker, 설명).

    **`allow_env` 가 없어진 자리다.** 예전에는 세 번째로 우회 환경변수 이름을 돌려줬다.
    V1 분기도 함께 줄였다 — 기본 마커 `integration` 은 유지하되, V1 프로젝트에서도
    환경변수 우회는 더 이상 없다.
    """
    if not _hookutil.is_v2():
        return (
            ("integration",),
            (
                "integration 마커 테스트는 LlamaParse/OpenAI 에 실제 과금이 발생합니다. "
                "기본 검증은 `pytest -q` 로 충분합니다."
            ),
        )
    section = _hookutil.check_config("expensive_tests") or {}
    raw = section.get("pytest_markers")
    markers = (
        tuple(item.strip() for item in raw if isinstance(item, str) and item.strip())
        if isinstance(raw, list)
        else ()
    )
    reason = section.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = "설정된 expensive test는 비용 또는 긴 실행 시간이 발생할 수 있습니다."
    return markers, reason.strip()


_PAID_MARKERS, _POLICY_REASON = _policy()


# 따옴표를 벗긴다. `"not slow"` -> `not slow`
def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


# 경로·따옴표를 걷어낸 실행 파일 이름. `.\.venv\Scripts\python.exe` -> `python.exe`
def _basename(token: str) -> str:
    token = _unquote(token.strip())
    for sep in ("/", "\\"):
        token = token.rsplit(sep, 1)[-1]
    return token


# 세그먼트를 토큰으로 자른다. **공백이 든 경로를 따옴표로 감싼 형태 때문에 shlex 가 필요하다.**
#
# `segment.split()` 만 쓰면 `& "C:\Program Files\Python\python.exe" -m pytest -m paid -q` 의
# 첫 토큰이 `"C:\Program` 이 되고, basename 이 `Program` 이라 어떤 실행기 패턴에도 안 걸려
# **유료 명령이 통째로 샜다**(2026-11-19 실측). `posix=False` 라야 Windows 의 역슬래시가
# 이스케이프로 먹히지 않고 따옴표도 토큰에 남아 `_basename` 이 벗길 수 있다.
#
# 따옴표가 안 닫히면 shlex 가 ValueError 를 낸다. 그때는 `None` 이다 — **`split()` 로
# 떨어지면 안 된다.** 처음에는 그렇게 뒀는데, 그것이 바로 이 함수가 고치려던 구멍이다:
# `& "C:\Program Files\Python\python.exe -m pytest -m paid -q`(닫는 따옴표 없음)가
# `split()` 에서 `"C:\Program` 으로 쪼개져 실행기를 못 알아보고 유료 명령이 그대로 샜다
# (2026-11-19 실측. 고친 뒤 스스로 두드려 보다 찾았다)
def _tokens(segment: str) -> list[str] | None:
    try:
        return shlex.split(segment, posix=False)
    except ValueError:
        return None


# 이 세그먼트가 pytest 를 실행하나. 첫 토큰만 보므로 `git commit -m "..."` 에 안 걸린다
def _runs_pytest(segment: str) -> bool:
    tokens = _tokens(segment)
    if tokens is None:
        # 토큰을 믿을 수 없다. 실행기를 식별하는 대신 **pytest 라는 말이 있으면 pytest 로
        # 본다.** 틀리는 방향을 «묻는» 쪽으로 둔다 — 따옴표가 깨진 명령에서 오탐이 한 번
        # 나는 것이 유료 호출이 한 번 새는 것보다 싸다
        return bool(_PYTEST_WORD_RE.search(segment))
    # 실행기 앞에 붙는 것들을 걷어낸다.
    #   `&`      PowerShell 호출 연산자. 이 저장소의 명령 예시가 전부 이 형태라
    #            (`& $py -m pytest ...`) 안 걷어내면 제일 흔한 호출이 그대로 샌다
    #   `FOO=1`  환경변수 지정
    while tokens and (tokens[0] == "&" or ("=" in tokens[0] and not tokens[0].startswith("-"))):
        tokens = tokens[1:]
    if not tokens:
        return False

    head = _basename(tokens[0])

    if _PYTEST_RE.match(head):
        return True
    if _PYTHON_RE.match(head):
        return bool(_DASH_M_PYTEST_RE.search(segment))
    if head.lower() in _RUNNERS:
        return bool(_PYTEST_WORD_RE.search(segment))
    if _VARIABLE_RE.match(head):
        # 인터프리터 경로가 변수에 담겨 있으면(`& $py -m pytest ...`) 무엇을 부르는지
        # 정적으로 알 수 없다. 세그먼트에 pytest 라는 말이 있으면 pytest 로 본다.
        # 첫 토큰이 변수인 명령이 커밋 메시지일 리는 없으므로 오탐 위험이 낮다
        return bool(_PYTEST_WORD_RE.search(segment))
    return False


# 이 마커 표현식이 marker 를 고르나. `not marker` 는 반대로 빼는 것이라 아니다
def _negative_marker_re(marker: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w-])not\s*\(?\s*{re.escape(marker)}\s*\)?(?![\w-])", re.IGNORECASE)


def _selects_marker(expr: str, marker: str) -> bool:
    # 부정을 먼저 지운다. 이걸 안 하면 pyproject 기본값과 같은 안전한 호출까지 막혀서
    # 훅이 통째로 무시당하게 된다
    remaining = _negative_marker_re(marker).sub(" ", expr)
    return bool(re.search(rf"(?<![\w-]){re.escape(marker)}(?![\w-])", remaining, re.IGNORECASE))


# V1 테스트와 외부 호출을 위한 호환 이름
def _selects_integration(expr: str) -> bool:
    return _selects_marker(expr, "integration")


# 이 식이 **설정된 모든 유료 마커를 빼는 것이 증명되나.**
#
# 증명할 수 있는 모양만 좁게 인정한다 — `or` 도 괄호도 없는 단순 AND 식에서 마커마다
# `not <마커>` 가 보일 때다. `not paid or unit` 은 `not paid` 라는 문자열이 있어도 `or` 의
# 다른 가지로 유료가 선택되므로 증명이 아니다. 괄호는 아예 해석하지 않는다.
# **문자열 eval 은 쓰지 않는다** — 명령줄에서 온 식을 평가하는 것은 그 자체가 구멍이다.
#
# 마커 목록이 비면 `all(())` 이 True 라서 무엇이든 통과한다. 그것이 맞다 — 유료 마커를
# 정하지 않은 프로젝트에는 지킬 것이 없다
def _provably_excludes_all(expr: str) -> bool:
    text = expr.strip()
    if not text:
        # 빈 `-m` 도 기본 제외를 덮는다. 아무것도 안 빼므로 증명이 아니다
        return not _PAID_MARKERS
    if "(" in text or ")" in text or _OR_RE.search(text):
        return not _PAID_MARKERS
    return all(_negative_marker_re(marker).search(text) for marker in _PAID_MARKERS)


# 이 세그먼트가 승인이 필요한 pytest 호출인가. 그렇다면 사유 한 줄, 아니면 None.
#
# **`-m` 이 있으면 기본 제외가 덮였다고 본다.** pytest 는 명령줄 `-m` 을 `addopts` 의
# `-m` 보다 뒤에 적용하므로, 우리가 아는 제외가 남아 있다고 볼 수 없다. 그래서 «유료를
# 고르나» 가 아니라 «유료를 다 빼나» 로 묻는다(모듈 docstring 참조)
#
# **원문을 그대로 본다 — 셸 주석을 지우지 않는다.** 주석 경계를 명령 문자열에서 증명하려던
# `_strip_comment()` 가 그 자체로 우회 수단이었다. 토큰 머리 조건, 따옴표 안의 `#`,
# 이스케이프된 공백까지 규칙을 세 번 덧댔는데도 CDEX-08
# (``pytest -q -o junit_suite_name=x` # -m paid``)이 승인 없이 유료 본문을 실행했다 —
# 두 셸 모두에서 표식 파일로 확인했다(2026-11-19). 전처리를 걷어내면 그 과녁이 사라진다.
#
# 대가는 오탐 하나다. 진짜 주석에 위험 옵션이 적힌 `pytest -q # -m paid` 도 이제 묻는다.
# 승인창이 한 번 더 뜨는 쪽을 받아들인다 — 셸 문법을 문자열로 판별하려다 유료 호출을
# 놓치는 것보다 싸다
def _paid_reason(segment: str) -> str | None:
    if not _runs_pytest(segment):
        return None

    # **여기 있던 수집 전용 예외를 없앴다.** 이 훅에서 나온 우회 여덟 건이 전부 그 예외를
    # 노렸다. 「`--collect-only` 가 진짜 옵션인가」를 문자열만 보고 가리는 일을 그만두면
    # 그 과녁이 사라진다. 자세한 이유는 모듈 docstring 에 있다
    marker_text = ", ".join(_PAID_MARKERS)

    # 다른 설정 파일을 고르면 그 파일의 addopts 가 적용된다. 우리는 그 내용을 모른다
    for raw in _CONFIG_FILE_RE.findall(segment):
        value = _unquote(raw)
        return (
            f"`-c {value}` 가 다른 pytest 설정을 고릅니다. 그 설정의 기본 제외를 알 수 없어 "
            f"expensive marker({marker_text}) 테스트가 수집될 수 있습니다."
        )

    for raw in _MARKER_RE.findall(segment):
        value = _unquote(raw)
        # `python -m pytest` 의 앞쪽 -m 은 모듈 이름이라 마커가 아니다
        if value.lower() in {"pytest", "py.test"}:
            continue
        if _provably_excludes_all(value):
            continue
        # **옵션이 반복돼도 여기서 걸린다.** 뒤의 `-m` 이 안전해도 앞의 것이 증명되지
        # 않으면 묻는다 — 어느 쪽이 이기는지에 판정을 걸지 않는 보수적인 선택이다
        return (
            f"마커 표현식 `-m {value}` 가 expensive marker({marker_text}) 제외를 "
            "보장하지 못합니다. 명령줄 -m 은 설정의 기본 제외를 덮어씁니다."
        )

    for raw in _ADDOPTS_OVERRIDE_RE.findall(segment):
        value = _unquote(raw)
        if not value.lower().startswith("addopts"):
            continue
        # 덮어쓴 값이 모든 유료 마커를 스스로 빼는 것이 증명되면 괜찮다
        if _provably_excludes_all(value):
            continue
        return (
            f"`-o {value}` 가 설정의 addopts 를 덮어씁니다. "
            f"기본 제외가 사라져 expensive marker({marker_text}) 테스트까지 돌아갈 수 있습니다."
        )

    return None


# 명령 전체를 보고 막아야 할 사유. 막을 이유가 없으면 None.
# 세그먼트로 자르는 것이 판정의 일부라 main() 이 아니라 여기에 둔다 — 테스트가 이 함수를
# 부르면 실제 실행 경로와 같은 것을 검사하게 된다
def blocked_reason(command: str) -> str | None:
    for segment in _SEGMENT_SPLIT_RE.split(command):
        reason = _paid_reason(segment)
        if reason:
            return reason
    return None


# 승인이 필요한 명령에 대한 권한 모드별 응답.
#
# **기본이 deny 인 것이 요점이다.** 아는 모드만 `ask` 로 보내고 나머지는 전부 막는다.
# 반대로 두면(모르는 모드를 ask) 승인창이 안 뜨는 환경에서 그대로 실행되는데, 그때
# 아무 신호도 없어서 보호가 있다고 착각한 채로 과금이 일어난다
def _decision_for_mode(mode: str) -> str:
    return "ask" if mode in _ASK_MODES else "deny"


# 판정을 하네스에 돌려준다. `decision` 은 "ask" 또는 "deny".
#
# **한 함수로 둔 것이 요점이다.** `hookSpecificOutput` 의 모양은 둘이 똑같고 다른 것은
# 판정값과 안내 문구뿐이라, 두 벌로 두면 한쪽 형식만 고쳐져 하네스가 조용히 무시한다 —
# 이 저장소가 `_hookutil`·`_quality` 를 공용부로 모은 이유와 같다
def _respond(decision: str, detail: str, mode: str) -> None:
    # Windows 콘솔 기본 인코딩(cp949)으로는 한국어 사유를 못 내보내 UnicodeEncodeError 로
    # 훅이 죽는다. 실패 경로에서만 드러나므로 여기서 못 박는다
    sys.stdout.reconfigure(encoding="utf-8")

    if decision == "ask":
        head = "유료 API 를 호출할 수 있는 테스트입니다. 이 호출을 실행할지 승인해 주세요."
        tail = "승인은 이 도구 호출 하나에만 적용됩니다. 다음 유료 명령은 다시 묻습니다."
        system = "유료 테스트 실행 승인을 요청했습니다."
    else:
        head = "유료 API 를 호출할 수 있는 테스트라 막았습니다."
        if mode in _DENY_MODES:
            why = f"현재 권한 모드 `{mode}` 는 호출별 승인창을 보장하지 않습니다."
        else:
            why = f"권한 모드를 확인할 수 없습니다(받은 값: `{mode or '누락'}`)."
        tail = f"{why} default 나 acceptEdits 모드에서 다시 실행해 승인해 주세요."
        system = "유료 테스트 실행을 막았습니다."

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": (f"{head}\n\n{detail}\n\n{_POLICY_REASON}\n{tail}"),
                },
                "systemMessage": system,
            },
            ensure_ascii=False,
        )
    )
    sys.exit(0)


# 훅 진입점. stdin 으로 받은 도구 호출을 보고 유료 테스트일 때만 막는다
def main() -> None:
    # 한국어가 담겨 오므로 stdin 을 UTF-8 로 못 박는다. cp949 로 읽으면 UnicodeDecodeError
    # 가 나는데 이건 ValueError 하위라 아래 except 에 조용히 먹히고 검사가 무력화된다.
    # utf-8 이 아니라 utf-8-sig 인 이유: BOM 이 붙어 오면 json.load 가 실패해 같은 경로로
    # 조용히 통과한다. 실제로 이 훅을 검증하다 겪었다(PowerShell 5.1 의 `Out-File -Encoding
    # utf8` 은 BOM 을 붙인다). BOM 이 없는 입력에는 utf-8 과 완전히 같게 동작한다
    sys.stdin.reconfigure(encoding="utf-8-sig", errors="replace")

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # 판단 근거가 없다. 막지 않는다 — `_hookutil` 의 공통 규약과 같다
        return

    # **환경변수 우회가 있던 자리다.** 값이 비어 있지 않은지만 봐서 `=0` 도 통과시켰고,
    # 한 번 켜면 세션의 모든 유료 테스트가 열렸다. 승인으로 바꾸면서 없앴다 —
    # 이제 허용의 단위는 세션이 아니라 도구 호출 하나다

    if not _PAID_MARKERS:
        return

    command = str(payload.get("tool_input", {}).get("command", ""))
    if not command:
        return

    reason = blocked_reason(command)
    if not reason:
        return

    # 모드는 **입력 payload** 에서 읽는다. 환경이 아니라 하네스가 알려주는 값이다
    mode = str(payload.get("permission_mode") or "")
    _respond(_decision_for_mode(mode), reason, mode)


if __name__ == "__main__":
    main()
