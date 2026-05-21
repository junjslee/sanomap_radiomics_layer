# Design Spec — Precision-First, MINERVA-Aligned Extraction Instrument (v1)

**Status:** DRAFT for operator review. NOT approved. No implementation, no corpus code, until this doc is approved.
**Date:** 2026-05-19 · **Author lane:** brainstorming → spec (pre-writing-plans)
**Supersedes for the extraction methodology:** the ad-hoc funnel described in PROGRESS pre-2026-05-19. Does not override CLAUDE.md locked guardrails.

---

## 0. Context, problem, estimand

**Problem (from measurement, not assumption).** "The corpus is too small" is, in code, a *funnel-collapse + degenerate-estimand* problem:
- The radiomic retrieval vocab is 7 features (GLCM + first-order + 1 shape). GLRLM/GLSZM/NGTDM/GLDM are harvested but **structurally cannot become nodes**; the Task-2 dense retriever has **zero radiomic concepts** → only 6 `RadiomicFeature` nodes exist.
- The 66-row gold set is pool-starved (8 accepted edges, 13 substring candidates, 3 extended-keyword hits / 187 records) and degenerate for measurement (Pass-1: 71% `not_associated`, 1 positive, 0 explicit-null).

**Estimand (operator-selected).** Every graph edge is high-precision at a stated decision rule; **recall is explicitly NOT claimed**; the graph is validated by **external-DB concordance**; methodology is **anchored to MINERVA** (parent project, same lab) for credibility-by-comparability.

**Governing principle.** Better-characterized > bigger. Prefer learned over heuristic; deterministic logic only as an enumerated precision-safety guard set (§6).

