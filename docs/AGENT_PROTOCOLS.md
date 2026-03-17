# Agent Operating Procedures

This file defines the Sanomap repo-local execution rules for Claude and Codex.
Shared project truth lives in `AGENTS.md`, `docs/*.md`, and `pipeline_tracking.md`.

## Read Order
Read these before planning or implementation work:
- `AGENTS.md`
- `CLAUDE.md` for Claude sessions only
- `docs/REQUIREMENTS.md`
- `docs/PLAN.md`
- `docs/PROGRESS.md`
- `docs/RUN_CONTEXT.md`
- `docs/NEXT_STEPS.md`
- `docs/RADIOMICS_LAYER_SPECS.md`
- `pipeline_tracking.md`
- `ReadME.md`

## Standard Flow
1. Explore:
   read repo memory, inspect the affected code path, and confirm the active blocker.
2. Plan:
   keep `docs/PLAN.md` aligned with the current milestone before substantial implementation.
3. Implement:
   make the smallest change that advances the gated milestone.
4. Review:
   verify semantics, artifact expectations, and regressions before merge or handoff.
5. Handoff:
   update `docs/PROGRESS.md`, `docs/NEXT_STEPS.md`, and `pipeline_tracking.md` when state moved.

## Tool Roles
- Claude:
  use the global `planner`, `researcher`, `reviewer`, `test-runner`, and `docs-handoff` agents that are installed by `agent-os`.
- Codex:
  use built-in read-heavy exploration and bounded worker delegation, while relying on the same shared repo docs.
  Repo-local `.codex/config.toml` only loads in trusted paths; trust each new worktree path if Codex falls back to read-only defaults.
- Cursor:
  use as an editor and review surface only; do not treat it as a third runtime configuration target.

## Worktree Policy
- Use one bounded objective per worktree.
- Use one active owner per worktree.
- Preferred prefixes:
  - `research/query-*`
  - `fix/entity-cleanup-*`
  - `ops/remote-run-*`
  - `docs/handoff-*`
- Record the active branch or worktree lane in `docs/NEXT_STEPS.md` when handing work off.

## Logging And Tracking
- `agent_logs/action_log.md` is for substantive runs only:
  remote executions, cleanup passes, bounded loops, major audits, or branch handoffs.
- Do not log every shell command.
- The source of truth remains:
  - `docs/PROGRESS.md`
  - `docs/NEXT_STEPS.md`
  - `pipeline_tracking.md`

## Public Vs Local Files
- Treat this repository as the public project record for supervisor review.
- Commit shared runtime files that help another agent or engineer reproduce the workflow.
- Keep private or machine-specific state out of Git:
  `.claude/settings.local.json`, user-level auth, home-directory trust config, `.env*`, `secrets/`, and private keys.
- Keep `sample_papers/` local-only for now.
- Commit markdown files that define the project workflow or handoff:
  `AGENTS.md`, `CLAUDE.md`, and `docs/*.md`.

## Review Gate
- Review is required before merge for:
  - relation logic changes
  - entity cleanup logic
  - edge assembly changes
- Confirm that direct-evidence graph policy still holds before merge or export.

## Bounded Automation
- Allowed unattended or semi-attended loops:
  - query exploration and selection
  - training or model-selection experiments
- Every loop must record:
  - objective
  - candidate set
  - max iterations
  - evaluation rubric
  - artifact outputs
  - stop condition
  - human review checkpoint
- No unattended code-writing, auto-merge, or graph-promotion loops are allowed.

## Evidence Guardrails
- Direct evidence only:
  do not emit graph edges from within-paper bridge matches that only share a disease context.
- Preserve the locked semantics:
  - verified subject-to-feature figure edges use `CORRELATES_WITH`
  - text-derived phenotype-to-disease edges use `ASSOCIATED_WITH`
  - bridge hypotheses remain audit-only and never become asserted graph edges
- Deterministic checks still come first for the Vision Track; do not trust VLM outputs without geometric verification.
