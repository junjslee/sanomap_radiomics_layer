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
from src.journal_metrics import ImpactFactorResolver, resolve_paper_metrics
from src.schema_utils import SchemaValidationError, load_schema, validate_record
from src.types import EdgeCandidate, to_dict


def _edge_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _build_verification_index(verification_results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in verification_results:
        proposal_id = str(row.get("proposal_id") or "")
        if proposal_id:
            index[proposal_id] = row
    return index


def _build_paper_index(papers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in papers:
        pmid = str(row.get("pmid") or "")
        if pmid:
            index[pmid] = row
    return index


def _coerce_int_or_none(value: Any) -> int | None:
    if value in (None, "", "NA"):
        return None
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed


def _paper_metadata(
    pmid: str,
    paper_index: dict[str, dict[str, Any]],
    resolver: ImpactFactorResolver | None,
) -> dict[str, Any]:
    paper = paper_index.get(pmid, {})
    metrics = resolve_paper_metrics(paper, resolver=resolver)

    return {
        "journal": str(paper.get("journal") or "").strip() or None,
        "title": str(paper.get("title") or "").strip() or None,
        "pmcid": str(paper.get("pmcid") or "").strip() or None,
        "publication_year": _coerce_int_or_none(paper.get("year")),
        "impact_factor": metrics.impact_factor,
        "quartile": metrics.quartile,
        "issn": str(paper.get("issn") or "").strip() or None,
    }


def _is_text_deterministically_supported(mention: dict[str, Any], min_confidence: float) -> bool:
    confidence = float(mention.get("confidence") or 0.0)
    canonical_feature = str(mention.get("canonical_feature") or "").strip()
    evidence = str(mention.get("evidence") or "").strip()
    if confidence < min_confidence:
        return False
    if not canonical_feature:
        return False
    if not evidence:
        return False
    return True


def _build_text_edges(
    text_mentions: list[dict[str, Any]],
    text_min_confidence: float,
    paper_index: dict[str, dict[str, Any]],
    resolver: ImpactFactorResolver | None,
) -> tuple[list[EdgeCandidate], int]:
    edges: list[EdgeCandidate] = []
    rejected = 0
    for mention in text_mentions:
        if not _is_text_deterministically_supported(mention, text_min_confidence):
            rejected += 1
            continue

        pmid = str(mention.get("pmid") or "")
        feature = str(mention.get("canonical_feature") or "unknown_radiomic_feature")
        disease = mention.get("disease")
        confidence = float(mention.get("confidence") or 0.0)
        evidence = str(mention.get("evidence") or "")
        mention_id = str(mention.get("mention_id") or "")
        meta = _paper_metadata(pmid, paper_index, resolver)

        edge = EdgeCandidate(
            edge_id=_edge_id("text", pmid, feature, str(disease), mention_id),
            pmid=pmid,
            microbe=None,
            radiomic_feature=feature,
            disease=disease,
            relation_type="TEXT_ASSOCIATION",
            r_value=None,
            evidence_type="text_rule_verified",
            confidence=confidence,
            figure_id=None,
            evidence=evidence,
            verification_passed=True,
            journal=meta["journal"],
            title=meta["title"],
            pmcid=meta["pmcid"],
            publication_year=meta["publication_year"],
            impact_factor=meta["impact_factor"],
            quartile=meta["quartile"],
            issn=meta["issn"],
        )
        edges.append(edge)
    return edges, rejected


def _resolve_proposal_verification(
    proposal: dict[str, Any],
    verification_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    proposal_id = str(proposal.get("proposal_id") or "")
    if proposal_id and proposal_id in verification_index:
        return verification_index[proposal_id]

    nested = proposal.get("verification")
    if isinstance(nested, dict):
        return nested
    return {}


def _build_vision_edges(
    vision_proposals: list[dict[str, Any]],
    verification_index: dict[str, dict[str, Any]],
    include_unverified: bool,
    paper_index: dict[str, dict[str, Any]],
    resolver: ImpactFactorResolver | None,
) -> tuple[list[EdgeCandidate], int]:
    edges: list[EdgeCandidate] = []
    rejected = 0

    for proposal in vision_proposals:
        verification = _resolve_proposal_verification(proposal, verification_index)
        verified = bool(verification.get("pass_fail", verification.get("verified", False)))
        if not verified and not include_unverified:
            rejected += 1
            continue

        pmid = str(proposal.get("pmid") or "")
        figure_id = str(proposal.get("figure_id") or "")
        feature = str(proposal.get("radiomic_feature") or "unknown_radiomic_feature")
        disease = proposal.get("disease")
        microbe = proposal.get("microbe")
        proposed_r = proposal.get("candidate_r", proposal.get("proposed_r"))
        meta = _paper_metadata(pmid, paper_index, resolver)

        support_fraction = float(verification.get("support_fraction") or 0.0)
        confidence = max(0.35, min(1.0, support_fraction if verified else support_fraction * 0.5))

        reason = str(verification.get("reason_code", verification.get("reason", "none")))
        distance_metric = verification.get("distance_metric", verification.get("min_abs_error"))
        evidence = (
            f"Vision proposal {proposal.get('proposal_id', '')}; "
            f"reason={reason}; "
            f"distance_metric={distance_metric}"
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
            journal=meta["journal"],
            title=meta["title"],
            pmcid=meta["pmcid"],
            publication_year=meta["publication_year"],
            impact_factor=meta["impact_factor"],
            quartile=meta["quartile"],
            issn=meta["issn"],
        )
        edges.append(edge)

    return edges, rejected


def build_edge_candidates(
    text_mentions: list[dict[str, Any]],
    vision_proposals: list[dict[str, Any]],
    verification_results: list[dict[str, Any]] | None = None,
    include_unverified_vision: bool = False,
    text_min_confidence: float = 0.6,
    papers: list[dict[str, Any]] | None = None,
    resolve_journal_metrics: bool = False,
) -> list[EdgeCandidate]:
    verification_index = _build_verification_index(verification_results or [])
    paper_index = _build_paper_index(papers or [])
    resolver = ImpactFactorResolver() if resolve_journal_metrics else None

    text_edges, _ = _build_text_edges(
        text_mentions,
        text_min_confidence,
        paper_index,
        resolver,
    )
    vision_edges, _ = _build_vision_edges(
        vision_proposals,
        verification_index,
        include_unverified_vision,
        paper_index,
        resolver,
    )

    all_edges = text_edges + vision_edges

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
        "journal",
        "title",
        "pmcid",
        "publication_year",
        "impact_factor",
        "quartile",
        "issn",
        "evidence",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for edge in edges:
            writer.writerow(to_dict(edge))


def _neo4j_rows_from_edge(edge: EdgeCandidate) -> list[dict[str, Any]]:
    if edge.relation_type == "TEXT_ASSOCIATION":
        return [
            {
                "source_node_type": "RadiomicFeature",
                "source_node": edge.radiomic_feature,
                "target_node_type": "Disease",
                "target_node": edge.disease,
                "rel_type": "PREDICTS",
                "pmid": edge.pmid,
                "pmcid": edge.pmcid,
                "journal": edge.journal,
                "title": edge.title,
                "publication_year": edge.publication_year,
                "impact_factor": edge.impact_factor,
                "quartile": edge.quartile,
                "issn": edge.issn,
                "evidence": edge.evidence,
                "confidence": edge.confidence,
                "verification_passed": edge.verification_passed,
            }
        ]

    rows: list[dict[str, Any]] = []
    if edge.microbe:
        rows.append(
            {
                "source_node_type": "Microbe",
                "source_node": edge.microbe,
                "target_node_type": "RadiomicFeature",
                "target_node": edge.radiomic_feature,
                "rel_type": "CORRELATES_WITH",
                "pmid": edge.pmid,
                "pmcid": edge.pmcid,
                "journal": edge.journal,
                "title": edge.title,
                "publication_year": edge.publication_year,
                "impact_factor": edge.impact_factor,
                "quartile": edge.quartile,
                "issn": edge.issn,
                "evidence": edge.evidence,
                "confidence": edge.confidence,
                "verification_passed": edge.verification_passed,
            }
        )
    if edge.disease:
        rows.append(
            {
                "source_node_type": "RadiomicFeature",
                "source_node": edge.radiomic_feature,
                "target_node_type": "Disease",
                "target_node": edge.disease,
                "rel_type": "PREDICTS",
                "pmid": edge.pmid,
                "pmcid": edge.pmcid,
                "journal": edge.journal,
                "title": edge.title,
                "publication_year": edge.publication_year,
                "impact_factor": edge.impact_factor,
                "quartile": edge.quartile,
                "issn": edge.issn,
                "evidence": edge.evidence,
                "confidence": edge.confidence,
                "verification_passed": edge.verification_passed,
            }
        )
    return rows


def _write_neo4j_relationships_csv(path: str | Path, edges: list[EdgeCandidate]) -> int:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "source_node_type",
        "source_node",
        "target_node_type",
        "target_node",
        "rel_type",
        "pmid",
        "pmcid",
        "journal",
        "title",
        "publication_year",
        "impact_factor",
        "quartile",
        "issn",
        "evidence",
        "confidence",
        "verification_passed",
    ]

    row_count = 0
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for edge in edges:
            for row in _neo4j_rows_from_edge(edge):
                writer.writerow(row)
                row_count += 1
    return row_count


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assemble graph-ready edge candidates.")
    parser.add_argument("--text-mentions", default="artifacts/text_mentions.jsonl")
    parser.add_argument("--vision-proposals", default="artifacts/vision_proposals.jsonl")
    parser.add_argument("--verification-results", default="artifacts/verification_results.jsonl")
    parser.add_argument("--papers", default="artifacts/papers.jsonl")
    parser.add_argument("--output-jsonl", default="artifacts/verified_edges.jsonl")
    parser.add_argument("--output-csv", default="artifacts/verified_edges.csv")
    parser.add_argument("--output-neo4j-csv", default="artifacts/neo4j_relationships.csv")
    parser.add_argument("--manifest-dir", default="artifacts/manifests")
    parser.add_argument("--include-unverified-vision", action="store_true")
    parser.add_argument("--text-min-confidence", type=float, default=0.6)
    parser.add_argument("--resolve-journal-metrics", action="store_true")
    parser.add_argument("--validate-schema", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    text_mentions = read_jsonl(args.text_mentions) if Path(args.text_mentions).exists() else []
    vision_proposals = read_jsonl(args.vision_proposals) if Path(args.vision_proposals).exists() else []
    verification_results = (
        read_jsonl(args.verification_results) if Path(args.verification_results).exists() else []
    )
    papers = read_jsonl(args.papers) if Path(args.papers).exists() else []

    paper_index = _build_paper_index(papers)
    verification_index = _build_verification_index(verification_results)
    resolver = ImpactFactorResolver() if args.resolve_journal_metrics else None

    text_edges_preview, text_rejected = _build_text_edges(
        text_mentions,
        args.text_min_confidence,
        paper_index,
        resolver,
    )
    vision_edges_preview, vision_rejected = _build_vision_edges(
        vision_proposals,
        verification_index,
        args.include_unverified_vision,
        paper_index,
        resolver,
    )

    edges = build_edge_candidates(
        text_mentions,
        vision_proposals,
        verification_results=verification_results,
        include_unverified_vision=args.include_unverified_vision,
        text_min_confidence=args.text_min_confidence,
        papers=papers,
        resolve_journal_metrics=args.resolve_journal_metrics,
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
    neo4j_rows = _write_neo4j_relationships_csv(args.output_neo4j_csv, edges)

    metrics = {
        "text_mentions_in": len(text_mentions),
        "vision_proposals_in": len(vision_proposals),
        "verification_results_in": len(verification_results),
        "papers_in": len(papers),
        "text_edges_candidates": len(text_edges_preview),
        "vision_edges_candidates": len(vision_edges_preview),
        "text_rejected": text_rejected,
        "vision_rejected": vision_rejected,
        "edges_out": jsonl_count,
        "neo4j_rows_out": neo4j_rows,
        "vision_verified_edges": sum(
            1
            for e in edges
            if e.relation_type == "VISION_CORRELATION" and e.verification_passed
        ),
        "text_edges": sum(1 for e in edges if e.relation_type == "TEXT_ASSOCIATION"),
    }
    write_manifest(
        manifest_dir=args.manifest_dir,
        stage="assemble_edges",
        params={
            "text_mentions": args.text_mentions,
            "vision_proposals": args.vision_proposals,
            "verification_results": args.verification_results,
            "papers": args.papers,
            "include_unverified_vision": args.include_unverified_vision,
            "text_min_confidence": args.text_min_confidence,
            "resolve_journal_metrics": args.resolve_journal_metrics,
        },
        metrics=metrics,
        outputs={
            "verified_edges_jsonl": str(Path(args.output_jsonl).resolve()),
            "verified_edges_csv": str(Path(args.output_csv).resolve()),
            "neo4j_relationships_csv": str(Path(args.output_neo4j_csv).resolve()),
        },
        command=" ".join(sys.argv),
    )

    print(json.dumps({"output": args.output_jsonl, "metrics": metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
