# Radiomics-First Imaging Phenotype Layer Specifications

## Objective
Build a MINERVA-aligned graph extension that remains radiomics-first but models a broader imaging phenotype space when the literature supports it.

The graph supports these direct-evidence relations:
- `(Microbe)-[:CORRELATES_WITH]->(RadiomicFeature)`
- `(Microbe)-[:CORRELATES_WITH]->(BodyCompositionFeature)`
- `(MicrobialSignature)-[:CORRELATES_WITH]->(RadiomicFeature)`
- `(MicrobialSignature)-[:CORRELATES_WITH]->(BodyCompositionFeature)`
- `(RadiomicFeature)-[:ASSOCIATED_WITH]->(Disease)`
- `(BodyCompositionFeature)-[:ASSOCIATED_WITH]->(Disease)`
- `(RadiomicFeature)-[:MEASURED_AT]->(BodyLocation)`
- `(BodyCompositionFeature)-[:MEASURED_AT]->(BodyLocation)`
- `(RadiomicFeature)-[:ACQUIRED_VIA]->(ImagingModality)`
- `(BodyCompositionFeature)-[:ACQUIRED_VIA]->(ImagingModality)`
- `(ImagingModality)-[:REPRESENTED_BY]->(ImageRef)`
- `(Microbe)-[:POSITIVELY_CORRELATED_WITH]->(Disease)` (RO:0002328, positive polarity via relation extraction)
- `(Microbe)-[:NEGATIVELY_CORRELATED_WITH]->(Disease)` (RO:0002329, negative polarity via relation extraction)

## Node Types
- `Microbe`: taxon-specific entities such as `Fusobacterium nucleatum` or `Akkermansia`.
- `MicrobialSignature`: non-taxon-specific microbiome states such as `dysbiosis`, `alpha diversity`, `beta diversity`, `microbiota composition`, or `intratumoral microbiome`.
- `RadiomicFeature`: IBSI-backed quantitative imaging features such as `glcm_entropy` or `first_order_kurtosis`.
- `BodyCompositionFeature`: imaging-derived phenotype markers such as `skeletal_muscle_index`, `visceral_adipose_tissue`, `myosteatosis`, or `sarcopenia`.
- `Disease`: disease or outcome concepts grounded in paper text.
- `BodyLocation`: anatomical sites where imaging measurements are taken, such as `liver`, `lung`, `colon`, or `abdomen`.
- `ImagingModality`: imaging modalities used to acquire phenotype data, such as CT, MRI, PET, DXA, or ultrasound. Carries DICOM modality codes where applicable.
- `ImageRef`: a verified figure reference produced by the Vision Track pipeline. Stores PMCID, figure ID, panel ID, image path, topology (heatmap/forest_plot), and modality. Completes the professor's chain: `Disease ← Feature → BodyLocation / ImagingModality → ImageRef`.

## Text Track
- Extract IBSI-backed radiomics mentions and a seeded body-composition vocabulary from titles and abstracts.
- Follow upstream MINERVA by downloading PMC full text when a paper has open-access `PMCID`; the primary full-text target is PMC HTML/article text, not PDF.
- Use a deduplicated merged microbiome-side paper corpus before text extraction so strict radiomics, adjacent imaging, and body-composition seeds do not create duplicate downstream work.
- Emit mention-level metadata:
  - `feature_family`
  - `node_type`
  - `ontology_namespace`
  - `claim_hint`
  - `subject_node_type`
  - `subject_node`
- `claim_hint` is descriptive metadata only. It does not override graph relation semantics in the first pass.
- When `full_text_path` exists, the text stages should prefer PMC full text over title/abstract-only content.

## Vision Track
- Vision proposals remain proposal-only until verified.
- Verified figure relations are only emitted when there is a direct subject-to-feature quantitative correlation.
- Default figure relation semantics:
  - `Microbe|MicrobialSignature -[:CORRELATES_WITH]-> RadiomicFeature|BodyCompositionFeature`
- `r_value` is preserved as edge metadata when available.

## Evidence Policy
- Only direct evidence becomes a graph edge.
- Shared-disease co-occurrence within the same paper is not enough to assert `Microbe -> Feature`.
- Within-paper bridge matches are written to an audit artifact as hypotheses and must not be ingested into Neo4j as asserted relationships.

## Relation Semantics
- Text-derived phenotype-to-disease edges use `ASSOCIATED_WITH` in the first refinement pass.
- `PREDICTS` is intentionally not emitted by default.
- Stronger semantics such as predictive, diagnostic, or prognostic language are preserved only in `claim_hint` until they are separately validated.

## Query Strategy
- `microbe_radiomics_strict`: strict radiomics + microbiome/taxa.
- `microbe_imaging_adjacent`: adjacent imaging phenotype language + microbiome/taxa.
- `microbe_bodycomp`: body-composition phenotype + microbiome/taxa.
- `microbe_imaging_phenotype`: broader union of strict radiomics, adjacent imaging phenotype, and body-composition evidence.
- `radiomics_disease_strict`: strict radiomics + disease/outcome language.
- `bodycomp_disease`: body-composition phenotype + disease/outcome language.
- `microbe_radiomics`: deprecated compatibility alias for the broader mixed imaging phenotype query.
- Microbe-side retrieval profiles should exclude review, meta-analysis, and protocol-style papers because they are not direct-evidence extraction targets.
