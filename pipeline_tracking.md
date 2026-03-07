# Pipeline Tracking

Last updated: 2026-03-07 (America/Chicago)

## 1) Locked Direction
The repository is now locked to a hybrid two-tier design:
- strict `RadiomicFeature` core
- broader imaging phenotype extension via `BodyCompositionFeature`
- explicit `MicrobialSignature` support for non-taxon-specific microbiome states

Direct evidence graph paths are:
- `(Microbe)-[:CORRELATES_WITH]->(RadiomicFeature)`
- `(Microbe)-[:CORRELATES_WITH]->(BodyCompositionFeature)`
- `(MicrobialSignature)-[:CORRELATES_WITH]->(RadiomicFeature)`
- `(MicrobialSignature)-[:CORRELATES_WITH]->(BodyCompositionFeature)`
- `(RadiomicFeature)-[:ASSOCIATED_WITH]->(Disease)`
- `(BodyCompositionFeature)-[:ASSOCIATED_WITH]->(Disease)`

Bridge matches that only share disease context are now hypothesis artifacts, not graph edges.

## 2) Locked Harvest Profiles
Current code now supports these named profiles in `src/harvest_pubmed.py`:

### A. `microbe_radiomics_strict`
Purpose: collect papers for strict `Microbe|MicrobialSignature <-> RadiomicFeature`.

### B. `microbe_bodycomp`
Purpose: collect papers for `Microbe|MicrobialSignature <-> BodyCompositionFeature`.

### C. `microbe_imaging_adjacent`
Purpose: collect papers for microbiome-linked adjacent imaging phenotype literature that uses terms such as `CT changes`, `quantitative CT`, `imaging phenotype`, `emphysema`, or `airway lesions` without explicitly using `radiomics`.

### D. `microbe_imaging_phenotype`
Purpose: optional broader union profile combining strict radiomics, adjacent imaging phenotype, and body-composition retrieval for query-stage audits.

### E. `radiomics_disease_strict`
Purpose: collect papers for `RadiomicFeature <-> Disease`.

### F. `bodycomp_disease`
Purpose: collect papers for `BodyCompositionFeature <-> Disease`.

### G. `bodycomp_disease_association`
Purpose: collect a broader recall-oriented `BodyCompositionFeature <-> Disease` corpus when association wording beyond predictive/prognostic phrasing is needed.

Compatibility aliases kept in code:
- `microbe_radiomics`
- `radiomics_disease`

These should be treated as legacy names, not as the preferred conceptual framing.

Current assessment:
- the split itself is good and matches the hybrid two-tier design
- the microbe-side profiles are acceptably separated for proof of concept
- the disease-side profiles are still somewhat biased toward predictive/prognostic phrasing and may under-retrieve pure association papers
- therefore the default `bodycomp_disease` profile remains precision-leaning, while `bodycomp_disease_association` exists as the broader optional fallback
- review/protocol-style noise should be filtered out before text extraction because those papers do not usually carry direct evidence edges

Benchmark snapshot on 2026-03-06 using PubMed counts from 2010-01-01 through 2026-12-31:
- `microbe_radiomics_strict`: `23 -> 12`
- `microbe_bodycomp`: `122 -> 139`
- `radiomics_disease_strict`: `17,556 -> 14,060`
- `bodycomp_disease`: `10,912 -> 10,195`
- `bodycomp_disease_association`: `16,519` as optional broader-recall profile

Retrieval expansion benchmark on 2026-03-07:
- `microbe_imaging_adjacent`: `21`
- the new adjacent-imaging profile captures PMID `28704452`, the COPD lung CT changes + microbiome paper surfaced during sample-paper reference audit
- `microbe_radiomics_strict` remains unchanged at `12`, which preserves the clean direct-radiomics precision set

Query-quality refinement on 2026-03-07 after reviewing sampled titles/abstracts:
- added exclusion of reviews, meta-analyses, and protocol-style papers on the microbe-side retrieval profiles
- updated corpus counts:
  - `microbe_radiomics_strict`: `8`
  - `microbe_imaging_adjacent`: `15`
  - `microbe_bodycomp`: `99`
- sampled strict-radiomics titles are now materially cleaner and include direct imaging-microbiome studies such as:
  - PMID `40892452`: intratumoral microbiome-related MRI model
  - PMID `40114207`: intratumoral microbiota-aided fusion radiomics model
  - PMID `37894458`: CT texture analysis plus gut microbial community signatures
  - PMID `37173744`: respiratory microbiota and radiomics features in stable COPD
- sampled adjacent-imaging titles still include broader recall-oriented papers and should be treated as a secondary lane, not the precision set

