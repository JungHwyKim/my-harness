# hook-dicision.md — conflict review

Date: 2026-11-18. Checkout `release/v2` at `4f5300c` with Rounds 1–3 of
`tasks/handoff.review.md` uncommitted in the working tree. Spec unchanged since
21:49 (83 lines). **Nothing implemented** — four conflicts, two of them blocking.

## Citations: 23 of 24 resolve

I mechanically checked every `file:line` claim in the spec. Six shifted by 1–4
lines, all of them because **I reformatted those files in Round 3**, not because
the spec was wrong. Content is intact in every case.

| Spec says | Now at |
|---|---|
| `paid_test_check.py:211-234` `_deny()` | `209-232` |
| `paid_test_check.py:253-256` env bypass | `251-252` |
| `paid_test_check.py:258-259` empty-marker return | `256-257` |
| `_quality.py:187-212` `run_stage()` | `subprocess.run` at `216` |
| `test_v2_templates.py:23-28` | `schema_version` at `29-30` |
| `test_hook_wiring.py:258` | `257` |
| `conftest.py:142` | `139` |

One apparent drift was my own checker's false positive: `_deny()` builds its
reason with `f"{_ALLOW_ENV}=1"`, so the literal `ALLOW_PAID_TESTS` never appears
inside the function. The spec's description of it is accurate.

## C1 (blocking). Item 6 does not fix the 14 failing tests

The spec's verification table requires `python -m pytest tests -q` to pass. It
cannot, because item 6 never addresses why those tests fail.

The 12 `test_paid_commands_are_blocked` failures have nothing to do with the
deny→ask change. They fail because `blocked_reason()` consults **this
repository's** config:

- `.claude/harness.json:63` is `"pytest_markers": []`
- `paid_test_check.py:256-257` returns early on an empty marker tuple
- `tests/test_paid_test_check.py:67-68` calls `blocked_reason()` on the
  module imported against that config, and asserts a non-`None` result

Item 3 makes detection *stricter*, which changes nothing here: with no markers
configured there is nothing to detect, so all 12 still fail. `test_deny_payload_shape`
and `test_bom_prefixed_input_is_still_judged` fail for the same reason — the hook
emits nothing, so `json.loads("")` raises.

**The test file already contradicts itself.** Two tests in it inject a config
through the `load_hook` fixture and pass: `test_v2_marker_policy_is_project_defined`
(`:134`) and `test_v2_without_markers_disables_expensive_guard` (`:159`). The
second one *asserts that an empty marker list disables the guard* — the very
behaviour that makes the other 12 fail. So the file simultaneously requires
detection and requires its absence, under one configuration.

The fix is small and the pattern is already in the file: the direct-call tests
need `load_hook` with a marker policy, and the three subprocess tests need
`CLAUDE_PROJECT_DIR` pointed at such a project. The spec should say so, because
without it item 6 leaves the suite red and the Full gate failing.

## C2 (blocking). The completion criteria are not reachable by Claude

The spec states 아래 검사는 모두 필수다 and lists, among others:

- 승인·거절을 각각 시험하고, 한 번의 승인으로 다음 유료 명령이 자동 허용되지 않음을 확인
- `permissions.allow`에 `Bash(pytest*)` 류 규칙이 있을 때, auto mode와 권한 확인을
  건너뛰는 모드에서 승인창이 뜨는지
- 승인을 받을 수 없는 비대화형 실행에서 유료 테스트가 실행되지 않는다

These require someone to observe and answer an approval dialog, and to run the
session under other permission modes. I cannot do either. So the spec's own
rule — 하나라도 실패하면 구현 완료로 보지 않는다 — means I could implement items
3–6 and still never be able to declare them done.

This matters more than a process technicality, because of C3.

## C3 (blocking, and the reason to stop). deny→ask weakens a control on an unverified premise

Item 3 converts a hard block into a user prompt, and item 3 also deletes the
`ALLOW_PAID_TESTS` bypass. The spec is explicit that the change rests on an
assumption it has not confirmed: *"승인창 없이 실행되는 경로가 확인되면 `deny`로
되돌린다."*

Implementing it would therefore replace a control that definitely blocks with
one that only blocks if this installed version honours `ask` — and C2 says the
check that would justify it is the one I cannot run. If `ask` is not honoured on
some path, paid API calls run with no block and no bypass flag to notice its
absence. I am not willing to make that trade without the verification, and I do
not think I should make it on the user's behalf.

Items 3–6 are also atomic: removing `allow_env` from the config and schema
(item 4) and from `tests/_escape_hatches.py` (item 5) breaks
`test_hook_wiring.py:257` `test_no_stale_escape_hatch_names` unless item 3 lands
in the same change. So there is no safe partial implementation.

## C4 (scope). Items 1 and 2 are about a different repository

Both say 실제 프로젝트 — the real project, not this template:

- Item 1: register paid markers in that project's `checks.expensive_tests.pytest_markers`
  and exclude them in its pytest `addopts`
- Item 2: add the exclusion to that project's Fast/Full pytest `argv`

This repository is the template. It has no paid tests, no `pyproject.toml`, and
the spec itself says the template's list stays empty. `C:\agentic-rag-proj` is
not in this session's directories, so I cannot act on either item here. They
belong to a task scoped to that repository.

## What is actionable here

| Item | Status |
|---|---|
| 1, 2 | Not in this repository (C4) |
| 3, 4, 5 | Blocked on C2/C3 — a safety control change whose justification cannot be verified by me |
| 6 | Incomplete as written (C1); the 14 failures need a marker policy in the tests |
| 7 | Actionable. `.codex/hooks.json` wires `paid_test_check.py`, and if Codex does not honour `ask` the wiring gives no protection. Depends on item 3 landing first, so it has no meaning on its own |

The one change that is both safe and useful today is the C1 fix: give the
failing tests a marker policy so they exercise the hook at all. It touches no
hook behaviour, makes the suite green, and is a prerequisite for item 6 rather
than a substitute for it — you cannot tell whether a hook rewrite regressed
anything while 14 of its tests fail before you start. It does, however, edit
`tests/test_paid_test_check.py`, which item 6 claims, so it is the user's call
whether to pre-empt that.

## Phase A — complete, automated verification passed

Date: 2026-11-18. Implemented against the revised spec (23:18, 192 lines), which
resolves C1–C4. Checkout `release/v2` at `4f5300c` with Rounds 1–3 uncommitted.

**C1 is closed.** `tests/test_paid_test_check.py` no longer reads this
repository's `.claude/harness.json`. The policy-dependent tests take their marker
policy from a temporary V2 project through a new `paid_hook` fixture
(`load_hook` + `_v2_config(["integration"])`). Because `load_hook` also sets
`CLAUDE_PROJECT_DIR`, the five subprocess tests inherit the same policy; the one
that passes `env` explicitly keeps the path via `dict(os.environ, ...)`, which
the helper's comment now states as a requirement.

Hook behaviour, configuration and schema are **unchanged** in this phase, as the
spec requires: the response is still `deny` and `test_escape_hatch` still passes.

Three cases added, keeping the three policy states independent:

| Test | Covers |
|---|---|
| `test_v1_without_config_uses_integration_default` | V1 compatibility — no config file, `integration` is the default marker |
| `test_module_state_is_restored_between_tests` | a temp project's markers must not leak onward |
| `test_repo_config_is_seen_after_reload` | asserts `_PAID_MARKERS == ()` for this repo, so the restore fixture cannot break silently |

The leak was real, not hypothetical: `load_hook` reloads `_hookutil` and the
hook **globally**, so without restoration any later test judging via the
module-level import would use the temp project's markers. A new autouse
`_restore_module_state` fixture reloads both against `REPO_ROOT` after each
test, and takes `monkeypatch` as a parameter so it tears down *before*
monkeypatch restores the environment — the reverse order would restore from an
already-reverted `CLAUDE_PROJECT_DIR`.

### Verification — automated, complete

| Command | Exit | Result |
|---|---|---|
| `pytest tests/test_paid_test_check.py -q` | **0** | 34 passed (was 14 failed / 17 passed) |
| `pytest tests/test_paid_test_check.py tests/test_hook_wiring.py tests/test_v2_templates.py -q` | **0** | 60 passed |
| `pytest -q` | **0** | **344 passed** (was 14 failed / 327 passed) |
| `ruff check .` | **0** | All checks passed |
| `ruff format --check .` | **0** | 76 files already formatted |

All three Full stages are green for the first time in this session. No new
failures appeared elsewhere, so nothing needed separating from pre-existing
failures. The spec's exclusions were respected: no marker was added to
`.claude/harness.json`, `test_v2_without_markers_disables_expensive_guard` was
kept rather than deleted, and no rule was relaxed.

Changed: `tests/test_paid_test_check.py` only.

### Phase status

