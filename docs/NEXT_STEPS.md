# Next Steps

This file is the operational handoff for the next agent run.

It is not auto-generated. The active agent is expected to update it whenever the main priority, blocker, execution environment, or next milestone changes.

Read this together with:
- `AGENTS.md`
- `docs/AGENT_SYSTEM.md`
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
  - `docs/AGENT_SYSTEM.md`
  - `docs/*.md`
  - `pipeline_tracking.md`
- Repo-local Claude runtime:
  - `.claude/settings.json`
  - `.claude/hooks/`
- Repo-local Codex runtime:
  - `.codex/config.toml`
  - requires the repo or worktree path to be trusted by Codex before project config is applied
- Cursor is an editor surface only.
- Optional Claude-only plugins such as `claude-mem` are not canonical project memory and are not required for normal repo operation.

## Primary Goal
Finish the radiomics-first imaging phenotype extension to a level that is methodologically close to upstream MINERVA, while keeping the current graph semantics and direct-evidence policy.

The next major milestone is:
- tighten text-derived phenotype-to-disease filtering so assembled edges are semantically cleaner
- confirm which assembled outputs are graph-eligible versus audit-only
- expand BodyLocation and ImagingModality coverage through improved extractor vocabulary
- run expanded 640-paper corpus through improved extraction pipeline (no API calls needed for text stages)
- validate Vision Track on more gradient-colormap heatmap figures specifically (dot-plot figures will correctly fail)
- then continue to final edge assembly and downstream graph export

## Current Baseline
- Last pushed baseline before this handoff: commit `b8b4981`
- Active implementation lane: `ops/remote-run-hf-hosted`
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
- New optional recall profile exists:
  - `microbe_bodycomp_clinical_recall`
  - use it only when a larger human-clinical body-composition recall audit is worth the added noise
- Recall artifacts now exist separately from the default corpus:
  - `artifacts/papers_microbe_bodycomp_clinical_recall.jsonl`
  - `artifacts/text_mentions_microbe_bodycomp_clinical_recall.jsonl`
- Separate merged-harvest audit artifacts also exist:
  - `artifacts/papers_microbe_harvest_baseline_dedup.jsonl`
  - `artifacts/papers_microbe_harvest_expanded_dedup.jsonl`
  - `artifacts/text_mentions_microbe_harvest_baseline.jsonl`
  - `artifacts/text_mentions_microbe_harvest_expanded.jsonl`
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
- `src/model_backends.py` now supports:
  - `heuristic`
  - `hf_textgen`
  - `openai_compatible`
- `src/relation_extract_stage.py` now accepts hosted backend inputs through:
  - `--api-base-url`
  - `--api-key`
- `src/assemble_edges.py` supports the hybrid graph schema and bridge hypothesis policy
- `src/assemble_edges.py` now also emits audit-only direct text subject-to-phenotype candidates
- Shared span cleanup is now implemented in `src/span_cleanup.py` and wired into:
  - `src/text_ner_minerva.py`
  - `src/build_relation_input.py`
  - `src/relation_extract_stage.py`
- `src/verify_heatmap.py` legend detection has been repaired and the local Conda `base` pytest suite is currently green.
- Vision Track is validated end-to-end:
  - `src/index_figures.py` → `src/propose_vision_qwen.py` → `src/verify_heatmap.py`
  - first real figure extraction: Gemini 2.5 Flash-Lite extracted r=0.95 for Prevotella_nigrescens ↔ GLCM_Correlation on CT from PMC10605408
  - deterministic verification accepted with distance_metric=0.05 and support_fraction=1.0
- Imaging backbone nodes are implemented:
  - `BodyLocation` and `ImagingModality` as first-class graph nodes
  - `collect_imaging_backbone_nodes()` and `build_imaging_backbone_neo4j_rows()` in `src/assemble_edges.py`
  - current corpus yields: 5 body locations (brain, kidney, liver, heart, colon), 3 imaging modalities (CT/CT, PET/PT, MRI/MR)
  - 25 MEASURED_AT + ACQUIRED_VIA Neo4j rows from 1,129 text mentions
