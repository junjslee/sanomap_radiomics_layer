# Pipeline Tracking

Last updated: 2026-03-18 (America/Chicago)

Primary operational handoff file:
- `docs/NEXT_STEPS.md`

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

Local sample-paper audit on 2026-03-06:
- one local radiomics sample maps to PMID `37173744` and is present in `artifacts/papers_microbe_radiomics_strict.jsonl`
- one local imaging/body-composition sample maps to PMID `34472211` and is present in `artifacts/papers_microbe_bodycomp.jsonl`; it is not a strict radiomics paper and should be treated as body-composition/imaging-phenotype evidence
- reference inspection from the local radiomics sample identified PMID `28704452` (`Influence of lung CT changes in chronic obstructive pulmonary disease (COPD) on the human lung microbiome`) as directly adjacent imaging+microbiome literature that is not captured by the strict radiomics profile because it does not use explicit radiomics wording

Implication:
- the `microbe_radiomics_strict` corpus is a precision-oriented direct-radiomics set, not the full universe of imaging-plus-microbiome papers
- broader coverage should come from separate adjacent-imaging or citation-based expansion lanes rather than weakening the strict radiomics definition

Current query-stage recommendation:
- use `microbe_radiomics_strict` when the goal is explicit radiomics evidence
- use `microbe_imaging_adjacent` when the goal is adjacent imaging phenotype coverage without polluting the strict radiomics corpus
- use `microbe_imaging_phenotype` only as a broader union profile for audits or seed-paper expansion

Live retrieval optimization on 2026-03-18:
- strict-radiomics loop:
  - baseline `microbe_radiomics_strict`: live count `8`
  - broadened strict candidate with extra microbiome synonyms, imaging-biomarker language, and association/outcome signals: live count `16`
  - sampled-title decision: reject the broadened strict variant as default because the additional titles were materially noisier
- body-composition loop:
  - baseline `microbe_bodycomp`: live count `99`
    - first `30` fetched papers: `11` mention-positive papers and `61` body-composition mentions under the current text extractor
  - no-modality variants:
    - association/outcome constrained: live count `955`, first `30` fetched papers: `4` mention-positive papers and `20` body-composition mentions
    - unconstrained no-modality: live count `1324`, first `30` fetched papers: `6` mention-positive papers and `17` body-composition mentions
  - bounded recall compromise:
    - new `microbe_bodycomp_clinical_recall`: live count `584`
    - first `30` fetched papers: `8` mention-positive papers and `46` body-composition mentions
    - local harvested artifact: `artifacts/papers_microbe_bodycomp_clinical_recall.jsonl` with `584` papers, `583` abstracts, and `403` PMCIDs
    - title/abstract extractor output: `artifacts/text_mentions_microbe_bodycomp_clinical_recall.jsonl` with `748` mentions
    - baseline title/abstract extractor comparison:
      - `artifacts/papers_microbe_bodycomp.jsonl`: `99` papers -> `162` mentions
      - `artifacts/papers_microbe_bodycomp_clinical_recall.jsonl`: `584` papers -> `748` mentions
    - separate merged-harvest audit:
      - baseline default microbe-side harvest: `120` unique PMIDs -> `31` PMIDs with mentions -> `162` mentions
      - expanded harvest with recall lane: `640` unique PMIDs -> `176` PMIDs with mentions -> `777` mentions
      - added PMIDs from the recall expansion: `520`
- operational decision:
  - keep `microbe_radiomics_strict` unchanged
  - keep `microbe_bodycomp` unchanged as default
  - add `microbe_bodycomp_clinical_recall` only as an optional recall-expansion profile

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

Hosted relation backend implementation on 2026-03-17:
- `src/model_backends.py` now includes an `openai_compatible` backend that uses chat-completions-style HTTP calls
- `src/relation_extract_stage.py` now accepts:
  - `--backend openai_compatible`
  - `--api-base-url`
  - `--api-key`
- current intent is Hugging Face first through `https://router.huggingface.co/v1`, while preserving compatibility with Ollama or another OpenAI-compatible provider later
- local verification is complete through mocked HTTP tests and the full local pytest suite (`75 passed`)
- a real hosted smoke run is still pending, so no provider-backed merged relation artifacts have been recorded yet

Hosted pilot status on 2026-03-18:
- real provider-backed smoke run is no longer pending:
  - `deepseek-ai/DeepSeek-V3-0324` completed a 3-row Hugging Face router smoke run successfully
