# SanoMap Radiomics Layer (Hybrid Imaging Phenotype Extension)

## What This Pipeline Does
This repository implements a MINERVA-style extraction pipeline that extends the graph with a radiomics-first imaging phenotype layer.

Operational handoff for the next agent run lives in `docs/NEXT_STEPS.md`.

Direct evidence edges emitted by the current pipeline are:
- `(Microbe)-[:CORRELATES_WITH]->(RadiomicFeature)`
- `(Microbe)-[:CORRELATES_WITH]->(BodyCompositionFeature)`
- `(MicrobialSignature)-[:CORRELATES_WITH]->(RadiomicFeature)`
- `(MicrobialSignature)-[:CORRELATES_WITH]->(BodyCompositionFeature)`
- `(RadiomicFeature)-[:ASSOCIATED_WITH]->(Disease)`
- `(BodyCompositionFeature)-[:ASSOCIATED_WITH]->(Disease)`

The repository keeps the original name for continuity, but the implemented scope is broader than strict radiomics alone.

## Why The Scope Is Hybrid
- Strict radiomics plus microbiome papers exist, but they are a narrow slice.
- The current local corpus and PubMed query behavior show stronger yield for imaging-derived body-composition phenotypes.
- The pipeline therefore keeps `RadiomicFeature` as a precise core while adding `BodyCompositionFeature` and `MicrobialSignature` handling in the first pass.
- The current merged microbe-side corpus is not mostly strict radiomics:
  - `microbe_radiomics_strict`: `8`
  - `microbe_imaging_adjacent`: `15`
  - `microbe_bodycomp`: `99`
  - merged unique papers: `120`

## Model Stack (Current Substitutes)
1. Relation extraction target when model-backed text generation is available: `BioMistral/BioMistral-7B`
2. Data augmentation: `mistralai/Mixtral-8x7B-v0.1`
3. Microbe NER substitute: `d4data/biomedical-ner-all`
4. Disease NER adapter base: `allenai/scibert_scivocab_uncased` with fallback to `en_ner_bc5cdr_md`
5. Vision proposal model: `Qwen/Qwen2.5-VL-7B-Instruct`
6. Deterministic verification gate: `src/verify_heatmap.py`

These are temporary substitute models for proof-of-concept execution. Some upstream MINERVA-associated weights or checkpoints are not yet available in this workspace, so the current priority is end-to-end pipeline completion before final model-parity reruns.

## Stage-by-Stage Data Flow
1. `src/harvest_pubmed.py`
- In: query parameters
- Out: `artifacts/papers.jsonl`
- Profiles:
  - `microbe_radiomics_strict`
  - `microbe_imaging_adjacent`
  - `microbe_imaging_phenotype`
  - `microbe_bodycomp`
  - `radiomics_disease_strict`
  - `bodycomp_disease`
  - deprecated compatibility aliases: `microbe_radiomics`, `radiomics_disease`

2. `src/merge_paper_corpora.py`
- In: multiple harvested `papers_*.jsonl` corpora
- Out: deduplicated merged `papers_microbe_merged_dedup.jsonl` plus provenance sidecar
- Current default microbe-side merge:
  - `microbe_radiomics_strict`
  - `microbe_imaging_adjacent`
  - `microbe_bodycomp`

3. `src/download_pmc_fulltext.py`
- In: harvested `papers.jsonl` with PMCID metadata
- Out: updated `papers_with_fulltext.jsonl`, `artifacts/full_text/html/*.html`, `artifacts/full_text/text/*.txt`
- Upstream-aligned behavior:
  - resolve open-access PMC articles via PMCID
  - download the PMC article HTML
  - extract article text and attach `full_text_path`
- Current status:
  - implemented and validated
  - wired into the phenotype extractor and text NER content-selection path

4. `src/text_ner_minerva.py`
- In: `artifacts/papers.jsonl`
- Out: `artifacts/entity_sentences.jsonl`, `artifacts/relation_input.jsonl`
- Current optimization status:
  - prefers PMC full text when available
  - chunks long sentences before inference
  - batches NER calls via `--ner-batch-size`
  - runs disease extraction first and only runs microbe NER on disease-positive sentences

5. `src/extract_radiomics_text.py`
- In: `artifacts/papers.jsonl`
- Out: `artifacts/text_mentions.jsonl`
- Emits phenotype-level metadata:
  - `feature_family`
  - `node_type`
  - `ontology_namespace`
  - `claim_hint`
  - `subject_node_type`
  - `subject_node`
