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
]

DISEASE_PATTERN = re.compile(
    r"\b([a-z][a-z\- ]{1,40}(?:cancer|carcinoma|tumou?r|disease|syndrome|lesion|fibrosis|diabetes|obesity|cirrhosis|adenocarcinoma|inflammation))\b",
    re.IGNORECASE,
)


_ALIAS_TO_CANONICAL: dict[str, tuple[str, str]] = {}
for feat in IBSI_FEATURES:
    canonical = feat["canonical"]
    ibsi_id = feat["ibsi_id"]
    for alias in feat["aliases"]:
        _ALIAS_TO_CANONICAL[alias.lower()] = (canonical, ibsi_id)

_SORTED_ALIASES = sorted(_ALIAS_TO_CANONICAL.keys(), key=len, reverse=True)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


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


def _detect_disease(sentence: str, title: str) -> str | None:
    for source in (sentence, title):
        match = DISEASE_PATTERN.search(source)
        if match:
            return _normalize_text(match.group(1))
    return None


def _exact_alias_matches(sentence: str) -> list[tuple[int, int, str, str, str]]:
    norm = _normalize_text(sentence)
    matches: list[tuple[int, int, str, str, str]] = []
    for alias in _SORTED_ALIASES:
        pattern = rf"\b{re.escape(alias)}\b"
        for hit in re.finditer(pattern, norm):
            canonical, ibsi_id = _ALIAS_TO_CANONICAL[alias]
            matches.append((hit.start(), hit.end(), alias, canonical, ibsi_id))

    # Dedupe overlaps by preferring longer spans first.
    matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    kept: list[tuple[int, int, str, str, str]] = []
    occupied: list[tuple[int, int]] = []
    for candidate in matches:
        start, end = candidate[0], candidate[1]
        overlap = any(not (end <= a or start >= b) for a, b in occupied)
        if overlap:
            continue
        kept.append(candidate)
        occupied.append((start, end))
    return kept


def _fuzzy_alias_match(sentence: str) -> list[tuple[int, int, str, str, str]]:
    norm = _normalize_text(sentence)
    tokens = re.findall(r"[a-z0-9/\-]+", norm)
    if not tokens:
        return []

    alias_keys = list(_ALIAS_TO_CANONICAL.keys())
    best: tuple[int, int, str, str, str] | None = None

    for n in range(4, 0, -1):
        for i in range(0, len(tokens) - n + 1):
            phrase = " ".join(tokens[i : i + n])
            close = difflib.get_close_matches(phrase, alias_keys, n=1, cutoff=0.90)
            if not close:
                continue
            alias = close[0]
            canonical, ibsi_id = _ALIAS_TO_CANONICAL[alias]
            start = norm.find(phrase)
            if start < 0:
                continue
            end = start + len(phrase)
            best = (start, end, phrase, canonical, ibsi_id)
            break
        if best:
            break

    return [best] if best else []


def extract_mentions_from_paper(paper: dict[str, Any]) -> tuple[list[RadiomicMention], list[dict[str, Any]]]:
    pmid = str(paper.get("pmid") or "")
    title = str(paper.get("title") or "")
    abstract = str(paper.get("abstract") or "")
    full_text = f"{title}. {abstract}".strip()

    mentions: list[RadiomicMention] = []
    mapping_logs: list[dict[str, Any]] = []

    for sent_idx, sentence in enumerate(split_sentences(full_text)):
        exact = _exact_alias_matches(sentence)
        matches = exact if exact else _fuzzy_alias_match(sentence)
        if not matches:
            continue

        modality = _detect_modality(sentence)
        body_location = _detect_body_location(sentence)
        disease = _detect_disease(sentence, title)

        for start, end, raw, canonical, ibsi_id in matches:
            mapping_method = "exact" if exact else "fuzzy"
            confidence = 0.45
            confidence += 0.15 if mapping_method == "exact" else 0.05
            confidence += 0.15 if modality else 0.0
            confidence += 0.15 if body_location else 0.0
            confidence += 0.10 if disease else 0.0
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
                ibsi_id=ibsi_id,
                confidence=confidence,
                mapping_method=mapping_method,
                evidence=f"PMID {pmid} sentence {sent_idx}",
                modality=modality,
                body_location=body_location,
                disease=disease,
            )
            mentions.append(mention)
            mapping_logs.append(
                {
                    "mention_id": mention_id,
                    "pmid": pmid,
                    "raw_feature": raw,
                    "canonical_feature": canonical,
                    "ibsi_id": ibsi_id,
                    "mapping_method": mapping_method,
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
