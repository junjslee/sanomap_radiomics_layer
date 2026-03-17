# Next Steps

This file is the operational handoff for the next agent run.

It is not auto-generated. The active agent is expected to update it whenever the main priority, blocker, execution environment, or next milestone changes.

Read this together with:
- `AGENTS.md`
- `CLAUDE.md`
- `docs/AGENT_PROTOCOLS.md`
- `docs/REQUIREMENTS.md`
- `docs/PLAN.md`
- `docs/PROGRESS.md`
- `docs/RUN_CONTEXT.md`
- `docs/RADIOMICS_LAYER_SPECS.md`
- `pipeline_tracking.md`
- `README.md`

## Repo Runtime Status
- Shared project truth lives in:
  - `AGENTS.md`
  - `docs/*.md`
  - `pipeline_tracking.md`
- Repo-local Claude runtime:
  - `.claude/settings.json`
  - `.claude/hooks/`
- Repo-local Codex runtime:
  - `.codex/config.toml`
  - requires the repo or worktree path to be trusted by Codex before project config is applied
- Cursor is an editor surface only.

## Primary Goal
Finish the radiomics-first imaging phenotype extension to a level that is methodologically close to upstream MINERVA, while keeping the current graph semantics and direct-evidence policy.

The next major milestone is:
- produce graph-ready merged relation outputs on a GPU-backed run
- rebuild merged text and relation artifacts with the shared cleanup helper
- confirm the cleanup materially removes obvious entity-span junk before edge assembly
- then continue to final edge assembly and downstream graph export

## Current Baseline
- Last pushed baseline before this handoff: commit `a8e4341`
- Current repo direction is locked:
  - hybrid imaging phenotype scope
  - strict `RadiomicFeature` core
  - `BodyCompositionFeature` support
  - `MicrobialSignature` support
- Current relation semantics are locked:
  - feature-to-disease text edges use `ASSOCIATED_WITH`
  - verified figure-derived subject-to-feature edges use `CORRELATES_WITH`
  - bridge matches are audit-only and never direct graph edges

## What Is Already Working
### Retrieval and corpus preparation
- Query profiles are split and refined in `src/harvest_pubmed.py`
- Microbe-side merged corpus exists and is deduplicated
- PMC full-text acquisition is implemented in `src/download_pmc_fulltext.py`
- Full-text-aware merged corpus exists

### Text extraction
- `src/extract_radiomics_text.py` works on the merged corpus
- `src/text_ner_minerva.py` is operational on the merged full-text corpus
- NER bottleneck was reduced with:
  - long-sentence chunking
  - batched inference
  - disease-first microbe extraction

### Relation pipeline plumbing
- `src/build_relation_input.py` exists and threads `subject_node_type` and `subject_node`
- `src/relation_extract_stage.py` exists and produces:
  - predictions
  - within-paper aggregation
  - strength scores
- `src/assemble_edges.py` supports the hybrid graph schema and bridge hypothesis policy
- Shared span cleanup is now implemented in `src/span_cleanup.py` and wired into:
  - `src/text_ner_minerva.py`
  - `src/build_relation_input.py`
  - `src/relation_extract_stage.py`
- `src/verify_heatmap.py` legend detection has been repaired and the local Conda `base` pytest suite is currently green.
- Professor-facing deliverables now exist in the repo:
  - `docs/knowledge_map.md`
  - `docs/explorer/index.html`
  - `docs/explorer/README.md`
  - `README.md`
  - `docs/proposal/proposal_sanomap_minerva_extension.tex`

## What Is Not Yet Upstream-Parity
### Model-backed merged relation extraction
- The merged relation pass was only executed with `--backend heuristic` in the local CPU-only environment.
- That run is valid for proof-of-concept pipeline flow only.
- It is not the final model-backed relation extraction result.

### Entity quality
- The code-level cleanup pass has now been rebuilt locally against the merged corpus twice.
- The second 2026-03-17 local audit removed the previously observed residual fragment patterns from accepted aggregated outputs:
  - token-fragment subjects like `##fidobacteria`: removed
  - generic subjects like `bacterial species`: removed
  - subject tail fragments like `fusobacteria were`: removed
  - disease clause-prefix fragments like `in adults with chronic hiv infection`: removed
  - disease relation-language and clause-like spans flagged by the shared cleanup helper: removed
- Local accepted aggregated count after the narrower cleanup rerun: `20`
- This means local span cleanup looks acceptable for the audited heuristic run, but it still needs confirmation on the real model-backed merged run.

### Upstream-style completeness
- Upstream-equivalent hosted or GPU-backed LLM classification has not yet been executed on the merged branch.
- Final evaluation and benchmark-quality precision auditing are still missing.
- Phenotype normalization is still lighter than upstream disease/microbe normalization maturity.

## What We Are Waiting On
### Infrastructure
- GPU-backed execution environment for real model-backed relation extraction
- or a hosted inference path for the relation classifier