- Professor-facing deliverables now exist in the repo:
  - `docs/knowledge_map.md` (updated with BodyLocation and ImagingModality)
  - `docs/explorer/index.html`
  - `docs/explorer/README.md`
  - `README.md`
  - `docs/proposal/proposal_sanomap_minerva_extension.tex`

## What Is Not Yet Upstream-Parity

### MINERVA pipeline alignment (verified 2026-03-19)
The pipeline structure is directly adapted from MINERVA. Verified against `references/minerva_mgh_lmic.pdf`:
- ✓ Sentence-level processing with joint entity gating
- ✓ Self-consistency with complete-consistency requirement (not majority)
- ✓ Within-paper aggregation with majority voting
- ✓ 3-label classification (Positive / Negative / Unrelated)
- ✓ PMC full-text preferred over abstract-only

Known gaps vs upstream:
- Microbe NER: `d4data/biomedical-ner-all` (general) vs MINERVA's custom BNER2.0-finetuned DistilBERT (F1=0.914). Ours is a substitute.
- Disease NER: `en_ner_bc5cdr_md` (spaCy BC5CDR) vs MINERVA's SciBERT. Substitute.
- UMLS normalization: MINERVA assigns a CUI to every entity via ScispaCy; we skip this (`--umls-linker off`). Missing — means alias deduplication is not done.
- Relation model: Gemini 2.5 Flash-Lite (zero-shot prompt) vs BioMistral-AUG-7b (fine-tuned on 1,100 labeled sentences + augmented training data).
- We only promote Positive relations to graph edges; MINERVA keeps both Positive and Negative.

### Model-backed merged relation extraction
- The merged relation pass has now been executed locally with a real hosted model-backed backend:
  - `openai_compatible`
  - `gemini-2.5-flash-lite`
- That run was sufficient to validate provider plumbing and expose model-backed cleanup failures.
- It is still not the final graph-ready relation extraction result.

### Entity quality
- The code-level cleanup pass has now been rebuilt locally against the merged corpus twice.
- The second 2026-03-17 local heuristic audit removed the previously observed residual fragment patterns from accepted aggregated outputs:
  - token-fragment subjects like `##fidobacteria`: removed
  - generic subjects like `bacterial species`: removed
  - subject tail fragments like `fusobacteria were`: removed
  - disease clause-prefix fragments like `in adults with chronic hiv infection`: removed
  - disease relation-language and clause-like spans flagged by the shared cleanup helper: removed
- Local accepted aggregated count after the narrower cleanup rerun: `20`
- A real model-backed merged relation run has now been executed with Gemini direct on the current 26-row local relation-input set.
- That run reopened the cleanup milestone because accepted aggregated outputs still included clause-prefix disease spans such as:
  - `and metabolic syndrome`
  - `in cirrhosis`
  - `reduces inflammation`
- Current accepted aggregated count on the Gemini full run: `14`
- A refinement pass has now been implemented locally in `src/span_cleanup.py`:
  - disease spans strip leading conjunction and preposition fragments such as `and ...` and `in ...`
  - verb-led and generic relation-language disease fragments such as `reduces inflammation` and `pro-inflammatory or disease` are now rejected
  - subject tails such as `phylum`, `class`, `families`, and `bearing` are now stripped
- The Gemini rerun has now confirmed those malformed-prefix and subject-tail patterns are gone from accepted aggregated rows too.
- Current accepted aggregated count on the cleaned Gemini rerun: `8`
- The remaining review question is narrower:
  - decide whether qualified outcome concepts like `systemic inflammation` and `low-grade chronic inflammation` should remain graph-eligible or should move to an audit-only lane
- The phenotype-axis PoC is now explicit in local assembled artifacts:
  - `17` text-derived phenotype-to-disease edges after assembly-only semantic normalization
  - `61` audit-only direct text subject-to-phenotype candidates
  - `143` audit-only bridge hypotheses
- The remaining review question is now centered on disease-node policy, not on whether the extension axis exists.

### Upstream-style completeness
- Upstream-equivalent hosted or GPU-backed LLM classification has not yet been executed on the merged branch.
- Final evaluation and benchmark-quality precision auditing are still missing.
- Phenotype normalization is still lighter than upstream disease/microbe normalization maturity.

