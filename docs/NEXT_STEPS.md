# Next Steps

Operational handoff. Update whenever priority, blocker, or milestone changes.

## Current State (2026-04-03)
- Vision Track: **code complete** for heatmap, forest_plot, scatter_plot, dot_plot
- Pipeline orchestrator: `scripts/run_vision_pipeline.py` — fetch → classify → propose → verify
- 46 tests passing (`conda run -n base python -m pytest tests/test_propose_vision_qwen.py tests/test_assemble_edges.py -v`)
- `.env` file contains `GEMINI_API_KEY` but is NOT auto-loaded — must source before `conda run`

## UMLS Runtime Note
**Always run UMLS scripts from Terminal.app (not VSCode terminal):**
```bash
conda activate base
python scripts/apply_umls_to_entity_sentences.py --input <in> --output <out>
```

## .env / API Key Note
Scripts use `os.environ.get("GEMINI_API_KEY")` — no dotenv loading. Source before running:
```bash
set -a && source .env && set +a
```

## Priority 1: Run Vision Track on Real Corpus

**Before full run — benchmark flash-lite vs flash on 3 papers:**
```bash
set -a && source .env && set +a
conda run -n base python scripts/run_vision_pipeline.py \
    --pmcids PMC10176953,PMC10605408,PMC11924647 \
    --model-id gemini-2.5-flash-lite-preview \
    --proposals-out artifacts/proposals_lite_test.jsonl \
    --verification-out artifacts/verify_lite_test.jsonl
```
Check `proposals_lite_test.jsonl` for garbled axis labels (prior failure: `"6th Ai"` from old prompt). If clean, proceed.

**Dry-run to see qualifying figures and cost estimate (no API calls):**
```bash
set -a && source .env && set +a
conda run -n base python scripts/run_vision_pipeline.py --dry-run
```

**Full run on merged fulltext corpus (77 PMCIDs):**
```bash
set -a && source .env && set +a
conda run -n base python scripts/run_vision_pipeline.py
```
Outputs: `artifacts/vision_proposals_pipeline.jsonl`, `artifacts/verification_results_pipeline.jsonl`

**After verified edges exist — merge into graph:**
```bash
conda run -n base python src/assemble_edges.py \
    --vision-proposals artifacts/vision_proposals_pipeline.jsonl \
    --vision-verification artifacts/verification_results_pipeline.jsonl
```

## Priority 2: Compile Proposal PDF
```bash
cd docs/proposal
pdflatex report_sanomap_radiomics_layer.tex
```
Note: fix `.tex` naming inconsistency before compiling — proposal uses `POSITIVELY_ASSOCIATED_WITH` but code uses `POSITIVELY_CORRELATED_WITH` for vision edges.

## Priority 3: Optional Improvements
- **Neo4j CUI properties**: merge CUI fields from `relation_input_*_umls.jsonl` into `neo4j_relationships_microbe_expanded.csv` for alias deduplication
- **NER upgrade**: benchmark `OpenMed/OpenMed-NER-SpeciesDetect-BioMed-109M` vs `d4data/biomedical-ner-all` on 5-paper subset

## Do Not Change Without Documented Reason
- `ASSOCIATED_WITH` for text-derived phenotype-to-disease edges
- `CORRELATES_WITH` for verified quantitative figure edges
- Bridge hypotheses as audit-only
- Direct-evidence-only graph policy
- QUALIFYING_TOPOLOGIES: `{heatmap, forest_plot, scatter_plot, dot_plot}`

## Runtime Notes
- Local Python: Conda `base`
- VLM backend: `qwen_api` → Gemini OpenAI-compatible endpoint (default in `run_vision_pipeline.py`)
- Qwen local: **impossible on 8GB M2** (~14GB FP16 needed)
- **Before any paid run: dry-run first and confirm cost estimate**
- UMLS: native Terminal only