- **A — complete**, automated verification passed.
- **B — not started.** Its judgement upgrade (proving that an `-m` expression
  excludes *every* configured paid marker, across repeated options, parenthesised
  and `or` expressions, `-c`/`--config-file` and `-o addopts` overrides) plus the
  permission-mode table changes what the hook blocks. It is also atomic with the
  bypass removal across `_policy()`, `.claude/harness.json`,
  `harness.schema.json` and `tests/_escape_hatches.py` — `test_hook_wiring.py`
  fails if those move apart. Starting it at the tail of a session risks leaving
  the hook half-converted, which is the one state worse than either end.
- **C — awaiting the user**, unchanged and not startable by Claude.

## Recommended spec corrections

1. Add the marker-policy fix for the existing tests to item 6, naming the
   `load_hook` fixture and `CLAUDE_PROJECT_DIR` for the subprocess cases, and
   resolve the contradiction with `test_v2_without_markers_disables_expensive_guard`.
2. Mark the interactive verification rows as user-performed, and say what Claude
   may declare done without them.
3. Move items 1 and 2 into a spec scoped to the real project.
4. Re-read the seven shifted citations above before relying on their numbers.

---

# Phase B — 코드·자동 검증 완료 / C 미확인

Date: 2026-11-18. Implemented per the revised spec. **Automated verification is
complete; the approval-dialog behaviour is not verified** and the two are kept
separate below, as C2 requires.

## The judgement rule was inverted

The old rule asked *does this `-m` select a paid marker*, so `-m unit` passed.
But a command-line `-m` **replaces** the config's `addopts` exclusion, so
`-m unit` runs with no exclusion at all and can collect paid tests. `-m 'not paid
or unit'` was worse: it contains the string `not paid` yet the other branch of
the `or` still selects paid tests.

The rule now asks *does this provably exclude **every** configured marker*.
`_provably_excludes_all()` accepts only a simple AND expression — no `or`, no
parentheses — in which every configured marker appears as `not <marker>`.
Anything else asks. No string `eval`, since evaluating a command-line expression
would itself be the hole.

**This is a deliberate broadening.** Commands that previously passed now ask:
`-m unit`, an empty `-m`, `-m 'not paid'` when two markers are configured, any
parenthesised expression, a repeated `-m` where one is unprovable, `-c` /
`--config-file`, and an `-o addopts=` override that does not exclude everything.
`pytest -q` with no `-m` still passes, relying on the project's default
exclusion — which is why the README now insists on configuring all three places.

## The mode table is fail-closed

`ask` only for `default`, `acceptEdits`, `auto`. Everything else is `deny`,
including `plan`, `dontAsk`, `bypassPermissions` **and a missing or unrecognised
mode**. This is the direct answer to C3: if the mode cannot be read, emitting
`ask` risks running with no dialog and no trace, which is worse than blocking.
`deny` is the default branch, not an enumerated list, so a new mode name cannot
silently become permissive.

## The bypass is gone, atomically

`ALLOW_PAID_TESTS` removed from four places in one change, since any subset
breaks `test_hook_wiring.py`:

| File | Change |
|---|---|
| `paid_test_check.py` | `_policy()` returns a 2-tuple; V1 branch keeps the `integration` default but loses the bypass; the env check in `main()` is gone; `import os` removed with it; docstring rewritten |
| `.claude/harness.json` | `allow_env` removed |
| `harness.schema.json` | `allow_env` property removed |
| `tests/_escape_hatches.py` | `ALLOW_PAID_TESTS` removed, with a comment saying why it must go together with the other three |
| `tests/conftest.py` | the 2026-08-22 measurement is preserved, with a note that the bypass no longer exists |

`_deny()` became `_respond(decision, detail, mode)` — one function for both
verdicts, because the `hookSpecificOutput` shape is identical and two copies
would let one drift until the harness silently ignores it.

## Other files

- `.codex/hooks.json`: the paid-hook entry removed, the other hooks untouched.
  Codex's `PreToolUse` does not support `ask` and continues the tool call after
  reporting an error, so leaving it wired would look like protection while
  providing none.
- `README.md`: a new 유료·외부 테스트 보호 section covering all three required
  places, with the `pyproject.toml` and Quality `argv` examples, and a note that
  importing into an existing project must not overwrite its config.
- `.claude/wiki/knowledge/paid-test-approval.md`: the current contract, the
  judgement and mode tables, what the hook cannot detect, and an explicit
  "아직 확인하지 못한 것" list so unverified behaviour is not recorded as fact.

## Verification — automated, complete

| Command | Exit | Result |
|---|---|---|
| `pytest tests/test_paid_test_check.py -q` | **0** | 64 passed (34 at end of A) |
| `pytest …paid… …hook_wiring… …v2_templates… -q` | **0** | 90 passed |
| `ruff check .` | **0** | All checks passed |
| `ruff format --check .` | **0** | 77 files already formatted |
| `pytest -q` | **0** | **374 passed** (344 at end of A) |

New tests: the full command table (10 approval cases, 6 free cases) against a
**two-marker** project — one marker alone would let `all()` be misread as
`any()` and still pass; the six-row mode table; ask and deny payload shapes;
missing/unknown mode; BOM input now carrying a mode; a parametrized
`test_env_bypass_is_gone` covering `=1`, `=0` and a formerly project-defined
`allow_env` name; and the reason text naming both markers and the offending
option.

### No-cost proof that the default exclusion works

A throwaway project with `unit` / `paid` / `paid2` marked tests that only write
a marker file — no network, no API key — verified the README guidance:

| Invocation | Collected | Marker files left |
|---|---|---|
| `pytest -q` (README `addopts`) | 1 passed, 2 deselected | `unit` only |
| `pytest -m "not paid and not paid2" -q` (Quality `argv` style) | 1 passed, 2 deselected | `unit` only |
| `pytest --collect-only -q` | 1/3 collected, 2 deselected | — |
| `pytest -m paid -q` (**control**) | 1 passed | `paid` |

The control row matters: without it, the exclusion would "pass" even if the
markers were misspelled and nothing ran at all.

## 사용자 승인창 확인 대기 — Phase C

**Not verified, and not claimable by Claude.** The protection now depends on the
harness honouring `ask`, which only you can observe. Every row below is open:

| 확인 | 기대 결과 |
|---|---|
| `default`/`acceptEdits`/`auto` 에서 유료 명령 | 승인창이 뜨고, 응답 전에는 표식 없음 |
| 거절 | 표식 없음 |
| 승인한 뒤 같은 명령 재요청 | 첫 호출만 표식, 두 번째는 다시 묻는다 |
| `permissions.allow` 에 pytest 허용 규칙 존재 | 호출별 승인이 유지된다 |
| `plan`/`dontAsk`/`bypassPermissions`/알 수 없는 모드 | deny, 표식 없음 |
| 승인 전달 수단이 없는 비대화형 실행 | 실행되지 않는다 |

### Reproduction procedure (prepared and preflighted)

A self-contained probe project was built outside this repository, at
`<scratchpad>/paidprobe`. It holds copies of `paid_test_check.py` and
`_hookutil.py`, a minimal `.claude/settings.json` wiring only the paid hook, a
`.claude/harness.json` declaring markers `["paid", "paid2"]`, a `pyproject.toml`
with `addopts = "-m 'not paid and not paid2'"`, and `test_paid_probe.py` whose
`paid`/`paid2` tests write a file into `ran/` and touch nothing else. No
network, no API key, no shared template config is modified.

Recreate it anywhere with those five files if the folder is gone — it is a
scratch location and a reboot can clear it.

**Preflight already passed, 11 of 11.** Driving the hook directly with
`CLAUDE_PROJECT_DIR` pointed at the probe gives: `ask` for `default`,
`acceptEdits`, `auto`; `deny` for `bypassPermissions`, `dontAsk`, `plan` and a
missing mode; `ask` for `-m 'not paid'` (only one of two markers excluded); and
no output for `pytest -q`, `-m 'not paid and not paid2'` and
`--collect-only -m paid`. So the judgement layer is not the variable in phase C —
only whether the harness surfaces `ask` as a dialog.

**The command must be run by Claude, not in a plain terminal.** `PreToolUse`
fires on Claude's tool call; a command typed into a shell bypasses the hook
entirely and proves nothing.

| Step | Action | Expected |
|---|---|---|
| 0 | Open a Claude Code session with the probe folder as its directory | the probe's `.claude/settings.json` is the active hook config |
| 1 | Ask Claude to run `python -m pytest -q` | no dialog; `ran/` contains only `unit` |
| 2 | Delete `ran/`, ask Claude to run `python -m pytest -m paid -q` in `default` mode | approval dialog appears, and `ran/` is still absent until answered |
| 3 | Decline it | no `ran/paid` |
| 4 | Repeat step 2 and approve | `ran/paid` appears |
| 5 | Ask for the same command again | asked again — approval must not carry over |
| 6 | Add a `permissions.allow` rule for pytest, repeat step 2 | still asked |
| 7 | Repeat step 2 under `plan`, `dontAsk`, `bypassPermissions` | blocked, no `ran/paid` |
| 8 | Run the same command non-interactively, with no way to answer | not executed |

