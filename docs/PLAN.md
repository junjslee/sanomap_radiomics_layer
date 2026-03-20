# Plan

## Current Goal
- Produce a concrete phenotype-axis PoC for the radiomics-first imaging phenotype branch, then promote only the clean graph-eligible edges safely to edge assembly.

## Active Gating Items
- Tighten phenotype-edge assembly cleanup so text-derived phenotype-to-disease edges and axis candidates are inspectable.
- Re-audit the local assembled phenotype-axis outputs for graph-readiness and audit-only boundaries.
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
- Stage 6 is the active implementation stage for the actual phenotype-axis extension PoC.
- Active implementation lane: `ops/remote-run-hf-hosted`
- Immediate sub-goal:
  - keep the hosted relation backend stable
  - keep the explicit phenotype-axis audit artifact in place
  - clean phenotype-to-disease assembly on the text side
  - review whether the current assembled disease targets are graph-eligible or still too clause-like
- Local CPU-only proof-of-concept plumbing exists; the inherited microbe-disease lane is sufficiently validated for now, and the extension axis is now explicit in local assembled artifacts.
- Shared span cleanup is now implemented locally in:
  - `src/span_cleanup.py`
  - `src/text_ner_minerva.py`
  - `src/build_relation_input.py`
  - `src/relation_extract_stage.py`
- Current next step:
  - keep the professor-facing knowledge map, explorer, proposal source, and README wired into the repo surface
  - keep the hosted backend and local tests in place
  - treat the malformed-prefix cleanup issue on the inherited microbe-disease lane as resolved for now
  - keep the live retrieval benchmark decisions in place:
    - `microbe_radiomics_strict` stays unchanged as the precision lane
    - `microbe_bodycomp` stays unchanged as the default high-yield body-comp lane
    - `microbe_bodycomp_clinical_recall` is optional recall-only, not default
  - keep the explicit phenotype-axis outputs from the local assembly run:
    - `17` text-derived phenotype-to-disease edges after assembly-only semantic normalization
    - `61` audit-only direct text subject-to-phenotype candidates
    - `143` audit-only bridge hypotheses
  - preserve the current assembly-only disease-side filter boundary: clause fragments and phenotype leakage stay out of graph edges, while qualified inflammation outcomes remain an explicit policy question
- Local validation status:
  - `src/verify_heatmap.py` legend detection has been repaired for synthetic legend selection
  - the local Conda `base` pytest suite is green again (`98 passed`)

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
- Upstream-associated weights/checkpoints are still unavailable in this workspace.
- The hosted relation path is working, but model-backed acceptance is stricter than the heuristic audit and can surface new malformed accepted spans.
- The local cleanup audit is now clean for the previously observed conjunction-led, preposition-led, and verb-led disease fragments on the Gemini rerun.
- The remaining quality risk is semantic breadth on assembled text-derived disease targets such as `inflammation`, plus residual noise in some direct text subject-to-phenotype candidates.

## Verification Plan
- Compare rebuilt merged text-stage artifact counts against the current local baseline.
- Audit accepted aggregated relations for:
  - fewer `##` fragments
  - fewer generic subject phrases
  - fewer clause-like disease strings
  - fewer accepted leading `and ...`, `in ...`, and `reduces ...` disease fragments
  - explicit review of whether broad concepts such as `inflammation` should remain graph-eligible
- Audit phenotype-axis outputs for:
  - graph-eligible phenotype-to-disease edges
  - audit-only bridge hypotheses
  - audit-only direct text subject-to-phenotype candidates
  - cleaned subject and disease spans in assembled outputs
  - residual clause-like disease examples in assembled text edges
- Validate edge outputs and confirm bridge hypotheses were not ingested as direct graph edges.
