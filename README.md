# SanoMap Radiomics Layer

SanoMap Radiomics Layer is a MINERVA-inspired extension that adds imaging phenotypes to a literature-derived microbiome knowledge graph. The project focuses on making microbiome, imaging phenotype, and disease evidence usable together, with radiomic and body-composition features acting as explicit intermediate nodes instead of leaving the graph as a microbe-to-disease view only.

## Knowledge Graph Schema

```mermaid
graph LR
    M([Microbe]) -->|CORRELATES_WITH| RF([RadiomicFeature])
    M -->|CORRELATES_WITH| BCF([BodyCompositionFeature])
    MS([MicrobialSignature]) -->|CORRELATES_WITH| RF
    MS -->|CORRELATES_WITH| BCF
    RF -->|ASSOCIATED_WITH| D([Disease])
    BCF -->|ASSOCIATED_WITH| D
    RF -->|MEASURED_AT| BL([BodyLocation])
    BCF -->|MEASURED_AT| BL
    RF -->|ACQUIRED_VIA| IM([ImagingModality])
    BCF -->|ACQUIRED_VIA| IM
    IM -->|REPRESENTED_BY| IR([ImageRef])
    M -->|POSITIVELY_ASSOCIATED_WITH\nNEGATIVELY_ASSOCIATED_WITH| D

    style M fill:#1e40af,color:#fff
    style MS fill:#1e40af,color:#fff
    style RF fill:#065f46,color:#fff
    style BCF fill:#065f46,color:#fff
    style D fill:#7c2d12,color:#fff
    style BL fill:#4c1d95,color:#fff
    style IM fill:#4c1d95,color:#fff
    style IR fill:#92400e,color:#fff
```

## Corpus Metrics

| Metric | Value |
|---|---|
| Papers in corpus | 640 |
| Phenotype mentions extracted | 5,721 |
| ASSOCIATED_WITH edges (phenotype → disease) | 72 |
| Clean disease targets | 30 |
| Microbe-disease edges (signed polarity) | 12 |
| BodyLocation nodes | 18 |
| ImagingModality nodes | 5 |
| ImageRef nodes (Vision Track verified) | 1 |
| Total Neo4j export rows | 161 |
| Automated test checks passing | 156 |

## Graph Policy

The current direct-evidence graph policy is:
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
- `(Microbe)-[:POSITIVELY_ASSOCIATED_WITH / NEGATIVELY_ASSOCIATED_WITH]->(Disease)`

Audit-only lanes that help inspect the extension without asserting new graph facts are:
- direct text subject-to-phenotype candidates in `phenotype_axis_candidates*.jsonl`
- bridge matches that only share disease context in `bridge_hypotheses*.jsonl`

These audit artifacts are not written as asserted graph edges.

## Professor Deliverable Mapping

- Topic:
  microbiome, imaging phenotypes, and disease knowledge graph construction from biomedical literature
- Knowledge map:
  [docs/knowledge_map.md](docs/knowledge_map.md)
- Small tool:
  [docs/explorer/index.html](docs/explorer/index.html)
- Visualization:
  the Mermaid diagram in [docs/knowledge_map.md](docs/knowledge_map.md)
- GitHub work surface:
  code, docs, tests, and handoff state are tracked in this repository
- Living proposal source:
  [docs/proposal/report_sanomap_radiomics_layer.tex](docs/proposal/report_sanomap_radiomics_layer.tex)

## Why This Extension Exists

MINERVA is strong prior work for large-scale microbe-disease extraction, but our project scope is different. This repo is not trying to be a verbatim reproduction of MINERVA. It is extending the upstream idea by making imaging phenotypes explicit and by adding a figure-aware path for quantitative evidence extraction.

That means the repo is trying to answer a different practical question:

How can we connect microbiome findings to imaging-derived phenotypes and then to disease in a graph that stays explainable and reviewable?

## What Is Already Working

- PubMed retrieval and merged corpus preparation
- PMC full-text acquisition for open-access articles
- phenotype text extraction in `src/extract_radiomics_text.py`
- disease and microbe sentence extraction in `src/text_ner_minerva.py`
- relation-input construction in `src/build_relation_input.py`
- relation aggregation in `src/relation_extract_stage.py`
- shared span cleanup in `src/span_cleanup.py`
- phenotype edge assembly and audit artifacts in `src/assemble_edges.py`
- imaging backbone node extraction (BodyLocation, ImagingModality) in `src/assemble_edges.py`
- deterministic heatmap verification in `src/verify_heatmap.py`
- Vision Track end-to-end: figure indexing, VLM proposal, deterministic verification
- local static explorer in `docs/explorer/index.html`
- explicit graph diagram in `docs/knowledge_map.md`

