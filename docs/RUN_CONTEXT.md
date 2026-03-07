# Run Context

Read this file at the start of implementation work.

## Model Availability Note
- Some model weights and checkpoints used in or associated with the upstream MINERVA paper are not yet available in this workspace.
- Because of that, this repository currently uses default substitute models to get a proof-of-concept end-to-end pipeline running first.
- This is intentional. The immediate goal is pipeline completion and evidence flow validation, not final model parity.

## Current Substitute Model Policy
- Relation extraction targets `BioMistral/BioMistral-7B` when model-backed text generation is available.
- Data augmentation currently uses `mistralai/Mixtral-8x7B-v0.1`.
- Microbe NER currently uses `d4data/biomedical-ner-all`.
- Disease NER currently uses `allenai/scibert_scivocab_uncased` with fallback to `en_ner_bc5cdr_md`.
- Vision proposal currently uses `Qwen/Qwen2.5-VL-7B-Instruct`.

## Current Workspace Constraint
- This workspace is currently CPU-only (`cuda_available = false`).
- For merged proof-of-concept relation extraction runs in this workspace, `BioMistral/BioMistral-7B` text generation is not a practical default execution path.
- When that constraint matters, record explicitly whether the run used the intended text-generation backend or the `heuristic` backend.

## Interim Candidate Models
- If microbe NER quality is the priority, evaluate `pruas/BENT-PubMedBERT-NER-Organism`.
- If microbe NER speed is the priority, evaluate `OpenMed/OpenMed-NER-SpeciesDetect-ElectraMed-33M`.
- If disease NER coverage is the priority, evaluate `pruas/BENT-PubMedBERT-NER-Disease`.
- If disease NER should stay BC5CDR-oriented, evaluate `Francesco-A/BiomedNLP-PubMedBERT-base-uncased-abstract-bc5cdr-ner-v1`.
- Do not switch relation extraction or vision defaults just because they are newer. The current bottleneck is the text NER stage.

## Why This Matters
- Do not describe the current model stack as exact upstream parity.
- Describe it as a proof-of-concept substitute stack aligned with upstream methodology.
- When the intended upstream weights/checkpoints become available, the pipeline should be re-run with those models and re-evaluated.

## Query Assessment Snapshot
- The split query design is correct for the current hybrid scope.
- `microbe_radiomics_strict`, `microbe_imaging_adjacent`, and `microbe_bodycomp` are appropriately separated.
- Keep `microbe_radiomics_strict` as the explicit-radiomics precision lane.
- Use `microbe_imaging_adjacent` for adjacent imaging phenotype papers that do not say `radiomics`.
- The current merged microbe-side corpus is mostly imaging phenotype/body-composition, not mostly strict radiomics.
- The main current limitation is that the disease-side queries are more tuned to predictive/prognostic language than to general association language.
- For proof of concept, keep the current queries stable unless recall becomes a blocker.

## NER Optimization Snapshot
- Prefer batching and inference reduction before large model swaps.
- `src/text_ner_minerva.py` now chunks long sentences, batches NER calls, and runs microbe NER only after disease-positive sentence filtering.
- Revisit model substitution only after checking whether those safer runtime optimizations are enough.
