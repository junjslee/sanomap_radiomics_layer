from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.artifact_utils import read_jsonl, write_jsonl, write_manifest
from src.paper_text_utils import paper_text
from src.schema_utils import SchemaValidationError, load_schema, validate_record
from src.types import RadiomicMention, to_dict

IBSI_FEATURES = [
    {
        "canonical": "glcm_entropy",
        "ibsi_id": "IBSI:GLCM_ENTROPY",
        "aliases": ["glcm entropy", "haralick entropy", "co occurrence entropy", "co-occurrence entropy"],
    },
    {
        "canonical": "glcm_contrast",
        "ibsi_id": "IBSI:GLCM_CONTRAST",
        "aliases": ["glcm contrast", "haralick contrast", "texture contrast"],
    },
    {
        "canonical": "glcm_homogeneity",
        "ibsi_id": "IBSI:GLCM_HOMOGENEITY",
        "aliases": ["glcm homogeneity", "inverse difference moment", "homogeneity"],
    },
    {
        "canonical": "first_order_mean",
        "ibsi_id": "IBSI:FIRSTORDER_MEAN",
        "aliases": ["mean intensity", "first order mean", "average intensity", "mean"],
    },
    {
        "canonical": "first_order_skewness",
        "ibsi_id": "IBSI:FIRSTORDER_SKEWNESS",
        "aliases": ["skewness", "intensity skewness", "first order skewness"],
    },
    {
        "canonical": "first_order_kurtosis",
        "ibsi_id": "IBSI:FIRSTORDER_KURTOSIS",
        "aliases": ["kurtosis", "intensity kurtosis", "first order kurtosis"],
    },
    {
        "canonical": "shape_sphericity",
        "ibsi_id": "IBSI:SHAPE_SPHERICITY",
        "aliases": ["sphericity", "shape sphericity"],
    },
]

# BODYCOMP_FEATURES semantic mapping strategy:
# UMLS CUIs are the primary normalization standard, chosen over hardcoded SNOMED/LOINC because:
#   1. MINERVA uses UMLS CUIs — shared reference enables cross-graph node merging.
#   2. SNOMED/LOINC codes are cross-referenced within UMLS; using CUIs avoids dual-namespace fragmentation.
#   3. The running UMLSNormalizer (3.9M entity KB) already produces CUIs at inference time;
#      these static CUIs serve as expected-value anchors for known-good concepts.
# CUIs are best-effort mappings against UMLS 2022 KB. Verify with UMLS Metathesaurus browser if needed.
BODYCOMP_FEATURES = [
    {
        "canonical": "skeletal_muscle_index",
        "ontology_id": "BODYCOMP:SKELETAL_MUSCLE_INDEX",
        "umls_cui": "C1822407",  # Skeletal muscle mass ratio (best-effort; SMI not a direct UMLS concept)
        "aliases": ["skeletal muscle index", "smi"],
    },
    {
        "canonical": "visceral_adipose_tissue",
        "ontology_id": "BODYCOMP:VISCERAL_ADIPOSE_TISSUE",
        "umls_cui": "C1706244",  # Visceral Adipose Tissue
        "aliases": ["visceral adipose tissue", "visceral adiposity", "vat"],
    },
    {
        "canonical": "subcutaneous_adipose_tissue",
        "ontology_id": "BODYCOMP:SUBCUTANEOUS_ADIPOSE_TISSUE",
        "umls_cui": "C0282536",  # Subcutaneous adipose tissue
        "aliases": ["subcutaneous adipose tissue", "sat"],
    },
    {
        "canonical": "myosteatosis",
        "ontology_id": "BODYCOMP:MYOSTEATOSIS",
        "umls_cui": "C0948046",  # Fat infiltration of muscle
        "aliases": ["myosteatosis"],
    },
    {
        "canonical": "muscle_attenuation",
        "ontology_id": "BODYCOMP:MUSCLE_ATTENUATION",
        "umls_cui": "C0026845",  # Muscle atrophy (closest UMLS concept; CT-derived HU attenuation lacks direct CUI)
        "aliases": ["muscle attenuation"],
    },
    {
        "canonical": "psoas_area",
        "ontology_id": "BODYCOMP:PSOAS_AREA",
        "umls_cui": "C0032530",  # Psoas major
        "aliases": ["psoas area", "psoas muscle area"],
    },
    {
        "canonical": "liver_surface_nodularity",
        "ontology_id": "BODYCOMP:LIVER_SURFACE_NODULARITY",
        "umls_cui": "C3665309",  # Liver surface nodularity
        "aliases": ["liver surface nodularity"],
    },
    {
        "canonical": "sarcopenia",
        "ontology_id": "BODYCOMP:SARCOPENIA",
        "umls_cui": "C0872084",  # Sarcopenia
        "aliases": ["sarcopenia"],
    },
]