## Current Snapshot

- Corpus: `640` papers (merged baseline + clinical-recall expansion)
- Phenotype mentions extracted: `5,721`
- Disease string quality: `30` clean, clinically meaningful disease targets after expanded stopword filtering
- Graph-ready phenotype-to-disease edges: `72` ASSOCIATED_WITH edges across 30 disease targets
- Graph-ready microbe-disease edges: `9` CORRELATES_WITH_DISEASE pairs (Gemini 2.5 Flash-Lite validated)
- Imaging backbone: `18` BodyLocation nodes, `5` ImagingModality nodes, `75` MEASURED_AT / ACQUIRED_VIA Neo4j rows
- ImageRef: `1` node from validated Vision Track figure (PMC10605408, r=0.95, Prevotella_nigrescens ↔ GLCM_Correlation)
- Total Neo4j export rows: `149`
- Vision Track: 3 figures attempted total — 1 verified (PMC10605408), 2 correctly rejected by deterministic verifier (PMC10176953 dot-plot style, PMC11924647 feature-feature only)
- Validation: `156` pytest checks passing locally

## Current Status

- The full 640-paper corpus has been run through the improved extraction pipeline.
- Disease string quality is substantially improved: sentence-fragment noise removed at two layers (`_detect_disease()` stopword expansion + assembly-side prefix/substring patterns).
- Final disease target set contains 30 clinically meaningful concepts — no sentence fragments, no section-header noise, no technique/method strings.
- The imaging backbone (BodyLocation + ImagingModality) is implemented with vocabulary-expanded coverage (body location 8.1% → 42.8%).
- The ImageRef node type completes the professor's four-part chain: Disease ← Feature → BodyLocation / ImagingModality → ImageRef.
- The Vision Track is validated end-to-end: 1 verified figure, 2 correctly rejected by deterministic verifier.
- The local pytest suite is green at `156 passed`.

## PubMed Harvest Queries

These are the query profiles used to build the corpus. Run via `src/harvest_pubmed.py --query-profile <name>`.

| Profile | Purpose |
|---|---|
| `microbe_radiomics_strict` | Core: radiomic features (GLCM/wavelet/first-order) × microbiome co-mention |
| `microbe_bodycomp` | Body composition (sarcopenia, SMI, VAT) × microbiome |
| `microbe_bodycomp_clinical_recall` | Body composition × microbiome × clinical population |
| `microbe_imaging_adjacent` | Quantitative CT/MRI phenotypes (emphysema, airway, 3D-CT) × microbiome |
| `microbe_imaging_phenotype` | Union of the three microbe-radiomics lanes above |
| `radiomics_disease` | Radiomic features × disease (phenotype-to-disease lane) |
| `bodycomp_disease` | Body composition × disease outcome |
| `bodycomp_disease_association` | Body composition × disease (association + outcome signal) |

Key query blocks (defined in `src/harvest_pubmed.py`):

```
RADIOMICS_FEATURE_BLOCK_STRICT  — GLCM, wavelet, first-order, shape, gldm, LoG,
                                    fractal dimension, quantitative imaging features,
                                    radiogenomics, deep radiomics

BODYCOMP_FEATURE_BLOCK          — sarcopenia, SMI, VAT, SAT, myosteatosis, muscle attenuation,
                                    bone mineral density, hepatic steatosis, PDFF, fat fraction,
                                    intramuscular fat

MICROBIOME_BLOCK                — microbiome, microbiota, gut flora, dysbiosis,
                                    alpha/beta diversity, 16S rRNA, metagenomics,
                                    bacteriome, mycobiome, virome

IMAGING_PHENOTYPE_ADJACENT_BLOCK — quantitative CT, emphysema, airway remodeling,
                                    3D-CT, radiographic phenotype

All primary research only — systematic reviews and meta-analyses are excluded.
```

## Neo4j Graph Queries

After importing `artifacts/neo4j_relationships_microbe_expanded.csv`:

