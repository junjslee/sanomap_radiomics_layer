# Plan

## Current Goal (2026-05-04)
- Land four structural upgrades that convert the proof-of-concept pipeline into a research-defensible, measurable artifact:
  1. UMLS-grounded entity sanitization (rejects entity-type errors at NER post-processing)
  2. Embedding-based candidate retrieval (replaces hand-curated `_FEATURE_VOCAB`)
  3. Dual-verifier consensus for Vision Track (pixel + independent VLM)
  4. Gold-label benchmark (150 stratified instances, measured P/R/F1)
- Each gate is independently auditable; no edge reaches the graph without passing every applicable gate.

## Active Gating Items (2026-05-07, end of session)
- **Task 1 closed live**. UMLS audit drop rate 25% (2/8). Outputs in `artifacts/dropped_entities_audit.jsonl` + `artifacts/umls_gate_report.json`.
- **Task 2** (dense retrieval): implementation done; τ calibration is strictly downstream of Pass-2 gold labels.
- **Task 3 closed**. Vision verifier pivoted to local Qwen2.5-VL-3B via Ollama. Full smoke run on n=13: 7 AND-consensus ACCEPT, 6 REVIEW (XOR), 0 REJECT, 0 ERRORS. 28/28 unit tests still passing after `proposed_r=None` crash-guard added to `verify_heatmap_r_value` + classified as `INCONCLUSIVE`.
- **Task 4 Pass-1 closed**. 66-row authoritative `gold_set_v1_LABELED_pass1.jsonl` generated via Claude propose → junjslee review → 7 imaging-scope overrides. Schema bumped v1.0 → v1.1 (§ 6.9 imaging-derived rule). 14-day temporal window opens 2026-05-07; Pass-2 earliest 2026-05-21.

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