- Now prefers PMC full text via `full_text_path` when available

6. `src/build_relation_input.py`
- In: `entity_sentences.jsonl`, `text_mentions.jsonl`, `papers.jsonl`
- Out: final `artifacts/relation_input.jsonl`
- Carries upstream-style normalized subject identity through the row:
  - `microbe` (legacy compatibility)
  - `subject_node_type`
  - `subject_node`

7. `src/relation_extract_stage.py`
- In: `artifacts/relation_input.jsonl`
- Out: `artifacts/relation_predictions.jsonl`, `artifacts/relation_aggregated.jsonl`, `artifacts/relation_strengths.jsonl`
- Preserves `subject_node_type` and `subject_node` through prediction and within-paper aggregation while keeping the current classifier prompt microbe-disease scoped for upstream compatibility
- Current merged-run note:
  - this workspace is CPU-only, so the merged proof-of-concept run was executed with `--backend heuristic`
  - use that output for structural pipeline validation, not as final upstream-parity relation quality

8. `src/index_figures.py`
- In: paper metadata and/or images
- Out: `artifacts/figures.jsonl`

9. `src/propose_vision_qwen.py`
- In: `artifacts/figures.jsonl`
- Out: `artifacts/vision_proposals.jsonl`

10. `src/verify_heatmap.py`
- In: `artifacts/vision_proposals.jsonl`
- Out: `artifacts/verification_results.jsonl`

11. `src/assemble_edges.py`
- In: `text_mentions`, `relation_aggregated`, `vision_proposals`, `verification_results`, `papers`
- Out:
  - `artifacts/verified_edges.jsonl`
  - `artifacts/verified_edges.csv`
  - `artifacts/neo4j_relationships.csv`
  - `artifacts/bridge_hypotheses.jsonl`

## Edge Semantics
- Text-derived phenotype-to-disease edges default to `ASSOCIATED_WITH`.
- Verified figure-derived subject-to-feature edges use `CORRELATES_WITH`.
- `PREDICTS` is not emitted by default in the current pass.
- Shared-disease bridge matches are audit-only hypotheses and are not written to Neo4j.

## Core Commands
```bash
# Strict radiomics + microbiome
python3 src/harvest_pubmed.py --query-profile microbe_radiomics_strict --retmax 0 --from-year 2010 --to-year 2026 --output artifacts/papers_microbe_radiomics_strict.jsonl

# Merge and deduplicate the three microbe-side corpora
python3 src/merge_paper_corpora.py --validate-schema

# Upstream-style PMC full-text acquisition for the merged microbe-side corpus
python3 src/download_pmc_fulltext.py --papers artifacts/papers_microbe_merged_dedup.jsonl --output artifacts/papers_microbe_merged_fulltext.jsonl --validate-schema

# Adjacent imaging phenotype + microbiome
python3 src/harvest_pubmed.py --query-profile microbe_imaging_adjacent --retmax 0 --from-year 2010 --to-year 2026 --output artifacts/papers_microbe_imaging_adjacent.jsonl

# Body-composition phenotype + microbiome
python3 src/harvest_pubmed.py --query-profile microbe_bodycomp --retmax 0 --from-year 2010 --to-year 2026 --output artifacts/papers_microbe_bodycomp.jsonl

# Broader mixed imaging phenotype + microbiome
python3 src/harvest_pubmed.py --query-profile microbe_imaging_phenotype --retmax 0 --from-year 2010 --to-year 2026 --output artifacts/papers_microbe_imaging_phenotype.jsonl

# Strict radiomics + disease
python3 src/harvest_pubmed.py --query-profile radiomics_disease_strict --retmax 0 --from-year 2010 --to-year 2026 --output artifacts/papers_radiomics_disease_strict.jsonl

# Body-composition phenotype + disease
python3 src/harvest_pubmed.py --query-profile bodycomp_disease --retmax 0 --from-year 2010 --to-year 2026 --output artifacts/papers_bodycomp_disease.jsonl

# Optional broader body-composition association corpus
python3 src/harvest_pubmed.py --query-profile bodycomp_disease_association --retmax 0 --from-year 2010 --to-year 2026 --output artifacts/papers_bodycomp_disease_association.jsonl

# Phenotype text extraction on merged full-text-aware microbe corpus
python3 src/extract_radiomics_text.py --papers artifacts/papers_microbe_merged_fulltext.jsonl --output artifacts/text_mentions_microbe_merged.jsonl --mapping-log artifacts/text_mapping_log_microbe_merged.jsonl --validate-schema

# Edge assembly
python3 src/assemble_edges.py --relation-aggregated artifacts/relation_aggregated.jsonl --validate-schema
```