Reading the result is always the same: `ran/` is the evidence. A marker file
exists only if that test body actually ran, so "dialog declined but `ran/paid`
exists" is the failure to look for.

Reset between steps by deleting `ran/`. Cleanup is deleting the whole probe
folder; nothing in this repository is involved.

If any path is observed running **without** a dialog, restore `deny` for that
path first and record the cause — per the spec, before anything else. The
narrowest change is to move that mode out of `_ASK_MODES` in
`paid_test_check.py`, which sends it to the default `deny` branch.

## Phase status

- **A — complete**, automated verification passed.
- **B — 코드·자동 검증 완료.** All five commands exit 0; 374 tests pass.
- **C — 미확인, 사용자 대기.** No 최종 완료 and no real-project rollout until
  those six rows are recorded.
- Out of scope and untouched, as the spec requires: no other repository, no real
  paid API call, no commit or push, no marker added to this template's `[]`.

---

# Phase C — 승인 동작 확인, 진행 중

Date: 2026-11-19. Run by the user in the probe project; Claude prepared and
observed but cannot operate the dialog. Environment: Claude Code on Windows, the
`PowerShell` tool path.

## Confirmed: `ask` surfaces as a real confirmation dialog

This was the premise the whole deny→ask change rested on, and it is now
evidenced rather than assumed. The harness attributes the prompt to the hook by
name and renders our reason verbatim:

```
Hook PreToolUse:PowerShell requires confirmation for this command:
유료 API 를 호출할 수 있는 테스트입니다. 이 호출을 실행할지 승인해 주세요.

마커 표현식 `-m paid` 가 expensive marker(paid, paid2) 제외를 보장하지 못합니다.
명령줄 -m 은 설정의 기본 제외를 덮어씁니다.

검증용입니다. 이 프로젝트의 paid 테스트는 네트워크를 쓰지 않고 표식 파일만 남깁니다.
승인은 이 도구 호출 하나에만 적용됩니다. 다음 유료 명령은 다시 묻습니다. [settings]
```

Three things this settles at once:

1. The decision reaches the user as a confirmation, not as a silent pass.
2. The reason carries what the user needs to decide — both configured markers,
   the offending option, the project's own reason, and the scope of the approval.
3. The `PowerShell` matcher path is covered, not only `Bash`. That matters here
   because this repository's command examples are all PowerShell, and a
   `Bash`-only matcher was a historical gap `test_hook_wiring.py` exists to catch.

| 확인 | 결과 |
|---|---|
| `default` 에서 유료 명령 → 승인창 | **확인됨.** 위 문구 그대로 |
| 거절 → 표식 없음 | **확인됨.** 거절 뒤 `ran/` 자체가 없었다 |

The declined run was observed before the dialog text was captured, so pairing
the two is an inference — but the hook demonstrably asks for that exact command,
so the dialog the user declined was this one.

A control run was also recorded: the same command typed **directly into a
terminal** ran to completion and left `ran/paid`. That is correct and worth
keeping — `PreToolUse` governs Claude's tool calls, not the user's own shell. It
also proves the probe is not vacuous: the paid test does run and does leave
evidence when nothing intercepts it.

## Still open

| 확인 | 기대 |
|---|---|
| 승인 → 표식 생성 | `ran/paid` 가 생긴다 |
| 승인 뒤 같은 명령 재요청 | 다시 묻는다. 승인이 이어지면 안 된다 |
| `permissions.allow` 에 pytest 허용 규칙 존재 | 그래도 호출별로 묻는다 |
| `plan`·`dontAsk`·`bypassPermissions` | deny, 표식 없음 |
| 승인 전달 수단이 없는 비대화형 실행 | 실행되지 않는다 |

The allowlist row is the one worth doing next: it is the only check that
separates this hook's protection from the harness's own generic Bash
confirmation. Until it is recorded, 최종 완료 is not claimed.

## Observed: the hook's dialog offers no "don't ask again"

The user reported that the confirmation for the paid command has no
always-allow option, unlike an ordinary tool-permission prompt.

That is a result in itself, and a favourable one. A hook-driven `ask` is not a
suppressible tool permission — there is nothing on the prompt to allowlist, so a
user cannot turn one approval into a standing one by clicking through. It also
distinguishes the two prompt types at a glance: the generic Bash confirmation
offers always-allow, this one does not.

It does change how the allowlist row has to be tested. The rule cannot be
created from the dialog, so it has to come from settings. A
`.claude/settings.local.json` granting the `Bash` and `PowerShell` tools
outright was placed in the probe for that purpose — deliberately broader than
anything a real project would use, because the question is whether the hook
still asks under the most permissive condition available.

Exact permission-matcher syntax for the `PowerShell` tool is **unverified** on
this installation. Whether the rule took effect is checked indirectly: a safe
command (`-m pytest -q`) should run with no prompt at all once it applies.

## Confirmed: a permission rule does not bypass the hook

The decisive row. With `{"permissions": {"allow": ["Bash", "PowerShell"]}}`
active in the probe's `settings.local.json` — tools granted outright, broader
than any real project would configure — the sequence was:

| Step | Command | Result |
|---|---|---|
| control | `… -m pytest -q` | ran with **no prompt**, so the rule is in force |
| test | `… -m pytest -m paid -q` | **hook confirmation still appeared**, then approved |
| evidence | `ran/` | `unit` and `paid` present, `paid2` absent |

So the hook's per-call approval survives a tool-permission grant. That answers
the question this phase existed for: the protection is this hook's own, not a
side effect of the harness's generic Bash confirmation. The control row is what
makes it conclusive — without the safe command running silently first, a
confirmation on the paid command would prove nothing about allowlists.

Two further rows fall out of the same run:

- **승인 → 표식 생성: 확인됨.** Approving produced `ran/paid`.
- `paid2` never ran under either invocation, which confirms the two-marker
  default exclusion from the README guidance holds in practice, and that
  `-m paid` selects only the marker named.

The control step's "no prompt" is taken from the user's report that both
commands behaved as predicted; if that first command did in fact prompt, the
allowlist conclusion above has to be revisited.

## Confirmed: approval does not carry over

Re-requesting the identical command after approving it produced the
confirmation **again**. This is the row that justifies deleting the
`ALLOW_PAID_TESTS` bypass: the old design turned one decision into a
session-wide unlock, while approval now covers exactly one tool call.

Together with the allowlist result above, the two ways an approval could have
leaked — a standing permission rule, or the previous approval persisting — are
both closed by observation rather than by reading the code.

## Confirmed: `bypassPermissions` is blocked, not waved through

The most important row, because it is the adversarial one: that mode exists to
skip confirmations, and the session also had `Bash` and `PowerShell` granted
outright. Every other safeguard was off, so the result is the hook alone.

```
Not run · permission denied
│ Reason: PreToolUse:PowerShell hook error: 유료 API 를 호출할 수 있는 테스트라 막았습니다.
PreToolUse:PowerShell says: 유료 테스트 실행을 막았습니다.
```

`ran/` stayed empty — the paid test never executed. **Hook `deny` is honoured in
`bypassPermissions`.** The fail-closed branch in `_decision_for_mode()` is
therefore real protection and not a decorative default, which is exactly what
C3 of the earlier review demanded before the deny→ask change could be accepted.

Two observations from the same output, neither a problem:

- The harness presents a deny as `hook error`. That matches what
  `auto_test_check.py` already does with exit-code-2 blocks; it is a
  presentation detail, and the reason text still reaches the model intact.
- The assisting session offered to let the **user** run the command in their own
  shell instead. That is correct and by design: `PreToolUse` governs Claude's
  tool calls, not a person's terminal. The hook is a guard against accidental
  spend by the agent, not a lock on the human — and it did not attempt to
  circumvent itself.

## Confirmed: a non-interactive run does not execute the paid test

`claude -p` from the probe folder reported the hook had blocked the command and
asked for approval, and `ran/` was still empty afterwards — verified directly,
not taken from the agent's summary.

**One honest qualification.** The mode here was `default`, so the hook returned
`ask`, and what stopped execution was the harness declining to proceed on an
approval nobody could answer — not our `deny` branch. The payload gives the hook
no way to tell `-p` apart from an interactive `default` session, so this path
cannot be hardened from the hook side. The protection is real but partly
outside this hook's control, and that belongs in the knowledge document rather
than being reported as our own guarantee.

## Phase C — 승인 동작 확인 완료