- bounded 10-row comparison pilot status:
  - `deepseek-ai/DeepSeek-V3-0324`: completed successfully with `9/10` accepted aggregated relations
  - `meta-llama/Llama-3.1-8B-Instruct`: auto-routed to Cerebras and failed with Cloudflare `1010`
  - `Qwen/Qwen2.5-7B-Instruct`: auto-routed to Together and failed with Cloudflare `1010`
  - `meta-llama/Llama-3.1-8B-Instruct:novita`: explicit provider routing reached HF router successfully but failed with `402` because included HF credits were exhausted
- current operational conclusion:
  - HF router auth and transport are proven
  - provider routing and quota, not repo code, are now the main blockers
  - `deepseek-ai/DeepSeek-V3-0324` is the only confirmed usable hosted baseline in the current account/environment

Gemini direct-path fix on 2026-03-18:
- official Gemini OpenAI-compatible docs were verified before patching:
  - base URL: `https://generativelanguage.googleapis.com/v1beta/openai`
  - model ids such as `gemini-2.5-flash` and `gemini-2.5-flash-lite`
- `src/relation_extract_stage.py` now resolves `gemini-*` model ids through Gemini-specific env settings instead of inheriting the generic HF router base URL
- `src/model_backends.py` now fails fast if a `gemini-*` model id is pointed at a non-Google base URL
- Gemini 10-row pilot status:
  - `gemini-2.5-flash-lite`: completed successfully
  - accepted aggregated relations: `6/10`
  - rough estimated run cost: about `$0.0004`
- current operational conclusion:
  - Gemini direct is now a real low-cost hosted option in this repo
  - DeepSeek remains the stronger accepted-rate baseline on the current 10-row pilot
  - Gemini is the cheaper and more conservative direct path

Gemini full current-local relation run on 2026-03-18:
- execution context:
  - input: `artifacts/relation_input_microbe_merged.jsonl`
  - backend: `openai_compatible`
  - model: `gemini-2.5-flash-lite`
  - default relation-stage self-consistency settings were used (`7` samples, full-consistency acceptance)
- output artifacts:
  - `artifacts/relation_predictions_microbe_merged.gemini25_flash_lite.jsonl`
  - `artifacts/relation_aggregated_microbe_merged.gemini25_flash_lite.jsonl`
  - `artifacts/relation_strengths_microbe_merged.gemini25_flash_lite.jsonl`
  - `artifacts/manifests_gemini25_flash_lite/`
- metrics:
  - `input_rows`: `26`
  - `predictions_out`: `26`
  - `accepted_sentence_relations`: `14`
  - `accepted_aggregated_relations`: `14`
  - `full_consistency_rate`: `0.8462`
- accepted-output audit:
  - accepted disease-prefix fragments still present:
    - `and ...`: `5`
    - `in ...`: `3`
    - `reduces ...`: `1`
  - accepted examples included:
    - `propionibacteriaceae` + `and metabolic syndrome`
    - `proteobacteria phylum` + `in cirrhosis`
    - `clostridium symbiosum` + `reduces inflammation`
- current operational conclusion:
  - Gemini direct is now the first low-cost real model-backed full run on the current local relation set
  - provider setup is no longer the main blocker
  - the cleanup milestone is reopened because the model-backed run exposed accepted span junk that the heuristic rerun had masked

Cleanup refinement after the first full Gemini run on 2026-03-18:
- code changes:
  - `src/span_cleanup.py` now strips leading disease conjunction and preposition fragments such as `and ...` and `in ...`
  - `src/span_cleanup.py` now rejects verb-led and generic relation-language disease phrases such as `reduces inflammation` and `pro-inflammatory or disease`
  - `src/span_cleanup.py` now strips noisy subject tails such as `phylum`, `class`, `families`, and `bearing`
- validation:
  - targeted local pytest:
    - `tests/test_span_cleanup.py`
    - `tests/test_build_relation_input.py`
    - `tests/test_relation_extract_stage.py`
    - result: `26 passed`
  - full local pytest:
    - result: `85 passed`
- local pre-inference audit on `artifacts/relation_input_microbe_merged.jsonl`:
  - kept rows: `19/26`
  - filtered reasons: `{'disease_relation_language': 7}`
  - no kept rows still start with `and `, `in `, or `reduces `
  - no kept subject rows remain as `proteobacteria phylum`, `proteobacteria bearing`, `clostridia class`, or `peptostreptococcaceae families`
