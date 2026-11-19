# task-spec-identifiers — implementation report

Date: 2026-11-19. Checkout `main` at `bfeb428`, clean before this work. No
commits made. Implemented against the spec as revised on 2026-11-19 — see
"The spec changed under the implementation" below, which is a finding in its
own right.

Status: implemented, approved by Codex on 2026-11-19, preserved in `438dc3c`
and cleaned up under step 9. The Full profile is green. One deviation and two
out-of-spec additions are listed; nothing is left unreported.

## Changed files

| File | Change |
|---|---|
| `.claude/skills/handoff/SKILL.md` | +42 / −10. New `## 작업 ID와 명세 파일` section; placeholders moved from `<기능>` to `<작업 ID>`; ownership row for the template filled in; steps 1-4 and the one-owner paragraph reconciled with the in-progress rule |
| `tasks/_template.md` | +15 / −4. Metadata header (작업 ID, 상태, 명세, 리뷰, 선행 작업, 관계) and a header comment naming the file a permanent, Codex-owned template |
| `CLAUDE.md` | +1. `.claude/skills/` row added to Information Ownership — **F4**, outside this spec; see additions |

`AGENTS.md` was not touched: 57 lines, still under its 120-line limit, and the
spec's item 3 forbids copying the detailed rules into either entry file.

## What the spec asked for, and where it now lives

| Spec requirement | Where |
|---|---|
| Unique ID and a new file per task; no overwriting | `SKILL.md` 「작업 ID와 명세 파일」 1st, 5th bullets |
| `tasks/<작업 ID>.md` / `.review.md`, same ID for both | 2nd bullet, and the ownership table rows |
| No generic reuse of `handoff.md`/`plan.md`/`task.md`, no date-or-`v2`-only split | 3rd bullet |
| Check for an existing path; disambiguate by target and purpose | 4th bullet |
| A deleted task's ID is not reusable; check with `git log --all` | 4th bullet |
| Codex may polish a draft in place; a spec Claude is reviewing or implementing is frozen | 5th bullet, plus step 4 of 절차 and the 「한 명세에 소유자는 하나다」 paragraph |
| In-place revision only for that task's own revision requests | 5th bullet, same paragraph |
| New work / added scope / changed requirements become a new-ID follow-up, not a competing copy | 6th bullet |
| A follow-up records its predecessor and relation; same-file follow-ups wait | 7th bullet |
| A 상태 field grants Claude no authority over the spec | 8th bullet, and the template's 상태 line |
| Template header fields, 「없음」 or completion evidence for 선행 작업 | `_template.md` lines 3-9 |
| 관계 states new-vs-follow-up, predecessor path, changed scope, no automatic replacement | `_template.md` 관계 line |
| `_template.md` is a permanent template owned by Codex | ownership table + the template's own comment |
| One source for the procedure; no duplication into `CLAUDE.md`/`AGENTS.md` | neither entry file gained a rule; `CLAUDE.md`'s one added line is an ownership pointer, not procedure |

## Five cases walked through the changed documents

Required by 구현 및 검증. Done by reading, against real paths; no throwaway
spec or review files were created.

1. **Draft revision.** Codex drafts `tasks/foo.md`, no one else has opened it.
   5th bullet permits in-place polishing. Path unchanged, no new ID.
2. **Change request while Claude is working.** Claude is at step 3 or 6 on
   `tasks/foo.md`. 5th bullet freezes body and path; step 4 repeats it; the new
   requirement becomes a new-ID follow-up under the 6th bullet. The 「한 명세에
   소유자는 하나다」 paragraph no longer reads as blanket permission to edit in
   place — it now carries the same qualifier.
3. **Applying a finished review.** Claude's step has ended and no agent holds
   the file. 5th bullet allows the in-place revision, for that task's own
   findings only.
