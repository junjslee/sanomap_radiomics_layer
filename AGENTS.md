# Agent Operating Manual

## Purpose
This file is the vendor-neutral operating manual for agents working in this repository.

## Required Memory Files
- `CLAUDE.md`
- `docs/REQUIREMENTS.md`
- `docs/PLAN.md`
- `docs/PROGRESS.md`
- `docs/RUN_CONTEXT.md`
- `docs/NEXT_STEPS.md`
- `pipeline_tracking.md`

## Workflow
1. Read project memory before planning or code changes.
2. Clarify the active objective in `docs/REQUIREMENTS.md`.
3. Update `docs/PLAN.md` before substantial implementation.
4. Track completed work, decisions, and validation in `docs/PROGRESS.md`.
5. Keep `docs/NEXT_STEPS.md` current as the handoff for the next session.
6. Use git worktrees for non-trivial parallel work, with one bounded objective per worktree.
7. Treat `AGENTS.md`, `docs/*.md`, and `pipeline_tracking.md` as the source of truth over tool-specific settings.
8. Use Conventional Commits for final commit messages.

## Guardrails
- Prefer the smallest useful verification step first.
- Do not duplicate large prompt blocks in chat when they belong in project memory.
- Record environment limits, APIs, and rate limits in `docs/RUN_CONTEXT.md`.
- Keep `CLAUDE.md` short and use it as an index into the live docs.
- Keep tool-specific runtime files lightweight; they should shape behavior, not replace project memory.
- Keep the GitHub repo publishable for supervisor review:
  commit project docs, reusable repo runtime files, and research artifacts meant for shared review.
- Keep machine-specific, credential-bearing, or operator-private state local:
  `.claude/settings.local.json`, user auth, trust settings, `.env*`, `secrets/`, and private keys do not belong in the repo.
- Commit these agent/runtime files:
  `AGENTS.md`, `CLAUDE.md`, `.claude/settings.json`, `.claude/hooks/`, `.codex/config.toml`, and the shared `docs/*.md` memory files.
- Keep these local only:
  `sample_papers/`, `.claude/settings.local.json`, any future `.codex/config.local.toml`, and any home-directory tool config.