- next required check:
  - rerun `gemini-2.5-flash-lite` on the same 26-row local relation set and re-audit accepted aggregated outputs
  - before that paid rerun, estimate the cost in chat and ask the operator:
    - `acknowledge the cost and proceed? [y/n]`

Gemini rerun after cleanup refinement on 2026-03-18:
- execution context:
  - input: `artifacts/relation_input_microbe_merged.jsonl`
  - backend: `openai_compatible`
  - model: `gemini-2.5-flash-lite`
  - transient-hosted retry logic was active in `OpenAICompatibleRelationBackend`
- metrics:
  - `input_rows`: `26`
  - `rows_after_filters`: `19`
  - `filtered_out_rows`: `7`
  - `filtered_reason_counts`:
    - `disease_relation_language`: `7`
  - `predictions_out`: `19`
  - `accepted_sentence_relations`: `10`
  - `accepted_aggregated_relations`: `8`
  - `full_consistency_rate`: `0.7895`
- accepted-output audit:
  - previous malformed accepted patterns are now removed:
    - leading `and ...`: `0`
    - leading `in ...`: `0`
    - leading `reduces ...`: `0`
    - `pro-inflammatory or disease`: `0`
    - subject tails `proteobacteria phylum`, `proteobacteria bearing`, `clostridia class`, `peptostreptococcaceae families`: `0`
  - accepted rows now include:
    - `propionibacteriaceae` + `metabolic syndrome`
    - `proteobacteria` + `cirrhosis`
    - `clostridia` + `cirrhosis`
    - `proteobacteria` + `systemic inflammation`
    - `peptostreptococcaceae` + `inflammation`
    - `coprococcus` + `polycystic ovary syndrome`
    - `faecalibacterium prausnitzii` + `diabetes`
    - `roseburia spp` + `inflammation`
- current operational conclusion:
  - the cleanup refinement solved the malformed disease-prefix and noisy subject-tail issues exposed by the first Gemini run
  - the remaining graph-readiness question is semantic breadth on accepted disease targets like `inflammation`, not malformed span extraction

Phenotype-axis PoC assembly on 2026-03-18:
- code changes:
  - `src/assemble_edges.py` now cleans text-derived disease spans before emitting phenotype-to-disease edges
  - `src/assemble_edges.py` now emits audit-only direct text subject-to-phenotype candidates
  - `src/types.py` now includes `PhenotypeAxisCandidate`
  - new schema: `src/schemas/phenotype_axis_candidates.schema.json`
  - `docs/explorer/index.html` now supports `verified_edges*.jsonl`, `bridge_hypotheses*.jsonl`, and `phenotype_axis_candidates*.jsonl`
- local assembly run:
  - input text mentions: `artifacts/text_mentions_microbe_merged.jsonl`
  - input relation aggregation: `artifacts/relation_aggregated_microbe_merged.gemini25_flash_lite.jsonl`
  - output artifacts:
    - `artifacts/verified_edges_microbe_merged.gemini25_flash_lite.jsonl`
    - `artifacts/verified_edges_microbe_merged.gemini25_flash_lite.csv`
    - `artifacts/neo4j_relationships_microbe_merged.gemini25_flash_lite.csv`
    - `artifacts/bridge_hypotheses_microbe_merged.gemini25_flash_lite.jsonl`
    - `artifacts/phenotype_axis_candidates_microbe_merged.jsonl`
  - metrics:
    - `text_edges`: `17`
    - `axis_candidates_out`: `61`
    - `bridge_hypotheses_out`: `143`
    - `text_rejected`: `1100`
    - `axis_rejected`: `996`
    - `unique_disease_targets`: `9`
    - `unique_phenotype_subjects`: `6`
  - follow-up tightening:
    - `src/span_cleanup.py` now strips `abundances`, trailing `with`, and trailing `but` from subject spans
    - `src/assemble_edges.py` now applies an assembly-specific semantic filter and normalization pass so clause-like text-derived disease strings are less likely to become graph-ready edges
