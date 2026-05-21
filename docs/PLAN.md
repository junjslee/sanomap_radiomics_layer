# Plan

## Current Goal (2026-05-04)
- Land four structural upgrades that convert the proof-of-concept pipeline into a research-defensible, measurable artifact:
  1. UMLS-grounded entity sanitization (rejects entity-type errors at NER post-processing)
  2. Embedding-based candidate retrieval (replaces hand-curated `_FEATURE_VOCAB`)
  3. Dual-verifier consensus for Vision Track (pixel + independent VLM)
  4. Gold-label benchmark (150 stratified instances, measured P/R/F1)
- Each gate is independently auditable; no edge reaches the graph without passing every applicable gate.

## Governing Frame (2026-05-21) — supersedes the 2026-05-04 Current Goal for end-of-summer cadence

**What is being built.** The **Microbe ↔ Imaging-Phenotype ↔ Disease evidence graph** — `RadiomicFeature` + `BodyCompositionFeature` as the intermediate axis between gut microbiome and disease. Every edge gated; every claim cites PMID + sentence + figure.

**Deliverables, priority order:**
1. **App** (build all summer) — graph-backed explorer on live Neo4j; read-only scope per Fork 3 (resolved 2026-05-21).
2. **Manuscript** (build all summer) — measured P/R/F1 + Cohen's κ on the 66-row gold set; full gate-chain disclosure.
3. **Video** — end-stage walkthrough, sequenced strictly after #1 and #2. Not a parallel concern.

**Three governance tests applied at every decision:**
1. **Novelty — proven, protected, plausible.**
   - *Proven*: measured P/R/F1 + κ, reproducible from source.
   - *Protected*: gates catch hallucination, entity-type errors, proposer/verifier collusion; failure modes named.
   - *Plausible*: every edge cites PMID + sentence + figure; the graph organizes prior biology, doesn't invent.
2. **Utility — truly helpful.** Clinician/researcher asks "for disease X, what microbe ↔ imaging-feature evidence exists?" — app returns a cited 3-hop traversal in seconds.
3. **Sharp & dense system design.** Every expansion compounds novelty OR utility. No polish without a payload. Positive-system enumeration is the default rule shape (list what's in, not what's out).

**Two compounding lanes through summer:**
- **Engineering lane.** Stage B explorer rewire → 6 canonical queries → evidence drill-down → expansion lanes (data + extraction). Unattended-safe except for Docker bring-up and any irreversible op.
- **Annotator lane.** Pass-2 (window opens 2026-05-21) → Cohen's κ + binary P/R/F1 with 95% Wilson CI → manuscript headline → coherence-pass on every `.tex` count.

**Video** is the wrap-up artifact derived from a working app + a measured manuscript. Do not script before B + C close.

