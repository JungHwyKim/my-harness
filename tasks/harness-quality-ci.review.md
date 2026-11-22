# Harness quality/CI spec review (pre-implementation)

- Task ID: `harness-quality-ci`
- Spec: `tasks/harness-quality-ci.md` (untracked working-tree file)
- Reviewer: Claude Code (Opus 5)
- Date / revision: 2026-11-22 · `C:\my-harness`, `main` / `675b461`, working tree has only the three
  untracked `tasks/*.md` specs
- Stage: procedure step 3 (spec reviewed against current code). No implementation started; the only file
  I created is this review.

## Scope of this review

Read in full: `tasks/harness-quality-ci.md`, `.claude/skills/handoff/SKILL.md`, `.claude/harness.json`,
`.claude/settings.json`, `.claude/harness/hooks/_hookutil.py`, `.claude/harness/hooks/_quality.py`,
`.claude/harness/hooks/auto_test_check.py`, `.claude/harness/schemas/harness.schema.json`,
`tests/conftest.py`, `tests/test_hook_wiring.py`, `tests/test_v2_templates.py`,
`tests/_escape_hatches.py`, `.claude/wiki/knowledge/quality-env.md`. Read the relevant regions of
`doctor.py` (`resolve_root`, `chosen_python`, `check_python`, `check_mapping`, `check_scaffold`,
`_target_for`, `_check_executable`), `tests/test_doctor.py` (sections 7 and 8),
`history_check.py`, `README.md`, `.claude/wiki/knowledge/doctor.md`, and
`tasks/template-core-packs.md` where it touches this task.

Measured on this machine at `675b461`, with the configured interpreter:

| Probe | Result |
|---|---|
| `pytest -q` | **651 passed, 1 skipped** in 20.97 s / 16.92 s / 15.80 s (three runs) |
| `pytest -q` with `CLAUDE_PROJECT_DIR=C:\my-harness` | 651 passed, 1 skipped — no test depends on the variable being unset |
| `pytest tests/ tests/test_v2_templates.py -q` | 651 passed — pytest de-duplicates an overlapping dir + file target, so `{mapped_targets}` collapsing to both is harmless |
| `doctor.py` on this repo | PASS 24 · WARN 5 · FAIL 0, exit 0 |
| `doctor.py` with `python` removed, `.venv` present | PASS 23 · **WARN 6** · FAIL 0, exit 0 — see C-01 |
| `pytest tests/test_new.py` on a file with no test functions | **exit 5** — see C-06 |
| Python / tools | Python 3.12.5, `pytest==9.2.0`, `ruff==0.17.5` |

Probes ran in the session scratchpad (a copy of `.claude/` plus the root docs) and in one temp directory.
The real checkout was not modified.

## Every citation in the spec checks out

All of `## 기존 코드 근거` is accurate at `675b461`:

| Spec citation | Verified |
|---|---|
| `.claude/harness.json:14` quality tracking is `src/`, `tests/`, `pyproject.toml`, one config file | correct |
| `:17` the only mapping is `src/` → `tests/`, and no `src/` exists | correct (`git ls-files` has no `src/`) |
| `:32` Fast treats exit 5 as success | correct |
| `auto_test_check.py:67` reads `quality.tracked_paths`, falling back to `source_prefixes` | correct |
| `:108` mappings come from config, V2 and V1 sections apart | correct |
| `:156` `test_target_for()` narrows a direct test file but returns `None` for `tests/conftest.py` **before** consulting the mapping table | correct — the `tests/` branch at `:167`-`:177` returns ahead of the prefix loop at `:179` |
| `_quality.py:94` a missing profile yields an empty stage list | correct (`profile_config()` → `None` → `return ()`) |
| `:169` an empty list placeholder skips the stage | correct — `_expand_argv` returns `None` at `:186`, `run_stage` returns `ok=True, skipped=True` at `:213` |
| `:256` `run_profile` is the shared engine and breaks on the first failure | correct (`:270`-`:271`) |
| `_hookutil.py:181` order is configured path → Windows venv → POSIX venv → current interpreter | correct |
| `tests/conftest.py:81` the marker store is redirected to a temp dir | correct (`_isolate_plugin_data`, autouse) |
| `.github/` has no tracked file | correct (`git ls-files .github` is empty; no such directory exists) |

Two of the spec's judgments are not just correct but load-bearing, and should not be softened:

- **The gap in 목적 is real and Doctor already says so out loud.** Today `.claude/harness.json` is tracked,
  has no mapping, and is not in `unmapped_by_design`, so an edit to it produces `changed_files` with no
  target, the Fast stage is skipped, and the hook returns silently. Doctor's own D-MAPPING WARN on this
  repo states it verbatim: `이 파일만 고친 변경에서는 stage 가 건너뛰어지고 성공으로 보고됩니다`.
  `.claude/harness/` is not even tracked.
- **Reusing `test_target_for()` instead of re-deriving Fast targets is the right call**, for the reason
  `_hookutil.py:7`-`:13` gives about duplicated logic. C-04 and C-05 below are about making that reuse
  complete, not about reversing it.

## Blocking findings

### C-01 · P1 · removing the `python` key turns D-PYTHON into a permanent, nonsensical WARN

**Location** — spec `### 호환성` (`설정의 python 키는 제거해 두 OS가 각자의 .venv를 쓰게 한다`), against
`doctor.py:1722` `check_python` and `:1704` `chosen_python`. Collides with
`### 심각도와 종료 코드` (`이 저장소에서 설정 누락·매핑 누락으로 생긴 WARN은 해결하고`).

**Evidence** — measured, with the key removed and a `.venv/Scripts/python.exe` in place:

```text
[WARN] D-PYTHON  .claude/harness.json: python — 설정한 None 가 없어 .venv/Scripts/python.exe 로
대체됩니다 (Doctor 의 루트 기준 선택). 검사가 통과해도 지정한 환경에서 돌았다고 볼 수 없습니다.
    고치는 법: 환경을 None 에 만들거나 python 값을 .venv/Scripts/python.exe 로 고친다.
```

`chosen_python` returns `source == ".venv/Scripts/python.exe"`, which is not `"python"`, so
`check_python` takes its middle branch — written for "the configured path is missing" — and interpolates
`configured`, which is `None`. The fix line instructs the reader to create an environment at `None`.

**Why this blocks** — the spec removes the key *and* requires that config-omission WARNs be resolved, but
`### 호환성` permits touching Doctor's cloned branch only `소비자를 바꾼 경우에만`, and the consumer
(`_hookutil.venv_python()`) is not changing. As written the spec forbids the fix it also demands, and the
implementer has no legitimate move. This is not repo-local cosmetics either: `python` is optional in the
schema (`harness.schema.json` has it under `properties`, not `required`), so every deployed copy that
omits it gets the same message.

**Expected behavior** — with no `python` key and a `.venv` interpreter found, D-PYTHON is PASS, naming the
interpreter it found and stating that the choice is OS-dependent. The "configured path is missing" wording
fires only when a `python` value actually exists and is absent.

**Verification criteria** — a test asserts that for a config without `python` and with a `.venv`
interpreter present, D-PYTHON is PASS and the message contains no `None`; the existing
`test_python_choice_matches_hookutil` / `test_python_fallback_order_matches_hookutil` cross-checks keep
passing. Add `check_python` to 범위와 제외's 포함 list.

### C-02 · P1 · the Full profile's test timeout is not shorter than the Stop hook budget, and no test covers V2 stage timeouts