- local audit summary:
  - the extension axis is now explicit as an artifact instead of being buried in raw text mentions
  - `phenotype_axis_candidates` currently splits as:
    - `Microbe`: `45`
    - `MicrobialSignature`: `16`
  - before the assembly-only disease-side pass, the text edge artifact had `39` edges and `32` unique disease strings; after the pass it has `17` edges and `9` unique disease targets
  - graph-invalid disease-side patterns now audit to `0` in the emitted edge artifact for:
    - scaffold starters like `as a measure of ...`, `such as ...`, `evidence for ...`, `time points of ...`
    - clause fragments like `... causes ...`, `... is a disease`, `... without affecting ...`
    - phenotype leakage like `subcutaneous adipose tissue in colorectal cancer` and `gut microbiota in cirrhosis`
    - bare `inflammation`
  - current residual review question:
    - whether qualified inflammation outcomes such as `systemic inflammation` and `low-grade chronic inflammation` should remain as graph `Disease` nodes or move to audit-only treatment
- current operational conclusion:
  - the phenotype-axis proof of concept now exists locally in a concrete artifact set
  - the next blocker is policy-level disease-node admissibility, not the existence of the axis layer itself

Cleanup-aware local rebuild on 2026-03-17:
- execution context:
  - worktree-local ignored outputs in `artifacts/`
  - read-only merged input corpus from `/Users/junlee/Desktop/sanomap-radiomics-layer/artifacts/papers_microbe_merged_fulltext.jsonl`
  - `heuristic` relation backend on CPU
- output metrics:
  - `src/extract_radiomics_text.py`: `1,129` mentions, unchanged from the previous local baseline
  - `src/text_ner_minerva.py`: `54` entity sentences and `83` raw relation rows
  - `src/build_relation_input.py`: `35` final relation-input rows after radiomics-context gating
  - `src/relation_extract_stage.py`: `35` aggregated relations, `23` accepted aggregated relations
- important runtime note:
  - the local environment could not download `d4data/biomedical-ner-all`
  - `microbe_model_available = false`
  - this rebuild therefore used regex fallback for microbe extraction and should be treated as a lower-recall local audit, not a final production-quality run
- accepted aggregated quality delta versus the 2026-03-07 baseline:
  - subject nodes containing `##`: `14 -> 0`
  - generic subject terms caught by the shared cleanup helper: `16 -> 0`
  - disease spans caught by shared cleanup as relation-language: `24 -> 0`
  - disease spans caught by shared cleanup as clause-like: `15 -> 0`
  - disease strings of `6+` words: `42 -> 6`
- residual accepted examples still worth fixing before graph promotion:
  - subject tail fragments such as `peptostreptococcaceae and`, `fusobacteria is`, and `fusobacteria were`
  - disease clause-prefix fragments such as `in adults with chronic hiv infection` and `one of the main manifestations of cirrhosis`
- interpretation:
  - the shared cleanup helper materially improved accepted relation quality
  - this historical rerun still left a smaller residual cleanup pass to do before graph promotion
  - the follow-up local audit should be compared against this point before deciding whether to move on to remote model-backed extraction and edge assembly

Residual-cleanup rerun on 2026-03-17:
- execution context:
  - same read-only merged input corpus from `/Users/junlee/Desktop/sanomap-radiomics-layer/artifacts/papers_microbe_merged_fulltext.jsonl`
  - same CPU-only `heuristic` relation backend
  - same offline fallback constraint for `d4data/biomedical-ner-all`
- output metrics:
  - `src/text_ner_minerva.py`: `38` entity sentences and `60` raw relation rows
  - `src/build_relation_input.py`: `26` final relation-input rows after radiomics-context gating
  - `src/relation_extract_stage.py`: `26` aggregated relations, `20` accepted aggregated relations
- accepted aggregated quality delta versus the 2026-03-07 baseline:
  - subject nodes containing `##`: `14 -> 0`
  - generic subject terms caught by the shared cleanup helper: `16 -> 0`
  - disease spans caught by shared cleanup as relation-language: `23 -> 0`
  - disease spans caught by shared cleanup as clause-like: `18 -> 0`
  - disease strings of `6+` words: `42 -> 0`
  - subject trailing fragments: `7 -> 0`
  - disease leading-prefix fragments: `7 -> 0`
- interpretation:
  - the narrower cleanup pass removed the previously remaining subject-tail and disease-prefix fragment patterns from accepted aggregated outputs in the local heuristic rerun
  - this is still a lower-recall local audit because microbe extraction fell back to regex
  - do not treat it as upstream-parity relation quality until the same cleanup result is confirmed on a model-backed GPU or hosted run

