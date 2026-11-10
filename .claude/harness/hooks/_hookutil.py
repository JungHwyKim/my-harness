"""훅들이 공유하는 최소 도구 모음.

`task_log_check.py`(구현 후 회고) · `plan_log_check.py`(설계 논의) · `auto_test_check.py`
(자동 테스트)는 트리거가 다 다르지만 바닥에서 하는 일은 같다 — 훅 입력을 읽고, 무엇이
바뀌었는지 보고, 세션당 한 번만 막는다.

**이 모듈이 존재하는 진짜 이유는 조용히 무력화되는 함정들이다.** 아래 `changed_paths()` 의
`-z` 와 `-uall` 은 둘 다 없으면 검사가 소리 없이 통과한다. 실제로 `-uall` 누락은 구현 중에
한 번 겪었고(새 디렉터리를 통째로 만들면 "?? rag_pipeline/" 한 줄로 접혀 안의 .py 가 안
보인다) 단위 테스트로는 안 잡혀 실제 저장소 호출로만 드러났다. `read_payload()` 의
utf-8-sig 도 같은 종류다. 같은 코드가 훅마다 복사되면 한쪽만 고쳐져 그 버그가 되살아난다 —
BOM 교훈이 실제로 `paid_test_check.py` 에만 있다가 `auto_test_check.py` 에서 다시 걸렸다.
그래서 이런 교훈이 한 곳에만 있게 한다. `relative_to_root()` 를 여기 둔 것도 그래서다.

공통 규약: **판단이 서지 않으면 막지 않는다.** 기록 하나를 놓치는 것보다 사용자를 끝나지
않는 세션에 가두는 쪽이 훨씬 나쁘다. 그래서 모든 실패 경로가 None/False 를 돌려준다.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


# 저장소 뿌리를 찾는다. **`__file__` 로는 못 센다** — 이 파일이 플러그인 설치 경로에 살아서
# 위로 두 칸 올라가면 저장소가 아니라 플러그인 폴더가 나온다.
#
# **`CLAUDE_PROJECT_DIR` 하나로도 안 된다.** 실측(2026-09-10 탐침)으로 그 값은 저장소 뿌리가
# 아니라 **세션을 띄운 폴더**다 — `agentic-rag-proj/evaluation` 에서 띄우니 그 값이 그대로 왔다.
# 그래서 거기서 시작해 `.claude/` 를 가진 폴더가 나올 때까지 위로 올라간다.
#
# **git 을 표시로 쓰지 않는다** — 두 번째 프로젝트에 `.git` 이 아예 없다(확인함).
# `.claude/` 를 쓰면 설정이 사는 자리와 뿌리가 같은 자리가 되어, 설정이 없을 때 검사가 안 도는
# 것으로 저절로 이어진다. 못 찾으면 시작한 자리를 그대로 쓴다
def _find_root() -> Path:
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        start = Path(raw).resolve()
    except OSError:
        return Path.cwd()
    for candidate in (start, *start.parents):
        if (candidate / ".claude").is_dir():
            return candidate
    return start


PROJECT_ROOT = _find_root()

# 프로젝트가 자기 사정을 대는 파일
CONFIG_PATH = PROJECT_ROOT / ".claude" / "harness.json"

_CONFIG: dict | None = None


# `.claude/harness.json` 의 내용. 없거나 못 읽으면 빈 사전.
#
# utf-8-sig 인 이유는 `read_payload()` 와 같다 — BOM 이 붙으면 json 이 죽는데 그것도
# ValueError 하위라 조용히 빈 설정이 되고, 그러면 검사가 꺼진 채 아무도 모른다
def config() -> dict:
    global _CONFIG
    if _CONFIG is None:
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError, ValueError):
            loaded = {}
        _CONFIG = loaded if isinstance(loaded, dict) else {}
    return _CONFIG


# 설정 계약 버전. 기존 프로젝트에는 이 필드가 없으므로 1로 본다.
#
# V2 기능은 반드시 이 값이 2 이상일 때만 켠다. 플러그인을 업데이트했다는 이유만으로
# 기존 기록 게이트와 품질 검사가 바뀌면, 프로젝트가 준비되지 않은 상태에서 작업 흐름이
# 깨진다. 버전 분기가 그 호환 경계다.
def schema_version() -> int:
    value = config().get("schema_version")
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 1


def is_v2() -> bool:
    return schema_version() >= 2


# `checks` 아래 한 절. 없으면 None.
#
# **빈 사전을 돌려주면 안 된다** — 그러면 «설정이 없다» 와 «비워 뒀다» 가 안 갈려서 부르는
# 쪽이 기본값으로 돈다. 이 저장소가 막으려는 실패가 정확히 그 모양이라 None 이다
def check_config(name: str) -> dict | None:
    checks = config().get("checks")
    if not isinstance(checks, dict):
        return None
    section = checks.get(name)
    return section if isinstance(section, dict) else None


# 설정에서 문자열 목록을 꺼낸다. 없거나 모양이 틀리면 빈 튜플
def config_list(key: str, section: dict | None = None) -> tuple[str, ...]:
    source = config() if section is None else section
    value = source.get(key)
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


# 기록 세 폴더(plan_log·task_log·verify_log)를 담은 위키의 뿌리.
#
# **한 자리에 두는 이유는 어긋나도 아무 에러가 안 나서다.** 두 기록 훅이 각자
# `"plan_log/"` `"task_log/"` 를 들고 있었는데, 그 접두사가 실제 경로와 어긋나면
# `rel.startswith()` 가 늘 False 를 돌려 **기록을 남긴 세션이 안 남긴 것으로 보인다** —
# 검사가 죽는 게 아니라 반대로 늘 막는 쪽으로 고장 나고, 그러면 `SKIP_TASKLOG=1` 이
# 습관이 되어 검사가 통째로 죽는다. `openwork/collect.py` 의 `WIKI_ROOT` 와 같은 기준이고
# (거기는 조용히 짧아지는 쪽으로 고장 난다), 양쪽을 `tests/hooks` 가 잠근다.
#
# 이제 값은 프로젝트가 `wiki_root` 로 준다. **끝의 `/` 를 여기서 못 박는다** — 설정에서
# 빠뜨리면 접두사 비교가 조용히 어긋나는데, 그 고장이 바로 위 문단이 말하는 그 모양이다
def _wiki_root() -> str:
    raw = config().get("wiki_root")
    value = raw if isinstance(raw, str) and raw.strip() else ".claude/wiki/"
    return value if value.endswith("/") else value + "/"


WIKI_ROOT = _wiki_root()


# V2 History 종류별 저장 접두사. 설정값은 wiki_root 기준 상대 경로이고, 이미 wiki_root를
# 포함한 프로젝트 상대 경로도 받는다. 모든 결과는 접두사 비교에 안전하도록 `/`로 끝난다.
def history_prefix(kind: str) -> str:
    if kind not in {"plan", "task", "verify"}:
        raise ValueError(f"알 수 없는 History 종류: {kind}")

    section = config().get("history")
    raw = section.get(kind) if isinstance(section, dict) else None
    value = raw.strip().replace("\\", "/") if isinstance(raw, str) else ""
    if not value:
        value = f"history/{kind}/"
    while value.startswith("./"):
        value = value[2:]
    value = value.lstrip("/")
    if not value.startswith(WIKI_ROOT):
        value = WIKI_ROOT + value
    return value if value.endswith("/") else value + "/"


HISTORY_PREFIXES = {kind: history_prefix(kind) for kind in ("plan", "task", "verify")}

GIT_TIMEOUT_SEC = 20


# stdin 으로 온 훅 입력. 못 읽으면 None (막지 않는다)
def read_payload() -> dict | None:
    # 훅 입력에 한국어 경로·메시지가 담겨 오므로 UTF-8 로 못 박는다. cp949 로 읽으면
    # UnicodeDecodeError 가 나는데 이건 ValueError 하위라 아래 except 에 조용히 먹히고
    # 검사가 통째로 무력화된다.
    #
    # utf-8 이 아니라 **utf-8-sig** 인 이유: BOM 이 붙어 오면 json.load 가
    # "Unexpected UTF-8 BOM" 으로 죽고, 그것도 ValueError 하위라 같은 경로로 조용히
    # 통과한다. PowerShell 이 파이프에 BOM 을 붙이는 일이 실제로 있다 —
    # paid_test_check.py 가 먼저 겪어 자체 stdin 읽기에 utf-8-sig 를 박아뒀는데,
    # 그 교훈이 공용부에는 안 와 있어서 auto_test_check.py 를 검증하다 다시 걸렸다.
    # utf-8-sig 는 BOM 이 없는 입력도 그대로 읽으므로 잃는 것이 없다
    sys.stdin.reconfigure(encoding="utf-8-sig", errors="replace")
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


# 프로젝트 테스트·린트를 돌릴 파이썬. 설정의 `python` → `.venv` → 이 스크립트를 돌린 것 순.
#
# **훅 자신은 이 값이 필요 없다** — 훅 아홉은 전부 표준 라이브러리만 쓴다(확인함).
# 필요한 것은 훅이 부르는 pytest·ruff 쪽이라, 설정 이름도 «훅 파이썬» 이 아니라 `python` 이다.
#
# **두 훅이 각자 들고 있던 것을 여기로 모았다** — `auto_test_check` 와 `pre_commit_check` 가
# 같은 함수를 한 벌씩 갖고 있었는데, 그러면 한쪽만 고쳐진다. 이 모듈이 있는 이유가 그것이다
def venv_python() -> str:
    configured = config().get("python")
    if isinstance(configured, str) and configured.strip():
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        if candidate.is_file():
            return str(candidate)
    for candidate in (
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",  # Windows
        PROJECT_ROOT / ".venv" / "bin" / "python",  # POSIX
    ):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


# 자식 프로세스에 물릴 환경. **`PYTHONIOENCODING` 하나가 요점이다.**
#
# 부모는 `encoding="utf-8", errors="replace"` 로 받는데 Windows 자식은 파이프로 나갈 때
# 로케일(cp949)로 내보낸다. 그래서 한국어 실패 사유·skip 사유가 대체문자로 바뀌어
# **사유는 나오는데 못 읽는** 모양이 된다 — 실측(2026-08-29) pytest 실패 한 줄에 U+FFFD 52개,
# 이 변수를 넣으면 0개다. 대신 `errors="replace"` 를 빼는 것은 답이 아니다: 호출부가 잡는
# 예외가 TimeoutExpired·OSError 뿐이라 UnicodeDecodeError 로 훅이 죽는다. 둘 다 필요하다.
#
# **`openwork/collect.py`·`cost/__init__.py` 가 «부르는 쪽이 붙이는 규약» 을 기각한 것과
# 어긋나지 않는다.** 저쪽은 *우리 CLI* 가 자기 출력을 스스로 못 박으라는 것이고, pytest·ruff 는
# 우리 것이 아니라 자식 환경이 유일한 손잡이다.
#
# **`PYTHONUTF8=1` 은 안 쓴다** — 자식의 모든 파일 I/O 기본 인코딩까지 바꿔서, 훅이 돌린
# pytest 와 사람이 손으로 돌린 pytest 가 다른 조건이 된다.
#
# **갈아끼우지 않고 복제한다** — `.venv` 를 찾는 PATH 를 잃으면 검사가 통째로 안 돈다
def child_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return env


# git 이 보고하는 변경 경로 목록. 판단할 수 없으면 None
def changed_paths() -> list[str] | None:
    try:
        proc = subprocess.run(
            # 옵션 두 개가 다 필수다. 하나라도 빠지면 검사가 조용히 통과한다.
            #
            # -z     기본 --porcelain 은 ASCII 밖 경로를
            #        "task_log/routing-diff-\354\213\234..." 처럼 따옴표+8진 이스케이프로
            #        내보낸다. 이 저장소는 한국어 파일명이 흔해서, 그대로 접두사 비교를
            #        하면 기록 파일을 못 알아본다
            #
            # -uall  기본값은 통째로 untracked 인 디렉터리를 "?? rag_pipeline/" 한 줄로
            #        접는다. 그러면 안의 .py 가 안 보여서 검사가 통과한다. 하필 제일
            #        중요한 경우가 그렇다 — 새 파이프라인 단계 디렉터리를 통째로 새로
            #        만든 작업은 남길 게 제일 많은데 검사가 안 걸린다
            ["git", "status", "--porcelain", "-uall", "-z"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            timeout=GIT_TIMEOUT_SEC,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if proc.returncode != 0:
        return None

    paths: list[str] = []
    for chunk in proc.stdout.split(b"\0"):
        if not chunk:
            continue
        # 항목은 "XY <경로>" 형태다. 이름이 바뀐 항목(R/C)은 원래 경로가 다음 레코드에
        # 접두사 없이 따라오는데, 그것도 실제 경로이므로 그대로 받는다
        entry = chunk[3:] if chunk[2:3] == b" " else chunk
        paths.append(entry.decode("utf-8", "replace"))
    return paths


# 절대·상대 경로를 저장소 기준 posix 경로로 바꾼다. 저장소 밖이면 None
def relative_to_root(raw: str) -> str | None:
    # 훅 입력의 file_path 는 절대 경로로 온다. 접두사 비교를 하려면 먼저 저장소 기준으로
    # 낮춰야 한다. 저장소 밖(스크래치패드 등)은 우리가 볼 것이 아니라 None 이다
    if not raw:
        return None
    try:
        path = Path(raw)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        rel = path.resolve().relative_to(PROJECT_ROOT.resolve())
    except (OSError, ValueError):
        return None
    return rel.as_posix()


# 세션 마커 파일 경로. 세션 id 를 못 쓰면 None
def _marker_path(namespace: str, session_id: str) -> Path | None:
    # 세션 id 가 그대로 파일명이 되므로 경로 문자를 걷어낸다
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_")[:64]
    if not safe:
        return None
    return _marker_root() / namespace / safe


# 세션 마커를 담는 폴더.
#
# **한때 `PROJECT_ROOT/.git/` 이었다** — git 이 관리하지 않는 영역이라 gitignore 가 필요 없다는
# 이유였다. 플러그인으로 옮기며 그 전제가 깨졌다: 두 번째 프로젝트에 **`.git` 이 없어**,
# 거기서는 없는 `.git` 을 훅이 새로 만들어 버린다.
#
# 그래서 플러그인 데이터 폴더로 옮겼다(실측으로 `CLAUDE_PLUGIN_DATA` 가 훅에 온다).
# 프로젝트를 안 더럽히고 git 여부를 안 탄다. **프로젝트 경로 해시로 한 겹 가르는 것은**
# 한 플러그인이 여러 저장소에서 도는데 마커가 한 폴더에 섞이면 읽는 사람이 못 가르기 때문이다.
# 환경변수가 없는 경우(플러그인 밖에서 직접 부를 때)에는 임시 폴더로 떨어진다
def _marker_root() -> Path:
    base = os.environ.get("CLAUDE_PLUGIN_DATA") or tempfile.gettempdir()
    key = hashlib.sha256(str(PROJECT_ROOT).encode("utf-8")).hexdigest()[:12]
    return Path(base) / "harness-sessions" / key


# 이 세션에서 마커를 처음 만들면 True, 이미 있으면 False
def claim_session(namespace: str, session_id: str) -> bool:
    marker = _marker_path(namespace, session_id)
    if marker is None:
        return False

    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        # O_EXCL 로 "만들면서 동시에 검사"한다. 존재 확인 후 생성으로 나누면 훅이 겹쳐
        # 돌 때 둘 다 통과해버릴 수 있다
        fd = os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except OSError:
        # 마커를 못 남기면 다음 Stop 에서 또 막게 되고 그게 무한 루프다. 막지 않는다
        return False

    os.close(fd)
    return True


# 이 세션에 마커가 있나
def is_marked(namespace: str, session_id: str) -> bool:
    marker = _marker_path(namespace, session_id)
    return marker is not None and marker.exists()


# 세션이 시작된 시각을 남기는 마커. 그 세션에서 처음 도는 훅이 찍고 나머지는 읽기만 한다.
#
# **이것이 필요한 이유는 "누가 썼는가"로 판정하면 구멍이 난다는 것이다.** 기록 훅들은
# "이번 세션에 기록했는가"를 PostToolUse 의 `tool_input.file_path` 로만 봤는데, 그 필드는
# Write/Edit 에만 있다. Bash 로 쓴 기록은 **아무리 잘 써도 안 보인다** — 2026-08-19 에
# .claude/wiki/plan_log/ 를 python heredoc 으로 고친 세션이 회차·INDEX 를 다 남기고 커밋까지 하고도
# 막혔다. 도구를 Write/Edit 로 쓰라고 지시해서 고칠 수는 없다. 모델에게 시키는 일은
# 지켜질 때도 있고 아닐 때도 있다는 것이 이 장치 전체의 전제이기 때문이다.
#
# 그래서 **도구가 아니라 파일이 실제로 바뀌었는가**를 본다. 그러려면 "언제부터"가 필요하고,
# 그 기준이 이 마커다. 어느 훅이 먼저 돌든 상관없도록 네임스페이스를 공유한다
SESSION_START_NS = "claude_session_started"


# 세션 시작 표시를 남긴다. 이번 호출이 처음 만든 것이면 True.
#
# True 면 **기준 시각으로 쓸 수 없다** — 방금 찍었으니 모든 파일이 그보다 옛것이 된다.
# 부르는 쪽이 이 값을 보고 mtime 판정을 건너뛴다
def mark_session_start(session_id: str) -> bool:
    return claim_session(SESSION_START_NS, session_id)


# 세션 시작 시각(epoch). 표시가 없거나 못 읽으면 None
def session_started_at(session_id: str) -> float | None:
    marker = _marker_path(SESSION_START_NS, session_id)
    if marker is None:
        return None
    try:
        return marker.stat().st_mtime
    except OSError:
        return None


# 세션이 시작된 뒤 <prefix> 아래 파일이 하나라도 새로 쓰였나. 판단이 안 서면 None.
#
# **`changed_paths()`(git)로 하지 않는 이유가 이 함수의 요점이다.** git status 는 세션을
# 구분하지 못해서, 지난 세션이 남긴 미커밋 기록이 이번 세션을 그냥 통과시킨다 —
# 2026-08-17 에 실제로 그 상태였고(미커밋 3건), 기록이 밀릴수록 검사가 더 헐거워지는
# 정반대 방향이었다. 세션 시작 시각과 비교하면 그 구멍이 안 생긴다. 커밋은 작업트리의
# mtime 을 건드리지 않으므로 방금 커밋한 기록도 그대로 잡힌다
def wrote_under(prefix: str, session_id: str) -> bool | None:
    started = session_started_at(session_id)
    if started is None:
        return None

    root = PROJECT_ROOT / prefix
    if not root.is_dir():
        return False

    try:
        for path in root.rglob("*"):
            if path.is_file() and path.stat().st_mtime > started:
                return True
    except OSError:
        return None
    return False


# 마커의 mtime. 없거나 못 읽으면 None. 세션 안에서 "마지막으로 ~한 시각"을 담는 데 쓴다
def marker_mtime(namespace: str, session_id: str) -> float | None:
    marker = _marker_path(namespace, session_id)
    if marker is None:
        return None
    try:
        return marker.stat().st_mtime
    except OSError:
        return None


# 마커를 만들거나 mtime 을 지금으로 갱신한다. 실패해도 조용히 넘어간다
def touch_marker(namespace: str, session_id: str) -> None:
    marker = _marker_path(namespace, session_id)
    if marker is None:
        return
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except OSError:
        return


# 마커를 지운다. 없으면 아무 일도 안 한다. `touch_marker` 의 짝이다.
#
# 세션 마커는 대부분 "한 번 켜지면 끝"이라 지울 일이 없었지만, **켰다 껐다 하는 게이트**는
# 끄는 쪽이 있어야 성립한다. 실패해도 조용히 넘어가는 것은 touch_marker 와 같은 규약이다 —
# 못 지우면 게이트가 열린 채로 남는데, 그건 사용자를 가두는 쪽이 아니라 통과시키는 쪽이다
def clear_marker(namespace: str, session_id: str) -> None:
    marker = _marker_path(namespace, session_id)
    if marker is None:
        return
    try:
        marker.unlink()
    except OSError:
        return


# 기준 시각 이후에 바뀐 파일들의 저장소 기준 경로. 판단이 안 서면 None.
#
# `changed_paths()`(git)와 쓰임이 다르다. 저쪽은 "커밋 안 된 것"을 묻고 이쪽은 "이 시각
# 이후에 손댄 것"을 묻는다. 세션 안에서 방금 무엇을 고쳤는지 보려면 이쪽이어야 한다
def paths_newer_than(prefixes: tuple[str, ...], since: float) -> list[str] | None:
    found: list[str] = []
    try:
        for prefix in prefixes:
            root = PROJECT_ROOT / prefix
            if not root.is_dir():
                continue
            for path in root.rglob("*.py"):
                if path.is_file() and path.stat().st_mtime > since:
                    found.append(path.relative_to(PROJECT_ROOT).as_posix())
    except OSError:
        return None
    return found


# V2 History Gate가 쓰는 범용 변경 탐지. `paths_newer_than()`은 기존 Python 자동 테스트의
# 계약이라 `.py`만 보지만, V2는 TypeScript·Java·Rust 등 파일 확장자를 가정할 수 없다.
# 항목이 `/`로 끝나면 디렉터리, 아니면 정확한 파일로 취급한다.
def tracked_paths_newer_than(entries: tuple[str, ...], since: float) -> list[str] | None:
    found: list[str] = []
    try:
        for entry in entries:
            normalized = entry.replace("\\", "/")
            while normalized.startswith("./"):
                normalized = normalized[2:]
            normalized = normalized.lstrip("/")
            if not normalized:
                continue
            path = PROJECT_ROOT / normalized
            if normalized.endswith("/"):
                if not path.is_dir():
                    continue
                for child in path.rglob("*"):
                    if child.is_file() and child.stat().st_mtime > since:
                        found.append(child.relative_to(PROJECT_ROOT).as_posix())
            elif path.is_file() and path.stat().st_mtime > since:
                found.append(path.relative_to(PROJECT_ROOT).as_posix())
    except OSError:
        return None
    return found


# UserPromptSubmit 페이로드에서 사용자가 친 글을 꺼낸다. 없으면 빈 문자열.
#
# **필드명을 하나로 못 박지 않는 것이 이 함수의 요점이다.** 두 훅이 `user_input` 하나만
# 읽고 있었는데 실제로 오는 필드는 `prompt` 라, 사용자가 게이트 문구를 말해도 훅에는 늘 빈
# 값이 들어가 **면담 게이트가 한 번도 안 열렸다**(2026-08-21 발견). 두 훅 다 그 줄 위에
# "필드명은 user_input 이다. prompt 가 아니다 — 틀리면 늘 빈 값이라 아무 경고 없이 영영 안
# 걸린다" 는 경고를 적어두고 그 실수를 했다.
#
# 그래서 **둘 다 본다.** 하네스가 필드명을 바꿔도 한쪽이 받는다 — 이 훅들의 공통 규약
# ("판단이 서지 않으면 막지 않는다")과 같은 방향이고, 잘못 고르면 조용히 안 걸리는 종류라
# 관대한 쪽이 맞다. 값이 있는 첫 필드를 쓴다
def prompt_text(payload: dict) -> str:
    for key in ("prompt", "user_input"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


# 종료를 막고 사유를 모델에게 넘긴다. 이 함수는 돌아오지 않는다
def block(reason: str) -> None:
    # Windows 콘솔 기본 인코딩(cp949)으로는 한국어 사유를 못 내보내 UnicodeEncodeError 로
    # 훅이 죽는다. 실패 경로에서만 드러나므로 여기서 못 박는다
    sys.stderr.reconfigure(encoding="utf-8")
    print(reason, file=sys.stderr)
    # Stop 훅에서 종료코드 2 는 "멈추지 말고 대화를 이어가라"는 뜻이고, stderr 가 모델에게
    # 전달된다
    sys.exit(2)
