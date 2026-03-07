from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.artifact_utils import read_jsonl, write_jsonl, write_manifest
from src.extract_radiomics_text import (
    BODYCOMP_FEATURES,
    IBSI_FEATURES,
    MICROBIAL_SIGNATURE_TERMS,
    MICROBE_GENUS_TERMS,
)
from src.journal_metrics import ImpactFactorResolver, resolve_paper_metrics
from src.schema_utils import SchemaValidationError, load_schema, validate_record
from src.types import BridgeHypothesis, EdgeCandidate, to_dict


BODYCOMP_CANONICAL = {feat["canonical"] for feat in BODYCOMP_FEATURES}
RADIOMIC_CANONICAL = {feat["canonical"] for feat in IBSI_FEATURES}
MICROBE_BINOMIAL_PATTERN = re.compile(r"\b([A-Z][a-z]{2,}\s[a-z][a-z\-]{2,})\b")
MICROBE_STOPWORDS = {
    "analysis",
    "cancer",
    "carcinoma",
    "disease",
    "lesion",
    "model",
    "response",
    "syndrome",
    "therapy",
    "tumor",
    "tumour",
}


def _edge_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _classify_feature(canonical_feature: str) -> tuple[str, str]:
    feature = _normalize_text(canonical_feature)
    if feature in BODYCOMP_CANONICAL:
        return "body_composition", "BodyCompositionFeature"
    return "radiomic", "RadiomicFeature"


def _classify_subject_node(raw_subject: Any) -> tuple[str | None, str | None]:
    subject = str(raw_subject or "").strip()
    if not subject:
        return None, None

    norm = _normalize_text(subject)
    for match in MICROBE_BINOMIAL_PATTERN.finditer(subject):
        candidate = _normalize_text(match.group(1))
        words = candidate.split()
        if (
            words
            and words[0] in MICROBE_GENUS_TERMS
            and words[-1] not in MICROBE_STOPWORDS
        ):
            return "Microbe", candidate

    for genus in sorted(MICROBE_GENUS_TERMS):
        if re.search(rf"\b{re.escape(genus)}\b", norm):
            return "Microbe", genus

    for term in sorted(MICROBIAL_SIGNATURE_TERMS, key=len, reverse=True):
        if term in norm:
            return "MicrobialSignature", term

    return "Microbe", norm


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
        feature = str(mention.get("canonical_feature") or "unknown_imaging_phenotype")
        disease = str(mention.get("disease") or "").strip()
        confidence = float(mention.get("confidence") or 0.0)
        evidence = str(mention.get("evidence") or "")
        mention_id = str(mention.get("mention_id") or "")
        claim_hint = mention.get("claim_hint")
        feature_family = str(mention.get("feature_family") or _classify_feature(feature)[0])
        feature_node_type = str(mention.get("node_type") or _classify_feature(feature)[1])
        meta = _paper_metadata(pmid, paper_index, resolver)

        if not disease:
            rejected += 1
            continue

        edge = EdgeCandidate(
            edge_id=_edge_id("text", pmid, feature, str(disease), mention_id),
            pmid=pmid,
            subject_node_type=feature_node_type,
            subject_node=feature,
            object_node_type="Disease",
            object_node=disease,
            graph_rel_type="ASSOCIATED_WITH",
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
            feature_family=feature_family,
            claim_hint=str(claim_hint) if claim_hint else None,
            assertion_level="direct_evidence",
        )
        edges.append(edge)
    return edges, rejected


def _disease_match(text_disease: Any, relation_disease: Any) -> bool:
    a = _normalize_text(str(text_disease or ""))
    b = _normalize_text(str(relation_disease or ""))
    if not a or not b:
        return False
    return a == b or a in b or b in a