Interpretation:
- `microbe_radiomics_strict` became tighter and less taxon-biased
- `microbe_bodycomp` gained useful coverage for microbial signatures and broader body-composition wording
- `radiomics_disease_strict` dropped some generic imaging-biomarker noise while aligning better with `ASSOCIATED_WITH`
- `bodycomp_disease` stayed conservative because fully broadening association language inflated counts too aggressively

Sample-paper audit on 2026-03-06:
- `sample_papers_of_radiomics/radiomics_2.pdf` maps to PMID `37173744` and is present in `artifacts/papers_microbe_radiomics_strict.jsonl`
- `sample_papers_of_radiomics/radiomics_1.pdf` maps to PMID `34472211` and is present in `artifacts/papers_microbe_bodycomp.jsonl`; it is not a strict radiomics paper and should be treated as body-composition/imaging-phenotype evidence
- reference inspection from `radiomics_2.pdf` identified PMID `28704452` (`Influence of lung CT changes in chronic obstructive pulmonary disease (COPD) on the human lung microbiome`) as directly adjacent imaging+microbiome literature that is not captured by the strict radiomics profile because it does not use explicit radiomics wording

Implication:
- the `microbe_radiomics_strict` corpus is a precision-oriented direct-radiomics set, not the full universe of imaging-plus-microbiome papers
- broader coverage should come from separate adjacent-imaging or citation-based expansion lanes rather than weakening the strict radiomics definition

Current query-stage recommendation:
- use `microbe_radiomics_strict` when the goal is explicit radiomics evidence
- use `microbe_imaging_adjacent` when the goal is adjacent imaging phenotype coverage without polluting the strict radiomics corpus
- use `microbe_imaging_phenotype` only as a broader union profile for audits or seed-paper expansion

Merged microbe-side corpus build on 2026-03-07:
- added `src/merge_paper_corpora.py` to merge and deduplicate the three microbe-side profiles by PMID
- `122` input rows collapsed to `120` unique PMIDs
- output artifacts:
  - `artifacts/papers_microbe_merged_dedup.jsonl`
  - `artifacts/papers_microbe_merged_provenance.jsonl`

Regenerated corpus artifacts on 2026-03-06:
- `artifacts/papers_microbe_radiomics_strict.jsonl`: `12` papers, `12` with abstract, `7` with PMCID
- `artifacts/papers_microbe_bodycomp.jsonl`: `139` papers, `139` with abstract, `95` with PMCID
- `artifacts/papers_radiomics_disease_strict.jsonl`: `13,889` papers, `13,702` with abstract, `8,681` with PMCID
- `artifacts/papers_bodycomp_disease.jsonl`: `10,148` papers, `10,108` with abstract, `5,690` with PMCID
- `artifacts/papers_bodycomp_disease_association.jsonl`: `16,259` papers, `16,205` with abstract, `8,996` with PMCID

Regenerated corpus artifact on 2026-03-07:
- `artifacts/papers_microbe_imaging_adjacent.jsonl`: `21` papers, `21` with abstract, `9` with PMCID

Regenerated corpus artifacts after review/protocol exclusion on 2026-03-07:
- `artifacts/papers_microbe_radiomics_strict.jsonl`: `8` papers, `8` with abstract, `5` with PMCID
- `artifacts/papers_microbe_imaging_adjacent.jsonl`: `15` papers, `15` with abstract, `7` with PMCID
- `artifacts/papers_microbe_bodycomp.jsonl`: `99` papers, `99` with abstract, `66` with PMCID

Important harvest implementation note:
- `src/harvest_pubmed.py` now splits large PubMed searches by date range to avoid the ESearch retrieval cap around 10k IDs.
- This change was necessary to regenerate the large disease-side corpora completely.

Upstream full-text alignment note on 2026-03-07:
- upstream MINERVA does not primarily download PDFs for text mining
- the upstream code resolves `PMCID`, downloads the PMC article HTML, extracts `full_text`, and then processes those full-paper texts sentence by sentence
- this repo now has an equivalent preparatory stage in `src/download_pmc_fulltext.py`
- validation on the merged microbe-side corpus:
  - `120` papers total
  - `77` with PMCID
  - `69` newly downloaded
  - `5` reused cached text
  - `3` failed PMC fetches
  - `43` without PMCID
- the downstream paper-content selection path now prefers `full_text_path` when available in both:
  - `src/extract_radiomics_text.py`
  - `src/text_ner_minerva.py`

Merged phenotype extraction pass on 2026-03-07:
- input: `artifacts/papers_microbe_merged_fulltext.jsonl`
- output: `artifacts/text_mentions_microbe_merged.jsonl`
- metrics:
  - `papers_processed`: `120`
  - `mentions_emitted`: `1,129`
  - `unique_features`: `9`
  - `with_modality`: `618`
  - `with_body_location`: `92`
  - `with_disease`: `283`