## Query Status
- The query split is directionally correct for the current hybrid imaging phenotype scope.
- `microbe_radiomics_strict`, `microbe_imaging_adjacent`, and `microbe_bodycomp` are intentionally separated so strict radiomics precision is not diluted by adjacent imaging terms.
- The microbe-side profiles now exclude reviews, meta-analyses, and study protocols because those are not useful for direct edge extraction.
- The main known limitation is that `radiomics_disease_strict` and `bodycomp_disease` are still more tuned to predictive/prognostic wording than to broad association wording.
- That is acceptable for the current proof-of-concept pass, but it should be revisited before final corpus generation.
- Query refinement on 2026-03-06 tightened `microbe_radiomics_strict`, enriched microbiome/body-composition vocabulary, removed seed-taxon bias from default profiles, and added a broader optional `bodycomp_disease_association` profile for recall-oriented runs.
- Query refinement on 2026-03-07 added an explicit `microbe_imaging_adjacent` lane for papers that use imaging-phenotype language such as `CT changes`, `quantitative CT`, or `emphysema` without explicitly saying `radiomics`.
- Current default stance:
  - `microbe_radiomics_strict`: precision-leaning
  - `microbe_imaging_adjacent`: adjacent imaging recall lane for microbiome-linked imaging phenotypes that fall outside explicit radiomics wording
  - `microbe_bodycomp`: broader phenotype coverage
  - `microbe_imaging_phenotype`: optional broader union profile for query-stage retrieval audits
  - `radiomics_disease_strict`: balanced predictive plus association language
  - `bodycomp_disease`: still precision-leaning by default
  - `bodycomp_disease_association`: optional broader recall profile
- Large PubMed corpora are now harvested with date-window splitting in `src/harvest_pubmed.py` so disease-side profiles do not silently truncate near the ESearch 10k retrieval cap.
- Live benchmark on 2026-03-07:
  - before review/protocol exclusion:
    - `microbe_radiomics_strict`: `12`
    - `microbe_imaging_adjacent`: `21`
  - after review/protocol exclusion:
    - `microbe_radiomics_strict`: `8`
    - `microbe_imaging_adjacent`: `15`
    - `microbe_bodycomp`: `99`
  - the new adjacent-imaging profile captures PMID `28704452`, the COPD lung CT changes + microbiome paper identified during sample-paper audit
  - query-text audit outcome:
    - `microbe_radiomics_strict` is now materially cleaner and contains direct radiomics/microbiome papers such as microbiota-aided radiomics, texture analysis plus microbial signatures, and COPD radiomics
    - `microbe_imaging_adjacent` remains a broader recall lane and still includes some weaker phenotype-adjacent papers, which is acceptable because it is no longer the precision set
  - merged microbe-side corpus after deduplication:
    - `120` unique papers from `122` input rows
    - `2` duplicate PMIDs removed

## Full-Text Status
- Upstream MINERVA does not download PDFs as its main full-text path.
- The upstream code resolves `PMCID`, downloads the PMC article HTML, extracts article text, and stores that full text for later sentence processing.
- This repo now supports the same basic approach in `src/download_pmc_fulltext.py`.
- Validation on 2026-03-07 for the merged microbe-side corpus:
  - `120` total papers
  - `77` with `PMCID`
  - `69` newly downloaded
  - `5` reused cached text
  - `3` failed PMC full-text fetches
- Example merged full-text-backed paper:
  - PMID `40114207` with `PMCID` `PMC11924647` now points to `artifacts/full_text/text/PMC11924647.txt`

## Current Microbe Corpus Status
- Deduplicated merged corpus:
  - `artifacts/papers_microbe_merged_dedup.jsonl`: `120` papers
  - `artifacts/papers_microbe_merged_provenance.jsonl`: `120` provenance rows
- Full-text-aware merged corpus:
  - `artifacts/papers_microbe_merged_fulltext.jsonl`: `120` papers