Expanded corpus build on 2026-03-19:
- PMC full-text download for the recall lane:
  - input: `artifacts/papers_microbe_bodycomp_clinical_recall.jsonl` (`584` papers)
  - downloaded: `400` papers with full text
  - output: `artifacts/papers_microbe_bodycomp_clinical_recall_fulltext.jsonl`
- Merged baseline + recall into expanded corpus:
  - `640` unique papers (deduplicated by PMID)
  - output: `artifacts/papers_microbe_expanded_fulltext.jsonl`
- Text extraction on expanded corpus:
  - `src/extract_radiomics_text.py`: `5,721` phenotype mentions
  - output: `artifacts/text_mentions_microbe_expanded.jsonl`
- NER and relation input on expanded corpus:
  - `src/text_ner_minerva.py`: `119` entity sentences, `143` raw NER rows
  - `d4data/biomedical-ner-all` downloaded successfully this run (`microbe_model_available = true`, MPS device)
  - output: `artifacts/entity_sentences_microbe_expanded.jsonl`
  - `src/build_relation_input.py`: `67` relation-input rows after radiomics-context gating
  - output: `artifacts/relation_input_microbe_expanded.jsonl`
- MPS acceleration added to `src/text_ner_minerva.py` on 2026-03-19:
  - `MicrobeExtractor.__init__` now detects MPS via `torch.backends.mps.is_available()` and sets `device="mps"` for Apple Silicon
  - fallback to `cpu` on non-MPS platforms

Span cleanup Option C implementation on 2026-03-19:
- Decision rationale: risk-stratified dual-layer — pre-Gemini high-confidence rules only, post-assembly schema enforcement regardless
- Pre-Gemini changes in `src/span_cleanup.py`:
  - added `"as"` to `SUBJECT_TRAILING_FRAGMENT_TOKENS` (catches `akkermansia as` patterns)
  - extended `DISEASE_RELATION_LANGUAGE_TOKENS` with finite causal verbs: `ameliorate`, `ameliorates`, `appears`, `cause`, `causes`, `contribute`, `contributes`, `induce`, `induces`, `prevent`, `prevents`, `promote`, `promotes`
  - extended `_is_generic_microbe_term`: length guard raised from `<= 3` to `<= 5` tokens; hyphenated-compound detection added (e.g. `bacteria-derived`)
  - added trailing numeric suffix stripping in `clean_subject_span` (e.g. `ruminococcus 2` → `ruminococcus`)
  - tightened disease length threshold from `> 8` to `>= 8` tokens
- Post-assembly changes in `src/assemble_edges.py`:
  - article prefix stripping in `_clean_text_disease`: removes leading `a`, `an`, `the`, `this`, `that` when followed by remaining tokens
  - new `TEXT_EDGE_DISEASE_PREFIX_PATTERNS`: gerund/subordinating-conjunction leads (`offering`, `dependent`, `preventing`, `since`, `because`, `despite`, `including`, `hallmark of`, `models? of`, `improve`); population prefix leads (`individuals? with`, `patients? with`, `subjects? with`); participle fragment leads (`mediated`, `grade`, `[a-z]+-driven`)
  - new `TEXT_EDGE_DISEASE_SUBSTRING_PATTERNS`: causal/directional verbs not caught by pre-filter (`promotes?`, `induces?`, `ameliorates?`, `contributes?`, `prevents?`, `in patients? without`)
- Validation after Option C implementation:
  - `conda run -n base python -m pytest -q`: `99 passed`
  - pre-Gemini audit on `artifacts/relation_input_microbe_expanded.jsonl` (`67` rows): `16` filtered (`12 generic_microbe_term`, `4 disease_relation_language`), `51` rows passed to Gemini

Gemini v1 run on expanded corpus on 2026-03-19:
- execution context:
  - input: `artifacts/relation_input_microbe_expanded.jsonl` (before pre-filter deployment)
  - backend: `openai_compatible`
  - model: `gemini-2.5-flash-lite`
  - full-consistency self-consistency sampling (`7` samples)
- output artifact: `artifacts/relation_aggregated_microbe_expanded.gemini25_flash_lite.jsonl`
- metrics:
  - `input_rows`: `67`
  - `predictions_out`: `65`
  - `accepted_aggregated_relations`: `31`
  - `full_consistency_rate`: `0.8955`
