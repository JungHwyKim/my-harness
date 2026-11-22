# Doctor spec review (pre-implementation)

- Task ID: `doctor`
- Spec: `tasks/doctor.md` (working-tree version, uncommitted; `Codex 명세 재검토 — 2026-11-22` section present)
- Reviewer: Claude Code (Opus 5)
- Date / revision: 2026-11-22 · `C:\my-harness`, `main` / `bd89a04`, working tree has only `M tasks/doctor.md`
- Stage: procedure step 3 (spec reviewed against current code). No implementation started, no files created
  other than this review.

## Scope of this review

Read in full: `tasks/doctor.md`, `.claude/skills/handoff/SKILL.md`, `.claude/harness/schemas/harness.schema.json`,
`.claude/harness/hooks/_hookutil.py`, `.claude/harness/hooks/_quality.py`, `.claude/settings.json`,
`.claude/harness.json`, `.claude/wiki/knowledge/quality-env.md`, relevant regions of
`auto_test_check.py`, `pre_commit_check.py`, `prose_style_check.py`, `heredoc_write_check.py`,
`tests/conftest.py`, `tests/test_hook_wiring.py`, `README.md`.

Edge cases were executed with the configured interpreter (`.venv/Scripts/python.exe`) against the live
hook modules — results are quoted inline under each finding. No project file was modified.

## Every citation in the spec checks out

All line references in `## 기존 코드 근거` are accurate at `bd89a04`:

| Spec citation | Verified |
|---|---|
| `harness.schema.json:6` root required = `schema_version`·`wiki_root`·`history`·`quality` | correct |
| `:63` `profiles` has no `required`, so neither `fast` nor `full` is mandatory | correct |
| `:113`·`:118` `triggers`/`stages` have no `minItems`, so empty arrays validate | correct |
| `_hookutil.py:64` `config()` absorbs every config error into `{}` | correct |
| `:80` missing version reads as V1; `:86` `is_v2()` is `>= 2` | correct |
| `:181` python order = configured file → `.venv/Scripts/python.exe` → `.venv/bin/python` → `sys.executable` | correct |
| `_quality.py:73`·`:94` cwd and stage validation | correct |
| `:169` substitution only when the value is a whole argv item; empty list skips the stage | correct |
| `auto_test_check.py:67` tracked paths = `quality.tracked_paths`, else `source_prefixes` | correct |
| `:281` fast/post_change, `:316` full/stop | correct |
| `pre_commit_check.py:165` full/pre_commit only, no lists passed; `auto_test_check.py:324` same | correct |
| `settings.json:19`·`:74`·`:105`·`:131` current wiring | correct |
| `test_hook_wiring.py:33` extraction is filename-centric (`r"hooks/([\w.]+\.py)"`) | correct |
| `conftest.py:31` `scripts/` is on the test import path | correct — a bare `scripts/doctor.py` is importable as `doctor` |
| `README.md:77` other-language projects swap the Quality Profile | correct |

Two spec decisions are not only correct but well-founded, and should not be weakened:

- **D-WIRING's table matches the live wiring.** `fast/post_change` needs all four tools and gets them from
  two separate `PostToolUse` groups (`settings.json:74` `Write|Edit` → `:98`, `:105` `Bash|PowerShell` → `:114`);
  the `Stop` group has no matcher (`:131` → `:136`); `full/pre_commit` comes from `PreToolUse` `Bash|PowerShell`
  (`:5` → `:19`). Requiring the merge across groups is necessary here, not defensive.
- **D-ARGV's "full stage with a list placeholder is a FAIL" is exactly right.** `pre_commit_check.py:169` and
  `auto_test_check.py:324` both call `run_profile("full")` with no lists; `_quality.py:186` then returns `None`
  and `:213` returns `ok=True, skipped=True`. Such a stage can never run and never reports anything.

`새 스크립트는 현재 Fast 추적 경로 밖` is also accurate — measured:
`_matches_tracked(".claude/harness/scripts/doctor.py")` → `False`.

## Blocking findings

### C-01 · P1 · D-VERSION FAILs without telling the user which way the runtime falls

**Location** — spec `### 2. 검사별 심각도와 종료 코드`, both D-VERSION rows. Code: `_hookutil.py:80-86`.

**Evidence** — `schema_version()` is
`return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 1`.
So for `"2"`, `2.0`, `true`, `0`, `-1` the live hooks run as **V1**: every V2 quality gate and the V2 History
gate are off and nothing errors. For `3` the hooks run as **V2** (`is_v2()` is `>= 2`), while the schema
rejects it (`harness.schema.json:9` is `{ "const": 2 }`).

**Why this blocks** — the spec's 목적 is to report config errors "때문에 훅이나 품질 검사가 조용히 빠지는"
cases with location and fix. A bare `FAIL … 지원 범위 안내` satisfies the severity but drops the single most
useful fact: that the session is currently running with V2 gates silently disabled (or, for `3`, enabled
despite the schema). The user cannot act on "unsupported" alone.

**Expected behavior** — for any `schema_version` outside `2`, the FAIL message names the branch
`_hookutil.schema_version()` will actually take (V1 fallback for non-positive-int values; V2 for integers > 2)
and cites that function as the reason.

**Verification criteria** — a test asserts the output for `"2"`, `2.0`, `true`, `0` contains the V1-fallback
statement, and for `3` contains the V2-enabled statement, in both cases with exit code 1.

### C-02 · P1 · D-CONFIG contradicts D-VERSION on V1 projects

**Location** — spec D-CONFIG row vs both D-VERSION rows, and `### 호환성과 보안·비용 경계`.

**Evidence** — `harness.schema.json:6` makes `schema_version`, `wiki_root`, `history`, `quality` all root-required,
and `:9` pins `schema_version` to `const: 2`. A genuine V1 project has none of them.

**Why this blocks** — read literally, such a project gets D-VERSION `WARN` (classify as V1, skip V2 checks) *and*
D-CONFIG `FAIL` (root schema violated, three missing required fields) → exit 1. That contradicts
`V1에서는 공통 파일·JSON·해석 가능한 훅 경로만 점검하고 V2 구조·stage·트리거 점검은 미검사 경고로 남긴다`,
and it fails the one scenario the spec names in 목적 (a harness just copied into an existing project).

**Expected behavior** — state explicitly that (a) `schema_version` is owned by D-VERSION and is never also a
D-CONFIG finding, and (b) when D-VERSION resolves to V1, root `required`, `history`, `quality`, profile, stage
and mapping validation are reported as `[WARN] 미검사`, not FAIL.

**Verification criteria** — a V1 fixture (`{}` as `harness.json`, or V1-era keys only) yields WARN-only output
and **exit code 0**; the same fixture with `"schema_version": 2` added yields the D-CONFIG FAILs.

### C-03 · P1 · D-TRACKED misses the trailing-slash trap, the highest-value check available here

**Location** — spec D-TRACKED row ("유효 추적 경로가 전혀 없음") and `### 4`'s History paragraph.
Code: `auto_test_check.py:80-90`, `_hookutil.py:478-503`.

**Evidence** — both matchers treat an entry *without* a trailing `/` as an exact file, never as a directory.
`_matches_tracked` returns True only on `path.startswith(entry)` for `/`-terminated entries or `path == entry`
otherwise; `tracked_paths_newer_than` handles the non-`/` case in `elif path.is_file()`, which a directory never
satisfies. Measured on this checkout:

```
tracked_paths = ("tests",)   _matches_tracked("tests/test_doctor.py") -> False
                             tracked_paths_newer_than(("tests",), 0)  -> []
tracked_paths = ("tests/",)  tracked_paths_newer_than(("tests/",), 0) -> 17 files
```

**Why this blocks** — `quality.tracked_paths: ["src", "tests"]` is the obvious hand-merge of
`source_prefixes` (the current values genuinely are `["src/", "tests/"]`, so the slash looks incidental).
With it, the Fast gate and the V2 History gate silently track nothing, no error is raised anywhere, and under
the spec as written Doctor reports PASS — the entries are non-empty strings, so "유효 추적 경로가 전혀 없음"
is false. This is precisely the failure class Doctor exists to catch, and it is cheap to detect statically.
`history.tracked_paths` has the identical contract (`history_check.py:41-50` → `:124`) and the spec currently
checks nothing about it at all.

**Expected behavior** — a new check (or an added D-TRACKED condition) over both `quality.tracked_paths` and
`history.tracked_paths`: an entry that does not end with `/` but resolves to an existing **directory** is a
FAIL naming the entry, the two consumers it silently disables, and `add a trailing /` as the fix. An entry
that resolves to neither an existing directory nor an existing file stays a D-SCAFFOLD WARN.

**Verification criteria** — a fixture with `["src", "tests"]` over existing directories FAILs with exit 1 and
names both entries; the same fixture with `["src/", "tests/"]` passes that check; an entry naming a real file
(`pyproject.toml`) is not flagged; `history.tracked_paths` is covered by its own case.

### C-04 · P1 · D-ARGV's placeholder predicate is narrower than the runtime's

**Location** — spec D-ARGV rows and `### 4`'s first bullet. Code: `_quality.py:130-134`.

**Evidence** — the runtime rejects an arg iff
`arg.startswith("{") and arg.endswith("}") and arg not in _KNOWN_PLACEHOLDERS`. Measured against that rule:

```
'{python}'            rejected=False  expands=True
'{unknown}'           rejected=True   expands=False
'{a}x{b}'             rejected=True   expands=False
'{}'                  rejected=True   expands=False
'{python} --version'  rejected=False  expands=False   (passed through literally)
'--opt={python}'      rejected=False  expands=False   (passed through literally)
```

