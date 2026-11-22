"""하네스를 복사해 넣은 직후의 **정적** 진단 CLI.

이 명령이 있는 이유는 설정 오류가 **에러 없이 통과한다**는 것이다. `_hookutil.config()` 는
읽기 실패를 빈 사전으로 흡수하고(`:64`), `schema_version` 이 이상하면 조용히 V1 으로
떨어지고(`:80`), `tracked_paths` 항목에서 끝의 `/` 가 빠지면 변경 탐지가 아무것도 못
찾는다(`auto_test_check.py:80`). 어느 쪽도 사람에게 신호를 주지 않는다 — 검사가 **꺼진
채로 통과**한다. 그래서 그 조용한 자리들만 모아 한 번에 들여다본다.

**명령을 실행하지 않는 것이 이 CLI 의 보안·비용 경계다.** 훅·stage·Git·다른 인터프리터를
돌리지 않고, 대상 프로젝트의 모듈을 import 하지도 않는다. 그래서 「결선이 맞다」까지만
말할 수 있고 「명령이 성공한다」는 말하지 못한다. 그 한계를 출력에 적는다.

**실행기보다 엄격한 자리가 몇 군데 있다.** 스키마가 허용하는데 소비자가 무시하는 조합
(fast 에 stop 트리거 같은 것)은 스키마만 봐서는 안 보이고, 그런 설정은 조용히 안 도는
쪽으로 고장 난다. 그 자리는 FAIL 로 올리고 근거를 함께 적는다.

종료 코드는 셋이다. 0 = FAIL 없음, 1 = 발견한 FAIL 있음, 2 = **진단 자체를 못 마쳤다**.
2 를 따로 둔 이유는 「문제 없음」과 「못 봤음」이 같은 0 으로 보이면 안 되기 때문이다.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

# `_hookutil._wiki_root()` 의 기본값과 같아야 한다. 어긋나면 Doctor 가 훅이 보는 자리와
# 다른 자리를 보고 「없다」고 말한다
DEFAULT_WIKI_ROOT = ".claude/wiki/"

HARNESS_JSON = ".claude/harness.json"
SETTINGS_JSON = ".claude/settings.json"
HOOKS_DIR = ".claude/harness/hooks"

# `_quality.py:22` 의 집합과 같아야 한다
LIST_PLACEHOLDERS = ("{changed_files}", "{mapped_targets}")
KNOWN_PLACEHOLDERS = ("{python}", *LIST_PLACEHOLDERS)

# 아래 다섯 묶음은 `.claude/harness/schemas/harness.schema.json` 을 그대로 옮긴 것이다.
# **코드에 옮긴 이유는 `jsonschema` 를 새로 깔지 않기로 했기 때문이고**, 그러면 스키마와
# 어긋날 수 있다. 그래서 `tests/test_doctor.py` 가 스키마 파일을 읽어 이 상수들과 대조한다
ROOT_REQUIRED = ("schema_version", "wiki_root", "history", "quality")
HISTORY_REQUIRED = ("plan", "task", "verify", "tracked_paths")
HISTORY_ALLOWED = HISTORY_REQUIRED
QUALITY_REQUIRED = ("profiles",)
QUALITY_ALLOWED = ("tracked_paths", "mappings", "unmapped_by_design", "profiles")
PROFILE_REQUIRED = ("triggers", "stages")
PROFILE_ALLOWED = PROFILE_REQUIRED
STAGE_REQUIRED = ("id", "argv")
STAGE_ALLOWED = ("id", "label", "argv", "cwd", "timeout", "success_codes")
MAPPING_REQUIRED = ("path", "tests")
MAPPING_ALLOWED = ("path", "tests", "why")
TRIGGER_ENUM = ("post_change", "stop", "pre_commit")
STAGE_ID_PATTERN = "^[a-z][a-z0-9_-]*$"
PROFILE_NAMES = ("fast", "full")

# 스키마가 아니라 **소비자가** 정하는 것. `auto_test_check.py:281`·`:316` 과
# `pre_commit_check.py:165` 가 실제로 읽는 조합만 적는다. 스키마 enum 에 있어도 여기
# 없는 조합은 아무도 처리하지 않아 조용히 안 돈다
CONSUMER_TRIGGERS = {"fast": ("post_change",), "full": ("stop", "pre_commit")}


@dataclass(frozen=True)
class Wiring:
    profile: str
    trigger: str
    event: str
    tools: tuple[str, ...]
    script: str


# 활성 트리거마다 반드시 있어야 하는 결선. `full / stop` 에 도구가 없는 것은 Stop 이벤트에
# 도구 matcher 가 없기 때문이다(`settings.json:131`)
REQUIRED_WIRING = (
    Wiring(
        "fast",
        "post_change",
        "PostToolUse",
        ("Write", "Edit", "Bash", "PowerShell"),
        "auto_test_check.py",
    ),
    Wiring("full", "stop", "Stop", (), "auto_test_check.py"),
    Wiring("full", "pre_commit", "PreToolUse", ("Bash", "PowerShell"), "pre_commit_check.py"),
)

# 이름 목록으로 읽을 matcher 의 모양. 정규식 메타문자가 하나도 없을 때만 이 길로 간다
_NAME_LIST_RE = re.compile(r"^[A-Za-z0-9_\-, |]+$")

# **차단 목록으로는 안 된다.** Python 이 컴파일했다는 사실은 JavaScript 와 뜻이 같다는
# 근거가 못 된다. 실측(V8, 2026-11-22)으로 `(?i)Write` 는 Invalid group 이고
# `Bash++`·`Bash*+`·`Bash?+`·`Bash{1,2}+` 는 Nothing to repeat 인데 Python 3.12 는 넷 다
# 받는다. 그래서 **뜻이 같다고 확인한 문법만** 받고(아래 `classify_pattern`), 나머지는
# 「확인 불가」로 남긴다 — 틀린 PASS 보다 모른다는 말이 낫다
#
# 두 엔진에서 뜻이 같다고 확인한 이스케이프. 목록에 없는 글자는 확인 불가다
_COMMON_ESCAPES = "dDwWsSbBnrtfv0" + "^$.|?*+()[]{}/\\-"

# V8 이 Invalid group 으로 거부한다고 확정한 그룹 문법(실측). 어느 도구에도 걸릴 수 없다
_JS_INVALID_GROUPS = ("(?P<", "(?P=", "(?#", "(?>", "(?(")

# **전역** 인라인 플래그 `(?i)`. JavaScript 에는 범위가 있는 형태만 있어서 V8 은 Invalid
# group 이다(실측). 범위가 있는 `(?i:…)` 는 아래에서 따로 본다 — 둘을 한 규칙으로 묶으면
# 정상 설정을 FAIL 시킨다(R3-04)
_GLOBAL_FLAG_RE = re.compile(r"^\(\?[a-zA-Z]+\)")

# 범위가 있는 modifier 그룹 `(?ims-ims:…)`. 켜는 쪽과 끄는 쪽을 따로 잡는다
_SCOPED_FLAG_RE = re.compile(r"^\(\?([a-zA-Z]*)(?:-([a-zA-Z]*))?:")

# modifier 그룹이 받는 플래그는 i·m·s 뿐이다(MDN). 그 밖의 글자는 modifier 를 지원하는
# 엔진에서도 Invalid group 이고(실측) 지원하지 않는 엔진에서도 오류다 — 엔진과 무관하다
_JS_MODIFIER_FLAGS = frozenset("ims")

# 두 엔진에서 뜻이 같은 그룹 시작. 룩비하인드는 Python 이 고정 너비만 받아서 제외한다
_COMMON_GROUP_OPENS = ("(?:", "(?=", "(?!")

# 셸이 해석하는 글자. 따옴표 밖에서 보이면 명령을 정적으로 못 읽는다.
# `$` 를 넣지 않는 것은 `${CLAUDE_PROJECT_DIR}` 를 치환해 쓰기 때문이다
_SHELL_OPERATORS = ("|", "&", ";", "<", ">", "`", "\n")

_PYTHON_NAMES = ("python", "python3", "py", "python.exe", "python3.exe", "py.exe")

# Python 의 실행 옵션. **스크립트 자리를 찾으려면 이 표가 있어야 한다.** `.py` 로 끝나는
# 인자가 있다는 것은 실행 증거가 아니다 — `python -c pass "<훅>.py"` 는 그 파일을 열지도
# 않는데 결선으로 인정됐다(R2-01). 모르는 옵션에서 멈추는 것도 같은 이유다. 값을 받는
# 옵션을 모르면 그 값을 스크립트로 읽는다
_PY_NO_SCRIPT_MODES = ("-c", "-m", "-V", "--version", "-h", "--help", "-?")
_PY_VALUE_OPTS = ("-W", "-X", "--check-hash-based-pycs")
_PY_FLAG_RE = re.compile(r"^-[uBEIOsSvqbdPRt]+$")
_PY_LAUNCHER_RE = re.compile(r"^-[0-9](\.[0-9]+)?(-(32|64|arm64))?$")


@dataclass(frozen=True)
class Finding:
    level: str
    check: str
    where: str
    why: str
    fix: str = ""


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, level: str, check: str, where: str, why: str, fix: str = "") -> None:
        self.findings.append(Finding(level, check, where, why, fix))

    def ok(self, check: str, where: str, why: str) -> None:
        self.add(PASS, check, where, why)

    def unchecked(self, check: str, where: str, why: str) -> None:
        # **미검사는 PASS 가 아니다.** 선행 오류로 못 본 것을 PASS 로 적으면 이 CLI 가
        # 막으려는 「꺼진 채로 통과」를 CLI 자신이 하게 된다
        self.add(WARN, check, where, f"미검사 — {why}", "선행 오류를 고친 뒤 다시 실행한다.")

    @property
    def failed(self) -> bool:
        return any(item.level == FAIL for item in self.findings)


class LayoutError(Exception):
    """Doctor 가 자기 배치를 신뢰할 수 없을 때. 진단을 시작하지 않는다."""


# ───────────────────────── 대상 루트 ─────────────────────────


# **`__file__` 로 루트를 세는 것은 `_hookutil.py:30` 이 일부러 기각한 방법이다.** 저쪽은
# 플러그인 설치 경로에 살 수 있어서 위로 세면 저장소가 아니라 플러그인 폴더가 나온다.
# 이 CLI 는 전제가 다르다 — 저장소에 복사해 넣고 그 저장소를 진단한다. 그래서 `__file__`
# 을 쓰되, **쓰기 전에 배치가 그 전제와 맞는지 먼저 본다.** 어긋나면 남의 폴더를 진단하는
# 대신 멈춘다. 이것이 두 결정이 공존하는 방식이다
def resolve_root(script: Path) -> Path:
    try:
        resolved = script.resolve()
    except OSError as exc:
        raise LayoutError(f"스크립트 경로를 해석하지 못했습니다: {exc}") from exc

    parents = resolved.parents
    expected = ("scripts", "harness", ".claude")
    if len(parents) < 4:
        raise LayoutError(
            f"배치 전제와 다릅니다: {resolved} 가 <root>/{HOOKS_DIR.rsplit('/', 1)[0]}"
            "/scripts/ 아래가 아닙니다."
        )
    actual = (parents[0].name, parents[1].name, parents[2].name)
    if actual != expected:
        raise LayoutError(
            f"배치 전제와 다릅니다: {resolved} 는 <root>/.claude/harness/scripts/ 아래여야 "
            f"하는데 상위가 {'/'.join(reversed(actual))} 입니다."
        )

    root = parents[3]
    if not root.is_dir():
        raise LayoutError(f"대상 루트에 접근할 수 없습니다: {root}")
    return root


# ───────────────────────── JSON 읽기 ─────────────────────────


@dataclass
class Loaded:
    path: str
    data: dict | None
    error: str | None

    @property
    def usable(self) -> bool:
        return self.data is not None


# BOM 을 받는 것이 요점이다. `_hookutil.py:68` 과 같은 이유로 utf-8-sig 를 쓴다 — BOM 이
# 붙으면 json 이 죽고 그 예외가 ValueError 하위라 조용히 빈 설정이 된다
def load_json(root: Path, relative: str) -> Loaded:
    target = root / relative
    try:
        text = target.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return Loaded(relative, None, "파일이 없습니다.")
    except OSError as exc:
        return Loaded(relative, None, f"읽지 못했습니다: {exc}")
    except UnicodeDecodeError as exc:
        return Loaded(relative, None, f"UTF-8 로 디코딩하지 못했습니다: {exc}")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return Loaded(relative, None, f"JSON 문법 오류 ({exc.lineno}행 {exc.colno}열): {exc.msg}")

    if not isinstance(parsed, dict):
        return Loaded(relative, None, f"최상위가 객체가 아닙니다: {type(parsed).__name__}")
    return Loaded(relative, parsed, None)


# ───────────────────────── 경로 규약 ─────────────────────────


# `_hookutil.tracked_paths_newer_than()` 의 정규화를 그대로 옮긴 것이다. 여기서 어긋나면
# Doctor 가 런타임과 다른 항목을 보고 판정한다
def normalize_entry(entry: str) -> str:
    value = entry.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value.lstrip("/")


# `_hookutil._wiki_root()` 와 같다. `strip()` 한 값을 쓰지 않고 원본을 쓰는 것까지 같다
def wiki_root_of(config: dict) -> str:
    raw = config.get("wiki_root")
    value = raw if isinstance(raw, str) and raw.strip() else DEFAULT_WIKI_ROOT
    return value if value.endswith("/") else value + "/"


# `_hookutil.history_prefix()` 와 같다
def history_prefix_of(config: dict, kind: str, wiki_root: str) -> str:
    section = config.get("history")
    raw = section.get(kind) if isinstance(section, dict) else None
    value = raw.strip().replace("\\", "/") if isinstance(raw, str) else ""
    if not value:
        value = f"history/{kind}/"
    while value.startswith("./"):
        value = value[2:]
    value = value.lstrip("/")
    if not value.startswith(wiki_root):
        value = wiki_root + value
    return value if value.endswith("/") else value + "/"


def string_list(config: dict, key: str) -> tuple[str, ...]:
    value = config.get(key)
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


# ───────────────────────── 필수 파일 ─────────────────────────


def check_files(root: Path, report: Report) -> None:
    for relative in ("CLAUDE.md", HARNESS_JSON, SETTINGS_JSON):
        target = root / relative
        if not target.is_file():
            report.add(
                FAIL,
                "D-FILES",
                relative,
                "필수 파일이 없습니다.",
                "템플릿의 같은 경로에서 복사하거나 기존 파일에 병합한다.",
            )
            continue
        try:
            target.read_bytes()
        except OSError as exc:
            report.add(
                FAIL, "D-FILES", relative, f"읽지 못했습니다: {exc}", "권한과 파일 상태를 확인한다."
            )
            continue
        report.ok("D-FILES", relative, "있고 읽을 수 있습니다.")

    agents = root / "AGENTS.md"
    if agents.is_file():
        report.ok("D-OPTIONAL", "AGENTS.md", "있습니다.")
    else:
        report.add(
            WARN,
            "D-OPTIONAL",
            "AGENTS.md",
            "Codex 진입점이 없습니다.",
            "Codex 를 함께 쓸 때만 필요하다. 쓰지 않으면 그대로 두어도 된다.",
        )


# Wiki 두 README 는 `wiki_root` 아래에 있다. 그래서 설정을 읽지 못했거나 버전 2 에서
# `wiki_root` 가 깨졌으면 **어디를 봐야 할지 모른다** — 임의의 기본값으로 보고 FAIL 을
# 더 만들지 않고 미검사로 남긴다
def check_wiki_files(root: Path, report: Report, harness: Loaded, wiki_root: str | None) -> None:
    targets = ("overview/README.md", "knowledge/README.md")
    if wiki_root is None:
        reason = (
            f"{harness.path} 의 선행 오류로 wiki_root 를 확정할 수 없습니다"
            if not harness.usable
            else f"{harness.path} 의 wiki_root 가 올바르지 않습니다"
        )
        for name in targets:
            report.unchecked("D-FILES", f"<wiki_root>/{name}", reason)
        return

    for name in targets:
        relative = f"{wiki_root}{name}"
        if (root / relative).is_file():
            report.ok("D-FILES", relative, "있습니다.")
        else:
            report.add(
                FAIL,
                "D-FILES",
                relative,
                "Wiki 필수 문서가 없습니다.",
                f"{wiki_root} 아래에 만들거나 harness.json 의 wiki_root 를 고친다.",
            )


# ───────────────────────── 버전 ─────────────────────────


@dataclass(frozen=True)
class Version:
    value: object
    present: bool
    v2_detail: bool  # V2 상세 구조 검증을 돌릴지


# `_hookutil.schema_version()` 은 bool 을 제외한 양의 정수만 받고 나머지를 전부 1 로
# 떨군다(`:82`). 그 사실을 **메시지에 적는 것이 이 검사의 값이다** — 「지원 안 함」만
# 적으면 지금 V2 게이트가 꺼져 있다는 정작 쓸모 있는 사실이 빠진다
def check_version(report: Report, harness: Loaded) -> Version:
    where = f"{harness.path}: schema_version"
    if not harness.usable:
        report.unchecked("D-VERSION", where, f"{harness.path} 을 읽지 못했습니다")
        return Version(None, False, False)

    config = harness.data or {}
    present = "schema_version" in config
    raw = config.get("schema_version")

    if not present:
        report.add(
            WARN,
            "D-VERSION",
            where,
            "필드가 없어 V1 로 분류합니다. 실제 훅도 V1 경로이며 V2 Quality·History "
            "분기는 실행되지 않습니다.",
            "V2 기능이 필요하면 schema_version 을 2 로 추가한다. 자동 마이그레이션은 없다.",
        )
        return Version(raw, False, False)

    if isinstance(raw, bool) or not isinstance(raw, int):
        shown = "null" if raw is None else f"{type(raw).__name__} {raw!r}"
        report.add(
            FAIL,
            "D-VERSION",
            where,
            f"정수가 아닙니다({shown}). _hookutil.schema_version() 이 1 로 대체하므로 "
            "V2 Quality·History 분기가 꺼진 채로 돕니다.",
            'schema_version 을 정수 2 로 고친다 — 따옴표 없이 `"schema_version": 2`.',
        )
        return Version(raw, True, False)

    if raw == 1:
        report.add(
            WARN,
            "D-VERSION",
            where,
            "V1 입니다. 실제 훅도 V1 경로이며 V2 Quality·History 분기는 실행되지 않습니다.",
            "V2 기능이 필요하면 2 로 올린다. 자동 마이그레이션은 없다.",
        )
        return Version(raw, True, False)

    if raw <= 0:
        report.add(
            FAIL,
            "D-VERSION",
            where,
            f"0 이하입니다({raw}). _hookutil.schema_version() 이 1 로 대체하므로 "
            "V2 분기가 꺼진 채로 돕니다.",
            "schema_version 을 2 로 고친다.",
        )
        return Version(raw, True, False)

    if raw >= 3:
        report.add(
            FAIL,
            "D-VERSION",
            where,
            f"현재 스키마는 2 만 지원합니다({raw}). 다만 is_v2() 는 참이므로 실제 훅은 "
            "V2 분기로 돕니다 — 검증되지 않은 조합입니다.",
            "schema_version 을 2 로 내린다. Doctor 는 이 버전의 V2 상세 검증을 생략한다.",
        )
        return Version(raw, True, False)

    report.ok("D-VERSION", where, "V2(2) 입니다.")
    return Version(raw, True, True)


# ───────────────────────── V2 구조 ─────────────────────────


def _type_name(value: object) -> str:
    return "null" if value is None else type(value).__name__


def _check_keys(report: Report, where: str, value: dict, required, allowed) -> None:
    for key in required:
        if key not in value:
            report.add(
                FAIL,
                "D-CONFIG",
                f"{where}.{key}",
                "필수 필드가 없습니다.",
                f"{where} 에 {key} 를 추가한다.",
            )
    for key in value:
        if key not in allowed:
            report.add(
                FAIL,
                "D-CONFIG",
                f"{where}.{key}",
                "스키마가 허용하지 않는 필드입니다.",
                f"{where} 에서 {key} 를 지운다 — 허용: {', '.join(allowed)}.",
            )


def _check_string_array(report: Report, where: str, value: object, *, unique: bool = True) -> None:
    if not isinstance(value, list):
        report.add(
            FAIL,
            "D-CONFIG",
            where,
            f"배열이어야 합니다({_type_name(value)}).",
            "문자열 배열로 고친다.",
        )
        return
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            report.add(
                FAIL,
                "D-CONFIG",
                f"{where}[{index}]",
                f"비어 있지 않은 문자열이어야 합니다({_type_name(item)}).",
                "항목을 문자열로 고친다.",
            )
    if unique:
        strings = [item for item in value if isinstance(item, str)]
        if len(set(strings)) != len(strings):
            report.add(FAIL, "D-CONFIG", where, "중복 항목이 있습니다.", "중복을 지운다.")


def check_history_section(report: Report, path: str, config: dict) -> None:
    where = f"{path}: history"
    section = config.get("history")
    if not isinstance(section, dict):
        if "history" in config:
            report.add(
                FAIL,
                "D-CONFIG",
                where,
                f"객체여야 합니다({_type_name(section)}).",
                "history 를 객체로 고친다.",
            )
        return
    _check_keys(report, where, section, HISTORY_REQUIRED, HISTORY_ALLOWED)
    for kind in ("plan", "task", "verify"):
        if kind in section and not (isinstance(section[kind], str) and section[kind]):
            report.add(
                FAIL,
                "D-CONFIG",
                f"{where}.{kind}",
                f"비어 있지 않은 문자열이어야 합니다({_type_name(section[kind])}).",
                "wiki_root 기준 상대 경로를 적는다.",
            )
    if "tracked_paths" in section:
        _check_string_array(report, f"{where}.tracked_paths", section["tracked_paths"])


def check_quality_section(report: Report, path: str, config: dict) -> None:
    where = f"{path}: quality"
    section = config.get("quality")
    if not isinstance(section, dict):
        if "quality" in config:
            report.add(
                FAIL,
                "D-CONFIG",
                where,
                f"객체여야 합니다({_type_name(section)}).",
                "quality 를 객체로 고친다.",
            )
        return
    _check_keys(report, where, section, QUALITY_REQUIRED, QUALITY_ALLOWED)

    if "tracked_paths" in section:
        _check_string_array(report, f"{where}.tracked_paths", section["tracked_paths"])

    if "unmapped_by_design" in section:
        unmapped = section["unmapped_by_design"]
        if not isinstance(unmapped, dict):
            report.add(
                FAIL,
                "D-CONFIG",
                f"{where}.unmapped_by_design",
                f"객체여야 합니다({_type_name(unmapped)}).",
                "`경로: 이유` 모양의 객체로 적는다.",
            )
        else:
            # 스키마(`harness.schema.json:59`)는 각 값을 문자열로 제한한다. 객체 타입만
            # 보고 끝내면 `{"src/": 42}` 가 조용히 통과한다(R2-03). minLength 는 없으므로
            # 빈 문자열은 거부하지 않는다
            for key, value in unmapped.items():
                if not isinstance(value, str):
                    report.add(
                        FAIL,
                        "D-CONFIG",
                        f"{where}.unmapped_by_design[{key!r}]",
                        f"문자열이어야 합니다({_type_name(value)}).",
                        "제외한 이유를 문자열로 적는다.",
                    )

    mappings = section.get("mappings")
    if "mappings" in section:
        if not isinstance(mappings, list):
            report.add(
                FAIL,
                "D-CONFIG",
                f"{where}.mappings",
                f"배열이어야 합니다({_type_name(mappings)}).",
                "배열로 고친다.",
            )
        else:
            for index, row in enumerate(mappings):
                spot = f"{where}.mappings[{index}]"
                if not isinstance(row, dict):
                    report.add(
                        FAIL,
                        "D-CONFIG",
                        spot,
                        f"객체여야 합니다({_type_name(row)}).",
                        "path·tests 를 가진 객체로 고친다.",
                    )
                    continue
                _check_keys(report, spot, row, MAPPING_REQUIRED, MAPPING_ALLOWED)
                for key in ("path", "tests"):
                    if key in row and not (isinstance(row[key], str) and row[key]):
                        report.add(
                            FAIL,
                            "D-CONFIG",
                            f"{spot}.{key}",
                            f"비어 있지 않은 문자열이어야 합니다({_type_name(row[key])}).",
                            "프로젝트 상대 경로를 적는다.",
                        )
                # 스키마(`harness.schema.json:54`)는 why 를 문자열로 제한한다. path·tests
                # 와 달리 minLength 가 없어 빈 문자열은 적법하다
                if "why" in row and not isinstance(row["why"], str):
                    report.add(
                        FAIL,
                        "D-CONFIG",
                        f"{spot}.why",
                        f"문자열이어야 합니다({_type_name(row['why'])}).",
                        "이유를 문자열로 적거나 키를 지운다.",
                    )

    profiles = section.get("profiles")
    if "profiles" not in section:
        return
    if not isinstance(profiles, dict):
        report.add(
            FAIL,
            "D-CONFIG",
            f"{where}.profiles",
            f"객체여야 합니다({_type_name(profiles)}).",
            "fast·full 을 담은 객체로 고친다.",
        )
        return
    for name in profiles:
        if name not in PROFILE_NAMES:
            report.add(
                FAIL,
                "D-CONFIG",
                f"{where}.profiles.{name}",
                "스키마가 허용하지 않는 profile 이름입니다.",
                f"{name} 을 지운다 — 허용: {', '.join(PROFILE_NAMES)}.",
            )
    for name in PROFILE_NAMES:
        if name in profiles:
            _check_profile(report, f"{where}.profiles.{name}", name, profiles[name])


def _check_profile(report: Report, where: str, name: str, profile: object) -> None:
    if not isinstance(profile, dict):
        report.add(
            FAIL,
            "D-CONFIG",
            where,
            f"객체여야 합니다({_type_name(profile)}).",
            "triggers·stages 를 가진 객체로 고친다.",
        )
        return
    _check_keys(report, where, profile, PROFILE_REQUIRED, PROFILE_ALLOWED)

    triggers = profile.get("triggers")
    if "triggers" in profile:
        if not isinstance(triggers, list):
            report.add(
                FAIL,
                "D-CONFIG",
                f"{where}.triggers",
                f"배열이어야 합니다({_type_name(triggers)}).",
                "배열로 고친다.",
            )
        else:
            for index, item in enumerate(triggers):
                if item not in TRIGGER_ENUM:
                    report.add(
                        FAIL,
                        "D-CONFIG",
                        f"{where}.triggers[{index}]",
                        f"스키마 enum 밖입니다({item!r}).",
                        f"허용: {', '.join(TRIGGER_ENUM)}.",
                    )
            if len(set(map(repr, triggers))) != len(triggers):
                report.add(
                    FAIL,
                    "D-CONFIG",
                    f"{where}.triggers",
                    "중복 트리거가 있습니다.",
                    "중복을 지운다.",
                )

    stages = profile.get("stages")
    if "stages" in profile:
        if not isinstance(stages, list):
            report.add(
                FAIL,
                "D-CONFIG",
                f"{where}.stages",
                f"배열이어야 합니다({_type_name(stages)}).",
                "배열로 고친다.",
            )
        else:
            _check_stage_shapes(report, where, name, stages)


def _check_stage_shapes(report: Report, where: str, name: str, stages: list) -> None:
    seen: set[str] = set()
    for index, stage in enumerate(stages):
        spot = f"{where}.stages[{index}]"
        if not isinstance(stage, dict):
            report.add(
                FAIL,
                "D-CONFIG",
                spot,
                f"객체여야 합니다({_type_name(stage)}).",
                "id·argv 를 가진 객체로 고친다.",
            )
            continue
        _check_keys(report, spot, stage, STAGE_REQUIRED, STAGE_ALLOWED)

        stage_id = stage.get("id")
        if "id" in stage:
            if not isinstance(stage_id, str) or not re.fullmatch(STAGE_ID_PATTERN, stage_id):
                report.add(
                    FAIL,
                    "D-CONFIG",
                    f"{spot}.id",
                    f"스키마 패턴 {STAGE_ID_PATTERN} 과 맞지 않습니다({stage_id!r}).",
                    "소문자로 시작하고 소문자·숫자·`_`·`-` 만 쓴다.",
                )
            else:
                # 실행기는 strip 한 id 로 중복을 본다(`_quality.py:113`). 스키마에는 이
                # 제약이 없어서, 중복은 여기서만 걸린다
                if stage_id.strip() in seen:
                    report.add(
                        FAIL,
                        "D-CONFIG",
                        f"{spot}.id",
                        f"같은 profile 에 stage id {stage_id!r} 가 중복됩니다. "
                        "load_profile() 이 QualityConfigError 로 막습니다.",
                        "id 를 서로 다르게 고친다.",
                    )
                seen.add(stage_id.strip())

        # **argv 의 모양을 여기서 봐야 한다.** 아래 D-ARGV 는 치환값과 실행 파일을 보는
        # 검사라 목록이 아니거나 비어 있으면 볼 것이 없어 그대로 돌아간다. 그러면
        # `argv: []`·`argv: "ruff"` 가 아무 말 없이 통과하는데, 실행기는 둘 다
        # QualityConfigError 로 막는다(`_quality.py:120`)
        argv = stage.get("argv")
        if "argv" in stage:
            if not isinstance(argv, list) or not argv:
                report.add(
                    FAIL,
                    "D-CONFIG",
                    f"{spot}.argv",
                    f"비어 있지 않은 문자열 배열이어야 합니다({_type_name(argv)}). "
                    "load_profile() 이 막습니다.",
                    '실행할 명령을 배열로 적는다 — 예: ["{python}", "-m", "pytest"].',
                )
            else:
                for pos, item in enumerate(argv):
                    if not isinstance(item, str):
                        report.add(
                            FAIL,
                            "D-CONFIG",
                            f"{spot}.argv[{pos}]",
                            f"문자열이어야 합니다({_type_name(item)}). load_profile() 이 막습니다.",
                            "항목을 문자열로 고친다.",
                        )

        if "label" in stage and not (isinstance(stage["label"], str) and stage["label"].strip()):
            report.add(
                FAIL,
                "D-CONFIG",
                f"{spot}.label",
                f"비어 있지 않은 문자열이어야 합니다({_type_name(stage['label'])}).",
                "label 을 지우면 id 가 기본값으로 쓰인다.",
            )

        if "cwd" in stage and not (isinstance(stage["cwd"], str) and stage["cwd"].strip()):
            report.add(
                FAIL,
                "D-CONFIG",
                f"{spot}.cwd",
                f"비어 있지 않은 문자열이어야 합니다({_type_name(stage['cwd'])}).",
                "cwd 를 지우면 프로젝트 루트가 기본값으로 쓰인다.",
            )

        timeout = stage.get("timeout")
        if "timeout" in stage:
            bad = (
                isinstance(timeout, bool)
                or not isinstance(timeout, int)
                or not 1 <= timeout <= 3600
            )
            if bad:
                report.add(
                    FAIL,
                    "D-CONFIG",
                    f"{spot}.timeout",
                    f"1~3600 사이 정수여야 합니다({_type_name(timeout)} {timeout!r}).",
                    "정수로 고치거나 지워서 기본값 120 을 쓴다.",
                )

        codes = stage.get("success_codes")
        if "success_codes" in stage:
            if not isinstance(codes, list) or not codes:
                report.add(
                    FAIL,
                    "D-CONFIG",
                    f"{spot}.success_codes",
                    f"비어 있지 않은 배열이어야 합니다({_type_name(codes)}).",
                    "정수 배열로 고치거나 지워서 기본값 [0] 을 쓴다.",
                )
            else:
                for pos, code in enumerate(codes):
                    if isinstance(code, bool) or not isinstance(code, int):
                        report.add(
                            FAIL,
                            "D-CONFIG",
                            f"{spot}.success_codes[{pos}]",
                            f"정수여야 합니다({_type_name(code)}).",
                            "정수로 고친다.",
                        )
                if len(set(map(repr, codes))) != len(codes):
                    report.add(
                        FAIL,
                        "D-CONFIG",
                        f"{spot}.success_codes",
                        "중복 코드가 있습니다.",
                        "중복을 지운다.",
                    )


# ───────────────────────── 트리거 조합 ─────────────────────────


def profile_of(config: dict, name: str) -> dict | None:
    quality = config.get("quality")
    profiles = quality.get("profiles") if isinstance(quality, dict) else None
    if not isinstance(profiles, dict):
        return None
    profile = profiles.get(name)
    return profile if isinstance(profile, dict) else None


def triggers_of(config: dict, name: str) -> tuple[str, ...]:
    profile = profile_of(config, name)
    raw = profile.get("triggers") if profile else None
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, str))


def stages_of(config: dict, name: str) -> tuple[dict, ...]:
    profile = profile_of(config, name)
    raw = profile.get("stages") if profile else None
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, dict))


# 활성 = triggers 와 stages 가 둘 다 비어 있지 않다. 한쪽만 있으면 그 profile 은 아무 일도
# 하지 않는데 스키마는 통과한다 — 그래서 WARN 으로 알린다
def check_profiles(report: Report, path: str, config: dict) -> dict[str, bool]:
    active: dict[str, bool] = {}
    for name in PROFILE_NAMES:
        where = f"{path}: quality.profiles.{name}"
        profile = profile_of(config, name)
        triggers = triggers_of(config, name)
        stages = stages_of(config, name)

        if profile is None:
            report.add(
                WARN,
                "D-PROFILE",
                where,
                f"{name} profile 이 없어 해당 자동 검사가 비활성입니다. 스키마는 허용합니다.",
                f"{name} 자동 검사가 필요하면 triggers 와 stages 를 추가한다.",
            )
            active[name] = False
        elif not triggers or not stages:
            missing = "triggers" if not triggers else "stages"
            report.add(
                WARN,
                "D-PROFILE",
                f"{where}.{missing}",
                f"{missing} 가 비어 있어 {name} 자동 검사가 비활성입니다. 스키마는 허용합니다.",
                f"{name} 을 쓰려면 {missing} 를 채운다. 안 쓸 거면 그대로 둔다.",
            )
            active[name] = False
        else:
            report.ok("D-PROFILE", where, f"활성입니다 — 트리거 {', '.join(triggers)}.")
            active[name] = True

        # **비활성이어도 트리거 조합은 본다.** 나중에 stages 를 채우는 순간 조용히 안 도는
        # 설정이 되기 때문이다
        allowed = CONSUMER_TRIGGERS[name]
        for trigger in triggers:
            if trigger in allowed:
                continue
            if trigger not in TRIGGER_ENUM:
                continue  # 스키마 enum 위반은 D-CONFIG 가 이미 말했다
            report.add(
                FAIL,
                "D-TRIGGER",
                f"{where}.triggers",
                f"{name} 에 {trigger} 가 있지만 이 조합을 읽는 소비자가 없습니다 — "
                f"{name} 이 처리하는 트리거는 {', '.join(allowed)} 뿐입니다.",
                f"{trigger} 를 지우거나 {_other_profile(name)} profile 로 옮긴다.",
            )
    return active


def _other_profile(name: str) -> str:
    return "full" if name == "fast" else "fast"


# ───────────────────────── 훅 명령 해석 ─────────────────────────


@dataclass(frozen=True)
class Command:
    script: str | None  # 프로젝트 기준 posix 경로. 외부·미해석이면 None
    note: str | None  # 해석하지 못한 이유


def tokenize(command: str) -> list[str] | None:
    tokens: list[str] = []
    current: list[str] = []
    quote: str | None = None
    # 따옴표를 열었다 닫은 토큰은 **빈 인자 하나**다. 버리면 argv 의 자리가 하나 밀려
    # 다음 인자를 실행 대상으로 읽는다. `current` 가 비었는지만 보면 `""` 의 흔적이 남지
    # 않아서, 따옴표가 있었는지를 따로 기억한다
    quoted = False
    index = 0
    while index < len(command):
        char = command[index]
        if quote is not None:
            if char == quote:
                quote = None
            else:
                current.append(char)
        elif char in "\"'":
            quote = char
            quoted = True
        elif char in _SHELL_OPERATORS:
            return None
        elif char == "$" and command[index : index + 2] == "$(":
            return None
        elif char == "#" and not current and not quoted:
            # 셸 주석. 뒤는 명령이 아니다 — 스크립트 뒤의 주석은 그래서 해롭지 않다.
            # `""#x` 는 단어 안이라 주석이 아니다 — 그래서 `quoted` 도 본다
            break
        elif char.isspace():
            if current or quoted:
                tokens.append("".join(current))
                current = []
                quoted = False
        else:
            current.append(char)
        index += 1
    if quote is not None:
        return None
    if current or quoted:
        tokens.append("".join(current))
    return tokens


# `${CLAUDE_PROJECT_DIR}` 만 치환한다. **다른 변수를 추측해 풀지 않는 것이 요점이다** —
# 틀리게 풀어서 「결선이 있다」고 말하는 쪽이 모른다고 말하는 쪽보다 나쁘다
def substitute(token: str, root: Path) -> str | None:
    value = token.replace("${CLAUDE_PROJECT_DIR}", str(root))
    value = value.replace("$CLAUDE_PROJECT_DIR", str(root))
    if "${" in value or re.search(r"\$[A-Za-z_]", value):
        return None
    return value


def _is_python_name(token: str) -> bool:
    return Path(token).name.lower() in _PYTHON_NAMES


# 실행 옵션을 지나 **Python 이 실제로 스크립트로 여는 자리**를 찾는다. 첫 비옵션 토큰이
# 그 자리이고, 확장자는 따지지 않는다 — Python 은 `.py` 가 아닌 파일도 실행한다.
# 돌려주는 값은 (스크립트, 못 찾은 이유)다
def _script_token(tokens: list[str], launcher: bool) -> tuple[str | None, str | None]:
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("-"):
            # **빈 자리와 자리가 없는 것은 다르다.** 실제 Python 은 빈 인자를 디렉터리로
            # 읽고 `__main__` 을 찾다 실패한다 — 뒤의 훅 경로는 실행되지 않는다(실측)
            if not token:
                return None, "스크립트 자리가 빈 인자라 실행 대상을 확정할 수 없습니다."
            return token, None
        if token == "-":
            return None, "표준 입력에서 읽는 호출이라 실행할 스크립트가 없습니다."
        if token in _PY_NO_SCRIPT_MODES or token[:2] in ("-c", "-m"):
            return None, f"{token} 모드는 인자로 준 스크립트를 실행하지 않습니다."
        if launcher and _PY_LAUNCHER_RE.fullmatch(token):
            index += 1
            continue
        if token in _PY_VALUE_OPTS:
            index += 2
            continue
        if token[:2] in ("-W", "-X") and len(token) > 2:
            index += 1
            continue
        if _PY_FLAG_RE.fullmatch(token):
            index += 1
            continue
        return None, f"모르는 실행 옵션이 있어 호출 대상을 확정할 수 없습니다: {token}"
    return None, "실행할 스크립트 인자가 없습니다."


def parse_command(command: object, root: Path) -> Command:
    if not isinstance(command, str) or not command.strip():
        return Command(None, "command 가 비어 있습니다.")

    tokens = tokenize(command)
    if tokens is None:
        return Command(None, "셸 연산자·따옴표 짝 때문에 정적으로 읽을 수 없습니다.")
    if not tokens:
        return Command(None, "command 에 토큰이 없습니다.")

    resolved: list[str] = []
    for token in tokens:
        value = substitute(token, root)
        if value is None:
            return Command(None, f"해석할 수 없는 변수가 있습니다: {token}")
        resolved.append(value)

    candidate: str | None = None
    if resolved[0].endswith(".py"):
        candidate = resolved[0]
    elif _is_python_name(resolved[0]):
        launcher = Path(resolved[0]).name.lower() in ("py", "py.exe")
        candidate, note = _script_token(resolved[1:], launcher)
        if candidate is None:
            return Command(None, note)
    else:
        return Command(None, f"Python 직접 호출이 아닙니다: {resolved[0]}")

    path = Path(candidate)
    if not path.is_absolute():
        path = root / path
    try:
        relative = path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return Command(None, f"프로젝트 밖을 가리킵니다: {candidate}")
    return Command(relative.as_posix(), None)


# ───────────────────────── matcher ─────────────────────────


COMMON = "common"
JS_ERROR = "js-error"
UNKNOWN = "unknown"
# 내부 전용. 「여기까지는 확인 불가지만 **나머지를 계속 봐야 한다**」는 뜻이다 —
# `(?i:Write` 처럼 확정 오류가 뒤에 있으면 그것이 이기게 하려고 둔다
MODIFIER = "modifier"

_QUANT_BRACE_RE = re.compile(r"^\{\d+(,\d*)?\}")
_LOOSE_BRACE_RE = re.compile(r"^\{[\d,]*\}")


def _hex_run(pattern: str, start: int, count: int) -> bool:
    chunk = pattern[start : start + count]
    return len(chunk) == count and all(char in "0123456789abcdefABCDEF" for char in chunk)


# 이스케이프 하나를 분류한다. 돌려주는 값은 (판정, 이유, 다음 위치)다
def _classify_escape(pattern: str, index: int) -> tuple[str, str, int]:
    if index + 1 >= len(pattern):
        return JS_ERROR, "`\\` 로 끝나 이스케이프가 비어 있습니다", index
    char = pattern[index + 1]
    if char == "x":
        if _hex_run(pattern, index + 2, 2):
            return COMMON, "", index + 4
        return UNKNOWN, "`\\x` 뒤가 두 자리 16진수가 아닙니다", index
    if char == "u":
        if _hex_run(pattern, index + 2, 4):
            return COMMON, "", index + 6
        return UNKNOWN, "`\\u{…}` 는 JavaScript 의 u 플래그가 필요합니다", index
    if char in _COMMON_ESCAPES:
        return COMMON, "", index + 2
    # `\A` 가 대표적이다 — V8 은 리터럴 `A` 로 읽어 `Write` 에 걸리지 않고 Python 은 시작
    # 앵커로 읽어 걸린다(실측). 컴파일은 양쪽 다 되므로 컴파일 성공은 근거가 못 된다
    return UNKNOWN, f"이스케이프 `\\{char}` 의 뜻이 같다고 확인하지 못했습니다", index


# 문자클래스 하나를 분류한다. `[]` 는 JavaScript 에서 「아무것도 안 걸리는 빈 클래스」지만
# Python 에서는 `]` 를 담은 클래스다 — 뜻이 갈리므로 확인 불가다
def _classify_class(pattern: str, index: int) -> tuple[str, str, int]:
    cursor = index + 1
    if pattern[cursor : cursor + 1] == "^":
        cursor += 1
    if pattern[cursor : cursor + 1] == "]":
        return UNKNOWN, "`]` 가 클래스의 첫 글자라 두 엔진의 뜻이 갈립니다", index
    while cursor < len(pattern):
        char = pattern[cursor]
        if char == "\\":
            kind, reason, cursor = _classify_escape(pattern, cursor)
            if kind != COMMON:
                return kind, reason, index
            continue
        if char == "]":
            return COMMON, "", cursor + 1
        if pattern[cursor : cursor + 2] == "[:":
            return UNKNOWN, "POSIX 문자클래스처럼 보입니다", index
        cursor += 1
    return JS_ERROR, "문자클래스 `[` 가 닫히지 않았습니다", index


# 범위가 있는 modifier 그룹을 분류한다. **뜻이 갈려서가 아니라 엔진 나이 때문에 UNKNOWN
# 이다** — modifier 그룹은 2025 에 들어온 문법이고(MDN Baseline 2025), 그 전 엔진은 `(?i:`
# 를 `(?i)` 와 똑같이 거부한다. 제품이 어느 엔진을 쓰는지 보지 않았으므로 같은 matcher 가
# 「네 도구를 다 덮는다」일 수도 「아무것도 안 걸린다」일 수도 있다. 뜻 자체는 Python 과
# 같다 — 그래서 FAIL 도 PASS 도 아니다
def _classify_modifier(scoped: re.Match[str], index: int) -> tuple[str, str, int]:
    on, off = scoped.group(1) or "", scoped.group(2) or ""
    letters = on + off
    outside = sorted(set(letters) - _JS_MODIFIER_FLAGS)
    if outside:
        return (
            JS_ERROR,
            f"modifier 그룹은 i·m·s 만 받습니다 — `{''.join(outside)}` 는 Invalid group 입니다",
            index,
        )
    if not letters:
        return JS_ERROR, "플래그가 없는 modifier 그룹은 Invalid flag group 입니다", index
    if len(set(letters)) != len(letters):
        return JS_ERROR, "modifier 그룹에서 같은 플래그를 두 번 쓸 수 없습니다", index
    return (
        MODIFIER,
        "범위가 있는 modifier 그룹은 2025 이후 엔진만 받습니다 — 제품의 엔진을 보지 못했습니다",
        index + scoped.end(),
    )


# 그룹 시작을 분류한다
def _classify_group(pattern: str, index: int) -> tuple[str, str, int]:
    rest = pattern[index:]
    if not rest.startswith("(?"):
        return COMMON, "", index + 1
    for token in _JS_INVALID_GROUPS:
        if rest.startswith(token):
            return JS_ERROR, f"`{token}` 는 JavaScript 에 없는 그룹 문법입니다", index
    # `(?:` `(?=` `(?!` 를 먼저 받는다. 아래 modifier 규칙이 `(?:` 까지 집어가지 않게
    for token in _COMMON_GROUP_OPENS:
        if rest.startswith(token):
            return COMMON, "", index + len(token)
    if _GLOBAL_FLAG_RE.match(rest):
        return JS_ERROR, "전역 인라인 플래그는 JavaScript 에 없습니다", index
    scoped = _SCOPED_FLAG_RE.match(rest)
    if scoped:
        return _classify_modifier(scoped, index)
    if rest.startswith("(?<"):
        return UNKNOWN, "`(?<` 는 룩비하인드와 JS 의 이름 있는 그룹이 겹칩니다", index
    return UNKNOWN, f"그룹 문법 `{rest[:4]}` 를 확인하지 못했습니다", index


# **뜻이 같다고 확인한 문법만 "common" 이다.** Python 이 컴파일했다는 사실은 근거가 못
# 된다 — 그 판단으로 `(?i)…` 와 possessive 수량자가 PASS 로 흘렀다(R2-02).
#
# `prev` 가 상태다. 수량자를 붙일 수 있는 것이 바로 앞에 있었는지를 기억해야 possessive
# (`a++`)와 「반복할 것이 없음」(`*a`)을 가린다. 둘 다 V8 이 거부한다(실측)
def classify_pattern(pattern: str) -> tuple[str, str]:
    index = 0
    depth = 0
    prev = "none"  # none·open·alt·anchor·atom·quant·lazy
    pending: tuple[str, str] | None = None  # 확인 불가지만 계속 봐야 하는 것(modifier 그룹)
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            kind, reason, index = _classify_escape(pattern, index)
            if kind != COMMON:
                return kind, reason
            prev = "atom"
            continue
        if char == "[":
            kind, reason, index = _classify_class(pattern, index)
            if kind != COMMON:
                return kind, reason
            prev = "atom"
            continue
        if char == "(":
            kind, reason, index = _classify_group(pattern, index)
            if kind == MODIFIER:
                pending = (UNKNOWN, reason)
            elif kind != COMMON:
                return kind, reason
            depth += 1
            prev = "open"
            continue
        if char == ")":
            depth -= 1
            if depth < 0:
                return JS_ERROR, "`)` 의 짝이 없습니다"
            index += 1
            prev = "atom"
            continue
        if char == "|":
            index += 1
            prev = "alt"
            continue
        if char in "^$":
            index += 1
            prev = "anchor"
            continue
        brace = _QUANT_BRACE_RE.match(pattern[index:]) if char == "{" else None
        if char == "{" and brace is None and _LOOSE_BRACE_RE.match(pattern[index:]):
            # Python 은 `{,3}` 을 `{0,3}` 으로 읽고 JavaScript 는 리터럴로 읽는다
            return UNKNOWN, f"`{_LOOSE_BRACE_RE.match(pattern[index:]).group(0)}` 의 뜻이 갈립니다"
        if char in "*+" or brace is not None:
            if prev in ("quant", "lazy"):
                return JS_ERROR, f"수량자 뒤의 `{char}` 는 possessive 수량자입니다"
            if prev != "atom":
                return JS_ERROR, f"`{char}` 앞에 반복할 것이 없습니다"
            prev = "quant"
            index += len(brace.group(0)) if brace is not None else 1
            continue
        if char == "?":
            if prev == "atom":
                prev = "quant"
            elif prev == "quant":
                prev = "lazy"
            elif prev == "lazy":
                return JS_ERROR, "`?` 가 수량자 뒤에 두 번 붙었습니다"
            else:
                return JS_ERROR, "`?` 앞에 반복할 것이 없습니다"
            index += 1
            continue
        index += 1
        prev = "atom"
    if depth:
        return JS_ERROR, "`(` 의 짝이 없습니다"
    # 확정 오류가 먼저 돌아간다. 끝까지 오면 modifier 그룹의 확인 불가가 남는다
    return pending or (COMMON, "")


# 공식 Hooks reference(2026-11-22 확인)가 정한 것은 셋이다 — 누락·빈 값·`*` 는 전체 적용,
# 이름 목록은 정확 비교, 정규식은 JavaScript 의 **부분 일치**다. 기존
# `test_hook_wiring.py:158` 의 Python fullmatch 는 그 저장소 테스트의 규약이고 제품의
# 의미가 아니라서 복제하지 않는다.
#
# **전체 적용 특례에 strip 을 쓰지 않는다.** `" * "` 를 전체 적용으로 바꾸는 것은 제품이
# matcher 를 strip 한다는 쪽에 걸고 PASS 를 내는 것이다. 문서가 정한 것은 `*` 이고, V8 은
# `" * "` 를 「공백 0개 이상」으로 읽어 어느 도구에도 걸리지 않는다(실측).
#
# 돌려주는 값이 셋인 이유: True/False 와 **「모르겠다」(None)** 를 갈라야 미확인 matcher 로
# PASS 하는 일이 없다
def matcher_covers(matcher: object, tool: str) -> tuple[bool | None, str]:
    if matcher is None:
        return True, "matcher 없음 — 전체 적용"
    if not isinstance(matcher, str):
        return None, f"matcher 가 문자열이 아닙니다({_type_name(matcher)})"
    if matcher in ("", "*"):
        return True, f"matcher {matcher!r} — 전체 적용"

    if _NAME_LIST_RE.fullmatch(matcher):
        names = [part.strip() for part in re.split(r"[|,]", matcher)]
        names = [name for name in names if name]
        if not names:
            return None, f"matcher {matcher!r} 가 공백뿐이라 이름 목록도 정규식도 아닙니다"
        return tool in names, f"이름 목록 {', '.join(names)}"

    kind, reason = classify_pattern(matcher)
    if kind == JS_ERROR:
        return False, f"정규식 {matcher!r} 는 JavaScript 정규식이 아닙니다 — {reason}"
    if kind == UNKNOWN:
        return None, f"정규식 {matcher!r} 가 JS 와 뜻이 같은지 확인하지 못했습니다 — {reason}"
    try:
        pattern = re.compile(matcher)
    except re.error as exc:
        return None, f"공통 문법으로 봤지만 Python 이 컴파일하지 못했습니다({exc})"
    return bool(pattern.search(tool)), f"정규식 {matcher!r} 부분 일치"


# JS 가 거부한다고 확정한 matcher 의 이유. 그 항목은 어느 도구에도 걸릴 수 없다
def matcher_js_error(matcher: object) -> str | None:
    if not isinstance(matcher, str) or matcher in ("", "*") or _NAME_LIST_RE.fullmatch(matcher):
        return None
    kind, reason = classify_pattern(matcher)
    return reason if kind == JS_ERROR else None


# ───────────────────────── settings 구조와 결선 ─────────────────────────


@dataclass(frozen=True)
class WiredHook:
    event: str
    group_index: int
    hook_index: int
    matcher: object
    command: Command
    kind: object

    @property
    def where(self) -> str:
        return f"{SETTINGS_JSON}: hooks.{self.event}[{self.group_index}].hooks[{self.hook_index}]"


def collect_hooks(report: Report, settings: Loaded, root: Path) -> list[WiredHook] | None:
    if not settings.usable:
        return None
    raw_hooks = (settings.data or {}).get("hooks")
    if raw_hooks is None:
        report.add(
            WARN,
            "D-CONFIG",
            f"{SETTINGS_JSON}: hooks",
            "hooks 절이 없어 연결된 훅이 하나도 없습니다.",
            "템플릿의 hooks 절을 병합한다.",
        )
        return []
    if not isinstance(raw_hooks, dict):
        report.add(
            FAIL,
            "D-CONFIG",
            f"{SETTINGS_JSON}: hooks",
            f"객체여야 합니다({_type_name(raw_hooks)}).",
            "이벤트 이름을 키로 둔 객체로 고친다.",
        )
        return None

    wired: list[WiredHook] = []
    for event, groups in raw_hooks.items():
        where = f"{SETTINGS_JSON}: hooks.{event}"
        if not isinstance(groups, list):
            report.add(
                FAIL,
                "D-CONFIG",
                where,
                f"배열이어야 합니다({_type_name(groups)}).",
                "group 객체의 배열로 고친다.",
            )
            continue
        for group_index, group in enumerate(groups):
            spot = f"{where}[{group_index}]"
            if not isinstance(group, dict):
                report.add(
                    FAIL,
                    "D-CONFIG",
                    spot,
                    f"객체여야 합니다({_type_name(group)}).",
                    "matcher·hooks 를 가진 객체로 고친다.",
                )
                continue
            matcher = group.get("matcher")
            if "matcher" in group and not isinstance(matcher, str):
                report.add(
                    FAIL,
                    "D-CONFIG",
                    f"{spot}.matcher",
                    f"문자열이어야 합니다({_type_name(matcher)}).",
                    "도구 이름 목록이나 정규식 문자열로 고친다.",
                )
            group_hooks = group.get("hooks")
            if not isinstance(group_hooks, list):
                report.add(
                    FAIL,
                    "D-CONFIG",
                    f"{spot}.hooks",
                    f"배열이어야 합니다({_type_name(group_hooks)}).",
                    "훅 객체의 배열로 고친다.",
                )
                continue
            for hook_index, hook in enumerate(group_hooks):
                place = f"{spot}.hooks[{hook_index}]"
                if not isinstance(hook, dict):
                    report.add(
                        FAIL,
                        "D-CONFIG",
                        place,
                        f"객체여야 합니다({_type_name(hook)}).",
                        "type 과 command 를 가진 객체로 고친다.",
                    )
                    continue
                kind = hook.get("type")
                if not isinstance(kind, str) or not kind.strip():
                    report.add(
                        FAIL,
                        "D-CONFIG",
                        f"{place}.type",
                        f"비어 있지 않은 문자열이어야 합니다({_type_name(kind)}).",
                        '보통 "command" 다.',
                    )
                    continue
                if kind != "command":
                    # 기존 프로젝트가 둔 다른 종류를 오류로 만들지 않는다
                    continue
                raw_command = hook.get("command")
                if not isinstance(raw_command, str) or not raw_command.strip():
                    report.add(
                        FAIL,
                        "D-CONFIG",
                        f"{place}.command",
                        f"비어 있지 않은 문자열이어야 합니다({_type_name(raw_command)}).",
                        "실행할 명령을 적는다.",
                    )
                    continue
                wired.append(
                    WiredHook(
                        event,
                        group_index,
                        hook_index,
                        matcher,
                        parse_command(raw_command, root),
                        kind,
                    )
                )
    return wired


def check_hook_scripts(report: Report, root: Path, wired: list[WiredHook]) -> None:
    unresolved = 0
    checked = 0
    for hook in wired:
        if hook.command.script is None:
            unresolved += 1
            report.add(
                WARN,
                "D-HOOK",
                hook.where,
                f"미확인 — {hook.command.note}",
                "외부·래퍼 명령이면 그대로 두어도 된다. 정상 결선의 근거로는 쓰지 않는다.",
            )
            continue
        checked += 1
        if not (root / hook.command.script).is_file():
            report.add(
                FAIL,
                "D-HOOK",
                hook.where,
                f"연결된 스크립트가 없습니다: {hook.command.script}",
                "경로를 고치거나 해당 훅 설정을 지운다.",
            )
    if checked and not any(
        item.level == FAIL and item.check == "D-HOOK" for item in report.findings
    ):
        report.ok(
            "D-HOOK",
            SETTINGS_JSON,
            f"프로젝트 내부 스크립트 {checked}건이 모두 있습니다"
            + (f" (미확인 {unresolved}건 제외)." if unresolved else "."),
        )


def check_wiring(
    report: Report, root: Path, config: dict, wired: list[WiredHook], active: dict[str, bool]
) -> None:
    for rule in REQUIRED_WIRING:
        where = f"{SETTINGS_JSON}: hooks.{rule.event}"
        label = f"{rule.profile}/{rule.trigger}"
        if not active.get(rule.profile) or rule.trigger not in triggers_of(config, rule.profile):
            report.add(
                WARN,
                "D-WIRING",
                where,
                f"미검사 — {label} 이 비활성이라 필수 결선을 요구하지 않습니다.",
                f"{label} 을 쓰려면 profile 을 채운 뒤 다시 실행한다.",
            )
            continue

        expected = f"{HOOKS_DIR}/{rule.script}"
        candidates = [
            hook for hook in wired if hook.event == rule.event and hook.command.script == expected
        ]
        if not candidates:
            report.add(
                FAIL,
                "D-WIRING",
                where,
                f"{label} 이 활성인데 {rule.event} 에 {expected} 연결이 없습니다. "
                "이 상태로는 해당 게이트가 한 번도 돌지 않습니다.",
                f'{rule.event} 에 `python "${{CLAUDE_PROJECT_DIR}}/{expected}"` 훅을 추가한다.',
            )
            continue

        if not rule.tools:
            report.ok("D-WIRING", where, f"{label} → {expected} 연결이 있습니다.")
            continue

        # **JS 가 거부한다고 확정한 matcher 는 미확인이 아니라 FAIL 이다.** 그 항목은 어느
        # 도구에도 걸릴 수 없으므로 아래 도구별 계산에서도 빼야 한다 — 남겨 두면 「덮지
        # 않는다」가 아니라 「모르겠다」로 보인다
        usable: list[WiredHook] = []
        for hook in candidates:
            note = matcher_js_error(hook.matcher)
            if note is None:
                usable.append(hook)
                continue
            report.add(
                FAIL,
                "D-WIRING",
                hook.where,
                f"matcher {hook.matcher!r} 는 JavaScript 정규식이 아닙니다 — {note}. "
                "이 항목은 어느 도구에도 걸리지 않습니다.",
                "matcher 를 이름 목록이나 두 엔진 공통 정규식 문법으로 고친다.",
            )
        if not usable:
            continue
        candidates = usable

        missing: list[str] = []
        unsure: list[str] = []
        for tool in rule.tools:
            verdicts = [matcher_covers(hook.matcher, tool) for hook in candidates]
            if any(result is True for result, _ in verdicts):
                continue
            if any(result is None for result, _ in verdicts):
                # 후보 훅이 여러 개면 같은 이유가 그만큼 반복된다 — 한 번만 적는다
                reasons = dict.fromkeys(note for result, note in verdicts if result is None)
                unsure.append(f"{tool}({'; '.join(reasons)})")
            else:
                missing.append(tool)

        if missing:
            report.add(
                FAIL,
                "D-WIRING",
                where,
                f"{label} 의 {expected} 연결이 {', '.join(missing)} 를 덮지 않습니다. "
                "그 도구로 고친 변경은 게이트를 그냥 지나갑니다.",
                f"해당 matcher 에 {', '.join(missing)} 를 포함시킨다.",
            )
        if unsure:
            report.add(
                WARN,
                "D-WIRING",
                where,
                f"{label} 의 {', '.join(unsure)} 는 matcher 를 해석하지 못해 확인하지 못했습니다.",
                "matcher 를 이름 목록이나 공통 정규식 문법으로 적으면 확인할 수 있다.",
            )
        if not missing and not unsure:
            report.ok(
                "D-WIRING",
                where,
                f"{label} → {expected} 가 {', '.join(rule.tools)} 를 모두 덮습니다.",
            )


# ───────────────────────── stage 정적 점검 ─────────────────────────


def check_stages(report: Report, root: Path, path: str, config: dict) -> None:
    exec_items = 0
    for name in PROFILE_NAMES:
        for index, stage in enumerate(stages_of(config, name)):
            where = f"{path}: quality.profiles.{name}.stages[{index}]"
            _check_stage_cwd(report, root, where, stage)
            exec_items += _check_stage_argv(report, root, where, name, stage)
    if not exec_items:
        report.add(
            WARN,
            "D-EXEC",
            path,
            "미검사 — 실행 파일 자리가 모두 치환값이라 정적으로 확인할 대상이 없었습니다.",
            "`{python}` 은 D-PYTHON 이 따로 본다.",
        )


def _check_stage_cwd(report: Report, root: Path, where: str, stage: dict) -> None:
    raw = stage.get("cwd")
    if raw is None:
        report.ok("D-STAGE", f"{where}.cwd", "기본값(프로젝트 루트)을 씁니다.")
        return
    if not isinstance(raw, str) or not raw.strip():
        return  # D-CONFIG 가 이미 말했다
    # `_quality._stage_cwd()` 와 같은 순서로 본다 — resolve 뒤 루트 안인지, 그리고 실제
    # 디렉터리인지. 둘 중 하나라도 어긋나면 실행기가 QualityConfigError 로 막는다
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        report.add(
            FAIL,
            "D-STAGE",
            f"{where}.cwd",
            f"프로젝트 밖을 가리킵니다: {raw}. _stage_cwd() 가 막습니다.",
            "프로젝트 안의 상대 경로로 고친다.",
        )
        return
    if not candidate.is_dir():
        report.add(
            FAIL,
            "D-STAGE",
            f"{where}.cwd",
            f"존재하는 디렉터리가 아닙니다: {raw}. _stage_cwd() 가 막습니다.",
            "디렉터리를 만들거나 cwd 를 고친다.",
        )
        return
    report.ok("D-STAGE", f"{where}.cwd", f"{raw} 는 프로젝트 안의 디렉터리입니다.")


def _check_stage_argv(report: Report, root: Path, where: str, profile: str, stage: dict) -> int:
    argv = stage.get("argv")
    if not isinstance(argv, list) or not argv:
        return 0
    if not all(isinstance(item, str) for item in argv):
        return 0

    if not argv[0].strip():
        report.add(
            FAIL,
            "D-ARGV",
            f"{where}.argv[0]",
            "실행 파일이 비어 있습니다. load_profile() 이 막습니다.",
            "실행할 명령이나 `{python}` 을 적는다.",
        )
        return 0

    for position, arg in enumerate(argv):
        spot = f"{where}.argv[{position}]"
        # **실행기와 같은 조건을 그대로 쓴다**(`_quality.py:131`). 여기서 더 좁게 보면
        # 실행기가 거부하는 설정을 Doctor 가 통과시킨다
        if arg.startswith("{") and arg.endswith("}") and arg not in KNOWN_PLACEHOLDERS:
            report.add(
                FAIL,
                "D-ARGV",
                spot,
                f"알 수 없는 치환값입니다({arg}). load_profile() 이 "
                "QualityConfigError 로 막습니다.",
                f"아는 치환값은 {', '.join(KNOWN_PLACEHOLDERS)} 뿐이다.",
            )
            continue
        if arg in KNOWN_PLACEHOLDERS:
            if arg in LIST_PLACEHOLDERS and position == 0:
                report.add(
                    FAIL,
                    "D-ARGV",
                    spot,
                    f"목록 치환값을 실행 파일 자리에 두었습니다({arg}).",
                    "argv[0] 에는 실행할 명령이나 `{python}` 을 둔다.",
                )
            if arg in LIST_PLACEHOLDERS and profile == "full":
                report.add(
                    FAIL,
                    "D-ARGV",
                    spot,
                    f"full stage 가 {arg} 를 씁니다. 두 full 트리거는 빈 목록을 "
                    "넘기므로(pre_commit_check.py:169, auto_test_check.py:324) "
                    "이 stage 는 항상 건너뛰면서 성공으로 보고됩니다.",
                    f"{arg} 를 지우거나 이 stage 를 fast 로 옮긴다.",
                )
            continue
        if any(token in arg for token in KNOWN_PLACEHOLDERS):
            report.add(
                WARN,
                "D-ARGV",
                spot,
                f"알려진 치환값이 문자열 안에 있습니다({arg}). 실행기는 항목 전체가 "
                "치환값일 때만 확장하므로 이 값은 글자 그대로 전달됩니다.",
                "치환값을 별도 argv 항목으로 분리한다.",
            )

    return _check_executable(report, root, where, stage, argv[0])


def _check_executable(report: Report, root: Path, where: str, stage: dict, raw: str) -> int:
    if raw in KNOWN_PLACEHOLDERS:
        return 0

    spot = f"{where}.argv[0]"
    path = Path(raw)
    if path.is_absolute():
        if not path.is_file():
            report.add(
                FAIL,
                "D-EXEC",
                spot,
                f"실행 파일이 없습니다: {raw}",
                "경로를 고치거나 `{python}` 같은 치환값을 쓴다.",
            )
            return 1
        # POSIX 에서만 의미가 있다. Windows 는 실행 권한 비트가 없어 확인할 것이 없다
        if sys.platform != "win32" and not os.access(path, os.X_OK):
            report.add(
                FAIL,
                "D-EXEC",
                spot,
                f"실행 권한이 없습니다: {raw}",
                "chmod +x 로 실행 권한을 준다.",
            )
            return 1
        report.ok("D-EXEC", spot, f"{raw} 가 있습니다. 실행해 보지는 않았습니다.")
        return 1

    if "/" in raw or "\\" in raw:
        base = stage.get("cwd")
        anchor = root / base if isinstance(base, str) and base.strip() else root
        report.add(
            WARN,
            "D-EXEC",
            spot,
            f"상대 실행 경로입니다({raw}). stage.cwd 기준 후보는 "
            f"{(anchor / raw)} 이며 존재는 "
            f"{'확인됨' if (anchor / raw).is_file() else '확인되지 않음'} 입니다.",
            "절대 경로나 PATH 의 명령 이름으로 적으면 확정할 수 있다.",
        )
        return 1

    found = shutil.which(raw)
    if found is None:
        report.add(
            WARN,
            "D-EXEC",
            spot,
            f"Doctor 프로세스의 PATH 에서 {raw} 를 찾지 못했습니다. 실제 훅 프로세스의 "
            "PATH 는 다를 수 있어 미확정입니다.",
            "해당 도구를 설치하거나 절대 경로로 적는다.",
        )
        return 1
    report.ok("D-EXEC", spot, f"{raw} → {found} (Doctor 프로세스의 PATH 에서만 확인).")
    return 1


# ───────────────────────── 인터프리터 ─────────────────────────


# `_hookutil.venv_python()` 의 순서와 분기를 그대로 옮긴 것이다. 다른 점은 루트 하나 —
# 저쪽은 환경변수·cwd 로 찾고 이쪽은 Doctor 의 대상 루트를 쓴다.
#
# 따로 뺀 이유는 **대조할 수 있게 하려고**다. 복제한 분기는 조용히 어긋나는 종류라
# `tests/test_doctor.py` 가 실제 훅 모듈의 결과와 맞춰 본다.
# 돌려주는 값은 (고른 경로, 출처, 시도한 순서)이고 출처는 `"python"` 또는 `.venv` 상대 경로다
def chosen_python(root: Path, config: dict) -> tuple[str | None, str | None, list[str]]:
    tried: list[str] = []
    configured = config.get("python")
    if isinstance(configured, str) and configured.strip():
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = root / candidate
        tried.append(str(candidate))
        if candidate.is_file():
            return str(candidate), "python", tried
    for relative in (".venv/Scripts/python.exe", ".venv/bin/python"):
        candidate = root / relative
        tried.append(str(candidate))
        if candidate.is_file():
            return str(candidate), relative, tried
    return None, None, tried


def check_python(report: Report, root: Path, path: str, config: dict) -> None:
    uses = any(
        "{python}" in (stage.get("argv") or [])
        for name in PROFILE_NAMES
        for stage in stages_of(config, name)
        if isinstance(stage.get("argv"), list)
    )
    if not uses:
        report.add(
            WARN,
            "D-PYTHON",
            f"{path}: python",
            "미검사 — `{python}` 을 쓰는 stage 가 없어 확인할 대상이 없습니다.",
            "다른 언어 프로젝트라면 그대로 두어도 된다.",
        )
        return

    where = f"{path}: python"
    configured = config.get("python")
    chosen, source, tried = chosen_python(root, config)

    if chosen is not None and source == "python":
        report.ok("D-PYTHON", where, f"설정한 {configured} 를 씁니다 (Doctor 의 루트 기준 선택).")
        return

    if chosen is not None:
        report.add(
            WARN,
            "D-PYTHON",
            where,
            f"설정한 {configured!r} 가 없어 {source} 로 대체됩니다 "
            "(Doctor 의 루트 기준 선택). 검사가 통과해도 지정한 환경에서 "
            "돌았다고 볼 수 없습니다.",
            f"환경을 {configured} 에 만들거나 python 값을 {source} 로 고친다.",
        )
        return

    report.add(
        WARN,
        "D-PYTHON",
        where,
        f"설정한 {configured!r} 와 `.venv` 둘 다 없어 현재 프로세스 "
        f"({sys.executable}) 가 쓰입니다 (Doctor 의 루트 기준 선택). "
        f"시도 순서: {' → '.join(tried)}.",
        "가상환경을 만들거나 python 값을 실제 인터프리터로 고친다.",
    )


# ───────────────────────── 추적 경로 ─────────────────────────


@dataclass(frozen=True)
class TrackedField:
    key: str
    where: str
    impact: str  # 이 항목이 실제로 쓰일 때 꺼지는 것
    backs: str = ""  # 대체로 받치는 필드. 비어 있으면 1차 필드다


def _tracked_fields(path: str) -> tuple[TrackedField, ...]:
    return (
        TrackedField(
            "quality.tracked_paths",
            f"{path}: quality.tracked_paths",
            "Fast/post_change 와 Full/stop 의 변경 감지",
        ),
        TrackedField(
            "history.tracked_paths",
            f"{path}: history.tracked_paths",
            "V2 History Gate 의 변경 감지",
        ),
        TrackedField(
            "source_prefixes",
            f"{path}: source_prefixes",
            "Fast/Full 과 History Gate 의 변경 감지",
            "quality.tracked_paths 와 history.tracked_paths",
        ),
        TrackedField(
            "harness_paths",
            f"{path}: harness_paths",
            "V2 History Gate 의 변경 감지",
            "history.tracked_paths",
        ),
    )


def _field_entries(config: dict, key: str) -> tuple[str, ...]:
    if "." in key:
        head, tail = key.split(".", 1)
        section = config.get(head)
        return string_list(section, tail) if isinstance(section, dict) else ()
    return string_list(config, key)


# 두 소비자의 선택 규칙이다(`auto_test_check.py:67`, `history_check.py:41`) — 리스트이고
# 공백이 아닌 문자열이 하나라도 있으면 그 값을 쓰고, 아니면 대체로 내려간다
def _selected(config: dict, key: str) -> bool:
    return any(item.strip() for item in _field_entries(config, key))


def _nonblank(config: dict, key: str) -> tuple[str, ...]:
    return tuple(item for item in _field_entries(config, key) if item.strip())


# Fast/Full 이 실제로 보는 추적 항목. `auto_test_check._v2_tracked_paths()` 와 같다
def selected_quality_tracked(config: dict) -> tuple[str, ...]:
    return _nonblank(config, "quality.tracked_paths") or string_list(config, "source_prefixes")


# V2 History Gate 가 실제로 보는 추적 항목. `history_check.tracked_paths()` 와 같다
def selected_history_tracked(config: dict) -> tuple[str, ...]:
    entries = _nonblank(config, "history.tracked_paths")
    if entries:
        return entries
    return (*string_list(config, "source_prefixes"), *string_list(config, "harness_paths"))


# **대체 항목이 실제로 선택되는지 먼저 본다.** 안 그러면 쓰이지도 않는 항목을 「게이트가
# 꺼졌다」며 FAIL 로 막는다(R2-04). V2 에서 이 두 필드의 다른 소비자는 모두 버전 게이트로
# 꺼져 있다 — `task_log_check.py:193` 은 `is_v2()` 면 즉시 반환하고
# `auto_test_check.py:416` 은 V2 핸들러로 보내고 돌아온다
def _tracked_live(config: dict, key: str) -> bool:
    if key == "source_prefixes":
        return not _selected(config, "quality.tracked_paths") or not _selected(
            config, "history.tracked_paths"
        )
    if key == "harness_paths":
        return not _selected(config, "history.tracked_paths")
    return True


# **이 검사가 이 CLI 를 만든 이유에 가장 가깝다.** 끝의 `/` 가 없는 항목은 두 소비자가
# 전부 「정확한 파일 하나」로 읽는다(`auto_test_check.py:88`, `_hookutil.py:499`). 그래서
# `"tests"` 라고 적으면 디렉터리 아래 아무것도 안 걸리고, 게이트는 조용히 통과한다.
# 실측으로 `("tests",)` 는 0건, `("tests/",)` 는 17건이었다
def check_tracked(
    report: Report, root: Path, path: str, config: dict, active: dict[str, bool]
) -> None:
    for item in _tracked_fields(path):
        entries = _field_entries(config, item.key)
        if not entries:
            continue
        live = _tracked_live(config, item.key)
        clean = 0
        for index, raw in enumerate(entries):
            normalized = normalize_entry(raw)
            if not normalized:
                continue
            spot = f"{item.where}[{index}]"
            target = root / normalized
            if normalized.endswith("/"):
                clean += 1
                continue
            if target.is_dir() and live:
                report.add(
                    FAIL,
                    "D-TRACKED",
                    spot,
                    f"{raw!r} 는 기존 디렉터리인데 끝에 `/` 가 없습니다. 소비자는 끝에 "
                    "`/` 가 없는 항목을 정확한 파일 하나로 읽습니다"
                    "(`_hookutil.tracked_paths_newer_than`). 이 항목으로는 아무 변경도 "
                    f"잡히지 않아 {item.impact}가 조용히 꺼집니다.",
                    f"{normalized}/ 처럼 끝에 `/` 를 붙인다.",
                )
                continue
            if target.is_dir():
                report.add(
                    WARN,
                    "D-TRACKED",
                    spot,
                    f"{raw!r} 는 기존 디렉터리인데 끝에 `/` 가 없습니다. 지금은 "
                    f"{item.backs} 가 있어서 이 항목을 읽는 소비자가 없습니다 — 고장은 "
                    f"아닙니다. {item.backs} 를 비우면 이 항목이 대체로 쓰이고, 그때는 "
                    f"{item.impact}가 꺼집니다.",
                    f"대체로 쓰일 때를 대비하려면 {normalized}/ 처럼 끝에 `/` 를 붙인다.",
                )
                continue
            if target.is_file():
                clean += 1
                continue
            report.add(
                WARN,
                "D-SCAFFOLD",
                spot,
                f"{raw!r} 가 아직 없습니다. 디렉터리로 쓸 거면 끝에 `/` 가 필요합니다.",
                "경로를 만들거나 설정에서 지운다.",
            )
        if clean:
            report.ok("D-TRACKED", item.where, f"항목 {clean}건의 디렉터리·파일 구분이 맞습니다.")

    # 추적할 것이 아예 없으면 변경 자체가 안 잡힌다. `auto_test_check.py:67` 의 대체까지
    # 적용한 뒤에 본다
    effective = selected_quality_tracked(config)
    needs = active.get("fast") and "post_change" in triggers_of(config, "fast")
    needs = needs or (active.get("full") and "stop" in triggers_of(config, "full"))
    if needs and not effective:
        report.add(
            WARN,
            "D-TRACKED",
            f"{path}: quality.tracked_paths",
            "quality.tracked_paths → source_prefixes 대체까지 적용해도 추적 항목이 "
            "없습니다. 활성 트리거가 변경을 감지할 대상이 없습니다.",
            "quality.tracked_paths 에 감시할 경로를 추가한다.",
        )


# ───────────────────────── 매핑 ─────────────────────────


def _unmapped_keys(config: dict) -> tuple[str, ...]:
    quality = config.get("quality")
    raw = quality.get("unmapped_by_design") if isinstance(quality, dict) else None
    if isinstance(raw, (dict, list)):
        return tuple(key for key in raw if isinstance(key, str))
    return ()


def _mapping_rows(config: dict) -> tuple[tuple[str, str], ...]:
    quality = config.get("quality")
    raw = quality.get("mappings") if isinstance(quality, dict) else None
    if not isinstance(raw, list):
        return ()
    rows: list[tuple[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        source, target = item.get("path"), item.get("tests")
        if isinstance(source, str) and isinstance(target, str):
            rows.append((source, target))
    return tuple(rows)


# `auto_test_check.test_target_for()` 를 **확정 가능한 입력에만** 옮긴 것이다. 디렉터리
# 항목은 아래 파일을 전수 탐색하지 않으므로 커버리지를 증명하지 않는다
def _target_for(
    rel: str, rows: tuple[tuple[str, str], ...], unmapped: tuple[str, ...]
) -> str | None:
    if any(rel == item or rel.startswith(item) for item in unmapped):
        return rel  # 의도적 제외는 경고 대상이 아니다
    if rel.startswith("tests/"):
        name = rel.rsplit("/", 1)[-1]
        if not name.endswith(".py"):
            return None
        return rel if name.startswith("test_") else None
    best: tuple[str, str] | None = None
    for prefix, target in rows:
        if (rel == prefix or rel.startswith(prefix)) and (
            best is None or len(prefix) > len(best[0])
        ):
            best = (prefix, target)
    return best[1] if best else None


def check_mapping(
    report: Report, root: Path, path: str, config: dict, active: dict[str, bool]
) -> None:
    if not active.get("fast") or "post_change" not in triggers_of(config, "fast"):
        return
    uses = any(
        "{mapped_targets}" in (stage.get("argv") or [])
        for stage in stages_of(config, "fast")
        if isinstance(stage.get("argv"), list)
    )
    if not uses:
        return

    rows = _mapping_rows(config)
    unmapped = _unmapped_keys(config)
    where = f"{path}: quality.tracked_paths"
    orphans: list[str] = []
    for raw in _field_entries(config, "quality.tracked_paths") or string_list(
        config, "source_prefixes"
    ):
        normalized = normalize_entry(raw)
        if not normalized or normalized.endswith("/"):
            continue
        if not (root / normalized).is_file():
            continue
        if _target_for(normalized, rows, unmapped) is None:
            orphans.append(normalized)

    if orphans:
        report.add(
            WARN,
            "D-MAPPING",
            where,
            f"추적 파일 {', '.join(orphans)} 에 대응하는 테스트 대상이 없습니다. "
            "Fast stage 가 `{mapped_targets}` 를 쓰므로 이 파일만 고친 변경에서는 "
            "stage 가 건너뛰어지고 성공으로 보고됩니다.",
            "quality.mappings 에 대상을 추가하거나, 의도한 것이면 "
            "quality.unmapped_by_design 에 이유와 함께 적는다.",
        )
    else:
        report.ok("D-MAPPING", where, "확정 가능한 추적 파일에 대응 대상이 있습니다.")


# ───────────────────────── scaffold ─────────────────────────


def check_scaffold(
    report: Report, root: Path, path: str, config: dict, wiki_root: str | None
) -> None:
    missing: list[str] = []
    for source, target in _mapping_rows(config):
        for value in (source, target):
            normalized = normalize_entry(value)
            if normalized and not (root / normalized).exists():
                missing.append(f"quality.mappings → {value}")

    if wiki_root is not None:
        for kind in ("plan", "task", "verify"):
            prefix = history_prefix_of(config, kind, wiki_root)
            if not (root / prefix).is_dir():
                missing.append(f"history.{kind} → {prefix}")

    if missing:
        report.add(
            WARN,
            "D-SCAFFOLD",
            path,
            "설정이 참조하는 경로가 아직 없습니다: " + ", ".join(missing),
            "새 프로젝트라면 만들거나, 설정을 이 프로젝트의 경로로 고친다. "
            "History 파일 자체는 필요하지 않다.",
        )
    else:
        report.ok("D-SCAFFOLD", path, "설정이 참조하는 경로가 모두 있습니다.")


# ───────────────────────── 진단 ─────────────────────────


# 루트는 스키마가 `additionalProperties: true` 라 추가 키를 거부하지 않는다. 그래서 루트에는
# `_check_keys` 를 쓰지 않고 required 만 본다. `schema_version` 은 D-VERSION 소유라 빼고,
# 그러지 않으면 V1 프로젝트가 같은 사실로 WARN 과 FAIL 을 동시에 받는다
def _root_required_only(report: Report, config: dict) -> None:
    for key in ROOT_REQUIRED:
        if key == "schema_version":
            continue
        if key not in config:
            report.add(
                FAIL,
                "D-CONFIG",
                f"{HARNESS_JSON}: {key}",
                "필수 루트 필드가 없습니다.",
                f"{key} 를 추가한다.",
            )


def diagnose(root: Path) -> Report:
    report = Report()
    harness = load_json(root, HARNESS_JSON)
    settings = load_json(root, SETTINGS_JSON)

    check_files(root, report)

    for loaded in (harness, settings):
        if loaded.usable:
            report.ok("D-JSON", loaded.path, "읽고 파싱했습니다.")
        elif (root / loaded.path).exists() or loaded.error != "파일이 없습니다.":
            report.add(
                FAIL,
                "D-JSON",
                loaded.path,
                loaded.error or "읽지 못했습니다.",
                "JSON 문법과 인코딩을 고친다. UTF-8 BOM 은 허용된다.",
            )

    version = check_version(report, harness)
    config = harness.data or {}

    # Wiki 경로를 확정할 수 있는 조건은 둘이다 — 설정을 읽었고, 그리고 버전 2 라면
    # wiki_root 가 스키마대로 있어야 한다. 아니면 어디를 볼지 모르니 미검사다
    wiki_root: str | None = None
    if harness.usable:
        raw_wiki = config.get("wiki_root")
        valid = isinstance(raw_wiki, str) and raw_wiki.strip()
        if version.v2_detail and not valid:
            report.add(
                FAIL,
                "D-CONFIG",
                f"{HARNESS_JSON}: wiki_root",
                f"비어 있지 않은 문자열이어야 합니다({_type_name(raw_wiki)}).",
                '`"wiki_root": ".claude/wiki/"` 처럼 적는다.',
            )
        else:
            wiki_root = wiki_root_of(config)
    check_wiki_files(root, report, harness, wiki_root)

    if not harness.usable:
        for check in (
            "D-CONFIG",
            "D-PROFILE",
            "D-TRIGGER",
            "D-STAGE",
            "D-ARGV",
            "D-EXEC",
            "D-PYTHON",
            "D-TRACKED",
            "D-MAPPING",
            "D-SCAFFOLD",
        ):
            report.unchecked(check, HARNESS_JSON, f"{HARNESS_JSON} 을 읽지 못했습니다")
        active: dict[str, bool] = {}
    elif not version.v2_detail:
        for check in (
            "D-CONFIG",
            "D-STAGE",
            "D-ARGV",
            "D-EXEC",
            "D-PYTHON",
            "D-TRACKED",
            "D-MAPPING",
            "D-SCAFFOLD",
        ):
            report.unchecked(
                check, HARNESS_JSON, "V2(schema_version 2) 가 아니라 V2 구조 검사를 건너뜁니다"
            )
        active = {}
    else:
        _root_required_only(report, config)
        check_history_section(report, HARNESS_JSON, config)
        check_quality_section(report, HARNESS_JSON, config)
        active = check_profiles(report, HARNESS_JSON, config)
        check_stages(report, root, HARNESS_JSON, config)
        check_python(report, root, HARNESS_JSON, config)
        check_tracked(report, root, HARNESS_JSON, config, active)
        check_mapping(report, root, HARNESS_JSON, config, active)
        check_scaffold(report, root, HARNESS_JSON, config, wiki_root)

    wired = collect_hooks(report, settings, root)
    if wired is None:
        for check in ("D-HOOK", "D-WIRING"):
            report.unchecked(check, SETTINGS_JSON, f"{SETTINGS_JSON} 의 훅 구조를 읽지 못했습니다")
    else:
        check_hook_scripts(report, root, wired)
        if harness.usable and version.v2_detail:
            check_wiring(report, root, config, wired, active)
        else:
            report.unchecked(
                "D-WIRING",
                SETTINGS_JSON,
                "V2 Quality Profile 을 확정하지 못해 필수 결선을 판정하지 않습니다",
            )
    return report


# ───────────────────────── 출력 ─────────────────────────


def render(root: Path, report: Report) -> list[str]:
    lines = [
        f"대상 루트: {root}",
        f"검토 범위: 공유 설정 {HARNESS_JSON} · {SETTINGS_JSON} 과 필수 문서만. "
        "사용자·로컬·관리자 설정과 세션의 훅 활성 여부는 보지 않는다.",
        "한계: 명령을 실행하지 않으므로 결선 PASS 는 명령 성공을 뜻하지 않는다. "
        "모듈 설치 상태와 버전은 미검증이다.",
        "",
    ]
    for item in report.findings:
        head = f"[{item.level}] {item.check}  {item.where}"
        lines.append(f"{head} — {item.why}" if item.why else head)
        if item.fix:
            lines.append(f"    고치는 법: {item.fix}")

    counts = {level: 0 for level in (PASS, WARN, FAIL)}
    for item in report.findings:
        counts[item.level] += 1
    lines.extend(
        [
            "",
            f"요약: PASS {counts[PASS]} · WARN {counts[WARN]} · FAIL {counts[FAIL]}",
        ]
    )
    return lines


def _print(lines: list[str]) -> None:
    # Windows 콘솔 기본 인코딩(cp949)으로는 한국어 출력이 UnicodeEncodeError 로 죽는다.
    # `_hookutil.block()` 이 stderr 에 못 박은 것과 같은 이유로 여기서 못 박는다
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    print("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    _ = argv
    try:
        root = resolve_root(Path(__file__))
    except LayoutError as exc:
        _print(
            [
                f"[FAIL] D-RUN  {Path(__file__)} — 진단 미완료: {exc}",
                "    고치는 법: <root>/.claude/harness/scripts/doctor.py 로 복사해 그 경로로 "
                "실행한다.",
                "",
                "요약: 진단을 완료하지 못했습니다.",
            ]
        )
        return 2

    try:
        report = diagnose(root)
        lines = render(root, report)
    except Exception as exc:  # noqa: BLE001 — 내부 오류를 0/1 로 숨기지 않기 위한 마지막 그물
        _print(
            [
                f"[FAIL] D-RUN  {root} — 진단 미완료: 예상하지 못한 내부 오류 "
                f"({type(exc).__name__}: {exc})",
                "    고치는 법: 위 오류를 그대로 보고한다. 발견 사항 0/1 과 구분되는 "
                "종료 코드 2 다.",
                "",
                "요약: 진단을 완료하지 못했습니다.",
            ]
        )
        return 2

    _print(lines)
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