| 확인 | 결과 |
|---|---|
| `default` 에서 승인창 | **확인됨**, 훅 문구 그대로 |
| 거절 → 표식 없음 | **확인됨** |
| 승인 → 표식 생성 | **확인됨** |
| 승인 뒤 재요청 → 다시 묻는다 | **확인됨** |
| `permissions.allow` 로 도구 통째 허용 → 그래도 묻는다 | **확인됨** |
| `bypassPermissions` → deny, 표식 없음 | **확인됨** |
| 비대화형 → 실행 안 됨 | **확인됨** (위 한정 조건 참고) |
| `acceptEdits`·`auto` 의 실제 승인창 | 미관찰. 단위 테스트로만 덮임 |
| `plan`·`dontAsk` | 미관찰. `plan` 은 다른 이유로 명령을 막아 귀속이 안 된다 |

The two unobserved rows are recorded as unobserved. They are covered by unit
tests over `_decision_for_mode()` and by the fail-closed default branch, which
is not the same as having been seen, and the knowledge document says so.

## Final gate, after all of the above

| Command | Exit | Result |
|---|---|---|
| `ruff check .` | **0** | All checks passed |
| `ruff format --check .` | **0** | 77 files already formatted |
| `pytest -q` | **0** | 374 passed |

## What is left

1. **Codex's final result review** of the code against the done criteria.
2. **Nothing is committed.** Every change from Rounds 1–3 and phases A–B is
   still uncommitted in the working tree, so the cleanup precondition
   "both temporary files exist in a verified Git commit" is unmet for every task
   in `tasks/`. F1 is unchanged.
3. **Probe cleanup** — deleting the probe folder. Kept for now in case Codex's
   review asks for another row.
4. The spec's exclusions held throughout: no other repository touched, no real
   paid API called, no marker added to this template's `[]`, no commit, no push.

---

# Handoff to Codex — what to review

Working tree at `release/v2`, HEAD `4f5300c`, **nothing committed**. 25 tracked
files modified, 729 insertions / 201 deletions, plus new files. Sorted by how
much attention each deserves, because most of the line count is mechanical.

## Behaviour changes — review these against the done criteria

| File | What changed |
|---|---|
| `.claude/harness/hooks/paid_test_check.py` | judgement inverted to "provably excludes all markers"; `_decision_for_mode()` + fail-closed default; `_deny()` → `_respond()`; `_policy()` 2-tuple; env bypass and `import os` removed; docstring rewritten |
| `.claude/harness.json` · `harness/schemas/harness.schema.json` | `allow_env` removed from both |
| `tests/_escape_hatches.py` | `ALLOW_PAID_TESTS` removed |
| `tests/test_paid_test_check.py` | +337 lines: config isolation (phase A), command table, mode table, ask/deny shapes, bypass-is-gone regression |
| `.claude/harness/hooks/_hookutil.py` | `_ARTIFACT_DIRS` excluded from both mtime scanners (Round 3 defect) |
| `.claude/harness/hooks/auto_test_check.py` | `.py` guard in the `tests/` branch (same defect, second line of defence) |
| `tests/test_hookutil.py` · `tests/test_auto_test_check.py` | regression tests for that defect |
| `tests/conftest.py` | comment only — the 2026-08-22 measurement kept, annotated |

**One change will not appear in any diff:** `.codex/hooks.json` is untracked, and
the `paid_test_check.py` entry was removed from it. Please inspect that file
directly. Codex's `PreToolUse` does not support `ask`, so leaving it wired would
have looked like protection while providing none.

## New files

`ruff.toml`, `requirements.txt`, `.claude/skills/handoff/SKILL.md`,
`tasks/_template.md`, `.claude/wiki/knowledge/paid-test-approval.md`,
`.claude/wiki/history/plan/2026-11-18-handoff-workflow.md`.

## Mechanical only — safe to skim

These changed solely because of the one-time `ruff format` adoption:
`_quality.py`, `history_check.py`, `prose_style_check.py`,
`scripts/openwork/collect.py`, `scripts/quiz/collect.py`,
`test_collect_openwork.py`, `test_heredoc_write_check.py`,
`test_hook_wiring.py`, `test_plan_interview_check.py`,
`test_prose_style_check.py`, `test_v2_templates.py`.

`AGENTS.md`'s 83 changed lines are the user's Korean translation of the file;
only the 4-line 작업 인수인계 section came from this work.

## Open items, carried forward rather than closed

- **F1** — `tasks/` is untracked, so no task can satisfy the Git-commit cleanup
  precondition. Unchanged and now blocking cleanup for four specs.
- **F2** — `tasks/_template.md` still has no named owner.
- **F7** — Round 3 (ruff config + the Fast-gate defect) ran with no task ID,
  contrary to `tasks/task-spec-identifiers.md`, which itself is still 구현 대기
  and unblocked.
- Round 3's format pass shifted line numbers in `paid_test_check.py` and its
  test. Citations in this spec were re-verified afterwards, but any new citation
  should be taken from the current files.
- Phase C rows for `acceptEdits`/`auto` and `plan`/`dontAsk` are unobserved, not
  passed.
- `tasks/_template.md`'s 「보안·비용 경계」 section proved its worth here; worth
  considering whether the spec template should also require naming which
  verification steps need a human.

---

# Round 4 — two bypasses from Codex's review, fixed

The spec was updated at 00:52 (+3 lines: one row in the command table, one
bullet in 함께 변경할 파일) requiring regression tests for two command shapes.
**Both were real leaks.** Each was reproduced against the current hook before
any code changed.

## Leak 1 — a shell comment disabled the check

```
pytest -m paid -q # --collect-only     →  통과 (should be 승인 필요)
```

`_COLLECT_ONLY_RE` searched the raw segment, so the words `--collect-only`
inside a comment satisfied the collect-only exception and the paid command was
waved through. The same path would have let a comment supply a decoy `-m`.

Fixed with `_strip_comment()`, which removes from an **unquoted** `#` to end of
segment, applied before any judgement. Quoted `#` is preserved so
`git commit -m "fix #123"` keeps working. Separately, the collect-only test now
runs on `_without_quoted(segment)`, so `-k "--collect-only"` inside a string is
no longer read as an option.

## Leak 2 — a quoted interpreter path with spaces was not recognised at all

```
& "C:\Program Files\Python\python.exe" -m pytest -m paid -q   →  통과
  "C:\Program Files\Python\python.exe" -m pytest -m paid -q   →  통과
```

`segment.split()` made the first token `"C:\Program`, whose basename is
`Program`, which matches no interpreter pattern — so `_runs_pytest()` returned
False and the hook never even looked at the markers. This is the worse of the
two: it is a plausible real-world path, not a contrived string.

Fixed with `_tokens()` using `shlex.split(posix=False)` — non-posix so Windows
backslashes are not treated as escapes and the quotes stay on the token for
`_basename()` to strip. Unbalanced quotes raise `ValueError`, which falls back
to the old `split()` rather than abandoning judgement.

## A process trap worth recording

My first re-test after fixing appeared to show both leaks still open. The cause
was the test script importing the hook from **the probe's copy**, which was made
by `cp` earlier and therefore predated the fix. The repository's hook was
already correct. The script now pins `sys.path` to the repository's hooks
directory while leaving `CLAUDE_PROJECT_DIR` on the probe for its marker policy,
and the probe's copies have been re-synced. Anyone re-running phase C should
copy the hook again first.

## Verification

| Command | Exit | Result |
|---|---|---|
| `pytest tests/test_paid_test_check.py -q` | **0** | 71 passed (64 before) |
| `ruff check .` | **0** | All checks passed |
| `ruff format --check .` | **0** | 77 files already formatted |
| `pytest -q` | **0** | **381 passed** (374 before) |

Seven new cases, four of them guarding against the opposite error:
`git commit -m "fix #123 paid"` (quoted `#` is not a comment),
`pytest -m 'not paid and not paid2' # 주석` (a comment does not make a safe
expression unsafe), and the quoted-space-path spelling of a safe invocation.
Blocking the hook's own false positives matters as much as closing the leaks —
a hook that stops `git commit` gets switched off within a day.

## Status after Round 4

- **코드·자동 검증: 완료.** 381 passed, both leaks closed with regression cover.
- **C단계: 이전 확인 그대로 유효, 그리고 주석 케이스는 실측으로 확인됨.**

## Live confirmation of the comment fix

The comment command was run in a probe session and **produced the approval
dialog**, with `ran/` empty afterwards. This is the strongest single result in
the whole task: before Round 4 that exact command would have executed the paid
test with no prompt at all, because the hook read `--collect-only` out of the
comment.

The spaced-path shape remains judgement-only (unit tests plus the direct
`blocked_reason()` probe); it was not run live, since the path in it is
deliberately fictional and a live run would only produce a "file not found".

### Methodology note — the agent's caution can hide the result

The first live attempt was **inconclusive, not a failure**, and the reason is
worth recording for anyone re-running phase C.