**Why this blocks** — the spec says `알 수 없는 **단독** 치환값` → FAIL, which reads as exactly-`{unknown}`.
`{a}x{b}` and `{}` would then be PASS in Doctor while `load_profile` raises `QualityConfigError`, so the hook
blocks the session with `설정이 잘못됐습니다`. Doctor would certify a config the runtime refuses to load —
the inverse of its purpose.

**Expected behavior** — reproduce the predicate verbatim in the spec, and keep the two outcomes separate:
brace-wrapped-and-not-a-known-placeholder → FAIL (runtime raises); a known placeholder embedded in a longer
string → WARN (runtime passes it literally, no expansion). The existing WARN row is already correct; only the
FAIL row needs the exact predicate.

**Verification criteria** — `{a}x{b}`, `{}`, `{unknown}` each FAIL; `{python} --version` and `--opt={python}`
each WARN and do not FAIL; `{python}` alone is clean.

## Non-blocking findings

### C-05 · P2 · `"matcher": "*"` is a valid wildcard but an invalid regex

`re.fullmatch("*", "Write")` raises `re.error: nothing to repeat at position 0` (measured). D-WIRING says
`잘못된 정규식은 해당 설정 위치의 FAIL이다`, so a config using the `*` wildcard — same intent as the spec's own
"누락·빈 값은 모든 도구에 적용" rule — gets FAIL and exit 1. Suggest: treat `*` (and missing/empty) as
"all tools" *before* compiling, and reserve FAIL for a non-wildcard string that fails `re.compile`.
`re.fullmatch` itself is the right choice and matches the existing convention at `tests/test_hook_wiring.py:158`.

### C-06 · P2 · D-EXEC's `shutil.which` FAIL is PATH-dependent in both directions

Stages run with `_hookutil.child_env()` (`_hookutil.py:214-217`), which copies the **hook** process environment
(the Claude Code session). Doctor's `shutil.which` resolves against the **Doctor** process PATH — routinely a
different shell, often with a venv activated. Measured here: `shutil.which("ruff")` → `None`, while `ruff`
runs fine as `{python} -m ruff` in the Full profile. A bare-name miss is therefore weak evidence of a real
break. Suggest downgrading it to WARN, or keeping FAIL but requiring the output to state that the PATH checked
is Doctor's and not the hooks'. This also aligns the severity with the limit the spec already accepts
(`실제 프로세스 경로 해석까지 검증한 것으로 표시하지 않는다`).

### C-07 · P2 · D-PYTHON reproduces `venv_python()` against a different root than the runtime uses

`venv_python()` resolves a relative `python` against `_hookutil.PROJECT_ROOT`, which `_find_root()`
(`_hookutil.py:40-49`) derives from `CLAUDE_PROJECT_DIR` or cwd by ascending to the nearest directory
containing `.claude/`. Doctor's root is `parents[3]` of `__file__` and, by the spec's own 실행 계약, never moves.
The two diverge for a nested project whose parent also has `.claude/`, and whenever `CLAUDE_PROJECT_DIR` points
outside the target. The spec requires `그대로 설명·재현` but never requires Doctor to disclose the difference.
Suggest one output line: the interpreter was resolved against Doctor's own root, while the live hooks resolve
against a `CLAUDE_PROJECT_DIR`-derived root, so the two can differ.

### C-08 · P2 · D-FILES' wiki READMEs depend on `wiki_root`, hence on D-JSON

`overview/README.md` and `knowledge/README.md` live under the project-supplied `wiki_root`
(`_hookutil.py:121-124`; `.claude/wiki/` here and as the documented default). D-FILES names them as bare
relative paths and makes absence a FAIL, but when `.claude/harness.json` fails D-JSON their location is unknown
— and 실행 계약 says a check blocked by a prior error must be `[WARN] 미검사`. Suggest stating that the two
wiki READMEs resolve under the configured `wiki_root` (default `.claude/wiki/`), and that they are 미검사
rather than FAIL when `harness.json` is unreadable or malformed.

### C-09 · P2 · `__file__`-based root contradicts a recorded decision without reconciling it

`_hookutil.py:30-39` records as a measured decision that the root **cannot** be taken from `__file__`, because
"이 파일이 플러그인 설치 경로에 살아서 위로 두 칸 올라가면 저장소가 아니라 플러그인 폴더가 나온다"; `:294-297`
still reads `CLAUDE_PLUGIN_DATA`, and this checkout still carries `plugins/harness-core/` and `plugins/quiz/`
(untracked, no files). `parents[3]` is correct for the copy-into-`.claude/` distribution `README.md` describes,
and it is the right call for a CLI that must not follow cwd — but the spec asserts it without naming the
assumption or addressing the recorded counter-case. Suggest: state the assumption (Doctor is a repo-local
script at `<root>/.claude/harness/scripts/doctor.py`) and have Doctor verify its own layout — that
`<root>/.claude/harness/scripts` is its own directory — and exit with a clear message instead of diagnosing an
unrelated tree. That guard also protects `parents[3]` if the script is later moved into a package.

### C-10 · P3 · D-SCAFFOLD's wording hardcodes this repo's names

`설정이 참조하는 src/tests/pyproject.toml, mapping 대상, History 디렉터리` names this repository's layout, while
`### 4` forbids hardcoding any language or tool. A faithful implementation of that sentence would ship those
names. Suggest rephrasing as "설정이 참조하는 경로 — `tracked_paths` 항목, mapping의 `path`·`tests`,
`stage.cwd`, History 디렉터리".

### C-11 · P3 · suggestion · `unmapped_by_design` is available as a signal and unused

Measured: `test_target_for("pyproject.toml")` and `test_target_for(".claude/harness.json")` both return `None`,
yet both are in `quality.tracked_paths`. A change to either triggers Fast, `mapped_targets` is empty, and the
stage is skipped with `ok=True` (`_quality.py:183-187`, `:212-213`) — the gate reports success having run
nothing. `quality-env.md` documents this in prose ("문서·스킬 파일 변경에는 매핑된 검사가 없다") and
`quality.unmapped_by_design` is `{}`, i.e. the config does not declare it although the mechanism exists for
exactly that purpose. Suggest a WARN for a tracked path that has no mapping, is not under `tests/`, and is not
declared in `unmapped_by_design`. This is a static property of the config, so it does not conflict with the
spec's correct refusal to judge Fast by the momentary absence of dynamic input.

### C-12 · nit · layout consistency

Existing `scripts/` entries are packages (`openwork/`, `quiz/`); the spec adds a bare `scripts/doctor.py`.
That works — `tests/conftest.py:31` puts `scripts/` on `sys.path`, so `import doctor` resolves — and keeps
`parents[3]` valid. Noted only because the package convention and the `parents[3]` depth are now coupled.

## Open questions

1. **Exit code for Doctor's own failure.** The spec fixes 0/1 on the presence of FAIL only. What should a
   caller see when Doctor itself cannot run (unreadable root, unexpected layout per C-09, an internal error)?
   Suggest reserving 2, so "no findings" stays distinguishable from "did not run".
2. **Does D-HOOK cover the seven non-quality hooks?** D-HOOK's wording ("해석 가능한 명령이 … 존재하지 않는
   훅 스크립트를 가리킴") reads as every wired command, while D-WIRING's required-connection table covers only
   the three quality wirings. I read the intent as: all wired commands get path-existence checks, but only the
   three get required-wiring checks. Please confirm, since `settings.json` wires nine scripts.
3. **Fast coverage of the new script.** `.claude/harness/scripts/` is outside `quality.tracked_paths`
   (measured), so `doctor.py` gets no automatic Fast coverage, and the spec excludes `품질 추적 범위 확대`.
   Confirm that staying outside is intended rather than a follow-up task.
4. **D-PROFILE vs D-TRIGGER on a profile with triggers but no stages.** `### 3` defines "활성" as both
   non-empty, so such a profile is inactive → D-PROFILE WARN. Should D-TRIGGER still validate the trigger
   names on an inactive profile, or report them 미검사? The table does not say, and the trigger values are
   checkable regardless.

## What I did not do

- No implementation, no test file, no README or Knowledge edit. Nothing was run from `.claude/harness.json`'s
  Quality Profile: this change touches only this new review file, and the spec's own verification plan belongs
  to the implementation step.
- Linux behavior is unverified (Windows-only checkout), consistent with `quality-env.md`'s limits.
- I did not edit `tasks/doctor.md` — per `.claude/skills/handoff/SKILL.md` it is Codex's file, and findings
  belong here.

## Round 1 recommendation (pre-implementation)

C-01 through C-04 should be resolved in the spec before implementation; each one has Doctor reporting PASS or
exit 0 on a config the live runtime handles differently, which inverts the command's purpose. C-03 and C-04 are
the two that would let a broken project through. C-05 through C-09 are corrections I would otherwise have to
make judgment calls on at implementation time. The spec's structure, severity model, and the D-WIRING and
full-stage-placeholder rules need no change.

---

# Round 2 — revised spec check and implementation report

- Date / revision: 2026-11-22 · `C:\my-harness`, `main` / `bd89a04`
- Spec read: `tasks/doctor.md` as revised by Codex (34,597 bytes, mtime 15:25 — the
  `## Claude 구현 전 리뷰 반영 — 2026-11-22` section)
- Nothing is committed. `git status`: `M README.md`, `M tasks/doctor.md`, and untracked
  `.claude/harness/scripts/doctor.py`, `.claude/wiki/knowledge/doctor.md`, `tests/test_doctor.py`,
  `tasks/doctor.review.md`.

