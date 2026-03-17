# Plan

## Current Goal
- Produce graph-ready merged relation outputs for the radiomics-first imaging phenotype branch, then promote them safely to edge assembly.

## Active Gating Items
- Run true model-backed merged relation extraction outside `local_mac_base`.
- Clean malformed subject and disease spans before graph promotion.
- Promote to edge assembly only after review confirms graph semantics and span quality.

## Stages
1. Keep repo memory current:
   - `AGENTS.md`
   - `CLAUDE.md`
   - `docs/REQUIREMENTS.md`
   - `docs/PLAN.md`
   - `docs/PROGRESS.md`
   - `docs/NEXT_STEPS.md`
2. Recreate the merged text path on the full-text-aware corpus:
   - `src/extract_radiomics_text.py`
   - `src/text_ner_minerva.py`
   - `src/build_relation_input.py`
3. Run true model-backed relation extraction on GPU or hosted inference:
   - avoid `--backend heuristic` for the real merged pass
4. Clean subject and disease spans before graph promotion:
   - reject `##` fragments
   - reject generic microbial placeholders
   - reject clause-like disease spans
5. Re-run relation extraction and audit quality deltas.
6. Promote to `src/assemble_edges.py` and validate graph export artifacts.

## Operational Lanes
- `research/query-*`:
  query exploration, profile audits, and query-selection loops.
- `fix/entity-cleanup-*`:
  cleanup rules and relation-quality fixes.
- `ops/remote-run-*`:
  remote or hosted execution setup, runbooks, and result capture.
- `docs/handoff-*`:
  memory upkeep, tracking, and handoff consolidation.

## Active Stage
- Stage 3 and Stage 4 are the real gating items.
- Local CPU-only proof-of-concept plumbing exists; graph-ready merged quality still depends on model-backed extraction plus cleanup.

## Bounded Automation
- Allowed loop classes:
  - query exploration and selection
  - training or model-selection experiments
- Every loop must declare:
  - objective
  - candidate set
  - max iterations
  - evaluation rubric
  - artifact outputs
  - stop condition
  - human review checkpoint

## Risks And Unknowns
- GPU-backed execution environment or hosted relation path is still pending.
- Upstream-associated weights/checkpoints are still unavailable in this workspace.
- Accepted merged relations still contain malformed subject and disease spans inherited from NER.

## Verification Plan
- Compare rebuilt merged text-stage artifact counts against the current local baseline.
- Audit accepted aggregated relations for:
  - fewer `##` fragments
  - fewer generic subject phrases
  - fewer clause-like disease strings
- Validate edge outputs and confirm bridge hypotheses were not ingested as direct graph edges.