MODALITY_TERMS = {
    "ct": "CT",
    "computed tomography": "CT",
    "mri": "MRI",
    "magnetic resonance": "MRI",
    "pet": "PET",
    "pet/ct": "PET/CT",
    "ultrasound": "US",
    "radiograph": "XRAY",
    "x ray": "XRAY",
    "dxa": "DXA",
    "dexa": "DXA",
    "dual-energy x-ray absorptiometry": "DXA",
    "dual energy x-ray absorptiometry": "DXA",
    "absorptiometry": "DXA",
}

BODY_LOCATION_TERMS = [
    "liver",
    "lung",
    "pancreas",
    "kidney",
    "colon",
    "rectum",
    "brain",
    "prostate",
    "breast",
    "spleen",
    "heart",
    "aorta",
    "abdomen",
    "abdominal",
    "muscle",
    "muscular",
    "skeletal",
    "adipose",
    "bone",
    "cerebral",
    "waist",
    "lumbar",
    "vertebral",
    "spine",
    "spinal",
    "hip",
    "trunk",
    "femur",
    "femoral",
    "thigh",
]

# Single-token aliases are useful but highly ambiguous in clinical writing.
AMBIGUOUS_ALIASES = {
    "mean",
    "entropy",
    "contrast",
    "homogeneity",
    "inhomogeneity",
    "skewness",
    "kurtosis",
    "sphericity",
}

RADIOMICS_CONTEXT_TERMS = {
    "radiomics",
    "radiomic",
    "texture",
    "histogram",
    "first order",
    "first-order",
    "glcm",
    "glrlm",
    "glszm",
    "ngtdm",
    "gray level",
    "voxel",
    "pixel",
    "ibsi",
    "haralick",
    "feature",
    "features",
    "intensity",
    "attenuation",
    "adc",
    "suv",
}

BODYCOMP_CONTEXT_TERMS = {
    "body composition",
    "skeletal muscle",
    "muscle index",
    "adipose",
    "adiposity",
    "myosteatosis",
    "sarcopenia",
    "dxa",
    "dual-energy x-ray absorptiometry",
    "waist",
    "fat mass",
    "lean mass",
    "psoas",
}

MICROBIAL_SIGNATURE_TERMS = {
    "dysbiosis",
    "alpha diversity",
    "beta diversity",
    "microbial signature",
    "microbial signatures",
    "microbiota composition",
    "gut microbiota composition",
    "microbial community",
    "intratumoral microbiome",
    "microbiome abundance",
}

MICROBE_GENUS_TERMS = {
    "akkermansia",
    "bacteroides",
    "bifidobacterium",
    "bilophila",
    "christensenellaceae",
    "collinsella",
    "enterococcus",
    "escherichia",
    "fusobacterium",
    "helicobacter",
    "lactobacillus",
    "parabacteroides",
    "phascolarctobacterium",
    "porphyromonadaceae",
    "prevotella",
    "rikenellaceae",
    "roseburia",
    "ruminococcus",
    "streptococcus",
}

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

DISEASE_PATTERN = re.compile(
    r"\b([a-z][a-z\-]*(?:\s[a-z][a-z\-]*){0,4}\s(?:cancer|carcinoma|tumou?r|disease|syndrome|lesion|fibrosis|diabetes|obesity|cirrhosis|adenocarcinoma|inflammation))\b",
    re.IGNORECASE,
)


_ALIAS_TO_CANONICAL: dict[str, tuple[str, str, str, str]] = {}
for feat in IBSI_FEATURES:
    canonical = feat["canonical"]
    ontology_id = feat["ibsi_id"]
    for alias in feat["aliases"]:
        _ALIAS_TO_CANONICAL[alias.lower()] = (
            canonical,
            ontology_id,
            "radiomic",
            "RadiomicFeature",
        )

