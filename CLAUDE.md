# Project Claude Memory

## Mission (read first, every session)

Build the **Microbe ↔ Imaging-Phenotype ↔ Disease evidence graph** — `RadiomicFeature` + `BodyCompositionFeature` as the intermediate axis between gut microbiome and disease outcomes. Every edge is gated; every claim cites PMID + sentence + figure.

**End-of-summer deliverables (priority order):**
1. **App** (build all summer) — graph-backed explorer on live Neo4j; read-only scope per Fork 3 (2026-05-21); 6 canonical queries + evidence drill-down (PMID → sentence → figure).
2. **Manuscript** (build all summer) — measured P/R/F1 + Cohen's κ on the 66-row gold set; full gate-chain disclosure.
3. **Video** — end-stage walkthrough, strictly **after** #1 and #2 land. Not a parallel concern.

## Three Governance Tests (apply at every decision)

1. **Novelty — proven, protected, plausible.**
   - *Proven*: measured P/R/F1 + κ; reproducible end-to-end from source PDFs.
   - *Protected*: gates catch hallucination, entity-type errors, proposer/verifier collusion; failure modes named, not silenced.
   - *Plausible*: every edge has PMID + sentence + figure provenance; the graph organizes prior biology, doesn't invent it.
2. **Utility — truly helpful.** Clinician/researcher asks "for disease X, what microbe ↔ imaging-feature evidence exists?" — and the app returns a cited 3-hop traversal in seconds.
3. **Sharp & dense system design.** Every expansion (data lane, extraction gate, app feature) must compound novelty OR utility. No polish without a payload. Positive-system enumeration is the default rule shape: list what's in, not what's out.

## Work-Style Defaults

- **Failure-first.** Start from uncomfortable friction; convert *why* into *how*.
- **Causal-chain explanations**, not pattern-match.
- **Docs-first.** `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/NEXT_STEPS.md` are authoritative. Chat is acceleration only.
- **Loss-averse on irreversible ops.** Reversible work runs unattended; irreversible needs an explicit Reasoning Surface (Knowns / Unknowns / Assumptions / Disconfirmation).
- **No AI co-author / generated-by trailers** in commits, PRs, or issue comments.
- **Conventional Commits** for final commit messages (not `chkpt:` checkpoint format).

## Start Each Session By Reading

- `docs/NEXT_STEPS.md` — current priority and next actions
- `docs/PROGRESS.md` — current state and key decisions

## Critical Guardrails (always apply)

- Text phenotype-to-disease edges: `ASSOCIATED_WITH` only
- Verified figure edges: `CORRELATES_WITH` only
- Bridge hypotheses: audit-only — **never write as graph edges**
- Direct evidence only — no edges from shared-disease-context bridge matches
- Review required before merge for: relation logic, entity cleanup, edge assembly changes

## Read on Demand

- `AGENTS.md` — full operating manual and bounded automation rules
- `docs/REQUIREMENTS.md` — what is being built and acceptance criteria (incl. Summer-2026 overlay)
- `docs/PLAN.md` — staged execution plan + Governing Frame (2026-05-21) + Active Stage
- `docs/RUN_CONTEXT.md` — runtime assumptions, model policy, API env vars
- `docs/RADIOMICS_LAYER_SPECS.md` — graph schema (node/edge types)
- `docs/DESIGN_PRECISION_FIRST_V1.md` — precision-first extraction spec (DRAFT — pending operator approval)
- `docs/NEO4J_RUNBOOK.md` — live Neo4j bring-up + load procedure
- `README.md` — project overview and graph schema
- `pipeline_tracking.md` — long-form artifact tracking
