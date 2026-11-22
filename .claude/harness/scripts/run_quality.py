"""Quality Profile을 **직접 실행하는** CLI. 훅 없이 같은 검사를 돌리는 진입점이다.

이 명령이 있는 이유는 검사 기준이 갈라지는 것이다. Codex는 Claude Code의 훅을 받지 않고
CI도 받지 않는데, 그 둘이 각자 `pytest -q`·`ruff check .` 을 적어 두면 세 자리의 기준이
조용히 어긋난다. argv·timeout·성공 코드·중단 규칙을 여기서 새로 구현하지 않고
`_quality.run_profile()` 을 부르는 것이 그 때문이다 — 훅이 돌리는 것과 **같은 것**을 돌린다.

**읽기 전용 Doctor와 반대쪽이다.** Doctor는 「결선이 맞다」까지만 말하고 명령을 돌리지
않는다. 이쪽은 설정된 명령을 실제로 실행하므로 pytest·Ruff 캐시가 생긴다. 다만 **이 CLI
자체는** History와 세션 마커를 만들지 않는다 — 훅의 `main()` 이나 이벤트 처리기를 부르지
않고, 세션 개념 자체를 쓰지 않는다. stage로 설정한 임의의 명령이 무엇을 하든 그것까지
막아 주는 샌드박스는 아니다.

**대상 루트는 자기 배치에서 센다.** cwd나 상위 프로젝트의 `CLAUDE_PROJECT_DIR` 로 대상이
바뀌면, 다른 저장소의 테스트를 자기 것이라고 보고하게 된다. 그래서 Doctor와 같은 배치
검증을 쓰고(`doctor.resolve_root`), 그 루트를 **훅 모듈을 import 하기 전에**
`CLAUDE_PROJECT_DIR` 로 박는다. `_hookutil` 의 `PROJECT_ROOT`·`CONFIG_PATH`·`WIKI_ROOT` 는
import 시점에 정해지므로, 나중에 전역값을 갈아끼우는 길은 없다.

**훅의 `SKIP_*` 우회 변수를 보지 않는다.** 저 변수는 「모델이 돌리는 자동 검사를 잠시
끈다」는 뜻이고, 이 명령은 사람이나 CI가 일부러 돌리는 것이다. 환경변수 하나로 CI 게이트가
통째로 무력화되면 그건 검사가 아니다. 반대로 자식 환경에서 그 변수들을 지우지도 않는다 —
stage 명령이 무엇을 읽는지는 그 설정의 몫이다.

종료 코드는 셋이다. 0 = PASS 또는 SKIP, 1 = stage 실패, 2 = 사용 오류·설정 결함.
**SKIP을 0으로 두면서 「통과」라고 쓰지 않는 것이 요점이다** — 돌릴 것이 없었다는 사실과
검사가 통과했다는 사실은 다르고, 그 둘을 같은 말로 보고하면 검사가 꺼진 것을 아무도 모른다.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import doctor

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_ERROR = 2

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"
NOT_RUN = "NOT RUN"

PROFILES = ("fast", "full")

# `_quality._LIST_PLACEHOLDERS` 와 같아야 한다. 저쪽이 늘면 「필요한 단계의 빈 치환값」을
# 여기서 못 보고 지나간다
LIST_PLACEHOLDERS = ("{changed_files}", "{mapped_targets}")


class UsageError(RuntimeError):
    """입력이 계약과 다를 때. 검사를 시작하지 않는다."""


class ConfigError(RuntimeError):
    """설정이 이 CLI의 계약과 다를 때. 검사를 시작하지 않는다."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_quality.py",
        description="이 저장소의 Quality Profile을 직접 실행한다.",
    )
    parser.add_argument("--profile", required=True, choices=PROFILES)
    parser.add_argument(
        "--changed",
        action="append",
        default=[],
        metavar="PATH",
        help="프로젝트 상대 파일 경로. 반복 지정한다. fast에만 쓴다.",
    )
    return parser


# ───────────────────────── 입력 검증 ─────────────────────────