```cypher
// Three-hop path: Microbe → Imaging Phenotype → Disease
MATCH (m)-[:CORRELATES_WITH]->(f)-[:ASSOCIATED_WITH]->(d:Disease)
RETURN m.name AS microbe, labels(f)[0] AS feature_type, f.name AS feature, d.name AS disease
ORDER BY m.name, d.name;

// Which imaging features associate with a specific disease?
MATCH (f)-[:ASSOCIATED_WITH]->(d:Disease)
WHERE toLower(d.name) CONTAINS 'colorectal'
RETURN labels(f)[0] AS node_type, f.name AS feature, d.name AS disease;

// Signed microbe-disease associations with weighted evidence
MATCH (m:Microbe)-[r:POSITIVELY_ASSOCIATED_WITH|NEGATIVELY_ASSOCIATED_WITH]->(d:Disease)
RETURN m.name AS microbe, type(r) AS direction, d.name AS disease,
       r.net_confidence, r.positive_support, r.negative_support
ORDER BY r.net_confidence DESC;

// CT radiomic features measured at a specific body location
MATCH (f:RadiomicFeature)-[:MEASURED_AT]->(bl:BodyLocation)
WHERE bl.name = 'liver'
RETURN f.name AS feature, bl.name AS location;

// Full four-part chain with modality backbone
MATCH (m:Microbe)-[:CORRELATES_WITH]->(f)-[:ACQUIRED_VIA]->(mod:ImagingModality)
MATCH (f)-[:ASSOCIATED_WITH]->(d:Disease)
RETURN m.name, f.name, mod.name, d.name;

// Vision Track verified correlation edge
MATCH (m:Microbe)-[r:CORRELATES_WITH]->(f)
WHERE r.evidence_type = 'vision_verified'
RETURN m.name, f.name, r.r_value, r.confidence, r.pmid;
```

## Prior Work And Boundary

- Prior work:
  MINERVA is the methodological inspiration for large-scale microbiome relationship mining.
- This project:
  a radiomics-first imaging phenotype extension built on that direction, not a claim of exact upstream reproduction.
- Current model policy:
  substitute models are used where upstream-associated checkpoints are not available in this workspace.
- Checkpoint access:
  if professor-mediated or upstream-mediated access later becomes available, the repo should document the model ids and rerun steps, while keeping restricted weights out of Git history.

## BNER Provenance Note

The MINERVA paper states that microbial NER used `BNER2.0` and reused the original authors' public GitHub splits.

Current verification status:
- strongest public candidate lineage:
  `https://github.com/lixusheng1/bacterial_NER`
- checked-in `test_set.iob` in that repo matches MINERVA's reported `2,043` bacterial test entities
- exact release parity is still unconfirmed because the checked-in public corpus totals do not match MINERVA's full reported `BNER2.0` totals

Operationally, this repo treats `lixusheng1/bacterial_NER` as the strongest public candidate source for MINERVA-style microbial NER training data, but not as the exact confirmed upstream release.

## Pipeline At A Glance

1. `src/harvest_pubmed.py`
   harvests literature using split query profiles
2. `src/merge_paper_corpora.py`
   merges the microbiome-side corpora
3. `src/download_pmc_fulltext.py`
   attaches PMC full text when available
4. `src/extract_radiomics_text.py`
   extracts phenotype mentions and feature metadata
5. `src/text_ner_minerva.py`
   extracts disease and microbe-bearing evidence sentences
6. `src/build_relation_input.py`
   joins sentence evidence with phenotype context
7. `src/relation_extract_stage.py`
   predicts and aggregates relation labels
8. `src/index_figures.py`, `src/propose_vision_qwen.py`, and `src/verify_heatmap.py`
   support the figure-analysis path
9. `src/assemble_edges.py`
   emits graph-ready phenotype-to-disease edges plus audit-only phenotype-axis artifacts after review

## Repo Guide

- Project objective:
  [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)
- Active implementation plan:
  [docs/PLAN.md](docs/PLAN.md)
- Completed work and validation:
  [docs/PROGRESS.md](docs/PROGRESS.md)
- Runtime assumptions and constraints:
  [docs/RUN_CONTEXT.md](docs/RUN_CONTEXT.md)
- Next operational handoff:
  [docs/NEXT_STEPS.md](docs/NEXT_STEPS.md)
- Long-form tracking:
  [pipeline_tracking.md](pipeline_tracking.md)

## Next Milestones

- review the current phenotype-axis assembly outputs for semantic graph readiness
- decide whether broad disease targets such as `inflammation` should remain graph-eligible
- promote only reviewed outputs to edge assembly
- expand direct subject-to-phenotype evidence beyond audit-only status only after a stronger validation policy exists

Until then, the repo should be described as a validated proof-of-concept extension with a clear professor-facing deliverable and an explicit upstream-alignment roadmap.