## Revised spec: no conflicts, so I implemented

C-01 through C-04 are all adopted in a form that matches the runtime. I re-read the revised spec against the
current code and found nothing blocking. The one new factual claim it added, I verified rather than assumed:

- **`harness_paths` really is a tracked-path fallback.** `history_check.py:47` returns
  `(*config_list("source_prefixes"), *config_list("harness_paths"))` when `history.tracked_paths` is empty or
  malformed, and `:124` feeds that into `tracked_paths_newer_than`. So applying the trailing-slash check to it
  is correct, not over-reach.

**C-05: Codex rejected my suggestion and Codex is right.** I had said Python `fullmatch` "matches the existing
convention at `tests/test_hook_wiring.py:158`". That is true of the repo's own test but it is not the product's
matcher semantics, which the revised spec cites as name-lists plus JavaScript partial match. I implemented the
spec's three-way rule. I did **not** independently fetch the cited documentation page, so the JS-partial-match
premise rests on Codex's citation, not on my own verification — flagging that rather than implying I checked
it. For this repository's actual matchers (`Write|Edit`, `Bash|PowerShell`) the name-list path yields the same
verdict as the old fullmatch convention, so nothing about the current wiring judgment changed.

## Files changed

| File | State |
|---|---|
| `.claude/harness/scripts/doctor.py` | new, 1 file, the CLI |
| `tests/test_doctor.py` | new, 129 tests |
| `README.md` | new `### 설치 직후 점검 — Doctor` section |
| `.claude/wiki/knowledge/doctor.md` | new, the preserved contract |

I did not touch `tasks/doctor.md` (Codex's file), the existing hooks, `.claude/harness.json`,
`.claude/settings.json`, or any existing test.

## Commands actually run, with results

All with the configured interpreter `.venv/Scripts/python.exe`.

| Command | Result |
|---|---|
| `-m ruff format <two new files>` | `2 files reformatted` |
| `-m ruff check .` | `All checks passed!`, exit 0 |
| `-m ruff format --check .` | `71 files already formatted`, exit 0 |
| `-m pytest tests/test_doctor.py -q` | **128 passed, 1 skipped**, 4.76s |
| `-m pytest -q` | **533 passed, 1 skipped**, 19.66s |
| `python .claude/harness/scripts/doctor.py` (this repo) | `PASS 24 · WARN 5 · FAIL 0`, exit 0 |

533 = the 405 recorded in `quality-env.md` plus my 128 new passes. I am reporting it as a new measurement, not
reusing the 405. The 1 skip is the POSIX executable-permission test. Every figure above is from the final
re-run after all documentation edits, not from an intermediate state.

One incidental finding worth knowing: **`ruff format --check .` also checks Markdown in this setup.** The file
count went 68 → 71 across my runs, and the +3 is exactly my three new `.md` files (`knowledge/doctor.md` and
the two Plan History entries); `.claude` alone accounts for 30 md + 17 py = 47. So the documentation I added
is inside the Full gate's format scope and passes it. `quality-env.md` describes the format stage only in
terms of Python, which is now incomplete — not something I changed, just noting it.

**The Fast gate also ran on its own and earned its keep.** `tests/test_doctor.py` is inside
`quality.tracked_paths` and hits `test_target_for()`'s direct-test special case, so writing the test file
triggered `pytest tests/test_doctor.py -q` automatically. It failed and caught a real defect (below).
`doctor.py` itself is outside the tracked paths, as the spec intends, so it has **no** automatic Fast
coverage — I ran its tests directly instead and am not claiming Fast verified it.

## Not run, and why

- **Linux is unverified.** Windows-only checkout. The POSIX permission-bit test is the 1 skip and reports as
  skipped rather than passing. The opposite-OS path classification is covered by a pure-input test only.
- No hook, stage, Git or other interpreter was executed by the diagnostic code. Two tests assert this
  positively: one snapshots every file's bytes before and after `diagnose()` and compares, another
  monkeypatches `subprocess.Popen`/`run`, `os.system`, `spawn*`, `execv` and `fork` to raise. Two more plant a
  wired hook and a stage command that write a file if executed, and assert the file never appears.

## Defect found during implementation

**D-CONFIG did not validate stage `argv` shape.** `argv: []` and `argv: "ruff"` produced no finding at all,
although `_quality.load_profile` raises `QualityConfigError` for both (`_quality.py:120-127`). The cause: my
D-ARGV routine returns early when `argv` is not a non-empty list, so nothing examined the shape. That is the
same inversion C-04 was about — Doctor passing a config the runtime refuses to load. Fixed by adding argv
shape validation to `_check_stage_shapes`, with the two cases now covered by
`test_bad_stage_fields_fail[{'argv': []}]` and `[{'argv': 'ruff'}]`.

This was a first-implementation defect caught before review, not a fix attempt, so it does not count toward
the model-escalation policy.

## Two of my own Round 1 assumptions were wrong

I corrected the tests, not the code, after checking which side was right:

1. I wrote a test asserting `matcher_covers("ri", "Write")` is True on the theory that the regex path applies.
   It does not: `ri` contains only alphanumerics, so the spec's name-list rule claims it first and compares
   exactly. **False is the correct answer.** I replaced it with `[Ww]ri`, which has metacharacters, takes the
   regex path, and demonstrates partial match (fullmatch would miss `Write`), plus a second test pinning the
   bare-word case as a name list.
2. I asserted "no PASS for D-WIRING" globally when only one event had an unresolvable matcher. The other two
   rows were legitimately PASS. Scoped the assertion to the affected event.

## Judgment calls the spec left open — please review these

The spec is specific, but these seven points needed a decision I made myself:

1. **A check with zero applicable items.** When every stage's `argv[0]` is `{python}`, D-EXEC has nothing to
   examine. The spec forbids dressing 미검사 as PASS but does not say whether to emit a WARN or stay silent. I
   emit `[WARN] D-EXEC 미검사`. Consequence: a perfectly healthy Python project carries a permanent WARN (exit
   still 0). This repo shows it. Silence would also be defensible.
2. **"명백히 깨진 패턴".** The spec gives unclosed `[` as the example. I implemented bracket/paren balance only
   (`_brackets_balanced`); anything else Python rejects becomes an unverifiable WARN rather than a FAIL.
3. **The JS-divergent syntax list is mine**: `(?P<`, `(?P=`, `(?#`, `\A`, `\Z`, `\z`, `(?>`. The spec says only
   "JS 전용 문법 등". A pattern containing one of these is reported unverifiable instead of being matched.
4. **Explicit `"schema_version": null`.** I treat a present-but-null field as FAIL and an absent field as
   WARN/V1, because the spec's test list names `null` among the FAIL cases. Note the runtime makes no such
   distinction — both become 1. Confirm this is the intent.
5. **Shell-operator set for unresolvable commands**: `|`, `&`, `;`, `<`, `>`, backtick, newline, and `$(`.
   `${CLAUDE_PROJECT_DIR}` and `$CLAUDE_PROJECT_DIR` are substituted; any other `${...}` or `$VAR` makes the
   command unresolvable (WARN).
6. **D-TRACKED checks all four fields unconditionally** — `quality.tracked_paths`, `history.tracked_paths`,
   `source_prefixes`, `harness_paths` — rather than only when a fallback is actually in play. The spec's
   "실제로 대체에 쓰이는" reads both ways; checking always is the stricter reading and each message names the
   consumer that field affects.
7. **`unmapped_by_design` reproduction accepts dict or list**, matching `_load_unmapped`'s real behavior, even
   though the schema permits only a dict (a list is separately a D-CONFIG FAIL).

## This repository's own diagnosis

`PASS 24 · WARN 5 · FAIL 0`, exit 0. All five WARNs are real facts about this repo's configuration, not
install problems:

- D-SCAFFOLD ×3 — `src/` and `pyproject.toml` do not exist, and `quality.mappings` points at `src/`.
- D-EXEC ×1 — the zero-applicable-items case in judgment call 1.
- D-MAPPING ×1 — `.claude/harness.json` is tracked but has no corresponding test target, so a change to only
  that file makes the Fast stage skip and report success. This is the C-11 case, and it turns what
  `quality-env.md` records in prose ("문서·스킬 파일 변경에는 매핑된 검사가 없다") into a check.

I did not change any configuration to silence these. Whether to add `unmapped_by_design` entries or adjust
`quality.tracked_paths` is outside this task's scope (`품질 추적 범위 확대` is excluded).

## Remaining items

- **Linux unverified**, as above.
- **History: two Plan entries written, no Verify entry.** I ran the project's `history-significance`
  assessment. Its closing rule is that Knowledge carries only the currently valid rules while reasons and
  rejected alternatives belong in History — my first draft had put both in `knowledge/doctor.md`, so I split
  them:
  - `.claude/wiki/history/plan/2026-11-22-doctor-matcher-semantics.md` — the matcher decision, with Python
    `fullmatch` as the rejected alternative, the measured `re.error` on `*`, and the explicit note that
    `test_hook_wiring.py:158` keeps using fullmatch for its own purpose and that **the two rules differing is
    not a bug**. That last point is the one a future worker is most likely to "fix".
  - `.claude/wiki/history/plan/2026-11-22-doctor-target-root.md` — the root decision, why the two tools'
    premises are opposite, and why importing `_hookutil` was rejected (its `config()` swallows exactly the
    failure Doctor must find).
  - `knowledge/doctor.md` now keeps the current rules and points at both entries instead of repeating them.
  - **No `verify-log` entry.** 533 passed is "일반 test 성공", which that skill excludes, and the repo's own
    diagnosis baseline sits in `knowledge/doctor.md`'s 현재 확인된 상태 table — the same pattern
    `quality-env.md` already uses. Flagging the call in case you want it recorded as a Verify baseline instead.
  - One gap I recorded rather than fixed: the `_hookutil` branches Doctor copies
    (`venv_python`, `_wiki_root`, `history_prefix`, tracked-path normalization) are **not** cross-checked by a
    test the way the schema constants are. If those change, Doctor drifts silently. Closing that would mean
    importing the hook module, which the root decision rejects.
- **Temp files not deleted and nothing committed.** Step 8 (your final review against the completion
  criteria) has not happened, so the cleanup conditions are not met. `tasks/doctor.md` and
  `tasks/doctor.review.md` both stay. Note that neither is in a commit yet, so the preservation condition
  ("두 임시 파일의 최신 내용이 확인된 Git 커밋에 있거나…") is also unmet — I have not committed because the
  procedure says not to create commits without approval to satisfy that condition.
- **No blocking finding is hidden by a completion claim.** The seven judgment calls above are open questions,
  not resolved items.

# Round 3 — your result review, checked before fixing

Scope: `tasks/doctor.md` as it now stands (46,549 bytes — the appended **Codex Round 2 결과 리뷰** plus your
in-place edits to section 3), read against the working tree at `main` / `bd89a04`. I changed no
implementation file this round and nothing is committed. This is the check, not the fix.

**All four findings reproduce.** None is a misreading of the code, and I found no conflict between the
revised spec and the two Plan History entries that would stop me implementing. Three additions and one
question below.

## How I checked

Each probe copied this repo's `.claude/` tree into a fresh temp root with `src/`, `tests/`, `pyproject.toml`
and `CLAUDE.md`, changed one field, and ran the copied `doctor.py` as a subprocess. `matcher_covers` and
`parse_command` cases ran against the module directly. For the JavaScript side I measured a real V8 — the
desktop app's browser pane — rather than taking the claim on trust; there is no `node`, `deno` or `bun` on
this machine, so that was the only engine available.

## R2-01 — confirmed, and the hole is wider than the three cases you named

Measured, all against the healthy fixture's hook command shape:

```text
python -c pass "${CLAUDE_PROJECT_DIR}/…/auto_test_check.py"        -> script=.claude/harness/hooks/auto_test_check.py
python -m not_a_hook "${CLAUDE_PROJECT_DIR}/…/auto_test_check.py"  -> script=.claude/harness/hooks/auto_test_check.py
python --version "${CLAUDE_PROJECT_DIR}/…/auto_test_check.py"      -> script=.claude/harness/hooks/auto_test_check.py
python -c "import x" "${CLAUDE_PROJECT_DIR}/…/auto_test_check.py"  -> script=.claude/harness/hooks/auto_test_check.py
```

The fourth is mine, not from your list: a `-c` whose program text is quoted behaves the same way, so the
negative cases to pin are the *modes*, not the bare `-c pass` spelling. `parse_command` scans `resolved[1:]`
for the first token ending in `.py` and never looks at what came before it, so any Python invocation that
mentions a hook path anywhere counts as running it.

The fix needs a small table of the options Python actually accepts, split into value-taking (`-c`, `-m`,
`-W`, `-X`, `--check-hash-based-pycs`) and standalone (`-u`, `-B`, `-E`, `-I`, `-O`/`-OO`, `-s`, `-S`, `-v`,
`-q`, `-b`, `-d`), plus the `py` launcher's `-3`/`-3.12`. The first non-option token is the script; `-c`,
`-m`, `-V`/`--version`, `-h`/`--help`/`-?` mean there is none; an option not in the table means unknown,
because a value-taking option we don't know would make us read its value as the script. All three outcomes
other than "script" are D-HOOK unresolved WARN, and leave the required wiring at D-WIRING FAIL.

One design consequence worth your confirmation: once options are parsed properly, the first positional *is*
the script whatever its extension, so I plan to drop the current `.endswith(".py")` requirement on the
positional and keep it only for the no-interpreter form (`"<path>.py"` as `argv[0]`). That is strictly more
accurate about what Python runs, and it does not loosen D-WIRING, which still compares the resolved path
against the one expected script.

## R2-02 — confirmed, with the JS side measured rather than assumed

V8 (`new RegExp`), measured this round:

```text
(?i)Write|Edit|Bash|PowerShell  SyntaxError: Invalid group
Bash++                          SyntaxError: Nothing to repeat
Bash*+                          SyntaxError: Nothing to repeat
Bash?+                          SyntaxError: Nothing to repeat
Bash{1,2}+                      SyntaxError: Nothing to repeat
(?P<n>W)rite                    SyntaxError: Invalid group
(?>Write)                       SyntaxError: Invalid group
(?#c)Write                      SyntaxError: Invalid group
" * "                           compiles; test("Write") false
"   "                           compiles; test("Write") false
[Ww]ri                          compiles; test("Write") true
\AWrite                         compiles; test("Write") false
```

Python 3.12 compiles every one of the first five, and `matcher_covers` returns `(True, …)` for
`(?i)Write|Edit|Bash|PowerShell`, `Bash++`, `" * "` and `"   "`. So there are four live false-PASS routes,
not three. The possessive family is all four spellings, which the spec body now covers generically
("possessive quantifier 등") — I am listing them as the regression set, not as a new finding.

Two things this measurement settles about my own `_PY_ONLY_SYNTAX` list:

- `(?P<`, `(?P=`, `(?#` and `(?>` are JS **syntax errors**, not merely patterns of uncertain meaning. They
  belong in the new FAIL class, not in "unknown".
- `\A`, `\Z`, `\z` are the genuine uncertain-meaning case, and in the direction that matters: V8 compiles
  `\AWrite` as the literal `AWrite` and does **not** match `Write`, while Python's start anchor does match
  it. Keeping them out of the regex path was right, and now there is a measurement behind it.

For the bounded subset I will allow only constructs with identical meaning in both engines — literals, `.`,
`|`, `(`/`(?:`/`)`, `[...]` classes, the quantifiers `*`, `+`, `?`, `{m}`, `{m,}`, `{m,n}` each optionally
followed by `?` but never by `+`, the anchors `^` and `$`, and the escapes `\d\w\s\D\W\S\b\B` plus
punctuation escapes, `\xHH`, `\uHHHH` — and return unknown for everything else. The real matchers in this
repo and the plausible ones (`.*`, `mcp__.*`, `Notebook.*`, `Write|Edit`, `[Ww]ri`) all stay inside it.

## R2-03 — confirmed, and the enumerated scope has no other gap

The fixture's baseline is `PASS 22 · WARN 4 · FAIL 1` (the one FAIL is the fixture's own missing
`CLAUDE.md`). Both mutations leave that count untouched:

