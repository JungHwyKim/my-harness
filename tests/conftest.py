"""훅 테스트 공용 픽스처.

훅은 `.claude/hooks/` 에 있어 패키지가 아니다. 실제 실행도 파일 경로로 직접 호출되므로
(`settings.json` 의 command), 테스트도 그 디렉터리를 `sys.path` 에 얹어 같은 방식으로
임포트한다. `task_log_check.py` 와 `plan_log_check.py` 가 `import _hookutil` 로 평평하게
부르기 때문에 이 경로가 없으면 임포트 자체가 안 된다.
"""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from _escape_hatches import ESCAPE_HATCHES

# tests/conftest.py -> 플러그인 저장소 뿌리
REPO_ROOT = Path(__file__).resolve().parents[1]

HOOKS_DIR = REPO_ROOT / ".claude" / "harness" / "hooks"

# 옛 이름. 이 저장소에는 «프로젝트» 가 없고 플러그인만 있는데, 테스트 여럿이 이 이름으로
# 임시 저장소를 만들어 쓴다. 뜻이 바뀐 것을 이름으로 알리려 아래에서 REPO_ROOT 를 쓴다
PROJECT_ROOT = REPO_ROOT

# 스킬이 부르는 수집기들. 훅과 달리 **패키지**라 그 폴더가 아니라 부모를 얹는다
SCRIPT_DIRS = (
    REPO_ROOT / ".claude" / "harness" / "scripts",
)

# 모듈 수준에서 얹는다. conftest 는 같은 폴더의 테스트 모듈보다 먼저 임포트되므로
# 이 시점이면 테스트가 `import _hookutil` 하기 전이 보장된다
for _path in (HOOKS_DIR, *SCRIPT_DIRS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


# 비어 있는 임시 git 저장소. `changed_paths()` 를 실제 git 으로 재기 위한 것이다.
#
# 이 픽스처가 fake 가 아니라 진짜 저장소인 이유가 있다. `_hookutil` 의 `-uall`/`-z` 누락은
# git 의 실제 출력 형태로만 드러나서, subprocess 를 모킹하면 그 버그가 그대로 통과한다.
# 실제로 구현 중에 그렇게 놓친 적이 있다(_hookutil 모듈 docstring 참조).
#
# git 이 없는 환경에서도 기본 테스트는 통과해야 하므로 그때는 조용히 skip 한다 —
# tests/fixtures/ 가 없을 때 실파일 회귀 테스트가 skip 되는 것과 같은 방침이다
@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    if shutil.which("git") is None:
        pytest.skip("git 이 PATH 에 없다")

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-q"],
        cwd=repo,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    return repo


# 마커 파일만 검사하는 테스트용.
#
# **한때 `.git/` 을 만들었다** — 마커가 거기 살았기 때문이다. 플러그인으로 옮기며 마커가
# `CLAUDE_PLUGIN_DATA` 아래로 갔으므로(`.git` 이 없는 프로젝트가 실재한다) 여기도 따라간다
@pytest.fixture
def marker_root(tmp_path: Path) -> Path:
    (tmp_path / ".claude").mkdir(exist_ok=True)
    return tmp_path


# 훅이 마커를 개발자의 실제 플러그인 데이터 폴더에 쓰지 않게 막는다.
#
# **autouse 인 것이 요점이다.** 각 테스트가 손으로 덮는 규약이면 새 테스트가 잊는 순간 다시
# 샌다 — 원 저장소가 `ORIGINALS_DIR`·`QUERY_LOG_PATH` 에서 이미 밟은 자리다.
# 환경변수인 것은 `_marker_root()` 가 **호출 때마다** 읽어서, 한 줄이 in-process 와
# subprocess 양쪽에 다 먹기 때문이다
@pytest.fixture(autouse=True)
def _isolate_plugin_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "_plugin_data"))


