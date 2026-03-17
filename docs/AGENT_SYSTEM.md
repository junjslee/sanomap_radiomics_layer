# Agent System

## Purpose
This file explains how the global `agent-os` architecture is applied in the Sanomap repository.

Use it to answer:
- what counts as canonical memory here
- what is Claude-only
- what is Codex-only
- where optional plugins such as `claude-mem` fit

## Layer Map For This Repo
### 1. Global `agent-os`
This repo inherits the user's cross-project workflow from `~/agent-os`.

That layer defines:
- global workflow policy
- shared skills
- shared subagents
- bootstrap and sync logic
- Conda `base` as the local Python runtime for `agent-os`

### 2. Shared Repo Truth
These files are canonical for this project:
- `AGENTS.md`
- `docs/REQUIREMENTS.md`
- `docs/PLAN.md`
- `docs/PROGRESS.md`
- `docs/RUN_CONTEXT.md`
- `docs/NEXT_STEPS.md`
- `pipeline_tracking.md`

These files must stay authoritative even if a tool adds its own memory, history, or plugin state.

### 3. Claude Adapter
Claude-specific repo runtime lives in:
- `CLAUDE.md`
- `.claude/settings.json`
- `.claude/hooks/`

Claude-local-only state stays outside Git:
- `.claude/settings.local.json`
- Claude auth state
- optional Claude plugins and their local data

### 4. Codex Adapter
Codex-specific repo runtime lives in:
- `.codex/config.toml`

Codex depends on:
- the shared repo docs above
- repo trust for this path or worktree path
- global Codex skills installed by `agent-os`

Codex-local-only state stays outside Git:
- any future `.codex/config.local.toml`
- home-directory Codex auth and trust state

### 5. Cursor Role
Cursor is the editing and review surface.

It is not the canonical runtime authority for this repo.

## Source Of Truth Order
When there is any conflict, use this order:
1. Shared repo docs
2. Repo-local runtime files
3. Global `agent-os`
4. Optional plugin or tool memory

## What This Repo Commits
Commit:
- workflow docs
- handoff docs
- repo runtime files that another operator can reuse

Keep local:
- `sample_papers/`
- `.claude/settings.local.json`
- home-directory auth and trust state
- `.env*`, `secrets/`, and private keys

## Sanomap-Specific Runtime Rules
- Cursor is not a third runtime target.
- Local helper work and repo automation should run in Conda `base`.
- Local Mac runs are valid for orchestration, smoke tests, audits, and light experimentation.
- Real model-backed merged relation production is non-local by default.

## Worktree And Agent Usage
Preferred worktree lanes:
- `research/query-*`
- `fix/entity-cleanup-*`
- `ops/remote-run-*`
- `docs/handoff-*`

Preferred agent usage:
- Claude:
  use the global `planner`, `researcher`, `reviewer`, `test-runner`, and `docs-handoff` agents
- Codex:
  use built-in exploration and bounded worker delegation with the same shared repo docs

## Allowed Automation
Allowed bounded loops:
- query exploration and selection
- training or model-selection experiments

Not allowed:
- unattended code-writing
- auto-merge
- unattended graph promotion

## `claude-mem` In This Repo
`claude-mem` is not part of the canonical Sanomap system today.

If added later, it belongs in the Claude-only layer.

What it could help with:
- recalling prior Claude sessions
- retrieving past debugging or implementation context

What it must not replace:
- `AGENTS.md`
- `docs/PLAN.md`
- `docs/PROGRESS.md`
- `docs/NEXT_STEPS.md`
- `docs/RUN_CONTEXT.md`

Important consequence:
- `claude-mem` does not make Codex smarter by itself
- it does not replace shared repo memory
- any durable insight retrieved through Claude should be written back into repo docs

## Current Gap Vs `claude-mem`
This system already gives:
- explicit persistent project memory
- clear handoff state
- cross-tool shared truth
- reproducible repo behavior

This system does not yet give:
- automatic cross-session episodic recall
- plugin-driven memory search
- automatic capture of every Claude interaction

That gap is acceptable because the repo favors explicit, reviewable markdown memory over opaque tool-private memory.

## Session Checklist
1. Read `AGENTS.md` and the repo docs.
2. Work inside one bounded worktree when the task is non-trivial.
3. Keep changes within the current milestone.
4. Run verification.
5. Update `docs/PROGRESS.md` and `docs/NEXT_STEPS.md` when state changes.
6. Commit with a Conventional Commit message.
