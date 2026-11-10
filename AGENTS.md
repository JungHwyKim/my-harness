# Codex Working Guide

## Start Here

- Before starting work, read `CLAUDE.md` and follow its **Global Rules**,
  **Context Router**, and **Information Ownership** sections.
- This file is the Codex entry point. `CLAUDE.md` remains the shared source for
  project-wide context; do not copy its contents here.

## Context Loading

Load only the context needed for the task, in this order:

1. Read `.claude/wiki/overview/README.md` to orient yourself in the project.
2. Read the relevant document under `.claude/wiki/knowledge/` for current
   contracts and behavior.
3. Read `.claude/wiki/history/` only when the reason for an earlier decision is
   necessary to make a safe change.
4. For a matching repeatable workflow, read its `.claude/skills/<name>/SKILL.md`
   before using that workflow.

Do not load all wiki or history documents by default.

## Quality Gate

- Claude Code hooks in `.claude/settings.json` do not run automatically in
  Codex.
- After changing code or harness configuration, manually run the applicable
  Quality Profile from `.claude/harness.json`:
  - `fast`: after a scoped change, run the affected tests.
  - `full`: before completion or commit, run lint, format check, and the full
    test suite when the change warrants it.
- Report any check that was not run and why.

## Instruction Ownership

Keep `AGENTS.md` under 120 lines. It may contain only durable, repository-wide
rules and routes to their source documents.

Before adding a rule here, confirm all three:

1. It applies to most tasks.
2. It must be known before opening task-specific documentation.
3. It is likely to remain true for at least three months.

If any answer is no, put the information in its proper owner instead:

- Current module contract: `.claude/wiki/knowledge/`
- Project map: `.claude/wiki/overview/`
- Decision rationale: `.claude/wiki/history/`
- Repeatable multi-step procedure: `.claude/skills/`
- Commands and quality configuration: `.claude/harness.json` or its scripts
- Temporary incident workaround: an issue, plan, task log, or pull request

Link to the source of truth; never duplicate long procedures, checklists, or
module-specific rules in this file.