# `.claude/harness.json` 을 가진 임시 프로젝트.
#
# 훅들이 프로젝트별 값을 이 파일에서 읽으므로, 그 값을 재는 테스트는 진짜 파일을 만들어야
# 한다. **모킹 대신 실제 파일인 이유는 `git_repo` 와 같다** — 읽는 경로(BOM·인코딩·
# `check_config` 의 None 대우)가 실제 파일에서만 드러난다.
#
# `CLAUDE_PROJECT_DIR` 도 함께 세워, 훅을 **프로세스로** 돌리는 테스트가 이 프로젝트를 보게 한다
@pytest.fixture
def harness_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def build(config: dict | None = None) -> Path:
        root = tmp_path / "proj"
        (root / ".claude").mkdir(parents=True, exist_ok=True)
        path = root / ".claude" / "harness.json"
        if config is None:
            # **지우는 것이 요점이다.** 안 지우면 앞서 깐 설정이 남아, «설정이 없을 때» 를
            # 재려던 테스트가 실은 설정이 있는 상태를 재고 통과한다
            path.unlink(missing_ok=True)
        else:
            path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
        return root

    return build


# 설정을 읽은 상태의 훅 모듈.
#
# **훅의 프로젝트별 상수는 임포트할 때 정해진다.** 운영에서는 그게 맞다 — 훅 호출마다
# 프로세스가 새로 뜨므로 늘 그 시점의 설정을 읽는다. 그래서 테스트도 **다시 임포트**해서
# 같은 길을 밟는다. 상수를 monkeypatch 로 갈아끼우면 그 경로(파일을 읽고 절을 고르는 부분)를
# 통째로 건너뛰어, 설정을 잘못 읽는 버그가 초록인 채로 지나간다.
#
# `_hookutil` 을 먼저 되읽는 이유는 뿌리(`PROJECT_ROOT`)와 캐시(`_CONFIG`)가 거기 있어서다
@pytest.fixture
def load_hook(harness_project):
    def load(module_name: str, config: dict | None = None):
        root = harness_project(config)

        import _hookutil

        importlib.reload(_hookutil)
        module = importlib.import_module(module_name)
        importlib.reload(module)
        return module, root

    return load



# 훅 테스트가 개발자 환경의 탈출구를 물려받지 않게 한다.
#
# 훅은 전부 `main()` 첫머리에서 자기 탈출구를 보고 **즉시 반환**한다. 그 변수가 켜진 채로
# 테스트를 돌리면 검사 대상이 아예 안 돌고, 결과가 두 갈래로 갈린다 — 마커나 출력을
# 단정하는 테스트는 실패하고(실측 2026-08-22: SKIP_PLANINTERVIEW=1 에서 13개,
# ALLOW_PAID_TESTS=1 에서 2개), "아무것도 안 낸다"를 단정하는 테스트는 **조용히 통과한다.**
# 뒤쪽이 더 나쁘다 — 이 저장소가 훅마다 두려워한 "검사가 있는 줄 알았는데 없는" 그 상태다.
#
# 탈출구를 켜는 것은 정상 사용이다(면담을 건너뛰는 세션 등). 그 사용자에게 저장소가 빨갛게
# 보이면 SKIP_*=1 이 더 굳어지므로, 고칠 곳은 훅이 아니라 테스트 격리다.
#
# **프로세스 안에서 지우는 것이 요점이다.** `monkeypatch.delenv` 가 `os.environ` 을 고치고
# `subprocess.run` 은 그것을 물려받으므로, 훅을 실제 프로세스로 돌리는 테스트까지 함께
# 덮인다(paid 쪽 둘이 그렇다). 탈출구 자체를 재는 테스트는 본문에서 `setenv` 로 다시
# 켜는데, 픽스처가 먼저 도므로 순서가 맞다
@pytest.fixture(autouse=True)
def _clear_escape_hatches(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ESCAPE_HATCHES:
        monkeypatch.delenv(name, raising=False)
