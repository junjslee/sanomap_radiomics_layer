# Next Steps

Operational handoff. Update whenever priority, blocker, or milestone changes.

## Current State (2026-05-20, evening) — Phase-0 PILOT VERDICT: FAIL (vacuous precision, deterministic)

**TL;DR.** Local cross-family unanimous-N judge (medgemma:4b + qwen3:4b @ Q8 on 8 GB) returned **ABSTAIN on every observed record — 11/11 across both model families** (8 medgemma Phase A + 3 qwen3 Phase B before operator-authorized kill once the deterministic outcome was locked). `cross_family(ABSTAIN, *) = ABSTAIN` by spec §2C, so the §3 verdict is locked at **FAIL: "judge asserted nothing (vacuous precision)"**. This is the precision-first design correctly disconfirming the local-only premise on this gold set — not a bug, not a crash, a clean empirical answer. Hand-computed report: `artifacts/pilot/pilot_report_slice.json`.

**Task 5a complete** (harness hardening — necessary after the 2026-05-19 95-min crash): broad fail-closed (`except Exception` at the precision-safety boundary) + 120 s per-request OpenAI client timeout + per-record checkpoint + resume + `--fresh` CLI flag + `logging.warning` for observability. Commits `ef0c215` + `b8ed935`. Pilot suite 18/18, full repo regression **339/0**. Spec §3 corrected + locked (operator-confirmed precision-on-gold + 3 gold-anchored decisions). The Phase-0 build is production-quality; the verdict above is the verdict the operator-locked criterion produces.

**Pilot run detail (slice, 8 accepted_edge rows):** Phase A medgemma:4b 8/8 ABSTAIN; Phase B qwen3:4b 3/8 ABSTAIN before kill (slice idx 0,1,2 = all 3 thesis anchors). Cross-family: 2 of 3 anchors wrong (eubacterium→VAT and ruminococcus→sarcopenia both gold-positive, judge ABSTAIN); 1 of 3 "correct" by universal-abstain coincidence (peptostrep→SMI gold *not_associated*, judge ABSTAIN — the gold-negative anchor). Accuracy 2/8 = 0.25 on the only 2 gold-non-assertable rows. The crashed 2026-05-19 full run corroborates: its 1 completed qwen3 record was also ABSTAIN. 12 ABSTAIN observations across 2 independent runs, 2 model families, 0 ASSERTs.

**GitHub durability:** branch pushed and tracking — `https://github.com/junjslee/sanomap_radiomics_layer/tree/feat/precision-first-phase0` @ `b8ed935`. `.episteme/advisory-surface` activated for this project (operator-authorized opt-out from the reasoning-surface classifier; reversible by `rm .episteme/advisory-surface`). All work is off-machine.

### Operator decisions pending (clear in one pass)

**1. Spec §3 fallback path (the verdict's required next action — recommended: (d) diagnose-first):**
- (a) loosen within-model unanimity (4-of-5 majority instead of 5-of-5) — deviates from MINERVA's all-agree contract; doesn't address per-sample variance root cause.
- (b) reduce `n_samples` 5→3 — minor; if temp-0 disagreement is the cause, fewer samples helps only marginally and weakens the precision claim.
- (c) defer to MGH unquantized compute (spec G upgrade path) — biggest lever; full-precision MedGemma-1.5/Qwen3 on stronger hardware likely addresses any per-sample disagreement; requires access setup.
- **(d) diagnose first — RECOMMENDED.** The harness emits no per-sample logs, so we can't distinguish whether (i) the 5 samples are emitting *different* `(relation_type, sign)` tuples breaking unanimity, (ii) at least one sample is itself returning ABSTAIN, or (iii) parse-fail is cascading to ABSTAIN via the broad boundary. Implement **5b: per-sample debug logging** behind a `--debug-samples` flag, run a single record, observe. ~30 min of work, then choose (a)/(b)/(c) on evidence not speculation.

**2. Known harness gap (5b-class, not blocking the §3 decision but worth fixing before any remediated rerun):** `timeout=120.0` on the OpenAI client is httpx's *per-byte* read timeout, not a wall-clock total. Slow-trickle Ollama responses bypass it (the 2026-05-19 crash root cause). The 5a fix did not patch this — the universal-ABSTAIN pattern hid it. Real fix = `httpx.Timeout(...)` with explicit connect/read/pool, or wrap the chat call in a wall-clock timer.

**3. Still parked from earlier sessions:**
- **WS-1**: `[Pasted text #1 +8 lines]` from the first session message never arrived.
- **WS-6**: does `pipeline_tracking.md` mention confer "do-not-move" on artifact files? Audit-only scaffold landed; the 26 vs ~90 file decision is yours.
- **chkpt→Conventional consolidation**: 28 `chkpt:` interleaved with 8 Conventional commits on the *pushed* branch. Consolidating before any PR is now a force-push history rewrite — needs explicit operator authorization.
- **Advisory-surface opt-out**: `.episteme/advisory-surface` durable until you `rm` it. Remove before next high-impact op if you want the classifier back enforcing.

### Resume commands (after §3 decision)
```bash
# RECOMMENDED — option (d), diagnose first:
#   1. Add per-sample logging to src/pilot/local_judge.py (5b): in _one_sample, emit
#      logging.debug("sample %d: decision=%s relation_type=%s sign=%s", idx, v.decision, v.relation_type, v.sign)
#      and a --debug-samples CLI flag on run_pilot that enables DEBUG level.
#   2. Run on one record, observe the 5 samples:
#      conda run -n base python -m src.pilot.run_pilot \
#        --gold artifacts/pilot/accepted_edge_only.jsonl \
#        --checkpoint /tmp/diag_ckpt.jsonl --fresh --debug-samples 2>&1 | grep 'sample '
#   3. Read the per-sample tuples; decide (a)/(b)/(c) based on what's broken.

# Option (c) MGH compute path is the deferred-to-better-hardware alternative; spec G makes that a rerun, not a rebuild.
```

---

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