for feat in BODYCOMP_FEATURES:
    canonical = feat["canonical"]
    ontology_id = feat["ontology_id"]
    for alias in feat["aliases"]:
        _ALIAS_TO_CANONICAL[alias.lower()] = (
            canonical,
            ontology_id,
            "body_composition",
            "BodyCompositionFeature",
        )

_SORTED_ALIASES = sorted(_ALIAS_TO_CANONICAL.keys(), key=len, reverse=True)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _has_phenotype_context(text: str) -> bool:
    norm = _normalize_text(text)
    return any(term in norm for term in RADIOMICS_CONTEXT_TERMS | BODYCOMP_CONTEXT_TERMS)


def _is_ambiguous_alias_match_valid(sentence_norm: str, *, start: int, end: int, alias: str) -> bool:
    window_start = max(0, start - 40)
    window_end = min(len(sentence_norm), end + 40)
    window = sentence_norm[window_start:window_end]

    if alias == "mean":
        if re.search(r"\bmean\s+(?:age|follow-?up|survival|years?|months?|days?|hours?)\b", window):
            return False
        if not re.search(
            r"\b("
            r"mean intensity|mean adc|mean attenuation|mean suv|suvmean|"
            r"mean positive pixel|mean gray|mean grey|histogram mean|"
            r"first[- ]order mean|mean dose|mean signal|mean ct"
            r")\b",
            window,
        ):
            return False
        return True

    return _has_phenotype_context(window) or _has_phenotype_context(sentence_norm)


def split_sentences(text: str) -> list[str]:
    chunks = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    return chunks or ([text.strip()] if text.strip() else [])


def _detect_modality(text: str) -> str | None:
    norm = _normalize_text(text)
    for key, label in MODALITY_TERMS.items():
        if key in norm:
            return label
    return None


def _detect_body_location(text: str) -> str | None:
    norm = _normalize_text(text)
    for location in BODY_LOCATION_TERMS:
        if re.search(rf"\b{re.escape(location)}\b", norm):
            return location
    return None


_DISEASE_LEAD_STOPWORDS = {
    # Copulas / prepositions / conjunctions
    "is", "are", "was", "were", "in", "of", "with", "and", "or",
    "the", "a", "an", "this", "that", "at", "by", "but", "for",
    "from", "among", "against", "through", "during", "without",
    "between", "according", "depending", "either", "as", "like",
    "to", "when", "particularly", "independent", "indicate",
    # Section-header words that appear at sentence start in structured abstracts
    "abstract", "introduction", "aims", "aim", "background",
    "abbreviations", "discussion", "conclusion", "methods", "results",
    "objectives", "purpose", "summary",
    # Temporal / narrative fragment starters
    "early", "consequently", "subsequently", "regardless", "considering",
    "delays", "determine", "findings", "investigating", "following",
    # Population prefix starters (full phrases caught in assembly; single word caught here)
    "controls", "participants", "people", "samples", "subjects",
    # Measurement / technique starters
    "fold", "basal", "flaxseed", "androgen",
    # Existing
    "exercise", "dietary", "important", "related", "training",
    "such", "pepper", "including", "affecting",
    "induced", "associated", "effects", "role", "impact",
}
_DISEASE_CONTEXT_STOPWORDS = {
    "humans", "human", "patients", "subjects", "training",
    "distribution", "degree", "density", "components", "intake",
    "lessens", "reduces", "causes", "affects", "affected", "induced", "diet",
    "is", "are", "was", "were", "by", "via", "phenotype", "marker",
    "highlight", "highlights", "exposure", "supplementation", "substrate",
    "pathway", "pathways", "consequently", "regardless", "subsequently",
}


def _detect_disease(sentence: str, title: str) -> str | None:
    for source in (sentence, title):
        for match in DISEASE_PATTERN.finditer(source):
            candidate = _normalize_text(match.group(1))
            tokens = candidate.split()
            if not tokens:
                continue
            if tokens[0] in _DISEASE_LEAD_STOPWORDS:
                continue
            if len(tokens) > 3 and set(tokens[:-1]) & _DISEASE_CONTEXT_STOPWORDS:
                continue
            return candidate
    return None


