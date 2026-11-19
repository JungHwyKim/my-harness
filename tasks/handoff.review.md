# handoff.md — review and implementation report

Date: 2026-11-18. Reviewed against the working tree at branch `release/v2`, no
commits made.

Status: revised proposal reviewed, no blocking conflict found, workflow
installed. Verification is partial — see Verification.

## Review: conflicts

**Verdict: no blocking conflict.** The revised proposal and
[hook-dicision.md](hook-dicision.md) partition cleanly. The hook task owns
`paid_test_check.py`, `.claude/harness.json`, `harness.schema.json`,
`tests/_escape_hatches.py`, `tests/test_paid_test_check.py` and
`.codex/hooks.json`; this installation touches `CLAUDE.md`, `AGENTS.md` and two
new documents. No file appears in both scopes.

Four non-blocking findings. None of them stopped the installation.

### F1. `tasks/` is untracked, so two "kept" artifacts have no preservation path

`git status --short` reports `?? tasks/` — the folder has never been committed,
and `.gitignore` does not exclude it, so this is an unmade decision rather than
a policy. Two consequences for the proposal's own rules:

- `tasks/_template.md` has lifetime "kept" (proposal line 29) but sits in an
  untracked folder. The proposal itself states that an untracked file is not a
  recoverable revision history (line 37-38).
- The cleanup precondition "the latest contents of both temporary files exist in
  a verified Git commit" (line 141-143) can never be satisfied for any task
  while `tasks/` stays untracked, which forces every task onto the preservation
  alternative.

Suggested correction: commit `tasks/_template.md` with the workflow. Whether the
in-flight spec and review files are also tracked is a separate decision, and the
proposal reads correctly either way once it is made.

### F2. `tasks/_template.md` has no owner

Proposal line 29 gives its owner as "maintained with the workflow", while every
other row names Codex or Claude. Since the template constrains what Codex
writes, and Claude is the one installing it, the ambiguity will surface the first
time the template needs a change. Suggest naming one owner explicitly.

### F3. Filename typo in the linked document

`tasks/hook-dicision.md` should be `hook-decision.md`. Proposal line 19 links to
the current spelling, so renaming requires editing both. Left alone — `tasks/`
specs are Codex's to rename.

### F4. `CLAUDE.md`'s Information Ownership does not list `.claude/skills/`

`AGENTS.md:49` routes repeatable procedures to `.claude/skills/`, but the
equivalent list in `CLAUDE.md` has no such row. The new route works regardless,
so this is cosmetic, but the two ownership lists now differ by one entry.

## Implementation

| File | Change |
|---|---|
| `.claude/skills/handoff/SKILL.md` | new, Korean, 117 lines — the single source for the procedure |
| `tasks/_template.md` | new, Korean, 66 lines — the spec template |
| `CLAUDE.md` | `## 작업 인수인계` added after Context Router, 1 route line |
| `AGENTS.md` | `## 작업 인수인계` added after 품질 검증, 1 route line |
| `.claude/wiki/history/plan/2026-11-18-handoff-workflow.md` | new, Korean — Plan History entry for the decisions this workflow settled |

The skill carries the ownership table, the language rule, the nine-step
workflow, the review/repair/model-escalation policy with its decision table and
counting rule, the completion and cleanup preconditions, and the exclusion of
hook work. Both entry-point blocks are the exact text from the proposal
(lines 182-194); neither duplicates the procedure.

**Deviations from the spec: none.** The escalation policy names model tiers
(Sonnet, Opus) without versions or prices, per proposal lines 91-92.

## Verification

### Performed

| Check | Result |
|---|---|
| `AGENTS.md` under its 120-line limit | 57 lines — pass |
| Local routes resolve | `.claude/skills/handoff/SKILL.md`, `tasks/_template.md`, `.claude/wiki/knowledge/`, `.claude/wiki/history/plan/`, `.claude/harness.json`, `.claude/skills/plan-log/SKILL.md` — all present |
| New skill is registered by the harness | the session's skill list picked up `handoff` with its description after the file was written |
| Read-through of the full sequence | design → review → revision → implementation → report → result review → preservation → cleanup is continuous; cleanup requires all three preconditions, so an untracked, unpreserved task cannot be deleted as completed work |
| History judgement | ran `history-significance`; four decisions rejected named alternatives, so `plan-log` recorded them. The installation itself was not recorded — it is reconstructible from the diff |

### Not performed, and why

**The Full Quality Profile could not run in this environment.** Neither `ruff`
nor `pytest` is installed for any interpreter found here:

```
python -m ruff check .          -> No module named ruff      (Python 3.12)
python -m ruff format --check . -> No module named ruff      (Python 3.12)
python -m pytest tests -q       -> No module named pytest    (Python 3.12)
py -3.11 -m pytest --version    -> No module named pytest
pyenv 3.11.9 python -m pytest   -> No module named pytest
ruff --version                  -> command not found
```

