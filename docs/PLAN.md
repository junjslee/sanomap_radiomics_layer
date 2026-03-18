# Plan

## Current Goal
- Produce graph-ready merged relation outputs for the radiomics-first imaging phenotype branch, then promote them safely to edge assembly.

## Active Gating Items
- Run true model-backed merged relation extraction outside `local_mac_base`.
- Confirm the shared cleanup helper still holds on the model-backed merged rerun.
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
7. Package the project explicitly for the professor-facing rubric:
   - publish a simple knowledge map
   - provide a small explorer over extracted relations
   - include at least one visible visualization or diagram

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
- Stage 3 is the main gating item; Stage 4 cleanup is now locally verified and needs confirmation on a model-backed rerun.
- Active implementation lane: `ops/remote-run-hf-hosted`
- Immediate sub-goal:
  - add a hosted relation backend that can call Hugging Face first through an OpenAI-compatible chat-completions API shape
  - keep the backend generic enough that Ollama or other OpenAI-compatible providers can be used later without another relation-stage redesign
  - verify the backend locally with mocked HTTP tests before any real hosted smoke run
- Local CPU-only proof-of-concept plumbing exists; graph-ready merged quality still depends on model-backed extraction.
- Shared span cleanup is now implemented locally in:
  - `src/span_cleanup.py`
  - `src/text_ner_minerva.py`
  - `src/build_relation_input.py`
  - `src/relation_extract_stage.py`
- Current next step:
  - keep the professor-facing knowledge map, explorer, proposal source, and README wired into the repo surface
  - extend `src/model_backends.py` and `src/relation_extract_stage.py` with a hosted chat backend
  - add local unit coverage for response parsing, URL construction, and backend selection
  - document the Hugging Face-first provider assumptions in `docs/RUN_CONTEXT.md`
  - rerun the merged branch on GPU or hosted inference with the shared cleanup helper already in place
  - confirm accepted aggregated outputs stay free of the old subject-tail and disease-prefix fragment patterns
  - use the current repo as the explicit topic + knowledge map + explorer + visualization deliverable for professor review while model-backed validation continues
  - do not promote the current local rebuild to edge assembly until the model-backed rerun is reviewed
- Local validation status:
  - `src/verify_heatmap.py` legend detection has been repaired for synthetic legend selection
  - the local Conda `base` pytest suite is green again

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
- The local cleanup audit is now clean for the previously observed malformed subject and disease span patterns, but that result still needs confirmation on a model-backed rerun.

## Verification Plan
- Compare rebuilt merged text-stage artifact counts against the current local baseline.
- Audit accepted aggregated relations for:
  - fewer `##` fragments
  - fewer generic subject phrases
  - fewer clause-like disease strings
- Validate edge outputs and confirm bridge hypotheses were not ingested as direct graph edges.
