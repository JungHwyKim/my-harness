# template-history-cleanup — implementation report

Date: 2026-11-19. Checkout `main` at `a1ba8a7`. The spec puts the commit and push
outside this task's scope; the user then authorized committing the document
changes, so `README.md`, `.gitignore` and this report are committed. **Nothing
is pushed, and no deploy ref exists yet.**

Implemented against the spec's **uncommitted** 2026-11-19 revision (its diff
against `bfeb428` was the authority; `tasks/template-history-cleanup.md` is still
modified in the tree). Its predecessor condition is met: the environment work is
reported complete, and no session was editing `README.md` — the only file both
tasks touch.

Status: implemented, with the deployment model decided by the user mid-task —
**the harness's History stays on `main`, and only a deploy ref is emptied.** See
"Decision" below. The initial-History criterion is therefore met by a documented
procedure that was executed and verified once, then reverted, rather than by a
permanent deletion on `main`.

## Changed files

| File | Change |
|---|---|
| `README.md` | 빠른 시작 split into 새 프로젝트로 시작 / 기존 프로젝트에 적용 / 적용 직후 고칠 네 곳, plus a new 무엇이 따라오고 무엇이 안 따라오는가 table. States that a plain clone of `main` *does* carry the harness's own records and must be cleared for a new project. The `requirements-harness.txt` guidance moved here from the tail of 유료·외부 테스트 보호, where it sat under an unrelated heading |
| `.gitignore` | The `.agents/`·`.codex/` comment keeps its live path and adds the preservation commit for readers of a deployed copy, where the record is absent |
| `.claude/wiki/history/` | **unchanged in the end** — five records deleted, verified, then restored per the decision |

## Decision: `main` keeps its History

The spec's done criterion reads 「배포할 초기 History에는 공통 README와 세 `.gitkeep`만
남고」. Executing that literally on `main` collides with this repository being
both the harness and the template:

- `CLAUDE.md`'s Context Router sends every future session to
  `.claude/wiki/history/` for decision rationale.
- The handoff procedure's own step 9 writes records into that folder, so template
  preparation would delete them again at every release — an endless loop.

Presented as two options; the user chose to keep History on `main` and strip it
only on the ref that is published. Under that reading the criterion applies to
the deploy ref, not to `main`.

### The deploy-ref procedure

**Naming, chosen by the user: versioned refs, `template/<version>`** — e.g.
`template/v2.1`, then `template/v2.2` for the next publish. Each is cut fresh
from `main`, so older template versions stay reachable and no force-push is
needed. The rejected alternative was a single stable `template` branch
re-pointed each release: one unchanging clone command, but a force-push every
time and no way back to an earlier template. `README.md` now documents this
convention and the `--depth 1` clone.

Executed and verified during this task, then reverted. To publish:

```powershell
git switch -c template/v2.1
Get-ChildItem .claude/wiki/history/plan, .claude/wiki/history/task, .claude/wiki/history/verify -Filter *.md | Remove-Item
git commit -a -m "chore: empty harness history for template deploy"
```

The deploy ref is never merged back into `main` — that commit deletes the
records, and merging it would put the deletion on `main`, which is the whole
thing this model avoids. `README.md` states that too.

`.claude/wiki/history/README.md` is not under those three folders, so it stays,
and `.gitkeep` is not `*.md`, so the three empty folders survive. The resulting
shape is exactly `README.md` plus three `.gitkeep` files — produced and verified
today, see Verification.

Before cutting such a ref, confirm each record exists in a commit. All five did:

| Record | Preserved in | Bytes |
|---|---|---|
| `plan/2026-11-18-handoff-workflow.md` | `bfeb428` | 5499 |
| `plan/2026-11-19-codex-dir-tracking.md` | `bfeb428` | 7656 |
| `plan/2026-11-19-paid-hook-comment-stripping.md` | `bfeb428` | 9166 |
| `plan/2026-11-19-task-spec-identifiers.md` | `438dc3c` | 4791 |
| `task/2026-11-19-spec-changed-mid-implementation.md` | `438dc3c` | 4338 |

Checked with `git cat-file -e` before deleting, and
`git status --short .claude/wiki/history/` was empty beforehand, so the
working-tree copies were identical to the committed ones.

The spec's table named the first three, as of `bfeb428`. The last two existed by
execution time — written earlier today under `task-spec-identifiers` step 9 — so
the spec's own rule applied: 아직 보존되지 않은 내용이 있으면 그 내용을 먼저 보존하고
삭제 여부를 판단한다. Deleting only the three named would leave the criterion
unmet, so the procedure covers all records, not a fixed list.

