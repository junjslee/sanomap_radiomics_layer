# Artifact Explorer

Use this lightweight interface to satisfy the professor’s “small tool” requirement by letting you open local JSONL artifacts from the phenotype-axis pipeline and browse them with filters for subject, disease or context, phenotype, or PMID.

## Usage
1. Open `docs/explorer/index.html` in your browser (double-clicking the file works in most environments).
2. Click **Choose a JSONL artifact** and select the JSONL output you want to explore.
3. Adjust the filter inputs to narrow down the focus. The filters match substrings without needing exact casing.
4. Use **Clear filters** to reset and see all loaded records again.

## Data schema hints
The explorer works best with artifacts that include at least some of these fields:

- `pmid` or `PMID`
- `subject_node`, `microbe_or_signature`, or `microbe`
- `phenotype`, `canonical_feature`, `radiomic_feature`, or `object_node`
- `disease`, `disease_context`, or `object_node`
- `relation_type`, `graph_rel_type`, or `not_for_graph_ingestion`
- `evidence`, `evidence_fragments`, `evidence_sentence`, or `sentence_text`

Useful examples in this repo include:

- `relation_aggregated*.jsonl`
- `verified_edges*.jsonl`
- `bridge_hypotheses*.jsonl`
- `phenotype_axis_candidates*.jsonl`

## Notes
- To keep the view responsive, only the first 200 matching rows are rendered; scroll further by refining filters or slicing the JSONL before loading.
- The explorer runs purely in-browser with no backend; sensitive data stays local and no network calls are made.
- `phenotype_axis_candidates*.jsonl` and `bridge_hypotheses*.jsonl` are audit-only artifacts, not direct graph edges.
