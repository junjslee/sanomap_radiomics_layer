"""
Post-processing pass: apply UMLS normalization to relation_input JSONL files.

Runs only the UMLS KB (no NER models) so memory stays under 8GB.
Reads relation_input JSONL (which has flat 'microbe' and 'disease' text fields),
fills in disease_cui / microbe_cui (and adds tui / similarity / official_name).
Does NOT filter rows — preserves full coverage.

Usage:
    python scripts/apply_umls_to_entity_sentences.py \
        --input artifacts/relation_input_microbe_expanded.jsonl \
        --output artifacts/relation_input_microbe_expanded_umls.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.text_ner_minerva import DISEASE_TUIS, UMLSNormalizer

MICROBE_TUIS = {"T007"}  # T007 = Bacterium


def apply_umls(row: dict, normalizer: UMLSNormalizer) -> dict:
    out = dict(row)
    disease_text = (row.get("disease") or "").strip()
    microbe_text = (row.get("microbe") or row.get("subject_node") or "").strip()

    if disease_text:
        r = normalizer.normalize(disease_text, allowed_tuis=DISEASE_TUIS)
        if r is None:
            # Retry without TUI restriction for edge cases
            r = normalizer.normalize(disease_text, allowed_tuis=None)
        if r:
            out["disease_cui"] = r.get("cui")
            out["disease_tui"] = r.get("tui")
            out["disease_umls_similarity"] = r.get("similarity")
            out["disease_official_name"] = r.get("official_name")

    if microbe_text:
        r = normalizer.normalize(microbe_text, allowed_tuis=MICROBE_TUIS)
        if r is None:
            r = normalizer.normalize(microbe_text, allowed_tuis=None)
        if r:
            out["microbe_cui"] = r.get("cui")
            out["microbe_tui"] = r.get("tui")
            out["microbe_umls_similarity"] = r.get("similarity")
            out["microbe_official_name"] = r.get("official_name")

    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    print("Loading UMLS KB (single process, ~5GB RAM, ~30s)...", flush=True)
    normalizer = UMLSNormalizer(enabled=True)
    if not normalizer.available:
        print("ERROR: UMLS linker not available. Check scispacy installation.", file=sys.stderr)
        sys.exit(1)
    print("UMLS KB ready.", flush=True)

    rows = [json.loads(l) for l in Path(args.input).read_text().splitlines() if l.strip()]
    print(f"Input rows: {len(rows)}", flush=True)

    enriched = [apply_umls(r, normalizer) for r in rows]

    cui_hits = sum(1 for r in enriched if r.get("disease_cui") or r.get("microbe_cui"))
    print(f"Rows with at least one CUI: {cui_hits}/{len(enriched)}", flush=True)

    Path(args.output).write_text("\n".join(json.dumps(r) for r in enriched) + "\n")
    print(f"Written: {args.output}", flush=True)


if __name__ == "__main__":
    main()
