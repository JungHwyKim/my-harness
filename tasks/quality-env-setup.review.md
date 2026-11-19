# quality-env-setup — review and state confirmation

Date: 2026-11-20, on `main` at `4b26083`; preservation round on `c433850`. The spec is
`tasks/quality-env-setup.md`, last refreshed 2026-11-19 against `bfeb428`.

This is the file the spec's header has pointed at as 「후속 리뷰」 since it was
written. It did not exist until now — see R1. No environment work was redone:
the spec's 실행 계약 forbids that. So this is a state confirmation against the
완료 기준, and every command below was actually run today.

## Verified today

| Check | Command | Result |
|---|---|---|
| interpreter at the configured path | `.venv/Scripts/python.exe --version` | Python 3.12.5 |
| pinned versions installed | `-m pytest --version`, `-m ruff --version` | pytest 9.2.0, ruff 0.17.5 — identical to `requirements.txt:7`, `:8` |
| install consistency | `-m pip check` | `No broken requirements found.`, exit 0 |
| requirements encoding | byte scan | ASCII only, so `pip install -r` survives a cp949 shell |
| `.venv/` excluded | `git check-ignore -v .venv` | matched by `.gitignore:5` |
| documents tracked | `git ls-files --error-unmatch` | `README.md`, `requirements.txt`, `tasks/_template.md` all tracked |

### Full profile — all three stages re-run

| Stage | Command | Result |
|---|---|---|
| lint | `ruff check .` | `All checks passed!`, exit 0 |
| format | `ruff format --check .` | `70 files already formatted`, exit 0 |
| tests | `pytest -q` | **405 passed** in 8.32s, exit 0 |

This is a current result, not a citation. The 2026-11-19 refresh deliberately did
not re-run the stages and cited `tasks/handoff.review.md:388` for the same 405.
Re-run now, the two agree.

## 완료 기준

| Criterion | Verdict |
|---|---|
| 환경 구축 완료와 최신 Full 통과 보고가 구분되어 있으며, 과거 실패는 해결 이력으로 남는다 | Met. The spec separates them and keeps F5 and F6 as resolved history |
| 기존 리뷰의 실행 증거로 연결되며, 필요 없는 재설치·검사 반복이나 기존 코드 변경이 없다 | Met. Every citation checked below; nothing reinstalled, no code changed |
| 추가 보고는 작업 ID에 맞는 리뷰에 남는다 | Met as of this file |

### The spec's citations, checked

All resolve: `handoff.review.md:159` (Environment result), `:186` (the three
stages that failed then), `:265` (Round 3), `:380` (F6 closed), `:388` (the green
Full); `harness.json:14` (tracked paths), `:41`, `:46`, `:51` (the three Full
argv); `requirements.txt:7`, `:8` (the pins). No stale line numbers — worth
stating, since `handoff.review.md` has been appended to several times since those
citations were written.

## Findings

### R1 · P2 — the review path the spec advertised was empty

The header has named `tasks/quality-env-setup.review.md` as 「후속 리뷰」 since the
spec was written, and the procedure puts Claude's reports in the same-ID review
file. The actual evidence went to `tasks/handoff.review.md` Rounds 2 and 3, under
the task this one was carved out of. Nothing was lost, but a reader following the
spec's own pointer found nothing.

Fixed by this file. The evidence stays where it was executed and is cited above
rather than copied.

**No blocking findings.** Nothing in the spec contradicts the current repository.

## Changed since the 2026-11-19 refresh

1. `.claude/wiki/knowledge/quality-env.md` exists as of `4b26083`. It holds the
   environment contract: the silent interpreter fallback, the ASCII rule, both
   profiles with their triggers and `fast`'s `success_codes [0, 5]`, the single
   `src/` → `tests/` mapping, and the Ruff selection. That is cleanup condition 2
   of the handoff procedure for this task.
2. The Full profile was re-run today and is green.
3. `main` is pushed through `4b26083`, so cleanup condition 3 holds for the spec.
   It does not yet hold for this file.

## Not run, and why

- `pip install -r requirements.txt` — not re-run. The build is reported finished
  and `pip check` passes. The spec excludes 필요 없는 재설치, and reinstalling could
  only disturb a working environment.
- Linux and CI — no such environment is available here. They stay unverified,
  which is what the spec's 호환성 절 already says.
- The `fast` profile — no mapped target exists. `quality.tracked_paths` is
  `src/`, `tests/`, `pyproject.toml`, `.claude/harness.json`, and the only
  mapping is `src/` → `tests/`, so a documentation change gives `fast` nothing to
  run. `full` covers the checkout regardless of path, and it is green.

## Codex's verdict and the preservation round — 2026-11-20

Codex reviewed `main` at `c433850` and **approved**: the environment build and
this report meet the 완료 기준, no blocking findings, and R1 is resolved by this
file existing. It asked for no reinstall and no further environment work. Its
three preservation conditions, and what this round did about them:

1. **`knowledge/quality-env.md`'s 「현재 확인된 상태」 was stale.** It attributed the
   Full result to `tasks/handoff.review.md` and said it had not been re-run
   since. Updated: the three stages carry today's numbers, `pip check` has its
   own row, and every row names when it was checked and by whom — Codex verified
   the interpreter, the pins and `pip check` itself, while the Full re-run is
   Claude's report, which the table says outright rather than implying a Codex
   re-execution.
2. **The permanent contract no longer hangs on a temporary file.** The figures
   now sit in that document, and the install record's location is given with its
   preservation commit — `07bd76e`, plus `git log --all -- tasks/handoff.review.md`
   for finding it later. So cleaning up `handoff.review.md` under its own task
   cannot strand this contract. That file was not touched here; it belongs to
   another task.
3. **Condition 3 is not met.** This file is still untracked, so none of it is
   preserved in a commit, and Codex is explicit that creating or staging is not
   preservation and that nothing may be committed or pushed without approval.

## Remaining

1. **Step 9 cleanup.** It needs this file in a confirmed commit first, along with
   the spec's current text — Codex's verdict in it is still uncommitted — and
   then the two temporary files removed. Not authorized in this round.
2. **The two cleanups are coupled.** `tasks/handoff.md:19` cites this review
   file's 2026-11-20 Full result, so removing this pair first leaves that
   citation dangling until handoff's own cleanup removes the file that carries
   it. Both pairs are slated for deletion, so the end state is sound; only the
   window between them is exposed. handoff.md's own step-9 list asks for the
   references in `quality-env.md` to be repointed at preserved commits before
   its pair goes — this round did that side of it. `quality-env-setup.md` still
   cites `handoff.review.md` line by line, and that spec is Codex's.
3. Nothing else is open. No further environment work is specced.