Asked to run the comment command, the assisting session did not run it. It
reasoned about the comment itself, concluded the paid test would execute,
substituted a `--collect-only` invocation, and then asked the user in prose
whether to proceed. `ran/` stayed empty — correct behaviour, but the hook never
saw the original command and therefore judged nothing. Reading that as "the hook
didn't ask" would have been wrong.

The decisive run needed a prompt demanding verbatim execution: *"Run this
verbatim, exactly as written. Do not modify it, do not substitute
--collect-only."*

Two things follow. First, a probe prompt must forbid substitution, or the
measurement is of the agent's judgement rather than the hook's. Second, the
agent's caution is a genuine second layer — it caught the comment trick
independently — but it is judgement, not a guarantee: it varies with phrasing,
model and context. The hook is the layer that does not change its mind, which is
the reason it exists.

- Nothing committed. F1, F2, F7 unchanged.

---

# Round 4b — a leak I introduced while fixing Round 4

Probing my own fix before handing it over found a third leak, this one mine.

```
& "C:\Program Files\Python\python.exe -m pytest -m paid -q   →  통과 (LEAK)
```

Note the missing closing quote. `shlex.split()` raises `ValueError` on that, and
my fallback was `segment.split()` — **the exact code path Round 4 existed to
fix.** So an unbalanced quote restored the leak: first token `"C:\Program`,
basename `Program`, no interpreter match, markers never consulted.

Falling back to the old behaviour was the wrong direction. `_tokens()` now
returns `None` on a parse failure, and `_runs_pytest()` treats an unparseable
segment as pytest when the word `pytest` appears in it, leaving the marker
judgement to decide. A false positive on a malformed command costs one
unnecessary dialog; a leak costs a real API call, and only one of those is
reversible.

Nine edge cases now pass, including the opposite-error guards that matter most:
`git commit -m "fix #123 paid"`, `echo 'pytest -m paid'`, and
`pytest --collect-only -m paid # 설명`. Two unbalanced-quote shapes and the
mixed-quote comment are locked in as regression tests.

| Command | Exit | Result |
|---|---|---|
| `ruff check .` | **0** | All checks passed |
| `ruff format --check .` | **0** | 77 files already formatted |
| `pytest -q` | **0** | **386 passed** |

The probe's hook copies were re-synced afterwards.

## Handoff map — delta since the map above

Only these two files changed in Rounds 4 and 4b:

- `paid_test_check.py` — `+import shlex`, `+_strip_comment()`,
  `+_without_quoted()`, `+_tokens()`, the unparseable-segment branch in
  `_runs_pytest()`, and `_paid_reason()` now strips comments first and tests the
  collect-only exception on the unquoted copy.
- `tests/test_paid_test_check.py` — 12 new cases across both rounds, roughly
  half of them false-positive guards.

Everything else in the earlier map stands.

### Where I would most like a second opinion

1. **The two quote state machines.** `_strip_comment()` and `_without_quoted()`
   track one quote character at a time, so a `'` inside a `"…"` span is treated
   as literal. I believe that is correct for both cmd and PowerShell, but it is
   hand-rolled parsing and that is where this kind of code goes wrong.
2. **The unparseable-segment branch widens detection.** Is "the word `pytest`
   appears" the right trigger, or too broad? It is the one place Round 4b traded
   precision for safety.
3. **`-c` and `-o` are still matched on the comment-stripped raw segment**, not
   the unquoted copy. Deliberate: a `-c` inside a quoted string produces one
   harmless extra ask. Flagging it so it reads as a choice, not an oversight.
4. **Known residual, by design.** A paid invocation that never contains the word
   `pytest` — a wrapper script, an alias, a variable holding the whole command —
   is not detectable statically and is out of scope, as the knowledge document
   already states.

---

# Round 5 — three more leaks from Codex, fixed

The spec gained one bullet at 01:15 naming three shapes. **All three leaked**,
each reproduced before any code changed. They landed exactly where I had asked
for a second opinion, on the hand-rolled quote and boundary handling.

| Command | Was | Cause |
|---|---|---|
| `pytest ./foo# -m paid -q` | 통과 | `_strip_comment()` cut at **any** unquoted `#`, so the trailing `-m paid` disappeared — comment stripping became a bypass |
| `pytest -m paid ./--collect-only -q` | 통과 | `_COLLECT_ONLY_RE`'s `(?<![\w-])` did not exclude `/`, so a **path named** like the option bought the collect-only exception |
| ``pytest -m paid -q -o "junit_suite_name=x`"--collect-only"`` | 통과 | PowerShell's backtick escape was unknown to the quote tracker, so the quote looked closed early and the following text counted as unquoted |

Fixes:

- `#` only starts a comment at a **token boundary** (start of segment or after
  whitespace). cmd, PowerShell and bash all agree; my original version did not.
- `_COLLECT_ONLY_RE` now requires `^` or whitespace before `--`, so only a real
  option token counts.
- Quote tracking moved into one shared `_walk()` generator that understands the
  backtick escape inside double quotes, and `_strip_comment()` /
  `_without_quoted()` are both built on it. One copy, for the reason this
  repository gives everywhere else: two copies drift and the gap becomes the
  bypass. Backslash is deliberately **not** an escape, because Windows paths
  live inside double quotes.

Seven new regression cases, three of them false-positive guards
(`pytest -m paid --collect-only`, `pytest ./foo# -m 'not paid and not paid2' -q`).

| Command | Exit | Result |
|---|---|---|
| `ruff check .` | **0** | All checks passed |
| `ruff format --check .` | **0** | 77 files already formatted |
| `pytest -q` | **0** | **392 passed** |

All nine Round 4/4b edge cases still pass. Probe hook re-synced.

**Running total: six real bypasses in this hook** — two found by Codex in
Round 4, one by me reviewing my own fix in 4b, three by Codex in Round 5. The
test suite was green at every point in between. It was green because it tested
what the author had thought of, which is the argument for the review loop rather
than for more tests written by the same person.

## Knowledge document brought up to date

`.claude/wiki/knowledge/paid-test-approval.md` was written at the end of phase B
and therefore predated all three of those rounds — its judgement table said
`--collect-only` passes, with none of the conditions that turned out to matter.
Left alone it would have been the worst kind of stale: a durable document
stating a contract the code no longer honours.

It now carries a 명령을 읽는 규칙 section with the eight parsing rules and the
reason for each, because that is where every one of the six bypasses actually
lived — not in the judgement logic but in how the command string was read. The
`--collect-only` row is qualified with 진짜 옵션일 때만, and shell comments have
a row of their own.

No code changed for this, so the Round 5 gate numbers above still stand.

---

# Round 5 live verification — attempted here, cannot be done here

Direction received: sync the probe to commit `d413f3b`, then request Round 5's
three commands verbatim through Claude's PowerShell tool, checking that no
execution marker exists before approval and that declining prevents execution.

## Done

- Probe synced to `d413f3b`. Both `paid_test_check.py` and `_hookutil.py` in the
  probe are **byte-identical** to that commit, compared with `git show`.
- `ran/` empty before starting.
- F1 is resolved: `tasks/` is committed (`9ce72f8`, `51ba164`, `d413f3b`). The
  working tree is clean apart from the still-untracked `.agents/` and `.codex/`
  — note that the `.codex/hooks.json` change from Round 4 is inside that
  untracked directory and therefore is **not** in any commit yet.

## The attempt, and why it cannot work from this session

Requested verbatim through the PowerShell tool:

```
C:\my-harness\.venv\Scripts\python.exe -m pytest -m paid -q # --collect-only
→ exit 5, "392 deselected in 0.09s", no confirmation dialog, command executed
```

**No dialog, and that is correct.** The hook resolves its project root from
`CLAUDE_PROJECT_DIR` before `os.getcwd()` (`_hookutil._find_root()`), and in this
session that variable points at `C:\my-harness`, whose
`checks.expensive_tests.pytest_markers` is `[]`. Measured directly:
`PROJECT_ROOT = C:\my-harness`, `_PAID_MARKERS = ()`,
`blocked_reason("pytest -m paid -q") = None`.

`cd` cannot change this. The hook process is spawned by the harness with the
session's environment, not by Claude, so from a session rooted at this
repository the hook is silent for every command. The three Round 5 commands
would all execute with no dialog here, and recording that as a Round 5 result
would be the same error this review has already caught twice.

This row *is* worth keeping as a contract observation, just not as the
verification: **a project that configures no paid markers is not interfered
with.** That is the template's own state and the reason this repository can run
`pytest -m paid` freely.

## A real finding from that one run

The output says `392 deselected`, with no "collected" line — so `-m paid` was
applied and `--collect-only` was **not**. PowerShell stripped `# --collect-only`
as a comment before pytest ever saw it.

