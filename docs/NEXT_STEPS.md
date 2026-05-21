# Next Steps

Operational handoff. Update whenever priority, blocker, or milestone changes.

## Current State (2026-05-21) — Fork 3 Decided, Summer Frame Locked

**Goal at the highest level.** Build the **Microbe ↔ Imaging-Phenotype ↔ Disease evidence graph**. App + Manuscript build through the summer (compounding); Video is the end-stage wrap-up. Every expansion must compound novelty OR utility — see `docs/PLAN.md` → Governing Frame (2026-05-21). CLAUDE.md now loads the mission + governance tests + work-style defaults at the top of every session.

**Fork 3 resolved → read-only graph explorer** for Stage B. Four positive-enumerated items in (rewire, 6 canonical queries, evidence drill-down, 3 thesis closers as featured demos). Everything else (ranked search, query builder, write paths) explicitly OUT to backlog. Detail + causal chain in `docs/PLAN.md` → Active Stage / Status (2026-05-21).

**Today (2026-05-21) is also when Pass-2 unblocks** — the 14-day temporal window closes. Two parallel lanes now active:

- **Engineering lane (ninth-pass status 2026-05-21 — handoff)**. NER swap deployed as default, but live re-extraction attempt blocked by missing scispacy model + strict-mode guard. Re-extraction is **deferred (not blocking)**. Critical path is Pass-2.

  **Next priority — Pass-2 annotator lane (operator-only):**
  ```bash
  cd "/Users/junlee/research/mgh lmic/sanomap-radiomics-layer"
  # Start from UNLABELED (do NOT consult Pass-1); randomize row order to break sequential context.
  cp artifacts/gold_set_v1_UNLABELED.jsonl artifacts/gold_set_v1_LABELED_pass2.jsonl
  # Hand-label fresh; then:
  conda run -n base python -m src.benchmark.evaluate \
      --gold artifacts/gold_set_v1_LABELED_pass1.jsonl \
      --iaa-pass2 artifacts/gold_set_v1_LABELED_pass2.jsonl \
      --multi-class \
      --output artifacts/gold_set_v1_metrics.json
  ```
  Output fills the manuscript's only headline blank — measured P/R/F1 + 95% Wilson CI + Cohen's κ.

  **Second priority — get free Gemini API key (~2 min):** https://aistudio.google.com/app/apikey → `echo 'GEMINI_API_KEY="AIza..."' >> .env`. Unblocks any future relation-extraction or vision-proposer rerun.

  **Deferred (optional A/B; not blocking):** full OpenMed re-extraction. Requires:
  ```bash
  # Install the missing scispacy disease NER model (operator-run, ~30 sec)
  pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_ner_bc5cdr_md-0.5.4.tar.gz
  python -c "import spacy; print([(e.text, e.label_) for e in spacy.load('en_ner_bc5cdr_md')('Patients with cirrhosis showed Faecalibacterium prausnitzii depletion.').ents])"
  # Expect at least one DISEASE entity ('cirrhosis'). If empty, deeper diagnosis needed.
  ```
  Then re-run Steps 1–4 per the prior quickstart. Reversible via `pip uninstall en_ner_bc5cdr_md`.

  **What does NOT need to change:** OpenMed-NER-SpeciesDetect-PubMed-335M is already the CLI default in `src/text_ner_minerva.py`; manuscript Gap 1 cites LINNAEUS F1=0.9649 as the closure evidence; 369-test suite passes; reasoning-surface restored to the prior authoritative entry.

