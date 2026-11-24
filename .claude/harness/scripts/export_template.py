"""공통 기본 구성과 선택 pack을 **새 디렉터리**로 내보낸다.

표준 라이브러리만 쓴다. 복사할 파일 목록은 `templates/manifest.json` **하나가** 소유하고
이 CLI 안에 같은 목록을 다시 적지 않는다 — 두 군데 적으면 한쪽만 고쳐져서 조용히 어긋난다.

**기존 프로젝트를 고치지 않는다.** 출력은 항상 새 디렉터리이고 병합·덮어쓰기·`--force` 를
제공하지 않는다. 설치물을 갱신하려면 새 경로로 다시 내보낸 뒤 사람이 비교해 옮긴다.

**명령을 실행하지 않는다.** 네트워크·Git·pip·Doctor·Profile 을 돌리지 않고 파일만 복사한다.
그것이 이 스크립트의 보안·비용 경계다.

종료 코드는 `0`(모두 생성), `1`(읽기·쓰기 실패 — 부분 출력 경로를 알린다),
`2`(인자·manifest 오류, 알 수 없는 pack, 누락 소스, 기존 대상, 경로 탈출·충돌)다.
2 는 **쓰기를 시작하기 전에만** 난다.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_ERROR = 2

MANIFEST_REL = "templates/manifest.json"
MANIFEST_SCHEMA = 1


class ExportError(Exception):
    """쓰기 전에 거부한다. 종료 코드 2."""


class WriteError(Exception):
    """쓰는 중에 실패했다. 종료 코드 1."""


# `doctor.py` 와 같은 전제다 — 소스 루트는 **자기 파일 경로**에서 정하고 cwd 나 환경변수로
# 바꾸지 않는다. 다른 데서 복사해 온 사본이 엉뚱한 루트를 내보내는 것을 막는다
def source_root(script: Path) -> Path:
    parents = script.resolve().parents
    expected = ("scripts", "harness", ".claude")
    actual = tuple(parents[index].name for index in range(3))
    if actual != expected:
        raise ExportError(
            "이 스크립트는 `<루트>/.claude/harness/scripts/export_template.py` 자리에서만 "
            f"돕니다. 지금 상위 세 칸은 {actual} 입니다."
        )
    return parents[2].parent


def load_manifest(root: Path) -> dict:
    path = root / MANIFEST_REL
    if not path.is_file():
        raise ExportError(f"manifest 가 없습니다: {MANIFEST_REL}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExportError(f"manifest 를 읽을 수 없습니다: {MANIFEST_REL}\n{exc}") from exc

    if not isinstance(data, dict):
        raise ExportError("manifest 는 객체여야 합니다.")
    if data.get("schema_version") != MANIFEST_SCHEMA:
        raise ExportError(
            f"manifest schema_version 이 {MANIFEST_SCHEMA} 여야 합니다: "
            f"{data.get('schema_version')!r}"
        )
    if not isinstance(data.get("core"), list):
        raise ExportError("manifest 의 `core` 는 배열이어야 합니다.")
    packs = data.get("packs")
    if not isinstance(packs, dict):
        raise ExportError("manifest 의 `packs` 는 객체여야 합니다.")
    for name, entries in packs.items():
        if not isinstance(entries, list):
            raise ExportError(f"manifest 의 `packs.{name}` 은 배열이어야 합니다.")
    return data


# 상대 경로만 받는다. 절대 경로와 `..` 는 **쓰기 전에** 거부한다
def _safe_rel(raw: object, where: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ExportError(f"{where}: 비어 있지 않은 문자열이어야 합니다 ({raw!r}).")
    candidate = Path(raw)
    # **`is_absolute()` 하나로는 모자란다.** Windows 에서 `Path("/etc/passwd").is_absolute()`
    # 는 드라이브가 없어서 False 인데, `Path("C:/out") / "/etc/passwd"` 는
    # `C:/etc/passwd` 가 되어 출력 디렉터리를 **벗어난다.** 실측으로 이 테스트가 그 구멍을
    # 잡았다. 그래서 anchor(루트 구분자나 드라이브)를 직접 본다.
    #
    # 드라이브 모양(`C:`)은 POSIX 에서 anchor 가 비므로 따로 본다 — 한 OS 에서 만든
    # manifest 가 다른 OS 에서 조용히 통과하면 안 된다
    if candidate.is_absolute() or candidate.anchor or raw.startswith(("/", "\\")):
        raise ExportError(f"{where}: 절대 경로는 쓸 수 없습니다 ({raw!r}).")
    if candidate.parts and candidate.parts[0].endswith(":"):
        raise ExportError(f"{where}: 드라이브 경로는 쓸 수 없습니다 ({raw!r}).")
    if ".." in candidate.parts:
        raise ExportError(f"{where}: `..` 는 쓸 수 없습니다 ({raw!r}).")
    return candidate


def selected_entries(manifest: dict, packs: list[str]) -> list[tuple[Path, Path]]:
    rows: list[tuple[object, object, str]] = []
    for index, entry in enumerate(manifest["core"]):
        rows.append((entry, f"core[{index}]", "core"))
    for name in packs:
        for index, entry in enumerate(manifest["packs"][name]):
            rows.append((entry, f"packs.{name}[{index}]", name))

    pairs: list[tuple[Path, Path]] = []
    for entry, where, _group in rows:
        if not isinstance(entry, dict):
            raise ExportError(f"{where}: 객체여야 합니다 ({entry!r}).")
        source = _safe_rel(entry.get("source"), f"{where}.source")
        destination = _safe_rel(entry.get("destination"), f"{where}.destination")
        pairs.append((source, destination))
    return pairs


# Windows junction 은 symlink 가 아니다 — `is_symlink()` 가 False 를 준다.
# `os.path.isjunction()` 은 3.12 에 들어왔으므로 없으면 조용히 건너뛴다
def _is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is None:
        return False
    try:
        return bool(isjunction(path))
    except OSError:
        return False


def check_sources(root: Path, pairs: list[tuple[Path, Path]]) -> None:
    resolved_root = root.resolve()
    missing: list[str] = []
    for source, _destination in pairs:
        path = root / source
        # **마지막 파일만 보면 모자란다.** `alias/a.txt` 에서 `alias` 가 링크면 마지막
        # 파일은 평범한 파일이고, 그 링크가 루트 안을 가리키면 `resolve()` 결과도 루트
        # 안이라 두 검사를 모두 통과한다. 그래서 루트 아래 **각 구성 요소**를 본다 —
        # 「루트 밖으로 resolve 되는 것을 막는다」와 「링크 자체를 거부한다」는 다른 조건이다
        current = root
        for part in source.parts:
            current = current / part
            if _is_link(current):
                raise ExportError(
                    f"소스 경로에 symlink·junction 이 있습니다: {source.as_posix()}\n"
                    f"  링크 자리: {current.relative_to(root).as_posix()}\n"
                    "내보내기는 링크를 따라가지 않습니다. 실제 파일을 manifest 에 적으세요."
                )
        try:
            inside = path.resolve().is_relative_to(resolved_root)
        except OSError as exc:  # 접근 불가도 쓰기 전 거부다
            raise ExportError(
                f"소스 경로를 확인할 수 없습니다: {source.as_posix()}\n{exc}"
            ) from exc
        if not inside:
            raise ExportError(f"소스가 루트를 벗어납니다: {source.as_posix()}")
        if not path.is_file():
            missing.append(source.as_posix())
    if missing:
        listing = "\n".join(f"  {item}" for item in missing)
        raise ExportError(f"manifest 가 가리키는 소스가 없습니다:\n{listing}")


# **문자열 비교 하나로는 모자랐다.** 세 가지가 전부 「같은 자리」로 끝난다.
#
#   1. 완전히 같은 destination — 뒤에 적힌 쪽이 앞을 덮는다
#   2. 대소문자만 다른 것 — Windows 에서 같은 파일이다. 실측으로 `CLAUDE.md` 와
#      `claude.md` 를 넣으면 종료 0 으로 끝나고 출력에는 **나중 내용 하나만** 남았다
#   3. 한쪽이 다른 쪽의 부모 — `docs` 와 `docs/guide.md` 를 넣으면 `docs` 파일을 만든 뒤
#      mkdir 이 WinError 183 으로 죽어 **부분 출력이 남은 채** 종료 1 이 됐다
#
# 2 번을 두 OS 에서 똑같이 거부한다. Linux 에서는 둘이 다른 파일이지만, 대소문자만 다른
# 출력을 내는 manifest 는 애초에 **옮겨 심을 수 없는** 설정이다 — 거부 계약이 OS 마다
# 갈리면 한쪽에서 통과한 manifest 가 다른 쪽에서 깨진다
def check_collisions(pairs: list[tuple[Path, Path]]) -> None:
    seen: dict[str, tuple[str, str]] = {}
    for source, destination in pairs:
        key = destination.as_posix()
        folded = key.casefold()
        if folded in seen:
            before_key, before_source = seen[folded]
            same = "같은 destination" if before_key == key else "대소문자만 다른 destination"
            raise ExportError(
                f"출력 경로가 겹칩니다 ({same}): {before_key} / {key}\n"
                f"  {before_source}\n  {source.as_posix()}\n"
                "두 소스가 같은 자리를 차지할 수 없습니다. Windows 에서는 대소문자가 "
                "달라도 같은 파일입니다."
            )
        seen[folded] = (key, source.as_posix())

    for folded, (key, source) in seen.items():
        parts = folded.split("/")
        for depth in range(1, len(parts)):
            ancestor = "/".join(parts[:depth])
            if ancestor in seen:
                raise ExportError(
                    f"출력 경로가 겹칩니다 (한쪽이 다른 쪽의 부모): "
                    f"{seen[ancestor][0]} / {key}\n"
                    f"  {seen[ancestor][1]}\n  {source}\n"
                    "같은 이름이 파일이면서 디렉터리일 수는 없습니다."
                )


def check_dest(root: Path, dest: Path) -> Path:
    if dest.exists() or dest.is_symlink():
        raise ExportError(
            f"대상이 이미 있습니다: {dest}\n"
            "이 CLI 는 덮어쓰지 않습니다. 새 경로를 지정하세요 (빈 디렉터리도 거부합니다)."
        )
    parent = dest.parent
    if not parent.is_dir():
        raise ExportError(f"대상의 부모 디렉터리가 없습니다: {parent}")

    resolved_root = root.resolve()
    resolved_dest = parent.resolve() / dest.name
    if resolved_dest == resolved_root:
        raise ExportError("대상이 소스 루트와 같습니다.")
    if resolved_dest.is_relative_to(resolved_root):
        raise ExportError(f"대상이 소스 루트 안입니다: {resolved_dest}")
    if resolved_root.is_relative_to(resolved_dest):
        raise ExportError(f"대상이 소스 루트를 포함합니다: {resolved_dest}")
    return resolved_dest


def copy_all(root: Path, dest: Path, pairs: list[tuple[Path, Path]]) -> int:
    written = 0
    for source, destination in pairs:
        target = dest / destination
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / source, target)
        except OSError as exc:
            raise WriteError(
                f"복사에 실패했습니다: {source.as_posix()} → {destination.as_posix()}\n{exc}\n"
                f"부분 출력이 남아 있습니다: {dest}\n"
                "자동으로 지우지 않습니다. 내용을 확인한 뒤 직접 정리하세요."
            ) from exc
        written += 1
    return written


def build_parser(pack_names: list[str]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="export_template.py",
        description="공통 기본 구성과 선택 pack 을 새 디렉터리로 내보낸다.",
    )
    parser.add_argument(
        "--dest",
        required=True,
        metavar="경로",
        help="만들 새 디렉터리. 이미 있으면 거부한다. 부모는 있어야 한다.",
    )
    parser.add_argument(
        "--pack",
        action="append",
        default=[],
        choices=pack_names,
        metavar="이름",
        help=f"선택 구성. 여러 번 지정할 수 있다. 가능한 값: {', '.join(pack_names)}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows 콘솔의 기본 코드페이지에서 한국어 출력이 깨진다. `doctor.py`·`run_quality.py`
    # 와 같은 처리다 — 두 OS CI 가 같은 출력을 읽어야 한다
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    try:
        root = source_root(Path(__file__))
        manifest = load_manifest(root)
    except ExportError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return EXIT_ERROR

    parser = build_parser(sorted(manifest["packs"]))
    args = parser.parse_args(argv)

    # 같은 pack 을 두 번 적어도 한 번만 센다. 순서는 manifest 가 정한다
    packs = [name for name in sorted(manifest["packs"]) if name in set(args.pack)]

    try:
        pairs = selected_entries(manifest, packs)
        check_sources(root, pairs)
        check_collisions(pairs)
        dest = Path(args.dest)
        resolved_dest = check_dest(root, dest)
    except ExportError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return EXIT_ERROR

    try:
        written = copy_all(root, dest, pairs)
    except WriteError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return EXIT_FAIL

    chosen = ", ".join(packs) if packs else "없음"
    print(f"내보냈습니다: {resolved_dest}")
    print(f"  파일 {written}개 · 선택 pack: {chosen}")
    print("  설치 직후 할 일은 출력의 `HARNESS-INSTALL.md` 에 있습니다.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