# `--changed` 항목 하나를 저장소 기준 상대 경로로 바꾼다.
#
# **절대 경로를 사용 오류로 두는 것은 `relative_to_root()` 보다 엄격한 선택이다.** 저쪽은
# 훅 입력의 절대 `file_path` 를 받아야 해서 절대 경로를 정규화한다. 이쪽 입력은 사람이나 CI가
# 적는 것이고, 절대 경로를 받아 주면 다른 체크아웃의 경로가 조용히 이 저장소의 상대 경로로
# 바뀌어 **엉뚱한 파일을 분류한다**. 틀린 입력은 멈추는 쪽이 낫다.
#
# **없는 파일은 받는다.** 지운 파일의 변경도 검사 대상이기 때문이다. 반대로 존재하는
# 디렉터리는 거절한다 — `{mapped_targets}` 에 디렉터리를 밀어 넣는 길을 열면 분류 표가
# 뜻을 잃는다
def _relative(root: Path, raw: str) -> str:
    value = raw.strip().replace("\\", "/")
    if not value:
        raise UsageError("--changed 에 빈 경로를 줬습니다.")
    if Path(value).is_absolute() or (len(value) > 1 and value[1] == ":"):
        raise UsageError(f"--changed 는 프로젝트 상대 경로여야 합니다: {raw}")
    while value.startswith("./"):
        value = value[2:]
    if value.startswith("../") or value.endswith("/"):
        raise UsageError(f"--changed 는 루트 안의 파일 경로여야 합니다: {raw}")

    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise UsageError(f"--changed 가 프로젝트 루트 밖을 가리킵니다: {raw}") from exc
    if candidate.is_dir():
        raise UsageError(f"--changed 는 디렉터리가 아니라 파일이어야 합니다: {raw}")
    return value


def _validate_args(root: Path, profile: str, changed: list[str]) -> tuple[str, ...]:
    if profile == "fast" and not changed:
        raise UsageError("fast 는 --changed 가 필요합니다. 무엇이 바뀌었는지가 대상을 정합니다.")
    if profile == "full" and changed:
        raise UsageError("full 은 변경 파일과 무관하게 돌므로 --changed 를 받지 않습니다.")

    seen: list[str] = []
    for raw in changed:
        value = _relative(root, raw)
        if value not in seen:
            seen.append(value)
    return tuple(seen)


# ───────────────────────── 설정 검증 ─────────────────────────


def _load_stages(quality, profile: str):
    try:
        stages = quality.load_profile(profile)
    except quality.QualityConfigError as exc:
        raise ConfigError(f"quality profile {profile!r} 의 모양이 잘못됐습니다.\n{exc}") from exc
    if not stages:
        raise ConfigError(
            f"quality profile {profile!r} 에 실행할 stage 가 없습니다. "
            "설정에 그 Profile 이 없거나 stages 가 비어 있습니다."
        )
    return stages


# 돌리기 **전에** 빈 치환값을 잡는다.
#
# 공통 엔진은 빈 목록 치환값을 만나면 그 stage 를 SKIP 하고 `ok=True` 를 돌려준다. 그 계약
# 자체는 바꾸지 않는다 — 훅이 거기 기대고 있다. 대신 **이 CLI 가 먼저 본다**: 돌릴 것이
# 없다는 사실이 「성공」으로 포장되는 자리가 바로 이 작업이 닫으려는 빈틈이다
def _empty_placeholders(stages, *, changed: tuple[str, ...], targets: tuple[str, ...]) -> list[str]:
    values = {"{changed_files}": changed, "{mapped_targets}": targets}
    offenders: list[str] = []
    for stage in stages:
        for arg in stage.argv:
            if arg in values and not values[arg]:
                offenders.append(f"{stage.stage_id} ({arg})")
    return offenders


# ───────────────────────── 출력 ─────────────────────────


def _print(lines: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines))


# **`[대상]`·`[ERROR]`·`[SKIP]` 이 실제 실행 여부와 맞아야 한다.** 한때 매핑이 필요 없는
# 정상 추적 파일(`CAUSE_NO_MAPPING_NEEDED`)이 `[SKIP]` 으로 찍혔는데, 그 파일은 실제로는
# 실행 대상이었다 — 출력과 동작이 반대였다
def _classification_lines(rows, auto_test_check) -> list[str]:
    lines = ["", "변경 파일 분류:"]
    for row in rows:
        if row.cause == auto_test_check.CAUSE_TARGET:
            lines.append(f"  [대상] {row.path} → {row.target}")
        elif row.cause == auto_test_check.CAUSE_NO_MAPPING_NEEDED:
            lines.append(f"  [대상] {row.path} — {row.reason}")
        elif row.cause in auto_test_check.PROBLEM_CAUSES:
            lines.append(f"  [ERROR] {row.path} — {row.reason}")
        else:
            lines.append(f"  [SKIP] {row.path} — {row.reason}")
    return lines