4. **ID collision.** 4th bullet: an existing path forces a more specific ID,
   and a deleted task's ID stays retired — `git log --all -- tasks/<작업 ID>.md`
   finds it. Verified on a real case: that command returns `07bd76e` for
   `tasks/hook-dicision.md`, so the retired ID is discoverable after deletion.
5. **Finished predecessor.** The template's 선행 작업 field takes 「없음」 or the
   completion evidence, so a done prerequisite is not carried as an open
   dependency. `tasks/quality-env-setup.md` is the live example.

No sentence in the procedure now tells Codex to revise a spec Claude is working
on, and no sentence sends new work to a generic `handoff.md`.

## Deviation: the template's owner is Codex, not Claude

I first named **Claude** the owner of `tasks/_template.md`, reasoning that
editing the procedure and the template is implementation work and that this very
task is Codex specifying such an edit for Claude. The revised spec decides
**Codex**, as "명세 작성 담당". I implemented the spec's decision and record mine
only as the alternative that was rejected.

The practical consequence is worth stating: Codex now owns a file that Claude
edits on Codex's instruction, which is the same split the ownership table
already uses for `tasks/<작업 ID>.md`. It is consistent; it just means "owner"
in this table means "decides the content", not "types it".

`.claude/skills/handoff/SKILL.md`'s own row still reads 「이 절차의 원본」 with no
named agent — the same gap F2 raised for the template, one row down. The spec
did not ask for it and I did not change it.

## Out-of-spec additions

Both were named in the session where the user chose this task and are reported
here rather than folded into the spec's own scope.

1. **F4** — `CLAUDE.md` Information Ownership gained a `.claude/skills/` row, to
   match `AGENTS.md:53`. One line, no procedure text.
2. The skill's frontmatter `description` now names `tasks/<작업 ID>.md` and adds
   "새 작업의 ID와 명세 파일을 정할 때" as a trigger. Without it the skill
   advertises the old `<기능>` paths it no longer uses. The harness re-read the
   description after the write, so the registered trigger is the new one.

## The spec changed under the implementation

`tasks/task-spec-identifiers.md`, `tasks/quality-env-setup.md` and
`tasks/template-history-cleanup.md` were all modified in this same checkout
while this implementation was in progress. I started from the `구현 대기`
version and found the revision when `git status` listed three files I had not
touched.

The revision was an improvement and inside the task's scope, so I re-read it and
implemented the revised version: the owner decision above, the retired-ID rule,
the 상태-field rule, the richer 관계 and 선행 작업 fields, and the 「영구 템플릿」
wording. Nothing was lost; I checked each added requirement into the table above.

**It is still the exact condition the new 5th bullet forbids** — "Claude가
검토하거나 구현하는 중인 명세는 본문과 경로를 그대로 둔다". Reporting it is not a
complaint: it is the first live instance of the problem this task exists to
prevent, and it cost a re-read plus one reversed edit. The rule now says what
should have happened: hold the change until Claude's step ends, or give it a new
ID. No blocking finding follows from it, and the two other specs were not part of
this work.

## Verification

| Stage | Command | Exit | Result |
|---|---|---|---|
| lint | `.venv/Scripts/python.exe -m ruff check .` | 0 | All checks passed |
| format | `.venv/Scripts/python.exe -m ruff format --check .` | 0 | 66 files already formatted |
| test | `.venv/Scripts/python.exe -m pytest -q` | 0 | 405 passed |

Run twice: once after the first pass, once after the revisions above. Identical
results both times.

- **No test was added.** The change is prose; it adds no executable code and no
  exit code. `tests/test_v2_templates.py::test_router_targets_have_templates`
  reads `CLAUDE.md` and still passes with the added row.
- **The Fast gate does not apply.** `quality.tracked_paths` is `src/`, `tests/`,
  `pyproject.toml`, `.claude/harness.json`; none of the three changed files sits
  under those prefixes, so Full was run directly, as above.
- **Not verified:** that Codex actually adopts the ID rule when writing the next
  spec. That is behavior, not a file property, and no check here can assert it.

