#!/usr/bin/env python3
"""Apply junjslee Pass-1 overrides on top of the LLM suggestions.

Inputs:  artifacts/gold_set_v1_LABELED_pass1_SUGGESTIONS.jsonl
Output:  artifacts/gold_set_v1_LABELED_pass1.jsonl

Override decision (2026-05-07): BodyCompositionFeature must be
imaging-derived. BMI, waist-hip ratio, and trunk-fat distribution
without imaging context are anthropometric and excluded; bone mineral
density is retained because DXA is imaging.

For each affected record:
  - label              -> not_associated
  - evidence_type      -> null
  - quantitative       -> null
  - evidence_span      -> null
  - inferred_feature_canonical -> null
  - inferred_node_type -> null
  - annotator_notes    -> override reason
  - _suggestion_rationale + _suggested_by  -> retained as audit trail

The 7 affected record_ids are listed in OVERRIDES below.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "artifacts" / "gold_set_v1_LABELED_pass1_SUGGESTIONS.jsonl"
OUTPUT = ROOT / "artifacts" / "gold_set_v1_LABELED_pass1.jsonl"

# Reason -> (note text, list of record_ids)
OVERRIDES: dict[str, tuple[str, list[str]]] = {
    "WHR": (
        "Scope decision: WHR is anthropometric, not an imaging-based body composition feature. Rejected.",
        ["5b9e031f0ee108f6", "e4c9fc61f452de6e", "91655ab9d223b281"],
    ),
    "BMI": (
        "Scope decision: BMI is anthropometric, not imaging-based. Rejected as BodyCompositionFeature.",
        ["0b2f558a2e6e6e9b", "f5ae9ff4a1be993b", "1b8deaecd521e3b5"],
    ),
    "TRUNK_FAT": (
        "Scope decision: Trunk fat distribution without imaging context is treated as anthropometric. Rejected.",
        ["824fa73a6f0aa2c4"],
    ),
}

# Build flat record_id -> note map
NOTE_BY_ID: dict[str, str] = {}
for note, ids in OVERRIDES.values():
    for rid in ids:
        NOTE_BY_ID[rid] = note


def main() -> int:
    if not INPUT.exists():
        print(f"ERROR: input not found: {INPUT}")
        return 1

    rows = [json.loads(line) for line in INPUT.read_text().splitlines() if line.strip()]
    print(f"Loaded {len(rows)} suggestion rows from {INPUT.name}")

    overridden_ids: set[str] = set()
    for rec in rows:
        rid = rec["record_id"]
        if rid in NOTE_BY_ID:
            rec["label"] = "not_associated"
            rec["evidence_type"] = None
            rec["quantitative"] = None
            rec["evidence_span"] = None
            rec["inferred_feature_canonical"] = None
            rec["inferred_node_type"] = None
            rec["annotator_notes"] = NOTE_BY_ID[rid]
            overridden_ids.add(rid)

    missing = set(NOTE_BY_ID) - overridden_ids
    if missing:
        print(f"WARNING: {len(missing)} expected override IDs not present in input: {missing}")

    OUTPUT.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"Wrote {len(rows)} pass-1 rows ({len(overridden_ids)} overridden) → {OUTPUT.name}")

    # Distribution
    from collections import Counter
    c = Counter(r["label"] for r in rows)
    print("\nFinal Pass-1 label distribution:")
    for lab, n in c.most_common():
        print(f"  {lab}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