```text
quality.unmapped_by_design = {"src/": 42}   PASS 22 · WARN 4 · FAIL 1   exit 0 … no new finding
quality.mappings[0].why    = []             PASS 22 · WARN 4 · FAIL 1   exit 0 … no new finding
quality.unmapped_by_design = {"docs/": ""}  PASS 22 · WARN 4 · FAIL 1   exit 0 … correctly silent
```

The third is the control for your "스키마가 허용하는 빈 문자열을 임의로 거부하지 않는다": neither
`unmapped_by_design`'s values nor `why` has a `minLength`, so `""` must stay legal while `path`/`tests`
keep their current non-empty requirement.

I swept the rest of the scope section 1 enumerates — `history.plan`/`task`/`verify`, both `tracked_paths`
arrays, stage `id`/`argv`/`argv[i]`/`label`/`cwd`/`timeout`/`success_codes`, `profiles.*.triggers` and its
enum and duplicates, `wiki_root` — and every one is already typed. Inside the enumerated scope the two you
named are the only omissions. (`wiki_root` without a trailing slash is also fine: `wiki_root_of` appends one
exactly as `_hookutil._wiki_root()` does, which I confirmed by diffing the two.)

## R2-04 — confirmed, and the reason is stronger than the one you gave

Reproduced in both directions:

```text
explicit quality+history tracked_paths, source_prefixes=["src"], harness_paths=["tests"]
  -> both tracked_paths PASS, source_prefixes[0] FAIL, harness_paths[0] FAIL, exit 1   (wrong)
both tracked_paths emptied, same fallbacks
  -> source_prefixes[0] FAIL, harness_paths[0] FAIL, exit 1                            (right)
only history.tracked_paths emptied
  -> source_prefixes[0] FAIL, harness_paths[0] FAIL, exit 1                            (right)
control: source_prefixes=["src/"], harness_paths=["tests/"]
  -> all four fields PASS, no D-TRACKED finding                                        (right)
```

Your premise — that those two fields are only fallbacks — is true, but `history_check.py:47` is not the
whole reason, and I checked before building on it. `source_prefixes` has four other consumers and
`harness_paths` one, and **every one of them is version-gated off on V2**: `task_log_check.py:193` returns
immediately when `is_v2()`, and `auto_test_check.py:416` dispatches to `_handle_v2_*` and returns before
`:245`, `:376` and `:426` are ever reached. Since D-TRACKED only runs under `schema_version: 2`, on every
project Doctor inspects those two fields really are nothing but fallbacks. The V2 Fast path uses
`QUALITY_TRACKED_PATHS` through `tracked_paths_newer_than` (`auto_test_check.py:260`, `:269`), which is the
slash-sensitive function, so the check itself stays worth having.

