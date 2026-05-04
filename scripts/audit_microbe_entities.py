#!/usr/bin/env python3
"""Audit existing accepted edges against the UMLS TUI gate.

Reads ``artifacts/microbe_feature_relations.jsonl`` (or any JSONL with a
``source_node`` field), evaluates each microbe surface form against the
UMLS gate, and reports which edges would be dropped by Task 1.

This is the closure step for Task 1 (UMLS entity sanitization). The
expected outcome on the current corpus: ``gut bacterial clpb-like gene
function`` (Edge #5) appears in the dropped list.

Per ``docs/RUN_CONTEXT.md`` and ``docs/NEXT_STEPS.md``, run this from
Terminal.app, NOT from VSCode/Claude Code subprocesses. The scispacy +
UMLS KB load is ~5GB and process-isolation matters.

Usage:
    python scripts/audit_microbe_entities.py \\
        --input artifacts/microbe_feature_relations.jsonl \\
        --output artifacts/dropped_entities_audit.jsonl \\
        --report artifacts/umls_gate_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# Allow running as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.text_ner_minerva import UMLSNormalizer
from src.umls_validator import GroundedEntity, make_microbe_gate


def _load_records(path: Path, surface_field: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if not isinstance(rec, dict):
            continue
        if surface_field not in rec:
            continue
        rows.append(rec)
    return rows


def _audit(records: list[dict[str, Any]], surface_field: str, gate) -> list[tuple[dict, GroundedEntity]]:
    results: list[tuple[dict, GroundedEntity]] = []
    seen: dict[str, GroundedEntity] = {}
    for rec in records:
        surface = str(rec.get(surface_field) or "").strip()
        if not surface:
            continue
        cached = seen.get(surface.lower())
        if cached is None:
            cached = gate.evaluate(surface)
            seen[surface.lower()] = cached
        results.append((rec, cached))
    return results


def _write_dropped(out_path: Path, dropped: list[tuple[dict, GroundedEntity]]) -> None:
    with out_path.open("w") as f:
        for rec, grounded in dropped:
            payload = {
                "record_id": rec.get("record_id"),
                "pmid": rec.get("pmid"),
                "source_node": rec.get("source_node"),
                "target_node": rec.get("target_node"),
                "rel_type": rec.get("rel_type"),
                "drop_reason": grounded.drop_reason,
                "grounding": grounded.as_dict(),
            }
            f.write(json.dumps(payload) + "\n")


def _write_report(report_path: Path, results: list[tuple[dict, GroundedEntity]]) -> dict[str, Any]:
    total = len(results)
    accepted = sum(1 for _, g in results if g.accepted)
    dropped = total - accepted
    by_reason: Counter[str] = Counter()
    by_surface: Counter[str] = Counter()
    for _, g in results:
        if not g.accepted:
            by_reason[g.drop_reason] += 1
            by_surface[g.surface.lower()] += 1
    drop_rate = (dropped / total) if total else 0.0
    report = {
        "total_records": total,
        "accepted": accepted,
        "dropped": dropped,
        "drop_rate": round(drop_rate, 4),
        "by_reason": dict(by_reason),
        "top_dropped_surfaces": by_surface.most_common(20),
    }
    report_path.write_text(json.dumps(report, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path,
                        help="Path for dropped-entity audit JSONL")
    parser.add_argument("--report", type=Path, default=None,
                        help="Path for summary JSON report")
    parser.add_argument("--surface-field", default="source_node",
                        help="JSONL field containing the microbe surface form")
    parser.add_argument("--min-similarity", type=float, default=0.85)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: input not found: {args.input}", file=sys.stderr)
        return 1

    print(f"Loading records from {args.input}...", flush=True)
    records = _load_records(args.input, args.surface_field)
    print(f"  {len(records)} records loaded", flush=True)

    print("Loading UMLS KB (scispacy en_core_sci_lg + UMLS linker, ~5GB, ~30s)...",
          flush=True)
    normalizer = UMLSNormalizer(enabled=True)
    if not normalizer.available:
        print("ERROR: UMLS linker not available. Check scispacy install.",
              file=sys.stderr)
        return 1
    print("  UMLS KB ready.", flush=True)

    gate = make_microbe_gate(normalizer, min_similarity=args.min_similarity)

    print(f"Auditing {len(records)} records against microbe-class TUI gate "
          f"(accept={sorted(gate.accepted_tuis)}, deny={len(gate.deny_cuis)} CUIs, "
          f"min_sim={gate.min_similarity})...", flush=True)
    results = _audit(records, args.surface_field, gate)

    dropped = [(rec, g) for rec, g in results if not g.accepted]
    _write_dropped(args.output, dropped)
    print(f"  {len(dropped)}/{len(results)} dropped → {args.output}", flush=True)

    if args.report:
        report = _write_report(args.report, results)
        print(f"  Report → {args.report}", flush=True)
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
