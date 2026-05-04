# Progress

## Last Updated
2026-05-04 — Four-task structural upgrade landed in scope. Pipeline acceptance is now framed against four stacked gates: (1) UMLS TUI grounding for entity sanitization, (2) BioClinical-ModernBERT dense retrieval replacing `_FEATURE_VOCAB`, (3) dual-verifier consensus (pixel + independent VLM) for Vision Track, (4) gold-label benchmark for measured P/R/F1. Tasks 1–3 implemented this session; Task 4 is the next deliverable.

## Architecture (post-upgrade)

The pipeline is now structured as five independent gates. Each gate is independently auditable; an edge reaches the graph only after passing every applicable gate.

| Gate | Purpose | Module | Failure mode |
|---|---|---|---|
| Retrieval (text) | Dense feature-mention retrieval over BioClinical-ModernBERT embeddings; replaces hand-curated `_FEATURE_VOCAB` substring matching | `src/feature_retrieval.py` (Task 2) | Recall ceiling, threshold τ |
| Entity sanitization | UMLS TUI grounding — Microbe must ground to T007/T194/T204; gene-function noise rejected | `src/umls_validator.py` (Task 1) | Coverage gap (novel taxa not in UMLS) |
| Relation acceptance (text) | Gemini 2.5 Flash-Lite, 7-sample temperature-varied self-consistency, full-agreement | `scripts/extract_microbe_feature_relations.py` | Self-correlated; doesn't bound systematic error |
| Verification (vision) | Pixel HSV verifier AND independent Gemini Vision verifier with verifier-only prompt; AND-consensus | `src/verify_vision_dual.py` (Task 3) | Verifier disagreement → human review queue |
| Evaluation | Stratified gold-label benchmark, intra-annotator IAA via temporal re-labeling | `src/benchmark/` (Task 4 — pending) | Single-annotator ceiling |

## Known Quality Issues Closed By This Upgrade

- **Edge #5 in `microbe_feature_relations.jsonl`**: `gut bacterial clpb-like gene function → body_fat`. The microbe NER (`d4data/biomedical-ner-all`) tagged a gene-function noun phrase as an organism; the substring vocab filter and Gemini self-consistency gate did not catch the entity-type error. Task 1's UMLS TUI gate rejects entities that fail to ground to a microbe-class Semantic Type. Audit re-run pending after this session's commit.
- **`_FEATURE_VOCAB` recall ceiling**: substring matching against a 25-alias vocabulary excluded paraphrastic mentions ("loss of muscle mass at L3", "diminished cross-sectional muscle area"). Task 2 replaces with dense retrieval.
- **VLM monoculture risk on figure verification**: pixel verifier alone gates Vision Track edges; same-model errors propagate undetected. Task 3 adds an independent Gemini Vision verifier with verifier-only prompt.

## Current Metrics (1,016-paper expanded corpus — pre-upgrade baseline)
- Papers: **1,016** (640 initial + 376 net-new from 4 new query lanes)
- Phenotype mentions: 5,721 (initial corpus)
- ASSOCIATED_WITH edges (phenotype→disease): **74** (72 initial + 2 from new lanes)
- Microbe-disease edges (signed): **29** total — 14 POSITIVELY_CORRELATED_WITH, 15 NEGATIVELY_CORRELATED_WITH
- CORRELATES_WITH edges: **9** total — 2 Vision Track (pixel-verified), 7 Text Track (Gemini 7/7 self-consistency)
  - **3 close three-hop paths**: Ruminococcus→sarcopenia (37 diseases), Peptostreptococcus stomatis→skeletal_muscle_index (7 diseases), Eubacterium→visceral_adipose_tissue (18 diseases)
  - **62 end-to-end Microbe→Feature→Disease traversable paths**
- BodyLocation nodes: 18, ImagingModality nodes: 5, ImageRef nodes: 1
- Total Neo4j export rows: **191**
- Tests passing: **46** (Vision Track + edge assembly; full suite 156)
- Gemini self-consistency rate (new corpus): **0.916**
- UMLS CUIs: merged into neo4j_relationships_microbe_expanded.csv, new_lanes.csv, microbe_merged.csv (29/29 Microbe→Disease rows enriched)

