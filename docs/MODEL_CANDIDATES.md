# Interim Model Candidates

This file tracks practical substitute models while upstream MINERVA-associated checkpoints remain unavailable.

## Current Position
- Keep the current defaults for proof-of-concept stability unless a controlled benchmark shows a clear gain.
- The current bottleneck is the merged full-text NER stage, so safer runtime optimizations come before aggressive model churn.

## Microbe NER
### Current default
- `d4data/biomedical-ner-all`
- Why it is only a placeholder:
  - broad biomedical NER model
  - not organism-specific
  - likely to be noisier for bacteria/species extraction than a dedicated organism model

### Accuracy-leaning candidate
- `pruas/BENT-PubMedBERT-NER-Organism`
- Why it is a better fit:
  - organism-specific token classification model
  - built on PubMedBERT
  - better aligned with species/genus extraction than a generic biomedical NER model

### Speed-leaning candidate
- `OpenMed/OpenMed-NER-SpeciesDetect-ElectraMed-33M`
- Why it is worth testing:
  - much smaller model footprint than typical PubMedBERT variants
  - explicitly positioned for species detection
  - a good candidate when throughput matters more than maximum recall

## Disease NER
### Current default
- `allenai/scibert_scivocab_uncased` checkpoint slot with fallback to `en_ner_bc5cdr_md`
- Why it is only partial:
  - the fallback is BC5CDR-specific and useful
  - the absent adapter checkpoint means the transformer path is not yet doing the intended specialized job

### Coverage-leaning candidate
- `pruas/BENT-PubMedBERT-NER-Disease`
- Why it is a better fit:
  - disease-specific model
  - PubMedBERT base
  - broader disease-entity focus than relying only on BC5CDR-style fallback behavior

### BC5CDR-oriented candidate
- `Francesco-A/BiomedNLP-PubMedBERT-base-uncased-abstract-bc5cdr-ner-v1`
- Why it is worth testing:
  - directly fine-tuned for BC5CDR disease extraction
  - close conceptual match to the current fallback behavior while staying in the transformer stack

## Relation Extraction
### Current default
- `BioMistral/BioMistral-7B`

### Optional later benchmark candidate
- `BioMistral/BioMistral-7B-DARE`
- Why it is not the first priority:
  - relation extraction is not the present throughput bottleneck
  - improving relation models before stabilizing NER will not address the main current failure mode

## Selection Rule
- If precision on microbe/species names is the problem, test `pruas/BENT-PubMedBERT-NER-Organism` first.
- If runtime is the problem, test `OpenMed/OpenMed-NER-SpeciesDetect-ElectraMed-33M` first.
- If disease recall is the problem, test `pruas/BENT-PubMedBERT-NER-Disease` first.
- If you want closest continuity with BC5CDR behavior, test `Francesco-A/BiomedNLP-PubMedBERT-base-uncased-abstract-bc5cdr-ner-v1` first.

## Recommended Benchmark Order
1. Keep the new batching and disease-first filtering on.
2. Benchmark current defaults on a fixed paper subset.
3. Swap only one NER model family at a time.
4. Compare sentence throughput, extracted entity quality, and downstream relation yield.
5. Promote a new default only after that comparison.

## Local Benchmark Snapshot (2026-03-07, 5-paper subset)
- Current stable default:
  - `bc5cdr` disease extractor + `d4data/biomedical-ner-all`
  - `3` relation rows on the subset
  - completed in about `10.63s`
- `OpenMed/OpenMed-NER-SpeciesDetect-ElectraMed-33M`:
  - ran successfully
  - produced `0` usable relation rows on the same subset
  - not a good drop-in replacement at the moment
- `pruas/BENT-PubMedBERT-NER-Organism`:
  - ran successfully
  - produced `2` usable relation rows on the same subset
  - not obviously better than the current default on the tested sample
- `Francesco-A/BiomedNLP-PubMedBERT-base-uncased-abstract-bc5cdr-ner-v1`:
  - ran successfully as a disease checkpoint
  - produced far more rows (`24`) but inspection showed strong noise and subword-like artifacts
  - do not promote without extra post-processing and a broader precision audit

## Example Commands
```bash
# Current stable proof-of-concept setting
python3 src/text_ner_minerva.py \
  --papers artifacts/papers_microbe_merged_fulltext.jsonl \
  --entity-output artifacts/entity_sentences_microbe_merged.jsonl \
  --relation-output artifacts/relation_input_microbe_merged.jsonl \
  --disease-ner-mode bc5cdr \
  --microbe-ner-model-id d4data/biomedical-ner-all \
  --umls-linker off \
  --ner-batch-size 8 \
  --validate-schema

# Accuracy-leaning microbe NER benchmark
python3 src/text_ner_minerva.py \
  --papers artifacts/tmp/papers_microbe_merged_subset5.jsonl \
  --entity-output artifacts/tmp/entity_sentences_subset5_bent_org.jsonl \
  --relation-output artifacts/tmp/relation_input_subset5_bent_org.jsonl \
  --disease-ner-mode bc5cdr \
  --microbe-ner-model-id pruas/BENT-PubMedBERT-NER-Organism \
  --umls-linker off \
  --ner-batch-size 8

# Disease transformer benchmark
python3 src/text_ner_minerva.py \
  --papers artifacts/tmp/papers_microbe_merged_subset5.jsonl \
  --entity-output artifacts/tmp/entity_sentences_subset5_bent_disease.jsonl \
  --relation-output artifacts/tmp/relation_input_subset5_bent_disease.jsonl \
  --disease-ner-mode scibert_adapter \
  --disease-ner-checkpoint pruas/BENT-PubMedBERT-NER-Disease \
  --disease-ner-base-model microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext \
  --microbe-ner-model-id d4data/biomedical-ner-all \
  --umls-linker off \
  --ner-batch-size 8
```
