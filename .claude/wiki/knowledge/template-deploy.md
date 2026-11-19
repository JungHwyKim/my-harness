# 템플릿 배포 모델

이 저장소는 하네스이면서 그 하네스의 템플릿이다. 그래서 **기록을 보존하는 자리와 배포하는
자리를 가른다.** 받는 쪽의 절차는 `README.md`의 「빠른 시작」이, 무엇이 따라오는지는 같은
문서의 표가 소유한다. 이 문서는 내보내는 쪽의 계약이다.

## 두 자리

| 자리 | 하는 일 |
|---|---|
| `main` | 작업 공간이고 **History를 보존한다.** `CLAUDE.md`의 Context Router가 결정 이유를 찾아 보내는 곳이고, 인수인계 절차 9단계가 기록을 쓰는 곳이다 |
| `template/<버전>` | 배포용 ref. `main`에서 새로 끊어 **초기 History만 비운** 스냅샷이다 |

`main`에서 History를 비우면 두 역할이 충돌한다 — 릴리스마다 방금 쓴 기록을 다시 지우는
순환이 된다. 그래서 「배포할 초기 History에는 공통 README와 세 `.gitkeep`만 남는다」는
기준은 **배포 ref에만 적용된다.**

## 배포 ref 규칙

- **버전마다 새 ref를 끊는다** — `template/v2.1`, 다음 배포는 `template/v2.2`. force-push가
  필요 없고 이전 템플릿 버전이 계속 닿는다. 하나의 `template` 브랜치를 매번 옮기는 방식은
  기각했다(clone 명령이 불변인 대신 force-push가 매번 필요하고 되돌아갈 수 없다).
- **전용 worktree에서 끊는다.** 작업 중인 체크아웃에서 끊으면 무관한 변경이 배포 커밋에
  섞인다.
- **푸시 전 게이트**: `git show --name-status --format= HEAD`의 목록이 기록 삭제뿐이어야
  한다. 다른 것이 보이면 푸시하지 않는다.
- **배포 ref는 `main`으로 병합하지 않는다.** 그 커밋이 기록을 지우는 커밋이고, 병합하면
  삭제가 `main`에 얹힌다. 이 모델이 피하려는 것이 정확히 그것이다.
- 비우는 범위는 `history/plan`·`task`·`verify` 아래의 `*.md`다. `history/README.md`는 그 세
  폴더 밖이고 `.gitkeep`은 `*.md`가 아니므로 둘 다 남는다.

## 끊기 전 보존 확인

**그 시점의 기록 전부**를 확인한다. 고정 목록을 확인하는 것이 아니다 — 명세가 이름을 적은
뒤에 새 기록이 생기면 그것까지 보존해야 기준이 충족된다.

| 보존 기준점 | 담긴 기록 |
|---|---|
| `bfeb428` | `plan/2026-11-18-handoff-workflow.md`, `plan/2026-11-19-codex-dir-tracking.md`, `plan/2026-11-19-paid-hook-comment-stripping.md` |
| `438dc3c` | `plan/2026-11-19-task-spec-identifiers.md`, `task/2026-11-19-spec-changed-mid-implementation.md` |

두 커밋 모두 `origin/main`에 있다(2026-11-20 확인). Git 색인에 올리기만 한 것은 보존이
아니다.

## 끊는 절차

작업 중인 체크아웃에서 끊지 않는다. 전용 worktree는 `main`의 커밋에서 **깨끗한 작업 트리와
자기 색인**을 들고 시작하므로, 원래 체크아웃의 스테이징·미스테이징 변경이 배포 커밋에 닿을
수 없다. 다른 작업의 변경을 지우거나 되돌려 트리를 깨끗하게 만들지 않는다 — 격리로 푼다.

위 「끊기 전 보존 확인」을 끝낸 뒤, 저장소 루트에서 실행한다.

```powershell
git worktree add -b template/v2.1 ../my-harness-template main
cd ../my-harness-template
Get-ChildItem .claude/wiki/history/plan, .claude/wiki/history/task, .claude/wiki/history/verify -Filter *.md | Remove-Item
git add -A .claude/wiki/history
git commit -m "chore: empty harness history for template deploy"
git show --name-status --format= HEAD
```

- 스테이징은 `.claude/wiki/history` 경로만 한다. `git commit -a`는 쓰지 않는다 — 추적된
  수정 전부를 끌어온다.
- 마지막 `git show`가 푸시 전 게이트다. 목록이 기록 삭제뿐이어야 한다. 남는 모양은
  `history/README.md`와 세 `.gitkeep`이다.
- 푸시한 뒤 원래 체크아웃에서 `git worktree remove ../my-harness-template`로 작업 사본만
  지운다. 브랜치는 남는다. 커밋하지 않은 변경이 그 worktree에 있으면 `remove`가 거부하므로,
  강제로 지우지 말고 무엇이 남았는지 본다.
- 검증 기록: 무관한 수정 하나를 스테이징하고 다른 하나를 미스테이징한 격리 복제에서 배포
  커밋에 기록 삭제 5개만 담겼고, 원래 체크아웃의 수정은 그대로였다(2026-11-20).

## 배포 사본에서 기록 읽기

| 사본 | 방법 |
|---|---|
| `main`을 통째로 clone | `git show <커밋>:<경로>` |
| 배포 ref를 `--depth 1`로 clone | 그 커밋이 로컬에 없어 위 명령이 **실패한다.** `git fetch --unshallow` 뒤에 쓰거나, 원본 저장소의 blob URL로 읽는다 |

`.gitignore`의 주석도 같은 전제를 달고 보존 커밋을 가리킨다.

## 기록이 빠져도 규칙은 남는다

배포 ref가 버리는 것은 결정의 **이유**이고 규칙 자체는 영구 문서에 있다 — 인수인계 절차와
작업 ID 규칙은 `.claude/skills/handoff/SKILL.md`, 유료 테스트 계약은
`paid-test-approval.md`, 검증 환경 계약은 `quality-env.md`, `.agents/`·`.codex/` 제외는
`.gitignore`의 주석이다. **배포 ref에서만 읽을 수 있는 규칙은 두지 않는다.**

## 현재 상태

- `template/v2.1` ref는 **아직 없다.** `README.md`의 `--branch template/v2.1` clone 명령은
  ref를 끊어 푸시한 뒤에 동작한다. 그래서 README는 `main`을 clone 해 기록을 지우는 경로를
  함께 둔다.
- 위 절차는 실제로 실행해 결과 모양(`README.md` + 세 `.gitkeep`)을 확인한 뒤 되돌렸다.
- 배포 모델 결정 자체의 Plan History 기록은 아직 없다. ref를 끊을 때 남긴다.