### Model assets
- Upstream-associated checkpoints/weights not currently present in this workspace
- Until those are available, this repo uses substitute defaults
- Professor review is now the most likely coordination path for any upstream or private checkpoint handoff, so keep the repo notes explicit about expected models, integration points, and rerun steps.
- If checkpoint access is granted later, record the model ids and execution instructions in the repo, but keep any restricted weights outside Git history.
- BNER provenance status is now partially verified:
  - `references/minerva_mgh_lmic.pdf` says MINERVA used `BNER2.0` from the original authors' public GitHub splits
  - `https://github.com/lixusheng1/bacterial_NER` is the strongest public candidate and its checked-in `test_set.iob` matches MINERVA's reported `2,043` test-set bacterial entities
  - but the checked-in public splits do not match MINERVA's reported full-corpus totals, so do not claim exact `BNER2.0` release parity yet
  - next verification step is to inspect ref `[30]` or its archival materials directly, or confirm via professor/upstream contact

### Important distinction
- Local PoC plumbing is real and useful
- Model-backed relation quality is still pending proper GPU or hosted execution
- The repo already has enough visible material for professor review of the assignment rubric.
- The remaining work is about stronger model-backed validation and graph-ready promotion, not about inventing the first visible deliverable.

## Local Environment Constraints
- Local development machine observed during the last run:
  - Apple M2
  - `8 GB` unified memory
  - `arm64`
  - `MPS` available
- Even though `MPS` exists, the current `BioMistral` relation path as wired is not a practical local default on this machine.
- Local relation runs should be treated as:
  - smoke tests
  - pipeline-flow verification
  - not final merged relation production
- The 2026-03-17 local rebuild also had no usable Hugging Face network path for `d4data/biomedical-ner-all`, so microbe extraction fell back to regex and recall dropped materially.

## Standard Worktree Lanes
- `research/query-*`:
  retrieval audits, query-selection loops, and corpus-composition checks
- `fix/entity-cleanup-*`:
  malformed subject and disease span cleanup before edge promotion
- `ops/remote-run-*`:
  remote or hosted execution setup and production-style merged runs
- `docs/handoff-*`:
  `PROGRESS`, `NEXT_STEPS`, and `pipeline_tracking.md` upkeep

## Allowed Automation
- Bounded loops are allowed only for:
  - query exploration and selection
  - training or model-selection experiments
- Every loop must define:
  - objective
  - candidate set
  - max iterations
  - evaluation rubric
  - artifact outputs
  - stop condition
  - human review checkpoint
- No unattended code-writing, auto-merge, or graph-promotion loops are allowed.

## GPU Cluster Execution Plan
Use this order on the GPU cluster unless a concrete blocker appears.

### Phase 1: Recreate the merged text path
1. Clone the repo at the latest pushed commit.
2. Recreate or sync required corpora and artifacts if they are not copied over.
3. Prefer the merged full-text corpus as the text-stage input:
   - `artifacts/papers_microbe_merged_fulltext.jsonl`
4. Rerun with the new shared cleanup helper already wired in:
   - `src/extract_radiomics_text.py`
   - `src/text_ner_minerva.py`
   - `src/build_relation_input.py`
5. Confirm that output counts are in the same rough range as the committed local baseline.

### Phase 2: Run true model-backed relation extraction
1. Do not use `--backend heuristic` for the real merged run unless explicitly doing a smoke test.
2. Run `src/relation_extract_stage.py` with a real text-generation backend.
3. Preferred target model policy for this phase:
   - `BioMistral/BioMistral-7B` if available and practical
4. Record:
   - exact backend
   - exact model id
   - device
   - temperatures
   - runtime
5. Save all output artifacts and update `pipeline_tracking.md`.

### Phase 3: Clean entity spans before graph promotion
Use the existing shared cleanup helper before trusting merged relation outputs.

Current implementation:
- `src/span_cleanup.py`
- called from `src/text_ner_minerva.py`
- called from `src/build_relation_input.py`
- called from `src/relation_extract_stage.py`

Current cleanup behavior:
- reject subject nodes containing `##`
- reject overly generic microbe phrases such as `bacterial`, `bacterial species`, `microbial`, and similar placeholders
- trim context tails from spans such as `obesity markers` or `liver cancer in this cohort`
- reject disease strings that still look clause-like after cleanup
- reject disease strings that are mostly relation language instead of disease concepts

### Phase 4: Rerun relation extraction after cleanup
1. Rerun `src/relation_extract_stage.py`
2. Re-audit accepted outputs
3. Confirm improvement against the last known warning profile:
  - fewer `##` fragments
  - fewer generic subject phrases
  - fewer clause-like disease spans
4. On the next model-backed rerun, confirm the local cleanup result still holds for:
   - subject trailing stopwords and verb fragments
   - disease strings with leading clause prefixes such as `in ...` or `of ...`

### Phase 5: Promote to edge assembly
Only after cleanup and model-backed relation extraction look acceptable:
1. Run `src/assemble_edges.py`
2. Inspect:
   - `artifacts/verified_edges.jsonl`
   - `artifacts/verified_edges.csv`
   - `artifacts/neo4j_relationships.csv`
   - `artifacts/bridge_hypotheses.jsonl`
