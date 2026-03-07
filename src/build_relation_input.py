from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.artifact_utils import read_jsonl, write_jsonl, write_manifest
from src.schema_utils import SchemaValidationError, load_schema, validate_record
from src.types import RelationInputRecord, to_dict

GENERIC_MICROBE_TERMS = {"bacteria", "bacterias", "probiotic", "probiotics"}
GENERIC_DISEASE_TERMS = {"disease", "diseases"}


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _paper_index(papers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in papers:
        pmid = str(row.get("pmid") or "")
        if pmid:
            out[pmid] = row
    return out


def _feature_index(text_mentions: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for row in text_mentions:
        pmid = str(row.get("pmid") or "")
        feat = str(row.get("canonical_feature") or "").strip()
        if not pmid or not feat:
            continue
        bucket = out.setdefault(pmid, [])
        if feat not in bucket:
            bucket.append(feat)
    return out


def _extract_entities(entity: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = entity.get(key)
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        text = _normalize(str(row.get("text") or ""))
        if not text:
            continue
        payload = dict(row)
        payload["text"] = text
        out.append(payload)
    return out


def _filter_reason(
    *,
    sentence: str,
    subject_node_type: str,
    subject_node: str,
    disease: str,
    has_radiomics_context: bool,
    max_words: int,
    max_chars: int,
    require_radiomics_context: bool,
) -> str | None:
    if not sentence:
        return "missing_sentence"
    if len(sentence.split()) >= max_words:
        return "evidence_too_long_words"
    if len(sentence) >= max_chars:
        return "evidence_too_long_chars"
    if subject_node_type == "Microbe" and subject_node in GENERIC_MICROBE_TERMS:
        return "generic_microbe_term"
    if disease in GENERIC_DISEASE_TERMS:
        return "generic_disease_term"
    if require_radiomics_context and not has_radiomics_context:
        return "missing_radiomics_context"
    return None


def build_relation_rows(
    *,
    entity_sentences: list[dict[str, Any]],
    text_mentions: list[dict[str, Any]],
    papers: list[dict[str, Any]],
    max_words: int,
    max_chars: int,
    require_radiomics_context: bool,
) -> tuple[list[RelationInputRecord], dict[str, Any]]:
    features_by_pmid = _feature_index(text_mentions)
    papers_by_pmid = _paper_index(papers)

    rows: list[RelationInputRecord] = []
    reason_counts: dict[str, int] = {}

    for item in entity_sentences:
        pmid = str(item.get("pmid") or "")
        sentence = str(item.get("sentence") or "").strip()
        entity_sentence_id = str(item.get("record_id") or "") or None

        microbes = _extract_entities(item, "microbes")
        diseases = _extract_entities(item, "diseases")
        if not microbes or not diseases:
            reason_counts["missing_entities"] = reason_counts.get("missing_entities", 0) + 1
            continue

        features = features_by_pmid.get(pmid, [])
        has_radiomics_context = bool(features)

        paper = papers_by_pmid.get(pmid, {})
        impact_factor = paper.get("impact_factor")
        quartile = paper.get("quartile")

        for microbe in microbes:
            microbe_text = str(microbe.get("text") or "")
            subject_node_type = "Microbe"
            subject_node = microbe_text
            for disease in diseases:
                disease_text = str(disease.get("text") or "")
                reason = _filter_reason(
                    sentence=sentence,
                    subject_node_type=subject_node_type,
                    subject_node=subject_node,
                    disease=disease_text,
                    has_radiomics_context=has_radiomics_context,
                    max_words=max_words,
                    max_chars=max_chars,
                    require_radiomics_context=require_radiomics_context,
                )
                if reason is not None:
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
                    continue

                row_id = _stable_id(
                    pmid,
                    sentence,
                    microbe_text,
                    disease_text,
                    entity_sentence_id or "na",
                )
                rows.append(
                    RelationInputRecord(
                        row_id=row_id,
                        pmid=pmid,
                        sentence=sentence,
                        microbe=microbe_text,
                        disease=disease_text,
                        subject_node_type=subject_node_type,
                        subject_node=subject_node,
                        impact_factor=float(impact_factor) if isinstance(impact_factor, (int, float)) else None,
                        quartile=str(quartile) if quartile not in (None, "", "NA") else None,
                        entity_sentence_id=entity_sentence_id,
                        disease_cui=(str(disease.get("cui")) if disease.get("cui") else None),
                        microbe_cui=(str(microbe.get("cui")) if microbe.get("cui") else None),
                        radiomic_features=features or None,
                        has_radiomics_context=has_radiomics_context,
                        source="build_relation_input",
                    )
                )

    metrics = {
        "entity_sentences_in": len(entity_sentences),
        "text_mentions_in": len(text_mentions),
        "rows_out": len(rows),
        "filtered_reason_counts": reason_counts,
    }
    return rows, metrics


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build final relation_input rows from entity sentence extraction + radiomics mentions."
    )
    parser.add_argument("--entity-sentences", default="artifacts/entity_sentences.jsonl")
    parser.add_argument("--text-mentions", default="artifacts/text_mentions.jsonl")
    parser.add_argument("--papers", default="artifacts/papers.jsonl")
    parser.add_argument("--output", default="artifacts/relation_input.jsonl")
    parser.add_argument("--manifest-dir", default="artifacts/manifests")
    parser.add_argument("--max-evidence-words", type=int, default=500)
    parser.add_argument("--max-evidence-chars", type=int, default=5000)
    parser.add_argument("--allow-missing-radiomics-context", action="store_true")
    parser.add_argument("--validate-schema", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    entity_sentences = read_jsonl(args.entity_sentences) if Path(args.entity_sentences).exists() else []
    text_mentions = read_jsonl(args.text_mentions) if Path(args.text_mentions).exists() else []
    papers = read_jsonl(args.papers) if Path(args.papers).exists() else []

    rows, metrics = build_relation_rows(
        entity_sentences=entity_sentences,
        text_mentions=text_mentions,
        papers=papers,
        max_words=args.max_evidence_words,
        max_chars=args.max_evidence_chars,
        require_radiomics_context=not args.allow_missing_radiomics_context,
    )

    if args.validate_schema:
        schema = load_schema("relation_input.schema.json")
        for idx, row in enumerate(rows):
            try:
                validate_record(to_dict(row), schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"relation_input[{idx}] invalid: {exc}") from exc

    count = write_jsonl(args.output, rows)

    stage_metrics = {
        **metrics,
        "rows_written": count,
        "require_radiomics_context": not args.allow_missing_radiomics_context,
    }

    write_manifest(
        manifest_dir=args.manifest_dir,
        stage="build_relation_input",
        params={
            "entity_sentences": args.entity_sentences,
            "text_mentions": args.text_mentions,
            "papers": args.papers,
            "max_evidence_words": args.max_evidence_words,
            "max_evidence_chars": args.max_evidence_chars,
            "require_radiomics_context": not args.allow_missing_radiomics_context,
        },
        metrics=stage_metrics,
        outputs={"relation_input": str(Path(args.output).resolve())},
        command=" ".join(sys.argv),
    )

    print(json.dumps({"output": args.output, "metrics": stage_metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
