# Next Steps

Operational handoff. Update whenever priority, blocker, or milestone changes.

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

## Priority 3 — Local Qwen2.5-VL-3B vision verifier smoke (CLOSED 2026-05-07)

Smoke ran via `scripts/run_vision_dual_smoke_qwen.py` against `localhost:11434`. Result: 2/2 available figures got dual ACCEPT (pixel + Qwen AND-consensus PASS).
- `PMC10176953_Fig3` panel G — *Peptostreptococcus* ↔ DLCO/VA%pred, r=-0.407, Qwen color band "light blue", pixel distance 0.019.
- `PMC10176953_Fig6` panel A — *Haemophilus* ↔ 4th Ai, r=-0.6, Qwen color band "blue", pixel distance 0.0.

11 of 13 proposals skipped because figures aren't on disk (proposals point at a stale Desktop path; pre-existing data hygiene issue, not new). To grow the smoke n past 2, re-fetch the missing PMC figures into `artifacts/figures/` under the `{figure_id}.jpg` naming convention used by `_resolve_figure`.

If Qwen2.5-VL-3B disagreement rate climbs once the smoke n grows, evaluate upgrade path: (a) `qwen2.5vl:7b` (~8GB at 4-bit, tight on this machine) or (b) DashScope hosted `qwen2.5-vl-32b-instruct` (cents per call).

## Priority 4 — Review gold-set label SUGGESTIONS, then commit Pass 1 (user-driven)

Hybrid (computer-aided manual annotation) approach selected this session. Claude generated 66 suggestions to `artifacts/gold_set_v1_LABELED_pass1_SUGGESTIONS.jsonl` using `scripts/suggest_gold_set_labels.py`. Each row carries `_suggestion_rationale` for fast review.

Distribution (suggested, pre-review):
- not_associated: 40
- associated_negative: 12
- unclear (entity-type errors, § 6.8): 8
- associated_unsigned: 3
- associated_positive: 2
- no_association_explicit: 1

**Open scope decision** (4 rows depend on this): Do `bmi`, `waist_hip_ratio`, `trunk_fat_distribution` count as `BodyCompositionFeature`? Schema § 3 framing is imaging-derived; these are anthropometric. Affected: 5b9e031f0ee108f6, e4c9fc61f452de6e, 91655ab9d223b281 (WHR), 0b2f558a2e6e6e9b, f5ae9ff4a1be993b, 1b8deaecd521e3b5 (BMI), 824fa73a6f0aa2c4 (trunk fat). If excluded, those rows downgrade to `not_associated`.

```bash
# Step 1: Review the suggestions file row-by-row.
# For each row: check the _suggestion_rationale against the schema, accept or override.
# Strip the _suggestion_rationale + _suggested_by fields before saving as authoritative pass 1.
# Save to: artifacts/gold_set_v1_LABELED_pass1.jsonl

# Step 2: Wait 14 calendar days from your review-completion date
# (per § 7.2 of docs/benchmark/annotation_schema.md).

# Step 3: Pass 2 — re-label the same 66 rows WITHOUT consulting pass 1.
cp artifacts/gold_set_v1_UNLABELED.jsonl artifacts/gold_set_v1_LABELED_pass2.jsonl
# Hand-edit fresh; randomize row order if feasible.

# Step 4: Evaluate.
conda run -n base python -m src.benchmark.evaluate \
    --gold artifacts/gold_set_v1_LABELED_pass1.jsonl \
    --iaa-pass2 artifacts/gold_set_v1_LABELED_pass2.jsonl \
    --multi-class \
    --output artifacts/gold_set_v1_metrics.json
```

Acceptance: Cohen's κ (binary collapse) ≥ 0.80; report binary P/R/F1 with 95% Wilson CI.

**Methods-section disclosure**: pass 1 used computer-aided manual annotation (Claude proposed; junjslee reviewed, accepted, or overrode). Pass 2 is junjslee independent. Cohen's κ measures intra-annotator consistency on junjslee's two passes. The Claude suggestions are an annotation aid, not the oracle.

## Priority 5 — Compile Proposal PDF (deferred from prior session)

Still blocked on `pdflatex`:
```bash
brew install --cask basictex
# restart terminal, then:
cd docs/proposal
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

> **TL;DR:** Tasks 1-3 are coded and tested. Task 1 needs a Terminal.app audit run; Task 2 needs a small dev-set τ calibration; Task 3 needs a live API smoke test on the 2 existing vision figures. Then Task 4 (gold benchmark) becomes the next session's primary deliverable.

- **Immediate**: Priority 4 — hand-label `artifacts/gold_set_v1_UNLABELED.jsonl` (Pass 1). All upstream code is in place.
- **Blockers**: None on the codebase. Task 4 closure is annotator-time-bound (~4 hours pass 1 + 14-day wait + ~4 hours pass 2). Live API smokes (Priorities 1, 3) are unblocked but lower urgency than getting labeled data.
- **Open Questions**:
  1. Accept the 66-row v1 gold set, or expand entity-sentence inputs to recover 150 rows? Recommended: accept 66 + report wider CIs in Limitations.
  2. After hand-labeling, run UMLS audit (Task 1 closure) before evaluating — that may change which accepted edges sit in the accepted_edge stratum and therefore the metrics.
  3. After Pass 1 + Pass 2 labels exist and Cohen's κ is computed, draft `docs/benchmark/IAA_v1.md` with the disagreement audit per § 7.6 of the schema?