**Location** — `.claude/harness.json:52` (`full` → `test` → `timeout: 600`) against
`.claude/settings.json:136`-`:137` (Stop → `auto_test_check.py`, `timeout: 600`), and
`tests/test_hook_wiring.py:175` `test_internal_timeout_fits_in_hook_budget`.

**Evidence** — the budget test asserts `inner < outer`, but `_TIMEOUT_BUDGETS` (`:62`) enumerates **module
constants** only: `SCOPED_TIMEOUT_SEC` (90) and `FULL_TIMEOUT_SEC` (540) for `auto_test_check.py`, plus
three for `pre_commit_check.py`. The V2 path never reads those constants — it reads the stage `timeout`
values out of `.claude/harness.json` through `_quality.load_profile()`. So:

- The V2 `full` test stage gets 600 s against a 600 s kill. The repo's own rule in that file is explicit:
  `합이 아니라 최댓값으로 잰다`, and `안쪽이 더 짧아야 한다`. 600 is not shorter than 600. V1 chose
  540 deliberately for exactly this headroom.
- Worst case wall time for `full` is 120 + 120 + 600 = 840 s before the engine would report anything,
  against the same 600 s kill.
- `test_internal_timeout_fits_in_hook_budget` is green for `auto_test_check.py`/`Stop` by checking a
  constant that the V2 branch does not use. That is the "검사가 꺼진 채로 통과" shape this repo keeps
  hunting, in the test suite rather than in a hook.

`pre_commit` is fine: its budget is 900 (`settings.json:20`) and the max stage is 600.

**Why this blocks** — the spec's own mapping table gives `.claude/settings.json` the reason
`배선과 timeout 계약을 검증한다`, and 구현 범위 1 rewrites `.claude/harness.json`. The timeout contract
the table claims to verify is currently unverified and, at the binding comparison, violated. Shipping a
rewritten config without closing this leaves the table's stated justification untrue.

**Expected behavior** — `full`'s test stage timeout is strictly less than the Stop budget (540 keeps V1's
60 s margin), or the Stop budget rises above the chosen value; and the budget coverage test reads V2 stage
timeouts from the config so a future profile edit cannot reopen it.

**Verification criteria** — a test that, for each `(script, event)` wired to a V2 profile, asserts
`max(stage.timeout) < settings.timeout`, failing on the current 600/600 pair before the fix.

### C-03 · P1 · the hook keeps passing silently on a tracked change with no target; only the manual CLI gets the ERROR rule

**Location** — 구현 범위 4 and the severity table row `추적 파일인데 매핑도 제외 이유도 없음 → ERROR / 2`,
against `auto_test_check.py:281` `_handle_v2_post_tool_use`. Completion criterion 1 is
`훅·스크립트·공유 설정 변경이 Fast의 실제 테스트 호출로 이어진다. 누락 시 실행 기록이 없다`.

**Evidence** — the hook computes `changed_files`, derives `targets`, and hands both to `run_profile`.
When `targets` is empty and `changed_files` is not, `_expand_argv` returns `None` (`_quality.py:186`),
`run_stage` returns `ok=True, skipped=True` (`:213`), `failure` is `None` (`:298`), and the hook returns
with nothing printed. That is today's hole, unchanged. The spec puts the ERROR rule only in
`run_quality.py`, a command nobody is obliged to run.

The proposed mapping table does close the hole *for the paths it lists*, by configuration. Nothing keeps
it closed: the next tracked path added without a mapping reopens it, in the one place where the gate
actually fires on every edit. 완료 기준 1 would then be satisfied only by whoever remembers to run the CLI.

**Why this blocks** — 목적's first sentence is about the hook, and the fix as specified lands everywhere
except the hook.

**Expected behavior** — the Fast hook path distinguishes two cases: every changed file is intentionally
excluded (stay silent), versus a tracked change has no target and no documented exclusion (report once,
naming the path and the two legitimate fixes).

**Caution, and why this is a scope question for you** — this must not become a per-edit block. A gate that
blocks forever trains `SKIP_AUTOTEST=1`, which is the failure mode recorded at `_hookutil.py:114`-`:118`
and the reason `tests/_escape_hatches.py` exists. Use `claim_session` (one report per session, as the Stop
gate does) or a non-blocking notice. Either way this adds hook behavior beyond 구현 범위's enumerated
list, so widening the scope is your call rather than the implementer's.

**Verification criteria** — a temp-project test driving a real `PostToolUse` payload for a tracked path
with no mapping, asserting the report appears; and a second with the path in `unmapped_by_design`,
asserting silence.

### C-04 · P1 · `test_target_for()` returning `None` conflates four causes, and the two-way severity table cannot separate them

**Location** — `### 심각도와 종료 코드`, rows four and five, against `auto_test_check.py:156`-`:185`.

**Evidence** — `None` comes back for four distinct reasons:

| Cause | Code | Correct verdict |
|---|---|---|
| (a) path resolves outside the repo | `:157` via `relative_to_root` | usage error |
| (b) `unmapped_by_design` hit | `:162` | SKIP / 0, with the recorded reason |
| (c) under `tests/` but not a `.py`, or a `.py` that is not `test_*` | `:167`-`:177` | **no row in the table** |
| (d) no mapping prefix matches | `:179`-`:185` | ERROR / 2 |

Case (c) is the problem. After 구현 범위 3 the "not `test_*`" half becomes `tests/`, but the non-`.py` half
still returns `None`, and the table would classify it ERROR / 2 — a hard failure for a perfectly ordinary
file. `tests/` holds only `.py` files plus `__pycache__` today, so this is latent rather than live, but
`tests/__pycache__/*.pyc` exists right now and `_hookutil._ARTIFACT_DIRS` (`:435`) is already the
canonical answer for it; the CLI should reuse it rather than re-deriving one. Case (a) likewise deserves a
usage error, not "missing mapping".

A second, smaller gap in the same place: `### 실행 계약` names only `test_target_for()` for reuse, but the
CLI also needs the tracked-path predicate. That is `auto_test_check._matches_tracked` (`:80`), built from
module-level `QUALITY_TRACKED_PATHS` (`:77`) at import. If the CLI re-implements it, the two drift, which
is the duplication hazard this module was consolidated to avoid.

**Why this blocks** — the table is the CLI's normative contract, and the implementer cannot implement it
from `None` alone. As written it also produces a wrong verdict for a normal file.

**Expected behavior** — the CLI classifies the cause rather than reading a bare `None`, with one row per
cause; artifact directories and non-Python files under a tracked test directory are SKIP with the reason
printed, not ERROR. `_matches_tracked` is named in the reuse list (promote it to a public name if the
underscore is a barrier).

**Verification criteria** — a parametrised test over one input per cause, asserting the four exit codes.

### C-05 · P1 · `doctor._target_for` is a clone of `test_target_for`, change #3 desyncs it, and nothing cross-checks the two

**Location** — 구현 범위 3, against `doctor.py:1956` `_target_for`. `### 호환성` promises to touch only
Doctor's *python* branch, and only `소비자를 바꾼 경우에만`.

**Evidence** — `doctor._target_for` reproduces the `tests/` branch line for line, including
`return rel if name.startswith("test_") else None`. Change #3 edits the hook's copy and not Doctor's, so
afterwards Doctor answers "no target" for `tests/conftest.py` while the hook and the new CLI answer
`tests/`. `test_doctor.py`'s section 8 (`복제한 분기 대조`) cross-checks `wiki_root`/`history_prefix`,
the python choice, and entry normalization — but `_target_for` appears **nowhere** in `tests/` (grepped),
so no test would notice.