That makes the Round 5 comment leak concrete rather than theoretical. Before the
fix, the hook read `--collect-only` out of that comment and treated the command
as collect-only — while the shell discarded the comment and pytest ran with
`-m paid` for real. The exception the hook granted had no counterpart in what
actually executed.

## What remains, and the exact requests to use

The three commands have to be requested in a session whose project **is** the
probe, because that is where the marker policy lives. The prompts must forbid
substitution — Round 4's methodology note explains why: an assisting session
once rewrote the command to `--collect-only` on its own, and the hook then had
nothing to judge.

For each one: confirm `ran/` is empty beforehand, watch for the hook's
confirmation, **decline**, then confirm `ran/` is still empty.

```
1. Run this verbatim, exactly as written. Do not modify or substitute it:
   C:\my-harness\.venv\Scripts\python.exe -m pytest -m paid -q # --collect-only

2. Run this verbatim, exactly as written. Do not modify or substitute it:
   C:\my-harness\.venv\Scripts\python.exe -m pytest -m paid ./--collect-only -q

3. Run this verbatim, exactly as written. Do not modify or substitute it:
   C:\my-harness\.venv\Scripts\python.exe -m pytest -m paid -q -o "junit_suite_name=x`"--collect-only"
```

Command 2 names a path that does not exist and command 3 sets a harmless ini
value, so approving either would only produce a pytest error — the dialog is the
whole result. Command 1 is the one that would really have run the paid test
before the fix, so it is the one worth approving once as well, to confirm the
marker appears only after approval.

No real paid API is involved in any of them: the probe's `paid` tests write a
file and nothing else.

## Result — all three asked, none executed

Run by the user in the probe session, hooks byte-identical to `d413f3b`
(re-verified after the run).

| Round 5 shape | 승인창 | 거절 후 실행 |
|---|---|---|
| `… -m pytest -m paid -q # --collect-only` | 떴다 | 없음 |
| `… -m pytest -m paid ./--collect-only -q` | 떴다 | 없음 |
| ``… -m pytest -m paid -q -o "junit_suite_name=x`"--collect-only"`` | 떴다 | 없음 |

`ran/` was verified directly afterwards and the directory **did not exist at
all** — so no test body ran under any of the three, not even the free `unit`
one.

All three were leaks before Round 5: each would have been granted the
collect-only exception or gone unrecognised entirely, and each would have
executed `-m paid` for real. They now reach the user as a per-call
confirmation, and declining stops them.

Attribution note, consistent with the rest of this review: the dialogs were not
pasted this time, so "it was our hook rather than the generic Bash
confirmation" rests on the user's report. That report is credible here — the
verbatim hook text was captured earlier for this same project and hook, and the
generic confirmation offers an always-allow option while the hook's does not.
The `ran/` state is first-hand.

Not re-observed: approving command 1 to watch `ran/paid` appear only after
approval. That row was already confirmed in phase C with a different paid
command, so it is covered, just not for this particular spelling.

## Phase C and Round 5 verification: complete

Observed: the confirmation appears, declining prevents execution, approving
permits it, approval does not carry to the next call, a tool-wide permission
grant does not bypass it, `bypassPermissions` is denied rather than waved
through, a non-interactive run does not execute, and all three Round 5 shapes
ask. Unobserved and recorded as such: `acceptEdits`/`auto` dialogs and
`plan`/`dontAsk`, covered by unit tests over `_decision_for_mode()` only.

---

# Handoff — current state, superseding the earlier map's baseline

**The "Handoff to Codex" map above opens with "HEAD `4f5300c`, nothing
committed". That is now stale.** Read this section's baseline instead; the map's
file-by-file breakdown is still accurate as a guide to *what* changed.

| | |
|---|---|
| HEAD | `d413f3b` |
| Commits since `4f5300c` | `9ce72f8` docs, `51ba164` build, `d413f3b` feat |
| Range | 39 files, +3445 / −205 |
| Uncommitted | `tasks/hook-dicision.review.md` (this file, still in use), plus untracked `.agents/` and `.codex/` |

## Correction: `.codex/` is not a distribution gap

An earlier note in this session claimed the uncommitted `.codex/hooks.json`
change meant "the next person's checkout keeps the Codex wiring". **That was
wrong.** The whole `.codex/` directory is untracked, so a clone receives neither
the directory nor any Codex hook configuration — there is no stale wiring to
inherit.

Verified: `.codex/hooks.json` in this working copy contains zero occurrences of
`paid_test_check`, so the Round 4 removal is present locally and in no commit.

The real open question is narrower and belongs to
`tasks/template-history-cleanup.md`, not here: whether `.codex/` should be
tracked at all. Until it is, Codex's hook configuration is per-machine and
cannot be reviewed from the repository.

## Round 5 delta since the earlier map

Two files beyond what that map lists:

- `paid_test_check.py` — `+_walk()` (one shared quote/escape tracker, backtick
  aware), `_strip_comment()` now requires a token boundary, `_COLLECT_ONLY_RE`
  now requires `^` or whitespace before `--`.
- `tests/test_paid_test_check.py` — 7 further cases, three of them
  false-positive guards.

Plus `.claude/wiki/knowledge/paid-test-approval.md`, which gained the
명령을 읽는 규칙 section after the three rounds had made its original judgement
table stale.

**Current gate after Round 8: `ruff check` 0, `ruff format --check` 0,
`pytest -q` 402 passed.** Beyond the Round 6 delta above, two more rounds landed
in `paid_test_check.py` and its test file:

- **Round 7** deleted the collect-only exception, and with it
  `_COLLECT_ONLY_RE` and `_without_quoted()`. Three tests moved from the free
  lists to the approval lists; that is the behaviour change made visible.
- **Round 8** added `_escapes_next()` as the single escape decision, extended
  escaping to outside quotes, and made `_strip_comment()` treat an escaped space
  as a non-boundary.

The knowledge document was rewritten in both rounds and is current.

## What a final review should weigh

1. **All nine bypasses were in command-string *reading*, none in the judgement
   logic.** Whether the parsing rules in the knowledge document are the right
   contract is the main design question left.
2. **Does comment stripping still earn its place?** Eight of the nine bypasses
   attacked the collect-only exception, which Round 7 removed. CDEX-08 is the
   first that did not need it — it attacks `_strip_comment()` directly. That
   leaves comment handling as the only remaining shell-parsing surface, and
   every parsing rule here has now leaked at least once. Deleting it would cost
   spurious approvals when a real comment happens to contain `-m paid`, and
   would remove the surface entirely. This is a judgement call for the spec
   owner, not something to settle from the implementation side.
