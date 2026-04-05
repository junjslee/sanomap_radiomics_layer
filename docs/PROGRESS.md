# Progress

## Last Updated
2026-04-03 — Vision Track expanded to all qualifying figure types (heatmap, forest_plot, scatter_plot, dot_plot). Pipeline orchestrator complete. 46 tests green.

## Current Metrics (1,016-paper expanded corpus — final)
- Papers: **1,016** (640 initial + 376 net-new from 4 new query lanes)
- Phenotype mentions: 5,721 (initial corpus)
- ASSOCIATED_WITH edges (phenotype→disease): **74** (72 initial + 2 from new lanes)
- Microbe-disease edges (signed): **29** total — 14 POSITIVELY_CORRELATED_WITH, 15 NEGATIVELY_CORRELATED_WITH
- BodyLocation nodes: 18, ImagingModality nodes: 5, ImageRef nodes: 1
- Total Neo4j export rows: **183**
- Tests passing: **46** (Vision Track + edge assembly; full suite 156)
- Gemini self-consistency rate (new corpus): **0.916**

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