**Hard constraints.**
- No paid API (operator's Gemini key no longer exists). All LLM steps local + free.
- Primary compute = 8 GB M2 Air → **Q8 is the quantization floor** (FP16 4B is infeasible; proven), models run **sequentially** via Ollama.
- Upgrade-and-rerun on larger MGH compute is a **designed-in requirement** (Unit G), not a later nicety.
- CLAUDE.md locked policy preserved verbatim: text phenotype→disease = `ASSOCIATED_WITH`; verified figure edges = `CORRELATES_WITH`; bridge hypotheses = audit-only; direct-evidence only; review-before-merge for relation/entity/edge-assembly changes.

---

## 1. MINERVA alignment summary

| Dimension | MINERVA (verified from repo+paper+supplement) | SanoMap v1 | Rationale |
|---|---|---|---|
| Corpus frame | month-windowed `Date-Create` PubMed harvest; English; PMID dedup; PMC full text when OA; **no publication-type filter** | same harvest mechanics; **+ deliberate exclusion of reviews/meta/protocols** on microbe side | direct-evidence estimand needs primary studies; deviation documented, corpus reported **both ways** for comparability |
| NER / normalization | SciBERT (disease) + DistilBERT-on-BNER2.0 (microbe) + ScispaCy→UMLS CUI | local substitute models **but keep UMLS-CUI normalization** | node identity must be CUI-comparable to MINERVA |
| Relation extraction | fine-tuned BioMistral-AUG-7B, **unanimous-5 self-consistency, discard on disagreement** | unanimous-N within **two independent local families (MedGemma×Qwen)** + cross-family agreement | MINERVA bought bias-control via fine-tuning (infeasible on 8 GB); we substitute cross-family independence; unanimity-or-abstain preserved |
| Calibration | none (entropy soft-check + dual-LLM adjudication only) | isotonic/Platt → calibrated p + reliability/Brier | SanoMap rigor **above** MINERVA; does not replace the unanimity gate |
| Evaluation | accuracy + macro-F1, 5-fold CV, "Coverage (F.C.)"; **no human IAA / κ / CI / sample-size** | Wilson 95% CI + Cohen's κ + power-sized stratified sample **and also** emit MINERVA's metric vocabulary | exceed MINERVA on rigor; stay diff-able on its metrics |
| External validation | 5 DBs: **AMADIS, GMMAD, HMDAD, Disbiome, MDIDB**; UMLS-CUI; 2-hop PARENT fallback; concordance over **overlapping-only**; GPT-4o+Gemini adjudication | mirror the five DBs + method exactly; **substitute human adjudication** (no-API) | comparability is the credibility mechanism; one forced deviation (§8) |
| Graph schema | Microbe/Disease; POSITIVE/NEGATIVE→aggregated `STRENGTH` (`strength_raw`, `strength_IF`); PARENT (NCBI taxonomy / SNOMED-CT) | keep `CORRELATES_WITH`/`ASSOCIATED_WITH` split (2 evidence types vs MINERVA's 1) **+ add `strength_raw`/`strength_IF` to signed microbe→disease edges** | principled extension; strength props make CSVs diff-able vs MINERVA `Data/strengths*.csv` |
| Reproducibility | stage scripts, **no DAG**, hardcoded model/creds | content-addressed DAG + config-swappable model backend | required by upgrade-and-rerun; legitimate improvement, not divergence |

---

## 2. Units A–G

Each unit is independently testable with a declared interface. Implementation of B/C/F and the graph-schema addendum is **review-gated** per CLAUDE.md.

### A · Corpus frame
- **Purpose:** make the corpus a documented census of a named population so a precision estimand has a population.
- **Method:** replicate MINERVA's month-windowed `Date-Create` + English + PMID dedup + PMC-OA full-text rule. Compute the **currently-missing dedup statistic** (overlap rate, not bare 640+376 arithmetic). Emit `frame.json` (query, window, filters, dedup rate, counts, git SHA).
- **Conscious deviation (positive-system):** exclude reviews/meta-analyses/protocols on the microbe side (MINERVA does not). Report corpus size/precision **both with and without** the exclusion so MINERVA comparison is apples-to-apples.
- **Interface:** `frame.json` → consumed by G's DAG.

### B · Retrieve-then-extract
- **B1 retriever (recall-first).** Dense bi-encoder over the full sentence pool. **Must carry the full IBSI feature space** — this is the single highest-leverage frame-safe fix:
  - Add GLRLM/GLSZM/NGTDM/GLDM canonical features (currently context-terms only, never emitted).
  - Add wavelet-/LoG-filtered + fractal canonicals (harvested, no retrieval entry).
  - Expand first-order/GLCM/shape within `IBSI_FEATURES`; for single-ambiguous-token features (energy, contrast, volume, correlation, mean) extend the existing `AMBIGUOUS_ALIASES` + `RADIOMICS_CONTEXT_TERMS` context-gating in lockstep — adding aliases without the guards is the known precision-failure mode.
  - Add `RadiomicFeature` concepts to the dense retriever (`feature_retrieval.py` is currently 100% body-comp → the planned upgrade silently kept the radiomic gap).
  - Sync `_FEATURE_VOCAB` with the documented `EXTENDED_FEATURE_KEYWORDS`.
  - **Rejected from the strict corpus:** harvest-level taxa-block / modality broadenings (coverage-review P6/P7) — they change corpus identity. Allowed only as a **separately-named profile**, never folded into the strict frame (conscious decision, §6).
- **B2 judge (precision-first).** LLM emits a structured verdict under a locked JSON schema with explicit **ABSTAIN**, evidence-span offsets, relation type in the CLAUDE.md vocabulary, self-confidence. UMLS-CUI normalization retained for node comparability.
- **Interface:** `candidate_edges.jsonl {triple, evidence_span, retrieval_score, model_id, raw_conf}`.

### C · Cross-family + unanimity — the primary precision lever
- **MINERVA-faithful core:** unanimous-N self-consistency, **discard on any disagreement** ("accuracy over coverage").
- **SanoMap substitute for fine-tuning (infeasible on 8 GB):** run B2 as **two genuinely independent local families** — **MedGemma-1.5-4B-it** (Google/Gemma lineage, medical) and **Qwen3-4B** (best small-model JSON adherence ~91%) or lighter **Qwen2.5-3B-Instruct** (Alibaba lineage). Q8, **sequential** (load→judge→unload). Each family runs N samples (default N=5, MINERVA-matched); an edge survives only if **unanimous within each family AND both families agree**; else abstain/discard. Each family independently re-locates the evidence span (not re-judging a shared span — the circular-consistency failure the vision audit caught).
- **Comparability output:** report the **discard/coverage rate** (MINERVA Table 2 "Coverage (F.C.)" analog).
- **Interface:** `verified_candidates.jsonl` with per-family per-sample votes + agreement structure.

### D · Calibration — rigor layer above MINERVA
- MINERVA has no calibration; this **adds**, does not replace C. Fit isotonic (Platt fallback) from {per-family confidence, agreement structure, retrieval score} to empirical P(edge correct) on E's sample. Output calibrated p, reliability diagram, Brier score, and the **decision rule** τ\* achieving the target precision. Graph becomes queryable by precision level.
- **Default target precision = 0.90** (operator override at review; ≥0.95 is the stricter alternative).
- **Honest degradation:** if the precision sample is too thin for per-relation-type calibration, fall back to one global calibrator and state it.

### E · Precision evaluation — the only annotation burden
- Power-sized **stratified sample of predicted-positives** (by relation type). Task = binary "is this asserted edge correct given its cited span?" — escapes the degenerate 6-class scheme; single-annotator-feasible.
- **Sizing:** Wilson 95% CI; at p≈0.90, half-width ±0.05 → n ≈ 138 per stratum (`n = 1.96²·p·(1−p)/e²`). Operator picks the half-width at review.
- **Rigor kept (exceeds MINERVA):** Wilson CI, Cohen's κ (intra-annotator, **secondary stability check only — not headline, not gated by the 2026-05-21 window**), Landis-Koch reference.
- **Comparability added:** also emit 5-fold accuracy + macro-F1 + full-confidence coverage % so a reviewer can place SanoMap directly against MINERVA Table 2.
- **Interface:** `precision_eval.json` (per-stratum precision + Wilson CI + MINERVA-vocab metrics).

### F · External-DB concordance — independent validation
- **Mirror MINERVA exactly** (the comparability is the point):
  - Same five DBs: **AMADIS, GMMAD, HMDAD, Disbiome, MDIDB**.
  - UMLS-CUI link both sides (ScispaCy); per-DB relation→{positive,negative,na} maps as MINERVA's.
  - Exact-CUI match in graph; else **2-hop `PARENT*2` hierarchical fallback** on both microbe (NCBI taxonomy) and disease (SNOMED-CT).
  - Direction from signed `strength_raw`/`strength_IF`.
  - Report the **four ratios verbatim**: entity coverage %, relationship-overlap %, **directional concordance % (denominator = overlapping relations only)**, unsure %; plus the IF-weighted variant.
  - Characterize **novel (not-in-DB) edges** as the discovery contribution; concordance reported as *corroboration*, never as recall (novel ≠ false).
- Imaging-relevant DBs may be added **only as a clearly-labeled extension**, never replacing the five.
- **Forced deviation (no-API) → see §8.**
- **Interface:** `concordance_report.json` (the four ratios per DB + novel-edge characterization).

#### Graph-schema addendum
Add MINERVA-style `strength_raw` (Σ ±1 per supporting paper) and `strength_IF` (Σ sign·log10(impact_factor)) as **properties on the existing** `POSITIVELY_/NEGATIVELY_CORRELATED_WITH` microbe→disease edges. **Open item (pre-F):** MINERVA's exact default-IF constant for papers with no impact factor was not captured by the methodology study — read MINERVA `graph_creator.py` to confirm the constant before implementing F, or numbers will not diff against `Data/strengths*.csv`. No new edge type; CLAUDE.md vocabulary unchanged. Makes SanoMap microbe-side CSVs diff-able against MINERVA `Data/strengths*.csv`.

### G · Reproducible DAG + provenance — designed-in
- One content-addressed pipeline frame→corpus→retrieve→extract→verify→calibrate→graph. Model backend is a **config field** (Ollama model id + quant level) → MGH-hardware upgrade is a **rerun, not a rebuild**.
- Keep MINERVA's stage decomposition + Neo4j + flat-CSV interchange contract (diff-able vs MINERVA `Data/`). The existing `build_graph_export.py` + `manifest.json` is the seed.
- Manifest carries: corpus vintage, `frame.json` hash, model ids+quant, N + agreement policy, calibration params + τ\*, concordance state, git SHA. Structurally supersedes the divergent-vintage class (9 `verified_edges*` / 5 `neo4j_relationships*`).

---

## 3. Pilot gate — go/no-go BEFORE building B–G

- **Step-0 (fit verification, the one inferred assumption):** `ollama pull` MedGemma-1.5-4B-it @ Q8; run ~5 schema-constrained judge prompts; confirm it loads AND honors the JSON+ABSTAIN schema within 8 GB on realistic RE context. Compare Qwen on identical prompts.
- **Step-1 (method disconfirmation):** run the cross-family unanimity pair on the **already-labeled data** (8 accepted edges + 66-row gold).
- **Disconfirmation condition (crisp, project-grounded):** at the §2-D default target precision (0.90), the pilot **fails** if the cross-family-unanimous survivors either (i) no longer retain **all 3 thesis-load-bearing three-hop closers** (Ruminococcus→sarcopenia, Peptostreptococcus→SMI, Eubacterium→VAT), **or** (ii) retain **< 5 of the 8** current accepted_edge candidates. On failure → fallback ladder: (a) raise N / tighten abstention, accept lower coverage; (b) defer to MGH unquantized compute (G makes this a rerun, not a rebuild); (c) consciously scope the graph smaller and state it in Limitations. Quantify *before* investing in B–G.

---

## 4. Failure-mode design (failure-first)

- Circular shared-evidence → independent per-family evidence re-location (C).
- Calibration overfit on a thin sample → CV + Brier + global-calibrator fallback (D).
- Curated-DB incompleteness/bias → concordance = corroboration, not recall; novel ≠ false; named limitation (F).
- LLM nondeterminism → temperature 0, pinned model ids in manifest, schema-validated output, **ABSTAIN-on-parse-failure (fail-closed = precision-safe)**.
- Local-model weakness → the §3 pilot gate is the explicit circuit-breaker; abstention absorbs residual weakness as lower coverage, not wrong edges.

---

## 5. Explicitly excluded (YAGNI vs the estimand)

No recall denominator; no second annotator for the headline; no balanced multiclass κ as headline; no dependence on the 2026-05-21 window for the main result; no corpus growth for v1 (frame fixed + characterized; growth = documented v2 lever); no paid API anywhere.

---

## 6. Conscious rule-shape choices (operator's positive/negative-system principle)

- **Corpus frame:** positive-system (only direct-evidence publication types) — deliberate deviation from MINERVA's negative-system (all types). Documented; corpus reported both ways.
- **Retrieval expansion:** P1–P5 IN (frame-safe, recovers from existing corpus); P6/P7 OUT of the strict corpus (harvest-identity change → separate named profile only).
- **Heuristics:** learned-by-default. Deterministic logic permitted only as this enumerated precision-safety guard set, each listed here for sign-off: (1) JSON-schema validation of judge output; (2) evidence-span-exists check; (3) the existing vision pre-verifier gates (caption/colorbar/range-sanity) retained for the figure track. Nothing else deterministic in the selection path.

---

## 7. Verification & testing

- Unit tests per bounded unit with mocked model clients; maintain the 321-suite discipline, zero regression.
- Golden-file DAG test on a frozen mini-corpus.
- Calibration math tested against a synthetic dataset of known reliability.
- Concordance tested against a tiny fixture DB; the four ratios asserted.
- MINERVA-comparability check: the metric-vocabulary emitter (5-fold acc/F1, coverage %, four concordance ratios) is itself unit-tested.

---

## 8. OPEN DECISION — operator review required

**No-API adjudicator substitute (Unit F).** MINERVA adjudicates DB-conflict labels with GPT-4o + Gemini 1.5 Pro and reports their %-agreement. SanoMap cannot (no paid API). Options:

1. **Human adjudication of the disagreement set (recommended).** Precision-first makes the disagreement set small; a human verdict is *stronger* than LLM adjudication, and it is **literally MINERVA's own stated future work** → an improvement, not a regression. Cost: bounded annotator time; the known tech-not-clinical-annotator caveat applies.
2. Local cross-family pair (MedGemma×Qwen) as adjudicator. Zero cost; but same models extract *and* adjudicate → circularity risk (the failure the vision audit caught).
3. Raw concordance ratios only, no adjudication layer + a human spot-check sample. Most honest, least comparable to MINERVA's Table 1 adjudication column.

Recommendation: **Option 1**, with the raw ratios (Option 3) reported alongside regardless. Awaiting operator decision; spec implementable on Option 1 default.

---

## 9. Sequencing

Pilot gate (§3) → A + B1 (radiomic retriever fix — highest frame-safe leverage) → B2/C (cross-family unanimity) → E (precision gold + calibration data) → D (calibrate) → F (concordance; finalized post-pilot, anchored to MINERVA) → G (hardened). F and G interfaces are specified now; F's adjudicator resolves at §8.

---

## Appendix · MINERVA provenance (VERIFIED vs INFERRED)

**VERIFIED** (read from cloned repo + paper + supplement): corpus query/month-windowing/dedup; SciBERT+DistilBERT-on-BNER2.0+ScispaCy-UMLS NER; BioMistral-AUG-7B + 3-class collapse + 1,100-sentence ref-[34] gold + 5-fold CV; **unanimous-5 discard gate**; no calibration; the **five external DBs**; exact concordance formulas + 2-hop PARENT fallback + overlapping-only denominator; absence of human IAA/κ/CI; Neo4j + `STRENGTH`/`strength_raw`/`strength_IF` + PARENT schema; no DAG, hardcoded model/creds.
**INFERRED:** 2013-vs-2014 corpus start (code says 2013, paper says 2014; not load-bearing); GMMAD≡GMDAD (high confidence from repo folder); production path = strict `llm_classifier.py` not the `_withUnc` entropy variant (from docstring + paper p9; strict file not line-read).
**Open MINERVA items (non-blocking):** exact strict-path sample-N/tie-break (read `llm_classifier.py`); whether `src/` already does N-sample unanimity (team check, = §3 work).