def build_bridge_hypotheses(
    text_mentions: list[dict[str, Any]],
    relation_aggregated: list[dict[str, Any]],
    text_min_confidence: float,
    _paper_index: dict[str, dict[str, Any]],
    _resolver: ImpactFactorResolver | None,
) -> tuple[list[BridgeHypothesis], int]:
    hypotheses: list[BridgeHypothesis] = []
    rejected = 0

    mentions_by_pmid: dict[str, list[dict[str, Any]]] = {}
    for mention in text_mentions:
        if not _is_text_deterministically_supported(mention, text_min_confidence):
            continue
        pmid = str(mention.get("pmid") or "")
        if not pmid:
            continue
        mentions_by_pmid.setdefault(pmid, []).append(mention)

    for relation in relation_aggregated:
        if not bool(relation.get("accepted")):
            continue

        pmid = str(relation.get("pmid") or "")
        microbe = _normalize_text(str(relation.get("microbe") or ""))
        subject_node_type = str(relation.get("subject_node_type") or "").strip() or None
        subject_node = _normalize_text(str(relation.get("subject_node") or ""))
        disease = _normalize_text(str(relation.get("disease") or ""))
        if not pmid or not disease:
            rejected += 1
            continue
        if not subject_node:
            subject_node_type, subject_node = _classify_subject_node(microbe)
        if not subject_node_type or not subject_node:
            rejected += 1
            continue

        mentions = mentions_by_pmid.get(pmid, [])
        matched_mentions = [
            m for m in mentions if _disease_match(m.get("disease"), disease)
        ]
        if not matched_mentions:
            rejected += 1
            continue

        relation_label = str(relation.get("final_label") or "").lower()
        relation_evidence = str(relation.get("evidence") or "").strip()
        label_score = 1.0 if relation_label in {"positive", "negative"} else 0.5

        for mention in matched_mentions:
            feature = str(mention.get("canonical_feature") or "").strip() or "unknown_radiomic_feature"
            feature_family, phenotype_node_type = _classify_feature(feature)
            mention_conf = float(mention.get("confidence") or 0.0)
            mention_id = str(mention.get("mention_id") or "")
            confidence = max(0.40, min(1.0, 0.55 * mention_conf + 0.45 * label_score))
            bridge_reason = (
                "within-paper shared disease bridge; "
                "do not ingest as direct graph edge"
            )
            hypotheses.append(
                BridgeHypothesis(
                    hypothesis_id=_edge_id("bridge", pmid, subject_node, feature, disease, mention_id),
                    pmid=pmid,
                    microbe_or_signature=subject_node,
                    microbe_or_signature_type=subject_node_type,
                    phenotype=feature,
                    phenotype_node_type=phenotype_node_type,
                    disease=disease,
                    evidence_fragments=[
                        relation_evidence,
                        str(mention.get("evidence") or ""),
                    ],
                    bridge_reason=bridge_reason,
                    confidence=confidence,
                    not_for_graph_ingestion=True,
                )
            )

    return hypotheses, rejected


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
        feature = str(proposal.get("radiomic_feature") or "unknown_imaging_phenotype")
        disease = proposal.get("disease")
        raw_subject = proposal.get("microbe")
        subject_node_type, subject_node = _classify_subject_node(raw_subject)
        if not subject_node_type or not subject_node:
            rejected += 1
            continue
        proposed_r = proposal.get("candidate_r", proposal.get("proposed_r"))
        meta = _paper_metadata(pmid, paper_index, resolver)
        feature_family, feature_node_type = _classify_feature(feature)

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
            subject_node_type=subject_node_type,
            subject_node=subject_node,
            object_node_type=feature_node_type,
            object_node=feature,
            graph_rel_type="CORRELATES_WITH",
            microbe=subject_node if subject_node_type == "Microbe" else None,
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
            feature_family=feature_family,
            claim_hint=None,
            assertion_level="direct_evidence",
        )
        edges.append(edge)

    return edges, rejected