- yield audit:
  - `49/120` papers produced at least one phenotype mention
  - feature-family split is heavily body-composition dominated:
    - `body_composition`: `1,099`
    - `radiomic`: `30`
  - subject-node detection remains sparse:
    - `Microbe`: `105`
    - `MicrobialSignature`: `28`
    - `None`: `996`
- interpretation:
  - the merged phenotype extractor is operational and useful for body-composition-heavy imaging phenotype coverage
  - it is not yet a strong subject-linked radiomics extractor on the merged corpus
  - therefore downstream graph assembly can proceed for exploratory audits, but subject-to-feature relation quality should still be refined before treating this as mature upstream-style extraction

Merged microbe-disease sentence extraction status:
- `src/text_ner_minerva.py` is now code-ready to prefer PMC full text when `full_text_path` exists
- after batching, long-sentence chunking, and disease-first microbe filtering were added, the merged full-text run completed successfully on 2026-03-07
- finalized artifacts now exist:
  - `artifacts/entity_sentences_microbe_merged.jsonl`
  - `artifacts/relation_input_microbe_merged.jsonl`
- completion metrics:
  - `papers_processed`: `120`
  - `sentences_processed`: `25,788`
  - `microbe_sentences_evaluated`: `2,032`
  - `microbe_sentences_skipped_no_disease`: `23,756`
  - `entity_sentences_out`: `90`
  - `relation_rows_out`: `148`
  - wall-clock runtime: about `37.38s` with `--disease-ner-mode bc5cdr --umls-linker off --ner-batch-size 8`
- current diagnosis:
  - this stage is no longer the main blocker
  - the optimization was enough to make merged full-text NER operational under the current proof-of-concept defaults
  - the next gating question is now entity quality, not basic throughput
- safe NER optimizations implemented on 2026-03-07:
  - long-sentence chunking modeled after upstream handling of very long sentences
  - batched inference for both disease and microbe extractors
  - disease-first filtering so microbe NER only runs on sentences that already contain disease mentions
  - new CLI control: `--ner-batch-size`
- current corpus-level runtime rationale:
  - merged full-text corpus currently contains about `25,199` sentences across `120` papers
  - a simple lexical audit found only about `2,081` sentences (`8.26%`) with joint disease-plus-microbiome hints
  - therefore inference reduction matters more than immediately swapping every model
- current retrieval composition reminder:
  - merged microbe-side corpus is not mostly strict radiomics
  - source profile counts are:
    - `microbe_radiomics_strict`: `8`
    - `microbe_imaging_adjacent`: `15`
    - `microbe_bodycomp`: `99`
- interim Hugging Face substitute candidates are now tracked in `docs/MODEL_CANDIDATES.md`
- small local substitute-model benchmark on 2026-03-07 (5-paper subset):
  - current default `bc5cdr + d4data/biomedical-ner-all`: `3` relation rows in about `10.63s`
  - `OpenMed/OpenMed-NER-SpeciesDetect-ElectraMed-33M`: `0` relation rows
  - `pruas/BENT-PubMedBERT-NER-Organism`: `2` relation rows
  - `Francesco-A/BiomedNLP-PubMedBERT-base-uncased-abstract-bc5cdr-ner-v1` disease checkpoint: `24` relation rows but with clear noisy extractions such as subword fragments and spurious disease mentions
- current recommendation remains:
  - keep the optimized default stack for proof-of-concept progression
  - do not switch microbe or disease defaults yet

Merged relation extraction pass on 2026-03-07:
- input: `artifacts/relation_input_microbe_merged.jsonl`
- outputs:
  - `artifacts/relation_predictions_microbe_merged.jsonl`
  - `artifacts/relation_aggregated_microbe_merged.jsonl`
  - `artifacts/relation_strengths_microbe_merged.jsonl`
- execution choice:
  - this workspace is CPU-only (`cuda_available = false`)
  - therefore the merged proof-of-concept run used `src/relation_extract_stage.py --backend heuristic`
  - `BioMistral/BioMistral-7B` remains the intended substitute model policy, but it was not practical to execute as a 7B text-generation backend on CPU for this pass
- metrics:
  - `input_rows`: `148`
  - `predictions_out`: `148`
  - `accepted_sentence_relations`: `70`
  - `aggregated_relations`: `138`
  - `accepted_aggregated_relations`: `60`
  - `strength_groups`: `60`
- label distribution:
  - sentence-level: `positive 49`, `negative 21`, `unrelated 78`
  - aggregated: `positive 39`, `negative 21`, `unrelated 78`
