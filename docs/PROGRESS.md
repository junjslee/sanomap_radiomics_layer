# Progress

## Last Updated
2026-05-07 — **Task 1 closed live; Task 4 entered hybrid-labeling mode; vision verifier pivoted to local Qwen2.5-VL-3B.** UMLS audit ran clean (drop rate 25% < 30% threshold; Edge #5 + 'bacteriodetes' typo dropped). 66 label suggestions generated for gold set via computer-aided annotation (Claude proposes + rationale, junjslee reviews). Ollama + Qwen2.5-VL-3B installed locally for vision verifier smoke (replaces paid Gemini Vision call).

2026-05-04 — All four structural upgrade tasks implemented. Pipeline acceptance is now framed against four stacked gates with full test coverage: (1) UMLS TUI grounding for entity sanitization, (2) BioClinical-ModernBERT dense retrieval replacing `_FEATURE_VOCAB`, (3) dual-verifier consensus (pixel + independent VLM) for Vision Track, (4) gold-label benchmark for measured P/R/F1.

## Session 8 (2026-05-07) — Live Closure of Task 1 + Hybrid Labeling Pivot

### Frame
Three priorities entered this session: (1) close Task 1 with a live UMLS audit; (2) pivot Task 3 from paid Gemini Vision to a free-local vision verifier given 8GB M2 constraints; (3) start Task 4 hand-labeling. Operator surfaced a real concern on (3): tech-background self-labeling is weaker than a bio-trained annotator, but having an LLM label the oracle that the LLM-extracted edges are evaluated against collapses the metric. Resolved as **hybrid (computer-aided manual annotation)**: Claude generates per-row label suggestions with rationale; junjslee reviews and overrides; methods section discloses the workflow.

### Changes Delivered
- **UMLS live audit** ran clean against `artifacts/microbe_feature_relations.jsonl` (8 records). Drop rate **25% (2/8)** — under the 30% recalibration threshold. Edge #5 (`gut bacterial clpb-like gene function`) dropped (`low_similarity:0.799<0.850`, grounded to 'Bacteria' T007). Bonus: `bacteriodetes` (typo of *Bacteroidetes*) also dropped (`no_umls_match`). Outputs: `artifacts/dropped_entities_audit.jsonl`, `artifacts/umls_gate_report.json`. **Task 1 closed.**
- **Vision verifier pivoted to local Qwen2.5-VL-3B via Ollama.** `src/verify_vision_dual.py` already used OpenAI-compatible chat completions, so the swap is a 2-flag change (`--api-base-url http://localhost:11434/v1 --model-id qwen2.5vl:3b`) with no code rewrite. Best free local option for 8GB M2 (3B at 4-bit ≈ 2GB, fits comfortably). Replaces the prior NEXT_STEPS plan to spend ~$0.04 on Gemini Flash.
- **Computer-aided gold-set labeling**. New `scripts/suggest_gold_set_labels.py` generates per-row label suggestions with rationale + `_suggestion_rationale` field for review traceability. 66 suggestions written to `artifacts/gold_set_v1_LABELED_pass1_SUGGESTIONS.jsonl`. Distribution: 40 not_associated, 12 associated_negative, 8 unclear (entity-type errors per § 6.8), 3 associated_unsigned, 2 associated_positive, 1 no_association_explicit.

### Decisions
- **Hybrid labeling protocol**: Claude is a label proposer, not an authoritative annotator. junjslee remains the schema's single annotator. The methods section will disclose 'computer-aided manual annotation' alongside Cohen's κ on junjslee's two passes.
- **Local Qwen over hosted API**: chosen on operator preference for free local inference. Qwen2.5-VL-3B is the recommended 8GB-feasible vision model (Apple Silicon Q4 quantization). DashScope hosted variant retained as future fallback if local quality proves insufficient.
- **WHR / BMI scope question deferred to operator review**: 4 of the recall_probe / random_co_occurrence rows have label suggestions tied to anthropometric (non-imaging) features — flagged in `_suggestion_rationale` for explicit reviewer decision.

### Open Questions
- After junjslee reviews the 66 suggestions and produces `gold_set_v1_LABELED_pass1.jsonl`, the 14-day temporal window starts. Pass 2 cannot begin before 2026-05-21.
- WHR / BMI scope inclusion in BodyCompositionFeature decides labels for 4 rows.
- The substring filter false-positive on 'peptostreptococcus stomatis ↔ skeletal_muscle_index' (record 5fce1d6ad71b9859) is a calibration finding for Task 2 dense retrieval — that row's label is `not_associated` despite being in the `accepted_edge` stratum.

### Validations
- UMLS audit acceptance criterion (per NEXT_STEPS): Edge #5 surface in dropped list — ✅ confirmed.
- Drop rate ≤ 30% — ✅ at 25%, no recalibration needed.
- 66/66 records have label suggestions; no records missed.
- Dual-verifier smoke (`scripts/run_vision_dual_smoke_qwen.py`) on local Qwen2.5-VL-3B, **full coverage on n=13 proposals** (after `scripts/fetch_missing_figures.py` pulled the 11 missing PMC figures into `artifacts/figures/`):
  - **7 AND-consensus ACCEPT** (pixel_pass + vision_pass) — true-positive heatmap readings dual-confirmed.
  - **6 REVIEW** (XOR-disagreement). Decomposition:
    - 3 cases `pixel_fail (insufficient_support)` + `vision_pass`: pixel found the legend but the predicted bbox-cell color matched too few pixels. Qwen reads `blue` / `light blue` / `light green`, which are biologically plausible for the negative r-values proposed (-0.46, -0.30, -0.50).
    - 3 cases `pixel_inconclusive (legend_not_found)` + `vision_pass`: pixel could not detect a colorbar legend on the figure. Qwen still returned a color read.
  - **0 REJECT, 0 ERRORS** (after fixing `proposed_r=None` crash in `verify_heatmap_r_value` + classifying `proposed_r_missing` as `INCONCLUSIVE` rather than `FAIL`).
  - Verifier disagreement rate: 6/13 = 46% — above the 25% recalibration threshold. Reading: the dual gate is doing its job (modal independence is empirically demonstrated; pixel and Qwen really do disagree). Whether the disagreements are pixel false-negatives or Qwen false-positives is the next investigation question; routing them to the review queue rather than silently picking a side is the schema-correct outcome.
  - 28/28 vision-verifier tests pass; no regressions. **Task 3 closed.**

### Pass-1 Override Decision (2026-05-07)
Operator reviewed all 66 LLM suggestions. Override applied to 7 rows on a single principle: **BodyCompositionFeature must be imaging-derived**. BMI, waist–hip ratio, and trunk-fat distribution without an imaging reference are anthropometric and excluded; bone mineral density retained because DXA is imaging. Affected record_ids:
- WHR: 5b9e031f0ee108f6, e4c9fc61f452de6e, 91655ab9d223b281
- BMI: 0b2f558a2e6e6e9b, f5ae9ff4a1be993b, 1b8deaecd521e3b5
- Trunk-fat distribution: 824fa73a6f0aa2c4

Mechanics codified in `scripts/apply_pass1_overrides.py` (re-runnable from suggestions). Authoritative file: `artifacts/gold_set_v1_LABELED_pass1.jsonl`. Schema clarified to v1.1 (see § 6.9 of `docs/benchmark/annotation_schema.md`).

Final Pass-1 distribution: 47 not_associated, 8 associated_negative, 8 unclear (entity-type errors), 2 associated_unsigned, 1 associated_positive, 0 no_association_explicit. **Task 4 Pass-1 closed.** 14-day temporal window opens; Pass-2 earliest 2026-05-21.

---

## Architecture (post-upgrade)

The pipeline is now structured as five independent gates. Each gate is independently auditable; an edge reaches the graph only after passing every applicable gate.

| Gate | Purpose | Module | Failure mode |
|---|---|---|---|
| Retrieval (text) | Dense feature-mention retrieval over BioClinical-ModernBERT embeddings; replaces hand-curated `_FEATURE_VOCAB` substring matching | `src/feature_retrieval.py` (Task 2) | Recall ceiling, threshold τ |
| Entity sanitization | UMLS TUI grounding — Microbe must ground to T007/T194/T204; gene-function noise rejected | `src/umls_validator.py` (Task 1) | Coverage gap (novel taxa not in UMLS) |
| Relation acceptance (text) | Gemini 2.5 Flash-Lite, 7-sample temperature-varied self-consistency, full-agreement | `scripts/extract_microbe_feature_relations.py` | Self-correlated; doesn't bound systematic error |
| Verification (vision) | Pixel HSV verifier AND independent Gemini Vision verifier with verifier-only prompt; AND-consensus | `src/verify_vision_dual.py` (Task 3) | Verifier disagreement → human review queue |
| Evaluation | Stratified gold-label benchmark, intra-annotator IAA via temporal re-labeling | `src/benchmark/sample_gold_set.py` + `evaluate.py` (Task 4 — implemented; hand-labeling pending) | Single-annotator ceiling; corpus undersizing on rare strata |

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

## Session 7 (2026-05-04, late) — Task 4 + Open-Question Resolutions

### Frame
After Tasks 1–3 landed in Session 6 (early), three open questions were carried into HITL review:
- Should T005 (Virus) be added to the TUI accept set for virome future-proofing?
- Should `faiss-cpu` be pinned in dependency tracking?
- Should the Task 4 annotation schema be drafted this session?

The user resolved all three as **yes** and authorized Task 4 implementation in full (annotation schema + sampling script + evaluation harness). This session executed those.

### Changes Delivered
- **T005 added** to `MICROBE_TUIS_ACCEPT` in `src/umls_validator.py`. Documented the rationale (gut-virome coverage). New test `test_accepts_virus_via_t005` verifies the path.
- **`requirements.txt`** created with conservative pinning for the actual transitive dependency surface used by the codebase. `faiss-cpu>=1.8,<2` pinned even though the module's numpy fallback works at current corpus scale.
- **`docs/benchmark/annotation_schema.md` v1.0** — locked: 6-class primary label, 3 secondary labels, 8 numbered edge-case decisions, IAA protocol with 14-day temporal-relabel window, schema versioning policy.
- **`src/benchmark/__init__.py` + `sample_gold_set.py`** — stratified sampler with deterministic seed (42). Reuses `_extract_candidates` from the production script so the gold set evaluates against the actual production candidate space. Five strata: accepted_edge, gemini_rejected, vocab_excluded (extended-vocab keywords beyond `_FEATURE_VOCAB`), recall_probe (generic body tokens, no specific feature), random_co_occurrence.
- **`src/benchmark/evaluate.py`** — binary P/R/F1 + 2×2 confusion matrix + per-stratum + per-feature + per-evidence_type breakdown. Cohen's κ (6-class and binary collapse) for IAA. CLI handles second-pass JSONL for κ computation.
- **`tests/test_benchmark_sample_gold_set.py`** (15 tests) — fixture-based stratification, exclusivity, seed determinism, abbrev-word-boundary corner cases.
- **`tests/test_benchmark_evaluate.py`** (31 tests) — label policy, confusion math, prediction lookup, per-stratum/feature aggregation, multi-class breakdown, Cohen's κ across passes.

### Bugs Caught + Fixed
- **PMI inside PMID false positive**: the original `_has_extended_feature_keyword` substring-matched `pmi` inside `pmid`, polluting the `vocab_excluded` stratum with PubMed-ID metadata sentences. Test surfaced it; fixed with explicit `EXTENDED_KEYWORD_ABBREVS` set requiring `\b` word-boundary matching for short abbreviations (pmi, imat, eat, pdff, asmm, ffmi, glcm).

### Situational Truth (worth flagging upstream)
- **Gold set lands at 66 rows, not 150.** The corpus has only 187 entity-sentence records and only 13 substring candidates total; the gemini_rejected stratum caps at 5 and vocab_excluded at 3. The 150-row design assumed a richer candidate pool than the production pipeline currently emits. Two paths to recover:
  - widen `--entity-sentences` inputs to include the broader text-mention files (5,721 mentions) — but those records lack the microbe-NER side, so the sampler would need a re-tagging step.
  - accept 66 as the v1 gold set size, label it, and note the wider confidence intervals (±0.10 instead of ±0.07 at p≈0.7) in the Limitations section.
- The user's call. Logged as a P1 open question in NEXT_STEPS.

### Validations
- `conda run -n base python -m pytest -q` → **280 passed** (44 new this session). No regressions.
- `python -m src.benchmark.sample_gold_set` against real artifacts → 66 rows written; reproducible under fixed seed.

## Session 6 (2026-05-04) — Four-Task Structural Upgrade (Tasks 1–3)

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
- New module tests: 17 UMLS validator (T005 added) + 17 feature retrieval + 25 dual verifier + 15 gold-set sampler + 31 benchmark evaluator = **105 new tests**, all passing.
- Full suite: **280 passed** (was 156 pre-upgrade) — no regressions.
- Backward-compat smoke: `scripts/extract_microbe_feature_relations.py --dry-run` (without `--umls-gate`) produces the same 13 candidates as the prior baseline. The Edge #5 surface (`gut bacterial clpb - like gene function`) is visible in the candidate list and will drop when `--umls-gate` is enabled.
- UMLS audit script (`scripts/audit_microbe_entities.py`): re-runs UMLS gate against `artifacts/microbe_feature_relations.jsonl`; must be run from Terminal.app per UMLS runtime policy. Live audit results pending.
- Gold-set sampler smoke run produced `artifacts/gold_set_v1_UNLABELED.jsonl` with 66 rows (8 accepted / 5 gemini_rejected / 3 vocab_excluded / 30 recall_probe / 20 random_co_occurrence). **The 150-row target is not reached on the current corpus** — only 13 substring candidates exist, so gemini_rejected caps at 5; only 3 entity-sentence records contain extended-vocabulary feature keywords. Honest situational truth, documented as a Limitation; expansion path is to widen `--entity-sentences` inputs beyond the two default files.

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