The persistent rules those records produced live in permanent documents already:
the handoff procedure and task-ID rules in `.claude/skills/handoff/SKILL.md`, the
paid-test contract in `.claude/wiki/knowledge/paid-test-approval.md`, and the
`.agents/`·`.codex/` exclusion in `.gitignore`'s own comment. No rule exists only
inside a record the deploy ref drops.

## References into the records

| Reference | State |
|---|---|
| `.gitignore:10-12` | Live path kept, preservation commit added for deployed copies |
| `tasks/template-history-cleanup.md:73-77` | Correct as written; cites `bfeb428` |
| `tasks/handoff.md:55`, `:95` | **Left alone.** In-flight spec; this task may not modify other tasks' files |
| `tasks/handoff.review.md:65`, `:396` | **Left alone**, same reason |

With `main` keeping its records, none of these is broken today. On a deploy ref
`handoff.review.md:396` would point at an absent path — but the handoff task's
own cleanup removes both of those files before any ref is cut, so the problem
cannot reach a published template.

## Finished temporary specs: nothing eligible

Spec item 5. Every file in `tasks/` checked against the completion and
preservation conditions:

| File | State | Action |
|---|---|---|
| `_template.md` | permanent template, owner Codex | keep |
| `doctor.md` | never implemented — `.claude/harness/scripts/` has only `openwork/` and `quiz/`, and no README or settings entry references `doctor.py` | keep |
| `handoff.md` + `handoff.review.md` | final review still open | keep |
| `quality-env-setup.md` | 최종 리뷰 대기, no review file yet | keep |
| `template-history-cleanup.md` + this report | in progress | keep |

The two `task-spec-identifiers` files were already removed in `a1ba8a7` under
their own task.

## Verification

| Check | Command | Result |
|---|---|---|
| local dirs excluded | `git check-ignore -v .venv/Scripts/python.exe .agents/ .codex/` | matched by `.gitignore:5`, `:23`, `:24` |
| nothing tracked under them | `git ls-files -- .venv .agents .codex` | empty |
| deploy files not ignored | `git check-ignore -q` on `requirements.txt`, `tasks/_template.md`, `README.md`, `history/README.md`, `history/plan/.gitkeep` | none ignored |
| no ignore rule over History | `grep -n history .gitignore` | comment lines only |
| **emptied-History shape** | `find .claude/wiki/history -type f` with the five records deleted | `README.md` + three `.gitkeep`, nothing else — the deploy-ref target state, reached and confirmed |
| Full profile **in that state** | ruff check / ruff format --check / pytest -q | exit 0 / exit 0 / **405 passed** |
| History restored | `find` after `git checkout -- .claude/wiki/history/` | all five records back, `git status` clean for that path |
| Full profile after restore | ruff check / ruff format --check / pytest -q | exit 0 / exit 0, 68 files formatted / **405 passed** |

Running the Full profile while the records were deleted was the point of running
it at all: it proves no test, hook or skill reads those files. None does. The
emptied state is therefore safe to publish.

- **Fast gate does not apply.** `quality.tracked_paths` is `src/`, `tests/`,
  `pyproject.toml`, `.claude/harness.json`; no changed path is under those.
- **No test added.** No executable code or quality setting changed.
- **Not verified:** the actual GitHub upload, a real deploy ref, and what a fresh
  clone looks like to a new user. None is in scope; no push was made.

## History judgement

Not recorded yet, deliberately. The deployment-model decision — `main` keeps its
History, the deploy ref is emptied — is a real architectural choice with a
rejected alternative, so it belongs in Plan History. But it was decided by the
user mid-task and its implementation (an actual deploy ref) does not exist yet.
Recording it now would describe a procedure nothing has executed.

It should be written when the first deploy ref is cut, together with the ref's
name and the commit it came from.

## Remaining

1. **No deploy ref exists.** `template/v2.1` is documented in `README.md` and in
   the procedure above, and the clone command in the README will not work until
   that ref is cut and pushed. The README keeps the `main`-and-clear-it route
   alongside it, so no reader is left without a working path.
2. **Nothing is pushed.** Publishing stays a separate instruction.
3. **Plan History entry** for the deployment model, when that ref is cut.
4. `tasks/quality-env-setup.md` and `tasks/template-history-cleanup.md` are
   Codex's uncommitted edits, left untouched.
5. `doctor.md` is still an unimplemented spec, unrelated to this task.
