# Codex ↔ Claude Handoff — Revised Proposal

Status: workflow installed per `tasks/handoff.review.md`; verification-environment
and reusable-template preparation authorized for Claude Code. Full verification,
template cleanup, and final review pending.

## Purpose and scope

Codex designs, investigates, and reviews results. Claude Code implements, fixes,
and runs tests. Both agents use the same project checkout, so the user can pass
a file path instead of copying its contents between sessions. Confirm the
checkout and current revision at each handoff; another worktree does not share
uncommitted files. Do not edit the same file concurrently.

This document contains the workflow installation design and the authorized
verification-environment follow-up below. Its detailed procedure belongs
in `.claude/skills/handoff/SKILL.md`, with the spec template at
`tasks/_template.md`. `CLAUDE.md` and `AGENTS.md` only route to that procedure.
Keep this proposal until installation, final review, and preservation are done.

Hook behavior, paid-test approval, and Codex hook wiring are outside this task.
They are covered by [the separate hook design](hook-dicision.md); the remaining
duplicate-hook cleanup follows that task's scope. Do not change or revalidate
hook behavior as part of installing this handoff workflow.

## 다음 작업: 검증 환경 구축과 범용 템플릿 준비 — Claude Code

### 목적과 현재 근거

`tasks/handoff.review.md`에서 미완료로 남은 Full 검증을 실행할 수 있도록 이 저장소의
개발용 Python 환경과 설치 명세를 마련한다. 이 절의 환경 구축·설치·검증은 사용자가
승인한 작업이다. 어느 프로젝트에서도 다시 설치할 수 있도록 설치 안내와 의존성을
배포하고, 새 프로젝트의 History는 빈 상태에서 시작하게 한다. Claude Code가 수행하고
같은 리뷰 파일에 결과를 덧붙인다.

- `.claude/harness.json:4`는 `.venv/Scripts/python.exe`를 사용하도록 설정한다.
  2026-11-18 확인 시 해당 실행 파일은 없었다. 인수 시 현재 상태를 다시 확인한다.
- `.claude/harness.json:41`, `:46`, `:51`의 Full 단계는 Ruff 린트·포맷 검사와 pytest다.
- `.gitignore:5`에 `.venv/` 제외 규칙이 추가되었다. 유지하고 실제 제외 여부를 확인한다.
- `requirements.txt:7`과 `:8`에 pytest·ruff 고정 버전이 작성되었다. 인수 시 설치·검증
  결과와 맞는지 확인한다. 파일 생성만으로 GitHub 반영이 끝난 것은 아니다.
- `README.md:90`에는 테스트 명령이 있지만 개발 의존성 설치 순서는 없다.
- 현재 기준 브랜치와 HEAD는 `release/v2`, `4f5300c`다. 인수 시 실제 체크아웃·리비전과
  기존 변경을 확인하고 그 상태를 보고에 남긴다.

### 구현 범위

| 대상 | 작업 |
|---|---|
| `.venv/` | 사용 가능한 Python으로 저장소 전용 가상환경을 만들고 검증 도구를 설치한다. 이미 정상 환경이 있으면 재사용한다. |
| `requirements.txt` | 직접 개발 의존성 `pytest`, `ruff`를 명시하고, 검증에 사용한 두 패키지의 버전을 `==`로 고정한다. |
| `.gitignore` | 기존 항목을 유지하며 `.venv/`를 추가한다. 가상환경 내용은 Git 관리 대상에서 제외한다. |
| `README.md` | 가상환경 생성, requirements 설치, Full 검사 명령을 현재 검증 안내에 추가한다. |
| 템플릿 배포 파일 | `requirements.txt`, README 설치 안내, `.gitignore`, 공통 지침·절차·작업 템플릿을 GitHub에 포함할 대상으로 정리한다. `.venv/`는 포함하지 않는다. |
| `.claude/wiki/history/plan/2026-11-18-handoff-workflow.md` | 필요한 현재 규칙과 보존할 이유를 확인한 뒤, 아래 보존 조건에 따라 템플릿의 초기 History에서 정리한다. |
| `.claude/wiki/history/` | 공통 README와 `plan/`·`task/`·`verify/`의 `.gitkeep`만 초기 구조로 남긴다. |
| `tasks/handoff.review.md` | 기존 보고를 보존하고 환경 구축 결과와 Full 각 단계의 실제 결과를 영어로 덧붙인다. |