## Session 6 (2026-05-04) — Four-Task Structural Upgrade

### Frame
The 1,016-paper baseline pipeline was end-to-end functional but carried three named structural weaknesses surfaced during axis-scoping review:

1. NER produces edges from entity-type errors (e.g. Edge #5: `gut bacterial clpb-like gene function` accepted as a microbe).
2. Hand-curated `_FEATURE_VOCAB` substring filter has unmeasured recall — paraphrastic feature mentions are silently excluded.
3. Vision Track verification is single-modality (pixel-HSV); same-model errors in the proposer cannot be caught by a same-family verifier (monoculture risk).

### Changes Delivered
- `src/umls_validator.py` (new): `EntityGate` class; rejects entities that fail UMLS TUI grounding. Configurable accept set defaults to `{T007 Bacterium, T194 Archaeon, T204 Eukaryote}` for microbe class. Includes a deny-list for non-microbe eukaryotes (Homo sapiens, Mus musculus, common model organisms).
- `scripts/extract_microbe_feature_relations.py`: integrated UMLS gate before relation classification; dropped entities written to `artifacts/dropped_entities_*.jsonl` with `drop_reason` for audit.
- `src/feature_retrieval.py` (new): `BiomedEncoder` (BioClinical-ModernBERT-base, mean-pooled with attention mask, L2-normalized) + `FeatureCandidateRetriever` (FAISS index when available, numpy fallback). Per-feature τ threshold; calibration scaffold ready for Task 4 labeled data.
- `src/verify_vision_dual.py` (new): wraps existing `verify_heatmap_r_value` (pixel verifier) plus an independent Gemini Vision verifier with a verifier-only prompt at temperature 0. AND-consensus accepts; XOR routes to `artifacts/vision_review_queue.jsonl`.
- Tests: `tests/test_umls_validator.py`, `tests/test_feature_retrieval.py`, `tests/test_verify_vision_dual.py` (mocked Gemini client).

### Decisions
- **TUI policy**: accept `{T007, T194, T204}` for microbes; reject all known non-microbe eukaryote CUIs via explicit deny-list (humans, mice, rats). Trade-off: T204 is broad enough to include some host model organisms; deny-list is the targeted mitigation.
- **Embedding model**: BioClinical-ModernBERT-base (150M params, 8K context, 53.5B-token bio+clinical pretraining). MPS-feasible on M2.
- **Default τ**: 0.62 per feature, with calibration hook awaiting Task 4 labeled set.
- **Vision verifier independence**: same Gemini family (Pro for proposer, Flash for verifier), distinct prompts, temperature 0 on verifier. True cross-family verification (Claude Vision, local VLM) is documented as the upgrade path.
- **AND-consensus, not majority**: dual verifiers, both must agree. Disagreement is preserved (review queue), not silenced.

### Why these specific upgrades, in this order
- Task 1 (UMLS gate) first because it removes false-positive entities that contaminate every downstream stage; without it, Tasks 2 and 3 measure quality on a contaminated input.
- Task 2 (retrieval) second because it determines what sentences reach relation classification; recall floor changes downstream metrics.
- Task 3 (dual verifier) third because it tightens the precision floor on figure-derived edges, which are the most defensible publication-grade evidence in the pipeline.
- Task 4 (gold benchmark) last because it measures the system after Tasks 1–3 land; benchmarking before would measure a known-stale pipeline.

### Validations
- New module tests: 16 UMLS validator + 17 feature retrieval + 25 dual verifier = **58 new tests**, all passing.
- Full suite: **236 passed** (was 156 pre-upgrade) — no regressions.
- Backward-compat smoke: `scripts/extract_microbe_feature_relations.py --dry-run` (without `--umls-gate`) produces the same 13 candidates as the prior baseline. The Edge #5 surface (`gut bacterial clpb - like gene function`) is visible in the candidate list and will drop when `--umls-gate` is enabled.
- UMLS audit script (`scripts/audit_microbe_entities.py`): re-runs UMLS gate against `artifacts/microbe_feature_relations.jsonl`; must be run from Terminal.app per UMLS runtime policy. Live audit results pending.

## Session 5 (2026-04-03) — Vision Track Multi-Type Expansion

### Problem
Vision Track was heatmap-only. User confirmed: forest plots, scatter plots, and dot plots must also be processed to extract quantitative microbiome ↔ radiomics associations.

### Changes Delivered
**`src/index_figures.py`**
- Added `SCATTER_KEYWORDS` and `DOT_PLOT_KEYWORDS` sets
- `classify_figure()` now returns `scatter_plot` and `dot_plot` in addition to `heatmap` and `forest_plot`

**`src/propose_vision_qwen.py`**
- `DEFAULT_PROMPT_ID` = `qwen_heatmap_v2_json`
- Added `_build_prompt_forest(caption)`: extracts OR/HR/β + 95% CI fields + p_value; null value guidance
- Added `_build_prompt_scatter(caption)`: extracts annotated r/ρ value
- `_build_prompt(caption, topology)` dispatcher routes to correct prompt by figure type
- `_parse_qwen_output` extended: `effect_type`, `ci_lower`, `ci_upper`, `p_value` fields; OR/HR values not clamped to [-1,1]
- `QUALIFYING_TOPOLOGIES = {"heatmap", "forest_plot", "scatter_plot", "dot_plot"}` — `include_non_heatmap=False` now only skips topology="unknown"

**`src/verify_heatmap.py`**
- Added `verify_forest_plot_association(effect_size, ci_lower, ci_upper, effect_type, null_value)`: CI-based verification — verified when CI does not cross null value (1.0 for OR/HR, 0.0 for β/r). No pixel analysis needed.
- `_verification_from_proposal()` routes by topology: `forest_plot` → CI verification; all others → pixel-color verification

**`scripts/run_vision_pipeline.py`** (new file, untracked)
- Full pipeline orchestrator: fetch PMC figures → classify + filter → cost estimate → VLM propose → verify → summary
- `_QUALIFYING_TOPOLOGIES` and `_caption_suggests_qualifying()` covering all four types
- Default backend: `qwen_api` pointing to Gemini OpenAI-compatible endpoint
- `--dry-run`, `--skip-fetch`, `--pmcids`, `--tolerance`, `--fetch-limit` flags

**`scripts/fetch_pmc_figures.py`** (new file, untracked)
- Downloads PMC figures + captions for each PMCID
- `--heatmap-only` caption filter, `--pmcids` flag for targeted runs

**`tests/test_propose_vision_qwen.py`**
- 17 new tests covering: forest prompt fields, scatter prompt fields, dispatcher routing, CI parsing, OR not clamped, `_extract_first_json_object` edge cases
- Renamed `test_skips_non_heatmap_by_default` → `test_skips_unknown_topology_by_default` (forest_plot is now qualifying)

### Validations
- `conda run -n base python -m pytest tests/test_propose_vision_qwen.py tests/test_assemble_edges.py -v` → **46/46 passed**

### Decisions
- Forest plot verification: CI-based, not pixel-based. Verified = CI excludes null value.
- VLM backend: Gemini via OpenAI-compatible API (`--backend qwen_api`); Qwen local impossible on 8GB M2 (~14GB needed)
- `.env` file is NOT auto-loaded — must `set -a && source .env && set +a` before `conda run`
- Model selection for bulk Vision Track run: benchmark flash-lite vs flash on 3 papers before committing full corpus

## Session 4 (2026-04-01) — UMLS Normalization + Vision Track v1
- UMLS resolved: scispacy 0.6.x `add_pipe` fix; 96%/83% CUI coverage; run from Terminal only
- Vision Track v1: `propose_vision_qwen.py` (v2 prompt), `verify_heatmap.py`, pixel-level colormap legend detection

## New Lanes (2026-03-30)
| Lane | Papers | Net-new | With PMCID |
|------|--------|---------|------------|
| `microbe_liver_radiomics` | 81 | ~77 | ~62 |
| `microbe_bone_dxa` | 200 | ~185 | ~134 |
| `microbe_lung_ct` | 43 | ~36 | ~24 |
| `microbe_colorectal_imaging` | 82 | ~80 | ~52 |
| **Total** | **406** | **376 net-new** | **253** |

## Locked Decisions
- Text phenotype-to-disease edges: `ASSOCIATED_WITH`
- Verified figure-derived edges: `CORRELATES_WITH`
- Bridge hypotheses: audit-only, never graph edges
- Microbe NER: `d4data/biomedical-ner-all` on MPS
- Relation model: Gemini 2.5 Flash-Lite via openai_compatible; self-consistency 0.896
- UMLS: post-processing via `scripts/apply_umls_to_entity_sentences.py` (Terminal only — not VSCode)
- Vision Track qualifying topologies: heatmap, forest_plot, scatter_plot, dot_plot

## Key Artifacts
- `artifacts/neo4j_relationships_microbe_expanded.csv` — 183 rows
- `artifacts/microbe_disease_edges.jsonl` — 12 signed microbe-disease pairs
- `artifacts/papers_microbe_merged_fulltext.jsonl` — 77 PMCIDs, source for Vision Track fetch
- `artifacts/vision_proposals_gemini_vision.jsonl` — 3 proposals (session 4 test run)
- `artifacts/verification_results_gemini_vision.jsonl` — 3 results (1 verified, 2 rejected)
- `docs/proposal/report_sanomap_radiomics_layer.tex` — report (PDF not yet compiled)

## What Is Complete
Full pipeline end-to-end on 1,016-paper corpus. Vision Track code complete for all four figure types. 46 tests green. Proposal current. Explorer live on GitHub Pages.

## Reasoning Surface

### Knowns
- The pipeline produced 9 `CORRELATES_WITH` edges (2 vision-pixel-verified + 7 text Gemini-7/7-self-consistency) on the 1,016-paper baseline.
- Edge #5 (`gut bacterial clpb-like gene function → body_fat`) is a confirmed entity-type error in published artifacts.
- `_FEATURE_VOCAB` is a hardcoded 25-alias substring filter (`scripts/extract_microbe_feature_relations.py:30-56`).
- `UMLSNormalizer` already wraps scispacy en_core_sci_lg + UMLS linker, returning `(cui, tui, similarity, official_name)` tuples.
- Verification is currently single-modality (pixel HSV vs colorbar).
- BioClinical-ModernBERT-base is loadable via transformers 5.0.0.dev0; faiss-cpu is not currently installed (numpy fallback in module).
- 46 vision+assemble tests + 156 full-suite tests are green pre-upgrade.

### Unknowns
- True precision/recall of the 9 accepted edges (no gold set yet — Task 4 is unstarted).
- Recall lost by the substring vocab vs embedding retrieval (no measurement before this session).
- Per-feature optimal τ for retrieval (defaulted to 0.62 pending labeled calibration data).
- Whether T204 (Eukaryote) acceptance creates a measurable false-positive rate even with the model-organism deny-list.
- Vision verifier disagreement rate on real figures (no observation yet — only 2 vision-verified edges in the corpus).

### Assumptions
- BioClinical-ModernBERT mean-pooled embeddings outperform substring matching on body-composition feature retrieval. Justified by domain-pretraining mass and 8K context, but not measured on this corpus.
- Gemini Flash with temperature 0 + verifier-only prompt produces less-correlated errors with Gemini Pro proposer than self-consistency on the same proposer. Reasonable on prompt-design grounds, but not formally independent.
- UMLS coverage is high enough on common gut microbes that the TUI gate's recall hit is bounded.

### Disconfirmation
- If UMLS gate drops > 30% of currently accepted edges in the audit re-run, the gate's similarity threshold (0.85) is too strict — recalibrate.
- If embedding retrieval at τ=0.62 returns < 50 candidates per common feature on the 1,016-paper corpus, retrieval is undertuned — sweep τ on a small dev set.
- If dual-verifier disagreement rate > 25% on the existing 2 vision edges, the Gemini Vision verifier prompt is wrong-shape (not actually doing verifier-only judgment) — redesign the prompt.
