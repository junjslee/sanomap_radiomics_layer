# Interim Model Candidates

This file tracks practical substitute models while upstream MINERVA-associated checkpoints remain unavailable.

Last updated: 2026-03-30 (research-agent sweep of HuggingFace Hub and arXiv 2024–2025 literature)

## Current Position
- Keep current defaults for proof-of-concept stability unless a controlled benchmark shows a clear gain.
- The current bottleneck is the merged full-text NER stage, so safer runtime optimizations come before aggressive model churn.

---

## Microbe NER

### Current default
- `d4data/biomedical-ner-all`
- Why it is a placeholder: general biomedical NER (MACCROBAT, 107 entity types); not organism-specific; no benchmark on Linnaeus or Species-800.

### Recommended upgrade
- **`OpenMed/OpenMed-NER-SpeciesDetect-BioMed-109M`** (DeBERTa-v3-base + LoRA, DAPT on 350K biomedical passages)
- Benchmarks: SotA on Linnaeus (+3.80 pp over prior best) and Species-800 (+0.92 pp). Prior Linnaeus SotA ≈ 92.7 (BERN2). Absolute F1 not published in model card but exceeds it.
- M2/MPS feasible: Yes — 109M params, LoRA adapter is small.
- Reference: arXiv 2508.01630

### Strong alternative
- **`dmis-lab/bern2-ner`** (multi-task NER, BioBERT backbone)
- F1 ≈ 92.7 on Linnaeus species track (published in BERN2 paper, PMC9563680).
- Covers 9 entity types including `species`, `disease`, `gene`, `chemical`.
- Note: designed to run with a BERN2 normalization backend; NER-only loading is supported but normalization won't be active.

### Watch list (not yet public)
- `github.com/omicsNLP/microbiomeNER` — BioBERT fine-tuned on 1,410 full-text microbiome articles, **F1 = 0.96**. Best known public microbiome-specific NER. Gated pending peer review as of August 2025 preprint (bioRxiv 2025.08.29.671515).

### Evaluated and rejected
- `OpenMed/OpenMed-NER-SpeciesDetect-ElectraMed-33M`: 0 usable relation rows on 5-paper subset (2026-03-07 benchmark).
- `pruas/BENT-PubMedBERT-NER-Organism`: 2 relation rows vs. 3 for current default on 5-paper subset; not obviously better on current data.

---

## Disease NER

### Current default
- `en_ner_bc5cdr_md` (spaCy CNN pipeline, BC5CDR)
- Estimated F1: ~0.84–0.87 on BC5CDR-Disease (community benchmarks, 2019-era model).

### Recommended upgrade (low friction)
- **`raynardj/ner-disease-ncbi-bionlp-bc5cdr-pubmed`** (PubMed-pretrained RoBERTa)
- Fine-tuned on NCBI-disease + BC5CDR. Standard HuggingFace `pipeline("ner", ...)` API. NCBI-disease SotA-class (~87–90).
- M2/MPS feasible: Yes — base-size.

### Best available accuracy
- **`OpenMed/OpenMed-NER-DiseaseDetect-BioMed-335M`** (DeBERTa-v3-large + LoRA DAPT)
- Current SotA on BC5CDR-Disease as of arXiv 2508.01630 (+2.70 pp over prior best).
- M2/MPS feasible: Borderline (335M params, ~1.3GB); should fit in 8GB unified memory.

### Additional candidates
- `pruas/BENT-PubMedBERT-NER-Disease` — PubMedBERT on NCBI Disease + BC5CDR + PHAEDRA; estimated ~88–90 F1.
- `Francesco-A/BiomedNLP-PubMedBERT-base-uncased-abstract-bc5cdr-ner-v1` — BC5CDR fine-tune, but produced 24 noisy rows on 5-paper subset (2026-03-07). Do not promote without precision audit.
- `Francesco-A/BiomedNLP-PubMedBERT-base-uncased-abstract-bc5cdr-ner-LoRA-v1` — LoRA variant; not separately benchmarked.

---

## Relation Extraction

### Current default
- Gemini 2.5 Flash-Lite via `openai_compatible` backend; 7 samples/pair, full-consistency acceptance.
- Measured full-consistency rate on current corpus: **0.896**.

### Best available (requires fine-tuning)
- Fine-tune **`microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract`** on **MicrobioRel-cur**
  - MicrobioRel dataset: gut microbiome domain, 22 relation types (bioRxiv 2025.08.03.666357, HuggingFace release pending).
  - Fine-tuned F1 = **71.3%** on MicrobioRel-cur (arXiv 2506.08647 — best encoder model on this benchmark).
  - M2/MPS feasible: Yes (base-size). Fine-tuning requires labeled data.