So the per-field predicate, matching `_v2_tracked_paths()` (`auto_test_check.py:67`) and
`history_check.tracked_paths()` (`:41`) — both of which accept a list holding at least one non-blank string
and otherwise fall back:

- `source_prefixes` is live iff `quality.tracked_paths` **or** `history.tracked_paths` resolves empty.
- `harness_paths` is live iff `history.tracked_paths` resolves empty.

The third probe above is the combination you asked me to add, and the current code is already right on it —
the history fallback is `source_prefixes + harness_paths`, so both fields are live when only
`history.tracked_paths` is empty, even though `quality` is explicit.

One wording point your criteria don't cover: when the fallback is **not** selected, on V2 the field has no
live consumer at all, so the non-blocking WARN should say the entry is currently unread. It should not
advise a trailing slash as though a gate were broken. `harness_paths` especially — its only other consumer
compares by exact string equality (`task_log_check.py:124`), where a directory entry matches nothing with or
without the slash, so "add `/`" would be wrong advice twice over.

## New findings

### R3-01 · P2 · a config the schema rejects passes clean with exit 0

Measured, each on an otherwise clean fixture (`PASS 23 · WARN 4 · FAIL 0`, exit 0):

| mutation | schema says | Doctor |
|---|---|---|
| `source_prefixes: "src/"` | array of strings | no finding, exit 0 |
| `harness_paths: [42]` | `minLength: 1` string items | no finding, exit 0 |
| `python: 42` | string, `minLength: 1` | no D-CONFIG; D-PYTHON prints `설정한 42` as if it were a path |
| `python: ""` | `minLength: 1` | no finding, exit 0 |

`_hookutil.config_list()` returns `()` for anything that is not a list and silently drops non-string items,
so these are absorbed the same way `config()` absorbs a read failure — the class this CLI exists to surface.

This one is yours to decide, so I am not treating it as a defect against the spec as written: section 1
enumerates `history`, `quality`, profile, stage and mappings, which leaves the root scalars and arrays
outside D-CONFIG's stated scope. The live impact on V2 is also limited — by R2-04's own reasoning these
three fields only matter through the two fallback paths, so with both `tracked_paths` explicit a non-array
`source_prefixes` changes nothing today. What I cannot defend is a config the schema rejects reporting
`FAIL 0`, when the first thing someone runs Doctor for is to find out whether their config is right.

### R3-02 · P2 · the matcher Plan History entry's 결정 section stops being true

`.claude/wiki/history/plan/2026-11-22-doctor-matcher-semantics.md` records, as 상태 승인: "그 밖은
정규식이고 `re.search`로 부분 일치를 본다". R2-02 replaces that with a bounded common subset plus a
JS-invalid FAIL class. Your documentation note covers Knowledge and the target-root entry's wording but not
this entry's decision itself. Its own 영향과 후속 조건 already flags both the blocklist and the "명백히 깨진
패턴" scope as unfinished, so an amendment fits; `plan-log`'s 상태 field also allows marking it 대체됨 with a
successor. **I plan to amend it in place** and record the measured V8 results as the reason, unless you want
a successor entry instead.

### R3-03 · nit · the D-TRACKED FAIL sentence builds broken Korean

Current output: `… — History Gate 의 대체 추적 항목(history_check.py:47) 가 조용히 꺼집니다.` The four
`impact` strings are noun phrases dropped into a `…가 조용히 꺼집니다` frame, and two of them don't fit it.
R2-04 rewrites these messages anyway; noting it so it doesn't survive the rewrite.

## Open question

### Q-1 — `" * "` and a whitespace-only matcher: FAIL, or unknown?

Section 3 now says not to strip before the wildcard case and R2-02 asks for exactly `*`/empty/absent to be
distinguished, which puts `" * "` on the regex path: V8 compiles it, it matches nothing, so the verdict
becomes FAIL. That is right **if** Claude Code does not strip the matcher first, and I cannot confirm that
it doesn't. The documented contract — name lists and JS regex — supports your reading, and I'll implement it
as specified. I'm flagging it because a padded `*` is the one case where a wrong verdict means Doctor FAILs
a working project, which is the harm the `*` handling was built around in the first place. Say so if you'd
rather it be an unconfirmed WARN.

`"   "` has the same shape but a clean answer: it reaches `_NAME_LIST_RE`, splits to an empty name list, and
today would produce `이름 목록 ` with nothing after it. I'll return unknown with an explicit reason instead
of an empty list message.

## Your seven decisions, and the `_hookutil` comparison test

All seven are clear and I have nothing to push back on. Decision 6 rejects my unconditional-FAIL choice,
which R2-04 now specifies; 2, 3 and the dict-value half of 7 fold into R2-02 and R2-03; 1, 4 and 5 I'll
implement as decided.

On the comparison test: you're right that banning `_hookutil` from the diagnostic runtime and comparing
against it in a test are different things, and that the existing `load_hook` fixture makes the comparison
possible. That makes the better fix for the target-root entry's "테스트로 대조한다" sentence **adding the
test** rather than weakening the sentence — it also closes the drift gap I recorded as open at the end of
Round 2, which is the last item on that entry's 영향과 후속 조건 list. I'll do that unless you'd rather keep
the two sides fully separate, in which case the sentence gets corrected instead.

## What I did not verify

- **Claude Code's own matcher implementation.** Everything above is the documented contract plus measured
  V8 behaviour. I did not read the product's source, so the new FAIL for a JS-invalid matcher will state
  what is measurable — the pattern is not a valid JavaScript regular expression, so it cannot mean what it
  looks like — and will not claim what the product does when it meets one. Same discipline C-01 set for
  D-VERSION.
- **The official Hooks reference page.** Not fetched this round either; the subset above rests on the V8
  measurements and the page you cited.
- **Linux / POSIX.** Unchanged from Round 2. The one skipped test is still the POSIX execute-bit case.
- **One thing I checked and chose not to report.** An empty effective History tracked set does not silently
  disable the History gate the way an empty quality set disables change detection: `_session_changes`
  (`history_check.py:115`) also feeds on `changed_paths()` from git, so the mtime path is supplementary. A
  history-side counterpart to the existing quality emptiness WARN would have overstated the consequence, so
  there is no finding here.
- **Pre-fix state only.** The numbers I re-ran this round (below) are the implementation as you reviewed it.
  The run that counts is the one after R2-01–R2-04 are fixed.

## Re-run of the current state

Before changing anything, so the fix has a baseline:

```text
.venv/Scripts/python.exe -m ruff check .            All checks passed!
.venv/Scripts/python.exe -m ruff format --check .    71 files already formatted
.venv/Scripts/python.exe -m pytest -q                533 passed, 1 skipped in 12.77s
python .claude/harness/scripts/doctor.py             PASS 24 · WARN 5 · FAIL 0, exit 0
```

Same four results you got, and the same 71 files — this review file was already among them, so adding a
section to it does not move the count.

## Round 3 recommendation

Nothing here blocks implementation. R2-01 and R2-04 are mechanical once the predicates above are written
down; R2-02 is the real work, because a bounded allowlist is a new piece of code rather than a longer
blocklist. R3-01 and Q-1 are the two I need an answer on before the result is final — R3-01 because it
changes D-CONFIG's scope, which is yours, and Q-1 because either verdict is defensible and only one of them
can be in the tests.

# Round 3 — implementation report

All four findings are fixed in the same implementation and tests, each verified by re-running the probe
that produced the counterexample. I implemented Q-1 as specified (padded `*` is not a wildcard) and left
R3-01 alone, since extending D-CONFIG's scope is your call. The seven decisions are applied as decided.

## Files changed

| file | what |
|---|---|
| `.claude/harness/scripts/doctor.py` | all four fixes; `chosen_python()` extracted for the comparison test |
| `tests/test_doctor.py` | 128 → 210 tests; two old assertions replaced; new section 8 |
| `.claude/wiki/knowledge/doctor.md` | matcher rules, fallback selection, script-position table, new counts |
| `…/history/plan/2026-11-22-doctor-matcher-semantics.md` | amended in place (R3-02), 3a recorded as rejected |
| `…/history/plan/2026-11-22-doctor-target-root.md` | the comparison claim is now true; the drift gap closed |

`README.md` needed nothing — it carries the command, the level table and the 0/1/2 contract, none of which
moved. `tasks/doctor.md` untouched, as before. `tests/test_hook_wiring.py` untouched, and the full suite
passing confirms the narrowed matcher rule does not change this repo's wiring verdict.

## R2-01 — the script position is parsed, not guessed

`_script_token()` walks a closed table of Python's own options — value-taking (`-W`, `-X`,
`--check-hash-based-pycs`), standalone (`-[uBEIOsSvqbdPRt]+`), the `py` launcher's `-3`/`-3.12`/`-3-64` —
and returns the first non-option token. `-c`, `-m`, `-V`/`--version`, `-h`/`--help`/`-?` and `-` mean there
is no script; an option not in the table means unknown, because an unknown value-taking option would make
us read its value as the script. `tokenize()` now also stops at an unquoted `#` that starts a token, which
is what makes a trailing comment harmless while `python # <hook>` is unresolved.

Re-measured, same commands as the Round 3 check:

