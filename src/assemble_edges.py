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
from src.span_cleanup import clean_disease_span, clean_subject_span
from src.types import (
    BodyLocationNode,
    BridgeHypothesis,
    EdgeCandidate,
    ImageRef,
    ImagingModalityNode,
    MicrobeDiseaseEdge,
    PhenotypeAxisCandidate,
    to_dict,
)


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
TEXT_EDGE_DISEASE_EXACT_REJECT = {
    "s disease",
    "all disease",
    "number of disease",
    "identifying disease",
    "any disease",
    "multidimensional syndrome",
    "disease",
    "cancer",
}
TEXT_EDGE_DISEASE_NORMALIZATION_PATTERNS = (
    (re.compile(r"^presence of\s+"), ""),
    (re.compile(r"^biopsy-proven\s+"), ""),
)
TEXT_EDGE_DISEASE_ALIAS_NORMALIZATIONS = {
    "mafld metabolic dysfunction-associated fatty liver disease": "metabolic dysfunction-associated fatty liver disease",
}
TEXT_EDGE_DISEASE_PREFIX_PATTERNS = (
    re.compile(r"^(?:is|are|was|were)\b"),
    re.compile(r"^(?:suggesting|revealed|triggering)\b"),
    re.compile(r"^such as\b"),
    re.compile(r"^as a measure of\b"),
    re.compile(r"^a specific measure of\b"),
    re.compile(r"^evidence for\b"),
    re.compile(r"^time points of\b"),
    re.compile(r"^may\b"),
    re.compile(r"^thus\b"),
    re.compile(r"^induced through\b"),
    re.compile(r"^modulation of\b"),
    re.compile(r"^rather than\b"),
    re.compile(r"^(?:the )?(?:development|treatment|mechanism)\b"),
    re.compile(r"^guidelines?\b"),
    re.compile(r"^the gut microbiota\b"),
    re.compile(r"^gut microbi(?:ota|ome)\b"),
    re.compile(r"^normal muscle mass\b"),
    re.compile(r"^dietary fiber intake\b"),
    re.compile(r"^vicious circle\b"),
    # Gerund / subordinating conjunction leads
    re.compile(r"^offering\b"),
    re.compile(r"^dependent\b"),
    re.compile(r"^preventing\b"),
    re.compile(r"^since\b"),
    re.compile(r"^because\b"),
    re.compile(r"^despite\b"),
    re.compile(r"^including\b"),
    re.compile(r"^hallmark of\b"),
    re.compile(r"^models? of\b"),
    re.compile(r"^improve\b"),
    # Population-prefix patterns
    re.compile(r"^individuals? with\b"),
    re.compile(r"^patients? with\b"),
    re.compile(r"^subjects? with\b"),
    re.compile(r"^controls? with(?:out)?\b"),
    re.compile(r"^participants? with(?:out)?\b"),
    re.compile(r"^people with(?:out)?\b"),
    re.compile(r"^samples? of\b"),
    re.compile(r"^from (?:individuals?|various|people)\b"),
    # Participle/adjective fragment leads without a disease head noun
    re.compile(r"^mediated\b"),
    re.compile(r"^grade\b"),
    re.compile(r"^[a-z]+-driven\b"),
    # Section-header words (structured abstracts)
    re.compile(r"^(?:abstract|introduction|aims?|background|abbreviations?|discussion|conclusion|objectives?|purpose|summary)\b"),
    # Preposition / conjunction leads not in _DISEASE_LEAD_STOPWORDS
    re.compile(r"^(?:according to|between|from|at the|depending|but|either|among|against|as a|like|when|particularly in|to (?:compare|the onset|protect))\b"),
    # Narrative / measurement fragment starters
    re.compile(r"^(?:consequently|subsequently|regardless|delays?|determine|findings?|investigating|early life|fold change|basal metabolic|androgen deprivation|flaxseed|biological substrate|cell division|amino acid ibd)\b"),
    # Clinical/pathology fragment leads
    re.compile(r"^mechanisms? of\b"),
    re.compile(r"^independent of\b"),
    re.compile(r"^known as\b"),
    re.compile(r"^indicate\b"),
    re.compile(r"^individual susceptibility\b"),
    re.compile(r"^influences? the\b"),
    re.compile(r"^roles?\b"),
    re.compile(r"^most prevalent\b"),
    re.compile(r"^multiple testing\b"),
    re.compile(r"^macrophage\b"),
    re.compile(r"^pan-"),
    re.compile(r"^picrosirius\b"),
    re.compile(r"^short-chain\b"),
    re.compile(r"^mm mercury\b"),
    re.compile(r"^succinate background\b"),
    re.compile(r"^tissue to\b"),
    # Protection/defense phrasing (not a disease concept)
    re.compile(r"^protection against\b"),
    re.compile(r"^all disease\b"),
    re.compile(r"^number of disease\b"),
    re.compile(r"^identifying disease\b"),
    re.compile(r"^organ dysfunction\b"),
    re.compile(r"^(?:f|na)\s"),
)
TEXT_EDGE_DISEASE_SUBSTRING_PATTERNS = (
    re.compile(r"\bcauses?\b"),
    re.compile(r"\bis a disease\b"),
    re.compile(r"\bwithout affecting\b"),
    re.compile(r"\bcontrolling\b"),
    re.compile(r"\blessens?\b"),
    re.compile(r"\baffect(?:s|ing)?\b"),
    re.compile(r"\binfluenc(?:e|ed)\b"),
    # Causal/directional finite verbs not caught by span_cleanup pre-filter
    re.compile(r"\bpromotes?\b"),
    re.compile(r"\binduces?\b"),
    re.compile(r"\bameliorates?\b"),
    re.compile(r"\bcontributes?\b"),
    re.compile(r"\bprevents?\b"),
    re.compile(r"\bmitigates?\b"),
    re.compile(r"\bin patients? without\b"),
    re.compile(r"\bsupplementation\b"),
    re.compile(r"\bhighlights?\b"),
    re.compile(r"\bpathways?\b"),
    re.compile(r"\bexposure\b"),
    re.compile(r"\bsubstrate\b"),
    re.compile(r"\btrigger\b"),
    re.compile(r"\bintervention\b"),
    re.compile(r"\bvisualize\b"),
    re.compile(r"\bstain\b"),
    re.compile(r"\bbackground\b"),
)
TEXT_EDGE_DISEASE_CONTEXT_TOKENS = {
    "development",
    "treatment",
    "mechanism",
    "guideline",
    "guidelines",
    "microbiota",
    "muscle",
    "intake",
    "circle",
    "intrinsic",
}
TEXT_EDGE_KEEP_INFLAMMATION_TERMS = {
    "low-grade chronic inflammation",
    "systemic inflammation",
}
TEXT_EDGE_OUTCOME_EXACT_REJECT = {
    "inflammation",
}
PHENOTYPE_DISEASE_LEAKAGE_TERMS = {
    canonical.replace("_", " ") for canonical in BODYCOMP_CANONICAL | RADIOMIC_CANONICAL
} | {
    "gut bacteria",
    "gut microbiome",
    "gut microbiota",
    "marrow adiposity",
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


def _clean_text_disease(raw_disease: Any) -> tuple[str | None, str | None]:
    cleaned, reason = clean_disease_span(raw_disease)
    if cleaned is None:
        return None, reason or "missing_disease"
    canonical = cleaned.canonical
    tokens = canonical.split()
    if len(tokens) > 1 and tokens[0] in {"a", "an", "the", "this", "that"}:
        canonical = " ".join(tokens[1:]).strip()

    for pattern, replacement in TEXT_EDGE_DISEASE_NORMALIZATION_PATTERNS:
        canonical = pattern.sub(replacement, canonical).strip()
    canonical = TEXT_EDGE_DISEASE_ALIAS_NORMALIZATIONS.get(canonical, canonical)

    recleaned, reclean_reason = clean_disease_span(canonical)
    if recleaned is None:
        return None, reclean_reason or "missing_disease"
    return recleaned.canonical, None


def _is_graph_eligible_text_disease(disease: str) -> bool:
    canonical = _normalize_text(disease)
    if not canonical or canonical in TEXT_EDGE_DISEASE_EXACT_REJECT:
        return False
    if any(pattern.search(canonical) for pattern in TEXT_EDGE_DISEASE_PREFIX_PATTERNS):
        return False
    if any(pattern.search(canonical) for pattern in TEXT_EDGE_DISEASE_SUBSTRING_PATTERNS):
        return False
    if canonical in TEXT_EDGE_OUTCOME_EXACT_REJECT:
        return False
    if canonical.endswith("inflammation") and canonical not in TEXT_EDGE_KEEP_INFLAMMATION_TERMS:
        return False
    if " and " in canonical:
        return False
    if any(
        canonical.startswith(f"{term} ")
        or canonical == term
        or f" {term} " in canonical
        for term in PHENOTYPE_DISEASE_LEAKAGE_TERMS
    ):
        return False
    tokens = canonical.split()
    if len(tokens) > 4 and set(tokens) & TEXT_EDGE_DISEASE_CONTEXT_TOKENS:
        return False
    return True


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
        disease, disease_reason = _clean_text_disease(mention.get("disease"))
        confidence = float(mention.get("confidence") or 0.0)
        evidence = str(mention.get("evidence") or "")
        mention_id = str(mention.get("mention_id") or "")
        claim_hint = mention.get("claim_hint")
        feature_family = str(mention.get("feature_family") or _classify_feature(feature)[0])
        feature_node_type = str(mention.get("node_type") or _classify_feature(feature)[1])
        meta = _paper_metadata(pmid, paper_index, resolver)

        if not disease or disease_reason is not None or not _is_graph_eligible_text_disease(disease):
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


def build_text_axis_candidates(
    text_mentions: list[dict[str, Any]],
    text_min_confidence: float,
) -> tuple[list[PhenotypeAxisCandidate], int]:
    candidates: list[PhenotypeAxisCandidate] = []
    rejected = 0

    for mention in text_mentions:
        if not _is_text_deterministically_supported(mention, text_min_confidence):
            rejected += 1
            continue

        raw_subject = str(mention.get("subject_node") or "").strip()
        if not raw_subject:
            rejected += 1
            continue

        subject_node_type = str(mention.get("subject_node_type") or "").strip()
        if not subject_node_type:
            inferred_type, inferred_subject = _classify_subject_node(raw_subject)
            subject_node_type = inferred_type or ""
            raw_subject = inferred_subject or raw_subject
        if subject_node_type not in {"Microbe", "MicrobialSignature"}:
            rejected += 1
            continue

        cleaned_subject, subject_reason = clean_subject_span(
            raw_subject,
            subject_node_type=subject_node_type,
        )
        if cleaned_subject is None or subject_reason is not None:
            rejected += 1
            continue

        feature = str(mention.get("canonical_feature") or "").strip()
        if not feature:
            rejected += 1
            continue
        feature_family, phenotype_node_type = _classify_feature(feature)
        confidence = float(mention.get("confidence") or 0.0)
        evidence = str(mention.get("evidence") or "").strip()
        if not evidence:
            rejected += 1
            continue

        disease_context, _ = _clean_text_disease(mention.get("disease"))
        if disease_context is not None and not _is_graph_eligible_text_disease(disease_context):
            disease_context = None
        mention_id = str(mention.get("mention_id") or "")
        claim_hint = mention.get("claim_hint")

        candidates.append(
            PhenotypeAxisCandidate(
                candidate_id=_edge_id(
                    "text-axis",
                    str(mention.get("pmid") or ""),
                    subject_node_type,
                    cleaned_subject.canonical,
                    feature,
                    str(disease_context or ""),
                    mention_id,
                ),
                mention_id=mention_id,
                pmid=str(mention.get("pmid") or ""),
                subject_node_type=subject_node_type,
                subject_node=cleaned_subject.canonical,
                phenotype=feature,
                phenotype_node_type=phenotype_node_type,
                feature_family=feature_family,
                disease_context=disease_context,
                evidence=evidence,
                confidence=confidence,
                claim_hint=str(claim_hint) if claim_hint else None,
                not_for_graph_ingestion=True,
            )
        )

    dedup: dict[tuple[str, str, str, str, str, str], PhenotypeAxisCandidate] = {}
    for candidate in candidates:
        key = (
            candidate.pmid,
            candidate.subject_node_type,
            candidate.subject_node,
            candidate.phenotype_node_type,
            candidate.phenotype,
            str(candidate.disease_context),
        )
        previous = dedup.get(key)
        if previous is None or candidate.confidence > previous.confidence:
            dedup[key] = candidate
            continue
        if candidate.confidence == previous.confidence and candidate.evidence not in previous.evidence:
            previous.evidence = f"{previous.evidence} || {candidate.evidence}".strip(" |")

    return list(dedup.values()), rejected


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


_LABEL_TO_REL_TYPE = {
    "positive": "POSITIVELY_ASSOCIATED_WITH",
    "negative": "NEGATIVELY_ASSOCIATED_WITH",
}


def build_microbe_disease_edges(
    relation_aggregated: list[dict[str, Any]],
    paper_index: dict[str, dict[str, Any]],
    resolver: ImpactFactorResolver | None,
) -> tuple[list[MicrobeDiseaseEdge], int]:
    edges: list[MicrobeDiseaseEdge] = []
    rejected = 0

    dedup: dict[tuple[str, str, str, str], MicrobeDiseaseEdge] = {}

    for relation in relation_aggregated:
        final_label = str(relation.get("final_label") or "").lower()
        if final_label not in _LABEL_TO_REL_TYPE:
            rejected += 1
            continue

        pmid = str(relation.get("pmid") or "")
        raw_microbe = str(relation.get("subject_node") or relation.get("microbe") or "").strip()
        raw_disease = str(relation.get("disease") or "").strip()
        if not pmid or not raw_microbe or not raw_disease:
            rejected += 1
            continue

        cleaned_subject, subject_reason = clean_subject_span(
            raw_microbe,
            subject_node_type=str(relation.get("subject_node_type") or "Microbe"),
        )
        if cleaned_subject is None or subject_reason is not None:
            rejected += 1
            continue

        disease, disease_reason = _clean_text_disease(raw_disease)
        if disease is None or disease_reason is not None or not _is_graph_eligible_text_disease(disease):
            rejected += 1
            continue

        subject_node_type = str(relation.get("subject_node_type") or "Microbe")
        graph_rel_type = _LABEL_TO_REL_TYPE[final_label]
        evidence = str(relation.get("evidence") or "").strip()
        confidence = float(relation.get("confidence") or 0.7)
        meta = _paper_metadata(pmid, paper_index, resolver)

        edge = MicrobeDiseaseEdge(
            edge_id=_edge_id("microbe-disease", pmid, cleaned_subject.canonical, disease, final_label),
            pmid=pmid,
            subject_node_type=subject_node_type,
            subject_node=cleaned_subject.canonical,
            object_node_type="Disease",
            object_node=disease,
            graph_rel_type=graph_rel_type,
            relation_direction=final_label,
            evidence=evidence,
            confidence=confidence,
            evidence_type="text_model_verified",
            assertion_level="direct_evidence",
            pmcid=meta["pmcid"],
            journal=meta["journal"],
            title=meta["title"],
            publication_year=meta["publication_year"],
        )

        key = (pmid, cleaned_subject.canonical, disease, final_label)
        prev = dedup.get(key)
        if prev is None:
            dedup[key] = edge
        elif edge.confidence > prev.confidence:
            dedup[key] = edge

    return list(dedup.values()), rejected


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


MODALITY_DICOM_CODES: dict[str, str] = {
    "CT": "CT",
    "MRI": "MR",
    "PET": "PT",
    "PET/CT": "PT",
    "US": "US",
    "XRAY": "DX",
    "DXA": "DXA",
}


def collect_imaging_backbone_nodes(
    text_mentions: list[dict[str, Any]],
) -> tuple[list[BodyLocationNode], list[ImagingModalityNode]]:
    body_locations: dict[str, BodyLocationNode] = {}
    modalities: dict[str, ImagingModalityNode] = {}

    for mention in text_mentions:
        bl = mention.get("body_location")
        if bl and isinstance(bl, str):
            bl_norm = bl.strip().lower()
            if bl_norm and bl_norm not in body_locations:
                body_locations[bl_norm] = BodyLocationNode(
                    node_id=f"body_location:{bl_norm}",
                    name=bl_norm,
                )

        mod = mention.get("modality")
        if mod and isinstance(mod, str):
            mod_norm = mod.strip().upper()
            if mod_norm and mod_norm not in modalities:
                modalities[mod_norm] = ImagingModalityNode(
                    node_id=f"modality:{mod_norm}",
                    name=mod_norm,
                    dicom_code=MODALITY_DICOM_CODES.get(mod_norm, mod_norm),
                )

    return list(body_locations.values()), list(modalities.values())


def build_imaging_backbone_neo4j_rows(
    text_mentions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for mention in text_mentions:
        feature = mention.get("canonical_feature", "")
        node_type = mention.get("node_type", "RadiomicFeature")
        bl = mention.get("body_location")
        mod = mention.get("modality")
        pmid = str(mention.get("pmid", ""))

        if bl and isinstance(bl, str):
            bl_norm = bl.strip().lower()
            key = f"{node_type}:{feature}:MEASURED_AT:{bl_norm}"
            if key not in seen:
                seen.add(key)
                rows.append({
                    "source_node_type": node_type,
                    "source_node": feature,
                    "target_node_type": "BodyLocation",
                    "target_node": bl_norm,
                    "rel_type": "MEASURED_AT",
                    "pmid": pmid,
                })

        if mod and isinstance(mod, str):
            mod_norm = mod.strip().upper()
            key = f"{node_type}:{feature}:ACQUIRED_VIA:{mod_norm}"
            if key not in seen:
                seen.add(key)
                rows.append({
                    "source_node_type": node_type,
                    "source_node": feature,
                    "target_node_type": "ImagingModality",
                    "target_node": mod_norm,
                    "rel_type": "ACQUIRED_VIA",
                    "pmid": pmid,
                })

    return rows


def collect_image_ref_nodes(
    vision_proposals: list[dict[str, Any]],
    verification_results: list[dict[str, Any]],
) -> list[ImageRef]:
    """Build ImageRef nodes from verified vision proposals."""
    verified_ids: set[str] = set()
    for vr in verification_results:
        if vr.get("verified") or vr.get("pass_fail"):
            pid = vr.get("proposal_id", "")
            if pid:
                verified_ids.add(pid)

    seen: set[str] = set()
    nodes: list[ImageRef] = []
    for vp in vision_proposals:
        proposal_id = vp.get("proposal_id", "")
        if proposal_id not in verified_ids:
            continue
        pmcid = str(vp.get("pmid") or vp.get("pmcid") or "")
        figure_id = str(vp.get("figure_id", ""))
        if not figure_id:
            continue
        # Use figure_id alone when pmcid is unavailable
        node_id = f"imageref:{pmcid}:{figure_id}" if pmcid else f"imageref:{figure_id}"
        if node_id in seen:
            continue
        seen.add(node_id)
        nodes.append(ImageRef(
            node_id=node_id,
            pmcid=pmcid,
            figure_id=figure_id,
            panel_id=vp.get("panel_id"),
            image_path=vp.get("image_path"),
            topology=None,
            modality=vp.get("modality"),
        ))
    return nodes


def build_image_ref_neo4j_rows(
    image_refs: list[ImageRef],
    vision_proposals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate REPRESENTED_BY edges: ImagingModality -> ImageRef."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    ref_by_figure: dict[str, ImageRef] = {}
    for ref in image_refs:
        ref_by_figure[ref.figure_id] = ref

    for vp in vision_proposals:
        figure_id = str(vp.get("figure_id", ""))
        ref = ref_by_figure.get(figure_id)
        if ref is None:
            continue
        modality = vp.get("modality")
        if not modality:
            continue
        mod_norm = modality.strip().upper()
        key = f"modality:{mod_norm}:REPRESENTED_BY:{ref.node_id}"
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "source_node_type": "ImagingModality",
            "source_node": mod_norm,
            "target_node_type": "ImageRef",
            "target_node": ref.node_id,
            "rel_type": "REPRESENTED_BY",
            "pmid": str(vp.get("pmid", "")),
        })
    return rows


def _write_bridge_hypotheses(path: str | Path, hypotheses: list[BridgeHypothesis]) -> int:
    return write_jsonl(path, hypotheses)


def _write_axis_candidates(path: str | Path, candidates: list[PhenotypeAxisCandidate]) -> int:
    return write_jsonl(path, candidates)


def _neo4j_row_from_microbe_disease_edge(edge: "MicrobeDiseaseEdge") -> dict[str, Any]:
    return {
        "source_node_type": edge.subject_node_type,
        "source_node": edge.subject_node,
        "target_node_type": edge.object_node_type,
        "target_node": edge.object_node,
        "rel_type": edge.graph_rel_type,
        "pmid": edge.pmid,
        "pmcid": edge.pmcid or "",
        "journal": edge.journal or "",
        "title": edge.title or "",
        "publication_year": edge.publication_year or "",
        "impact_factor": "",
        "quartile": "",
        "issn": "",
        "evidence": edge.evidence,
        "confidence": edge.confidence,
        "verification_passed": True,
    }


def _write_neo4j_relationships_csv(
    path: str | Path,
    edges: list[EdgeCandidate],
    imaging_backbone_rows: list[dict[str, Any]] | None = None,
    image_ref_rows: list[dict[str, Any]] | None = None,
    microbe_disease_edges: list["MicrobeDiseaseEdge"] | None = None,
) -> int:
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
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for edge in edges:
            for row in _neo4j_rows_from_edge(edge):
                writer.writerow(row)
                row_count += 1
        if imaging_backbone_rows:
            for row in imaging_backbone_rows:
                writer.writerow(row)
                row_count += 1
        if image_ref_rows:
            for row in image_ref_rows:
                writer.writerow(row)
                row_count += 1
        if microbe_disease_edges:
            for md_edge in microbe_disease_edges:
                writer.writerow(_neo4j_row_from_microbe_disease_edge(md_edge))
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
    parser.add_argument("--output-axis-candidates", default="artifacts/phenotype_axis_candidates.jsonl")
    parser.add_argument("--output-microbe-disease-edges", default="artifacts/microbe_disease_edges.jsonl")
    parser.add_argument("--output-body-locations", default="artifacts/body_location_nodes.jsonl")
    parser.add_argument("--output-imaging-modalities", default="artifacts/imaging_modality_nodes.jsonl")
    parser.add_argument("--output-image-refs", default="artifacts/image_ref_nodes.jsonl")
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
    axis_candidates_preview, axis_rejected = build_text_axis_candidates(
        text_mentions,
        args.text_min_confidence,
    )
    bridge_hypotheses_preview, bridge_rejected = build_bridge_hypotheses(
        text_mentions,
        relation_aggregated,
        args.text_min_confidence,
        paper_index,
        resolver,
    )
    microbe_disease_edges_preview, md_rejected = build_microbe_disease_edges(
        relation_aggregated,
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

    body_locations, imaging_modalities = collect_imaging_backbone_nodes(text_mentions)
    backbone_rows = build_imaging_backbone_neo4j_rows(text_mentions)

    image_refs = collect_image_ref_nodes(vision_proposals, verification_results)
    image_ref_rows = build_image_ref_neo4j_rows(image_refs, vision_proposals)

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
        axis_schema = load_schema("phenotype_axis_candidates.schema.json")
        for idx, candidate in enumerate(axis_candidates_preview):
            try:
                validate_record(to_dict(candidate), axis_schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"phenotype_axis_candidates[{idx}] invalid: {exc}") from exc
        md_schema = load_schema("microbe_disease_edges.schema.json")
        for idx, md_edge in enumerate(microbe_disease_edges_preview):
            try:
                validate_record(to_dict(md_edge), md_schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"microbe_disease_edges[{idx}] invalid: {exc}") from exc
        bl_schema = load_schema("body_location_nodes.schema.json")
        for idx, bl_node in enumerate(body_locations):
            try:
                validate_record(to_dict(bl_node), bl_schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"body_location_nodes[{idx}] invalid: {exc}") from exc
        mod_schema = load_schema("imaging_modality_nodes.schema.json")
        for idx, mod_node in enumerate(imaging_modalities):
            try:
                validate_record(to_dict(mod_node), mod_schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"imaging_modality_nodes[{idx}] invalid: {exc}") from exc
        image_ref_schema = load_schema("image_ref_nodes.schema.json")
        for idx, ir_node in enumerate(image_refs):
            try:
                validate_record(to_dict(ir_node), image_ref_schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"image_ref_nodes[{idx}] invalid: {exc}") from exc

    jsonl_count = write_jsonl(args.output_jsonl, edges)
    _write_edges_csv(args.output_csv, edges)
    neo4j_rows = _write_neo4j_relationships_csv(
        args.output_neo4j_csv, edges,
        imaging_backbone_rows=backbone_rows,
        image_ref_rows=image_ref_rows,
        microbe_disease_edges=microbe_disease_edges_preview,
    )
    bridge_hypothesis_count = _write_bridge_hypotheses(
        args.output_bridge_hypotheses,
        bridge_hypotheses_preview,
    )
    axis_candidate_count = _write_axis_candidates(
        args.output_axis_candidates,
        axis_candidates_preview,
    )
    md_edge_count = write_jsonl(args.output_microbe_disease_edges, microbe_disease_edges_preview)
    bl_count = write_jsonl(args.output_body_locations, body_locations)
    mod_count = write_jsonl(args.output_imaging_modalities, imaging_modalities)
    image_ref_count = write_jsonl(args.output_image_refs, image_refs)

    metrics = {
        "text_mentions_in": len(text_mentions),
        "relation_aggregated_in": len(relation_aggregated),
        "vision_proposals_in": len(vision_proposals),
        "verification_results_in": len(verification_results),
        "papers_in": len(papers),
        "text_edges_candidates": len(text_edges_preview),
        "axis_candidates": len(axis_candidates_preview),
        "bridge_hypotheses_candidates": len(bridge_hypotheses_preview),
        "vision_edges_candidates": len(vision_edges_preview),
        "text_rejected": text_rejected,
        "axis_rejected": axis_rejected,
        "bridge_rejected": bridge_rejected,
        "vision_rejected": vision_rejected,
        "md_rejected": md_rejected,
        "edges_out": jsonl_count,
        "neo4j_rows_out": neo4j_rows,
        "axis_candidates_out": axis_candidate_count,
        "bridge_hypotheses_out": bridge_hypothesis_count,
        "microbe_disease_edges_out": md_edge_count,
        "body_location_nodes_out": bl_count,
        "imaging_modality_nodes_out": mod_count,
        "imaging_backbone_neo4j_rows": len(backbone_rows),
        "image_ref_nodes_out": image_ref_count,
        "image_ref_neo4j_rows": len(image_ref_rows),
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
            "phenotype_axis_candidates_jsonl": str(Path(args.output_axis_candidates).resolve()),
            "bridge_hypotheses_jsonl": str(Path(args.output_bridge_hypotheses).resolve()),
            "microbe_disease_edges_jsonl": str(Path(args.output_microbe_disease_edges).resolve()),
            "body_location_nodes_jsonl": str(Path(args.output_body_locations).resolve()),
            "imaging_modality_nodes_jsonl": str(Path(args.output_imaging_modalities).resolve()),
            "image_ref_nodes_jsonl": str(Path(args.output_image_refs).resolve()),
        },
        command=" ".join(sys.argv),
    )

    print(json.dumps({"output": args.output_jsonl, "metrics": metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