- Phenotype text extraction on merged corpus:
  - `artifacts/text_mentions_microbe_merged.jsonl`: `1,129` mentions
  - `9` unique phenotype features
  - `618` mentions with modality
  - `92` mentions with body location
  - `283` mentions with disease context
  - `49/120` papers contributed at least one mention
  - current mention mix is heavily body-composition dominated and still sparse for explicit subject-linked radiomics

## Current NER Assessment
- The main bottleneck is the merged `text_ner_minerva.py` pass over PMC full text, not the query layer.
- The merged full-text corpus contains about `25,199` sentences across `120` papers.
- Only about `8.26%` of those sentences show simple joint disease-plus-microbiome lexical hints, so sentence-level pruning matters.
- The NER stage now uses safer optimizations before model swaps:
  - long-sentence chunking
  - batched inference
  - disease-first filtering before microbe extraction
- Current merged full-text run status after those optimizations:
  - completed successfully in about `37.38s` on `120` papers
  - processed `25,788` sentence chunks
  - skipped microbe NER on `23,756` sentence chunks with no disease mention
  - evaluated microbe NER on `2,032` sentence chunks
  - emitted `90` entity-sentence rows and `148` relation-input rows
- Small substitute-model benchmark outcome on a fixed 5-paper subset:
  - current default `bc5cdr + d4data/biomedical-ner-all`: still the best immediate drop-in
  - `OpenMed/OpenMed-NER-SpeciesDetect-ElectraMed-33M`: too weak on the tested sample
  - `pruas/BENT-PubMedBERT-NER-Organism`: usable, but not better on the tested sample
  - `Francesco-A/BiomedNLP-PubMedBERT-base-uncased-abstract-bc5cdr-ner-v1`: much noisier without extra cleanup
- Recommended interim Hugging Face candidates while upstream checkpoints remain unavailable are tracked in `docs/MODEL_CANDIDATES.md`.

## Current Relation Extraction Assessment
- Merged relation extraction completed on [relation_input_microbe_merged.jsonl](/Users/junlee/Desktop/sanomap-radiomics-layer/artifacts/relation_input_microbe_merged.jsonl) and wrote:
  - [relation_predictions_microbe_merged.jsonl](/Users/junlee/Desktop/sanomap-radiomics-layer/artifacts/relation_predictions_microbe_merged.jsonl)
  - [relation_aggregated_microbe_merged.jsonl](/Users/junlee/Desktop/sanomap-radiomics-layer/artifacts/relation_aggregated_microbe_merged.jsonl)
  - [relation_strengths_microbe_merged.jsonl](/Users/junlee/Desktop/sanomap-radiomics-layer/artifacts/relation_strengths_microbe_merged.jsonl)
- Metrics:
  - `148` sentence-level predictions
  - `70` accepted sentence-level relations
  - `138` within-paper aggregated relations
  - `60` accepted aggregated relations
- Current recommendation:
  - treat these outputs as pipeline-valid but not graph-ready
  - accepted relations still contain malformed subject and disease spans inherited from NER, so cleanup/filtering should happen before edge assembly on this branch
  - on the accepted aggregated set (`n=60`):
    - `14` subject nodes contain `##` fragment artifacts
    - `20` subject nodes are still generic phrases
    - `42` disease strings are long clause-like spans rather than clean disease entities

## Deterministic Safety Policy
- Vision model outputs are proposals only.
- The heatmap verifier is the acceptance gate.
- Only direct evidence becomes a graph edge.
- Within-paper shared-disease bridges are hypothesis artifacts, not asserted relationships.

## Upstream Alignment Notes
- The remaining relation pipeline now carries normalized subject identity end to end, matching the upstream MINERVA pattern of preserving extracted entity identity through later graph-building stages.
- The current relation classifier is still intentionally microbe-disease scoped; extending it beyond that should happen only when a direct subject-phenotype or phenotype-disease extraction stage is added.
- The text content selection path is now also upstream-aligned at a basic level:
  - prefer PMC full article text when available
  - otherwise fall back to title plus abstract

## Current Operational Verdict
- `harvest_pubmed.py`: good enough to move forward
- `merge_paper_corpora.py`: good enough to move forward
- `download_pmc_fulltext.py`: good enough to move forward
- `extract_radiomics_text.py`: useful and operational, but should still be refined because the merged output is dominated by body-composition mentions and many mentions lack explicit subject nodes
- `text_ner_minerva.py` on the merged full-text-aware corpus: current bottleneck; refine before treating it as a routine merged-corpus stage