It gets worse rather than better from there: `check_mapping` only inspects tracked entries that are *files*
(`:1996`-`:2001` skips `/`-terminated entries and anything that is not `is_file()`), so the disagreement
never shows up in Doctor's output. CI will run Doctor and the CLI back to back on the same config, quietly
disagreeing about the same path.

**Why this blocks** — the repo's standing rule for cloned branches is that a test must compare them
(`doctor.py:1698`-`:1703` states it explicitly). Change #3 breaks a clone that has no comparison test.

**Expected behavior** — change #3 applied to both copies, plus a section-8 cross-check asserting
`doctor._target_for(p, rows, unmapped) == auto_test_check.test_target_for(p)` over a fixed path set:
`tests/test_doctor.py`, `tests/conftest.py`, `tests/_escape_hatches.py`, `tests/fixtures/a.json`,
`tests/__pycache__/x.pyc`, `.claude/harness/hooks/_quality.py`, `.claude/harness/scripts/doctor.py`,
`.claude/settings.json`.

**Verification criteria** — that test fails if either copy is changed alone.

## Non-blocking findings

### C-06 · P2 · `success_codes: [0]` does not surface the defect the spec names

Measured: a freshly created `tests/test_new.py` containing only a docstring gives pytest **exit 5**. With
the proposed mapping table, every tracked path except a direct `test_*.py` maps to `tests/`, which always
collects 651 tests — so exit 5 can only arise from a test file under construction, never from a mapping
defect. The mapping defect the spec wants visible (`매핑한 테스트가 0건`) is the *skip* path, which
`success_codes` never reaches, because the stage never runs.

Keeping `[0]` is still defensible, and the V1 rationale at `auto_test_check.py:53`-`:57` genuinely does not
apply here: it is about `pyproject`'s `addopts = "-m 'not integration'"` deselecting a whole file, and this
repo has no `pyproject.toml` and no addopts. Recommend keeping `[0]`, restating its reason accurately in
구현 범위 2 and `quality-env.md`, and making the Fast failure message name exit 5 explicitly — otherwise
the model is told `단계가 실패했습니다` when nothing ran, while scaffolding a test file.

### C-07 · P2 · Fast now runs the whole suite on every edit — price it in the spec

With `.claude/harness/` → `tests/`, every hook, script, or schema edit runs all 651 tests: measured
15.8–21.0 s per tool call on this machine. `auto_test_check.py:20`-`:22` is the measurement that justified
scoped runs in the first place, and this spec knowingly reverses it for the harness paths —
correctly, for a repo whose hooks, shared modules, and schema interlock. But
`정밀 매핑 최적화는 이 작업에 포함하지 않는다` should be a priced deferral, so put the number in the spec
and in `quality-env.md`'s 현재 확인된 상태. Related: the Fast stage's `timeout: 90` against a ~21 s suite
is the number that will bite first as the suite grows (the PostToolUse budget is 120).

### C-08 · P2 · `fail-fast: false` is a matrix key, so "두 job" and `strategy.fail-fast: false` do not fit together

`strategy.fail-fast` governs cancellation of the *other legs of a matrix*. Two independently declared jobs
never cancel each other — both already run to completion — so the key is either inert or a sign that a
matrix was intended. Recommend one job with `strategy.fail-fast: false` and
`strategy.matrix.os: [windows-latest, ubuntu-latest]`, `runs-on: ${{ matrix.os }}`: it delivers
`두 OS 결과를 모두 얻는다` by the documented mechanism and gives a natural home for
`venv 실행 파일은 OS별로 명시한다`. Fold this into the action-ref confirmation the spec already requires.

### C-09 · P2 · say which lever pins the CLI's target root

`_hookutil.PROJECT_ROOT` is computed at import (`:52`) from `CLAUDE_PROJECT_DIR` or cwd (`:41`), and
`_quality` imports `_hookutil`. So `임포트 전에 대상 루트와 환경을 고정한다` can only mean: resolve the
root from `__file__` the way `doctor.resolve_root()` does (`doctor.py:181`), set
`os.environ["CLAUDE_PROJECT_DIR"]` to it, put `<root>/.claude/harness/hooks` on `sys.path`, **then**
import. Worth naming, so nobody tries patching `PROJECT_ROOT` after import and leaves `CONFIG_PATH`
(`:55`), `WIKI_ROOT` (`:127`), and `HISTORY_PREFIXES` (`:149`) pointing elsewhere.

Measured, so the environment half is de-risked: the full suite passes with `CLAUDE_PROJECT_DIR` set to the
repo root, so child processes inheriting it through `child_env()` (`:214`) changes nothing here.

### C-10 · P2 · the spec does not say whether the CLI honors `SKIP_AUTOTEST`

The hook does (`auto_test_check.py:404`), and `tests/_escape_hatches.py` enumerates the eight `SKIP_*`
names with `test_no_stale_escape_hatch_names` keeping the list honest. A deliberate manual run and a CI
gate should not be defeatable by an exported variable. Recommend: the CLI ignores every `SKIP_*` name,
says so in its output, `quality-env.md` records it, and the workflow sets none of them.

### C-11 · P2 · PASS/FAIL/SKIP has no state for the stages after a failure

`run_profile` breaks on the first failure (`_quality.py:270`-`:271`), so later stages produce no
`StageResult` at all. With three labels, a failed `lint` leaves `format` and `test` simply unprinted, and
absence reads as success. Recommend a fourth state (미실행 / NOT RUN) listing the configured stages that
were never reached, plus a one-line "aborted here" note.

### C-12 · P2 · nothing verifies the "no markers, no History" contract

`### 실행 계약` asserts `History·세션 마커는 만들지 않는다`, but `## 구현 및 검증` has no check for it,
while `test_doctor.py` already sets the precedent for exactly this kind of claim
(`test_wired_hook_that_writes_when_run_is_not_run`, `test_stage_command_that_writes_when_run_is_not_run`).
Recommend a test that points `CLAUDE_PLUGIN_DATA` at a temp directory, runs the CLI against a temp
project, and asserts nothing appears under it.

### C-13 · P3 · state the interim template gap between this task and task 2

`.claude/harness.json` is currently both this repo's config and the new-project example:
`tests/test_v2_templates.py:1` calls itself `새 프로젝트용 V2 설정`, `README.md:60` lists the file as the
one a new project edits, and `template-deploy.md` treats it as deployed content. The split happens in
`tasks/template-core-packs.md:49` and `:67` — task 2. So between this task landing and that one, the repo
ships a config whose mappings point at the harness's own `tests/`, and that test's stated purpose is false.
The ordering is right; the interim state should be named in 범위와 제외 as accepted, and item 7 should
either include the `test_v2_templates.py` docstring and the `README.md:60` line or say explicitly that both
belong to task 2.

### C-14 · P3 · the doc rows that go stale, collected so none is missed

All inside the spec's scope: `quality-env.md:9` (the `python` key), `:11` (the silent-substitution warning
— once the key is gone, that substitution becomes the intended per-OS mechanism, so the paragraph's point
changes rather than disappearing), `:32` (`[0, 5]`), `:35`-`:36` (tracked paths and the single mapping),
`:58` (405 passed → 651 passed, 1 skipped); `doctor.md:238`-`:243` (`자동 추적 범위 밖이다`, already named
in item 7) and `:250`-`:252` (현재 확인된 상태 — the WARN count moves, and its
`71 files already formatted` is already 73 as of this review); `README.md:189` and `:198`-`:203`.

### C-15 · nit · show the repeated `--changed` form

`### 실행 계약`'s example passes `--changed` once while the prose says
`--changed는 프로젝트 상대 경로로 반복 지정한다`. Showing `--changed a --changed b` removes the ambiguity
about whether it takes a list.

