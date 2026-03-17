# Relation Explorer

Use this lightweight interface to satisfy the professor’s “small tool” requirement by letting you open any local `relation_aggregated*.jsonl` (or similar) artifact and browse accepted relations with filters for microbe/subject, disease, feature, or PMID.

## Usage
1. Open `docs/explorer/index.html` in your browser (double-clicking the file works in most environments).
2. Click **Choose a relation JSONL artifact** and select the JSONL output you want to explore.
3. Adjust the filter inputs to narrow down the focus. The filters match substrings without needing exact casing.
4. Use **Clear filters** to reset and see all loaded records again.

## Data schema hints
The explorer expects objects that include at least one of these fields:

- `pmid` or `PMID`
- `subject_node` or `microbe`
- `disease`
- `feature_family`, `feature_title`, or `claim_hint`
- `evidence_sentence` or `sentence_text`

If your artifact uses different field names, you can open the file in a text editor and rename the keys to match the above schema before using the explorer.

## Notes
- To keep the view responsive, only the first 200 matching rows are rendered; scroll further by refining filters or slicing the JSONL before loading.
- The explorer runs purely in-browser with no backend; sensitive data stays local and no network calls are made.