- audit result: significant span leakage observed in accepted relations (clause-like disease strings, article-prefixed disease strings, gerund leads, causal-verb fragments) — triggered Option C implementation

Gemini v2 run on cleaned expanded corpus on 2026-03-19:
- execution context:
  - input: `artifacts/relation_input_microbe_expanded.jsonl` (with pre-Gemini filter active)
  - backend: `openai_compatible`
  - model: `gemini-2.5-flash-lite`
  - full-consistency self-consistency sampling (`7` samples)
- output artifact: `artifacts/relation_aggregated_microbe_expanded.gemini25_flash_lite.v2.jsonl`
- pre-filter metrics:
  - `input_rows`: `67`
  - `filtered_out_rows`: `16`
  - `rows_after_filters`: `51`
  - filtered reasons: `{'generic_microbe_term': 12, 'disease_relation_language': 4}`
- classifier metrics:
  - `predictions_out`: `51`
  - `accepted_aggregated_relations`: `22`
- accepted pairs (22, before post-assembly filter):
  - `proteobacteria` + `cirrhosis`
  - `catenibacterium` + `cardiovascular disease`
  - `peptostreptococcus stomatis` + `cirrhosis`
  - `ruminococcus` + `cirrhosis`
  - `bifidobacterium bifidum` + `obesity`
  - `bifidobacterium lactis` + `obesity`
  - `catenibacterium` + `body cell mass deficiency in cirrhosis`
  - `dysosmobacter` + `obesity`
  - `lactobacillus-containing probiotic` + `systemic inflammation`
  - plus `13` others with disease strings caught by post-assembly filter

Edge assembly v2 on expanded corpus on 2026-03-19:
- input relation aggregation: `artifacts/relation_aggregated_microbe_expanded.gemini25_flash_lite.v2.jsonl`
- input text mentions: `artifacts/text_mentions_microbe_expanded.jsonl`
- output artifacts:
  - `artifacts/verified_edges_microbe_expanded.gemini25_flash_lite.v2.jsonl`
  - `artifacts/bridge_hypotheses_microbe_expanded.gemini25_flash_lite.v2.jsonl`
  - `artifacts/phenotype_axis_candidates_microbe_expanded.v2.jsonl`
- metrics:
  - phenotype-to-disease text edges (from `extract_radiomics_text.py` co-mentions): `213`
  - axis candidates: `233`
  - bridge hypotheses: `232`
- important pipeline note: the `213` text edges are from phenotype co-mention extraction, not from Gemini microbe-disease output — these are two separate pipelines with independent disease string sources
- post-assembly filter applied to `22` Gemini-accepted microbe-disease pairs:
  - `13` rejected by post-assembly patterns (gerund disease leads, subordinating conjunction leads, causal-verb substrings, population-prefixed strings)
  - `9` clean graph-ready pairs passed through:
    - `proteobacteria` + `cirrhosis`
    - `catenibacterium` + `cardiovascular disease`
    - `peptostreptococcus stomatis` + `cirrhosis`
    - `ruminococcus` + `cirrhosis`
    - `bifidobacterium bifidum` + `obesity`
    - `bifidobacterium lactis` + `obesity`
    - `catenibacterium` + `body cell mass deficiency in cirrhosis`
    - `dysosmobacter` + `obesity`
    - `lactobacillus-containing probiotic` + `systemic inflammation`
- open policy questions:
  - `catenibacterium` + `body cell mass deficiency in cirrhosis`: borderline qualifier — `cirrhosis` context may be a disease qualifier rather than a separate disease
  - `lactobacillus-containing probiotic` + `systemic inflammation`: `MicrobialSignature` subject + broad inflammation target — needs explicit policy decision before graph promotion
- current full-suite result: `99 passed` (no regressions)
- NER strategy decision (2026-03-19):
  - confirmed local `d4data/biomedical-ner-all` with MPS is the right approach for microbe NER
  - HF Inference Providers and Serverless API credits are unified as of July 2025 — NOT a separate free tier
  - HF Inference API is not a free fallback for BERT token-classification at scale
  - PubTator3 (free NCBI REST API) is a viable free fallback for species + disease NER if local model is unavailable
  - Gemini LLM NER is NOT recommended: F1 `0.60-0.70` for microbial entities vs `0.75-0.83` for fine-tuned BERT; span boundary approximation unacceptable for the pipeline

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