```text
python -c pass "<hook>"        -> unresolved: -c 모드는 인자로 준 스크립트를 실행하지 않습니다
python -c "import x" "<hook>"  -> unresolved: 같음
python -m not_a_hook "<hook>"  -> unresolved: -m 모드는 …
python --version "<hook>"      -> unresolved: --version 모드는 …
python "<hook>"                -> .claude/harness/hooks/auto_test_check.py
python -u "<hook>"             -> .claude/harness/hooks/auto_test_check.py
py -3 "<hook>"                 -> .claude/harness/hooks/auto_test_check.py
```

One deliberate loosening: the positional no longer has to end in `.py`, because Python runs files with any
name and the first positional is the script whichever it is. The no-interpreter form (`"<path>.py"` as
argv[0]) still requires `.py`, since there the extension is the only evidence it is a Python script at all.
D-WIRING is not loosened by this — it still compares the resolved path against the one expected script.

## R2-02 — a bounded common subset, with the JS side measured

`classify_pattern()` replaces the blocklist. It is a single linear scan that returns `common`, `js-error` or
`unknown`, and tracks whether the previous element can take a quantifier — which is what catches the whole
possessive family positionally (`a++`, `a*+`, `a?+`, `a{1,2}+`) instead of as a list of spellings, and also
catches `*a` and `^*`. Inline flag groups, `(?P<`, `(?P=`, `(?#`, `(?>`, `(?(` and unbalanced brackets are
`js-error`; lookbehind, JS named groups, `\p{…}`, `[]…]`, `{,n}` and any escape outside the confirmed set
are `unknown`. Only `common` reaches `re.search`.

`matcher_covers()` no longer strips before the wildcard case, and a whitespace-only matcher now returns
unknown with a reason instead of comparing against an empty name list. A confirmed `js-error` matcher on a
required row gets its own D-WIRING FAIL naming the pattern, and is then excluded from the per-tool
computation, so it reads as "this pattern matches nothing" rather than "unknown".

Before → after on the four false-PASS routes:

```text
(?i)Write|Edit|Bash|PowerShell   True  -> False  (JavaScript 정규식이 아닙니다 — 인라인 플래그)
Bash++                           True  -> False  (… — possessive 수량자)
" * "                            True  -> False  (정규식 ' * ' 부분 일치)
"   "                            True  -> None   (공백뿐이라 이름 목록도 정규식도 아닙니다)
```

And the cases that must keep working: `*`, `""`, absent → True; `Write, Edit`, `[Ww]ri`, `.*`, `mcp__.*`,
`Note.*book`, `Write$`, `(Write|Edit)`, `Writ[a-z]?e`, `Write\b` all resolve; `\AWrite`, `\p{L}rite`,
`(?<=sub)Write`, `(?<name>Write)`, `[]Write`, `Write{,2}` are unknown and carry no FAIL.

The FAIL wording says only that the pattern is not a valid JavaScript regular expression and therefore
matches nothing. It does not say what Claude Code does when it meets one, which I have not observed.

## R2-03 — the two value types, and nothing wider

`unmapped_by_design` values and `mappings[].why` are now checked as strings, reported per field, with no
`minLength` of my own invention: `{"docs/": ""}` and `"why": ""` stay legal, and a missing `why` stays
legal. Parametrised over `42`, `None`, `[]`, `{}`, `True` for the first and `[]`, `42`, `None` for the
second. I did not extend this to the root fields from R3-01 — that is the scope question still open.

## R2-04 — the fallback is resolved before the suffix is judged

`selected_quality_tracked()` and `selected_history_tracked()` reproduce the two consumers' selection, and
`_tracked_live()` turns that into the per-field predicate: `source_prefixes` is live iff either
`tracked_paths` resolves empty, `harness_paths` iff `history.tracked_paths` does. A bare directory in a live
field is still FAIL; in a dormant one it is a WARN that says, in so many words, that nothing reads the entry
and this is not a fault — and the test asserts that phrase, so a later rewrite cannot quietly turn it back
into a gate-off claim. The FAIL message was also rebuilt (R3-03); all four `impact` strings now end in
"변경 감지" so the sentence frame fits.

```text
explicit quality+history, source_prefixes=["src"], harness_paths=["tests"]
  -> both PASS, two WARNs, FAIL 0            (was: two FAILs, exit 1)
both tracked_paths emptied
  -> source_prefixes[0] FAIL, harness_paths[0] FAIL
only history.tracked_paths emptied
  -> both FAIL (the history fallback is source_prefixes + harness_paths)
only quality.tracked_paths emptied
  -> source_prefixes FAIL, harness_paths spared
blank-only tracked_paths (["   "])
  -> the fallback is selected, so source_prefixes FAIL
control: ["src/"], ["tests/"]
  -> four PASS, no finding
```

## The `_hookutil` comparison test, and what it closes

New section 8 in `tests/test_doctor.py` uses conftest's `load_hook` to import the real consumer modules
against a given config and compare values, which is the distinction you drew: the diagnostic runtime must
not import `_hookutil`, but a test may stand the two side by side. It pins

- `selected_quality_tracked` against `auto_test_check.QUALITY_TRACKED_PATHS` and
  `selected_history_tracked` against `history_check.TRACKED_PATHS`, over nine configs including blank-only
  entries, a non-list, and a list with a non-string member;
- `wiki_root_of` against `_hookutil.WIKI_ROOT` and `history_prefix_of` against `history_prefix()`, over
  seven configs including a missing trailing slash, a whitespace value and an already-prefixed path;
- `chosen_python` against `venv_python()`, both the configured-hit case and the full fallback order.

That is why I extracted `chosen_python()` from `check_python()` — the branch was inlined and could not be
compared. Behaviour is unchanged; it is the one refactor of working code in this round.

This closes the gap I recorded as open at the end of Round 2, and I rewrote both Plan entries' claims to
match. What the comparison does **not** cover, and I have said so in the target-root entry: it checks that
the same config yields the same value, so if a consumer grows a new branch Doctor does not have, the test
passes quietly.

## Judgment calls in the fix — two are scope questions for you

1. **An unknown Python option is a FAIL, not just a WARN.** Your expected behaviour says the command is
   D-HOOK unresolved WARN and the remaining required wiring is D-WIRING FAIL, which is what I implemented.
   The consequence is that a hook command Doctor does not understand is reported as a missing connection.
   The option table covers what hook commands plausibly use, but it is closed by design.
2. **The JS-invalid matcher FAIL is reported only on required rows that have tools.** Not on the Stop row,
   because the spec says that row has no matcher check, and not on hooks for other events, because D-WIRING
   is limited to the three rows. So an invalid matcher on, say, the heredoc hook stays unreported. Same
   family as R3-01, and I did not widen it on my own.
3. `[]` is unknown, not an error: V8 accepts it as a never-matching class while Python reads `]` as a
   member, so the two disagree without either rejecting it.
4. `{,2}` is unknown for the same reason — Python reads it as `{0,2}`, V8 as a literal.
5. The confirmed-escape set is an allowlist, so a spelling I missed falls to unknown rather than to a wrong
   PASS. That inverts the failure direction of the old list, which is the point of the change.

## Commands run, with results

```text
.venv/Scripts/python.exe -m pytest tests/test_doctor.py -q   210 passed, 1 skipped
.venv/Scripts/python.exe -m ruff check .                      All checks passed!
.venv/Scripts/python.exe -m ruff format --check .             71 files already formatted
.venv/Scripts/python.exe -m pytest -q                         615 passed, 1 skipped in 12.22s
python .claude/harness/scripts/doctor.py                      PASS 24 · WARN 5 · FAIL 0, exit 0
```

615 against 533 before, so 82 tests were added and none removed; the two Round 2 assertions that encoded
the old behaviour were replaced rather than deleted, and both of their subjects are now covered by more
cases than before. This repository's own diagnosis is unchanged, which is the control: its
`source_prefixes` and `harness_paths` entries already end in `/` or name files, and its matchers take the
name-list path, so none of the four fixes moves its verdict.

The `ruff format` count is still 71 — the files I touched were already counted.

## Still open after this round

- **R3-01** — whether root `python`, `source_prefixes` and `harness_paths` should be type-checked. Not
  implemented; it changes D-CONFIG's scope.
- **Q-1** — implemented as specified. Reverse it if you would rather a padded `*` be an unconfirmed WARN;
  one test (`test_wildcard_special_case_is_not_stripped`) and one line of `matcher_covers` would move.
- **Judgment calls 1 and 2** above.
- **Linux / POSIX** unverified, unchanged. One skipped test, still the POSIX execute-bit case.
- **Claude Code's own matcher and option handling** not read from source; the verdicts rest on the
  documented contract, V8 measurements and Python's documented CLI.
- **Nothing is committed.** The preservation condition for cleanup is still unmet, and I have not created a
  commit to satisfy it.

# Round 4 — your result review, checked before fixing

Both findings are real, and I reproduced each from your recipe before touching any code. The empty-argument
defect is worse than you reported in one respect: it also misfires in the opposite direction, on a command
real Python runs. Your R3-04 correction holds, and my FAIL text was wrong in a second way you did not name —
it asserted that the syntax does not exist in JavaScript, which is now false for `i`/`m`/`s`.

## How I checked

| What | How |
|---|---|
| `tokenize`, `_script_token`, `parse_command` | the real functions loaded from `.claude/harness/scripts/doctor.py`, four argv shapes |
| The CLI verdict and exit code | a copied project in a temp root (`.claude/` tree, `src/`, `tests/`, `pyproject.toml`, `CLAUDE.md`); every hook command or the fast matcher rewritten; `doctor.py` run as a subprocess with `-I -X utf8` |
| What real Python does with that argv | `.venv/Scripts/python.exe` against a marker script that prints when it runs |
| What V8 does with each pattern | `new RegExp` in this session's browser — Chrome 156.0.8078.100 |
| What the standard says | MDN's `Modifier: (?ims-ims:...)` page, read 2026-11-22 |