- quality interpretation:
  - the relation stage is now structurally complete on the merged branch
  - however, accepted examples still show malformed spans inherited from NER, such as generic phrases or token-fragment artifacts
  - quantitative warning on accepted aggregated relations (`n=60`):
    - `14` subject nodes contain `##` fragment artifacts
    - `20` subject nodes are generic phrases like `bacterial` or `microbial`
    - `42` disease strings are long clause-like phrases of 6+ words rather than clean disease entities
  - do not promote this merged branch directly to graph edge assembly without another cleanup pass on subject/disease span quality

## 3) Why The Scope Changed
Observed mismatch in the previous baseline:
- local `microbe_radiomics` corpus contained many body-composition and DXA papers, not only strict radiomics papers
- local quick audit found roughly `20/144` papers with explicit radiomics-style wording versus roughly `119/144` with body-composition terms
- PubMed count checks used during planning showed strict `microbiome + radiomics` is a small slice relative to `microbiome + body composition`

Result:
- the extension is now documented as radiomics-first but not radiomics-only

## 4) Current Data Model
Phenotype mention records now carry:
- `feature_family`
- `node_type`
- `ontology_namespace`
- `claim_hint`
- `subject_node_type`
- `subject_node`

Verified graph edges now carry:
- `subject_node_type`
- `subject_node`
- `object_node_type`
- `object_node`
- `graph_rel_type`
- `feature_family`
- `claim_hint`
- `assertion_level`

New audit artifact:
- `artifacts/bridge_hypotheses.jsonl`

Relation-input and relation-aggregation artifacts now also carry:
- `microbe` as a legacy compatibility field
- `subject_node_type`
- `subject_node`

This is intentionally aligned with upstream MINERVA's pattern of preserving normalized entity identity through later pipeline stages, without changing the current classifier into a broader non-microbe relation model yet.

## 5) Relation Semantics
- Text-derived phenotype-to-disease edges emit `ASSOCIATED_WITH`
- Verified figure-derived subject-to-feature quantitative links emit `CORRELATES_WITH`
- `PREDICTS` is intentionally not emitted by default in the current pass
- predictive, diagnostic, and prognostic cues are preserved as `claim_hint` metadata only

## 6) Baseline Corpus Snapshot Before This Refinement
The following counts are retained as historical baseline from the previous broad query strategy:

### A. Broad `microbe_radiomics`
- Output: `artifacts/papers_microbe_radiomics_2010_2026_broad_v2.jsonl`
- Papers fetched: `144`
- With abstract: `144`
- With PMCID: `95`
- Year coverage: 2011-2026

### B. Broad `radiomics_disease`
- Output: `artifacts/papers_radiomics_disease_2010_2026.jsonl`
- Papers fetched: `17,539`
- With abstract: `17,324`
- With PMCID: `10,942`

These counts were produced before the profile split and should not be interpreted as the new strict radiomics/body-composition baselines.

## 7) Immediate Next Operational Step
Use the regenerated harvest artifacts to drive downstream extraction and yield audits:
- optionally run `src/download_pmc_fulltext.py` first for corpora with strong PMCID coverage
- use `artifacts/papers_microbe_merged_dedup.jsonl` as the default deduplicated microbiome-side input
- use `artifacts/papers_microbe_merged_fulltext.jsonl` as the preferred text-stage input when full-text-aware extraction is desired
- refine merged `text_ner_minerva.py` execution before relying on it for routine relation aggregation
- if immediate momentum is needed, continue exploratory downstream work with:
  - merged phenotype mentions
  - existing strict/adjacent/bodycomp corpora
  - full-text-backed paper metadata
- decide whether disease-side extraction should use the default precision profile or the broader association profile

After that, the next upstream-parity milestone is to replace mention-level co-occurrence on the new axes with direct relation extraction for subject-to-phenotype and phenotype-to-disease evidence.

## 8) Temporary Model Availability Note
- Some model weights or checkpoints associated with the upstream MINERVA stack are not yet available in this workspace.
- The current repo therefore uses substitute defaults to achieve an end-to-end proof-of-concept pipeline first.
- This is a temporary implementation choice, not a claim of exact upstream model parity.
- Once the intended upstream weights/checkpoints are available, rerun the pipeline and re-evaluate outputs under the final stack.
- interim substitution guidance while waiting on upstream checkpoints:
  - accuracy-leaning microbe NER candidate: `pruas/BENT-PubMedBERT-NER-Organism`
  - speed-leaning microbe NER candidate: `OpenMed/OpenMed-NER-SpeciesDetect-ElectraMed-33M`
  - broader disease NER candidate: `pruas/BENT-PubMedBERT-NER-Disease`
  - BC5CDR-focused disease NER candidate: `Francesco-A/BiomedNLP-PubMedBERT-base-uncased-abstract-bc5cdr-ner-v1`
  - optional stronger temporary relation model to evaluate later, after NER is stable: `BioMistral/BioMistral-7B-DARE`