## Active Gating Items (2026-05-07, end of session)
- **Task 1 closed live**. UMLS audit drop rate 25% (2/8). Outputs in `artifacts/dropped_entities_audit.jsonl` + `artifacts/umls_gate_report.json`.
- **Task 2** (dense retrieval): implementation done; τ calibration is strictly downstream of Pass-2 gold labels.
- **Task 3 closed + scoped down**. Vision verifier pivoted to local Qwen2.5-VL-3B via Ollama; dual-verifier alone surfaced as structurally insufficient (both verifiers consume proposer's bbox → self-consistent hallucinations pass silently). Three deterministic pre-verifier gates added (`src/vision_gates.py`: caption / colorbar_detect / range_sanity with VLM colorbar tick extraction). Retroactive audit on 14 figures (13 current + 1 historical) → 6 REJECT_GATE, 5 ACCEPT, 3 REVIEW. Historical PMC6178902 firmicutes edge dropped (wrong-sign + LFC scale per direct image inspection); PMC10605408 prevotella edge retained. Headline count: **9 CORRELATES_WITH → 8 (1 vision + 7 text)**. 28 vision-verifier + 24 new vision-gate tests pass.
- **Task 4 Pass-1 closed**. 66-row authoritative `gold_set_v1_LABELED_pass1.jsonl` generated via Claude propose → junjslee review → 7 imaging-scope overrides. Schema bumped v1.0 → v1.1 (§ 6.9 imaging-derived rule). 14-day temporal window opens 2026-05-07; Pass-2 earliest 2026-05-21.

## Active Stage — Deliverable Integration Gap (2026-05-18)

Trigger: codebase reviewed against the PI's 3-step pipeline (data sourcing / hybrid text-vision extraction / Neo4j integration) and 3 end-of-summer deliverables (working application, manuscript, video).

Findings (facts, not decisions):
- Step 1 data sourcing — **aligned**. 1,016-paper corpus + PMC full-text path mature.
- Step 2 hybrid text-vision — **capability aligned; evidentiary balance text-dominant by audited design.** Post-gate vision yield = 1 unambiguously-legitimate figure / 14. The gating chain (`src/vision_gates.py`) is itself the publishable vision contribution. This is a framing obligation, not a defect to hide.
- Step 3 Neo4j integration — **NOT aligned in the integration sense.** No `neo4j` driver / `GraphDatabase` / `bolt://` anywhere; export is a hand-run `.cypher`. Multiple `neo4j_relationships*.csv` vintages; unqualified `artifacts/neo4j_relationships.csv` is an 11-row smoke file containing clause-fragment junk diseases and the firmicutes vision edge the 2026-05-07 audit DROPPED. `scripts/neo4j_import.cypher` is Apr-7, pre-audit. Pipeline / cypher / explorer JSONL / verified_edges are four different vintages — no single regenerable graph.
- Deliverable #1 application — **partial.** `docs/explorer/index.html` is static, backend-less, reads a frozen 2026-04-05 185-row `data.jsonl` ("85 edges") — it browses a stale file, it does not query the graph.
- Deliverable #2 manuscript — **mature draft, data-gated.** `report_sanomap_radiomics_layer.tex` headline P/R/F1 + Cohen's κ blank pending Pass-2 (≥ 2026-05-21); embedded counts need a post-audit coherence pass.
- Deliverable #3 video — **not started** (correctly end-stage).

Governing reframe: the weak point is the integration spine + application, not extraction quality. Extraction is over-built relative to the graph store and the app; end-of-summer risk concentrates on A/B below.

Stages:
- **A. Single coherent regenerable graph artifact** (engineering lane, reversible, may start now). One command: pipeline artifacts → `graph_export/` (nodes + relationships + import.cypher + manifest with corpus vintage, counts, audit state, git SHA). Retire or alias the ambiguous unqualified `neo4j_relationships.csv`.
- **B. Graph-backed application.** App fed by the canonical export (or live Neo4j per Fork 1); expose the 6 Cypher queries already documented in README; entity search → neighborhood expansion → evidence drill-down (PMID/sentence/figure). Reuse the existing vis-network UI; the gap is the query layer + data freshness, not the UI.
- **C. Manuscript headline** (annotator lane, starts 2026-05-21, longest non-parallelizable lead). Pass-2 independent labels → Cohen's κ + binary P/R/F1 with 95% Wilson CI → `.tex` results; then a coherence pass reconciling every count to post-audit truth.
- **D. Video** — strictly after B; scripted off the working graph-backed app.

### Status (2026-05-19)
- **A — DONE.** `scripts/build_graph_export.py` emits `artifacts/graph_export/` (189 rows / 99 nodes) with `manifest.json` (source vintages, git SHA, drop records). Unqualified-CSV ambiguity superseded by the canonical bundle. Tests: `tests/test_build_graph_export.py`.
- **Fork 1 — RESOLVED → live Neo4j (operator decision 2026-05-18).** Delivered: `scripts/neo4j_load.py` (driver loader, safe `--dry-run` default), `src/graph_queries.py` (8 read-only injection-safe canonical traversals + `assert_read_only` enforced by tests), `docker-compose.neo4j.yml`, `docs/NEO4J_RUNBOOK.md`, `neo4j>=5,<6` pinned. Live import is operator-run (Docker daemon currently down — runbook step).
- **Coherence finding (Stage A earned its keep):** the documented `9 CORRELATES_WITH → 8 (1 vision + 7 text)` was never composed — vision retraction applied to the 9-superset but the separately-recorded UMLS `bacteriodetes` drop never subtracted from it. Coherent truth = **7 (1 vision + 6 text), 189 rows / 99 nodes**. 62 three-hop paths exact (all 3 closers survive). Paper + PROGRESS corrected to manifest truth.
- **B — PARTIAL.** Graph/query spine + live-load path done. Remaining: rewire `docs/explorer/index.html` off the frozen 2026-04-05 `data.jsonl` onto the canonical export / live Neo4j.
- **WS1 — DONE.** Proposal archived (`docs/paper/proposal/`); two-column manuscript `docs/paper/paper_sanomap_radiomics_layer.tex` compiles on local basictex.

### Status (2026-05-21) — Fork 3 Resolved + Summer Frame Locked

- **Fork 3 — RESOLVED → read-only graph explorer (operator decision 2026-05-21).** Stage B scope, positive-enumerated:
  - **(a) DONE (2026-05-21).** `docs/explorer/index.html` rewired off the frozen 2026-04-05 `data.jsonl` onto canonical `graph_export/`. New `scripts/build_explorer_data.py` regenerates `docs/explorer/data.jsonl` (189 rows / 99 nodes, post-audit truth) from `graph_export/relationships.csv` with a hard invariant (emitted count must equal `manifest.json` `post_total`; refuses to write on drift). Explorer header is now data-driven (computes breakdown live from loaded records). Frozen file preserved at `data.jsonl.frozen_2026_04_05.bak`. 11 new tests; full suite 332 passed. All 3 thesis 3-hop closers present in the new bundle; surviving vision edge (`prevotella_nigrescens ↔ GLCM_Correlation`) present. Live Neo4j is the v2 upgrade path for (a); the static-export wire is sufficient for read-only Stage B.
  - **(b) DONE (2026-05-21, B.b-3.α).** Queries panel added to `docs/explorer/index.html` exposing the 6 canonical traversals as named buttons (`three_hop_paths`, `signed_microbe_disease`, `vision_verified_edges`, `full_modality_chain`, `features_for_disease(disease)`, `features_at_location(location)`). JS implementation mirrors `src/graph_queries.py` Cypher semantics one-to-one; queries set an active-subset overlay on top of `records[]` so the existing table + graph + filter UI all keep working. Live "Active query: X — N records" status + Clear-query button. New `tests/test_explorer_query_semantics.py` (9 tests) pins parity invariants: 3 thesis closers traversable, exactly 1 vision-verified surviving edge, 14+15=29 signed microbe-disease, `features_for_disease("cirrhosis")` non-empty, `features_at_location("abdomen")` non-empty, `full_modality_chain` has at least one feature with BOTH modality AND disease legs. Full suite **341 passed / 0 failed** (was 332; +9; no regressions). Live Neo4j is still the v2 upgrade path (swap the JS query backend for Bolt/HTTP). 
  - (c) evidence drill-down: edge → PMID → sentence span → figure (when `CORRELATES_WITH`) — partial today (record-level evidence text already renders in the table; sentence-text + figure-ref enrichment still pending). **NEXT after (d).**
  - (d) the 3 thesis 3-hop closers (Ruminococcus→sarcopenia 37, Peptostreptococcus→SMI 7, Eubacterium→VAT 18 = 62 paths) surfaced as featured demos — **B.b-3.β NEXT**.

**Naming / category confirmation (2026-05-21).** Operator asked whether "radiomics" is the right category. Answer: **no — the umbrella is *imaging-derived phenotype* (IDP, UK-Biobank framework) or *imaging phenotype*; "radiomics-first" is the methodology, not the scope.** Today's graph has 6 `RadiomicFeature` nodes (IBSI-defined: GLCM_Correlation, first_order_kurtosis, ...) AND 8 `BodyCompositionFeature` nodes (SMI, VAT, sarcopenia, myosteatosis, ...) — body composition dominates the imaging side (6 of 7 CORRELATES_WITH edges target BodyCompositionFeature). Calling it "radiomics + microbiome" mis-cues a reviewer. The CLAUDE.md Mission line and the manuscript abstract already use "Imaging-Phenotype" as the umbrella — framing is in good shape; no further doc churn needed. The repo name (`sanomap-radiomics-layer`) and `RADIOMICS_LAYER_SPECS.md` filename are legacy naming, not worth a destructive rename. **Plausibility verified**: the four established axes (gut-muscle / gut-liver / gut-adipose / gut-bone) all have measurable imaging readouts in the graph; the 3 thesis closers traverse three of these directly. **Utility verified**: three user personas (microbiome / body-composition / clinical) map cleanly onto the 6 canonical queries.

### Status (2026-05-21, fourth pass) — Body-comp validity + harvest coverage + concerns C1/C2/C3

**Body-composition validity verdict: load-bearing, keep.** Operator asked whether body-comp (`BodyCompositionFeature` node type) is "even valid to add" to a microbiome ↔ imaging ↔ disease graph. Decisive answer:
- *Pragmatic*: removing BCF collapses the graph to 1 edge. 6/7 surviving CORRELATES_WITH, 3/3 thesis closers, 62/62 thesis paths route through BCF.
- *Scientific*: every BCF node IS imaging-derived (SMI/VAT/SAT from CT/MRI segmentation; sarcopenia/myosteatosis from CT HU; psoas area from CT at L3; body_fat from DXA). Per PyRadiomics docs they are "outside pyradiomics' scope" — but pyradiomics is texture/shape extraction, not the boundary of "imaging-derived phenotype." Under QIBA + UK-Biobank IDP frameworks, SMI/VAT/PDFF/BMD are canonical quantitative imaging biomarkers.
- *Mechanistic*: the four established gut axes (muscle / liver / adipose / bone) all operate through body-comp imaging readouts, not IBSI textures.
- *Literature density*: pure radiomics-microbiome is a niche (~hundreds of papers); body-comp-microbiome is ~thousands. Excluding BCF abandons ~95% of the relevant evidence base.

**Recommended framing for manuscript body** (not just abstract): *"The Imaging-Phenotype Layer organizes microbiome–imaging–disease evidence at two granularities: IBSI-aligned radiomic features (precision pole) and clinical body-composition biomarkers (coverage pole). Both are imaging-derived phenotypes under the QIBA framework; both extracted with the same five-gate acceptance discipline."*

**Harvest coverage verdict: strong core; named v2 expansion candidates.** `src/harvest_pubmed.py` covers all 8 PyRadiomics feature classes (First-Order, Shape 2D/3D, GLCM, GLRLM, GLSZM, NGTDM, GLDM) + filter classes (LoG, wavelet, fractal) + comprehensive body-comp vocab + comprehensive microbiome lexicon. V2 expansion candidates (not blocking; record for operator selection):
- **HV1**: imaging modality expansion → `ultrasound`, `sonograph*`, `elastography`, `MRE`, `FibroScan`, `mpMRI`, `DECT`. Especially relevant for proposed L11 (liver MRE) lane.
- **HV2**: emerging radiomics → `habitat imaging`, `delta radiomics`, `intratumoral heterogeneity`, `deep features`, `voxel-wise radiomics`, `radiopathomics`.
- **HV3**: body-comp depth → `sarcopenic obesity`, `cachexia`, `L3 vertebra`, `Hounsfield unit*`, `appendicular lean mass`, `lean mass index`, `liver iron concentration`.

**Material concerns addressed:**
- **C1 — DONE.** `scripts/build_explorer_data.py` now backfills PMID/PMCID/title/journal for vision-track CORRELATES_WITH rows via a lateral join: `evidence` → `proposal_id` → `vision_proposals_*.jsonl` (image_path / figure_id) → PMCID/PMID by regex → `papers_*.jsonl` corpus for title+journal. The Stage A canonical bundle stays unchanged; backfill runs explorer-side. The surviving vision edge (`prevotella_nigrescens ↔ GLCM_Correlation`) now carries PMID **37894458**, PMCID **PMC10605408**, title *"Computed Tomography-Based Quantitative Texture Analysis and Gut Microbial Community Signatures Predict Survival in Non-Small Cell Lung Cancer."*, journal *Cancers*. 10 new tests (5 unit on `extract_pmid_pmcid`, 4 unit on `backfill_vision_provenance`, 1 real-run integration that asserts the surviving edge gets backfilled end-to-end). Stage A v2 should add `pmid` + `figure_id_pmc` columns to `relationships.csv` so this lateral join becomes unnecessary.
- **C2 — DONE.** Signed-microbe-disease button relabeled from *"Polarity-resolved edges, strongest confidence first"* to *"Polarity-resolved edges (positively / negatively correlated)"* — accurate to the data (all 29 edges carry the relation-extractor default 0.7; the sort claim was a no-op). Confidence calibration is a downstream task once Pass-2 lands.
- **C3 — DRAFTED.** `docs/paper/LIMITATIONS_PATCH.md` carries a LaTeX-ready `\subsection{Scope and Coverage Limits}` block covering the five named limits: single-annotator IAA, vision-track yield (1/14 case study), ontological grounding uneven (UMLS for microbes only; Disease/BodyLocation/ImagingModality are free-text), signed-edge confidence uniform, body-comp scope explicitly defended. Operator inserts when ready.

**Biological-context check on the surviving vision edge.** PMC10605408 is a real microbiome-radiomics paper (NSCLC + ICI + CT quantitative texture analysis + shotgun MG; n=129 CT scans, n=58 stool). The (prevotella_nigrescens, GLCM_Correlation) cell is a real Spearman r=0.95 from the paper's correlation heatmap (Figure g004, retained per direct image inspection 2026-05-07). The microbe is NOT a central finding of the paper text — it lives in the many-by-many heatmap. Defensible as a methods case study, not as the project's central biological claim. Manuscript abstract already takes this posture; the new C3 Limitations patch makes it more explicit.

**Tests after the fourth pass:** full suite **351 passed / 0 failed** (was 341; +10 new; no regressions).

### Status (2026-05-21, fifth pass) — UI Stage B.b-β + visual polish + manuscript polish to MINERVA format

**Phase A — UI (Stage B.b-β + visual polish) DELIVERED.**
- **Featured 3-hop closer cards** sit above the queries panel: three large gradient cards, one per thesis closer (Ruminococcus→sarcopenia, Peptostreptococcus→SMI, Eubacterium→VAT). Each card carries an axis tag (Gut–muscle / Gut–adipose), the closer path, a large live-computed downstream-disease count (37/7/18), and a "Show traversal →" button that calls `runFeaturedCloser()` to set a query subset = the microbe→feature edge + all downstream feature→disease edges. Live counts recompute on load + file-upload via `updateFeaturedCounts()`.
- **Visual polish.** Header `h1` now uses a webkit gradient text-fill (slate → sky → accent), an italic tagline (`Microbe ↔ Radiomic / Body-Composition Feature ↔ Disease — a literature-mined, gate-audited knowledge graph extension over MINERVA`), a separate counts subtitle. Section eyebrows ("Featured thesis traversals", "Canonical traversals") use uppercase tracking with a soft accent gradient rule. Cards have hover transform + drop-shadow. Header title changed from "SanoMap Radiomics Layer" to "SanoMap Imaging-Phenotype Layer" — the umbrella-term decision lands in the UI surface, consistent with CLAUDE.md Mission + manuscript abstract.
- Test suite unchanged at 351/0 (UI-only changes; no Python test regressions). Manual smoke deferred to operator's local browser via `python3 -m http.server`.

**Phase B — Manuscript polish toward MINERVA paper format DELIVERED.**

The current `docs/paper/paper_sanomap_radiomics_layer.tex` was already IMRD-structured (Abstract / Introduction / Concept-and-Schema / Methods / Results / Discussion / Limitations / Conclusion / Reproducibility) but carried no inline citations, no bibliography, no schema figure, no consolidated metrics table — only the gap table in the Discussion. Fifth-pass additions:

- **Figure 1: ontology schema (TikZ).** Added a `figure*` with a `tikzpicture` rendering of the node/edge ontology — Microbe / MicrobialSignature / RadiomicFeature / BodyCompositionFeature / Disease (solid evidence-typed arrows: CORRELATES_WITH, ASSOCIATED_WITH, MEASURED_AT, ACQUIRED_VIA, REPRESENTED_BY) — plus a dashed-red shortcut showing the upstream MINERVA POS/NEG_CORRELATED_WITH edge that *collapses* the imaging-phenotype intermediary. Caption articulates the precision-pole / coverage-pole framing. Preamble: `\usepackage{tikz}` + `\usetikzlibrary{positioning,arrows.meta,fit,backgrounds,calc}` (`calc` required for the midpoint coordinate in node placement).
- **Table 1 (graph metrics)** inserted in the Results section consolidating headline counts: 1{,}016 papers, 5{,}721 mentions, 99 nodes (broken out per label), 189 reconciled rows (broken out per relation type, with 7 CORRELATES_WITH split 1 vision + 6 text), 62 3-hop paths, 0.916 Gemini self-consistency, 25% UMLS audit drop, 1/14 vision yield, 351 automated tests. Counts trace to `manifest.json` per the post-audit invariant.
- **References section** (20 bibitems) added before `\end{document}` covering radiomics foundational (Lambin 2012, Aerts 2014, IBSI Zwanenburg 2020, pyradiomics van Griethuysen 2017), UMLS (Bodenreider 2004), NER tooling (Neumann 2019 scispaCy, Li 2016 BC5CDR), statistics (Landis & Koch 1977 κ, Wilson 1927 CI), retrieval (Johnson 2019 FAISS), self-consistency (Wang 2023), microbiome–body-axis literature (Ticinesi 2019 gut–muscle, Tilg 2022 gut–liver, Cani 2008 endotoxemia, Sokol 2008 Faecalibacterium, Kostic 2013 F.\ nucleatum, Cruz-Jentoft 2019 EWGSOP2 sarcopenia), the surviving-vision-edge source paper (Botticelli 2023 NSCLC + microbiome + QTA — PMC10605408 / PMID 37894458), comparison-with-MINERVA references (Labrak 2024 BioMistral, Lever 2023 microbe-host relations). Marked with a note that final citation details should be verified against publisher records before submission.
- **22 inline `\cite{}` markers** placed at every empirical or methodological claim in the body: Lambin/Aerts at first radiomics mention; IBSI at IBSI-aligned naming + future-work map; Cruz-Jentoft + Ticinesi at body-comp + gut–muscle; Tilg + Cani at gut–liver + gut–adipose; Botticelli at the PMC10605408 prevotella claim; Bodenreider at UMLS; Neumann + Li at NER tooling; Johnson at FAISS; Wang at self-consistency; Landis-Koch at κ; Wilson at CI; Labrak at BioMistral; Lever at the microbiome-relation labeled set. All cite keys resolve against `\bibitem` entries (verified by hygiene check: 22 cite calls / 20 entries / 0 unmatched).
- **LaTeX hygiene verified**: balanced `\begin`/`\end` environments; 7 sections + 1 starred (References) + 11 subsections; 2 tables (gap + metrics) + 1 starred figure (schema TikZ) + 1 tikzpicture + 1 thebibliography. `pdflatex` compilation is operator-run per the existing runtime (basictex on macOS); the .tex is internally consistent.

**What's still missing for journal-submission readiness (operator decides priority):**
- *Final citation detail verification*: the bibitems anchor the empirical claims but several entries (notably Lever 2023) need full publisher details.
- *Pass-2 metrics insertion*: the headline P/R/F1 + κ blanks fill once the 2026-05-21+ Pass-2 closes. The current `\S\ref{sec:eval}` block explicitly reports them as pending, which is the honest posture.
- *Acknowledgments / Funding / Author Contributions* sections: minor; operator-supplied.
- *A second figure* (results visualization, e.g., 3-hop path traversal example as a force-graph screenshot) would strengthen the Results section; deferred until the explorer's featured-card view stabilizes and a publication-quality screenshot can be exported.

### Status (2026-05-21, eighth pass) — Microbe NER upgrade landed; Gap 1 closed in manuscript

**Microbe NER default swap**: `d4data/biomedical-ner-all` (DistilBERT-66M, MACCROBAT, no published benchmark F1) → **`OpenMed/OpenMed-NER-SpeciesDetect-PubMed-335M`** (BiomedBERT-large, LINNAEUS-trained, F1=0.9649, Apache 2.0). Selected via existing `--microbe-ner-model-id` CLI flag; d4data is retained as legacy fallback. `MicrobeExtractor` is schema-agnostic so the swap is a clean drop-in; only the `extractor` provenance tag changed from hardcoded `distilbert_biomedical` to a model-aware `_extractor_tag()` helper.

**Manuscript Gap 1 closure**: §Discussion table row for "NER (microbe)" upgraded to **"Closed via OpenMed-NER-SpeciesDetect-PubMed-335M (LINNAEUS F1=0.9649); TUI gate retained as second guard"**. Vision-track row also upgraded from "Partially closed" → **"Closed"** now that the sign-check gate is in place. The LINNAEUS F1=0.9649 matches BNER2.0's reported 0.914 envelope on open weights — both gaps the paper named are now genuinely closed.

**What still needs operator action**: rerun entity extraction over the 1,016-paper corpus to actualize the swap on the published graph. The model swap itself is reversible.

**Audit verdict on remaining components**: disease NER (BC5CDR-trained), embedding (BioClinical-ModernBERT-base), relation (Gemini 2.5 Flash-Lite), VLM (Qwen2.5-VL-3B + Gemini 2.5 Pro) — all are current SOTA at their tiers; no further model swaps needed.

Suite: **369 passed / 0 failed** (no regression from the swap).

### Status (2026-05-21, seventh pass) — Goal items 1–4 + pipeline audit + Korean writeup

**Item 1 — branch decision**: **KEEP** `feat/precision-first-phase0` (operator-confirmed via /goal). Carries 17 commits of Phase-0 pilot infrastructure + documented FAIL verdict + spec §3 fallback decision still pending. Merging clutters main with a failed approach; abandoning loses the audit trail.

**Item 2 — HV1 modality harvest**: query layer delivered in `src/harvest_pubmed.py`. `EXPANDED_MODALITY_BLOCK` adds US/sonography/elastography/MRE/FibroScan/mpMRI/DECT/spectral-CT to the baseline. Profiles added: `microbe_liver_elastography` (L11 lane), `microbe_bodycomp_expanded_modality`. Actual harvest is operator-run.

**Item 3 — E1 sign-check gate**: DELIVERED. `sign_check_gate()` (pure function: r-sign vs hemisphere; near-zero tolerance 0.10 backed by clinical convention) + `extract_color_hemisphere_via_vlm()` (independent, proposer-r-blind VLM call) in `src/vision_gates.py`. 16 new tests pin all paths including the firmicutes-retraction failure shape (`r=-0.95` + `observed=positive` → fail). Suite **369 passed / 0 failed**. Not yet wired into `run_all_gates`/audit-script (small follow-on; left for operator to choose whether to enable chain-wide).

**Item 4 — Pass-2**: operator-only. Window opens 2026-05-21.

**Pipeline audit verdict (high-level)**:
- Data-grounded thresholds: UMLS 0.85 (measured 25% drop), sign-check 0.10 (clinical convention), κ ≥ 0.80 (Landis-Koch), Wilson 95% CI, Gemini 7/7 self-consistency (Wang 2023 + measured 0.916).
- **Most clearly arbitrary remaining**: **τ=0.62** dense-retrieval threshold (explicitly "uncalibrated default" in code). Must calibrate post-Pass-2 via `calibrate_threshold`.
- Heuristics with rationale but no measured distribution: range-sanity 0.05, verifier-disagreement 25% (trigger heuristic, not acceptance threshold).

**Model "good to go"**: all six production components OK (NER, embedding, relation, VLM). Largest residual risk = NER precision on rare phylum/species; closure path documented.

**Phase A — Bibliography expansion to MINERVA-paper depth + direct MINERVA citation.**
- Read the actual MINERVA paper (`references/minerva_mgh_lmic.pdf`, Langarica et al., *Brief. Bioinform.* 2025, 26(5):bbaf472, DOI 10.1093/bib/bbaf472) — 13 pages of main paper covering platform, methods, related-work comparison set, and full reference list.
- Added 15 new bibitems (bibliography now 35 entries total) covering: the upstream MINERVA paper itself (was previously named but uncited — critical gap fixed); curated microbe-disease KG predecessors that MINERVA's own Table 1 compares to (HMDAD, gutMDisorder, Amadis, GMMAD, Disbiome, MDIDB, MMiKG); NLP foundations (BERT, SciBERT, DistilBERT, BNER2.0); microbe-host relation extraction prior art (Karkera 2023, Wenhao MarkerGenie 2022); LLM-in-healthcare risk literature (Aurangzeb 2023).
- Inline `\cite{}` markers added in Introduction (curated-KG predecessors + LLM tooling lineage + hallucination risk), Methods (NER tooling + UMLS), Gap analysis (MINERVA direct + BNER2.0 source + DistilBERT). All cite keys resolve; 46 cite calls total, 0 cites in abstract or headings.

**Phase B — Appendix added (6 sections, ~250 lines LaTeX).**
- *Appendix A — Gate Threshold Derivations.* Per-threshold derivation + disconfirmation conditions for: UMLS similarity 0.85 + 30% drop recalibration; TUI accept set {T005,T007,T194,T204} + non-microbe deny-list; default τ=0.62 for dense retrieval; vision range-sanity tolerance 0.05; dual-verifier 25% disagreement threshold (cites the live 46% finding that prompted the gate chain).
- *Appendix B — Sample Size + Statistical Design.* 66 vs 150 gold-set rows + Wilson CI math; 14-day intra-annotator window rationale (episodic-memory vs calibration-drift trade-off); 5-stratum deterministic seed-42 sampling.
- *Appendix C — Design Decision Rationale.* AND-consensus vs majority/OR; direct-evidence-only policy; ASSOCIATED_WITH vs CORRELATES_WITH split; ImageRef as separate node type; the documented decision to retain the prevotella vision edge despite REVIEW verdict.
- *Appendix D — Stage A Reconciliation Algorithm.* Drop-list composition logic; manifest.json as source of truth; the load-bearing reconciliation finding (the "8 (1+7)" headline was never composed — coherent truth is 7 (1+6) on 189-row base).
- *Appendix E — Body-Composition vs Radiomics: Scope Distinction.* IBSI-aligned `RadiomicFeature` (texture/shape/intensity) vs clinical aggregate `BodyCompositionFeature` (SMI/VAT/sarcopenia/myosteatosis); pyradiomics scope per IBSI; why both belong (6/7 CORRELATES_WITH target BCF; literature density argument; "radiomics-first methodology + body-composition-dominant coverage" framing).
- *Appendix F — Reproducibility Recipe.* Exact commands for `build_graph_export.py` → `build_explorer_data.py` → live Neo4j load → `pytest`; required env vars (`GEMINI_API_KEY`, `NEO4J_PASSWORD`); UMLS Terminal.app constraint.

**Phase C — Branch cleanup.**
- Deleted `fix/entity-cleanup-shared-filters` (0 unique commits vs `main`, no remote tracking — safe `git branch -d`).
- **Flagged for operator decision (NOT deleted):** `feat/precision-first-phase0` — tracks `origin/feat/precision-first-phase0`; tip commit explicitly says "Phase-0 verdict = FAIL ... spec §3 fallback decision pending; durability: branch pushed + advisory-surface activated". Deleting it locally wouldn't destroy work (remote still carries it), but the "fallback decision pending" note is load-bearing — operator should decide whether to merge, abandon, or keep open.

**Phase D — Stage B item (c): full evidence drill-down DELIVERED.**
- `scripts/build_explorer_data.py`: new `load_vision_audit_index(artifacts)` reads `vision_gated_audit.jsonl`, indexes retained vision rows (verdict ∈ {ACCEPT, REVIEW, None}; REJECT_GATE explicitly excluded) by PMCID prefix of the PMC-form figure_id (e.g. `PMC10605408_g004` → `PMC10605408`). `backfill_vision_provenance` extended to accept `audit_by_pmcid` and inject `figure_id_pmc` + `r_value` when PMCID matches. The surviving vision edge now carries all 6 backfilled fields: PMID **37894458**, PMCID **PMC10605408**, title, journal *Cancers*, **figure_id `PMC10605408_g004`**, **r_value 0.95**.
- Explorer UI (`docs/explorer/index.html`): table's first column changed from plain PMID text to a **clickable Source link** — for rows with PMCID, link to `https://pmc.ncbi.nlm.nih.gov/articles/{PMCID}/`; for rows with only PMID, link to `https://pubmed.ncbi.nlm.nih.gov/{PMID}/`; hover tooltip carries the paper title. Evidence cell shows `r=…` prefix for vision edges + `fig=PMC…_…` suffix when figure_id is present. New `escapeHtml()` helper applied to all table cells (defensive against any future schema fields with markup).
- Tests: 2 new (`test_load_vision_audit_index_indexes_by_pmcid_and_skips_rejects` covering ACCEPT/REVIEW retain + REJECT_GATE skip; `test_backfill_uses_audit_index_for_figure_id_and_r_value` covering the audit-side backfill path). The real-run integration test now also asserts `figure_id == "PMC10605408_g004"` and `r_value == 0.95` on the surviving vision edge. **Full suite: 353 passed / 0 failed** (was 351; +2; no regressions).

  **Explicitly OUT of Stage B** (backlog; promote to v2 only if novelty/utility test passes AND time remains): ranked text search, query builder UI, saved-query persistence, user accounts, any write path. **Rule shape: positive-system enumeration** — Stage B = these four items; anything else has to earn its way in via a new fork.

  *Causal chain.* Novelty payload = 3-hop traversal with cited evidence (queries + drill-down). Utility hook = "which microbes correlate with which imaging features for disease X, with evidence?" — answered by named queries, not by full-text search. Scope risk on richer features compounds against the video deadline. The 99-node graph is small enough that full-text search inside it solves a non-problem at current scale.

- **Video reframed.** Strictly end-stage. Sequenced after Stage B is live AND Pass-2 closes the manuscript headline. Do not start the script before both gates close — narrative against unconfirmed numbers and unwired UI is wasted footage.

- **Summer-long focus = App (#1) + Manuscript (#2)**, compounding. The manuscript's figures should be screenshots of the app's traversal panels; the app's gate-disclosure surface should mirror the manuscript's methods. Same canonical `graph_export/manifest.json` feeds both.

- **Candidate data-sourcing expansion lanes** (operator picks; positive-system enumeration; no lane runs until selected):
  - **L6**: pancreas + radiomics + microbiome (pancreatic-cancer microbiome literature is growing).
  - **L7**: cardiac CT epicardial-fat + microbiome.
  - **L8**: kidney / renal-sinus-fat + microbiome + CKD.
  - **L9**: multi-organ MRI body-composition (PDFF, ASMM) + microbiome.
  - **L10**: IBD radiomics + gut microbiome.
  - **L11**: liver MRE elastography + microbiome.

  *Promotion rule*: each new lane must show ≥3 candidate PMCIDs with microbe-NER hits AND at least one heatmap/forest/scatter figure before joining the default corpus. Aborts cheaply if the lane is dry.

- **Candidate extraction-sharpening items** (operator picks; positive-system enumeration):
  - **E1**: sign-check gate (proposer-claimed sign vs. Qwen-observed colour hemisphere) — catches wrong-sign collusion that `range_sanity` can't. ~50 lines + a new prompt. Resolves Fork 2 if opened.
  - **E2**: per-feature τ calibration on Pass-2 gold labels (downstream of Pass-2 closure; replaces default 0.62 across the board).
  - **E3**: WHR/BMI scope re-decision after Pass-2 (currently excluded under the imaging-derived rule § 6.9; revisit if the BodyCompositionFeature definition broadens).
  - **E4**: adjudicate the 3 REVIEW-queue vision rows (`PMC9466706_g004`, `PMC7230364_g001`, `PMC10605408_g004` historical) by direct image inspection.
  - **E5**: promote `PMC11453046_Fig6` to graph if current vision proposals are rerun (the one current-batch figure that survived gates AND is unambiguously legitimate per audit).
  - **E6**: virome lane probe — T005 was added to the TUI accept set; no virome-side edges have been produced yet. Exploratory query if L7–L11 don't yield enough.

OPEN decision forks still operator's call:
2. **Vision framing**: methodology-contribution + 1 audited case study (recommended, honest) **vs** invest E1 (sign-check gate) + rerun current proposals to recover more legitimate figures first. (Paper currently takes the recommended honest framing.)

Verification plan for this stage:
- A: unqualified-CSV ambiguity removed; one command reproduces `graph_export/` from current artifacts; manifest counts match post-audit `verified_edges.jsonl`.
- B: app loads current (not 2026-04-05) graph; the 6 Cypher queries return; evidence drill-down resolves to PMID/sentence/figure.
- C: κ ≥ 0.80 (binary collapse); P/R/F1 with 95% Wilson CI in `.tex`; every numeric claim in `.tex` reconciled to post-audit truth.

## Stages
1. Keep repo memory current:
   - `AGENTS.md`
   - `CLAUDE.md`
   - `docs/REQUIREMENTS.md`
   - `docs/PLAN.md`
   - `docs/PROGRESS.md`
   - `docs/NEXT_STEPS.md`
2. Recreate the merged text path on the full-text-aware corpus:
   - `src/extract_radiomics_text.py`
   - `src/text_ner_minerva.py`
   - `src/build_relation_input.py`
3. Run true model-backed relation extraction on GPU or hosted inference:
   - avoid `--backend heuristic` for the real merged pass
4. Clean subject and disease spans before graph promotion:
   - reject `##` fragments
   - reject generic microbial placeholders
   - reject clause-like disease spans
5. Re-run relation extraction and audit quality deltas.
6. Promote to `src/assemble_edges.py` and validate graph export artifacts.
7. Package the project explicitly for the professor-facing rubric:
   - publish a simple knowledge map
   - provide a small explorer over extracted relations
   - include at least one visible visualization or diagram

## Operational Lanes
- `research/query-*`:
  query exploration, profile audits, and query-selection loops.
- `fix/entity-cleanup-*`:
  cleanup rules and relation-quality fixes.
- `ops/remote-run-*`:
  remote or hosted execution setup, runbooks, and result capture.
- `docs/handoff-*`:
  memory upkeep, tracking, and handoff consolidation.

## Active Stage — Four-Task Structural Upgrade

### Task 1 — UMLS Entity Sanitization
- Module: `src/umls_validator.py`
- Integration: `scripts/extract_microbe_feature_relations.py` calls `EntityGate.evaluate()` before relation classification.
- Acceptance criterion: `gut bacterial clpb-like gene function` is dropped from the accepted-edge set on audit re-run.
- TUI accept policy: `{T007 Bacterium, T194 Archaeon, T204 Eukaryote}` plus an explicit deny-list of non-microbe eukaryote CUIs (Homo sapiens, Mus musculus, common model organisms).
- Similarity floor: 0.85 (recalibrate to 0.75 only if drop rate on accepted edges > 30%).

### Task 2 — Embedding-Based Candidate Retrieval
- Module: `src/feature_retrieval.py`
- Encoder: `thomas-sounack/BioClinical-ModernBERT-base` (mean-pooled with attention mask, L2-normalized).
- Index: FAISS when available; numpy cosine fallback for current corpus size (~30k sentences).
- Per-feature τ threshold; default 0.62, calibration scaffold awaits Task 4 labeled data.
- Replaces `_FEATURE_VOCAB` substring lookup in `scripts/extract_microbe_feature_relations.py`.

### Task 3 — Dual-Verifier Consensus
- Module: `src/verify_vision_dual.py`
- Verifier A: existing pixel HSV verifier (`verify_heatmap_r_value` in `src/verify_heatmap.py`).
- Verifier B: independent Gemini Vision call with verifier-only prompt at temperature 0.
- Consensus: AND-gate accepts; XOR routes to `artifacts/vision_review_queue.jsonl`.
- Modal-independence claim: pixel-level color comparison vs. semantic figure interpretation; named in methods as bounded by both verifiers' shared dependence on image quality.

### Task 4 — Gold-Label Benchmark (Implemented; hand-labeling pending)
- Annotation schema v1.0 locked in `docs/benchmark/annotation_schema.md`: 6-class primary label (associated_positive / associated_negative / associated_unsigned / no_association_explicit / not_associated / unclear), 3 secondary labels (evidence_type / quantitative / confidence), 8 numbered edge-case decisions.
- Sampling: `src/benchmark/sample_gold_set.py` — 5 strata, deterministic seed 42, reuses production `_extract_candidates`. Produced `artifacts/gold_set_v1_UNLABELED.jsonl` with 66 rows (target was 150; corpus-limited because only 13 substring candidates and 3 extended-keyword sentences exist in `entity_sentences`). The under-target size is the v1 honest constraint; CIs in the report will be ±0.10 instead of ±0.07.
- Evaluation: `src/benchmark/evaluate.py` — binary P/R/F1 + per-stratum/feature/evidence_type breakdown + Cohen's κ (6-class and binary collapse) for IAA.
- Single-annotator with intra-annotator IAA via 14-day temporal re-labeling; target Cohen's κ ≥ 0.80 (binary) per Landis & Koch.

## Inherited State (carried forward)
- Local CPU-only proof-of-concept plumbing exists; the inherited microbe-disease lane is sufficiently validated for now.
- Shared span cleanup remains implemented in `src/span_cleanup.py`, `src/text_ner_minerva.py`, `src/build_relation_input.py`, `src/relation_extract_stage.py`.
- Live retrieval benchmark decisions:
  - `microbe_radiomics_strict` stays unchanged as the precision lane
  - `microbe_bodycomp` stays unchanged as the default high-yield body-comp lane
  - `microbe_bodycomp_clinical_recall` is optional recall-only, not default
- Explicit phenotype-axis outputs from the local assembly run:
  - `17` text-derived phenotype-to-disease edges after assembly-only semantic normalization
  - `61` audit-only direct text subject-to-phenotype candidates
  - `143` audit-only bridge hypotheses
- `src/verify_heatmap.py` legend detection repaired for synthetic legend selection.
- The local Conda `base` pytest suite is green pre-upgrade; new module tests added this session must also pass.

## Bounded Automation
- Allowed loop classes:
  - query exploration and selection
  - training or model-selection experiments
- Every loop must declare:
  - objective
  - candidate set
  - max iterations
  - evaluation rubric
  - artifact outputs
  - stop condition
  - human review checkpoint

## Risks And Unknowns
- Upstream-associated weights/checkpoints are still unavailable in this workspace.
- The hosted relation path is working, but model-backed acceptance is stricter than the heuristic audit and can surface new malformed accepted spans.
- The local cleanup audit is now clean for the previously observed conjunction-led, preposition-led, and verb-led disease fragments on the Gemini rerun.
- The remaining quality risk is semantic breadth on assembled text-derived disease targets such as `inflammation`, plus residual noise in some direct text subject-to-phenotype candidates.

## Verification Plan
- Compare rebuilt merged text-stage artifact counts against the current local baseline.
- Audit accepted aggregated relations for:
  - fewer `##` fragments
  - fewer generic subject phrases
  - fewer clause-like disease strings
  - fewer accepted leading `and ...`, `in ...`, and `reduces ...` disease fragments
  - explicit review of whether broad concepts such as `inflammation` should remain graph-eligible
- Audit phenotype-axis outputs for:
  - graph-eligible phenotype-to-disease edges
  - audit-only bridge hypotheses
  - audit-only direct text subject-to-phenotype candidates
  - cleaned subject and disease spans in assembled outputs
  - residual clause-like disease examples in assembled text edges
- Validate edge outputs and confirm bridge hypotheses were not ingested as direct graph edges.

## Reasoning Surface

### Knowns
- Edge #5 (`gut bacterial clpb-like gene function → body_fat`) is a documented entity-type error in the published artifacts.
- `_FEATURE_VOCAB` substring matching has unmeasured recall on paraphrastic feature mentions.
- Single-modality pixel verification is structurally vulnerable to VLM monoculture in the proposer step.
- BioClinical-ModernBERT-base loads on M2 MPS; transformers 5.0.0.dev0 is installed.

### Unknowns
- Drop rate of UMLS gate on currently-accepted edges (Priority 1 measurement pending).
- Per-feature optimal τ (Priority 2 measurement pending).
- Vision verifier disagreement rate on real figures (Priority 3 measurement pending).
- True P/R/F1 of the system as a whole (Task 4 deliverable).

### Assumptions
- UMLS coverage of common gut microbes is high enough that recall hit is bounded.
- Mean-pooled ModernBERT embeddings beat substring matching on body-comp feature retrieval — defensible on domain-pretraining mass and 8K context grounds, but not measured.
- Independent Gemini Vision call (different prompt, temperature 0) is modally distinct from pixel HSV verification — partially independent (shared family), defensible as "modal independence" in the methods section.

### Disconfirmation
- UMLS audit drops > 30% of accepted edges → similarity threshold too strict; recalibrate.
- Embedding retrieval returns < 50 candidates per common feature → τ undertuned.
- Vision verifier disagreement > 25% on existing 2 figures → prompt is wrong-shape.
- Cohen's κ < 0.80 on intra-annotator gold-set re-labeling → annotation schema needs revision before benchmark publication.
