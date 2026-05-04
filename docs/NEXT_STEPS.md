# Next Steps

Operational handoff. Update whenever priority, blocker, or milestone changes.

## Current State (2026-05-04)
- **Four-task structural upgrade** in scope and partially landed:
  - Task 1 (UMLS gate): implemented `src/umls_validator.py` + integration; audit re-run pending Terminal-app session
  - Task 2 (dense retrieval): implemented `src/feature_retrieval.py`; corpus encoding pass + τ calibration pending
  - Task 3 (dual verifier): implemented `src/verify_vision_dual.py`; live API test pending
  - Task 4 (gold benchmark): not started — next deliverable
- Pre-upgrade baseline: 191 Neo4j rows, 9 CORRELATES_WITH edges, 62 traversable Microbe→Feature→Disease paths.
- **236 tests passing** (was 156 pre-upgrade) — 58 new tests for `umls_validator`, `feature_retrieval`, `verify_vision_dual`. No regressions.
- `.env` file contains `GEMINI_API_KEY` but is NOT auto-loaded — must source before `conda run`.

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

## Priority 1 — UMLS audit re-run (Task 1 closure)

Run from Terminal.app:
```bash
set -a && source .env && set +a
conda run -n base python scripts/audit_microbe_entities.py \
    --input artifacts/microbe_feature_relations.jsonl \
    --output artifacts/dropped_entities_audit.jsonl \
    --report artifacts/umls_gate_report.json
```
Acceptance: `gut bacterial clpb-like gene function` appears in `dropped_entities_audit.jsonl` with `drop_reason=tui_or_similarity_fail`. Report should show drop rate by surface form.

If drop rate on existing accepted edges > 30%, recalibrate:
- inspect `umls_similarity` distribution of dropped entities
- relax `MIN_GROUNDING_SIMILARITY` from 0.85 to 0.75 if the dropped distribution is bimodal at low scores
- document the recalibration choice in PROGRESS.md

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

## Priority 3 — Live Gemini Vision verifier smoke test (Task 3 closure)

Cost: 1 API call per existing vision-track figure × 2 figures = ~$0.04 at Gemini Flash pricing. Bounded.

```bash
set -a && source .env && set +a
conda run -n base python -m src.verify_vision_dual \
    --pmcids PMC10605408,PMC11924647 \
    --proposals artifacts/vision_proposals_pipeline.jsonl \
    --output artifacts/vision_dual_verification.jsonl
```
Acceptance: Both currently-verified figures pass the dual gate. If either fails the Vision verifier, inspect the prompt-output to determine whether the disagreement is signal (verifier caught a real issue) or noise (prompt is wrong-shape).

## Priority 4 — Build gold-label benchmark (Task 4)

Next session deliverable. Tracked separately in `docs/benchmark/` (to be created):
- `docs/benchmark/annotation_schema.md` — written before annotation begins
- `artifacts/gold_set_v1.jsonl` — 150 stratified instances
- `src/benchmark/evaluate.py` — scorer

Stratification: 15 accepted + 50 near-miss + 35 hard-negative + 30 recall-probe + 20 random.

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
- UMLS TUI accept set `{T007, T194, T204}` for microbe class — change requires methods-section update
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

- **Immediate**: Priority 1 — Terminal.app run of `audit_microbe_entities.py`. Confirms Edge #5 fix.
- **Blockers**: None on Tasks 1-3. Task 4 blocked on annotation schema authoring.
- **Open Questions**:
  1. Does the user want T005 (Virus) added to TUI accept set for virome-axis future-proofing?
  2. Should faiss-cpu be added to the conda environment for production runs, or numpy-fallback sufficient until corpus exceeds 100k sentences?
  3. Should Task 4 annotation schema be drafted this session as a starter, or deferred?
