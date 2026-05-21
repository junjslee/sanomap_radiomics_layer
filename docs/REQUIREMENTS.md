# Requirements

## Objective
- Finish a MINERVA-aligned radiomics-first imaging phenotype extension that can emit graph-ready direct-evidence relations.
- Preserve the current evidence policy:
  - verified subject-to-feature figure edges use `CORRELATES_WITH`
  - text-derived phenotype-to-disease edges use `ASSOCIATED_WITH`
  - bridge hypotheses remain audit-only and are never ingested as asserted graph edges

## Summer-2026 Operating Objective (overlay, 2026-05-21)

The v1 Objective above remains the layer-level acceptance criterion. The summer-2026 operating objective overlays it with deliverable framing.

- **What is being built.** The **Microbe ↔ Imaging-Phenotype ↔ Disease evidence graph** — `RadiomicFeature` + `BodyCompositionFeature` as the intermediate axis between gut microbiome and disease. Every edge gated; every claim cites PMID + sentence + figure.
- **End-of-summer deliverables, priority order:**
  1. **App** — graph-backed explorer on live Neo4j; read-only scope per Fork 3 (2026-05-21); 6 canonical queries + evidence drill-down (PMID → sentence → figure).
  2. **Manuscript** — measured P/R/F1 + Cohen's κ on the 66-row gold set; full gate-chain disclosure.
  3. **Video** — end-stage walkthrough, sequenced strictly after App + Manuscript.
- **Three governance tests applied at every decision** (detail in `docs/PLAN.md` → Governing Frame (2026-05-21)):
  1. **Novelty — proven, protected, plausible.** Proven = measured P/R/F1 + κ, reproducible from source. Protected = gates catch hallucination, entity-type errors, proposer/verifier collusion; failure modes named, not silenced. Plausible = every edge cites PMID + sentence + figure; the graph organizes prior biology, doesn't invent.
  2. **Utility — truly helpful.** Cited 3-hop traversal answers "for disease X, what microbe ↔ imaging-feature evidence exists?" in seconds.
  3. **Sharp & dense system design.** Every expansion compounds novelty OR utility. Positive-system enumeration is the default rule shape.
- **Acceptance overlay** (in addition to the v1 acceptance criteria below):
  - `docs/explorer/index.html` is graph-backed on live Neo4j with the 6 canonical queries + evidence drill-down + the 3 thesis 3-hop closers as featured demos.
  - Cohen's κ ≥ 0.80 (binary collapse) with binary P/R/F1 + 95% Wilson CI written into the `.tex`.
  - A video walkthrough produced from the working app + final manuscript counts.

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