def _stage_lines(stages, results, quality) -> list[str]:
    lines = ["", "단계:"]
    for index, stage in enumerate(stages):
        if index >= len(results):
            lines.append(f"  [{NOT_RUN}] {stage.stage_id} — {stage.label}")
            lines.append("      앞 단계가 실패해 도달하지 않았습니다.")
            continue
        result = results[index]
        if result.skipped:
            verdict = SKIP
        elif result.ok:
            verdict = PASS
        else:
            verdict = FAIL
        lines.append(f"  [{verdict}] {stage.stage_id} — {stage.label}")
        if result.argv:
            lines.append(f"      명령: {quality.command_display(result.argv)}")
        else:
            lines.append(f"      명령: (치환값이 비어 실행하지 않음) {' '.join(stage.argv)}")
        if result.timed_out:
            lines.append(f"      종료: timeout ({stage.timeout}초)")
        elif result.returncode is not None:
            lines.append(f"      종료 코드: {result.returncode}")
            # 종료 코드 5는 **돌았지만 수집이 0건**이라는 뜻이다. 「테스트가 실패했다」와
            # 전혀 다른 사정이라 그렇게 읽히면 안 된다 — 작성 중인 빈 test_*.py 가 흔한 원인이다
            if result.returncode == 5 and not result.ok:
                lines.append("      수집된 테스트 없음 — 빈 test_*.py 이거나 대상이 비었습니다.")
        if result.error:
            lines.append(f"      {result.error}")
        if result.output:
            lines.append("")
            lines.extend(f"      {line}" for line in result.output.splitlines())
    return lines


# ───────────────────────── 실행 ─────────────────────────