def _detect_claim_hint(sentence: str, title: str) -> str | None:
    norm = _normalize_text(f"{title} {sentence}")
    if any(term in norm for term in {"predict", "predictive", "prediction"}):
        return "predictive"
    if any(term in norm for term in {"prognosis", "prognostic", "survival", "outcome"}):
        return "prognostic"
    if any(term in norm for term in {"diagnosis", "diagnostic", "detect", "detection"}):
        return "diagnostic"
    if any(term in norm for term in {"associate", "associated", "correlat", "linked", "relationship"}):
        return "association"
    return None


def _detect_microbe(sentence: str) -> str | None:
    for match in MICROBE_BINOMIAL_PATTERN.finditer(sentence):
        candidate = _normalize_text(match.group(1))
        words = candidate.split()
        if (
            words
            and words[0] in MICROBE_GENUS_TERMS
            and words[-1] not in MICROBE_STOPWORDS
        ):
            return candidate

    norm = _normalize_text(sentence)
    for genus in sorted(MICROBE_GENUS_TERMS):
        if re.search(rf"\b{re.escape(genus)}\b", norm):
            return genus
    return None


def _detect_microbial_signature(sentence: str) -> str | None:
    norm = _normalize_text(sentence)
    for term in sorted(MICROBIAL_SIGNATURE_TERMS, key=len, reverse=True):
        if term in norm:
            return term
    return None


def _detect_subject_node(sentence: str) -> tuple[str | None, str | None]:
    microbe = _detect_microbe(sentence)
    if microbe:
        return "Microbe", microbe

    signature = _detect_microbial_signature(sentence)
    if signature:
        return "MicrobialSignature", signature
    return None, None


def _exact_alias_matches(sentence: str) -> list[tuple[int, int, str, str, str, str, str]]:
    norm = _normalize_text(sentence)
    matches: list[tuple[int, int, str, str, str, str, str]] = []
    for alias in _SORTED_ALIASES:
        pattern = rf"\b{re.escape(alias)}\b"
        for hit in re.finditer(pattern, norm):
            if alias in AMBIGUOUS_ALIASES and not _is_ambiguous_alias_match_valid(
                norm, start=hit.start(), end=hit.end(), alias=alias
            ):
                continue
            canonical, ontology_id, feature_family, node_type = _ALIAS_TO_CANONICAL[alias]
            matches.append(
                (
                    hit.start(),
                    hit.end(),
                    alias,
                    canonical,
                    ontology_id,
                    feature_family,
                    node_type,
                )
            )

    # Dedupe overlaps by preferring longer spans first.
    matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    kept: list[tuple[int, int, str, str, str, str, str]] = []
    occupied: list[tuple[int, int]] = []
    for candidate in matches:
        start, end = candidate[0], candidate[1]
        overlap = any(not (end <= a or start >= b) for a, b in occupied)
        if overlap:
            continue
        kept.append(candidate)
        occupied.append((start, end))
    return kept


def _fuzzy_alias_match(sentence: str) -> list[tuple[int, int, str, str, str, str, str]]:
    norm = _normalize_text(sentence)
    if not _has_phenotype_context(norm):
        return []
    tokens = re.findall(r"[a-z0-9/\-]+", norm)
    if not tokens:
        return []

    alias_keys = list(_ALIAS_TO_CANONICAL.keys())
    best: tuple[int, int, str, str, str, str, str] | None = None

    for n in range(4, 1, -1):
        for i in range(0, len(tokens) - n + 1):
            phrase = " ".join(tokens[i : i + n])
            if len(phrase) < 6:
                continue
            close = difflib.get_close_matches(phrase, alias_keys, n=1, cutoff=0.92)
            if not close:
                continue
            alias = close[0]
            canonical, ontology_id, feature_family, node_type = _ALIAS_TO_CANONICAL[alias]
            start = norm.find(phrase)
            if start < 0:
                continue
            end = start + len(phrase)
            if alias in AMBIGUOUS_ALIASES and not _is_ambiguous_alias_match_valid(
                norm, start=start, end=end, alias=alias
            ):
                continue
            best = (
                start,
                end,
                phrase,
                canonical,
                ontology_id,
                feature_family,
                node_type,
            )
            break
        if best:
            break

    return [best] if best else []