`.claude/harness.json` sets `python` to `.venv/Scripts/python.exe`, which does
not exist in this checkout, so `_hookutil.venv_python()` falls back to
`sys.executable` — the Python 3.12 above. Creating `.venv` and installing
`pytest` and `ruff` into it makes both profiles runnable; until then the
configured interpreter is silently substituted, which is the warning case
`tasks/doctor.md` item 4 describes.

**The Fast gate does not apply to this change by design.**
`quality.tracked_paths` is `src/`, `tests/`, `pyproject.toml`,
`.claude/harness.json`. None of the four changed files is under those prefixes,
so `auto_test_check.py` correctly treats this as out of scope. This reason is
independent of the missing interpreter: even with a working `.venv`, a
prose-only change here triggers no scoped tests.

**No test was added.** This change introduces no executable code. The one
mechanically checkable property — that every path named in the entry files and
the skill resolves — is verified above by inspection, not by a test. If that
property is worth locking, it belongs with the route checks that
`tasks/doctor.md` already specifies rather than in a test written here.

## Remaining

1. Resolve F1 before the first task reaches cleanup. Nothing can satisfy the
   Git-commit precondition while `tasks/` is untracked.
2. Resolve F2 — name an owner for `tasks/_template.md`.
3. Install `pytest` and `ruff` into `.venv`, then run the Full profile and
   append the result here. Until then no quality profile has been executed for
   this change.
4. F3 and F4 are cosmetic and need no action for this task.
5. This proposal and its review stay in `tasks/` until the final review and the
   preservation conditions are satisfied.

---

# Round 2 — verification environment

Date: 2026-11-18. Checkout `release/v2` at `4f5300c`, which matches the baseline
the spec states. Round-1 changes were already in the working tree, uncommitted:
`AGENTS.md` and `CLAUDE.md` modified; `.claude/skills/handoff/`, the plan-log
entry and `tasks/` untracked. No commits made in this round either.

All five of the spec's code citations resolve exactly: `harness.json:4`
(`python`), `:14` (tracked paths), `:41`/`:46`/`:51` (the three Full stages),
`.gitignore` with four entries and no `.venv/`, and the README test command.

This section supersedes round 1's "the Full Quality Profile could not run" item.
It can run now, and it fails — see below.

## Changed files

| File | Change |
|---|---|
| `.venv/` | new, Python 3.12.5; `sys.executable` confirmed inside it |
| `requirements.txt` | new, ASCII-only, pins `pytest==9.2.0` and `ruff==0.17.5` |
| `.gitignore` | `.venv/` appended; the four existing entries untouched |
| `README.md` | 검증과 주의 사항 now carries venv creation, requirements install, and the three Full commands |

## Environment result

| Check | Result |
|---|---|
| `.venv/Scripts/python.exe` exists, `sys.executable` points into the venv | pass |
| install from `requirements.txt` | exit 0 |
| `pip check` | exit 0, "No broken requirements found." |
| `git check-ignore -v .venv/Scripts/python.exe` | matched by `.gitignore:5:.venv/` |
| `requirements.txt`, `README.md` not ignored | pass |

Versions were read from the installed packages, not copied from a global
`pip freeze`.

## Deviation: `requirements.txt` has to be ASCII

The first version carried Korean comments and `pip install -r` died with
`UnicodeDecodeError: 'cp949' codec can't decode byte 0xec`. The second still
failed on a single em-dash (`0xe2`). The third is ASCII-only, verified byte-wise.
pip 24.2 decodes a requirements file with the locale encoding, so any non-ASCII
byte breaks installation on a cp949 shell. The Korean setup instructions went
into `README.md` instead, and the file's own comment says why it stays ASCII.

This is a deliberate exception to the Korean-prose rule, taken for a
machine-read manifest. Worth noting that the spec's own "reinstall from the
pinned file" step is what caught it — the first install took the package names
from the command line and never read the file.

## Full Quality Profile — all three stages ran, all three failed

| Stage | Command | Exit | Result |
|---|---|---|---|
| lint | `.venv/Scripts/python.exe -m ruff check .` | 1 | 11 errors: `PLW1510`×6, `I001`×3, `FURB167`×1, `RUF100`×1; 5 auto-fixable |
| format | `.venv/Scripts/python.exe -m ruff format --check .` | 1 | 23 files would be reformatted, 49 already formatted |
| test | `.venv/Scripts/python.exe -m pytest -q` | 1 | 14 failed, 321 passed in 11.28s |

**Nothing was fixed.** Per the spec's scope the repository was not auto-formatted
and no rule was relaxed. Environment setup succeeded; Full verification did not.
The two are reported separately on purpose.

