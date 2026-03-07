# Next Steps

This file is the operational handoff for the next agent run.

It is not auto-generated. The active agent is expected to update it whenever the main priority, blocker, execution environment, or next milestone changes.

Read this together with:
- `docs/AGENT_PROTOCOLS.md`
- `docs/RUN_CONTEXT.md`
- `docs/RADIOMICS_LAYER_SPECS.md`
- `pipeline_tracking.md`
- `ReadME.md`

## Primary Goal
Finish the radiomics-first imaging phenotype extension to a level that is methodologically close to upstream MINERVA, while keeping the current graph semantics and direct-evidence policy.

The next major milestone is:
- produce graph-ready merged relation outputs on a GPU-backed run
- remove obvious entity-span junk before edge assembly
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

## What Is Not Yet Upstream-Parity
### Model-backed merged relation extraction
- The merged relation pass was only executed with `--backend heuristic` in the local CPU-only environment.
- That run is valid for proof-of-concept pipeline flow only.
- It is not the final model-backed relation extraction result.

### Entity quality
- Accepted merged relation outputs still contain malformed spans:
  - token-fragment subjects like `##fidobacteria`
  - generic subjects like `bacterial species`
  - clause-like disease spans rather than clean disease entities
- This is the main quality blocker before graph-ready edge assembly on the merged branch.

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

### Important distinction
- Local PoC plumbing is real and useful
- Model-backed relation quality is still pending proper GPU or hosted execution

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

## GPU Cluster Execution Plan
Use this order on the GPU cluster unless a concrete blocker appears.

### Phase 1: Recreate the merged text path
1. Clone the repo at the latest pushed commit.
2. Recreate or sync required corpora and artifacts if they are not copied over.
3. Prefer the merged full-text corpus as the text-stage input:
   - `artifacts/papers_microbe_merged_fulltext.jsonl`
4. Rerun:
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
Implement a cleanup pass before trusting merged relation outputs.

Minimum cleanup rules:
- reject subject nodes containing `##`
- reject overly generic subject phrases:
  - `bacterial`
  - `bacterial species`
  - `microbial`
  - `microbial density`
  - `bacterial presence`
  - similar generic placeholders
- reject disease strings that are clearly clause-like rather than entity-like
- reject disease strings that are mostly relation language instead of disease concepts
- prefer normalized disease spans when possible

This cleanup can happen in one of two places:
- directly after NER
- or immediately before relation aggregation/edge assembly

Preferred choice:
- clean earlier, before aggregation, so the downstream artifacts are cleaner throughout

### Phase 4: Rerun relation extraction after cleanup
1. Rerun `src/relation_extract_stage.py`
2. Re-audit accepted outputs
3. Confirm improvement against the last known warning profile:
   - fewer `##` fragments
   - fewer generic subject phrases
   - fewer clause-like disease spans

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
- update `ReadME.md`
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
