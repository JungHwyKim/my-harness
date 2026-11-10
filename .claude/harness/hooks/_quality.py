"""프로젝트가 정의한 Quality Profile을 실행하는 공통 엔진.

이 모듈은 언제 검사를 돌릴지 결정하지 않는다. `auto_test_check.py`와
`pre_commit_check.py`가 트리거를 맡고, 이 모듈은 설정된 명령을 순서대로 실행해 결과를
돌려준다. 특정 언어·도구 이름은 여기 두지 않는다.

명령은 셸 문자열이 아니라 argv 배열로만 받는다. `{python}`·`{changed_files}`·
`{mapped_targets}`는 배열의 한 항목 전체일 때만 확장한다. 문자열 중간 치환을 허용하면
quoting과 명령 주입 경계가 다시 셸 수준으로 흐려지기 때문이다.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import _hookutil

DEFAULT_TIMEOUT_SEC = 120
MAX_OUTPUT_CHARS = 12_000
_LIST_PLACEHOLDERS = {"{changed_files}", "{mapped_targets}"}
_KNOWN_PLACEHOLDERS = _LIST_PLACEHOLDERS | {"{python}"}


class QualityConfigError(ValueError):
    """Quality Profile 모양이 잘못됐을 때 발생한다."""


@dataclass(frozen=True)
class Stage:
    stage_id: str
    label: str
    argv: tuple[str, ...]
    timeout: int
    success_codes: tuple[int, ...]
    cwd: Path


@dataclass(frozen=True)
class StageResult:
    stage_id: str
    label: str
    argv: tuple[str, ...]
    ok: bool
    skipped: bool = False
    returncode: int | None = None
    output: str = ""
    timed_out: bool = False
    error: str | None = None


def _quality_config() -> dict | None:
    value = _hookutil.config().get("quality")
    return value if isinstance(value, dict) else None


def profile_config(name: str) -> dict | None:
    quality = _quality_config()
    profiles = quality.get("profiles") if quality else None
    if not isinstance(profiles, dict):
        return None
    profile = profiles.get(name)
    return profile if isinstance(profile, dict) else None


def profile_has_trigger(name: str, trigger: str) -> bool:
    profile = profile_config(name)
    raw = profile.get("triggers") if profile else None
    return isinstance(raw, list) and trigger in raw


def _stage_cwd(raw: object, stage_id: str) -> Path:
    if raw is None:
        return _hookutil.PROJECT_ROOT
    if not isinstance(raw, str) or not raw.strip():
        raise QualityConfigError(f"quality stage {stage_id!r}의 cwd는 비어 있지 않은 문자열이어야 합니다.")
    candidate = (_hookutil.PROJECT_ROOT / raw).resolve()
    try:
        candidate.relative_to(_hookutil.PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise QualityConfigError(
            f"quality stage {stage_id!r}의 cwd가 프로젝트 밖을 가리킵니다: {raw}"
        ) from exc
    if not candidate.is_dir():
        raise QualityConfigError(
            f"quality stage {stage_id!r}의 cwd가 존재하는 디렉터리가 아닙니다: {raw}"
        )
    return candidate


def load_profile(name: str) -> tuple[Stage, ...]:
    profile = profile_config(name)
    if profile is None:
        return ()
    raw_stages = profile.get("stages")
    if not isinstance(raw_stages, list):
        raise QualityConfigError(f"quality profile {name!r}의 stages는 배열이어야 합니다.")

    stages: list[Stage] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_stages):
        if not isinstance(raw, dict):
            raise QualityConfigError(f"quality profile {name!r}의 {index + 1}번째 stage가 객체가 아닙니다.")
        stage_id = raw.get("id")
        if not isinstance(stage_id, str) or not stage_id.strip():
            raise QualityConfigError(f"quality profile {name!r}의 stage id가 비어 있습니다.")
        stage_id = stage_id.strip()
        if stage_id in seen:
            raise QualityConfigError(f"quality profile {name!r}에 stage id {stage_id!r}가 중복됩니다.")
        seen.add(stage_id)

        argv = raw.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
            raise QualityConfigError(f"quality stage {stage_id!r}의 argv는 문자열 배열이어야 합니다.")
        if not argv[0].strip():
            raise QualityConfigError(f"quality stage {stage_id!r}의 실행 파일이 비어 있습니다.")
        for arg in argv:
            if arg.startswith("{") and arg.endswith("}") and arg not in _KNOWN_PLACEHOLDERS:
                raise QualityConfigError(f"quality stage {stage_id!r}에 알 수 없는 치환값이 있습니다: {arg}")

        timeout = raw.get("timeout", DEFAULT_TIMEOUT_SEC)
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 3600:
            raise QualityConfigError(
                f"quality stage {stage_id!r}의 timeout은 1~3600 사이 정수여야 합니다."
            )

        success = raw.get("success_codes", [0])
        if (
            not isinstance(success, list)
            or not success
            or not all(isinstance(code, int) and not isinstance(code, bool) for code in success)
        ):
            raise QualityConfigError(
                f"quality stage {stage_id!r}의 success_codes는 비어 있지 않은 정수 배열이어야 합니다."
            )

        label = raw.get("label", stage_id)
        if not isinstance(label, str) or not label.strip():
            raise QualityConfigError(f"quality stage {stage_id!r}의 label이 올바르지 않습니다.")

        stages.append(
            Stage(
                stage_id=stage_id,
                label=label.strip(),
                argv=tuple(argv),
                timeout=timeout,
                success_codes=tuple(success),
                cwd=_stage_cwd(raw.get("cwd"), stage_id),
            )
        )
    return tuple(stages)


def _expand_argv(
    stage: Stage,
    *,
    changed_files: tuple[str, ...],
    mapped_targets: tuple[str, ...],
) -> tuple[str, ...] | None:
    values = {
        "{changed_files}": changed_files,
        "{mapped_targets}": mapped_targets,
    }
    expanded: list[str] = []
    for arg in stage.argv:
        if arg == "{python}":
            expanded.append(_hookutil.venv_python())
        elif arg in _LIST_PLACEHOLDERS:
            items = values[arg]
            if not items:
                return None
            expanded.extend(items)
        else:
            expanded.append(arg)
    return tuple(expanded)


def _combined_output(proc: subprocess.CompletedProcess[str]) -> str:
    parts = [part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip()]
    output = "\n".join(parts)
    if len(output) > MAX_OUTPUT_CHARS:
        return output[-MAX_OUTPUT_CHARS:] + "\n…(앞부분 생략)"
    return output


def run_stage(
    stage: Stage,
    *,
    changed_files: tuple[str, ...] = (),
    mapped_targets: tuple[str, ...] = (),
) -> StageResult:
    argv = _expand_argv(
        stage,
        changed_files=changed_files,
        mapped_targets=mapped_targets,
    )
    if argv is None:
        return StageResult(stage.stage_id, stage.label, (), ok=True, skipped=True)

    try:
        proc = subprocess.run(
            argv,
            cwd=stage.cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=stage.timeout,
            stdin=subprocess.DEVNULL,
            env=_hookutil.child_env(),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return StageResult(
            stage.stage_id,
            stage.label,
            argv,
            ok=False,
            timed_out=True,
            error=f"{stage.timeout}초 안에 끝나지 않았습니다.",
        )
    except OSError as exc:
        return StageResult(
            stage.stage_id,
            stage.label,
            argv,
            ok=False,
            error=f"명령을 실행하지 못했습니다: {exc}",
        )

    return StageResult(
        stage.stage_id,
        stage.label,
        argv,
        ok=proc.returncode in stage.success_codes,
        returncode=proc.returncode,
        output=_combined_output(proc),
    )


def run_profile(
    name: str,
    *,
    changed_files: tuple[str, ...] = (),
    mapped_targets: tuple[str, ...] = (),
) -> tuple[StageResult, ...]:
    results: list[StageResult] = []
    for stage in load_profile(name):
        result = run_stage(
            stage,
            changed_files=changed_files,
            mapped_targets=mapped_targets,
        )
        results.append(result)
        if not result.ok:
            break
    return tuple(results)


def command_display(argv: tuple[str, ...]) -> str:
    return subprocess.list2cmdline(list(argv))


def failure_message(result: StageResult) -> str:
    lines = [f"stage: {result.label}"]
    if result.argv:
        lines.append(f"command: {command_display(result.argv)}")
    if result.timed_out:
        lines.append("exit status: timeout")
    elif result.returncode is not None:
        lines.append(f"exit status: {result.returncode}")
    if result.error:
        lines.append(result.error)
    if result.output:
        lines.extend(("", result.output))
    return "\n".join(lines)
