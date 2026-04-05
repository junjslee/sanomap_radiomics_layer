# Project Claude Memory

Project docs live in `docs/`. Read them on demand — do not auto-load everything.

Start each session by reading:
- `docs/NEXT_STEPS.md` — current priority and next actions
- `docs/PROGRESS.md` — current state and key decisions

## Critical Guardrails (always apply)
- Text phenotype-to-disease edges: `ASSOCIATED_WITH` only
- Verified figure edges: `CORRELATES_WITH` only
- Bridge hypotheses: audit-only — **never write as graph edges**
- Direct evidence only — no edges from shared-disease-context bridge matches
- Review required before merge for: relation logic, entity cleanup, edge assembly changes

Read on demand:
- `AGENTS.md` — full operating manual and bounded automation rules
- `docs/REQUIREMENTS.md` — what is being built and acceptance criteria
- `docs/PLAN.md` — staged execution plan
- `docs/RUN_CONTEXT.md` — runtime assumptions, model policy, API env vars
- `docs/RADIOMICS_LAYER_SPECS.md` — graph schema (node/edge types)
- `README.md` — project overview and professor rubric
- `pipeline_tracking.md` — long-form artifact tracking
