# Artifact Explorer

A lightweight in-browser viewer for the JSONL artifacts emitted by the
phenotype-axis pipeline. It loads a local JSONL file and lets you filter
records by subject, disease or context, phenotype, or PMID.

> **Data source (2026-05-21).** `data.jsonl` is now regenerated from the
> canonical Stage-A graph export at `artifacts/graph_export/` (189 rows /
> 99 nodes, post-audit truth) via `scripts/build_explorer_data.py`. The
> prior frozen 2026-04-05 snapshot is preserved at
> `data.jsonl.frozen_2026_04_05.bak` for reference.
>
> Stage B v2 (next, per `docs/PLAN.md` Status 2026-05-21): expose the 6
> canonical Cypher queries (in `src/graph_queries.py`) as named one-click
> traversals, add evidence drill-down to figure refs, and feature the 3
> thesis 3-hop closers.

## Usage

1. Open `docs/explorer/index.html` in a browser (double-clicking the file
   works in most environments).
2. Click **Choose a JSONL artifact** and select a JSONL output.
3. Adjust the filter inputs to narrow the focus. Filters match substrings
   and are case-insensitive.
4. Use **Clear filters** to reset and see all loaded records again.

## Data schema hints

The explorer works best with artifacts that include at least some of these
fields:

- `pmid` or `PMID`
- `subject_node`, `microbe_or_signature`, or `microbe`
- `phenotype`, `canonical_feature`, `radiomic_feature`, or `object_node`
- `disease`, `disease_context`, or `object_node`
- `relation_type`, `graph_rel_type`, or `not_for_graph_ingestion`
- `evidence`, `evidence_fragments`, `evidence_sentence`, or `sentence_text`

Artifacts in this repo that load well:

- `relation_aggregated*.jsonl`
- `verified_edges*.jsonl`
- `bridge_hypotheses*.jsonl`
- `phenotype_axis_candidates*.jsonl`

## Notes

- Only the first 200 matching rows are rendered; refine filters or slice the
  JSONL before loading to see more.
- The explorer runs in-browser with no backend and makes no network calls.
- `phenotype_axis_candidates*.jsonl` and `bridge_hypotheses*.jsonl` are
  audit-only artifacts, not graph edges.