3. **Constructs still unexamined**, each a candidate for the same class of
   defect: command substitution (`$(...)`, a backtick pair outside quotes), a
   `;` or `&&` inside a quoted string, line continuations (`^` in cmd, trailing
   `` ` `` in PowerShell, trailing `\` in Bash), the `--` argument separator,
   and pytest's `@file` argument form.
3. `_walk()`'s escape handling: backtick inside double quotes, and backslash
   **only before a quote character**. The reasoning and the accepted cost
   (`"C:\dir\"` reads as unterminated) are in its docstring.
4. The unparseable-segment branch trades precision for safety. It is the one
   place that deliberately over-asks.
5. `acceptEdits`/`auto` and `plan`/`dontAsk` are unobserved, not passed.
6. F2 and F7 remain open. F1 is closed by the commits above.

---

# Round 7 — the exception itself is gone

Spec line 101 was rewritten: the collect-only exception does not apply to a
command that selects paid markers or overrides the default exclusion, because
the two shells' quoting and escape rules cannot be settled by string inspection
at a cost boundary. `paid_test_check.py:347` was where that exception lived.

This is a design change, not another patch, and it is the right one. **All eight
bypasses were attacks on that single exception** — the comment, the
`./--collect-only` path name, the quoted string, the PowerShell backtick, the
Bash backslash. Each was an attempt to answer "is this `--collect-only` a *real*
option?" from the command text. Removing the question removes the target.

## What changed

- The collect-only check is deleted from `_paid_reason()`.
- `_COLLECT_ONLY_RE` and `_without_quoted()` were used only there, so both are
  gone. No dead code left behind.
- `_walk()` stays, and its justification is now narrower and stated as such:
  quote tracking exists for **comment detection**. If a quote looks closed too
  early, a following `#` is mistaken for a comment and the command is truncated
  — and a truncation that removes `-m paid` makes a paid command look free. The
  two escape rules are kept for that reason, not for the removed exception.
- Module docstring, the knowledge document's judgement table, and its parsing
  table all rewritten. The knowledge document gained a section stating why the
  exception was dropped and what it costs.

## The cost, stated plainly

One thing gets worse: `pytest --collect-only -m paid`, which genuinely incurs no
charge, now asks. That is a real regression in convenience for anyone listing
paid tests. It was accepted deliberately — a spurious dialog costs a keystroke,
and the alternative is maintaining a string-level answer to a question two
shells disagree about.

Safe calls are unaffected, because they never needed the exception:
`pytest --collect-only -q` and
`pytest --collect-only -m 'not paid and not paid2'` pass on their own merits.

## Verification

| Command | Exit | Result |
|---|---|---|
| `ruff check .` | **0** | All checks passed |
| `ruff format --check .` | **0** | 77 files already formatted |
| `pytest -q` | **0** | **398 passed** |

Three tests moved from the free lists to the approval lists, which is the
behaviour change made visible: `pytest --collect-only -m integration`,
`pytest -m paid --collect-only`, `pytest --collect-only -m paid # 설명`. Two new
free cases pin the other side — a collect-only call that selects nothing paid
still passes. The Fast gate caught each of the three as I went, which is the
cleanest evidence that the change does what the spec asked.

Also fixed in passing: that edit duplicated two rows in the knowledge
document's parsing table. Caught on re-read and removed.

---

# Round 8 — CDEX-08, and the first bypass proved by execution

Spec line 153. The shape:

```
pytest -q -o junit_suite_name=x` # -m paid     (PowerShell)
pytest -q -o junit_suite_name=x\ # -m paid     (Bash)
```

The escape character takes the **space**, so `#` becomes part of the `-o` value
rather than starting a comment — and the `-m paid` after it is a genuine option.
`_strip_comment()` saw an unquoted `#` after whitespace, truncated there, and
the real `-m paid` vanished with the comment. The command then looked free.

Round 6 taught `_walk()` about escapes, but only **inside double quotes**. This
one escapes outside quotes, so none of that applied. Line 232 — the `_walk()`
loop in `_strip_comment()` — was where it landed.

## Proved by execution, not by argument

This is the first round where the threat was demonstrated end to end rather than
reasoned about. Paired, as the spec asked: hook verdict alongside a real shell
run in a no-cost project whose `paid` test writes a marker file.

| | hook | `ran/` after a real shell run |
|---|---|---|
| CDEX-08 Bash | `pass` | **`paid`** |
| CDEX-08 PowerShell | `pass` | **`paid`** |
| genuine comment, both shells | `pass` | `unit` only |
| plain `pytest -q` | `pass` | `unit` only |

The two `paid` markers are the finding: the shell really did hand `-m paid` to
pytest and the body really did run, while the hook said the command was free.
The controls confirm the other direction — where the `#` genuinely is a comment,
the shell drops `-m paid` too, so passing it is correct.

### My first attempt at this measurement was itself wrong

The initial script reported all five cases safe with no markers. Nothing had
run: `bash` ate the backslashes in `C:\my-harness\.venv\...`, so the command was
never a valid invocation. An unexecuted command leaves no marker, which looks
exactly like protection.

The script now refuses to report a verdict unless the output proves pytest
actually ran, and uses forward-slash paths for the Bash cases. Worth recording
because it is the same failure this review keeps meeting: a check that cannot
fail is not a check, and "no evidence of harm" is not evidence of safety.

## The fix

Escaping is now decided in one place, `_escapes_next(ch, following, quote)`:

- Backtick escapes everywhere except inside single quotes.
- Backslash escapes **outside** quotes broadly, and **inside** double quotes
  only before a quote character — the narrow rule from Round 6 that keeps
  `"C:\Program Files\python.exe"` intact.
- Single quotes escape nothing, in either shell.

`_strip_comment()` now tracks whether the preceding character was protected, so
an **escaped space is not a token boundary** and a `#` after one is not a
comment. Path separators outside quotes pick up a protection flag as a side
effect, which is harmless: the characters are still emitted unchanged.

## Verification

| Command | Exit | Result |
|---|---|---|
| `ruff check .` | **0** | All checks passed |
| `ruff format --check .` | **0** | 77 files already formatted |
| `pytest -q` | **0** | **402 passed** |

Four new cases: the two CDEX-08 shapes, plus two guards that a genuine comment
is still stripped — important now that escaping is interpreted more widely. All
eight cases from the earlier escape probe still pass; the one that changed
expectation did so because of Round 7's removal of the collect-only exception,
not a regression.

The knowledge document's escape rows were corrected: they claimed escapes apply
only inside double quotes, which this round makes false.

**Running total: nine real bypasses.** Eight were attacks on the collect-only
exception, which Round 7 deleted outright. CDEX-08 is the first that did not
need it — it attacks comment stripping directly, which means removing the
exception narrowed the surface but did not close it. The remaining surface is
`_strip_comment()`, and the open question for review is whether comment handling
earns its place at all given that every shell-parsing rule here has now leaked
at least once.

---

# Round 6 — the Bash half of the escape problem

Codex pointed at `paid_test_check.py:185`, the line where a quote closes. The
finding: this hook is wired to **`Bash|PowerShell`**, and Round 5 taught
`_walk()` only PowerShell's backtick. Bash escapes with a backslash, which
Round 5 deliberately excluded to protect Windows paths — so the same trick
survived in the other shell.

Reproduced before changing anything:

```
pytest -m paid -q -o "junit_suite_name=x\"--collect-only"   →  통과 (LEAK)
pytest -m paid -q -k "a\" --collect-only"                   →  통과 (LEAK)
```

Same mechanism as the backtick case: the tracker reads `\"` as a closing quote,
so everything after it counts as unquoted, and `--collect-only` is then seen as
a real option.

## The fix had to be narrow

Treating every backslash as an escape would break exactly what Round 5 was
protecting — `"C:\Program Files\Python\python.exe"` would have `\P` consumed as
an escape. So a backslash now escapes **only when the next character is a quote
character**. Path separators are followed by letters and stay literal; `\"`
cannot close a quote.

One accepted cost: a path ending in a separator, `"C:\dir\"`, now looks like an
unterminated quote. `_tokens()` then fails and the judgement falls to the
conservative branch, so the failure direction is "ask", not "miss".

Controls confirm both sides: the two leaks now ask, while
`& "C:\Program Files\Python\python.exe" -m pytest -m "not paid and not paid2"`
and `pytest -m "not paid and not paid2" --rootdir "C:\x\y"` stay free. Eight of
eight cases correct, and the PowerShell backtick case is unchanged.

| Command | Exit | Result |
|---|---|---|
| `ruff check .` | **0** | All checks passed |
| `ruff format --check .` | **0** | 77 files already formatted |
| `pytest -q` | **0** | **396 passed** |

Four new regression cases: the two Bash shapes, and two Windows-path guards
that would fail if the escape rule were widened again. The knowledge document's
parsing table was corrected in the same change — it had said "역슬래시는
이스케이프로 보지 않는다", which this round makes false.

Probe hooks re-synced to the working tree.

**Running total: eight real bypasses**, every one of them in how the command
string is read rather than in the judgement logic. Round 5 fixed the backtick
and left its mirror image in the other shell — a reminder that "fixed for the
shell I was thinking about" is not fixed, and that the matcher in
`settings.json` (`Bash|PowerShell`) is part of this hook's contract.


# Round 9 — the preprocessing step is gone

Round 8's fix worked. CDEX-08 asked afterwards and the suite was green. This
round removes the thing it fixed, per the design decision in
`hook-dicision.md`.

`_strip_comment()` ran before every judgement in `_paid_reason()`. Its purpose
was to stop characters inside a comment from flipping the verdict. Its rules
were patched three times:

| Patch | What it was for |
|---|---|
| `#` is a comment only at a token head | `pytest ./foo# -m paid -q` was cut to `pytest ./foo`, dropping a real `-m paid` |
| `#` inside quotes is not a comment | `git commit -m "fix #123"` must not be truncated |
| An escaped space is not a token boundary | CDEX-08 |

Three patches, each failing the same way: proving a shell's comment boundary
from the command string alone. Round 8 was the third, and it was correct. The
decision is that a fourth is not worth waiting for.

## What changed

`_paid_reason()` now reads the segment verbatim. `_strip_comment()`, `_walk()`
and `_escapes_next()` are gone — they called only each other, so the hook drops
62 lines (+27 / -89). The remaining string interpretation is `shlex`
tokenization and first-token executor identification; both already fail toward
"ask".

CDEX-08 is caught without interpreting either shell's escaping: `-m paid` is
simply visible in the raw text.

## The cost, stated plainly

Two commands that cost nothing to run now ask:

```
pytest -q # -m paid
pytest -q -o junit_suite_name=x # -m paid
```

The shell does treat these as comments, so no paid body runs. The hook asks
anyway. This is the accepted false positive, and it is now a regression test
rather than a known gap.

The blast radius is small. A command whose raw text proves every paid marker is
excluded stays free whatever its comment says — `pytest -m 'not paid and not
paid2' # 설명` does not ask. Only a raw text that *selects* a paid marker can
trigger the false positive, so `pytest -q` and every safe expression are
untouched.

Note the direction of the old error. The comment rules were not merely
incomplete; in CDEX-08 they were wrong the *other* way — an escaped space put
`#` inside an option value, and stripping cut a genuine `-m paid`, so a paid
body ran with no approval. Trading that for one extra prompt is not a
like-for-like trade.

## Verification

A throwaway project (markers `paid`/`paid2`, bodies that only touch a marker
file, no billing) driving the real hook process over stdin:

| Group | Cases | Result |
|---|---|---|
| Must ask | 7 | all `ask` |
| Must not ask | 7 | all silent (allow) |
| `plan` / `bypassPermissions` / missing mode | 3 | all `deny` |

Then the same commands through each shell, reading which tests actually ran:

| Shell | Command | Ran | Reading |
|---|---|---|---|
| PowerShell | `pytest -q # -m paid` | `unit` | real comment — the false positive costs nothing |
| PowerShell | ``pytest -q -o junit_suite_name=x` # -m paid`` | `paid` | CDEX-08 — the hook must ask |
| Bash | `pytest -q # -m paid` | `unit` | real comment |
| Bash | `pytest -q -o junit_suite_name=x\ # -m paid` | `paid` | CDEX-08 |

So the claim written into the knowledge document — that the shell does not pass
`-m paid` to pytest in the commented form — is measured, not argued.

| Command | Exit | Result |
|---|---|---|
| `ruff check .` | **0** | All checks passed |
| `ruff format --check .` | **0** | 78 files already formatted |
| `pytest -q` | **0** | **402 passed** |

The two false positives moved from `FREE` to `NEEDS_APPROVAL`; the stale
rationale comments that referenced comment stripping were rewritten to describe
what the code now does. `knowledge/paid-test-approval.md` keeps only the current
rules: the comment row, a reading-rules table without the escape machinery, and
an "accepted false positive" section. The reasoning and the rejected
alternatives went to Plan History
(`.claude/wiki/history/plan/2026-11-19-paid-hook-comment-stripping.md`), since
these `tasks/` files are deleted at cleanup.

**Running total: eight real bypasses, all eight in how the command string is
read.** Rounds 5 through 8 each narrowed that reading correctly and were each
followed by another case. Round 9 removes the reading instead of narrowing it
again, and pays one false positive for it.

Out of scope here, still open in `hook-dicision.md`: the `.codex/hooks.json`
entry, the README application example, and the Fast/Full argv exclusions.

## Files changed, checks not run, and deltas from the spec

Changed:

- `.claude/harness/hooks/paid_test_check.py` (+27 / -89) — `_paid_reason()`
  reads the raw segment; `_strip_comment()`, `_walk()` and `_escapes_next()`
  deleted; the module docstring and the comment above `_paid_reason()` record
  why the stage is gone, so it does not come back as a fix.
- `tests/test_paid_test_check.py` (+42 / -12) — the two real-comment commands
  moved `FREE` → `NEEDS_APPROVAL`; three rationale comments that explained a
  verdict by comment stripping now describe what the code does.
- `.claude/wiki/knowledge/paid-test-approval.md` (+38 / -13) — comment row
  inverted, escape-rule table dropped, `받아들인 오탐` section added.
- `.claude/wiki/history/plan/2026-11-19-paid-hook-comment-stripping.md` — new;
  problem, options, decision, reasons, four rejected alternatives, measurements.
- This file. `hook-dicision.md` is untouched — Codex owns it.

Not run, and why:

- No paid body ran against a billing provider. The throwaway project's
  `paid`/`paid2` tests only append to a marker file, so "`paid` ran" in the
  tables above means that dummy. That is what makes the CDEX-08 measurement
  safe to repeat on demand.
- The Fast profile was not run separately; the Full profile is a superset of it
  and is green.
- The README application example and the Fast/Full argv exclusions were not
  exercised. They are separate items in the spec and nothing in this round
  touches them, so the temp project checked the hook and the two shells only.
- `.codex/hooks.json` was not changed, and did not need to be. The user
  checked it: the paid-test hook entry is already absent and the other hooks
  are intact, so the spec item was already satisfied. `.codex/` stays out of
  Git by decision — `ce4b701` records both `.agents/` and `.codex/` in
  `.gitignore` with the reason, so the Codex hook config is per-machine
  deliberately rather than by omission, and Knowledge says so. Nothing about
  that file is open.

Deltas from the spec: none. The decision asked for the raw segment to reach
`_paid_reason()`, the three helpers removed if unused elsewhere, the contract
pinned in regression tests, a verdict-and-shell check in a cost-free project,
and the approval scope plus this false positive left in Knowledge as the
current contract. All six are done, and the helpers were in fact unused outside
each other.

## Correction — the spec moved, and it widened the contract

An earlier draft of this round flagged two rows in `hook-dicision.md` as
explaining a verdict by the mechanism this round removed. That note is
withdrawn: the spec revision in the working tree had already rewritten both the
`--collect-only` row and the `Bash의 \"` row to argue from the raw text. Reading
a stale copy was my error, not the spec's.

That same revision names three commands the earlier draft did not cover:

```
pytest -q # -m unit
pytest -q # -c other.ini
pytest -q # -o addopts=
```

These select no paid marker, so the accepted false positive is wider than "a
comment that selects a paid marker" — it is **any text that could override the
default exclusion**, comment or not. The implementation already behaved this
way (an unproven `-m`, a `-c` config switch and an `addopts` override are each
checked against the raw segment); all three return `ask` when driven through
the real hook. What was missing was the contract: they are now regression cases
in `NEEDS_APPROVAL`, and the scope sentence in `knowledge/paid-test-approval.md`
and in Plan History has been corrected, since both said the false positive
arises only when the raw text selects a paid marker.

Controls for the other side: `pytest -q # 설명` and `pytest -q # --collect-only`
stay free, so an ordinary comment still costs nothing.


# Final review — approved, three wordings corrected

Codex approved the code review for `hook-dicision`: `860fd7b` and `ce4b701` are
on `release/v2`, the new comment cases return the right verdicts, the
`.agents/`/`.codex/` exclusions are in place, and the full gate passes. No
further implementation round. Three statements in the permanent documents were
too strong, and each one is corrected after checking it against the hook rather
than against the review line.

**1. "A safe marker expression passes whatever the comment says."** Wrong, and
the hook disagrees:

```
pytest -m 'not paid and not paid2' # 설명          -> allow
pytest -m 'not paid and not paid2' # -m unit       -> ask
pytest -m 'not paid and not paid2' # -c other.ini  -> ask
pytest -m 'not paid and not paid2' # -o addopts=   -> ask
```

`_MARKER_RE` scans the whole segment and the loop asks on the first value it
cannot prove, so a safe expression in front does not license what follows it.
The boundary is "nothing anywhere in the raw text could override the default
exclusion", not "a safe expression appears". Corrected in
`knowledge/paid-test-approval.md` and in Plan History.

**2. "Tokenization and executor identification both fail toward ask."** True of
tokenization, false of executor identification:

```
./run_tests.sh -m paid    -> allow
bash run_tests.sh -m paid -> allow
make test -m paid         -> allow
```

`_runs_pytest()` ends in `return False`, so an unrecognized first token is not
judged at all. Only pytest, a python interpreter, the known runners and a
variable head reach the judgement. This is a pre-existing limit, already listed
under 「감지하지 못하는 것」, and this round did not change it — but Plan History
should not have claimed the safe direction for it. Corrected.

**3. The `.codex/` tracking memo.** Decided by `ce4b701`: both `.agents/` and
`.codex/` stay untracked, recorded in `.gitignore` with the reason. The memo no
longer says it is open.

## One spec item discharged while confirming the above

`hook-dicision.md` asked for a check this round had not run: that the README
application example and the Quality subprocess path exclude paid tests *without*
the hook, since that pytest runs as a subprocess and never reaches
`PreToolUse`. Run in the throwaway project:

| Invocation | Result |
|---|---|
| `pytest -q` (relies on `addopts`) | 1 passed, **2 deselected** |
| `pytest -m "not paid and not paid2" -q` (Fast/Full argv) | 1 passed, **2 deselected** |

So that path is protected by the configured default exclusion, not by this
hook — now stated in Knowledge, where it is a current fact rather than a
round's finding.

Gate after the corrections: `ruff check` clean, `ruff format --check` clean,
**405 passed**.

## Cleanup

Everything worth keeping is in permanent documents: the current contract in
`knowledge/paid-test-approval.md`, the decision with its rejected alternatives
in `history/plan/2026-11-19-paid-hook-comment-stripping.md`, the `.codex/`
decision in `history/plan/2026-11-19-codex-dir-tracking.md`. The eight bypasses
and the round-by-round history live on in the commits. With this report
committed, `hook-dicision.md` and this file are removed per step 9 of the
handoff procedure.