## Blockers
- Strict-radiomics and adjacent-imaging yield remain weak even with the expanded corpus; the expansion is body-composition-heavy.
- Disease string quality in `extract_radiomics_text.py` is now improved (stopword guards in `_detect_disease()`), but the expanded 640-paper corpus has not been re-run yet to quantify the improvement.
- Vision Track: 2 additional figures attempted (PMC10176953, PMC11924647), both correctly rejected. Need to identify papers with proper gradient-colormap heatmaps (not dot-plot style) for additional verified ImageRef nodes.
- NER: `d4data/biomedical-ner-all` remains the default; BENT was evaluated and rejected due to systematic FPs and tokenization issues.
- UMLS normalization: documented as a known gap vs upstream MINERVA; not yet implemented.

## Exact Next Actions
1. Re-run `src/extract_radiomics_text.py` on the expanded 640-paper corpus to measure improvement in disease string quality.
2. Search the PMC corpus specifically for papers with gradient-colormap heatmaps (not bar/dot charts) showing microbe-radiomics correlations.
3. If strict-radiomics yield needs improvement, improve adjacent-imaging / strict-radiomics extractor vocabulary rather than broadening retrieval queries.

## What We Are Waiting On
### Infrastructure
- GPU-backed execution environment is still useful for larger reruns, but it is no longer required to test real model-backed relation extraction.
- The hosted relation code path now exists and real provider-backed smoke/pilot runs have already completed.
- Current Hugging Face router status:
  - `deepseek-ai/DeepSeek-V3-0324` completed both a 3-row smoke run and a 10-row pilot
  - auto-routed `meta-llama/Llama-3.1-8B-Instruct` failed at Cerebras Cloudflare in this environment
  - auto-routed `Qwen/Qwen2.5-7B-Instruct` failed at Together Cloudflare in this environment
  - explicit `meta-llama/Llama-3.1-8B-Instruct:novita` then failed with HF `402` because included credits were exhausted
- Current Gemini direct status:
  - `gemini-2.5-flash-lite` completed a 10-row pilot successfully
  - `gemini-2.5-flash-lite` completed the full current local 26-row relation run successfully
- Current operator approval rule:
  - before any paid hosted-model run, estimate the cost in chat and ask:
    - `acknowledge the cost and proceed? [y/n]`
- The current infrastructure decision is therefore already made for the next pass:
  - use Gemini direct as the low-cost model-backed baseline while cleanup is being tightened
  - return to HF router or GPU only if we need broader model comparisons later

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
- Model-backed relation execution is now real on the current local relation set
- Model-backed relation quality is still pending cleanup hardening and rerun audit
- The phenotype axis is now explicit in assembled local artifacts, but not every assembled text-derived disease target is graph-ready yet
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
   - `gemini-2.5-flash-lite` as the current low-cost baseline
   - `BioMistral/BioMistral-7B` only if a practical hosted or GPU path becomes available later
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
- this now needs to be extended to catch accepted model-backed disease prefixes like `and ...`, `in ...`, and verb-led fragments like `reduces ...`

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

### Hosted smoke test via Hugging Face router
Use a tiny subset first and keep provider credentials local.
```bash
RELATION_API_BASE_URL="https://router.huggingface.co/v1" \
RELATION_API_KEY="$HF_TOKEN" \
python3 src/relation_extract_stage.py \
  --input artifacts/relation_input_microbe_merged.jsonl \
  --output-predictions artifacts/relation_predictions_microbe_merged.hosted_smoke.jsonl \
  --output-aggregated artifacts/relation_aggregated_microbe_merged.hosted_smoke.jsonl \
  --output-strengths artifacts/relation_strengths_microbe_merged.hosted_smoke.jsonl \
  --backend openai_compatible \
  --model-id deepseek-ai/DeepSeek-V3-0324 \
  --num-samples 1 \
  --allow-majority-consistency \
  --validate-schema
```

### Provider override note
If HF auto-routing selects a blocked provider, append the provider suffix directly to the model id.
Example:
```bash
--model-id meta-llama/Llama-3.1-8B-Instruct:novita
```