def build_edge_candidates(
    text_mentions: list[dict[str, Any]],
    vision_proposals: list[dict[str, Any]],
    relation_aggregated: list[dict[str, Any]] | None = None,
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
            edge.subject_node_type,
            edge.subject_node,
            edge.object_node_type,
            edge.object_node,
            edge.graph_rel_type,
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
        "subject_node_type",
        "subject_node",
        "object_node_type",
        "object_node",
        "graph_rel_type",
        "microbe",
        "radiomic_feature",
        "disease",
        "relation_type",
        "r_value",
        "evidence_type",
        "confidence",
        "figure_id",
        "verification_passed",
        "feature_family",
        "claim_hint",
        "assertion_level",
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
    return [
        {
            "source_node_type": edge.subject_node_type,
            "source_node": edge.subject_node,
            "target_node_type": edge.object_node_type,
            "target_node": edge.object_node,
            "rel_type": edge.graph_rel_type,
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


def _write_bridge_hypotheses(path: str | Path, hypotheses: list[BridgeHypothesis]) -> int:
    return write_jsonl(path, hypotheses)


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
    parser.add_argument("--relation-aggregated", default="artifacts/relation_aggregated.jsonl")
    parser.add_argument("--vision-proposals", default="artifacts/vision_proposals.jsonl")
    parser.add_argument("--verification-results", default="artifacts/verification_results.jsonl")
    parser.add_argument("--papers", default="artifacts/papers.jsonl")
    parser.add_argument("--output-jsonl", default="artifacts/verified_edges.jsonl")
    parser.add_argument("--output-csv", default="artifacts/verified_edges.csv")
    parser.add_argument("--output-neo4j-csv", default="artifacts/neo4j_relationships.csv")
    parser.add_argument("--output-bridge-hypotheses", default="artifacts/bridge_hypotheses.jsonl")
    parser.add_argument("--manifest-dir", default="artifacts/manifests")
    parser.add_argument("--include-unverified-vision", action="store_true")
    parser.add_argument("--text-min-confidence", type=float, default=0.6)
    parser.add_argument("--resolve-journal-metrics", action="store_true")
    parser.add_argument("--validate-schema", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    text_mentions = read_jsonl(args.text_mentions) if Path(args.text_mentions).exists() else []
    relation_aggregated = (
        read_jsonl(args.relation_aggregated) if Path(args.relation_aggregated).exists() else []
    )
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
    bridge_hypotheses_preview, bridge_rejected = build_bridge_hypotheses(
        text_mentions,
        relation_aggregated,
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
        bridge_schema = load_schema("bridge_hypotheses.schema.json")
        for idx, hypothesis in enumerate(bridge_hypotheses_preview):
            try:
                validate_record(to_dict(hypothesis), bridge_schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"bridge_hypotheses[{idx}] invalid: {exc}") from exc

    jsonl_count = write_jsonl(args.output_jsonl, edges)
    _write_edges_csv(args.output_csv, edges)
    neo4j_rows = _write_neo4j_relationships_csv(args.output_neo4j_csv, edges)
    bridge_hypothesis_count = _write_bridge_hypotheses(
        args.output_bridge_hypotheses,
        bridge_hypotheses_preview,
    )

    metrics = {
        "text_mentions_in": len(text_mentions),
        "relation_aggregated_in": len(relation_aggregated),
        "vision_proposals_in": len(vision_proposals),
        "verification_results_in": len(verification_results),
        "papers_in": len(papers),
        "text_edges_candidates": len(text_edges_preview),
        "bridge_hypotheses_candidates": len(bridge_hypotheses_preview),
        "vision_edges_candidates": len(vision_edges_preview),
        "text_rejected": text_rejected,
        "bridge_rejected": bridge_rejected,
        "vision_rejected": vision_rejected,
        "edges_out": jsonl_count,
        "neo4j_rows_out": neo4j_rows,
        "bridge_hypotheses_out": bridge_hypothesis_count,
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
            "relation_aggregated": args.relation_aggregated,
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
            "bridge_hypotheses_jsonl": str(Path(args.output_bridge_hypotheses).resolve()),
        },
        command=" ".join(sys.argv),
    )

    print(json.dumps({"output": args.output_jsonl, "metrics": metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
