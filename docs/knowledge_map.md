# Knowledge Map

This repository builds the microbiome + imaging phenotype portion of the SanoMap knowledge graph. All extracted artifacts remain organized around the same direct-evidence policy that MINERVA uses: only verified figure edges are promoted to `CORRELATES_WITH`, and only text-derived phenotype-to-disease edges are admitted as `ASSOCIATED_WITH` while bridge hypotheses stay in audit-only lanes.

The following Mermaid diagram makes the current schema explicit:

```mermaid
graph LR
  Microbe -->|CORRELATES_WITH| RadiomicFeature
  Microbe -->|CORRELATES_WITH| BodyCompositionFeature
  MicrobialSignature -->|CORRELATES_WITH| RadiomicFeature
  MicrobialSignature -->|CORRELATES_WITH| BodyCompositionFeature
  RadiomicFeature -->|ASSOCIATED_WITH| Disease
  BodyCompositionFeature -->|ASSOCIATED_WITH| Disease
  BridgeHypothesis[Bridge Hypotheses<br/>(audit-only)]
  BridgeHypothesis -.-> Disease
```

Each edge is grounded in a particular pipeline stage:

- `Microbe`/`MicrobialSignature` candidates come from the MINERVA-aligned NER + cleanup pipeline.
- `RadiomicFeature` and `BodyCompositionFeature` nodes originate in the radiomics text extractor plus vision verification stages.
- `Disease` mentions are filtered through the shared span cleanup helper before entering the relation extractor.
- `BridgeHypothesis` rows are retained in audit artifacts but explicitly marked as `not_for_graph_ingestion` so they never become asserted edges.