## Open questions

### Q-1 — should `.github/workflows/` really sit in `quality.tracked_paths`?

Tracking it and recording the exclusion in `unmapped_by_design` matches the spec's intent, but it also
pulls workflow-only edits into the Stop/Full gate: `_v2_session_changes` (`auto_test_check.py:303`) fires
`full` for any tracked change, so editing a YAML file would run ruff plus the whole suite at session end.
Wanted, or should the exclusion live in `quality-env.md` prose with the path left untracked?

### Q-2 — does `history.tracked_paths` gaining `.claude/harness/` mean every hook edit owes a History assessment?

`history_check.py:69` `is_recordable` and `:124` read that list. 구현 범위 1 says not to expand the
obligation to all document edits, but `.claude/harness/` is where the bulk of this repo's changes land, so
the obligation grows a lot. Intended, or should `history.tracked_paths` stay narrower than
`quality.tracked_paths`?

### Q-3 — 3.12 only, or 3.12 plus a floor?

The CI choice of 3.12 matches the local environment (3.12.5), but nothing in the repo declares a minimum,
and `tests/__pycache__` still holds 3.11 artifacts from an earlier run. If 3.11 is meant to work, the
matrix should say so; if 3.12 is the floor, somewhere durable should state it.

## What I did not do

- No implementation, and no file changed outside this review. Probes ran against a scratchpad copy of
  `.claude/` and one temp directory.
- **Hosted CI: not run, and not runnable.** There is no workflow at `675b461` and no remote push in this
  review's scope. Everything above about the workflow is a reading of the spec, not a CI result.
- **Linux: not exercised at all.** I read the suite for platform assumptions — the only `sys.platform`
  branches are `test_doctor.py:1336` (POSIX-only, the one skip in the Windows run) and `:1350`
  (Windows-only), `:981` picks a path shape that cannot exist on the running OS, and the Windows-looking
  literals in `test_paid_test_check.py` and `test_heredoc_write_check.py` are string-parsing inputs rather
  than filesystem paths. `.gitattributes` pins the worktree to LF, so `ruff format --check` should see the
  same bytes on both OSes. That reads as portable, which is not the same as passing: treat the Linux leg as
  unverified until the workflow runs.
- I did not re-verify the GitHub Actions reference pages cited in the spec; C-08 rests on
  `strategy.fail-fast` being a matrix key, which the implementer should confirm alongside the action refs
  the spec already asks about.

## Round 1 recommendation (pre-implementation)

The design is sound and should go ahead: one engine behind both the hook and a manual CLI, the Fast target
table expressed as config with a `why` per row, deliberate separation of PASS / FAIL / SKIP / ERROR, and a
CLI that pins its own root instead of trusting cwd. Every code citation in the spec is accurate, and the
gap in 목적 is real — Doctor reports it on this repo today.

