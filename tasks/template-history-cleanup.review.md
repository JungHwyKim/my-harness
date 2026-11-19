# template-history-cleanup — implementation report

Date: 2026-11-19, fix round 2026-11-20 on `main` at `6286ec0`. The spec puts the
commit and push outside this task's scope; the user then authorized committing the
document changes, so the 2026-11-19 versions of `README.md`, `.gitignore` and this
report are in `6286ec0`. **The 2026-11-20 fixes are uncommitted, nothing is
pushed, and no deploy ref exists yet.**

Implemented against the spec's **uncommitted** 2026-11-19 revision (its diff
against `bfeb428` was the authority; `tasks/template-history-cleanup.md` is still
modified in the tree). Its predecessor condition is met: the environment work is
reported complete, and no session was editing `README.md` — the only file both
tasks touch.

Status: implemented; Codex's 2026-11-20 review raised THC-01 and THC-02, both now
fixed and verified — see "Review findings" below. The deployment model was decided
by the user mid-task: **the harness's History stays on `main`, and only a deploy
ref is emptied.** See "Decision" below.

The initial-History criterion is reported in two halves, as the review asks.
**Cleanup procedure: verified** — executed in an isolated clone, see THC-01.
**Actual deploy state: pending** — no deploy ref exists, and producing the emptied
state locally then reverting it is not evidence that a published ref is in that
state.

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

Executed and verified during this task, then reverted. To publish, cut the ref in
its own worktree rather than on the checkout you work in — THC-01 below says why:

```powershell
git worktree add -b template/v2.1 ../my-harness-template main
cd ../my-harness-template
Get-ChildItem .claude/wiki/history/plan, .claude/wiki/history/task, .claude/wiki/history/verify -Filter *.md | Remove-Item
git add -A .claude/wiki/history
git commit -m "chore: empty harness history for template deploy"
git show --name-status --format= HEAD
```

That last line is the gate before any push: the list must be the record deletions
and nothing else. Afterwards, from the main checkout,
`git worktree remove ../my-harness-template` — the branch stays, only the extra
working copy goes.

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

## Review findings — Codex, 2026-11-20

Both are first-implementation defects, so neither carries a failed fix attempt.
Grounds were checked against the repository before anything changed, and both
reproduce. Fixed on this existing Opus session rather than switching to Sonnet as
the procedure's default suggests — model choice is the user's, and both fixes are
documentation changes.

Verification ran in throwaway clones under the session scratchpad, never on
`main`. Each clone reproduced the real checkout's two unrelated spec edits, one
staged and one unstaged, because that is the condition the findings turn on.

### THC-01 · P1 — unrelated changes could enter the deploy commit

**Confirmed.** The example cut the ref on the working checkout and committed with
`git commit -a`, which takes every tracked modification. Clone A, running it
verbatim, produced a commit holding the five record deletions **plus**
`tasks/quality-env-setup.md` and `tasks/template-history-cleanup.md`.

Fixed by cutting the ref in its own worktree. `git worktree add -b template/v2.1
../my-harness-template main` starts from `main`'s commit with a clean tree and its
own index, so neither staged nor unstaged changes in the source checkout can reach
it. The commit is `git add -A .claude/wiki/history` and a plain `git commit` — no
`-a` — and `git show --name-status` is the gate before pushing. Nothing in the
source checkout is deleted, restored or stashed, as the review required.

Clone B, same dirty state as A:

| Check | Result |
|---|---|
| files in the deploy commit | the five record deletions, nothing else |
| History shape on the ref | `README.md` + three `.gitkeep` |
| deploy worktree afterwards | `git status --short` empty |
| source checkout afterwards | both unrelated edits intact, the staged one still staged |

### THC-02 · P2 — the preservation hint fails in a shallow clone

**Confirmed, and reproduced further than the review could.** Cutting the ref in
clone B gave a real deploy ref to clone from:
`git clone --depth 1 --branch template/v2.1 file://…` yields one commit, History
already in the target shape, and the documented lookup failing.

| Route | Result in that shallow clone |
|---|---|
| `git show bfeb428:<record>`, as `README.md` and `.gitignore` told the reader | `fatal: invalid object name 'bfeb428'` |
| `git fetch --depth 1 origin bfeb428` — fetch that one commit by sha | `fatal: couldn't find remote ref bfeb428`; refused by the local test server, so it is not offered as a route. Whether github.com answers it is untested |
| `git fetch --unshallow`, then the same `git show` | record printed |
| blob URL at the preservation commit | **not verified** — this run had no network |

Fixed in both documents: the `git show` form now carries its precondition (the
commit must be local, which a full clone of `main` satisfies), and a shallow copy
gets two routes — the origin repository's blob URL at the preservation commit, and
`git fetch --unshallow` followed by the same `git show`. The clone method and the
lookup method now agree, which is what the review's criterion asked for.

Two limits, both written into the documents' own wording: the blob URL opens only
for pushed commits, and `438dc3c` — the preservation commit for two of the five
records — is on no remote (`git branch -r --contains 438dc3c` is empty, while
`bfeb428` is on `origin/main`). Until `main` is pushed, those two records are
reachable only from a local full clone or through `--unshallow`.

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
- **Not verified:** the actual GitHub upload and a published deploy ref. Neither
  is in scope; no push was made. What a fresh clone looks like *was* verified in
  the fix round, locally — see THC-01 and THC-02.

### Fix round, 2026-11-20

The two tables under "Review findings" are the verification for THC-01 and
THC-02. No path under `quality.tracked_paths` (`src/`, `tests/`,
`pyproject.toml`, `.claude/harness.json`) changed, so the Fast gate does not
match, and the Full profile was not re-run for two documentation fixes;
`git diff --check` reports nothing. The `405 passed` above is Claude's 2026-11-19
run, not a Codex re-execution.

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
2. **Nothing is pushed**, this fix round included. The revision request does not
   authorize a commit, so `README.md`, `.gitignore` and this report are modified
   in the working tree only.
3. **`438dc3c` is on no remote.** The blob route added for THC-02 resolves for
   `bfeb428` but not for the two records preserved in `438dc3c`, until `main` is
   pushed. The `--unshallow` route works either way.
4. **The deploy procedure lives only in this temporary file.** Step 9 deletes it.
   It should land in the Plan History entry written when the ref is cut, or in
   `README.md` as a maintainer section — the spec owns where deploy steps belong,
   so this is Codex's call, not a change made here.
5. **Plan History entry** for the deployment model, when that ref is cut.
6. `tasks/quality-env-setup.md`, `tasks/template-history-cleanup.md` and
   `.claude/skills/handoff/SKILL.md` are Codex's uncommitted edits, left
   untouched. SKILL.md changed *during* this fix round — it gained a
   「리뷰 결과 기록과 종료 확인」 section — which is why the working tree holds a
   file this task never touched. Nothing in that section changes what this report
   owes: the verdict stays in the spec, this file stays Claude's.
7. `doctor.md` is still an unimplemented spec, unrelated to this task.