### Gemini direct note
Gemini now has a working path through the same `openai_compatible` backend.
Recommended local env:
```bash
GEMINI_API_KEY="your_gemini_key"
```
Optional explicit override:
```bash
GEMINI_API_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai"
```
For `gemini-*` model ids, the relation stage now defaults to the official Google OpenAI-compatible base URL automatically.

### Current next cleanup target
Before edge promotion, decide whether to keep or further restrict broad or clause-like text-derived disease targets such as:
- `inflammation`
- `systemic inflammation`
- `gut microbiota in cirrhosis`
- `as a measure of obesity`
- `sarcopenia is a disease`
The malformed-prefix and noisy subject-tail cases from the first Gemini run are now fixed, and the extension axis is now explicit in a local audit artifact.

### Edge assembly after quality cleanup
```bash
python3 src/assemble_edges.py \
  --relation-aggregated artifacts/relation_aggregated_microbe_merged.jsonl \
  --validate-schema
```

## Current Local Validation Snapshot
- Conda `base` has `pytest` installed for this repo.
- Current full-suite result:
  - `conda run -n base python -m pytest -q`
  - `156 passed` (as of 2026-03-28)

### Expanded corpus metrics (2026-03-19)
- Papers: `640` unique (baseline `120` + recall `520`)
- PMC full text: `400` recall papers downloaded, `74` baseline papers from prior run
- Phenotype mentions: `5,721`
- Entity sentences: `119`
- Raw NER rows: `143`
- Relation input rows (after radiomics-context gating): `67`
- NER backend: `d4data/biomedical-ner-all` on MPS (`microbe_model_available = true`)

### Gemini v1 on expanded corpus (2026-03-19)
- Input: `67` rows
- Accepted aggregated: `31`
- Full consistency rate: `0.8955`
- Significant span leakage in accepted → triggered Option C cleanup

### Gemini v2 on cleaned expanded corpus (2026-03-19)
- Pre-filter: `16` of `67` rows rejected (`12 generic_microbe_term`, `4 disease_relation_language`)
- Input to Gemini: `51` rows
- Accepted aggregated: `22`
- Post-assembly filter: `13` of `22` rejected → `9` clean graph-ready pairs

### Clean graph-ready microbe-disease pairs (2026-03-19)
1. `proteobacteria` → `cirrhosis`
2. `catenibacterium` → `cardiovascular disease`
3. `peptostreptococcus stomatis` → `cirrhosis`
4. `ruminococcus` → `cirrhosis`
5. `bifidobacterium bifidum` → `obesity`
6. `bifidobacterium lactis` → `obesity`
7. `catenibacterium` → `body cell mass deficiency in cirrhosis` *(pending policy decision)*
8. `dysosmobacter` → `obesity`
9. `lactobacillus-containing probiotic` → `systemic inflammation` *(pending policy decision)*

### Phenotype-axis assembly v2 (2026-03-19)
- Text edges (phenotype-to-disease, from `extract_radiomics_text.py`): `213`
- Axis candidates: `233`
- Bridge hypotheses: `232`
- Note: text edges are from phenotype co-mention extraction (separate from Gemini microbe-disease pipeline) — improving their disease string quality requires changes to `extract_radiomics_text.py` or its assembly filter, not `span_cleanup.py`

- The immediate next work item is not another span cleanup pass.
- It is: (1) explicit policy decision on the two borderline disease targets; (2) a false-negative audit; (3) phenotype extraction disease quality as a separate problem.

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
- model-backed accepted outputs no longer keep obvious clause prefixes such as `and ...` or `in ...`, or verb-led fragments such as `reduces ...`
- any remaining broad concepts such as `inflammation` have been explicitly accepted as in-scope or filtered out by a documented rule
- the phenotype axis remains explicit in local artifacts via:
  - graph-eligible phenotype-to-disease edges
  - audit-only direct text subject-to-phenotype candidates
  - audit-only bridge hypotheses
- merged outputs are good enough to feed `src/assemble_edges.py` without obvious garbage propagation

## Short Version
The pipeline plumbing is in place.

The next real job is:
1. run the merged relation stage with a real model backend on GPU
2. clean bad entity spans
3. rerun relation aggregation
4. then promote to edge assembly
