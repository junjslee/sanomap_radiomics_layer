# Progress

## Last Updated
- 2026-03-17 America/Chicago

## Completed
- Query profiles were split and refined for strict radiomics, adjacent imaging, and body-composition retrieval.
- Microbe-side corpora were merged and deduplicated.
- PMC full-text acquisition was implemented and wired into downstream text stages.
- `src/extract_radiomics_text.py` works on the merged full-text-aware corpus.
- `src/text_ner_minerva.py` was optimized with long-sentence chunking, batching, and disease-first filtering.
- `src/build_relation_input.py` and `src/relation_extract_stage.py` carry `subject_node_type` and `subject_node`.
- The merged proof-of-concept relation pass completed locally with `--backend heuristic`.
- A reusable cross-agent operating scaffold is now installed for this repo:
  - `AGENTS.md`
  - `CLAUDE.md`
  - `.claude/settings.json`
  - `docs/REQUIREMENTS.md`
  - `docs/PLAN.md`
  - `docs/PROGRESS.md`
- The repo now has a dual-tool local runtime on top of global `agent-os`:
  - project `.claude/settings.json`
  - project `.codex/config.toml`
  - project Claude hook scripts in `.claude/hooks/`
  - shared docs remain the source of truth for both Claude and Codex

## In Progress
- Converting the repo from ad hoc markdown notes into a reusable dual-tool agent operating system.
- Preparing for the real GPU-backed or hosted merged relation run.
- Designing the cleanup pass for malformed subject and disease spans before edge promotion.

## Decisions
- The repo direction is locked to a hybrid imaging phenotype scope:
  - `RadiomicFeature`
  - `BodyCompositionFeature`
  - `MicrobialSignature`
- Text-derived phenotype-to-disease edges use `ASSOCIATED_WITH`.
- Verified figure-derived subject-to-feature edges use `CORRELATES_WITH`.
- Bridge matches remain audit-only and are not written to Neo4j as asserted relationships.
- Project memory is now split into:
  - vendor-neutral policy in `AGENTS.md`
  - Claude-native memory in `CLAUDE.md`
  - live operational state in `docs/*.md`
- Shared project truth lives in `AGENTS.md`, `docs/*.md`, and `pipeline_tracking.md`, not in tool-specific settings files.
- Claude and Codex both have repo-local runtimes for this project; Cursor remains an editor surface only.
- Local helper work and `agent-os` commands should run in Conda `base`.
- Standard worktree lanes are now:
  - `research/query-*`
  - `fix/entity-cleanup-*`
  - `ops/remote-run-*`
  - `docs/handoff-*`

## Validation
- Current merged corpus baseline:
  - `120` unique papers
- Current merged relation baseline:
  - `148` sentence-level predictions
  - `70` accepted sentence-level relations
  - `138` within-paper aggregated relations
  - `60` accepted aggregated relations
- Current accepted aggregated warning profile:
  - `14` subject nodes with `##` fragments
  - `20` generic subject phrases
  - `42` clause-like disease spans
- Verified the new global agent operating system locally on macOS:
  - Claude Code user memory and settings installed
  - custom Claude subagents installed
  - custom Claude slash commands installed
  - `agent-os-init` bootstrap script validated in a temporary repo
  - `agent-worktree` worktree script validated in a temporary repo
  - destructive bash hook blocked `git reset --hard` during smoke testing
- Verified that Codex can infer the project objective and handoff file from shared repo docs without repo-local Codex skills.
- Verified that trusted repo-local Codex config now loads from both the repo root and `src/`, switching Codex startup sandbox from `read-only` to `workspace-write`.
- Verified that `claude agents --setting-sources project` loads successfully, so the project-local Claude settings file is parseable even though this machine is not currently logged in for a full end-to-end Claude hook run.
- Tightened repo publication boundaries so supervisor-visible Git history keeps shared runtime files and research artifacts, while local-only state stays ignored.
- Updated the boundary again so `sample_papers/` stays local-only while shared markdown memory and repo runtime files remain commit-safe.

## Blockers
- No real GPU-backed merged relation run has been executed yet.
- Upstream-associated model assets remain unavailable.
- Entity cleanup is still the main quality blocker before edge assembly on the merged branch.