처음에는 `pytest`와 `ruff`를 설치하고, 실제 설치된 버전을 확인해 `requirements.txt`를
고정한다. 전역 환경의 `pip freeze`를 복사하지 않는다. 버전을 고정한 파일로 다시 설치해
설치가 성공하는지 확인하고, 패키지 간 의존성 검사도 수행한다.

저장소 루트의 Windows PowerShell 실행 예시는 다음과 같다. 모든 pip·검증 호출은
가상환경의 Python을 직접 지정한다. 활성화 스크립트나 전역 Python에 의존하지 않는다.

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q
```

이 명령들은 현 Full 프로필의 세 단계를 직접 실행한 것이다. 실행 시점의 설정과 다시
대조하고, 각 단계의 종료 코드와 결과를 개별 기록한다. 설치 실패·네트워크 제약이 있으면
실패한 명령과 원인을 보고한다. 미실행 검사를 통과로 적지 않는다.

### GitHub 배포와 새 프로젝트의 초기 상태

- GitHub에 올릴 것은 가상환경 생성·설치 방법과 의존성 명세다. `.venv/`와 설치된
  패키지·실행 파일은 프로젝트마다 다시 만들며 배포하거나 커밋하지 않는다.
- `requirements.txt`의 pytest·ruff는 이 하네스 저장소를 개발·검증하기 위한 도구다.
  이를 모든 대상 프로젝트의 제품 의존성이나 필수 품질 도구로 설명하지 않는다.
  다른 언어 프로젝트는 해당 도구에 맞게 Quality Profile을 구성하도록 README에 적는다.
- README에 새 템플릿으로 시작하는 경우와 기존 프로젝트에 가져오는 경우를 구분한다.
  기존 프로젝트의 `requirements.txt`를 덮어쓰지 않는다. 기존 프로젝트에 적용할 때는
  하네스의 의존성 파일을 `requirements-harness.txt`라는 별도 이름으로 가져와 필요한
  검증 도구를 설치하는 예시를 제공한다. 기존 가상환경과 프로젝트 설정도 덮어쓰지 않는다.
- 새 프로젝트에는 이 하네스를 개발하면서 만든 Plan·Task·Verify 기록을 넣지 않는다.
  공통 규칙·절차·템플릿은 유지하고, History는 공통 README와 빈 폴더의 `.gitkeep`만
  남긴다. `.gitignore`로 History 전체를 막지 않는다. 적용 후 새 프로젝트가 생성하는
  중요한 기록은 기존 절차대로 보존해야 한다.
- 현재 `2026-11-18-handoff-workflow.md`는 미추적 파일이다. 삭제 전에 지속되는 규칙은
  공통 절차에 반영됐는지 확인하고, 미래에도 필요한 결정 이유는 보존 가능한 기록에
  남긴다. 미추적·스테이징 상태만으로 Git에 보존됐다고 판단하지 않는다. 보존 조건을
  채우지 못하면 삭제를 미루고 템플릿 정리 미완료로 보고한다.
- 템플릿 배포 전에는 종료된 임시 명세·리뷰도 기존 완료·보존 조건에 따라 정리한다.
  `tasks/_template.md`와 아직 진행 중인 작업은 유지한다. 템플릿 관리 중 새 기록이 생기면
  배포 전 같은 기준으로 확인한다. 이 기준은 기존 프로젝트 사용자의 기록을 일괄
  삭제하는 명령이나 실행 시 자동 초기화를 뜻하지 않는다.
- GitHub의 새 템플릿 프로젝트는 원본 브랜치의 파일을 가져오므로, 배포할 브랜치의 실제
  파일 목록을 확인한다. `.gitignore`에 적는 것만으로 이미 추적된 기록이 빠지지 않는다.
  이번 작업은 배포할 변경을 준비·검증하는 범위이며 커밋·푸시는 별도 지시를 따른다.

### 범위와 제외

- 이 작업은 검증 환경 구축이다. 훅 코드·훅 설정·유료 테스트 승인, CI, Quality Profile의
  추적 경로 확대는 별도 작업으로 유지한다.
- `.claude/harness.json:14`의 추적 경로에는 이번 환경·문서 파일이 포함되지 않는다.
  Fast 자동 검사에 해당하지 않는 이유를 보고하고, Full은 직접 실행한다.
- 설치 후 기존 코드의 린트·포맷·테스트 실패가 드러나면 파일·원인·출력을 기록한다.
  검사를 통과시키려고 저장소 전체를 자동 포맷하거나 검사 규칙을 완화하지 않는다.
  환경 구축으로 해결되지 않는 실패는 후속 수정 대상으로 보고한다.
- 리뷰 F1은 영구 템플릿의 GitHub 포함 대상과 초기 기록 정리 기준을 반영해 상태를
  갱신한다. 실제 커밋이 없다면 보존이 끝났다고 표시하지 않는다. F2~F4는 별도 잔여
  항목으로 유지한다. 커밋과 아직 진행 중인 임시 명세·리뷰 삭제는 이 후속 작업에
  포함하지 않는다.
- Windows 로컬 환경이 이번 검증 대상이다. Linux 경로와 CI 호환성은 검증하지 않았다면
  미검증으로 보고한다. 기존 가상환경을 임의로 지우거나 전역 패키지를 변경하지 않는다.

### 검증 및 완료 기준

| 확인 사항 | 통과 기준 |
|---|---|
| 설정된 인터프리터 | `.venv/Scripts/python.exe`가 존재하고, 그 실행 파일의 `sys.executable`이 해당 가상환경을 가리킨다. |
| 의존성 재설치 | `requirements.txt`에 검증한 pytest·ruff 버전이 고정되고, 해당 파일로 설치와 `pip check`가 성공한다. |
| Git 제외 | `git check-ignore .venv/Scripts/python.exe`로 제외를 확인하고, requirements와 README는 제외되지 않는다. |
| Full 검증 | Ruff 린트·포맷 검사와 전체 pytest를 각각 실행하고 종료 코드 0을 확인한다. 하나라도 실패·미실행이면 Full 검증 완료로 표시하지 않는다. |
| 재현 안내 | README의 명령과 실제 실행 명령이 일치하고, Python·pytest·ruff 버전, 테스트 통과·실패·건너뜀 수, 남은 문제를 리뷰에 기록한다. |
| 배포 파일 | requirements·설치 안내·작업 템플릿이 GitHub 포함 대상으로 준비되고, `.venv/` 내용은 추적되지 않는다. 기존 프로젝트에 적용하는 안내는 대상 requirements와 설정을 덮어쓰지 않는다. |
| 초기 History | 최종 배포할 History에 공통 README와 세 `.gitkeep`만 남으며, 제거한 기존 기록의 필요한 내용은 보존되어 있다. 조건을 못 채우면 정리 미완료를 보고한다. |
| 초기 작업 파일 | 완료·보존 조건을 만족한 임시 명세·리뷰만 정리하고 `tasks/_template.md`와 진행 중인 작업은 유지한다. 배포할 브랜치의 파일 목록과 미완료 정리 항목을 보고한다. |

새 실행 코드를 추가하지 않는 환경·설치 문서 작업이므로 전용 테스트를 새로 만들 필요는
없다. 환경 구축 성공과 Full 검증 성공은 구분해 보고한다. Codex의 결과 리뷰와 기록 보존이
끝날 때까지 이 명세와 리뷰를 유지한다.

## Roles and ownership

| File | Owner | Language | Lifetime |
|---|---|---|---|
| `tasks/<feature>.md` | Codex | Korean | temporary; Claude cleans up after completion and preservation |
| `tasks/<feature>.review.md` | Claude | English | temporary; same cleanup conditions as the spec |
| `tasks/_template.md` | maintained with the workflow | Korean | kept |
| `.claude/skills/handoff/SKILL.md` | shared workflow source | Korean | kept |
| `.claude/wiki/knowledge/<topic>.md` | implementation owner | Korean | kept; current contracts and behavior |
| `.claude/wiki/history/plan/YYYY-MM-DD-<topic>.md` | Claude using the existing Plan History procedure | Korean | kept when the decision rationale merits it |

**One spec, one owner.** Claude writes findings and proposed corrections in the
review file; Codex revises the spec in place. Do not create competing specs such
as `doctor-revised.md`. Claude's cleanup responsibility does not give Claude
authority to rewrite the spec. Git preserves only content that was committed;
an untracked file is not a recoverable revision history.

## Languages

Specs are Korean, Claude's reviews and implementation reports are English,
and permanent workflow prose and wiki records are Korean. `AGENTS.md` is also
Korean, preserving its existing rules. Quoted code, identifiers, and source excerpts keep their
original language.

When a review finding becomes a lasting contract or decision record, summarize
it in Korean in the appropriate owner document. This proposal remains English
as the existing review document; it is temporary under the same cleanup rules.

## Handoff workflow

1. Codex writes `tasks/<feature>.md` using `tasks/_template.md` and records the
   scope, source evidence, verification plan, and done criteria.
2. The user starts Claude's review with one line, for example:
   "review `tasks/<feature>.md`".
3. Claude checks the spec against the current code and writes findings,
   evidence, proposed corrections, and unresolved questions to
   `tasks/<feature>.review.md`.
4. The user passes that path back to Codex. Codex reads the review and revises
   the original spec. Routine omissions and corrections within the authorized
   scope do not require a new confirmation. There is no fixed one-revision cap.
5. Bring scope changes, unresolved conflicting requirements, or a repeated
   disagreement with no new evidence to the user. State the decision needed
   and its consequence; do not silently choose a different scope.
6. Claude implements the revised spec when implementation is authorized. If
   that authorization was already given, do not ask for it again. Claude fixes
   issues within scope and runs the applicable quality checks.
7. Claude updates the same review file with an implementation and verification
   report: changed files, exact commands and results, checks not run and why,
   remaining issues, and any deviation from the spec. Keep unresolved findings
   visible rather than overwriting them with a completion claim.
8. Codex reads the report and inspects the matching code changes against the
   done criteria. Claude fixes blocking findings and updates the report before
   the work is considered complete. Codex's result review does not substitute
   for Claude's test execution. Apply the review and repair policy below when
   findings require another implementation pass.
9. After the final review and required verification are complete, Claude
   preserves the lasting information and checks the deletion conditions below
   before removing the two temporary task files.

**Handoffs are user-triggered.** A path replaces copying the text; writing a
file does not start another session. The user can start the next phase with a
short instruction naming the path. Work within an already authorized phase
continues without repeated permission requests. This workflow adds no automatic
cross-session trigger.

## Review, repair, and model escalation

Install this policy in the shared procedure, not in both entry-point files.
These thresholds are operating defaults, not vendor guarantees. Model versions
and pricing do not belong in durable instructions.

- Use Sonnet with Medium effort for ordinary implementation. Use a higher
  effort setting for complex logic when needed, and Opus for difficult root-cause
  analysis. Use the models and settings available in the user's Claude Code.
- Codex records each blocking finding with a stable identifier, the affected
  file and location, reproduction conditions or code evidence, expected
  behavior, and verification criteria. Label unverified suspicions explicitly.
- Claude checks the finding against the current code and tests before changing
  code. A review comment alone is not proof of a defect. Record counterevidence
  in the same review file when a finding is incorrect or cannot be reproduced.
- Keep the finding, attempted fixes, failed approaches, exact verification
  results, and remaining issues in `tasks/<feature>.review.md`. A repair attempt
  counts as failed when its verification or the subsequent review shows that
  the same defect remains. The initial implementation is not a repair attempt;
  separate defects do not share a counter.

| Condition | Next action |
|---|---|
| A defect is found in the initial implementation | Claude verifies it, then repairs it with Sonnet and runs the relevant checks. |
| The first repair fails to resolve the same defect | Strengthen the reproduction, relevant logs, or a regression test, then make one more Sonnet repair attempt. |
| Two repair attempts fail to resolve the same defect | Recommend switching Claude to Opus and analyze the cause before another edit. |
| Repairs repeatedly break other behavior | Reduce the change scope and recommend Opus analysis without waiting for the attempt threshold. |
| The cause is a missing or conflicting requirement or a design defect | Return the design to Codex; Claude records proposed corrections without rewriting the spec. |

Model escalation is a recommendation to the user, who controls the next Claude
session or model selection. Writing a file does not switch models or start a
session. Existing authorization for a model switch remains valid; if the model
is unavailable, report the limitation and continue evidence gathering without
repeating the same unsupported patch.

When escalating, provide the finding identifier, reproduction, failed attempts,
and verification results. Ask for a root-cause explanation followed by a minimal
fix and verification. If no new evidence emerges, stop blind repair loops and
report the blocker or decision needed. Final completion still requires the done
criteria and no unresolved blocking findings; model choice is not verification.

## Completion, preservation, and cleanup

A completed work order left among active tasks can be mistaken for a current
contract. Claude removes a task's spec and review only after all of the
following are true:

- The implementation meets its done criteria, the required checks are
  accounted for, and Codex's final review has no unresolved blocking findings.
- Current contracts and behavior have been summarized in the relevant
  `.claude/wiki/knowledge/` document. Decisions worth retaining follow the
  existing Plan History procedure and the paths configured in
  `.claude/harness.json`.
- Either the latest contents of both temporary files exist in a verified Git
  commit, or the necessary information has been preserved in the appropriate
  permanent documents. Merely adding a file to Git's index is not enough.

If preservation is incomplete, keep the files and report the remaining cleanup
work. Do not create a commit solely to satisfy this condition without existing
authorization, and do not delete unrelated tasks, `tasks/_template.md`, or the
shared procedure.

Knowledge holds what is true now; Plan History holds significant choices and
their reasons, including rejected alternatives. Do not move entire completed
specs or reviews into Plan History by default. A task using the preservation
alternative does not promise that its complete original text remains in Git.

## Spec template requirements

Create `tasks/_template.md` with purpose, execution contract, scope and
exclusions, existing-code evidence, implementation and verification, and done
criteria. Put detailed authoring prompts in that template, not in the two
entry-point instruction files.

- For work that defines diagnostic checks, assign a severity to each check and
  state the aggregate exit-code rule. Mark this section not applicable when
  the work has no such checks.
- Write out implementation-critical mappings and decision tables when needed.
- When configuration or a versioned contract is affected, specify older-version
  behavior and defaults. Otherwise mark compatibility not applicable.
- Cite claims about existing code with `file:line`, or label them unverified.
  Recheck evidence against the current files before relying on it.
- State the required verification, its completion criteria, and how skipped
  checks or remaining issues will be reported.

## Entry-point routing to install

Install the shared procedure and template before adding these routes. Keep
`AGENTS.md` under its existing 120-line limit and preserve its other rules.
The detailed procedure has one source; do not copy its checklist into both
entry files.

`CLAUDE.md`, after Context Router:

```markdown
## 작업 인수인계

- Codex와 Claude Code 사이의 작업 인수인계는 `.claude/skills/handoff/SKILL.md`를 읽고 따른다.
```

`AGENTS.md`, after its quality verification section:

```markdown
## 작업 인수인계

- Claude Code와 작업을 주고받을 때는 `CLAUDE.md`의 작업 인수인계 경로를 따른다.
```

## Installation done criteria

- The shared procedure and template exist at the paths above, in Korean, and
  contain the ownership, language, handoff, verification, cleanup, and review,
  repair, and model escalation rules. The review report can track individual
  findings and their repair attempts without losing unresolved issues.
- The two entry points route to that source without duplicating the procedure;
  every local route resolves and `AGENTS.md` remains under 120 lines.
- A read-through confirms the full sequence from design to final cleanup and
  that an untracked, unpreserved task cannot be deleted as completed work.
- The installer reports verification performed. Code tests and quality profiles
  are run when code or harness configuration changes warrant them; a prose-only
  change reports why those checks were not run.
- Hook implementation and hook configuration remain owned by their separate
  task. This proposal is removed only after these criteria and its preservation
  conditions are satisfied.