3. Confirm that bridge hypotheses were not ingested as direct graph edges

## Immediate Recommended Commands
These are the next practical commands to run on GPU after environment setup.

### Rebuild merged text-stage artifacts
```bash
python3 src/extract_radiomics_text.py \
  --papers artifacts/papers_microbe_merged_fulltext.jsonl \
  --output artifacts/text_mentions_microbe_merged.jsonl \
  --mapping-log artifacts/text_mapping_log_microbe_merged.jsonl \
  --validate-schema

python3 src/text_ner_minerva.py \
  --papers artifacts/papers_microbe_merged_fulltext.jsonl \
  --entity-output artifacts/entity_sentences_microbe_merged.jsonl \
  --relation-output artifacts/relation_input_microbe_merged.jsonl \
  --disease-ner-mode bc5cdr \
  --microbe-ner-model-id d4data/biomedical-ner-all \
  --umls-linker off \
  --ner-batch-size 8 \
  --validate-schema
```

### Rebuild relation input if needed
```bash
python3 src/build_relation_input.py --validate-schema
```

### Real model-backed merged relation run
Adjust device/backend details to match the GPU environment.
```bash
python3 src/relation_extract_stage.py \
  --input artifacts/relation_input_microbe_merged.jsonl \
  --output-predictions artifacts/relation_predictions_microbe_merged.jsonl \
  --output-aggregated artifacts/relation_aggregated_microbe_merged.jsonl \
  --output-strengths artifacts/relation_strengths_microbe_merged.jsonl \
  --backend hf_textgen \
  --model-family biomistral_7b \
  --device cuda \
  --validate-schema
```

### Edge assembly after quality cleanup
```bash
python3 src/assemble_edges.py \
  --relation-aggregated artifacts/relation_aggregated_microbe_merged.jsonl \
  --validate-schema
```

## Current Local Validation Snapshot
- Conda `base` now has `pytest` installed for this repo.
- Current full-suite result:
  - `conda run -n base python -m pytest -q`
  - `71 passed`
- Current residual-cleanup rerun metrics:
  - entity sentences: `38`
  - raw NER relation rows: `60`
  - final relation input rows: `26`
  - accepted aggregated relations: `20`
- The next work item is no longer another local cleanup pass; it is confirmation on a model-backed GPU or hosted rerun.

## Current Baseline Metrics To Compare Against
These are useful as rough reference points, not absolute targets.

### Merged corpus
- `120` unique papers
- `74` with `full_text_path`

### Phenotype extraction
- `1,129` mentions
- `49/120` papers with at least one mention
- heavily body-composition dominated:
  - `body_composition`: `1,099`
  - `radiomic`: `30`

### Text NER
- `25,788` sentence chunks processed
- `2,032` sentence chunks evaluated by microbe NER
- `90` entity-sentence rows
- `148` relation-input rows

### Local heuristic relation pass
- `148` predictions
- `138` aggregated rows
- `60` accepted aggregated rows
- not graph-ready because of entity-span quality issues

## What To Preserve
Do not change these without a clear documented reason:
- hybrid imaging phenotype framing
- `ASSOCIATED_WITH` default for text-derived phenotype-to-disease edges
- `CORRELATES_WITH` for verified quantitative subject-to-feature evidence
- direct-evidence-only graph policy
- bridge hypotheses remain audit-only

## What Not To Do
- Do not present the heuristic relation run as upstream-equivalent relation extraction.
- Do not emit graph edges from shared-disease bridge matches.
- Do not collapse the query lanes back into one mixed query profile.
- Do not introduce a generic `radiomics` node.
- Do not broaden relation labels back to blanket `PREDICTS`.
- Do not treat the current merged relation outputs as final graph-ingestion artifacts until cleanup is complete.

## Documentation Requirements For The Next Agent
After each substantive pass:
- update `README.md`
- keep `docs/proposal/proposal_sanomap_minerva_extension.tex` as the editable proposal source of truth
- update `pipeline_tracking.md`
- update this file if the next operational priority changes
- state clearly:
  - what backend actually ran
  - what artifacts were regenerated
  - whether the output is proof-of-concept only or graph-ready

## Completion Criteria For The Next Major Milestone
The next milestone is complete when all of these are true:
- merged relation extraction has been run with a real model-backed backend on GPU or hosted inference
- accepted relation outputs no longer have obvious `##` token-fragment artifacts at meaningful rates
- generic subject phrases are heavily reduced or removed
- disease spans are cleaned enough to look like actual disease entities rather than long clauses
- merged outputs are good enough to feed `src/assemble_edges.py` without obvious garbage propagation

## Short Version
The pipeline plumbing is in place.

The next real job is:
1. run the merged relation stage with a real model backend on GPU
2. clean bad entity spans
3. rerun relation aggregation
4. then promote to edge assembly