Please resolve **C-01 through C-05** in the spec before implementation starts. C-01 and C-05 are scope
corrections (`check_python`, `doctor._target_for`), C-02 and C-04 are contract corrections (the timeout
budget, the severity table's causes), and C-03 is the one genuine scope question: whether the hook — not
just the CLI — gets the "tracked change with no target" report. The remaining findings can be folded in as
you revise; none of them needs a decision from the user.

---

# Round 2 — review of the revised spec

- Date / revision: 2026-11-22 · `C:\my-harness`, `main` / `675b461`; `tasks/harness-quality-ci.md`
  revised in place (30433 bytes, mtime 21:13:35), source and config still unchanged.
- Stage: procedure step 4 completed by Codex, re-reviewed here. No implementation started.
- Ownership: Codex revised the spec only and left this file alone, as
  `SKILL.md`'s `Claude 소유의 .review.md는 대신 수정하지 않는다` requires. Confirmed three ways —
  the harness flagged only `harness-quality-ci.md` as changed on disk; this file's mtime (21:04:13)
  is nine minutes older than the spec's and matches its own directory-entry stamp; and its heading
  structure is byte-identical to what Round 1 wrote.

## Verdict

All fifteen findings and all three open questions are adopted, and two are strengthened past what I
asked for. **C-02** now checks the sequential sum rather than the maximum — which is the better rule,
because the per-stage maximum ignores the time the earlier stages already spent. **D-01**, Codex's own
addition, is correct and I had missed it: `doctor.py:2000` turns a bare `None` into a missing-mapping
warning, so Doctor needs the same cause split as the CLI, not just the `tests/` special case from C-05.

I verified the mechanics the revision now depends on. The arithmetic holds against the live wiring, and
the non-blocking notification is implementable with a two-site precedent in this repo. Three
implementation-level gaps remain, all narrow; none of them changes the design and none needs a decision
from the user.

## Confirmations

**The timeout table is arithmetically right against `settings.json` as it stands.**

| V2 path | Stages | `sum + 30` | Outer budget | Verdict |
|---|---|---|---|---|
| Fast / PostToolUse | 90 | 120 | 120 (`:99`, `:115` — both groups) | passes, exactly at the bound |
| Full / Stop | 120 + 120 + 540 | 810 | 900 (`:137`, raised from 600) | passes |
| Full / pre_commit | 120 + 120 + 540 | 810 | 900 (`:20`, unchanged) | passes |

The V1 constants stay consistent too: `SCOPED_TIMEOUT_SEC` 90 < 120 and `FULL_TIMEOUT_SEC` 540 < 900.
Confining the `최댓값만 본다` rule to V1 is right — `pre_commit_check.py`'s three constants sum to 960
against a 900 budget, so applying the new sum rule to V1 would fail a config the repo accepted on
purpose.

**C-03's non-blocking notice has a working precedent, so it is implementable as written.**
`plan_log_check.py:162`-`:167` and `plan_interview_check.py:172`-`:177` already do exactly the shape
item 4 asks for: `claim_session(HINTED_NS, session_id)`, then `sys.stdout.reconfigure(encoding="utf-8")`,
then `print(HINT)` — including the same comment, `세션당 한 번만. 매 메시지에 같은 줄이 붙으면 그게
소음이다`. The JSON `systemMessage` route also has four call sites
(`heredoc_write_check.py:196`, `paid_test_check.py:358`, `plan_interview_check.py:187`,
`pre_commit_check.py:127`). Round 1 raised no concern here; I checked because a notice that silently
goes nowhere is this repo's most-repeated bug, and the ground is solid.

**`tests/fixtures/a.json` not existing does not weaken the C-05 cross-check.** Both functions are pure
path logic — `relative_to_root` calls `Path.resolve()` non-strictly, and `doctor._target_for` takes an
already-normalized string — so the comparison input set works without creating any file.

## Round 2 findings

### R2-01 · P2 · `_wired_timeouts()` collapses duplicate keys, so "모든 관련 matcher 그룹" cannot be met without changing its shape

**Location** — 구현 범위 7 (`V2 stage 값과 실제 배선의 외부 timeout을 비교하는 테스트`) and the Fast row's
`두 matcher 그룹 모두 검사`, against `tests/test_hook_wiring.py:87`-`:97`.

**Evidence** — the function builds `budgets[(script, event)] = hook.get("timeout")` while walking every
group, so two groups wiring the same script to the same event keep only the **last** value.
`auto_test_check.py` is wired to `PostToolUse` twice — `Write|Edit` at `settings.json:98`-`:99` and
`Bash|PowerShell` at `:114`-`:115`. Both are 120 today, so nothing is wrong at the moment and nothing
would be detected if one of them were lowered.

**Expected behavior** — the budget lookup returns every wired timeout for a `(script, event)` pair, and
the V2 comparison uses the smallest, so lowering any one group's timeout fails the test.

**Verification criteria** — a test that sets the two `PostToolUse` groups to different timeouts (say 120
and 60) and fails on the 60 one. Today's implementation would pass it whenever the lower value happens
to be declared first.

### R2-02 · P2 · item 4's notice should use a shared `_hookutil` helper, not a third copy of the hint pattern

**Location** — 구현 범위 4, against `_hookutil.py:526` (`block()` is the only output helper) and the two
hint sites above.

**Evidence** — the non-blocking hint pattern is already duplicated across `plan_log_check.py` and
`plan_interview_check.py`, comment included. Item 4 would make it three. The load-bearing line is
`sys.stdout.reconfigure(encoding="utf-8")`: without it, Korean text on a cp949 console kills the hook
with `UnicodeEncodeError`, which is why `block()` carries the mirror-image `stderr.reconfigure` and says
so at `:527`-`:528`. This is precisely the class of lesson `_hookutil.py:7`-`:13` exists to keep in one
place, and `test_hook_wiring.py:35` already classifies the module as shared infrastructure.

**Expected behavior** — a `notify_once(namespace, session_id, message)` (or equivalent) in `_hookutil`
that claims the session marker, pins the encoding, and writes the message; item 4 calls it, and the two
existing hint sites can move to it in this task or later.

**Verification criteria** — a test asserting the hook's **stdout actually contains the message** for a
tracked-change-with-no-mapping payload, not merely that the marker was claimed. The marker and the
message are separate failure modes, and the repo has been bitten by the second one
(`_hookutil.py:506`-`:516`, where a wrong field name meant a gate never fired).

### R2-03 · P3 · Q-2's answer is right about writing but understates the per-session cost

**Location** — 구현 범위 1 (`판단 결과가 중요하지 않으면 기존대로 무기록이 가능하며 매 수정마다
History를 쓰라는 뜻은 아니다`) and the Q-2 row, against `history_check.py:135`-`:170`.

**Evidence** — accurate as far as it goes: `_handle_stop` blocks once per session when there are
recordable changes and no assessment marker, and the message ends
`중요하지 않으면 기록 없이 다시 마칠 수 있습니다`, so no file is required. But the marker is only set by
invoking the `history-significance` Skill (`:94`-`:99`, via `_skill_name`) or by writing under a History
prefix (`:103`-`:106`). So adding `.claude/harness/` to `history.tracked_paths` means: every session that
touches a hook, a script, or the schema is **blocked once at Stop** until that Skill runs. In this repo
that is close to every session.

That may well be the intended trade — the gate exists to force the judgment — but the spec currently
reads as though the cost were only "you might write a record." Recommend stating the actual cost in 구현
범위 1 and in `quality-env.md`, the way C-07's 15.80–20.97 s figure is now stated: one forced
`history-significance` invocation per session that touches harness code.

### Note, not a finding

`Fast / PostToolUse` sits at `90 + 30 <= 120` with zero slack, so adding any second Fast stage trips the
new check immediately. I read that as intended — it forces the budget conversation at the moment a stage
is added — but it is worth a word in the table so a future reader does not mistake the margin for room.
Separately, raising Stop to 900 means a session end can now hang for up to 15 minutes on a pathological
run, against 10 before; the measured suite is ~21 s, so this is a ceiling, not a cost.

## What I did not do in Round 2

- No implementation, and no file changed but this review.
- I re-read the revised spec in full and the code regions its new requirements touch
  (`_wired_timeouts`, the four `systemMessage` sites, the two hint sites, `history_check._handle_stop`,
  `doctor.py:2000`). I did not re-run the suite — nothing in the tree changed since Round 1's
  651 passed · 1 skipped, and Codex's own 308-test subset run is reported in the spec.
- Codex's `fail-fast` confirmation from the official docs matches C-08; I did not independently re-fetch
  the page.
- Still unverified, unchanged from Round 1: Linux, and hosted CI. No workflow file exists yet.

## Round 2 recommendation

The spec is ready to implement. R2-01 and R2-02 are corrections the implementer can make inside the
revised scope without another design round — R2-01 falls under 구현 범위 7's own test requirement, and
R2-02 under item 4's `공통 함수로 구현해` principle applied one level down. R2-03 is a documentation
sentence. None of the three blocks a start, so treat this round as "proceed, and fold these in," not as
a gate.

---

# Implementation report

- Date / revision: 2026-11-22 · `C:\my-harness`, `main` / `675b461` + uncommitted working tree.
  **Nothing is committed** — every change below is in the working tree only.
- Implemented: all ten items of 구현 범위, plus R2-01, R2-02 and R2-03 from Round 2.
- Verification: Windows local only. **Linux and hosted CI are not verified** — see
  「Not run, and why」 below.

## Files changed

| File | Change |
|---|---|
| `.claude/harness.json` | rewritten as this repo's dev config. `python` key removed; `source_prefixes`, both `tracked_paths`, five mappings with `why`, `.github/workflows/` in `unmapped_by_design`; Fast `success_codes` `[0]`; Full test timeout 600 → 540; stage `label`s added |
| `.claude/settings.json` | Stop → `auto_test_check.py` timeout 600 → 900 |
| `.claude/harness/hooks/_hookutil.py` | new `is_artifact()` (public, string-keyed) and `notify_once()` |
| `.claude/harness/hooks/_quality.py` | new `profile_uses(name, placeholder)` |
| `.claude/harness/hooks/auto_test_check.py` | V2 test-helper branch → `tests/`; `classify()` with eight causes; `UNMAPPED_REASONS`; `_notify_unmapped()`; V2 Fast path now classifies once and shares the verdict |
| `.claude/harness/scripts/run_quality.py` | **new** — the manual CLI |
| `.claude/harness/scripts/doctor.py` | `check_python()` absent-key PASS; `_target_for()` V2 branch; `ARTIFACT_DIRS`; `_benign_without_mapping()`; `check_mapping()` skips benign causes |
| `.github/workflows/harness-quality.yml` | **new** — one job, OS matrix, `fail-fast: false` |
| `tests/test_hook_wiring.py` | `_wired_timeout_values()` + tightest-wins `_wired_timeouts()`; `budget_violations()`; V2 sum-budget tests |
| `tests/test_auto_test_check.py` | classify causes, priority, notification (once per session, silent on intentional exclusion, valid target still runs) |
| `tests/test_doctor.py` | hook/Doctor target cross-check, `ARTIFACT_DIRS` comparison, three D-PYTHON tests |
| `tests/test_run_quality.py` | **new** — 31 CLI tests, all via real subprocesses |
| `tests/test_v2_templates.py` | docstring and two test names corrected: it checks the **dev** config, not a new-project template |
| `README.md`, `quality-env.md`, `doctor.md` | interpreter, Profile table, tracked/mapping table, time budget, CLI and CI usage, measurements |
| `history/plan/2026-11-22-v2-stage-timeout-budget.md` | **new** — why V2 sums and V1 does not |
| `history/task/2026-11-22-posix-project-dir-on-windows.md` | **new** — the `$PWD` trap below |

## Commands actually run, with results

All with `.venv/Scripts/python.exe` (Python 3.12.5, pytest 9.2.0, ruff 0.17.5).

| Command | Result |
|---|---|
| `pytest -q` (baseline, before any change) | 651 passed · 1 skipped, 20.97 / 16.92 / 15.80 s |
| `run_quality.py --profile full` (final) | lint PASS · format PASS · test PASS, **718 passed · 1 skipped** in 25.87 s, exit 0 |
| `doctor.py` (final) | **PASS 26 · WARN 1 · FAIL 0**, exit 0 — from PASS 24 · WARN 5 |
| `run_quality.py --profile fast --changed <…>` | exercised for every row of the classification table; exit codes 0 / 2 as the table says |
| `run_quality.py` from an outside cwd with a bogus `CLAUDE_PROJECT_DIR` | still reports `대상 루트: C:\my-harness` and runs this repo, exit 0 |
| `pytest -q` with `CLAUDE_PROJECT_DIR` set to the repo root | 651 passed · 1 skipped — confirmed before relying on the CLI's env pinning |
| The CI 「인터프리터 일치 확인」 step body, run locally from bash | `OK: C:\my-harness\.venv\Scripts\python.exe`, exit 0 |
| A real `PostToolUse` payload for `.claude/harness/hooks/_quality.py` piped into the hook process | exit 0 after **28 s** — it actually ran the `tests/` suite. Before this change that path was not even tracked, so nothing ran. This is 완료 기준 1, measured end to end rather than through the mapping function |

The one remaining Doctor WARN is `D-EXEC` 「미검사」: every stage executable is a `{python}`
placeholder, so there is nothing to resolve statically. That is the real limit the spec asked to report,
not a defect. The four WARNs that went away were the two non-existent `pyproject.toml` entries, the
`src/` mapping, and the D-MAPPING orphan on `.claude/harness.json`.

## Two defects the gate caught in my own work

Worth recording because both would have shipped as green.

**The same bug in two places — `mapping_required and not targets`.** My first cut of both the hook and
the CLI treated "no targets" as "nothing to do". That is wrong for a Profile whose stages use only
`{changed_files}`: such a Profile would never run again. The hook version was caught by
`test_intentional_exclusion_is_silent` (it was still calling `run_profile` with empty targets) and the
CLI version by `test_a_profile_without_target_placeholders_does_not_demand_mappings`. Both now gate on
`mapping_required`, and each carries a comment pointing at the other — a third consumer of `classify()`
will hit this, so the rule is written down at both sites.

**The CI interpreter check passed for the wrong reason.** I first wrote
`CLAUDE_PROJECT_DIR="$PWD"` in the workflow's verification step. On a Windows runner bash gives
`/d/a/…`, and Windows `Path()` reads that as `C:\d\a\…` — measured:
`Path('/d/a/my-harness/my-harness').resolve()` → `C:\d\a\my-harness\my-harness`, no `.claude` under it.
`_find_root()` then keeps that bogus root, `venv_python()` finds no `.venv` and falls back to the current
process — **which is the very interpreter the step was comparing against**, so the check passed while the
root was entirely wrong. The step now sets no environment variable (so `_find_root()` uses `os.getcwd()`,
which Python reports correctly) and asserts the root *before* comparing interpreters. Recorded in
`history/task/2026-11-22-posix-project-dir-on-windows.md`, since it applies to any Windows bash caller of
these hooks, not just CI.

## Where I went beyond or aside from the spec

- **The CLI reuses `doctor.resolve_root()`** rather than cloning the layout contract. `doctor.py` is
  stdlib-only with no import side effects, and the spec's rule is that *Doctor* must not import runtime
  hooks — not the reverse. This removes a clone instead of adding one, at the cost of `run_quality.py`
  depending on `doctor.py` being deployed beside it. `tests/test_run_quality.py` copies both, and
  `test_a_misplaced_script_refuses_to_run` locks the contract.
- **The workflow uses `shell: bash` on both OSes** instead of PowerShell on Windows. GitHub runs bash
  with `-eo pipefail`, so intermediate failures propagate by construction — which is what item 9 asks
  for, reached by removing the hazard rather than working around it. The consequence: the Windows leg
  does not exercise PowerShell at all. Nothing under test is shell-specific, but it is a deviation from
  what item 9 implies, so it is your call.
- **`notify_once()` emits JSON** (`hookSpecificOutput.additionalContext` + `systemMessage`) rather than
  the bare `print(HINT)` the two existing hint sites use. Those two are `UserPromptSubmit`, where stdout
  is model context by contract; `PostToolUse` has no such guarantee, so the fields are named explicitly.
  I did not migrate the two existing sites — R2-02 said that could come later, and moving them would mean
  changing output the plan-interview and plan-log gates depend on.
- **I recorded two History entries, not three.** The block-vs-notify decision is significant, but its
  reason (a permanently-blocking gate trains `SKIP_AUTOTEST=1`) is already stated in `_hookutil`'s
  comments, in `_notify_unmapped()`, and now in `quality-env.md`. The skill's own rule is not to
  duplicate an existing reason, so I left it out of Plan History.
- **Action refs: `actions/checkout@v7` and `actions/setup-python@v7`.** Verified current on 2026-11-22;
  checkout is at v7.0.1 and setup-python at v7.1.0. Older majors (checkout v5, setup-python v6) are still
  maintained if you would rather pin conservatively. Note setup-python v6+ needs runner ≥ 2.327.1, which
  GitHub-hosted runners satisfy.

## Not run, and why

- **Hosted CI: not run.** I wrote the workflow but did not commit or push, so no job has ever executed.
  The spec forbids pushing automatically and I did not. Treat both OS legs as unverified.
- **Linux: not run at all.** I re-read the suite for platform assumptions and found none beyond the two
  paired `sys.platform` tests in `test_doctor.py`; the new `tests/test_run_quality.py` uses
  `sys.executable` and relative paths throughout, and its one absolute-path case (`/etc/passwd`) is
  rejected as a usage error on both OSes by string inspection, before any filesystem call. That reads as
  portable. It is not evidence.
- **The workflow YAML is not parser-validated.** PyYAML is not installed and adding it would widen
  `requirements.txt`, which the spec excludes. The file's structure and the heredoc's column-0 terminator
  were checked by reading; the embedded Python body was executed locally and passed. First real
  validation will be the first CI run.
- **The 90-second Fast timeout has 0 s of slack** beyond the 30 s overhead allowance (`90 + 30 <= 120`).
  Intended — adding a second Fast stage must force the budget conversation — but it is the number that
  will break first.

## Still open

- `완료 기준`'s 「Windows 로컬 Full과 두 OS hosted CI가 성공한다」 stays **open**: the Windows local
  half is done (718 passed, exit 0), the hosted half is not started.
- Nothing is committed. `tasks/*.md` are still untracked, so this review and the spec have no revert
  history — worth a commit before the next task touches these files.
- Per the spec's own rule, the next implementation (`template-core-packs`) should not start until the two
  OS results exist or you explicitly accept the unverified constraint.

---

# HQCI-01 … HQCI-03 — reproduced, fixed, re-verified

- Date / revision: 2026-11-22 · `C:\my-harness`, `main` / `675b461` + uncommitted working tree.
- Round: first fix for each defect. Per `SKILL.md`'s 수정 정책 these are not retries, and the three are
  different defects, so none shares a failure count.
- **All three findings are confirmed.** I reproduced each one independently before changing any code,
  with a probe that copies the real modules into a temp project and records whether the stage command
  actually ran and what argv it received. One detail is worse than the finding says — see HQCI-03.

## HQCI-01 — confirmed on every sub-case, including two the finding did not list

Measured before the fix, with a Fast stage taking only `{changed_files}`:

| Input | Before | After |
|---|---|---|
| reasoned exclusion only (`docs/a.md`) | **ran**, argv `['docs/a.md']`, PASS / 0 | nothing ran, SKIP / 0 |
| untracked only (`other/a.md`) | **ran**, argv `['other/a.md']` | nothing ran, SKIP / 0 |
| artifact only (`src/__pycache__/x.pyc`) | **ran**, argv `['src/__pycache__/x.pyc']` | nothing ran, SKIP / 0 |
| non-Python test file only (`tests/a.md`) | **ran**, argv `['tests/a.md']` | nothing ran, SKIP / 0 |
| valid only (`src/a.py`) | ran, argv `['src/a.py']` | unchanged |
| mixed (`src/a.py` + `docs/a.md`) | ran, argv **`['src/a.py', 'docs/a.md']`** | argv `['src/a.py']` |
| hook, real `PostToolUse` payload, excluded file only | exit 0, **ran**, argv `['docs/a.md']` | exit 0, nothing ran |

The finding lists the artifact and non-Python cases under its verification criteria but not its
reproduction; both reproduced exactly the same way, so the cause is one, not four.

**Fix.** The root error was conflating two questions: *can this file be checked* and *does this profile
need mappings*. `auto_test_check` now exports `RUNNABLE_CAUSES = (CAUSE_TARGET, CAUSE_NO_MAPPING_NEEDED)`
and `PROBLEM_CAUSES`, and both consumers derive their execution input from the classification instead of
from `mapping_required and not targets`:

- The hook builds `runnable` from the rows, returns without calling the engine when it is empty, and
  passes `changed_files=tuple(row.path for row in runnable)`.
- The CLI does the same and rebinds `changed` to the runnable paths before `_empty_placeholders`.

Also fixed, per the finding's last bullet: `CAUSE_NO_MAPPING_NEEDED` was printed as `[SKIP]` while being
an execution target — output and behavior were opposite. It now prints `[대상]`.

Both sites carry a comment pointing at the other, because the two copies of this rule are the thing most
likely to drift.

## HQCI-02 — confirmed, and the fix aligns the CLI with Doctor

Before: `schema_version: 3` ran the probe and reported **PASS / 0**. The CLI gated on
`_hookutil.is_v2()`, whose meaning is `>= 2`.

Worth recording: Doctor already had this right. `check_version` FAILs for `raw >= 3` with
`다만 is_v2() 는 참이므로 실제 훅은 V2 분기로 돕니다 — 검증되지 않은 조합입니다`. So the CLI was the
only one of the three tools that disagreed, and the fix moves it onto Doctor's judgment rather than
inventing a third rule.

The CLI now requires the raw value to be exactly `int` 2, rejecting `bool` explicitly (`True == 1` would
otherwise slip) and `2.0` (which `!= 2` does *not* catch, since `2.0 == 2` in Python). `_hookutil.is_v2()`
is untouched.

The error message also changed, which the finding did not ask for but the measurement justified: every
bad version used to report `지금 1`, because `schema_version()` substitutes 1. For a config containing
`"2"` or `2.0` that is actively misleading. It now prints the raw value.

| Version | After |
|---|---|
| `3`, `4`, `99` | ERROR / 2, probe never ran |
| `1`, `0`, `-1`, absent | ERROR / 2, probe never ran |
| `"2"`, `2.0`, `True`, `[2]` | ERROR / 2, probe never ran |
| `2` | runs normally |

## HQCI-03 — confirmed, and the whitespace case is worse than described

Before, with `{mapped_targets}` in use and `--changed src/a.py`:

| `unmapped_by_design` value | Before | After |
|---|---|---|
| `""` | `[SKIP] … 등록돼 있지만 사유가 비어 있습니다`, SKIP / 0 | ERROR / 2 |
| `"   "` | **`[SKIP] src/a.py —`** — the reason printed as an empty string | ERROR / 2 |
| `null` | SKIP / 0 | ERROR / 2 |
| list form in a V2 config | SKIP / 0 | ERROR / 2 |

The whitespace row is the part the finding understates. `_unmapped_reason()` used
`why or "<substitute>"`, and `"   "` is truthy, so not even the substitute text appeared — the output
claimed the file was excluded and gave no reason at all. That is the exact failure this repo's
`unmapped_by_design` exists to prevent, reproduced inside the mechanism meant to prevent it.

**Fix.** `_unmapped_reason()` returns `why.strip() or None` — no substitute text, ever. A key that
matches but has no usable reason now yields the new `CAUSE_EXCLUDED_NO_REASON`, which is in
`PROBLEM_CAUSES`, so the CLI errors before running and the hook sends its non-blocking notice. **V1
list-form exclusions stay valid**, since that schema had no reason field at all; the strictness is gated
on `_hookutil.is_v2()`.

Two things I changed beyond the finding, both to keep the three tools consistent:

- `_unmapped_key_for()` now picks the **longest** matching prefix. The old `any(...)` was
  order-dependent, so with overlapping entries the reported reason depended on dict order.
- Doctor: `_reasoned_unmapped()` feeds `check_mapping` only keys with a usable reason, so a reason-less
  exclusion no longer suppresses the D-MAPPING warning, and `_benign_without_mapping`'s message now says
  `사유를 적은 의도적 제외`. Separately, `unmapped_by_design` values that are empty or whitespace get a
  **WARN** (`D-CONFIG`) — the schema has no `minLength`, so they were passing silently.

**Why WARN and not FAIL** — your call if you disagree. Doctor is static and cannot know whether that
path is ever changed, and at the moment it matters the CLI already hard-fails. A FAIL would also change
Doctor's exit code for a config that may never trip. Non-string values were already a FAIL and remain one.

## HQCI-N01 — documentation

- `quality-env.md` gained a 「운영 비용」 section stating the real R2-03 cost: a session touching
  `.claude/harness/` or `tests/` **is blocked once at Stop**, and the `history-significance` call cannot
  be skipped even though the record itself can. The two are now distinguished explicitly.
- `quality-env.md` gained 「수동 실행」 covering the `SKIP_*` contract, the exit codes, the exact-2
  version rule, and that classification limits execution input. The CLI's **output** now carries the
  same line — `훅 우회 변수(SKIP_*)는 이 명령에 적용되지 않습니다.` — which was the half the spec asked
  for and the implementation had only in its docstring and tests.
- `quality-env.md`'s `full` claim is corrected: `pre_commit` runs regardless of paths, `stop` does not —
  `_v2_session_changes()` gates it. I confirmed `pre_commit_check.py` has no tracked-change condition at
  all, so the asymmetry is real.
- `doctor.md`'s measurement row is corrected. You are right: the baseline run had the `python` key, so
  D-PYTHON was already PASS, and the four WARNs that disappeared were three D-SCAFFOLD (two
  `pyproject.toml`, one mapping `src/`) plus one D-MAPPING. The D-PYTHON message fix is now described as
  a separate improvement, not one of the four.
- `quality-env.md` also states that a reason-less exclusion is not an exclusion, since that is now a
  rule a reader has to know.

## Commands run, with results

| Command | Result |
|---|---|
| Reproduction probe, before the fixes | all three findings reproduced; argv and run-traces in the tables above |
| Same probe, after the fixes | all three rows clean — exclusions run nothing, mixed input passes only the valid file, bad versions never execute |
| `run_quality.py --profile full` | **762 passed · 1 skipped**, lint·format·test all PASS, exit 0 |
| `doctor.py` | **PASS 26 · WARN 1 · FAIL 0**, exit 0 — unchanged; the survivor is still D-EXEC 「미검사」 |
| Real `PostToolUse` payload for `.github/workflows/harness-quality.yml` (this repo's own exclusion) | exit 0 in **0 s** — nothing ran, as intended |
| Test count | 718 → **763 collected** (45 new) |

**One intermediate FAIL is worth reporting rather than hiding.** The first post-fix `--profile full` run
came back `PASS 1 · FAIL 1 · NOT RUN 1`: `ruff format --check` rejected three of the test files I had
just written. I ran `ruff format` and re-ran. That failure is incidental, but it exercised the `NOT RUN`
feature in anger — the `test` stage correctly did not run after `format` failed, and the summary said so
instead of implying the tests had passed.

## New regression tests

45 tests, all asserting on an execution trace rather than on output text where the distinction matters:

- `tests/test_run_quality.py` — the five classification cases from your criteria plus untracked-only,
  each asserting the stage command left no trace; mixed input receives only the valid file;
  `CAUSE_NO_MAPPING_NEEDED` runs and is not labelled SKIP; the `{mapped_targets}` profile still works;
  eleven bad `schema_version` values; five reason-less exclusion shapes.
- `tests/test_auto_test_check.py` — the same cases through `_handle_v2_post_tool_use` with real payloads,
  asserting the engine call and its exact `changed_files`/`mapped_targets`; the reason-less exclusion
  notice; **V1 list-form compatibility**; longest-prefix reason selection.
- `tests/test_doctor.py` — the empty-reason WARN, `_reasoned_unmapped()` filtering,
  `_benign_without_mapping` requiring a reasoned exclusion, and the existing hook cross-check updated to
  the reasoned-only source.

## Still open, unchanged

- **Linux and hosted CI remain unverified.** Nothing has been pushed; no CI job has run. The workflow
  YAML is still not parser-validated.
- Nothing is committed. `tasks/*.md` are still untracked.
- 완료 기준's 「Windows 로컬 Full과 두 OS hosted CI가 성공한다」 stays half open for the same reason as
  before.
- The three implementation choices you accepted are unchanged; I did not revisit them.

---

# Hosted CI — run, failed once, green on both OSes

- Date: 2026-11-22. Authorized by the user to commit, push `main`, monitor both jobs and record the
  results here. The task 2 and task 3 spec files were explicitly excluded from the commit.
- Commits: **`63201d2`** (the implementation, 20 files) and **`0e52390`** (one CI fix, below). Both are
  on `main` at `origin`. `tasks/template-core-packs.md` and `tasks/template-install-smoke.md` remain
  untracked, as instructed.

## Both jobs pass

Run **[45033823289](https://github.com/JungHwyKim/my-harness/actions/runs/45033823289)** on `0e52390` —
conclusion **success**.

| Job | Result | Duration | Link |
|---|---|---|---|
| `quality (ubuntu-latest)` | **success** | 16 s | [job 137243026598](https://github.com/JungHwyKim/my-harness/actions/runs/45033823289/job/137243026598) |
| `quality (windows-latest)` | **success** | 44 s | [job 137243026924](https://github.com/JungHwyKim/my-harness/actions/runs/45033823289/job/137243026924) |

Per-OS evidence, read from the job logs rather than inferred from the green tick:

| Step | ubuntu-latest | windows-latest |
|---|---|---|
| `pip check` | `No broken requirements found.` | same |
| Doctor | `PASS 26 · WARN 1 · FAIL 0` | same |
| `ruff check` | `All checks passed!` | same |
| `ruff format --check` | `75 files already formatted` | same |
| `pytest -q` | **762 passed, 1 skipped** in 7.93 s | **762 passed, 1 skipped** in 23.37 s |
| CLI verdict | `PASS 3 · FAIL 0 · SKIP 0 · NOT RUN 0` | same |

The Linux counts match Windows exactly, including the single skip — that is
`test_doctor.py`'s Windows-only branch test, which skips on POSIX while the POSIX
permission-bit test runs. So the suite has no hidden platform gap: each OS skips exactly the one test
written for the other.

## The first run failed on Windows, and not where I expected

Run **[45033603512](https://github.com/JungHwyKim/my-harness/actions/runs/45033603512)** on `63201d2`:
ubuntu **success**, windows **failure** at 「인터프리터 일치 확인」.

**Both of that step's assertions passed.** It died on the line after them:

```text
UnicodeEncodeError: 'charmap' codec can't encode characters in position 0-1
```

`print(f"일치: {chosen}")` — the Korean success message — could not be encoded, because the Windows
runner's stdout is not UTF-8 by default. The step verified what it was supposed to verify and then
crashed reporting it.

This is the same lesson this repo has already recorded three times. `_hookutil.child_env()` sets
`PYTHONIOENCODING=utf-8` for child processes for exactly this; `block()` and `notify_once()` pin the
encoding; `doctor._print()`, `run_quality._print()`, `openwork/collect.py:638` and
`quiz/collect.py:416` all pin their own stdout. **My inline workflow script was the one place in the
job that did not**, which is why the failure landed there and only there — the later Doctor and
`run_quality` steps would have been fine.

Fixed in `0e52390` by pinning the encoding in that script, not with a job-level `PYTHONIOENCODING`.
Relying on the caller to attach it is a convention this repo considered and rejected
(`_hookutil.child_env()`'s comment); the job-level variable would have hidden the fact that the script
was the odd one out.

Worth saying plainly: Round 2's R2-02 and the Task History entry both argued that this class of bug is
what `_hookutil` exists to centralize, and I then wrote a fourth copy of the pattern by hand in YAML and
left the encoding line out of it. The CI caught it on its first run, which is the point of having it.

## A new limitation: the interpreter check is weaker on Linux than on Windows

Not a blocker — both jobs pass and the check does catch what it was built for — but the two log lines
side by side show it is not verifying the same thing on both OSes:

```text
ubuntu-latest   일치: /opt/hostedtoolcache/Python/3.12.16/x64/bin/python3.12
windows-latest  일치: D:\a\my-harness\my-harness\.venv\Scripts\python.exe
```

On Windows a venv **copies** `python.exe`, so the comparison is genuinely between the prepared `.venv`
and what the harness chose. On Linux `.venv/bin/python` is a **symlink** to the base interpreter, and the
step compares `os.path.realpath()` of both sides — so both collapse to the hostedtoolcache binary. The
consequence: on Linux the step would still pass if the harness had chosen the bare base interpreter
instead of the venv, because the two realpath to the same file.

The practical risk is small, since a bare interpreter has no pytest or ruff and the `Full Quality
Profile` step would fail immediately. But the step's stated purpose is
「준비한 그 venv 를 고르는지」, and on Linux it does not establish that. The fix would be to compare
`sys.prefix` against the expected `.venv` directory, or compare the unresolved paths, instead of
comparing resolved binaries. **I did not change it** — both jobs are green, the user's instruction for
this round was to commit, push, monitor and report, and this is a new finding rather than one of the
HQCI items. It is Codex's call whether to fold it into this task or carry it forward.

## Completion criteria — the CI line now closes

- 「Windows 로컬 Full과 두 OS hosted CI가 성공한다」 — **met.** Windows local Full passed
  (762 passed · 1 skipped) and both hosted jobs passed on `0e52390` with the evidence above.
- The spec's gate on starting task 2 (「두 OS 성공 근거를 확보하거나 사용자가 미검증 제약을 수용」) is
  satisfied by evidence rather than by acceptance of an unverified constraint.
- Still not done: the workflow YAML has never been parser-validated locally (PyYAML is not installed and
  adding it would widen `requirements.txt`) — though two successful runs are stronger evidence than a
  parser would have been.
- The temporary task files stay in place until Codex's final review, as instructed. The handoff skill's
  cleanup condition about content living in a verified commit is now satisfied for both of them —
  they are in `63201d2`.