The lint rule set is reproducible: `ruff check . --isolated` returns the
identical 11 errors, and no `ruff.toml`, `.ruff.toml` or `pyproject.toml` exists
in the repo, at `C:\`, in `%APPDATA%\ruff` or in `~/.config/ruff`. So these are
ruff 0.17.5's own defaults, which the pin now fixes in place.

### The 14 test failures predate this task

All 14 are in `tests/test_paid_test_check.py`. The cause is established, not
suspected:

- `.claude/harness.json:63` sets `"pytest_markers": []`.
- `.claude/harness/hooks/paid_test_check.py:258-259` is `if not _PAID_MARKERS:
  return` — with no markers configured the hook returns without emitting a
  decision at all.
- `tests/test_paid_test_check.py:66-68` calls `paid_test_check.blocked_reason()`
  directly against **this repository's** configuration and asserts a non-`None`
  result for the 12 commands in its `BLOCKED` list (`:28-45`).

Direct probe in the venv: `_policy()` returns `((), <reason>,
'ALLOW_PAID_TESTS')` and `blocked_reason("pytest -m integration")` returns
`None`. That accounts for 12 parametrized failures; `test_deny_payload_shape`
and `test_bom_prefixed_input_is_still_judged` make 14, and both fail inside
`json.loads("")` because the hook writes nothing to stdout.

Three candidate causes ruled out:

- **Not `.venv`.** `paid_test_check.py` contains no reference to `venv_python`
  or `sys.executable`, so creating the virtualenv cannot change its judgement.
- **Not the pytest version.** Installed `pytest==9.1.1` — matching the
  cpython-311 bytecode left in `tests/__pycache__` — and got the identical 14
  failures, then restored 9.2.0.
- **Not this task's files.** None of them is imported by the hook or its test.
  `tests/test_v2_templates.py`, which does read `CLAUDE.md`, passes.

These tests were written for a project that defines paid markers — the `BLOCKED`
list still contains the literal path `C:\agentic-rag-proj\.venv\...`. V2 moved
the marker list into project configuration and the template leaves it empty, so
the suite now asserts a detection this repository's own config switches off.

Owned by [hook-dicision.md](hook-dicision.md); reported, not fixed. **That task
needs to know the suite is already red before it rewrites this hook, otherwise
it cannot tell its own regressions from this.** Its own evidence already notes
the empty marker list, but not that the test suite asserts the opposite.

### Not verified

- Linux paths and CI compatibility. This was a Windows local environment only.
- Whether the lint and format findings should be fixed or configured away. Out
  of this task's scope; no existing virtualenv was removed and no global package
  was changed.

## Remaining (updated)

1. **F1** — `tasks/` still untracked. Unchanged.
2. **F2** — `tasks/_template.md` still has no named owner. Unchanged.
3. ~~Install `pytest` and `ruff`~~ — done. Full runs now.
4. **F5 (new)** — lint and format are red at HEAD: 11 ruff errors and 23
   unformatted files, none of them introduced here. Needs a decision: fix the
   findings, or add a `ruff.toml` that states which rules this repo adopts. A
   repo whose Full gate cannot pass will train people to skip the gate.
5. **F6 (new)** — the 14 failing tests belong to the hook task, with the cause
   and evidence above. Either the template defines a marker, or those tests stop
   asserting detection against the template's own empty config.
6. **F3**, **F4** — cosmetic, no action needed for this task.

---

# Round 3 — gate repairs (user-directed, no spec ID)

Date: 2026-11-18. **This round had no spec**: the user asked for it directly
after Round 2 surfaced F5 and a new Fast-gate defect. Under
`tasks/task-spec-identifiers.md` it should have carried its own task ID, so it
is recorded here with the findings it acts on rather than in a review file for a
spec that does not exist. Codex may spec it retroactively.

## Two defects fixed

**1. Fast gate fed `.pyc` files to pytest (new, found in Round 3).**
Symptom: every tool call ended with `exit status: 4`, pytest given 15
`tests/__pycache__/*.pyc` paths. Root cause, traced rather than guessed:

- `auto_test_check.py:258` calls `_hookutil.tracked_paths_newer_than()`, a
  **filesystem mtime scan**, not git. `changed_paths()` (git) is immune because
  `.gitignore` excludes `__pycache__/`; this scanner had no such filter, so the
  `.pyc` files my own pytest runs created counted as changed files.
- `test_target_for()` then accepted them: its `.py` extension guard
  (`auto_test_check.py:155`) applies **only when not V2**, because V2 must let
  non-`.py` paths such as `pyproject.toml` reach the mapping table. The
  `tests/` branch only checked that the basename starts with `test_`, which
  `test_characters.cpython-312-pytest-9.2.0.pyc` does.

This was also **self-sustaining**: running pytest rewrote the `.pyc` files, which
made the next tool call see changes, which ran the gate, which ran pytest again.

Fixed in two places. `_hookutil._ARTIFACT_DIRS` now excludes `__pycache__`,
`.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.venv`, `node_modules` and
`.git` from both `paths_newer_than()` and `tracked_paths_newer_than()` — an
enumerated set, for the reason this repo gives for its other exception sets:
missing an entry only fails to filter, it never filters wrongly. `.gitignore` is
deliberately not parsed, since a project may ignore build output or data that a
person did edit. The `.py` guard in `test_target_for()`'s `tests/` branch is the
second line of defence.

Regression tests: `tests/test_hookutil.py` gained
`test_artifact_dirs_are_not_changed_files` and
`test_artifact_dirs_are_excluded_from_py_scan` (both scanners, because fixing
one and not the other is the failure mode `_hookutil` exists to prevent);
`tests/test_auto_test_check.py` gained
`test_non_python_under_tests_is_not_a_target` with four cases.

**2. F5 — lint and format were red at HEAD.**
Handled by declaring the standard rather than editing code to chase a default:

- New `ruff.toml` sets `select = ["E4", "E7", "E9", "F"]`, Ruff's own documented
  default. Verified: `ruff check . --isolated --select E4,E7,E9,F` was already
  exit 0, while `--isolated` alone produced the 11 errors. The repo had no Ruff
  config at all, so the gate was enforcing whatever rules Ruff 0.17.5 happens to
  ship; the 11 findings were never a standard this project chose. Pinning the
  selection means a Ruff upgrade cannot silently add rules.
- `line-length = 100`, chosen empirically. Ruff's formatter measures **display
  width**, and Korean counts two columns per character: only 9 lines in 33 `.py`
  files exceed 100 *characters*, but the widest is 113 columns. At Ruff's default
  88, every one-line Korean exception message gets split. Raising it is not the
  answer either — offenders went 23 (88) → 16 (100) → 18 (110) → 20 (120/130) →
  21 (140), because past some width the formatter starts rejoining lines the
  author deliberately split. **No width makes the existing code compliant**, so
  100 is the minimum-churn choice and the 16 files were formatted once to adopt
  it.

## Verification

| Stage | Command | Exit | Result |
|---|---|---|---|
| lint | `ruff check .` | **0** | All checks passed |
| format | `ruff format --check .` | **0** | 75 files already formatted |
| test | `pytest -q` | 1 | **14 failed, 327 passed** (was 14 / 321; the 6 new tests pass) |

The Fast gate confirmed its own fix: its next run passed real `.py` paths
(`tests/test_auto_test_check.py tests/test_collect_openwork.py …`) with no
`.pyc` among them.

Changed: `ruff.toml` (new), `.claude/harness/hooks/_hookutil.py`,
`.claude/harness/hooks/auto_test_check.py`, `tests/test_hookutil.py`,
`tests/test_auto_test_check.py`, plus 16 files touched by the one-time format
pass. Hook sources sit outside `quality.tracked_paths`, so the Fast gate does
not cover them automatically; Full was run directly, as above.

## The 14 failures were left alone, deliberately

They are F6, and `tasks/hook-dicision.md` item 6 already contains line-level
plans for `tests/test_paid_test_check.py`. Editing it here would be the exact
collision `tasks/task-spec-identifiers.md` was written to prevent — *"같은 구현
파일을 바꾸는 후속 작업은 선행 작업이 끝난 뒤 수행한다."* The other available fix,
adding a marker to the template's `checks.expensive_tests.pytest_markers`, is
ruled out by `hook-dicision.md`'s own decision not to hardcode markers in the
template. So the Full gate still fails on pytest, and every turn still ends red
until that task runs.

## New: the format pass shifted lines `hook-dicision.md` cites

`paid_test_check.py` and `tests/test_paid_test_check.py` were both reformatted
(net −2 and +2 lines). Spot-checked: that spec's citations into the test file
still resolve (`:110-112` is still `test_escape_hatch`), but its citations into
`paid_test_check.py` are now off by up to two lines — `:253-256`, claimed as the
environment-variable bypass, now lands on the tail of that block and
`if not _PAID_MARKERS:`. The content is all still present; only the numbers
moved. The spec template already requires rechecking evidence against the
current files before relying on it, so this is a re-read, not a rewrite.

## Remaining after Round 3

1. **F1**, **F2** — unchanged.
2. **F5** — closed. Lint and format are green and the adopted rules are declared.
3. **F6** — open, owned by `tasks/hook-dicision.md`. It is specced and its
   prerequisite (this environment work) is done, so it can run next.
4. **F7 (new)** — this round had no task ID, contrary to
   `tasks/task-spec-identifiers.md`, which itself is still 구현 대기 and now
   unblocked.
5. Adding `I` (import sorting) and `RUF100` to the Ruff selection costs four
   auto-fixes and is a separate, deliberate decision.