def extract_mentions_from_paper(paper: dict[str, Any]) -> tuple[list[RadiomicMention], list[dict[str, Any]]]:
    pmid = str(paper.get("pmid") or "")
    title = str(paper.get("title") or "")
    content, source_text = paper_text(paper)

    mentions: list[RadiomicMention] = []
    mapping_logs: list[dict[str, Any]] = []

    for sent_idx, sentence in enumerate(split_sentences(content)):
        exact = _exact_alias_matches(sentence)
        matches = exact if exact else _fuzzy_alias_match(sentence)
        if not matches:
            continue

        modality = _detect_modality(sentence)
        body_location = _detect_body_location(sentence)
        disease = _detect_disease(sentence, title)
        claim_hint = _detect_claim_hint(sentence, title)
        subject_node_type, subject_node = _detect_subject_node(sentence)

        for start, end, raw, canonical, ontology_id, feature_family, node_type in matches:
            mapping_method = "exact" if exact else "fuzzy"
            confidence = 0.45
            confidence += 0.15 if mapping_method == "exact" else 0.05
            confidence += 0.15 if modality else 0.0
            confidence += 0.15 if body_location else 0.0
            confidence += 0.10 if disease else 0.0
            confidence += 0.05 if subject_node else 0.0
            confidence = float(min(1.0, confidence))

            mention_id = hashlib.sha1(
                f"{pmid}|{sent_idx}|{start}|{end}|{canonical}".encode("utf-8")
            ).hexdigest()[:16]

            mention = RadiomicMention(
                mention_id=mention_id,
                pmid=pmid,
                sentence=sentence,
                span_start=start,
                span_end=end,
                raw_feature=raw,
                canonical_feature=canonical,
                ibsi_id=ontology_id,
                confidence=confidence,
                mapping_method=mapping_method,
                evidence=f"PMID {pmid} sentence {sent_idx}",
                feature_family=feature_family,
                node_type=node_type,
                ontology_namespace="IBSI" if feature_family == "radiomic" else "BODYCOMP",
                modality=modality,
                body_location=body_location,
                disease=disease,
                claim_hint=claim_hint,
                subject_node_type=subject_node_type,
                subject_node=subject_node,
            )
            mentions.append(mention)
            mapping_logs.append(
                {
                    "mention_id": mention_id,
                    "pmid": pmid,
                    "raw_feature": raw,
                    "canonical_feature": canonical,
                    "ibsi_id": ontology_id,
                    "mapping_method": mapping_method,
                    "feature_family": feature_family,
                    "node_type": node_type,
                    "subject_node_type": subject_node_type,
                    "subject_node": subject_node,
                    "source_text": source_text,
                }
            )

    return mentions, mapping_logs


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rule-based radiomics mention extraction with IBSI mapping.")
    parser.add_argument("--papers", default="artifacts/papers.jsonl")
    parser.add_argument("--output", default="artifacts/text_mentions.jsonl")
    parser.add_argument("--mapping-log", default="artifacts/text_mapping_log.jsonl")
    parser.add_argument("--manifest-dir", default="artifacts/manifests")
    parser.add_argument("--validate-schema", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    papers = read_jsonl(args.papers)

    all_mentions: list[RadiomicMention] = []
    all_mapping_logs: list[dict[str, Any]] = []

    for paper in papers:
        mentions, mapping_logs = extract_mentions_from_paper(paper)
        all_mentions.extend(mentions)
        all_mapping_logs.extend(mapping_logs)

    if args.validate_schema:
        schema = load_schema("text_mentions.schema.json")
        for idx, mention in enumerate(all_mentions):
            try:
                validate_record(to_dict(mention), schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"text_mentions[{idx}] invalid: {exc}") from exc

    mention_count = write_jsonl(args.output, all_mentions)
    # Keep explicit append path for easy pipeline extension where multiple runs merge logs.
    write_jsonl(args.mapping_log, all_mapping_logs)

    metrics = {
        "papers_processed": len(papers),
        "mentions_emitted": mention_count,
        "unique_features": len({m.canonical_feature for m in all_mentions}),
        "with_modality": sum(1 for m in all_mentions if m.modality),
        "with_body_location": sum(1 for m in all_mentions if m.body_location),
        "with_disease": sum(1 for m in all_mentions if m.disease),
    }
    write_manifest(
        manifest_dir=args.manifest_dir,
        stage="extract_radiomics_text",
        params={"papers": args.papers},
        metrics=metrics,
        outputs={
            "text_mentions": str(Path(args.output).resolve()),
            "mapping_log": str(Path(args.mapping_log).resolve()),
        },
        command=" ".join(sys.argv),
    )

    print(json.dumps({"output": args.output, "metrics": metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