def main(argv: list[str] | None = None) -> int:
    try:
        root = doctor.resolve_root(Path(__file__))
    except doctor.LayoutError as exc:
        _print([f"[ERROR] {exc}"])
        return EXIT_ERROR

    args = _parser().parse_args(argv)

    # **여기 순서가 계약이다.** `_hookutil` 은 import 시점에 루트와 설정 경로를 정한다.
    # 그래서 환경과 import 경로를 먼저 박고 그 다음에 import 한다
    os.environ["CLAUDE_PROJECT_DIR"] = str(root)
    hooks_dir = str(root / ".claude" / "harness" / "hooks")
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)

    import _hookutil
    import _quality
    import auto_test_check

    header = [
        f"대상 루트: {root}",
        f"Profile: {args.profile}",
    ]

    if _hookutil.PROJECT_ROOT != root:
        _print(
            [
                *header,
                "",
                f"[ERROR] 훅 모듈이 다른 루트({_hookutil.PROJECT_ROOT})를 잡았습니다. "
                "배치가 전제와 다릅니다.",
            ]
        )
        return EXIT_ERROR

    if not _hookutil.CONFIG_PATH.is_file():
        _print([*header, "", f"[ERROR] 설정이 없습니다: {_hookutil.CONFIG_PATH}"])
        return EXIT_ERROR
    if not _hookutil.config():
        _print(
            [
                *header,
                "",
                f"[ERROR] 설정을 읽지 못했습니다: {_hookutil.CONFIG_PATH}. "
                "JSON 문법이나 인코딩을 확인하세요.",
            ]
        )
        return EXIT_ERROR
    # **`is_v2()` 를 쓰면 안 되는 자리다.** 저 helper 의 뜻은 `>= 2` 이고, 훅의 **기능 분기**
    # 용도로 맞다 — 앞으로의 버전에서도 V2 경로를 켜 두는 쪽이 안전하기 때문이다. 이 CLI 의
    # 계약은 다르다: 「지원하는 버전은 정확히 2」다. 그 둘을 같은 것으로 쓰면
    # `schema_version: 3` 설정의 명령을 **이해한 것처럼 실행하고 PASS 로 보고한다**(실측).
    # Doctor 도 `>= 3` 을 FAIL 로 본다(`check_version`) — 이쪽을 그 판정에 맞춘다.
    #
    # 정수가 아닌 값까지 여기서 가른다. `schema_version()` 은 그런 값을 1 로 대체하므로
    # 그 값만 보면 「지금 1」이라고 보고하게 되는데, 설정에 적힌 것은 `"2"` 나 `2.0` 이다
    raw_version = _hookutil.config().get("schema_version")
    if not isinstance(raw_version, int) or isinstance(raw_version, bool) or raw_version != 2:
        _print(
            [
                *header,
                "",
                f"[ERROR] 이 CLI 는 schema_version 이 정확히 정수 2인 설정만 지원합니다 "
                f"(지금 {raw_version!r}). V1 과 그 밖의 버전은 훅 런타임이 담당합니다.",
            ]
        )
        return EXIT_ERROR

    interpreter = _hookutil.venv_python()
    header.append(f"인터프리터: {interpreter}")
    # **출력에 적는 것이 계약의 일부다.** docstring 과 테스트만 알고 있으면, 돌린 사람은
    # `SKIP_AUTOTEST=1` 이 켜진 환경에서 이 명령이 무엇을 했는지 알 수 없다
    header.append("훅 우회 변수(SKIP_*)는 이 명령에 적용되지 않습니다.")

    try:
        changed = _validate_args(root, args.profile, list(args.changed))
        stages = _load_stages(_quality, args.profile)
    except (UsageError, ConfigError) as exc:
        _print([*header, "", f"[ERROR] {exc}"])
        return EXIT_ERROR

    lines = list(header)
    targets: tuple[str, ...] = ()

    if args.profile == "fast":
        mapping_required = _quality.profile_uses("fast", "{mapped_targets}")
        rows = [
            auto_test_check.classify(path, mapping_required=mapping_required) for path in changed
        ]
        lines.extend(_classification_lines(rows, auto_test_check))

        problems = [row for row in rows if row.cause in auto_test_check.PROBLEM_CAUSES]
        if problems:
            listed = ", ".join(row.path for row in problems)
            lines.extend(
                [
                    "",
                    f"[ERROR] 추적 파일 {listed} 에 유효한 매핑도 사유 있는 제외도 없습니다. "
                    "quality.mappings 에 대상을 추가하거나 quality.unmapped_by_design 에 "
                    "사유와 함께 등록하세요.",
                ]
            )
            _print(lines)
            return EXIT_ERROR

        # **분류 결과가 실행 입력을 정한다.** 정책상 제외한 파일은 stage 인자에 넣지 않는다 —
        # 넣으면 출력은 SKIP 이라고 적고 명령은 그 파일을 받아 돌아간다. 전부 제외면 SKIP 이다.
        # `auto_test_check._handle_v2_post_tool_use()` 가 같은 집합으로 같은 판단을 한다
        runnable = [row for row in rows if row.cause in auto_test_check.RUNNABLE_CAUSES]
        if not runnable:
            lines.extend(
                [
                    "",
                    "[SKIP] 변경 파일 전부가 의도된 검사 제외입니다. 돌린 검사가 없습니다 — "
                    "검사가 통과했다는 뜻이 아닙니다.",
                ]
            )
            _print(lines)
            return EXIT_OK

        changed = tuple(row.path for row in runnable)
        targets = tuple(sorted({row.target for row in runnable if row.target is not None}))

    offenders = _empty_placeholders(stages, changed=changed, targets=targets)
    if offenders:
        lines.extend(
            [
                "",
                f"[ERROR] 치환값이 비어 실행할 수 없는 단계가 있습니다: {', '.join(offenders)}. "
                "이 Profile 에 그 치환값을 쓰는 stage 가 맞는지 확인하세요.",
            ]
        )
        _print(lines)
        return EXIT_ERROR

    try:
        results = _quality.run_profile(
            args.profile,
            changed_files=changed,
            mapped_targets=targets,
        )
    except _quality.QualityConfigError as exc:
        lines.extend(["", f"[ERROR] quality profile 설정이 잘못됐습니다.\n{exc}"])
        _print(lines)
        return EXIT_ERROR

    lines.extend(_stage_lines(stages, results, _quality))

    failed = [result for result in results if not result.ok]
    ran = [result for result in results if not result.skipped and result.ok]
    skipped = [result for result in results if result.skipped]
    not_run = len(stages) - len(results)

    summary = (
        f"요약: PASS {len(ran)} · FAIL {len(failed)} · SKIP {len(skipped)} · {NOT_RUN} {not_run}"
    )
    lines.extend(["", summary])
    if failed:
        lines.append("판정: FAIL — 위 단계의 원인을 고친 뒤 다시 실행하세요.")
        _print(lines)
        return EXIT_FAIL
    if not ran:
        lines.append("판정: SKIP — 실제로 돌린 단계가 없습니다. 검사 통과가 아닙니다.")
        _print(lines)
        return EXIT_OK
    lines.append("판정: PASS — 위 단계가 실제로 실행되어 성공했습니다.")
    _print(lines)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
