# Requirements

## Objective
- Finish a MINERVA-aligned radiomics-first imaging phenotype extension that can emit graph-ready direct-evidence relations.
- Preserve the current evidence policy:
  - verified subject-to-feature figure edges use `CORRELATES_WITH`
  - text-derived phenotype-to-disease edges use `ASSOCIATED_WITH`
  - bridge hypotheses remain audit-only and are never ingested as asserted graph edges

## Users Or Stakeholders
- Research and data-engineering workflows that need graph-ready microbiome, phenotype, and disease evidence.
- Future local or GPU agents that need a stable handoff and operating model.

## Constraints
- Local machine is an Apple M2 MacBook Air with 8 GB unified memory, so large local model-backed relation extraction is not the target execution path.
- Upstream MINERVA-associated checkpoints are not fully available in this workspace, so substitute models are currently used.
- The current graph scope is intentionally hybrid:
  - strict `RadiomicFeature` core
  - `BodyCompositionFeature` support
  - `MicrobialSignature` support
- Subject and disease span quality must improve before merged relation outputs are promoted to graph edges.

## Non-Goals
- Do not claim full upstream parity before a real GPU-backed or hosted model-backed relation run exists.
- Do not emit graph edges from within-paper bridge matches that only share disease context.
- Do not optimize for local heavy-model execution on this Mac as the final production path.

## Acceptance Criteria
- Rebuild merged text-stage artifacts on the full-text-aware merged corpus.
- Run true model-backed merged relation extraction on GPU or hosted inference.
- Add or apply cleanup rules that remove malformed subject and disease spans before edge promotion.
- Re-audit merged accepted relations and confirm reduced junk spans.
- Run edge assembly and validate:
  - `artifacts/verified_edges.jsonl`
  - `artifacts/verified_edges.csv`
  - `artifacts/neo4j_relationships.csv`
  - `artifacts/bridge_hypotheses.jsonl`

## Tech Stack
- Python pipeline in `src/`
- JSONL artifacts plus JSON Schema validation
- PubMed retrieval plus PMC full-text acquisition
- NER and relation extraction with substitute biomedical models
- Neo4j-oriented edge export artifacts