The V8 and Python numbers below are my own runs, not your report's.

## R2-01 extra — confirmed, and the same defect fires the other way too

The mechanism is narrower than "`tokenize` drops empty arguments". `tokenize` (`doctor.py:912`–`:923`)
keeps the quote state in `quote` and the characters in `current`, and appends a token only `if current` — at
the whitespace boundary (`:914`) and at the end (`:922`). Opening and closing a quote leaves no trace in
`current`, so the token disappears entirely. `_script_token` is then handed an argv that never contained the
empty slot; as you say, it cannot recover what is already gone.

Measured, with `HOOK = "${CLAUDE_PROJECT_DIR}/.claude/harness/hooks/auto_test_check.py"`:

| Command | `tokenize` | `parse_command` |
|---|---|---|
| `python "" "<HOOK>"` | `['python', '<HOOK>']` | script `.claude/harness/hooks/auto_test_check.py`, no note |
| `python '' "<HOOK>"` | same | same |
| `python -W "" "<HOOK>"` | `['python', '-W', '<HOOK>']` | **unresolved** — "실행할 스크립트 인자가 없습니다." |
| `python "<HOOK>" ""` | `['python', '<HOOK>']` | script resolved (correct verdict, by luck) |

End to end, with every hook command in the copied project rewritten:

- `python "" <hook>` → `PASS 23 · WARN 4 · FAIL 0`, exit 0. D-HOOK reports "프로젝트 내부 스크립트 21건이
  모두 있습니다" and all three D-WIRING rows PASS. `''` behaves identically. This is your finding, confirmed.
- Real Python, same argv: `python "" marker.py` → exit 1, the marker never ran. The error names what
  actually happens: `can't find '__main__' module in '<cwd>'`. Python read the empty argument as a
  **directory path** — the current directory — and looked for `__main__.py` in it. So the second argument is
  not merely ignored; the empty slot is itself the thing Python tried to run. That is the sense in which the
  spec's "프로젝트 루트 경로로 해석하지 않는다" matters.

The other direction, which your report does not cover:

- `python -W "" <hook>` is a command real Python runs. Measured: exit 0, the marker ran with
  `argv == ['marker.py']` — an empty `-W` value is accepted and the script still executes.
- Doctor today calls that same wiring broken. The empty value vanishes, `-W` consumes the hook path as its
  value, and the walker reports "실행할 스크립트 인자가 없습니다." The CLI result is 21 D-HOOK 미확인 WARNs
  and the three required D-WIRING rows FAIL, exit 1 — a false alarm on a working configuration.

So preserving the empty token is not only about refusing the broken form; it repairs both directions at
once. Your 검증 기준 already lists `-W ""` as a case that must keep working — I am reporting that it is
already wrong today, not merely at risk from the fix.

One trap the fix has to place deliberately: once the empty token survives tokenization, `_script_token`
returns `""` as the script candidate (it does not start with `-`), and `parse_command:` then does
`Path("")` → `root / ""` → `root`, whose `relative_to(root)` is `.`. A directory that exists would be
reported as a resolved script named `.`. The empty positional has to be stopped in the walker, where the
position is known, rather than left to the path code.

## R3-04 — confirmed, and the reason to leave it UNKNOWN is not the one in your note

`_INLINE_FLAG_RE` (`doctor.py:109`) is `^\(\?[aiLmsux]*-?[aiLmsux]+[:)]`. The trailing `[:)]` makes it match
the global form `(?i)` and the scoped form `(?i:` with one rule, and `_classify_group` (`:1075`) returns
`JS_ERROR` for both. Measured on the CLI: `(?i:Write|Edit|Bash|PowerShell)`, `(?s:…)`, `(?-i:…)` and
`(?im-s:…)` each produce two D-WIRING FAILs, `PASS 22 · WARN 4 · FAIL 2`, exit 1 — a normal configuration
called broken, exactly as you describe.

V8 (Chrome 156.0.8078.100), measured this session:

| Pattern | V8 `new RegExp` |
|---|---|
| `(?i:Write)` | compiles; matches `Write` **and** `write` |
| `(?s:Write)`, `(?-i:Write)`, `(?im-s:Write)`, `(?ims:Write)`, `(?mi:Write)`, `(?is-m:Write)`, `(?m-i:Write)`, `(?i-:Write)` | compile |
| `(?i)Write` | `Invalid group` |
| `(?x:Write)`, `(?u:Write)`, `(?a:Write)`, `(?L:Write)`, `(?sx:Write)` | `Invalid group` |
| `(?i-i:Write)` | `Repeated flag in flag group` |
| `(?-:Write)` | `Invalid flag group` |
| `(?i:Write` | `Unterminated group` |

MDN's Modifier page agrees with every row and adds the rules behind them: the flags are exactly `i`, `m`,
`s`; they must be unique across the two sides; at least one side must be non-empty, so `(?-:…)` is a syntax
error; `g`, `y`, `d`, `u`, `v` are syntax errors inside a modifier; and JavaScript has only the bounded form,
which is why the global `(?i)` stays an error. Two notes on your citation, neither of them substantive: the
page is labelled **Baseline 2025 · newly available** and its Specifications row points at the ECMAScript 2027
draft (`prod-RegularExpressionModifiers`), not the 2025 edition.

**Where I differ from your stated reason.** Your note treats this as "we don't know whether the engine
supports it, so don't call it a language error". The semantics are not in doubt at all: where modifier groups
exist, Python's `(?i:…)` and JavaScript's `(?i:…)` mean the same thing — flag scoped to the group — so this
is not a case of two engines reading one pattern differently. What is unresolved is **engine age**. Modifier
groups are a 2025 addition; an engine that predates them rejects `(?i:` exactly as it rejects `(?i)`. I have
not observed which engine the product runs, so the same matcher is either "covers all four tools" or "matches
nothing", and I cannot tell which. That is UNKNOWN in both directions — not FAIL, not PASS. I will record
that reason rather than "JavaScript has no such syntax", which is what the current message says and is now
false.

**What stays FAIL, and why that is still measurement-backed.** The global `(?flags)` form, a scoped group
with a flag letter outside `i`/`m`/`s`, `(?-:`, and a flag repeated across the two sides are all errors in an
engine that *does* support modifiers (measured above) and in one that does not (it rejects every `(?…` flag
group). The error is engine-independent, so those keep the FAIL class. Only the well-formed `i`/`m`/`s`
scoped group moves to UNKNOWN. This keeps `(?x:…)` — a Python-only flag that can never work in any JS engine
— out of the WARN bucket.

## What the fix will touch

1. `tokenize` — track whether the token was quoted, and append on a quote boundary even when `current` is
   empty. The `#` comment branch has to look at that flag too, so `"" #x` and `""#x` do not change meaning.
2. `_script_token` — an empty positional stops the walk with its own note ("빈 스크립트 자리"), before any
   path handling. Option values stay as they are: `-W ""` already consumes two tokens, so the empty value is
   skipped and the hook path is found.
3. `_classify_group` — split the global form from the scoped one. Global `(?flags)` and malformed or
   non-`i`/`m`/`s` scoped groups keep `JS_ERROR` with a message that names the measured reason; well-formed
   `i`/`m`/`s` scoped groups return `UNKNOWN` with the engine-age reason.
4. `tests/test_doctor.py` — `test_inline_flags_are_js_errors` pins `(?s:Write)` as an error and has to be
   split: the global form and the invalid-flag forms stay FAIL, the scoped forms become UNKNOWN. New cases
   for `python "" <hook>`, `python '' <hook>`, `python -W "" <hook>`, `python <hook> ""`, and for a required
   row whose only command has an empty script slot (D-WIRING FAIL, exit 1).
5. `.claude/wiki/knowledge/doctor.md` — the matcher table row and the script-slot table; both say "Python
   인라인 플래그" without the global qualifier, and the script-slot table has no row for the empty argument.
6. `.claude/wiki/history/plan/2026-11-22-doctor-matcher-semantics.md` — the 결정 bullet and the 3a rejection
   table describe the whole inline-flag family as a confirmed JS error. The `(?i)Write` row stays correct;
   the sentences around it need the bounded/unbounded distinction and the Baseline-2025 fact.

## One choice I would like you to confirm

Non-`i`/`m`/`s` scoped groups (`(?x:…)`, `(?u:…)`, `(?a:…)`, `(?L:…)`), `(?-:…)` and a flag repeated across
the two sides stay **FAIL** in my plan, on the measurements above. Your 검증 기준 only requires that valid
`i`/`m`/`s` combinations stop being FAIL, so this is my reading of the boundary, not something you asked for.
If you would rather every `(?…:` modifier group be UNKNOWN, it is one branch and one test.

## What I did not verify

- **Which JavaScript engine Claude Code runs.** Unchanged, and it is the whole basis of the UNKNOWN verdict
  above. If that engine is known to be 2025-or-newer, the scoped form could be promoted to the common subset.
- **Whether the product trims matcher whitespace** (Q-1). Unchanged; you kept the current behaviour.
- **The ECMAScript spec text itself.** I read MDN, not the specification document.
- **Linux / POSIX.** Unchanged, still one skipped test.
- **Python's option table against the CPython source.** The `-W ""` result above is a measurement of the
  installed 3.12, not a reading of the argument parser.

## Round 4 recommendation