### Strong alternative (Lever et al. 2023 dataset)
- Fine-tune **BioLinkBERT-large** on Lever et al. 2023 labeled microbiome-disease sentences (F1/P/R all > 0.80).
- Reference: BMC Bioinformatics doi:10.1186/s12859-023-05411-z. Dataset covers positive/negative/no association.
- M2/MPS: Borderline (large variant ~340M).

### Evaluated
- `BioMistral/BioMistral-7B` base (no fine-tune): "poor quality" on zero-shot RE per MINERVA authors and Lever et al. 2023. Requires >8GB VRAM. Not recommended.

### Note on BioMistral-AUG-7B
MINERVA's BioMistral-AUG-7B (BioMistral-7B fine-tuned on 1,100 sentences + Mixtral-8x7B augmentation) is **not publicly released**. No HuggingFace checkpoint exists. The base `BioMistral/BioMistral-7B` is public but zero-shot RE quality is poor.

---

## Note on BNER2.0

BNER2.0 refers to the labeled corpus and fine-tuned DistilBERT checkpoint used internally by the MINERVA project. No public HuggingFace model card or checkpoint exists. The MINERVA GitHub (`MGH-LMIC/MINERVA`) contains pipeline code only. The BNER2.0 dataset splits are referenced as coming from "the original BNER2.0 authors" in the MINERVA paper — this remains an internal reference with no public release as of 2025.

---

## Selection Rule
- If precision on microbe/species names is the bottleneck: `OpenMed/OpenMed-NER-SpeciesDetect-BioMed-109M`.
- If runtime is the bottleneck and species recall is acceptable: test `pruas/BENT-PubMedBERT-NER-Organism` again on a larger subset.
- If disease recall is the bottleneck: `raynardj/ner-disease-ncbi-bionlp-bc5cdr-pubmed` (low friction) or `OpenMed/OpenMed-NER-DiseaseDetect-BioMed-335M` (best accuracy).
- For relation extraction: continue Gemini zero-shot for proof-of-concept; fine-tune PubMedBERT on MicrobioRel if compute is available.

## Recommended Benchmark Order
1. Keep batching and disease-first filtering on.
2. Benchmark current defaults on a fixed paper subset.
3. Swap one NER model family at a time.
4. Compare sentence throughput, extracted entity quality, and downstream relation yield.
5. Promote a new default only after that comparison.

## Local Benchmark Snapshot (2026-03-07, 5-paper subset)
| Config | Relation rows | Time |
|--------|--------------|------|
| `bc5cdr` + `d4data/biomedical-ner-all` (current default) | 3 | 10.63s |
| `bc5cdr` + `OpenMed/OpenMed-NER-SpeciesDetect-ElectraMed-33M` | 0 | — |
| `bc5cdr` + `pruas/BENT-PubMedBERT-NER-Organism` | 2 | — |
| `scibert_adapter` + `Francesco-A/...bc5cdr-ner-v1` | 24 (high noise) | — |

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

# Recommended microbe NER upgrade benchmark
python3 src/text_ner_minerva.py \
  --papers artifacts/tmp/papers_microbe_merged_subset5.jsonl \
  --entity-output artifacts/tmp/entity_sentences_openmed_species.jsonl \
  --relation-output artifacts/tmp/relation_input_openmed_species.jsonl \
  --disease-ner-mode bc5cdr \
  --microbe-ner-model-id OpenMed/OpenMed-NER-SpeciesDetect-BioMed-109M \
  --umls-linker off \
  --ner-batch-size 8

# Low-friction disease NER upgrade benchmark
python3 src/text_ner_minerva.py \
  --papers artifacts/tmp/papers_microbe_merged_subset5.jsonl \
  --entity-output artifacts/tmp/entity_sentences_raynardj_disease.jsonl \
  --relation-output artifacts/tmp/relation_input_raynardj_disease.jsonl \
  --disease-ner-mode scibert_adapter \
  --disease-ner-checkpoint raynardj/ner-disease-ncbi-bionlp-bc5cdr-pubmed \
  --disease-ner-base-model raynardj/ner-disease-ncbi-bionlp-bc5cdr-pubmed \
  --microbe-ner-model-id d4data/biomedical-ner-all \
  --umls-linker off \
  --ner-batch-size 8
```