- **Previous engineering lane summary (eighth pass)** — Microbe NER model upgraded; manuscript Gap 1 closure recorded:
  - **Microbe NER default swap**: `d4data/biomedical-ner-all` (DistilBERT-66M, MACCROBAT, no published benchmark F1) → **`OpenMed/OpenMed-NER-SpeciesDetect-PubMed-335M`** (BiomedBERT-large, LINNAEUS-trained, F1=0.9649 precision 0.958 recall 0.972, Apache 2.0). Default value of `--microbe-ner-model-id` flag updated in `src/text_ner_minerva.py`; the new `_extractor_tag()` helper records `openmed_speciesdetect` provenance on every emitted row so downstream artefacts can be re-traced. d4data is retained as legacy fallback via the same CLI flag. Docstring in `src/umls_validator.py` updated to name both lineages.
  - **Manuscript Gap 1 closure**: paper's MINERVA-comparison table entry for "NER (microbe)" upgraded from "Substitute identified; TUI gate mitigates" → "**Closed** via OpenMed-NER-SpeciesDetect-PubMed-335M (LINNAEUS F1=0.9649); TUI gate retained as second guard". The methodological text in §Discussion also extended to name the swap + claim closure of Gap 1. Vision-track entry similarly upgraded from "Partially closed" → "**Closed**" now that the sign-check gate is in place. The LINNAEUS F1=0.9649 closes the open-weights envelope on BNER2.0's reported 0.914 with margin to spare.
  - **What the operator needs to do for the swap to take effect on the published graph**: rerun `src/text_ner_minerva.py` (or whichever script invokes it) over the 1,016-paper corpus to regenerate `entity_sentences.jsonl`, then re-run the UMLS audit + downstream relation extraction + `build_graph_export.py`. The current `graph_export/` bundle still reflects the d4data extraction. Expected effect: fewer non-microbe candidates entering the UMLS gate (since SpeciesDetect is species-specific) → potentially recovered legitimate edges + reduced gate load.
  - Suite: **369 passed / 0 failed** (no regression from the swap; the swap doesn't change any test invariant because the MicrobeExtractor is schema-agnostic).

- **Previous engineering lane summary (seventh pass)** — Goal items 1–4 + pipeline audit + Korean writeup all done in one /goal pass:
  - **Item 1 — `feat/precision-first-phase0` branch decision**: **KEEP** (do not merge, do not delete). 17 commits of Phase-0 pilot infrastructure + documented FAIL verdict + spec §3 fallback decision still pending per the operator's own tip note.
  - **Item 2 — HV1 modality harvest expansion**: query strings DELIVERED. New `EXPANDED_MODALITY_BLOCK` (US/sonography/elastography/MRE/FibroScan/mpMRI/DECT/spectral-CT) + new profiles `microbe_liver_elastography` (L11 lane) + `microbe_bodycomp_expanded_modality`. Actual PubMed harvest is operator-run (network + ~minutes): `conda run -n base python -m src.harvest_pubmed --query-profile microbe_liver_elastography --max-papers 200 [--dry-run]`.
  - **Item 3 — E1 sign-check gate**: DELIVERED. `sign_check_gate()` (pure function, r-sign vs observed hemisphere) + `extract_color_hemisphere_via_vlm()` (focused VLM call, blind to proposer's claimed r) added to `src/vision_gates.py`. Near-zero tolerance 0.10 backed by the |r| ≤ 0.10 clinical-microbiome convention. 16 new tests in `tests/test_sign_check_gate.py` covering happy paths, the firmicutes-retraction failure shape, near-zero passes, unrecognized inputs, mocked-HTTP VLM extraction. Suite **369 passed / 0 failed**. The audit script (`scripts/run_vision_gated_audit.py`) does NOT yet invoke the new gate by default — wiring it in is a small follow-on; the gate is fully self-contained and testable today.
  - **Item 4 — Pass-2 annotator lane**: operator-only. 14-day window opens today. Procedure already documented in this file's quickstart.
  - **Pipeline audit + Korean writeup**: full nine-stage walkthrough + threshold audit + model "good to go" verdict delivered in chat. Key finding: **τ=0.62 dense-retrieval threshold is the most clearly arbitrary number remaining** (code comment explicitly says "uncalibrated default; calibrate per-concept"). Must calibrate post-Pass-2 — the function `calibrate_threshold` is already in `src/feature_retrieval.py`. UMLS 0.85, sign-check 0.10, κ ≥ 0.80, self-consistency 7/7 are all data-grounded. Range-sanity 0.05 + verifier-disagreement 25% have stated rationale but no measured distribution — medium-priority refinements.

- **Previous engineering lane summary (sixth pass and earlier)**: Stage B items (a) + (b)-α + (b)-β + (c) ALL DELIVERED + C1/C2/C3 closed + manuscript expanded to MINERVA-paper depth + appendix added + branch cleanup partial 2026-05-21:
  - **Stage B (c) full evidence drill-down**: explorer table's Source column is clickable (PMCID → PMC article URL; PMID-only → PubMed URL; title in hover tooltip). Vision edge now carries 6 fields (PMID, PMCID, title, journal, figure_id `PMC10605408_g004`, r_value 0.95) via the new audit-index join in `build_explorer_data.py`. Evidence cell shows `r=…` prefix + `fig=PMC…` suffix. New `escapeHtml()` helper across the table. 2 new tests; suite **353 passed / 0 failed**.
  - **Manuscript expansion**: Bibliography 20 → 35 bibitems (added MINERVA direct citation Langarica 2025, curated-KG predecessor lineage HMDAD/gutMDisorder/Amadis/GMMAD/Disbiome/MDIDB/MMiKG, NLP foundations BERT/SciBERT/DistilBERT/BNER2.0, microbe-relation prior art Karkera/MarkerGenie, hallucination literature Aurangzeb). 46 inline cite calls; 0 in abstract or headings (verified).
  - **Appendix (6 sections, ~250 LaTeX lines)**: A gate thresholds; B sample size + stats; C design rationale; D Stage A reconciliation; E body-comp vs radiomics scope distinction; F reproducibility recipe with exact commands.
  - **Branch cleanup**: `fix/entity-cleanup-shared-filters` deleted (merged, no remote). `feat/precision-first-phase0` flagged for operator: tracks remote, unmerged, tip note says "fallback decision pending" — operator picks (keep open / merge / abandon).
  - **Next bounded steps queued (operator-pick)**:
    1. Decide on `feat/precision-first-phase0` branch (merge / abandon / keep open).
    2. Execute one of the v2 harvest-lane expansions HV1/HV2/HV3 (modality / emerging radiomics / body-comp depth).
    3. Execute one of the E1–E6 extraction-sharpening items (E1 sign-check gate is the highest-leverage; would resolve open Fork 2 vision-framing decision).
    4. Pass-2 annotator-lane closure (operator-only; 14-day temporal window now open).

- **Previous engineering lane summary (fifth pass and earlier)**:
  - (a–b) explorer rewire onto canonical export + 6 canonical queries as named buttons.
  - **(b)-β + visual polish**: 3 featured 3-hop-closer cards above queries panel with live downstream-disease counts (37/7/18) + "Show traversal" buttons; gradient header title, italic tagline, axis tags, hover transforms. **App title changed to "SanoMap Imaging-Phenotype Layer"** so the umbrella-term decision lands in the UI surface consistently with CLAUDE.md + manuscript.
  - **Manuscript polish (Phase B)**: Figure 1 TikZ schema (ontology + dashed MINERVA shortcut); Table 1 graph-metrics consolidation; **References section with 20 bibitems**; 22 inline `\cite{}` markers across Introduction / Methods / Results / Discussion / Limitations; preamble extended with `\usepackage{tikz}` + libraries (`positioning,arrows.meta,fit,backgrounds,calc`). LaTeX hygiene verified (balanced envs, all cite keys resolve). Operator runs `pdflatex paper_sanomap_radiomics_layer.tex` (twice for refs) to confirm compile.
  - **C1–C3** as before: vision-edge PMID/PMCID backfill, signed-edge button relabel, Limitations patch drafted at `docs/paper/LIMITATIONS_PATCH.md`.
  - Tests: **351 passed / 0 failed** (unchanged through fifth pass; UI + LaTeX edits don't touch Python; vision-edge backfill still works post-hoc).
  - **Next**: (c) full evidence drill-down (sentence text + figure refs for non-vision edges; the vision edge already carries PMID + title + journal via C1). Now feasible since C1 unblocked the PMID linkage.

- **Previous engineering lane summary**:
  - (a) `docs/explorer/data.jsonl` regenerated from canonical `graph_export/` via `scripts/build_explorer_data.py` (189 rows, row-count invariant).
  - (b)-α queries panel exposes the 6 canonical traversals as named buttons; JS mirrors `src/graph_queries.py` Cypher one-to-one.
  - **C1**: vision-edge PMID/PMCID backfill — `prevotella_nigrescens ↔ GLCM_Correlation` now carries **PMID 37894458 / PMCID PMC10605408** + title + journal. Stage A unmutated; backfill runs explorer-side via lateral join through `proposal_id`.
  - **C2**: signed-microbe-disease button relabeled to remove the no-op "confidence DESC" claim (all 29 edges carry default 0.7).
  - **C3**: `docs/paper/LIMITATIONS_PATCH.md` drafted — LaTeX-ready `\subsection{Scope and Coverage Limits}` block covering single-annotator IAA, vision yield 1/14, ontology grounding uneven, signed-confidence uniform, body-comp scope defended.
  - Tests: **351 passed / 0 failed** (was 321 at session start; +30 across four passes; no regressions).
  - **Next item (b)-β**: three thesis-closer featured cards above the queries panel (delivers item d) + visual polish ("legit visual" — typography, spacing, hierarchy). Then item (c) full sentence/figure drill-down: now unblocked by C1's PMID enrichment.

- **Body-composition validity (operator question, resolved 2026-05-21)**: load-bearing, keep. 6/7 surviving CORRELATES_WITH target BCF; without it the graph collapses to 1 edge. Pyradiomics + QIBA + UK-Biobank IDP confirm BCF measures are valid quantitative imaging biomarkers even outside strict pyradiomics scope. Pure-radiomics-microbiome is niche (~hundreds of papers); body-comp-microbiome is ~thousands. Detailed verdict in `docs/PLAN.md` Status (2026-05-21, fourth pass) + `docs/PROGRESS.md` fourth pass.

- **Harvest coverage v2 candidates** (operator picks; positive-system enumeration, no harvest runs without selection):
  - **HV1 modality**: `ultrasound`, `sonograph*`, `elastography`, `MRE`, `FibroScan`, `mpMRI`, `DECT` — especially relevant for L11 (liver MRE) lane.
  - **HV2 emerging radiomics**: `habitat imaging`, `delta radiomics`, `intratumoral heterogeneity`, `deep features`, `voxel-wise radiomics`, `radiopathomics`.
  - **HV3 body-comp depth**: `sarcopenic obesity`, `cachexia`, `L3 vertebra`, `Hounsfield unit*`, `appendicular lean mass`, `lean mass index`, `liver iron concentration`.
- **Annotator lane (operator)**: Pass-2 re-label the 66-row gold set **without consulting Pass-1**; start from `gold_set_v1_UNLABELED.jsonl`; randomize row order to break sequential context. Evaluate κ + binary P/R/F1 with 95% Wilson CI.

**Live Neo4j is no longer blocking Stage B.** The static `graph_export/` bundle is sufficient for read-only Stage B per Fork 3. Live Neo4j becomes a v2 upgrade path (swap the explorer's JS query backend for Bolt/HTTP) once Docker is up. The JS queries mirror `src/graph_queries.py` Cypher semantics one-to-one so the swap is mechanical.

**Naming / category framing (2026-05-21, recorded).** Operator asked whether "radiomics" is the right category. Answer: **no — the umbrella is "imaging-derived phenotype" (IDP, UK-Biobank framework) or "imaging phenotype"; "radiomics-first" is methodology, not scope.** Today's graph carries 6 `RadiomicFeature` nodes (IBSI) AND 8 `BodyCompositionFeature` nodes; body-composition dominates the imaging side (6 of 7 CORRELATES_WITH target BCF). CLAUDE.md Mission + manuscript abstract already use the correct umbrella; no further doc churn for framing. Repo name and `RADIOMICS_LAYER_SPECS.md` filename are legacy. Plausibility verified against four established gut-axes (muscle / liver / adipose / bone); utility verified against three user personas (microbiome / body-composition / clinical). Full analysis in `docs/PROGRESS.md` Session 10 follow-on, third pass.

**Candidate expansion lanes** are now named in `docs/PLAN.md` Status (2026-05-21):
- Six data-sourcing lanes (**L6–L11**): pancreas, cardiac CT epicardial-fat, kidney/renal-sinus-fat, multi-organ MRI body-composition, IBD radiomics, liver MRE elastography.
- Six extraction-sharpening items (**E1–E6**): sign-check gate, per-feature τ calibration, WHR/BMI scope re-decision, REVIEW-queue adjudication, `PMC11453046_Fig6` promotion, virome lane probe.

Positive-system enumeration: no lane runs until operator selects it. Each new data lane needs ≥3 candidate PMCIDs with microbe-NER hits AND at least one heatmap/forest/scatter figure before joining the default corpus.

**Last open fork.** Fork 2 (vision framing) sits on the honest framing until operator opens E1 (sign-check gate).

### Next-session quickstart (updated for Pass-2 + Stage B parallel)

```bash
# 1. (operator) bring up live Neo4j — Docker daemon is currently DOWN
open -a Docker
export NEO4J_PASSWORD='choose-strong'
docker compose -f docker-compose.neo4j.yml up -d

# 2. regenerate + load coherent graph (idempotent)
conda run -n base python scripts/build_graph_export.py
conda run -n base python scripts/neo4j_load.py --dry-run      # validate
NEO4J_PASSWORD="$NEO4J_PASSWORD" conda run -n base python scripts/neo4j_load.py

# 3. Pass-2 (annotator lane) — start from UNLABELED, do not consult Pass-1
cp artifacts/gold_set_v1_UNLABELED.jsonl artifacts/gold_set_v1_LABELED_pass2.jsonl
# hand-edit fresh; randomize row order if feasible

# 4. Evaluate κ + P/R/F1
conda run -n base python -m src.benchmark.evaluate \
    --gold artifacts/gold_set_v1_LABELED_pass1.jsonl \
    --iaa-pass2 artifacts/gold_set_v1_LABELED_pass2.jsonl \
    --multi-class \
    --output artifacts/gold_set_v1_metrics.json

# 5. Stage B explorer rewire (engineering lane, parallel to Pass-2)
# Point docs/explorer/index.html off the frozen 2026-04-05 data.jsonl onto
# graph_export/ or live Neo4j via src/graph_queries.py.
# Scope: 4 items per PLAN.md Status (2026-05-21). Ranked search OUT.
```

## Current State (2026-05-18) — Deliverable-Gap Reframing

Codebase reviewed against the PI's 3-step pipeline + 3 end-of-summer deliverables. Verdict:
- **Data sourcing**: aligned. **Hybrid text-vision**: capability aligned; vision is text-dominant by audited design (1 legit figure / 14 post-gate) — a paper-framing obligation, not a defect. **Neo4j integration**: NOT aligned in the integration sense — no driver/bolt, hand-run `.cypher`, four divergent graph-artifact vintages, unqualified `artifacts/neo4j_relationships.csv` is junk smoke data.
- **App (deliverable #1)**: partial — static explorer reads a frozen 2026-04-05 JSONL, does not query the graph. **Manuscript (#2)**: mature draft, headline P/R/F1 + κ blank pending Pass-2 (≥ 2026-05-21). **Video (#3)**: not started.
- **Reframe**: the critical path is the integration spine + graph-backed app (engineering), running in parallel with the annotator-bound Pass-2 (longest non-parallelizable lead). See `docs/PLAN.md` → "Active Stage" for stages A–D + status.
- **Delivered 2026-05-19**: WS1 (proposal archived; two-column manuscript compiling). WS2 Fork 1 = **live Neo4j** (operator decision): Stage A reconciler + `graph_export/` bundle, `neo4j_load.py`, read-only `graph_queries.py`, docker-compose, runbook; 321 tests pass. **Coherence finding: docs headline `8 (1 vision + 7 text)` was never composed; manifest truth = `7 (1 vision + 6 text)`, 189 rows / 99 nodes. Paper + PROGRESS corrected.** 62 three-hop paths intact.
- **Commit state**: all 22 files committed by the checkpoint automation in `36189da chkpt: 2026-05-19T00:17:22` (tree clean). These are `chkpt:` messages, not Conventional Commits — consolidating `679c68e..36189da` into one conventional commit before any PR is a history rewrite (destructive; needs explicit operator authorization). Hygiene: `docs/paper/paper_sanomap_radiomics_layer.log` got tracked — recommend `.gitignore` for `*.aux/.log/.out`, keep `*.{tex,pdf}`.

### Next-session quickstart (exact commands)
```bash
# 1. (operator) bring up live Neo4j — Docker daemon is currently DOWN
open -a Docker            # then wait for daemon
export NEO4J_PASSWORD='choose-strong'
docker compose -f docker-compose.neo4j.yml up -d
# 2. regenerate + load the coherent graph (idempotent)
conda run -n base python scripts/build_graph_export.py
conda run -n base python scripts/neo4j_load.py --dry-run      # validate
NEO4J_PASSWORD="$NEO4J_PASSWORD" conda run -n base python scripts/neo4j_load.py
# 3. Stage B (after Fork 3 decision): rewire docs/explorer/index.html off the
#    frozen 2026-04-05 data.jsonl onto graph_export/ or live Neo4j via
#    src/graph_queries.py  (the last engineering piece for deliverable #1)
```

## Current State (2026-05-07)
- **Task 1 closed live.** UMLS audit drop rate 25% (2/8) under the 30% threshold. Edge #5 + bacteriodetes typo dropped. Outputs: `artifacts/dropped_entities_audit.jsonl`, `artifacts/umls_gate_report.json`.
- **Task 3 pivoted to local Qwen2.5-VL-3B via Ollama** (free, fits 8GB M2 at 4-bit). Daemon running at `localhost:11434`. Smoke test queued; `verify_vision_dual.py` accepts the swap via `--api-base-url`/`--model-id` flags only.
- **Task 4 entered hybrid labeling mode**. `scripts/suggest_gold_set_labels.py` generated 66 label suggestions to `artifacts/gold_set_v1_LABELED_pass1_SUGGESTIONS.jsonl` with per-row `_suggestion_rationale`. Critical path is now junjslee's review of those suggestions.
- **Task 2 (dense retrieval)**: implementation complete; corpus encoding pass + τ calibration still pending. Calibration is now strictly downstream of pass 1 labels (need labeled data to set per-feature τ).
- Pre-upgrade baseline preserved: 191 Neo4j rows, 9 CORRELATES_WITH edges, 62 traversable Microbe→Feature→Disease paths.
- **280 tests passing**. No regressions.
- Vision verifier paid-API path (Gemini Flash) is now an alternative, not the default.

## Runtime Notes Preserved From Prior Sessions

### UMLS runtime (unchanged policy)
**Always run UMLS scripts from Terminal.app (not VSCode terminal):**
```bash
conda activate base
python scripts/audit_microbe_entities.py \
  --input artifacts/microbe_feature_relations.jsonl \
  --output artifacts/dropped_entities_audit.jsonl
```
Reason: scispacy en_core_sci_lg + UMLS KB load is ~5GB and process-isolation matters.

### .env / API key handling
Scripts use `os.environ.get("GEMINI_API_KEY")` — no dotenv loading. Source before running:
```bash
set -a && source .env && set +a
```

### Dependency check before Task 2 corpus run
- `transformers >= 4.45` — required for ModernBERT (`thomas-sounack/BioClinical-ModernBERT-base`). Verified 5.0.0.dev0 available in conda base.
- `torch >= 2.0` with MPS — verified.
- `faiss-cpu` — **not currently installed**. `src/feature_retrieval.py` falls back to numpy cosine search; for >100k sentence corpora install via `pip install faiss-cpu`.

## Priority 1 — UMLS audit (CLOSED 2026-05-07)

Live audit ran clean. Drop rate 25% (2/8 records). Outputs in `artifacts/dropped_entities_audit.jsonl` + `artifacts/umls_gate_report.json`. Edge #5 dropped at similarity 0.799 < 0.850; `bacteriodetes` typo dropped (no_umls_match). Recalibration not needed.

## Priority 2 — Calibrate retrieval τ on a small dev set (Task 2 closure)

Without Task 4's full gold set, calibrate per-feature τ on a 30-50 sentence hand-labeled dev split:
```bash
conda run -n base python -m src.feature_retrieval calibrate \
    --concept skeletal_muscle_index \
    --dev-set artifacts/dev_set_smi.jsonl \
    --target-precision 0.85
```
Outputs the τ that satisfies the precision floor and the resulting recall on dev. Repeat for each canonical concept.

If retrieval at calibrated τ returns < 50 candidates per common feature on the 1,016-paper corpus, the index is undertuned — sweep τ wider.

## Priority 3 — Vision Track scoped + audited (CLOSED + DOWNGRADED 2026-05-07)

After the dual-verifier smoke produced "7 ACCEPT / 6 REVIEW", manual review by the operator surfaced that most figures were not heatmaps and that proposed r-values were not appearing in source text. Subagent audit confirmed proposer-hallucination + Qwen rubber-stamping. Three deterministic pre-verifier gates were added (`src/vision_gates.py`) and a retroactive audit run via `scripts/run_vision_gated_audit.py`.

**Final post-gate audit results (n=14: 13 current proposals + 1 historical edge):**
- REJECT_GATE: 6 (caption × 3, range_sanity × 2, colorbar_detect × 1)
- ACCEPT: 5
- REVIEW: 3

**Graph cleanup applied** (`scripts/drop_failed_vision_edges.py`):
- DROPPED: PMC6178902_g0006 (firmicutes ↔ Total fat %, r=-0.95) — manual inspection: cell is RED (positive), claim was negative; LFC scale not Pearson r.
- KEPT: PMC10605408_g004 (prevotella ↔ GLCM_Correlation, r=0.95) — real Spearman heatmap, distance 0.05, support 1.0.

**Headline count change**: 9 CORRELATES_WITH → 8 (1 vision + 7 text). Backups under `.pre_vision_audit_2026_05_07.bak` suffix in case rollback is needed.

**Followup options (lower priority than Pass-2 of Task 4):**
1. **Sign-check gate** — proposer-claimed sign vs Qwen-observed colour hemisphere. Catches the wrong-sign failure mode that range_sanity cannot. Estimated: ~50 lines + new prompt.
2. **Promote PMC11453046_Fig6 to graph** if the current proposals are ever rerun — it is the one current-batch figure that survived gates AND is unambiguously legitimate per audit.
3. **Adjudicate 3 REVIEW-queue rows** (`PMC9466706_g004`, `PMC7230364_g001`, `PMC10605408_g004` historical) by manual eye if more vision edges are needed for the proposal.

## Priority 4 — Pass 1 CLOSED (2026-05-07); 14-day temporal window open

Pass 1 authoritative file: `artifacts/gold_set_v1_LABELED_pass1.jsonl` (66 rows). Generation pipeline:
1. `scripts/suggest_gold_set_labels.py` → `gold_set_v1_LABELED_pass1_SUGGESTIONS.jsonl` (Claude proposed).
2. Operator reviewed all 66 with the imaging-derived scope rule; 7 rows overridden.
3. `scripts/apply_pass1_overrides.py` → `gold_set_v1_LABELED_pass1.jsonl` (authoritative).
4. Schema bumped to v1.1 with the scope rule (§ 6.9).

Final distribution:
- not_associated: 47
- associated_negative: 8
- unclear (entity-type errors, § 6.8): 8
- associated_unsigned: 2
- associated_positive: 1
- no_association_explicit: 0

**14-day temporal window opens 2026-05-07. Pass-2 earliest start: 2026-05-21.** Per § 7.2 of the schema, the wait is non-negotiable: shorter intervals leak short-term memory and inflate κ artificially.

When the window closes, Pass-2 procedure:
```bash
# Pass-2: re-label the same 66 rows WITHOUT consulting pass 1.
# Critically — start from the UNLABELED file, not pass 1, so prior labels do not anchor.
cp artifacts/gold_set_v1_UNLABELED.jsonl artifacts/gold_set_v1_LABELED_pass2.jsonl
# Hand-edit fresh; randomize row order if feasible to break sequential context.

# Evaluate.
conda run -n base python -m src.benchmark.evaluate \
    --gold artifacts/gold_set_v1_LABELED_pass1.jsonl \
    --iaa-pass2 artifacts/gold_set_v1_LABELED_pass2.jsonl \
    --multi-class \
    --output artifacts/gold_set_v1_metrics.json
```

Acceptance: Cohen's κ (binary collapse) ≥ 0.80; report binary P/R/F1 with 95% Wilson CI.

**Methods-section disclosure**: Pass 1 was computer-aided manual annotation — Claude proposed labels with rationale; junjslee reviewed all 66 and overrode 7 under the imaging-derived scope rule. Pass 2 is junjslee independent (no Claude prompt, no consultation of Pass 1). Cohen's κ measures intra-annotator consistency on junjslee's two passes; the Claude suggestions are an annotation aid, not the oracle.

## Priority 5 — Compile Proposal PDF (deferred from prior session)

Still blocked on `pdflatex`:
```bash
brew install --cask basictex
# restart terminal, then:
cd docs/paper/proposal
pdflatex report_sanomap_radiomics_layer.tex
```
Lower priority than Tasks 1-4 closure; the proposal text needs updating with the four-task architecture before recompile is meaningful.

## Do Not Change Without Documented Reason
- `ASSOCIATED_WITH` for text-derived phenotype-to-disease edges
- `CORRELATES_WITH` for verified quantitative figure edges
- Bridge hypotheses as audit-only
- Direct-evidence-only graph policy
- QUALIFYING_TOPOLOGIES: `{heatmap, forest_plot, scatter_plot, dot_plot}`
- UMLS TUI accept set `{T005, T007, T194, T204}` for microbe class — change requires methods-section update
- Dual-verifier AND-consensus — change to majority/OR requires Limitation-section update

## Runtime Notes
- Local Python: Conda `base`
- VLM backend: `qwen_api` → Gemini OpenAI-compatible endpoint
- Qwen local: **impossible on 8GB M2** (~14GB FP16 needed)
- **Before any paid run: dry-run first and confirm cost estimate**
- UMLS: native Terminal only

## Reasoning Surface

### Knowns
- All three implementation modules exist and are unit-tested with mocks.
- `gut bacterial clpb-like gene function` is the named entity-type failure that Task 1 must reject.
- The 7 text-derived `CORRELATES_WITH` edges depend on `_FEATURE_VOCAB` substring matching for candidate generation.
- BioClinical-ModernBERT-base is downloadable and loads on MPS.
- Gemini API access works via OpenAI-compatible endpoint with `GEMINI_API_KEY`.

### Unknowns
- How many of the 9 accepted edges survive the UMLS gate (Priority 1 will measure this).
- Per-feature optimal τ for retrieval (Priority 2 will measure).
- Real-figure disagreement rate between pixel and Vision verifier (Priority 3 will measure).
- Whether faiss-cpu installation is worth the friction at current corpus size (~30k sentences).

### Assumptions
- UMLS gate at similarity 0.85 is appropriately strict for microbe class — testable.
- Default τ=0.62 lands in a reasonable range — testable on dev set.
- Independent Gemini Vision call (different prompt, temperature 0) provides modally distinct signal from pixel HSV verifier — partially defensible, fully testable.

### Disconfirmation
- UMLS audit drops > 30% of accepted edges → similarity threshold needs recalibration.
- Embedding retrieval returns < 50 candidates per common feature → τ undertuned.
- Vision verifier disagreement > 25% on existing 2 figures → prompt design is wrong.

## So-What Now?

> **TL;DR:** Tasks 1–4-Pass-1 closed; extraction is research-defensible. The end-of-summer risk is no longer extraction quality — it is the **integration spine + application** (Step 3 / deliverable #1), which is architecturally absent. Two independent lanes: engineering (A→B, startable now, gated only on Fork 1) and annotator (C Pass-2, hard floor 2026-05-21, longest lead).

- **Immediate (annotator lane)**: Pass-2 independent re-label the moment the temporal window opens (2026-05-21). It gates the manuscript's only blank — measured P/R/F1 + Cohen's κ — and Task 2 τ calibration sits downstream of it. Non-parallelizable; start on time, do not defer.
- **Immediate (engineering lane)**: Stage A done. Next = **Stage B explorer rewire** — point `docs/explorer/index.html` off the frozen 2026-04-05 `data.jsonl` onto the canonical `graph_export/` (or live Neo4j via `src/graph_queries.py`) + evidence drill-down. Decide Fork 3 (app scope ceiling) first. Operator-run: live load per `docs/NEO4J_RUNBOOK.md` (start Docker Desktop → `docker compose -f docker-compose.neo4j.yml up -d` → `neo4j_load.py`).
- **Blockers**: Engineering lane unblocked (Fork 1 resolved → live Neo4j; A delivered). Annotator lane blocked until 2026-05-21 by the non-negotiable temporal window.
- **Open decision forks (operator)**: Fork 1 RESOLVED (live Neo4j). Remaining: (2) vision paper-framing — paper currently takes the recommended honest framing; (3) app scope ceiling — decide before the Stage B explorer rewire. Detail in `docs/PLAN.md` → Active Stage / Status (2026-05-19).
- **Carried open questions**: (a) accept 66-row gold set + wider CIs (recommended) vs expand to 150; (b) re-run UMLS audit before evaluating so the accepted_edge stratum matches post-gate truth; (c) draft `docs/benchmark/IAA_v1.md` after κ per § 7.6.