Both findings are mine to fix, and neither is a scope question. I plan to fix them in the same implementation
and tests, re-run the gate plus the four earlier probes, and report under "Round 4 — implementation report".

# Round 4 — implementation report

Both findings are fixed in the same implementation and tests. Every number below is my own run after the last
documentation edit, and each fix is shown against the counterexample it had to stop.

## Files changed

| File | State |
|---|---|
| `.claude/harness/scripts/doctor.py` | 2245 lines, 67 defs (was 2187 / 66) |
| `tests/test_doctor.py` | 1489 lines, 111 test functions, 246 cases (was 210) |
| `.claude/wiki/knowledge/doctor.md` | 264 lines — matcher table, modifier rule, script-slot table, counts |
| `.claude/wiki/history/plan/2026-11-22-doctor-matcher-semantics.md` | amended in place again |

`README.md` needed nothing: it carries no counts and no matcher detail. `tasks/doctor.md` is yours and I did
not touch it. `.claude/wiki/history/plan/2026-11-22-doctor-target-root.md` is unchanged — this round touched
neither the root nor the interpreter choice.

## R2-01 extra — the empty argument survives tokenization, and position decides what it means

`tokenize` now keeps a `quoted` flag beside `current`, because an opened-and-closed quote leaves nothing in
the character buffer. A token is emitted when `current or quoted`, at the whitespace boundary and at the end.
The `#` branch looks at `quoted` as well, so `""#x` stays one token — a shell reads `#` as a comment only at
a word start.

`_script_token` stops on an empty positional with its own note, before any path handling. That placement is
deliberate: `parse_command` would otherwise take `""` as the candidate, and `Path("")` → `root / ""` → `root`
→ `relative_to(root)` is `.`, a directory that exists, so the empty slot would have been reported as a
resolved script. The position is only known in the walker.

| Command | Before | After |
|---|---|---|
| `python "" <hook>` | script resolved → `PASS 23 · WARN 4 · FAIL 0`, exit 0 | D-HOOK 미확인 WARN + required D-WIRING FAIL, exit 1 |
| `python '' <hook>` | same false PASS | same as above |
| `python -W "" <hook>` | "실행할 스크립트 인자가 없습니다" → 21 WARNs, 3 FAILs, exit 1 | script resolved → `PASS 23 · WARN 4 · FAIL 0`, exit 0 |
| `python <hook> ""` | resolved (correct by luck) | resolved, now for the right reason |

The third row is the direction your report does not cover, and real Python settles it: `python -W "" marker.py`
exits 0 and runs the script, while `python "" marker.py` exits 1 with `can't find '__main__' module in
'<cwd>'` and never runs it. One defect, two opposite false verdicts, one fix.

## R3-04 — the global form and the scoped modifier are now separate classes

`_INLINE_FLAG_RE` is gone. In its place: `_GLOBAL_FLAG_RE` (`^\(\?[a-zA-Z]+\)`), `_SCOPED_FLAG_RE`
(`^\(\?([a-zA-Z]*)(?:-([a-zA-Z]*))?:`), `_JS_MODIFIER_FLAGS = frozenset("ims")`, and `_classify_modifier`,
which reads the two flag sides and returns:

- `JS_ERROR` when a letter falls outside `i`/`m`/`s`, when both sides are empty (`(?-:`), or when a flag
  repeats — all errors in an engine that supports modifiers (measured) and in one that does not;
- the new internal `MODIFIER` kind otherwise, carrying the engine-age reason.

Two structural details. `_classify_group` now resolves `(?:`, `(?=`, `(?!` **before** the flag rules, so the
modifier regex cannot claim a plain non-capturing group. And `MODIFIER` does not stop the scan: `classify_pattern`
records it as a *pending* UNKNOWN and keeps reading, so a confirmed error later in the same pattern still
wins. I added that after comparing my first version against my own V8 table — it returned UNKNOWN for the
unterminated `(?i:Write`, which would have dropped a confirmed-error class the Plan document claims. Measured
now: `(?i:Write` , `(?i:Write))`, `(?i:[Write)` and `(?i:Bash++)` are all FAIL.

All 19 patterns I measured in V8 now agree with Doctor on the FAIL boundary — zero mismatches:

| Patterns | V8 | Doctor |
|---|---|---|
| `(?i:W)` `(?s:W)` `(?-i:W)` `(?im-s:W)` `(?ims:W)` `(?mi:W)` `(?is-m:W)` `(?m-i:W)` `(?i-:W)` | compile | UNKNOWN, `covers` is None |
| `(?:W)` | compiles | COMMON, `covers` True |
| `(?i)W` | `Invalid group` | JS_ERROR |
| `(?x:W)` `(?u:W)` `(?a:W)` `(?L:W)` `(?sx:W)` | `Invalid group` | JS_ERROR |
| `(?i-i:W)` | `Repeated flag` | JS_ERROR |
| `(?-:W)` | `Invalid flag group` | JS_ERROR |
| `(?i:W` | `Unterminated group` | JS_ERROR |

At report level, a required row whose only matcher is `(?i:Write|Edit|Bash|PowerShell)` is now
`PASS 22 · WARN 5 · FAIL 0`, exit 0 — WARN on that row, no PASS, no FAIL. `(?i)…` and `(?x:…)` still give
`FAIL 2`, exit 1. The FAIL text changed from "Python 인라인 플래그는 JavaScript 에 없습니다" to
"전역 인라인 플래그는 JavaScript 에 없습니다" and, for the flag letters, "modifier 그룹은 i·m·s 만
받습니다 — `x` 는 Invalid group 입니다".

## One change the fix made necessary

The unconfirmed-matcher WARN repeated its reason once per candidate hook, and my new reason is long enough
that the line became unreadable. `check_wiring` now de-duplicates the notes per tool (`dict.fromkeys`, order
preserved). The per-tool repetition is unchanged — that is the existing message shape.

## Judgment calls in the fix

1. **Non-`i`/`m`/`s` scoped groups stay FAIL**, as flagged in the review above. Your 검증 기준 only required
   that valid `i`/`m`/`s` combinations stop being FAIL.
2. **`(?i-:…)` is UNKNOWN, not FAIL.** MDN allows one empty side and V8 compiles it (measured). Only *both*
   sides empty is an error.
3. **`""#x` is one token `#x`.** A shell starts a comment at a word boundary, so the quote ends the comment
   opportunity. Pinned by a test.
4. **The pending-UNKNOWN mechanism applies only to modifier groups.** `(?<`, POSIX classes, `{,n}` and the
   other UNKNOWN branches still return immediately, so `(?<=a)Bash++` remains UNKNOWN rather than FAIL. That
   is pre-existing behaviour and widening it would change verdicts you have already accepted; say so if you
   want the same treatment everywhere.

## Tests

- `test_inline_flags_are_js_errors` is gone. It asserted the thing you corrected. In its place:
  `test_global_inline_flags_are_js_errors` (4 cases), `test_scoped_modifier_groups_are_unknown` (9 cases,
  one per V8-measured form, and it asserts the note names 2025 so the reason cannot drift back to "JS has no
  such syntax"), `test_modifier_flags_outside_ims_are_js_errors` (7 cases),
  `test_confirmed_error_inside_a_modifier_group_wins` (4 cases) and `test_scoped_modifier_wiring_is_warn_not_fail`
  at report level.
- `test_tokenize_keeps_empty_arguments` (8 cases) pins the token list itself, including `-W ""`, a trailing
  `""`, two empties in a row, and the two comment cases.
- `test_direct_python_call_forms` gained `python -W "" <hook>` and `python <hook> ""`;
  `test_unresolvable_commands_warn_and_do_not_prove_wiring` gained `python "" <hook>` and `python '' <hook>`,
  which is where the D-HOOK WARN and D-WIRING FAIL pair from your 검증 기준 is asserted.
- Nothing else changed: 210 → 246 cases, and no existing assertion was weakened.

## Commands run, with results

| Command | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_doctor.py -q` | 246 passed, 1 skipped |
| `.venv/Scripts/python.exe -m ruff check .` | All checks passed! |
| `.venv/Scripts/python.exe -m ruff format --check .` | 71 files already formatted |
| `.venv/Scripts/python.exe -m pytest -q` | 651 passed, 1 skipped, 12.93s |
| `python .claude/harness/scripts/doctor.py` | PASS 24 · WARN 5 · FAIL 0, exit 0 |

`ruff format` reformatted `tests/test_doctor.py` once (a long parametrize line) before the check passed; the
71 count is unchanged because the files were already counted. This repository's own diagnosis is the control:
its tracked entries already end in `/` or are files, and its matchers take the name-list path, so neither fix
moves a verdict here. `tests/test_hook_wiring.py` is untouched and passing, which is the check that the
narrowed matcher rules did not disturb this repository's wiring verdicts.

## Still open after this round

- **R3-01** — unchanged, deferred by your decision; not implemented.
- **Q-1** — unchanged, current behaviour kept per your decision.
- **Judgment calls 1–4 above**, plus the two from Round 3 you already accepted.
- **Which JavaScript engine the product runs.** Unobserved, and it is the whole reason the scoped form is
  UNKNOWN rather than COMMON. If it is known to be 2025-or-newer, that group can be promoted.
- **Linux / POSIX** unverified, one skipped test, unchanged.
- **Claude Code's matcher handling and CPython's argument parser** not read from source. The verdicts rest on
  the documented contracts, V8 measurements and the installed Python's behaviour.
- **Nothing is committed.** The preservation condition for cleanup is still unmet, and I have not created a
  commit to satisfy it.