## History judgement

Ran `history-significance` over three candidates, twice.

**At step 7 (implementation): none recorded.** The ID rules are reconstructible
from the diff and the spec; the owner decision and the mid-implementation
incident both had their rules already captured in the permanent `SKILL.md`, and
their reasoning still sat in two files that existed. Default on an ambiguous
call is not to record.

**At step 9 (preservation): two recorded**, because the files holding that
reasoning are now slated for deletion, which is the moment it would be lost.

| Record | Why |
|---|---|
| `history/plan/2026-11-19-task-spec-identifiers.md` | The ID decision with three options weighed, and the template-owner decision with Claude rejected. It also closes the two follow-up conditions the 2026-11-18 entry left open — `tasks/` tracking and the template's owner — and narrows that entry's 「제자리 수정」 line |
| `history/task/2026-11-19-spec-changed-mid-implementation.md` | The concurrent-edit incident: cause, the reversed edit, and why no blocking gate was added for it |

*The ID rules themselves* are still not recorded as such — that part is ordinary
implementation, and the diff carries it.

Neither record duplicates `SKILL.md`. The rules live there; History holds only
the rejected alternatives and the cause.

## Step 8: Codex approved

Codex recorded its final review in the spec itself on 2026-11-19: **승인,
해결되지 않은 blocking finding 없음, Step 8 완료.** It reviewed against
`438dc3ca132d729c1de4af17f67ce2e8e285756b`, this spec's done criteria, and this
report, checked all six criteria off, and confirmed that the implementation did
not modify, rename or delete any other task's spec.

Three things in that verdict are worth keeping here, since the spec it was
written in is being deleted:

- It agrees with the **Codex** owner decision for `tasks/_template.md`.
- It accepts the mid-implementation finding as valid, states that the change was
  Codex's own, and resolves it to the record rather than to an unmet criterion.
- It did **not** re-run the Full profile. It verified documents and the diff and
  took the lint/format/405-passed result from this report. So the only execution
  evidence for this task is the two runs recorded above, both mine.

## Step 9: preserved and cleaned up

The three cleanup preconditions, re-checked after the approval:

| Precondition | State |
|---|---|
| Done criteria met, checks accounted for, no unresolved blocking finding in Codex's final review | Satisfied by the approval above |
| Current contract summarized in its owner document; decisions follow the Plan History procedure | Satisfied. The contract *is* `.claude/skills/handoff/SKILL.md`, the owner document for repeatable procedures per `AGENTS.md:53` and the new `CLAUDE.md` row. Two History records, above |
| Latest contents of both temporary files in a verified Git commit | Satisfied: `438dc3c` holds the implementation, and the approval commit holds this file and the spec in their final state |

Both temporary files were then removed, the way `07bd76e` removed the hook
task's pair. They are readable in the commits named above.

I never set the spec's 상태 myself. The rule installed by this very task puts
that field in Codex's hands — 「명세의 상태 표기는 Claude에게 명세를 고칠 권한을 주지
않는다」 — so Codex wrote 「구현 완료 · Codex 최종 리뷰 승인」 and completion is
recorded here, in the file that is mine.

## Remaining

1. **F7** — Round 3 of `handoff.review.md` still has no task ID. Unchanged by
   this work; it is Codex's to spec retroactively or to close as recorded.
2. **`.claude/skills/handoff/SKILL.md` has no named owner** in its own ownership
   row, as noted above.
3. The Ruff `I` / `RUF100` adoption decision, the template History cleanup
   (`tasks/template-history-cleanup.md`), and Codex's final review of
   `tasks/handoff.md` are untouched by this task and stay open.
4. `tasks/quality-env-setup.md` and `tasks/template-history-cleanup.md` are
   Codex's uncommitted status refreshes to other tasks' specs. Left alone: not
   this task's files, and not deleted, so nothing is lost by leaving them in the
   working tree.
