from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.artifact_utils import read_jsonl, write_jsonl, write_manifest
from src.schema_utils import SchemaValidationError, load_schema, validate_record
from src.types import EdgeCandidate, to_dict


def _edge_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _build_text_edges(text_mentions: list[dict[str, Any]]) -> list[EdgeCandidate]:
    edges: list[EdgeCandidate] = []
    for mention in text_mentions:
        pmid = str(mention.get("pmid") or "")
        feature = str(mention.get("canonical_feature") or "unknown_radiomic_feature")
        disease = mention.get("disease")
        confidence = float(mention.get("confidence") or 0.0)
        evidence = str(mention.get("evidence") or "")
        mention_id = str(mention.get("mention_id") or "")

        edge = EdgeCandidate(
            edge_id=_edge_id("text", pmid, feature, str(disease), mention_id),
            pmid=pmid,
            microbe=None,
            radiomic_feature=feature,
            disease=disease,
            relation_type="TEXT_ASSOCIATION",
            r_value=None,
            evidence_type="text_rule",
            confidence=confidence,
            figure_id=None,
            evidence=evidence,
            verification_passed=True,
        )
        edges.append(edge)
    return edges


def _build_vision_edges(
    vision_proposals: list[dict[str, Any]],
    include_unverified: bool,
) -> list[EdgeCandidate]:
    edges: list[EdgeCandidate] = []
    for proposal in vision_proposals:
        verification = proposal.get("verification") or {}
        verified = bool(verification.get("verified"))
        if not verified and not include_unverified:
            continue

        pmid = str(proposal.get("pmid") or "")
        figure_id = str(proposal.get("figure_id") or "")
        feature = str(proposal.get("radiomic_feature") or "unknown_radiomic_feature")
        disease = proposal.get("disease")
        microbe = proposal.get("microbe")
        proposed_r = proposal.get("proposed_r")
        support_fraction = float(verification.get("support_fraction") or 0.0)
        confidence = max(0.35, min(1.0, support_fraction if verified else support_fraction * 0.5))
        evidence = (
            f"Vision proposal {proposal.get('proposal_id', '')}; "
            f"reason={verification.get('reason', 'none')}"
        )

        edge = EdgeCandidate(
            edge_id=_edge_id("vision", pmid, figure_id, feature, str(disease), str(proposed_r)),
            pmid=pmid,
            microbe=microbe,
            radiomic_feature=feature,
            disease=disease,
            relation_type="VISION_CORRELATION",
            r_value=float(proposed_r) if proposed_r is not None else None,
            evidence_type="vision_verified" if verified else "vision_unverified",
            confidence=confidence,
            figure_id=figure_id or None,
            evidence=evidence,
            verification_passed=verified,
        )
        edges.append(edge)
    return edges


def build_edge_candidates(
    text_mentions: list[dict[str, Any]],
    vision_proposals: list[dict[str, Any]],
    include_unverified_vision: bool = False,
) -> list[EdgeCandidate]:
    all_edges = _build_text_edges(text_mentions) + _build_vision_edges(
        vision_proposals, include_unverified_vision
    )

    dedup: dict[tuple[str, str, str, str, str, str], EdgeCandidate] = {}
    for edge in all_edges:
        key = (
            edge.pmid,
            str(edge.microbe),
            edge.radiomic_feature,
            str(edge.disease),
            edge.relation_type,
            str(edge.figure_id),
        )
        prev = dedup.get(key)
        if prev is None:
            dedup[key] = edge
            continue
        if edge.confidence > prev.confidence:
            dedup[key] = edge
        elif edge.confidence == prev.confidence:
            merged = prev
            if edge.evidence not in merged.evidence:
                merged.evidence = f"{merged.evidence} || {edge.evidence}".strip(" |")
            dedup[key] = merged

    return list(dedup.values())


def _write_edges_csv(path: str | Path, edges: list[EdgeCandidate]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "edge_id",
        "pmid",
        "microbe",
        "radiomic_feature",
        "disease",
        "relation_type",
        "r_value",
        "evidence_type",
        "confidence",
        "figure_id",
        "verification_passed",
        "evidence",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for edge in edges:
            writer.writerow(to_dict(edge))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assemble graph-ready edge candidates.")
    parser.add_argument("--text-mentions", default="artifacts/text_mentions.jsonl")
    parser.add_argument("--vision-proposals", default="artifacts/vision_proposals.jsonl")
    parser.add_argument("--output-jsonl", default="artifacts/verified_edges.jsonl")
    parser.add_argument("--output-csv", default="artifacts/verified_edges.csv")
    parser.add_argument("--manifest-dir", default="artifacts/manifests")
    parser.add_argument("--include-unverified-vision", action="store_true")
    parser.add_argument("--validate-schema", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    text_mentions = read_jsonl(args.text_mentions) if Path(args.text_mentions).exists() else []
    vision_proposals = read_jsonl(args.vision_proposals) if Path(args.vision_proposals).exists() else []

    edges = build_edge_candidates(
        text_mentions,
        vision_proposals,
        include_unverified_vision=args.include_unverified_vision,
    )

    if args.validate_schema:
        schema = load_schema("verified_edges.schema.json")
        for idx, edge in enumerate(edges):
            try:
                validate_record(to_dict(edge), schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"verified_edges[{idx}] invalid: {exc}") from exc

    jsonl_count = write_jsonl(args.output_jsonl, edges)
    _write_edges_csv(args.output_csv, edges)

    metrics = {
        "text_mentions_in": len(text_mentions),
        "vision_proposals_in": len(vision_proposals),
        "edges_out": jsonl_count,
        "vision_verified_edges": sum(1 for e in edges if e.relation_type == "VISION_CORRELATION" and e.verification_passed),
        "text_edges": sum(1 for e in edges if e.relation_type == "TEXT_ASSOCIATION"),
    }
    write_manifest(
        manifest_dir=args.manifest_dir,
        stage="assemble_edges",
        params={
            "text_mentions": args.text_mentions,
            "vision_proposals": args.vision_proposals,
            "include_unverified_vision": args.include_unverified_vision,
        },
        metrics=metrics,
        outputs={
            "verified_edges_jsonl": str(Path(args.output_jsonl).resolve()),
            "verified_edges_csv": str(Path(args.output_csv).resolve()),
        },
        command=" ".join(sys.argv),
    )

    print(json.dumps({"output": args.output_jsonl, "metrics": metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
